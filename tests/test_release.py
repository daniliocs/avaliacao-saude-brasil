"""
Testes de integração: validam os ARTEFATOS gerados pelo pipeline e os payloads do site.
Pulados automaticamente se os artefatos ainda não existem (ex.: CI sem dados).
Cobrem as regras inegociáveis 3 (rastreabilidade) e 4 (Nota Geral nunca sozinha).
"""
import json
import os

import numpy as np
import pandas as pd
import pytest

INDICE = os.path.join("data", "processed", "indice_saude_municipal.parquet")
SERIE = os.path.join("data", "processed", "serie_anual_sim_sinasc.parquet")
MAPA = os.path.join("site", "data", "releases", "latest", "mapa_resumo.json")
RANK = os.path.join("site", "data", "releases", "latest", "rankings_resumo.json")
LIM = os.path.join("config", "limites_calculados.json")
VERSAO = os.path.join("config", "metodologia_versao.txt")
RAW_DATASUS = os.path.join("data", "raw", "datasus")

pytestmark = pytest.mark.integracao

CAMPOS_AUDITORIA = ["fonte_id", "periodo_vintage", "data_coleta", "versao_metodologia", "qualidade_dado"]


@pytest.fixture(scope="module")
def df():
    if not os.path.exists(INDICE):
        pytest.skip("índice não gerado")
    return pd.read_parquet(INDICE)


@pytest.fixture(scope="module")
def mapa():
    if not os.path.exists(MAPA):
        pytest.skip("mapa_resumo.json não gerado")
    with open(MAPA, encoding="utf-8") as f:
        return json.load(f)


def test_cardinalidade_e_unicidade(df):
    assert len(df) == 5570
    assert df["ibge7"].is_unique and df["ibge6"].is_unique
    assert df["ibge7"].str.len().eq(7).all() and df["ibge6"].str.len().eq(6).all()


def test_notas_dentro_de_0_100(df):
    for c in ("nota_geral", "d1_nota", "d2_nota", "d3_nota"):
        v = df[c].dropna()
        assert ((v >= 0) & (v <= 100)).all(), c


def test_nota_geral_so_existe_com_tres_dimensoes(df):
    com_nota = df[df["nota_geral"].notna()]
    assert com_nota[["d1_nota", "d2_nota", "d3_nota"]].notna().all().all()
    sem_nota = df[df["nota_geral"].isna()]
    assert (sem_nota["status"] == "sem_classificacao").all()
    assert (sem_nota["motivo_sem_classificacao"].str.len() > 0).all()


def test_nota_geral_e_media_das_dimensoes_com_pesos_iguais(df):
    c = df[df["status"] == "classificado"]
    esperado = (c["d1_nota"] + c["d2_nota"] + c["d3_nota"]) / 3
    assert (c["nota_geral"] - esperado).abs().max() < 0.06   # arredondamento de 1 casa


def test_posicoes_consistentes_com_classificados(df):
    c = df[df["status"] == "classificado"]
    n = len(c)
    assert c["posicao_nacional"].min() == 1 and c["posicao_nacional"].max() <= n
    assert df.loc[df["status"] != "classificado", "posicao_nacional"].isna().all()
    # posição é monotônica na nota
    ordenado = c.sort_values("nota_geral", ascending=False)
    assert ordenado["posicao_nacional"].is_monotonic_increasing
    # faixa contém a posição
    assert (c["faixa_posicao_min"] <= c["posicao_nacional"]).all()
    assert (c["faixa_posicao_max"] >= c["posicao_nacional"]).all()


def test_sem_imputacao_componente_ausente_gera_nan_no_escore(df):
    for col, esc in [
        ("cob_vac_composta", "escore_D2_3"),
        ("tx_prof_ch", "escore_D3_2"),
        ("cob_esf", "escore_D3_3"),
        ("tx_leito_sus_reg", "escore_D3_1"),
    ]:
        assert df.loc[df[col].isna(), esc].isna().all(), f"{esc} foi preenchido apesar de {col} ausente"


