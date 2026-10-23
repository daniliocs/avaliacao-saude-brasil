#!/usr/bin/env python3
"""
pipeline/indicators/d1_resultados.py

Fase 2 da Especificação Técnica:
Calcula o Indicador D1.1 (Mortalidade Infantil) para todos os 5.570 municípios do Brasil.

Regras e Métodos Aplicados (Seções 4, 5 e 7):
1. Numerador: Óbitos de menores de 1 ano por lugar de residência (SIM / Estatísticas do Registro Civil - IBGE 2654).
2. Denominador: Nascidos vivos por lugar de residência da mãe (SINASC / IBGE 2609).
3. Taxa Bruta por 1.000 nascidos vivos.
4. Intervalo de Confiança de 95% exato (distribuição de Poisson via Qui-quadrado).
5. Suavização Bayesiana Empírica (Marshall 1991 shrinkage para a média da UF).
6. Normalização 0–100 baseada na Meta ODS 3.2 (<= 12 por mil NV = 100 pontos; pior limiar 35 por mil NV = 0 pontos).
7. Rankings nacional, estadual e por grupo de porte populacional com faixa de posição plausível.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from scipy.stats import chi2

DIM_MUNICIPIO_PATH = os.path.join("data", "processed", "dim_municipio.parquet")
OBITOS_RAW_PATH = os.path.join("data", "raw", "ibge_obitos_infantis_2022.json")
NV_RAW_PATH = os.path.join("data", "raw", "ibge_nascidos_vivos_2022.json")

OUTPUT_PARQUET = os.path.join("data", "processed", "indicador_d1_1.parquet")
OUTPUT_CSV = os.path.join("data", "processed", "indicador_d1_1.csv")

LIMITE_MELHOR = 5.0   # Padrão de excelência internacional (<= 5 óbitos por 1.000 NV) -> 100 pontos
LIMITE_PIOR = 30.0    # Limiar crítico de vulnerabilidade (>= 30 óbitos por 1.000 NV) -> 0 pontos


def calcular_ic_poisson(k: int, n: int, alpha: float = 0.05, fator: float = 1000.0) -> tuple:
    """Calcula o intervalo de confiança exato de Poisson (95%) para a taxa."""
    if n <= 0:
        return (0.0, 0.0)
    if k == 0:
        low = 0.0
    else:
        low = (chi2.ppf(alpha / 2, 2 * k) / (2 * n)) * fator
    high = (chi2.ppf(1 - alpha / 2, 2 * (k + 1)) / (2 * n)) * fator
    return (round(float(low), 2), round(float(high), 2))


def calcular_suavizacao_bayesiana(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica o estimador empírico de Bayes (Marshall 1991) agrupado por UF."""
    df["tmi_bayes"] = df["tmi_bruta"]

    for uf, group in df.groupby("uf_sigla"):
        total_obitos = group["obitos_infantis"].sum()
        total_nv = group["nascidos_vivos"].sum()

        if total_nv == 0:
            continue

        # Taxa média da UF (por unidade)
        mu = total_obitos / total_nv
        n_bar = group["nascidos_vivos"].mean()

        # Variância entre municípios ponderada pelo número de nascidos vivos
        diff_sq = (group["obitos_infantis"] / group["nascidos_vivos"].replace(0, np.nan) - mu) ** 2
        var_amostral = (group["nascidos_vivos"] * diff_sq).sum() / total_nv
        s2 = max(0.0, var_amostral - (mu / n_bar if n_bar > 0 else 0.0))

        # Fator de ponderação shrinkage w_i
        denom = s2 + (mu / group["nascidos_vivos"].replace(0, np.nan))
        w = s2 / denom
        w = w.fillna(0.0).clip(0.0, 1.0)

        # Taxa suavizada por Bayes
        r_i = (group["obitos_infantis"] / group["nascidos_vivos"].replace(0, np.nan)).fillna(mu)
        bayes_rate = (w * r_i + (1 - w) * mu) * 1000.0
        df.loc[group.index, "tmi_bayes"] = bayes_rate.round(2)

    return df


