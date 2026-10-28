"""
tests/test_cnes_infra.py

Testes automatizados para a auditoria de infraestrutura assistencial, equipamentos
e capacidade hospitalar SUS (CNES 2023-12, v0.8.0).
"""

import os
import pandas as pd
import pytest

PATH_INFRA = os.path.join("data", "processed", "indicadores_cnes_infra.parquet")


@pytest.fixture(scope="module")
def df_infra():
    if not os.path.exists(PATH_INFRA):
        from pipeline.indicators.cnes_infra import processar_cnes_infra
        return processar_cnes_infra()
    return pd.read_parquet(PATH_INFRA)


def test_cardinalidade_e_unicidade(df_infra):
    assert len(df_infra) == 5570
    assert df_infra["ibge7"].nunique() == 5570
    assert df_infra["ibge6"].nunique() == 5570


def test_escores_limites(df_infra):
    for col in ("escore_infra", "infra_basico", "infra_avancado", "infra_capacidade"):
        assert df_infra[col].min() >= 0.0
        assert df_infra[col].max() <= 100.0
        assert df_infra[col].notna().all()


def test_contagens_nao_negativas(df_infra):
    for col in (
        "eq_raiox", "eq_us", "eq_ecg", "eq_desfib", "eq_mamografo",
        "eq_tomografo", "eq_rm", "eq_hemodinamica", "eq_endoscopio",
        "leitos_uti_adulto_sus", "leitos_cirurgicos_sus", "ps_hospitalar_sus", "unid_moveis_urgencia"
    ):
        assert (df_infra[col] >= 0).all()


def test_plausibilidade_agregados_nacionais(df_infra):
    # Valores derivados dos microdados do CNES competência 2023-12
    assert df_infra["leitos_uti_adulto_sus"].sum() > 20000
    assert df_infra["leitos_cirurgicos_sus"].sum() > 70000
    assert df_infra["eq_tomografo"].sum() > 3000
    assert df_infra["eq_rm"].sum() > 1400
    assert df_infra["eq_hemodinamica"].sum() > 400
    assert df_infra["ps_hospitalar_sus"].sum() > 4500
    assert df_infra["unid_moveis_urgencia"].sum() > 5500


def test_capitais_possuem_infraestrutura_avancada(df_infra):
    # Capitais de referência (São Paulo, Rio, Belo Horizonte, Curitiba, Porto Alegre)
    capitais = ["3550308", "3304557", "3106200", "4106902", "4314902"]
    sub = df_infra[df_infra["ibge7"].astype(str).isin(capitais)]
    assert len(sub) == len(capitais)
    for col in ("eq_tomografo", "eq_rm", "eq_hemodinamica", "leitos_uti_adulto_sus", "leitos_cirurgicos_sus"):
        assert (sub[col] > 0).all()
        assert (sub["escore_infra"] >= 70.0).all()


def test_acesso_distancia_municipios_sem_tomografo(df_infra):
    # Municípios sem tomógrafo devem ter acc_tomografo < 1.0 (decaído por distância)
    sem_tomo = df_infra[df_infra["eq_tomografo"] == 0]
    assert len(sem_tomo) > 4000
    assert (sem_tomo["acc_tomografo"] <= 0.60).all()  # teto sem recurso local é 60%
