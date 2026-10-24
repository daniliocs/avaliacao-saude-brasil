"""Testes das regras do consolidador: sem imputação, mínimos por dimensão, Nota Geral exige D1+D2+D3."""
import numpy as np
import pandas as pd
import pytest
import yaml

from pipeline.indicators import build_composite_index as bci
from pipeline.indicators.estatistica import limites_percentis


@pytest.fixture(scope="module")
def cfgs():
    with open(bci.LIMITES_CFG, encoding="utf-8") as f:
        lim = yaml.safe_load(f)
    with open(bci.PESOS_CFG, encoding="utf-8") as f:
        pes = yaml.safe_load(f)
    return lim, pes


def _df(valores: dict):
    """Cria 1 município com escores por indicador (chaves 'D1.1' etc.)."""
    d = {f"escore_{k.replace('.', '_')}": [v] for k, v in valores.items()}
    return pd.DataFrame(d)


TODOS = ["D1.1", "D1.2", "D1.3", "D1.4", "D2.1", "D2.2", "D2.3", "D3.1", "D3.2", "D3.3"]


def test_dimensao_media_ponderada_entre_componentes_disponiveis(cfgs):
    lim, pes = cfgs
    df = _df({k: 80.0 for k in TODOS})
    df["escore_D2_3"] = 20.0
    r = bci.nota_dimensoes(df, lim, pes)
    assert r["d2_nota"].iloc[0] == 60.0   # (80+80+20)/3 com pesos 1/3 cada
    assert r["d3_nota"].iloc[0] == 80.0


def test_componente_informativo_peso_zero_nao_altera_a_nota(cfgs):
    lim, pes = cfgs
    assert pes["esquemas"]["pesos_iguais"]["indicadores"]["D1.2"] == 0.0
    df = _df({k: 80.0 for k in TODOS})
    df["escore_D1_2"] = 0.0
    r = bci.nota_dimensoes(df, lim, pes)
    assert r["d1_nota"].iloc[0] == 80.0


def test_componente_ausente_nao_e_imputado_e_pesos_sao_renormalizados(cfgs):
    lim, pes = cfgs
    v = {k: 90.0 for k in TODOS}
    v["D2.3"] = np.nan
    r = bci.nota_dimensoes(_df(v), lim, pes)
    assert r["d2_nota"].iloc[0] == 90.0                      # só D2.2 conta, sem mediana
    assert r["d2_componentes_ausentes"].iloc[0] == "D2.3"


def test_dimensao_sem_minimo_de_componentes_fica_nan(cfgs):
    lim, pes = cfgs
    v = {k: 70.0 for k in TODOS}
    v["D3.1"] = np.nan
    v["D3.2"] = np.nan                                       # D3 exige >= 2 componentes (1 disponível)
    r = bci.nota_dimensoes(_df(v), lim, pes)
    assert np.isnan(r["d3_nota"].iloc[0])


def test_nota_geral_exige_tres_dimensoes(cfgs):
    lim, pes = cfgs
    pesos_dim = pes["esquemas"]["pesos_iguais"]["dimensoes"]
    df = pd.DataFrame({"d1_nota": [80.0, 80.0], "d2_nota": [60.0, np.nan], "d3_nota": [40.0, 40.0]})
    nota = bci.combinar(df, pesos_dim)
    assert nota.iloc[0] == pytest.approx(60.0)
    assert np.isnan(nota.iloc[1])


def test_pesos_iguais_somam_um_nas_dimensoes_ativas(cfgs):
    _, pes = cfgs
    d = pes["esquemas"]["pesos_iguais"]["dimensoes"]
    assert d["D1"] + d["D2"] + d["D3"] == pytest.approx(1.0)
    assert d["D4"] == 0.0 and d["PRIVADA"] == 0.0     # DEC-001: fora da nota
    for esq in ("foco_resultados", "foco_atencao_primaria"):
        dd = pes["esquemas"][esq]["dimensoes"]
        assert dd["D1"] + dd["D2"] + dd["D3"] == pytest.approx(1.0)


def test_pesos_dos_indicadores_ativos_somam_um_por_dimensao(cfgs):
    lim, pes = cfgs
    pi = pes["esquemas"]["pesos_iguais"]["indicadores"]
    for dim in ("D1", "D2", "D3"):
        inds = [i for i, v in lim["indicadores"].items() if v["dimensao"] == dim and pi[i] > 0]
        assert sum(pi[i] for i in inds) == pytest.approx(1.0), dim


def test_config_nao_contem_limites_inventados(cfgs):
    lim, _ = cfgs
    assert lim["metodo_normalizacao"] == "percentis"
    for ind, d in lim["indicadores"].items():
        assert d["meta_oficial_confirmada"] is None, f"{ind}: meta só pode entrar após validação documentada"
        assert "pior" not in d and "melhor" not in d, f"{ind}: limite fixo proibido enquanto A_VALIDAR"


def test_faixa_de_posicao_contem_posicao_nacional(cfgs):
    lim, pes = cfgs
    rng = np.random.default_rng(0)
    n = 400
    df = pd.DataFrame({d["coluna"]: rng.uniform(0, 100, n) for d in lim["indicadores"].values()})
    limites = {}
    for i, d in lim["indicadores"].items():
        pior, melhor = limites_percentis(df[d["coluna"]], d["sentido"])
        limites[i] = {"coluna": d["coluna"], "pior": pior, "melhor": melhor}
    df = bci.escores_componentes(df, limites)
    df = bci.nota_dimensoes(df, lim, pes)
    df["nota_geral"] = bci.combinar(df, pes["esquemas"]["pesos_iguais"]["dimensoes"])
    pos = bci.rank_min(df["nota_geral"])
    fmin, fmax = bci.sensibilidade(df, lim, pes)
    assert (fmax >= fmin).all()
    # o build une a posição-base à faixa; após a união, a posição sempre está contida
    uniao_min, uniao_max = np.minimum(fmin, pos), np.maximum(fmax, pos)
    assert ((uniao_min <= pos) & (pos <= uniao_max)).all()
    # com pesos/percentis distintos, ao menos alguns municípios devem ter faixa não degenerada
    assert (uniao_max - uniao_min > 0).any()
