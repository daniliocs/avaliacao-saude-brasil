"""Testes das funções estatísticas puras (sem dependência de dados)."""
import numpy as np
import pandas as pd
import pytest

from pipeline.indicators.estatistica import ic_poisson, ic_wilson, limites_percentis, normalizar, suavizar_eb


def test_ic_poisson_zero_eventos_limite_inferior_zero_e_superior_conhecido():
    lo, hi = ic_poisson(0, 1000)
    assert float(lo) == 0.0
    # chi2.ppf(0.975, 2)/(2*1000)*1000 = 3.6889
    assert float(hi) == pytest.approx(3.689, abs=1e-3)


def test_ic_poisson_contem_taxa_bruta_e_estreita_com_n_maior():
    k, n = 10, 1000
    lo, hi = ic_poisson(k, n)
    taxa = k / n * 1000
    assert float(lo) < taxa < float(hi)
    lo2, hi2 = ic_poisson(k * 10, n * 10)
    assert float(hi2 - lo2) < float(hi - lo)


def test_ic_poisson_base_zero_retorna_nan():
    lo, hi = ic_poisson(0, 0)
    assert np.isnan(lo) and np.isnan(hi)


def test_ic_wilson_limites_e_cobertura():
    lo, hi = ic_wilson(50, 100)
    assert 0 <= float(lo) < 50 < float(hi) <= 100
    lo, hi = ic_wilson(100, 100)
    assert float(hi) == pytest.approx(100.0, abs=1e-6)
    assert float(lo) > 90
    lo, hi = ic_wilson(0, 0)
    assert np.isnan(lo)


def test_suavizar_eb_encolhe_pequenos_denominadores_e_preserva_grandes():
    # grupo com taxa média ~10%; município pequeno com taxa bruta 50% deve ser puxado para a média
    eventos = pd.Series([5, 1000, 900, 1100, 1000])
    base = pd.Series([10, 10000, 10000, 10000, 10000])
    grupo = pd.Series(["A"] * 5)
    s = suavizar_eb(eventos, base, grupo, fator=1.0)
    bruta = eventos / base
    assert s.iloc[0] < bruta.iloc[0]               # encolhido
    assert abs(s.iloc[1] - bruta.iloc[1]) < 0.01   # grande: quase igual à bruta


def test_suavizar_eb_base_zero_recebe_taxa_do_grupo_sem_nan():
    s = suavizar_eb(pd.Series([0, 10, 20]), pd.Series([0, 100, 200]), pd.Series(["A", "A", "A"]), fator=1.0)
    assert s.notna().all()


def test_normalizar_maior_melhor_menor_melhor_e_saturacao():
    x = pd.Series([0.0, 50.0, 100.0, 150.0, -10.0])
    mm = normalizar(x, pior=0.0, melhor=100.0)
    assert list(mm) == [0.0, 50.0, 100.0, 100.0, 0.0]
    me = normalizar(x, pior=100.0, melhor=0.0)
    assert list(me) == [100.0, 50.0, 0.0, 0.0, 100.0]


def test_normalizar_preserva_nan_sem_imputar():
    r = normalizar(pd.Series([np.nan, 5.0]), 0.0, 10.0)
    assert np.isnan(r.iloc[0]) and r.iloc[1] == 50.0


def test_normalizar_limites_identicos_levanta_erro():
    with pytest.raises(ValueError):
        normalizar(pd.Series([1.0]), 3.0, 3.0)


def test_limites_percentis_sentidos():
    s = pd.Series(np.arange(1000, dtype=float))
    pior, melhor = limites_percentis(s, "maior_melhor", 5, 95)
    assert pior < melhor
    pior, melhor = limites_percentis(s, "menor_melhor", 5, 95)
    assert pior > melhor


def test_limites_percentis_amostra_insuficiente_e_distribuicao_degenerada():
    with pytest.raises(ValueError):
        limites_percentis(pd.Series(np.arange(10, dtype=float)), "maior_melhor")
    with pytest.raises(ValueError):
        limites_percentis(pd.Series(np.ones(500)), "maior_melhor")
