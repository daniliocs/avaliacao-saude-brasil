"""
tests/test_vacinas.py

Testes de integridade, cálculo e rastreabilidade para o indicador D2.3
(Cobertura Vacinal Infantil Composta por 6 Vacinas Estratégicas do 1º ano)
e para a camada informativa das vacinas complementares e HPV (Meninas e Meninos).
"""

import json
import os
import numpy as np
import pandas as pd
import pytest

PROCESSED_PARQUET = os.path.join("data", "processed", "indice_saude_municipal.parquet")
MAPA_RESUMO_JSON = os.path.join("site", "data", "releases", "latest", "mapa_resumo.json")
HPV_RAW_PARQUET = os.path.join("data", "raw", "pni", "hpv_municipios.parquet")


@pytest.fixture(scope="module")
def df_indice():
    assert os.path.exists(PROCESSED_PARQUET), f"Arquivo não encontrado: {PROCESSED_PARQUET}"
    return pd.read_parquet(PROCESSED_PARQUET)


@pytest.fixture(scope="module")
def mapa_resumo():
    assert os.path.exists(MAPA_RESUMO_JSON), f"Arquivo não encontrado: {MAPA_RESUMO_JSON}"
    with open(MAPA_RESUMO_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def test_cardinalidade_e_completude_6_vacinas(df_indice):
    """Verifica que as 6 vacinas do 1º ano de vida estão presentes e sem NaNs para os 5.570 municípios."""
    vacinas_6 = [
        "cob_vac_polio", "cob_vac_penta", "cob_vac_tvd1",
        "cob_vac_pneumo", "cob_vac_menin", "cob_vac_rota"
    ]
    for v in vacinas_6:
        assert v in df_indice.columns, f"Coluna ausente: {v}"
        assert df_indice[v].notna().sum() == 5570, f"Coluna {v} possui valores ausentes"
        assert (df_indice[v] >= 0).all(), f"Coluna {v} possui valores negativos"


def test_calculo_exato_media_composta_6_vacinas(df_indice):
    """Verifica que cob_vac_composta é rigorosamente a média aritmética simples das 6 vacinas estratégicas."""
    vacinas_6 = [
        "cob_vac_polio", "cob_vac_penta", "cob_vac_tvd1",
        "cob_vac_pneumo", "cob_vac_menin", "cob_vac_rota"
    ]
    media_calculada = df_indice[vacinas_6].mean(axis=1)
    diferenca_max = (df_indice["cob_vac_composta"] - media_calculada).abs().max()
    assert diferenca_max < 1e-4, f"Diferença no cálculo da média composta: {diferenca_max}"


def test_vacinas_complementares_informativas(df_indice):
    """Verifica que BCG, HepA e HepB estão presentes para todos os municípios."""
    for col in ["cob_vac_bcg", "cob_vac_hepa", "cob_vac_hepb"]:
        assert col in df_indice.columns, f"Coluna complementar ausente: {col}"
        assert df_indice[col].notna().sum() == 5570, f"Coluna {col} com NaNs"


def test_hpv_meninas_e_meninos_segregacao(df_indice):
    """Verifica cobertura de HPV por sexo com dados censitários oficiais do InfoMS."""
    hpv_cols = [
        "hpv_cob_meninas", "hpv_cob_meninos", "hpv_cob_total",
        "hpv_doses_meninas", "hpv_doses_meninos", "hpv_pop_meninas", "hpv_pop_meninos"
    ]
    for c in hpv_cols:
        assert c in df_indice.columns, f"Coluna HPV ausente: {c}"
        assert df_indice[c].notna().sum() == 5570, f"Coluna HPV {c} possui valores ausentes"

    # Médias nacionais dentro de faixas epidemiológicas plausíveis (70% - 95%)
    assert 75.0 <= df_indice["hpv_cob_meninas"].mean() <= 95.0
    assert 70.0 <= df_indice["hpv_cob_meninos"].mean() <= 90.0
    assert (df_indice["hpv_doses_meninas"] >= 0).all()
    assert (df_indice["hpv_doses_meninos"] >= 0).all()


def test_payload_site_detalhes_vacinas(mapa_resumo):
    """Verifica que o payload JSON do site contém o dicionário detalhes_vacinas para todos os municípios."""
    assert len(mapa_resumo) == 5570
    chaves_esperadas = [
        "cob_vac_composta", "polio", "penta", "tvd1", "pneumo", "menin", "rota",
        "bcg", "hepa", "hepb", "hpv_meninas", "hpv_meninos", "hpv_total",
        "hpv_doses_meninas", "hpv_doses_meninos"
    ]
    for ibge7, mun in mapa_resumo.items():
        detalhes = mun.get("detalhes_vacinas")
        assert detalhes is not None, f"detalhes_vacinas ausente no município {ibge7}"
        for k in chaves_esperadas:
            assert k in detalhes, f"Chave {k} ausente em detalhes_vacinas para {ibge7}"
            assert detalhes[k] is not None, f"Chave {k} é None para {ibge7}"
