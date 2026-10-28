"""
tests/test_cirurgias_especialistas.py

Validação técnica dos indicadores da Fase 3:
- Atenção Cirúrgica SUS (Centros cirúrgicos, leitos cirúrgicos, polos de referência)
- Acesso a Médicos Especialistas (tempo e distância até o polo)
- Suporte de Exames Diagnósticos (Básicos e Avançados - TC e RM)
- Escore Sintético da Fase 3
"""

import json
import os
import numpy as np
import pandas as pd
import pytest

FASE3_PARQUET = os.path.join("data", "processed", "indicadores_cirurgias_especialistas.parquet")
MAPA_RESUMO_JSON = os.path.join("site", "data", "releases", "latest", "mapa_resumo.json")


def test_cardinalidade_e_unicidade_fase3():
    assert os.path.exists(FASE3_PARQUET), f"Arquivo {FASE3_PARQUET} não encontrado."
    df = pd.read_parquet(FASE3_PARQUET)
    assert len(df) == 5570, f"Esperado 5.570 municípios, obtido {len(df)}"
    assert df["ibge7"].is_unique, "Códigos IBGE-7 devem ser únicos"
    assert df["ibge6"].is_unique, "Códigos IBGE-6 devem ser únicos"


def test_escores_fase3_limites():
    df = pd.read_parquet(FASE3_PARQUET)
    for col in [
        "escore_exames_basicos", "escore_exames_avancados",
        "escore_cirurgico", "escore_especialistas", "escore_fase3_acesso"
    ]:
        assert col in df.columns, f"Coluna {col} ausente"
        assert df[col].notna().all(), f"Não deve haver NaN em {col}"
        assert (df[col] >= 0.0).all(), f"{col} contém valores negativos"
        assert (df[col] <= 100.0).all(), f"{col} contém valores superiores a 100.0"


def test_distancias_e_tempos_nao_negativos():
    df = pd.read_parquet(FASE3_PARQUET)
    for col in [
        "dist_polo_cirurgico_km", "tempo_polo_cirurgico_min",
        "dist_tomografo_km", "tempo_tomografo_min",
        "dist_ressonancia_km", "tempo_ressonancia_min",
        "dist_especialistas_km", "tempo_especialistas_min"
    ]:
        assert (df[col] >= 0).all(), f"{col} contém valores negativos"


def test_polos_cirurgicos_plausibilidade():
    df = pd.read_parquet(FASE3_PARQUET)
    # Pelo menos 2.000 municípios devem ter centro cirúrgico local
    polos = df[df["eh_polo_cirurgico"]]
    assert len(polos) >= 2000, f"Poucos polos cirúrgicos: {len(polos)}"
    # Em polos locais, a distância deve ser 0.0 e tempo 15 min
    assert (polos["dist_polo_cirurgico_km"] == 0.0).all()
    assert (polos["tempo_polo_cirurgico_min"] == 15).all()


def test_payload_site_cirurgias_especialistas():
    assert os.path.exists(MAPA_RESUMO_JSON), f"{MAPA_RESUMO_JSON} não encontrado."
    with open(MAPA_RESUMO_JSON, "r", encoding="utf-8") as f:
        payload = json.load(f)

    assert len(payload) == 5570, "Payload deve conter 5.570 municípios"

    # Verifica amostra (São Paulo)
    sp = payload.get("3550308")
    assert sp is not None, "São Paulo não encontrado"
    assert "cirurgias_especialistas" in sp, "cirurgias_especialistas ausente no payload de SP"
    f3 = sp["cirurgias_especialistas"]
    assert f3["escore_fase3"] >= 80.0
    assert f3["eh_polo_cirurgico"] is True
    assert f3["dist_polo_cirurgico_km"] == 0.0
    assert f3["tempo_polo_cirurgico_min"] == 15
    assert f3["leitos_cirurgicos_sus"] > 1000
