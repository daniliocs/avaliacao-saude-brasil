"""Testes das definições de caso (SIM/SINASC) com dados sintéticos."""
import pandas as pd

from pipeline.indicators.sim_sinasc import eh_obito_infantil, eh_obito_materno


def _sim(**kw):
    base = {"IDADE": "401", "TIPOBITO": "2", "SEXO": "1", "CAUSABAS": "I10"}
    base.update(kw)
    return pd.DataFrame([base])


def test_obito_infantil_unidades_de_tempo():
    for idade, esperado in [("101", True), ("205", True), ("311", True), ("401", False), ("501", False), ("000", False)]:
        assert bool(eh_obito_infantil(_sim(IDADE=idade)).iloc[0]) is esperado, idade


def test_obito_infantil_exclui_obito_fetal():
    assert not bool(eh_obito_infantil(_sim(IDADE="205", TIPOBITO="1")).iloc[0])


def test_obito_materno_capitulo_o_exclui_tardias_e_homens():
    ok = _sim(SEXO="2", CAUSABAS="O721", IDADE="428")
    assert bool(eh_obito_materno(ok).iloc[0])
    assert not bool(eh_obito_materno(_sim(SEXO="2", CAUSABAS="O96", IDADE="428")).iloc[0])
    assert not bool(eh_obito_materno(_sim(SEXO="2", CAUSABAS="O970", IDADE="428")).iloc[0])
    assert not bool(eh_obito_materno(_sim(SEXO="1", CAUSABAS="O721", IDADE="428")).iloc[0])
    assert not bool(eh_obito_materno(_sim(SEXO="2", CAUSABAS="I10", IDADE="428")).iloc[0])
    assert not bool(eh_obito_materno(_sim(SEXO="2", CAUSABAS="O721", TIPOBITO="1")).iloc[0])
