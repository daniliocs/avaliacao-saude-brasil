"""
tests/test_oncologia_tfd.py

Testes automatizados para a ingestão, cálculo de indicadores e integração
da Linha de Cuidado Oncológico & Alta Complexidade (CACON/UNACON / TFD) — Fase 2.
"""

import json
import os
import pandas as pd
import pytest

PATH_ONCOLOGIA = os.path.join("data", "processed", "indicadores_oncologia_tfd.parquet")
PATH_INDICE = os.path.join("data", "processed", "indice_saude_municipal.parquet")
PATH_MAPA_RESUMO = os.path.join("site", "data", "releases", "latest", "mapa_resumo.json")


@pytest.fixture(scope="module")
def df_onco():
    if not os.path.exists(PATH_ONCOLOGIA):
        from pipeline.indicators.oncologia_tfd import calcular_indicadores_oncologia
        return calcular_indicadores_oncologia()
    return pd.read_parquet(PATH_ONCOLOGIA)


@pytest.fixture(scope="module")
def df_indice():
    return pd.read_parquet(PATH_INDICE)


def test_cardinalidade_e_unicidade(df_onco):
    assert len(df_onco) == 5570
    assert df_onco["ibge7"].nunique() == 5570
    assert df_onco["ibge6"].nunique() == 5570


def test_escore_oncologia_limites(df_onco):
    assert df_onco["escore_oncologia"].min() >= 0.0
    # Calibração rigorosa: nenhum município atinge 100 absoluto
    assert df_onco["escore_oncologia"].max() <= 90.0
    assert df_onco["escore_oncologia"].notna().all()
    assert "tx_cancer_prem_bayes" in df_onco.columns
    assert df_onco["tx_cancer_prem_bayes"].notna().all()


def test_polos_cacon_unacon(df_onco):
    polos = df_onco[df_onco["eh_polo_onco"]]
    # Existem mais de 150 municípios polos com centros CACON/UNACON no Brasil
    assert len(polos) >= 150
    # Polos devem ter distância viária 0.0 km
    assert (polos["dist_cacon_km"] == 0.0).all()
    # Todas as distâncias devem ser não-negativas
    assert (df_onco["dist_cacon_km"] >= 0.0).all()
    assert (df_onco["tempo_cacon_min"] >= 10).all()


def test_tratamentos_de_ponta_capacidades(df_onco):
    for col in ("polo_tipo_centro", "polo_imunoterapia_alvo", "polo_radio_avancada", "polo_cirurgia_onco", "polo_onco_pediatrica", "polo_hematologia_tmo"):
        assert col in df_onco.columns
        assert df_onco[col].notna().all()

    # Polos CACON de referência devem ter imunoterapia e radioterapia ativas
    for ibge in ["4106902", "3550308", "3106200"]:
        row = df_onco[df_onco["ibge7"].astype(str) == ibge].iloc[0]
        assert row["polo_tipo_centro"] == "CACON (Centro Integral)"
        assert row["polo_imunoterapia_alvo"] is True or row["polo_imunoterapia_alvo"] == 1
        assert row["polo_radio_avancada"] is True or row["polo_radio_avancada"] == 1


def test_lei_60_dias_plausibilidade(df_onco):
    # Cumprimento da Lei dos 60 dias (Lei 12.732/2012)
    assert (df_onco["pct_60d_onco"] >= 0.0).all()
    assert (df_onco["pct_60d_onco"] <= 100.0).all()
    # Média nacional esperada entre 50% e 75%
    media_nac = df_onco["pct_60d_onco"].mean()
    assert 50.0 <= media_nac <= 75.0

    # Tempo mediano de fila pós-biópsia (nenhum município pode ter fila 0 dias)
    assert (df_onco["tempo_mediano_onco_dias"] >= 15.0).all()
    assert df_onco["tempo_mediano_onco_dias"].median() < 120.0

    # Os 10 primeiros colocados em Oncologia devem ser obrigatoriamente Polos Habilitados com retenção local
    top10 = df_onco.sort_values("escore_oncologia", ascending=False).head(10)
    assert top10["eh_polo_onco"].all()
    assert (top10["pct_fora"] < 20.0).all()

    # Passos (Polo CACON) deve ter nota superior a municípios dependentes de TFD da mesma região (ex: Itaú de Minas)
    s_passos = df_onco[df_onco["ibge6"].astype(str) == "314790"]["escore_oncologia"].iloc[0]
    s_itau = df_onco[df_onco["ibge6"].astype(str) == "313375"]["escore_oncologia"].iloc[0]
    assert s_passos > s_itau


def test_deslocamento_tfd_e_casos(df_onco):
    # Polos como SP, Curitiba, BH devem ter retenção local (baixa saída para fora)
    for ibge_polo in ["3550308", "4106902", "3106200"]:
        row = df_onco[df_onco["ibge7"].astype(str) == ibge_polo].iloc[0]
        assert row["eh_polo_onco"] is True or row["eh_polo_onco"] == 1
        assert row["pct_fora"] < 10.0

    # Total de casos válidos no triênio
    assert df_onco["casos_total"].sum() > 500_000


def test_integracao_indice_e_rankings(df_indice):
    assert "escore_oncologia" in df_indice.columns
    assert "rank_onco" in df_indice.columns
    assert "nota_integrada" in df_indice.columns
    assert "posicao_nacional_integrada" in df_indice.columns
    assert df_indice["escore_oncologia"].notna().all()
    assert df_indice["rank_onco"].notna().all()
    assert df_indice["nota_integrada"].notna().all()
    assert df_indice["nota_integrada"].min() >= 0.0
    assert df_indice["nota_integrada"].max() <= 100.0
    assert df_indice["rank_onco"].min() == 1


def test_payload_site_mapa_resumo():
    assert os.path.exists(PATH_MAPA_RESUMO)
    with open(PATH_MAPA_RESUMO, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 5570
    for ibge in ["4106902", "3550308", "3106200"]:
        item = data[ibge]
        assert "escore_oncologia" in item
        assert "nota_integrada" in item
        assert "oncologia_tfd" in item
        onco = item["oncologia_tfd"]
        assert "cacon_referencia" in onco
        assert "pct_60d_onco" in onco
        assert "dist_cacon_km" in onco
        assert "polo_imunoterapia_alvo" in onco
        assert "polo_tipo_centro" in onco
