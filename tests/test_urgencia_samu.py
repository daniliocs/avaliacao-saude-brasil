"""
tests/test_urgencia_samu.py

Testes automatizados para a ingestão e processamento de Urgência & SAMU (Fase 1).
"""

import os
import pandas as pd
import pytest

PATH_URGENCIA = os.path.join("data", "processed", "indicadores_urgencia_samu.parquet")


@pytest.fixture(scope="module")
def df_urgencia():
    if not os.path.exists(PATH_URGENCIA):
        from pipeline.indicators.urgencia_samu import processar_urgencia_samu
        return processar_urgencia_samu()
    return pd.read_parquet(PATH_URGENCIA)


def test_cardinalidade_e_unicidade(df_urgencia):
    assert len(df_urgencia) == 5570
    assert df_urgencia["ibge7"].nunique() == 5570
    assert df_urgencia["ibge6"].nunique() == 5570


def test_cobertura_samu_limites(df_urgencia):
    for col in ("cob_samu_mun", "cob_samu_reg", "cob_samu_efetiva"):
        assert df_urgencia[col].min() >= 0.0
        assert df_urgencia[col].max() <= 100.0


def test_escore_urgencia_limites(df_urgencia):
    assert df_urgencia["escore_urgencia_rue"].min() >= 0.0
    assert df_urgencia["escore_urgencia_rue"].max() <= 100.0
    assert df_urgencia["escore_urgencia_rue"].notna().all()


def test_contagens_nao_negativas(df_urgencia):
    for col in ("usb_mun", "usb_reg", "usa_mun", "usa_reg", "upa_mun", "upa_reg", "tx_frota_samu_reg_100k", "tx_upa_reg_100k"):
        assert (df_urgencia[col] >= 0.0).all()


def test_totais_nacionais_plausibilidade(df_urgencia):
    # Total de ambulâncias do SAMU cadastradas no país deve ser > 3.000 USBs e > 500 USAs
    assert df_urgencia["usb_mun"].sum() > 3000
    assert df_urgencia["usa_mun"].sum() > 500
    assert df_urgencia["upa_mun"].sum() > 500


def test_fator_distancia_golden_hour(df_urgencia):
    assert "dist_polo_km" in df_urgencia.columns
    assert "fator_golden_hour" in df_urgencia.columns
    assert (df_urgencia["dist_polo_km"] >= 0.0).all()
    assert ((df_urgencia["fator_golden_hour"] > 0.0) & (df_urgencia["fator_golden_hour"] <= 1.0)).all()
    polos = df_urgencia[df_urgencia["eh_polo_hospitalar"]]
    assert len(polos) >= 1000
    assert (polos["dist_polo_km"] == 0.0).all()
    assert (polos["fator_golden_hour"] == 1.0).all()
    diamantina = df_urgencia[df_urgencia["ibge7"].astype(str) == "3121605"]["escore_urgencia_rue"].iloc[0]
    sgrp = df_urgencia[df_urgencia["ibge7"].astype(str) == "3125507"]["escore_urgencia_rue"].iloc[0]
    assert diamantina > sgrp + 20.0