def normalizar_escore(taxa: float) -> float:
    """Normaliza a taxa em escala 0–100 onde menor taxa = melhor escore."""
    if taxa is None or pd.isna(taxa):
        return None
    if taxa <= LIMITE_MELHOR:
        return 100.0
    if taxa >= LIMITE_PIOR:
        return 0.0
    # Escala linear decrescente
    score = 100.0 * (LIMITE_PIOR - taxa) / (LIMITE_PIOR - LIMITE_MELHOR)
    return round(float(score), 1)


def processar_d1_1() -> pd.DataFrame:
    print("[d1_resultados] Carregando dimensao municipal e insumos brutos...")
    df_dim = pd.read_parquet(DIM_MUNICIPIO_PATH)

    with open(OBITOS_RAW_PATH, "r", encoding="utf-8") as f:
        obitos_map = json.load(f)

    with open(NV_RAW_PATH, "r", encoding="utf-8") as f:
        nv_map = json.load(f)

    df_dim["obitos_infantis"] = df_dim["ibge7"].map(obitos_map).fillna(0).astype(int)
    df_dim["nascidos_vivos"] = df_dim["ibge7"].map(nv_map).fillna(0).astype(int)

    # Taxa Bruta (por 1.000 NV)
    df_dim["tmi_bruta"] = np.where(
        df_dim["nascidos_vivos"] > 0,
        (df_dim["obitos_infantis"] / df_dim["nascidos_vivos"]) * 1000.0,
        0.0
    ).round(2)

    # Intervalos de Confiança Poisson 95%
    print("[d1_resultados] Calculando Intervalos de Confianca exatos de Poisson (95%)...")
    ics = [
        calcular_ic_poisson(row["obitos_infantis"], row["nascidos_vivos"])
        for _, row in df_dim.iterrows()
    ]
    df_dim["ic_95_min"] = [ic[0] for ic in ics]
    df_dim["ic_95_max"] = [ic[1] for ic in ics]

    # Suavização Bayesiana Empírica (Marshall 1991)
    print("[d1_resultados] Aplicando Suavizacao Bayesiana Empirica por UF...")
    df_dim = calcular_suavizacao_bayesiana(df_dim)

    # Escore Normalizado (0 a 100)
    df_dim["escore_d1_1"] = df_dim["tmi_bayes"].apply(normalizar_escore)

    # Rankings
    print("[d1_resultados] Calculando Rankings Nacional, Estadual e por Porte...")
    # Ranking Nacional: Maior escore (menor mortalidade) = 1º lugar
    df_dim["posicao_nacional"] = df_dim["escore_d1_1"].rank(ascending=False, method="min").astype(int)

    # Ranking Estadual
    df_dim["posicao_estadual"] = df_dim.groupby("uf_sigla")["escore_d1_1"].rank(ascending=False, method="min").astype(int)

    # Ranking por Porte
    df_dim["posicao_grupo_pares"] = df_dim.groupby("porte_populacional")["escore_d1_1"].rank(ascending=False, method="min").astype(int)

    # Faixa de Posição Plausível (Sensibilidade baseada nos ICs)
    escore_otimista = df_dim["ic_95_min"].apply(normalizar_escore)
    escore_pessimista = df_dim["ic_95_max"].apply(normalizar_escore)
    df_dim["faixa_posicao_min"] = escore_otimista.rank(ascending=False, method="min").astype(int)
    df_dim["faixa_posicao_max"] = escore_pessimista.rank(ascending=False, method="min").astype(int)

    # Salva artefatos processados
    os.makedirs(os.path.dirname(OUTPUT_PARQUET), exist_ok=True)
    df_dim.to_parquet(OUTPUT_PARQUET, index=False)
    df_dim.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")

    # Espelha para site/data/processed/
    site_processed = os.path.join("site", "data", "processed")
    os.makedirs(site_processed, exist_ok=True)
    df_dim.to_parquet(os.path.join(site_processed, "indicador_d1_1.parquet"), index=False)
    df_dim.to_csv(os.path.join(site_processed, "indicador_d1_1.csv"), index=False, encoding="utf-8")

    print(f"[d1_resultados] Indicador D1.1 calculado com sucesso para {len(df_dim)} municípios:")
    print(f"  - Média Nacional TMI Bayes: {df_dim['tmi_bayes'].mean():.2f} por 1.000 NV")
    print(f"  - Média Nacional Escore:    {df_dim['escore_d1_1'].mean():.1f} pontos")
    return df_dim


if __name__ == "__main__":
    processar_d1_1()