def test_contagens_e_taxas_nao_negativas(df):
    for c in ("d1_1_obitos", "d1_1_nv", "d1_2_obitos", "d1_2_nv", "d2_2_validas", "d2_2_7mais"):
        assert (df[c] >= 0).all(), c
    for c in ("tmi_bruta", "tmi_bayes", "rmm_bruta", "rmm_bayes", "pre7_pct"):
        assert (df[c].dropna() >= 0).all(), c
    assert (df["d2_2_7mais"] <= df["d2_2_validas"]).all()
    assert (df["d2_2_validas"] <= df["d2_2_nv"]).all()
    assert (df["pre7_pct"].dropna() <= 100).all()


def test_ic_contem_taxa_bruta(df):
    ok = df["tmi_bruta"].notna()
    assert (df.loc[ok, "tmi_ic95_min"] <= df.loc[ok, "tmi_bruta"] + 1e-9).all()
    assert (df.loc[ok, "tmi_ic95_max"] >= df.loc[ok, "tmi_bruta"] - 1e-9).all()


def test_totais_da_serie_batem_com_microdados_brutos():
    """Conservação: soma de nascidos vivos da série == registros SINASC com município válido."""
    if not os.path.exists(SERIE):
        pytest.skip("série não gerada")
    serie = pd.read_parquet(SERIE)
    dim = pd.read_parquet(os.path.join("data", "processed", "dim_municipio.parquet"))
    validos = set(dim["ibge6"])
    for ano in sorted(serie["ano"].unique()):
        bruto = pd.read_parquet(os.path.join(RAW_DATASUS, f"sinasc_{ano}.parquet"), columns=["CODMUNRES"])
        esperado = bruto["CODMUNRES"].str[:6].isin(validos).sum()
        assert int(serie.loc[serie["ano"] == ano, "nascidos_vivos"].sum()) == int(esperado), ano


def test_limites_congelados_correspondem_a_versao_vigente():
    if not os.path.exists(LIM):
        pytest.skip("limites não gerados")
    with open(LIM, encoding="utf-8") as f:
        lim = json.load(f)
    with open(VERSAO, encoding="utf-8-sig") as f:
        assert lim["versao"] == f.read().strip()
    for ind, d in lim["limites"].items():
        assert d["pior"] != d["melhor"], ind


def test_payload_toda_nota_vem_com_dimensoes_e_faixa(mapa):
    for m in mapa.values():
        if m["nota_geral"] is not None:
            assert m["d1_nota"] is not None and m["d2_nota"] is not None and m["d3_nota"] is not None
            assert m["faixa_posicao_min"] is not None and m["faixa_posicao_max"] is not None
            assert m["status"] == "classificado"
        else:
            assert m["status"] == "sem_classificacao"
            assert m.get("motivo_sem_classificacao")


def test_payload_todo_indicador_numerico_tem_metadados_de_rastreabilidade(mapa):
    """Regra 3: nenhum número sem fonte, período, data de coleta, versão e selo."""
    for ibge, m in mapa.items():
        for ind, item in m["indicadores"].items():
            if item is None or item.get("valor") is None:
                continue
            for campo in CAMPOS_AUDITORIA:
                assert item.get(campo), f"{ibge}/{ind}: campo '{campo}' ausente"
            assert item["data_coleta"] and item["data_coleta"] != "2026-10-23", f"{ibge}/{ind}: data_coleta fixa/legada"


def test_payload_fonte_do_d1_1_nao_e_rotulada_como_registro_civil(mapa):
    m = next(iter(mapa.values()))
    assert m["indicadores"]["D1.1"]["fonte_id"] in ("sim_do",)
    assert "SINASC" in m["indicadores"]["D1.1"].get("fonte_detalhe", "")


def test_d4_e_camada_privada_fora_da_nota(mapa):
    m = next(m for m in mapa.values() if m["status"] == "classificado")
    assert "d4_contexto" in m and "camada_privada" in m
    assert not any(k.startswith("PRIV") or k.startswith("D4") for k in m["indicadores"])


def test_rankings_top100_estados_e_capitais():
    if not os.path.exists(RANK):
        pytest.skip("rankings_resumo.json não gerado")
    with open(RANK, encoding="utf-8") as f:
        r = json.load(f)
    assert len(r.get("top100_brasil_melhores", [])) == 100
    assert len(r.get("ranking_estados", [])) == 27
    assert len(r.get("ranking_capitais", [])) == 27
    for est in r["ranking_estados"]:
        assert "lat" in est and "lng" in est and est["media_escore_uf"] is not None
    for cap in r["ranking_capitais"]:
        assert "lat" in cap and "lng" in cap and cap["escore"] is not None
