#!/usr/bin/env python3
"""
pipeline/indicators/build_composite_index.py

Calcula o Índice Sintético de Saúde Municipal do Brasil consolidando:
- Dimensão 1 (Resultados em Saúde): D1.1 Mortalidade Infantil (SIM / SINASC / IBGE com Bayes)
- Dimensão 2 (Atenção Primária): D2.2 Pré-Natal 7+ Consultas (SINASC) e D2.3 Cobertura Vacinal (SI-PNI)
- Dimensão 3 (Acesso e Estrutura): D3.1 Leitos SUS (CNES), D3.2 Médicos por 1.000 hab (CNES) e D3.3 Cobertura eSF (e-Gestor/SAPS)
- Camada Privada (fora da nota): Leitos Não-SUS por 100.000 hab (CNES)

Regras metodológicas:
- Pesos iguais de 33,33% para cada dimensão (D1, D2, D3), conforme config/pesos.yaml
- Normalização min-max com limites de referência baseados em metas oficiais
- Sensibilidade e faixa de posição plausível calculadas a partir de esquemas alternativos
- Cobertura integral dos 5.570 municípios do Brasil
"""

import os
import sys
import pandas as pd
import numpy as np

DIM_PATH = os.path.join("data", "processed", "dim_municipio.parquet")
D1_PATH = os.path.join("data", "processed", "indicador_d1_1.parquet")
RAW_MULTIDIM = os.path.join("data", "raw", "ieps_indicadores_2022.csv")

OUT_PARQUET = os.path.join("data", "processed", "indice_saude_municipal.parquet")
OUT_CSV = os.path.join("data", "processed", "indice_saude_municipal.csv")
SITE_PROCESSED = os.path.join("site", "data", "processed")


def normalizar(series: pd.Series, pior: float, melhor: float, menor_melhor: bool = False) -> pd.Series:
    """Normaliza para escala 0 a 100 com saturação fixa."""
    if menor_melhor:
        score = 100.0 * (pior - series) / (pior - melhor)
    else:
        score = 100.0 * (series - pior) / (melhor - pior)
    return score.clip(0.0, 100.0).round(1)


def build_composite_index() -> pd.DataFrame:
    print("[build_composite_index] Carregando bases dimensionais e indicadores...")

    if not os.path.exists(DIM_PATH):
        print(f"[build_composite_index:ERRO] {DIM_PATH} não encontrado.")
        sys.exit(1)

    df_dim = pd.read_parquet(DIM_PATH)

    if not os.path.exists(D1_PATH):
        print("[build_composite_index] Calculando indicador D1.1...")
        import pipeline.indicators.d1_resultados as d1_builder
        df_d1 = d1_builder.processar_d1_1()
    else:
        df_d1 = pd.read_parquet(D1_PATH)

    if not os.path.exists(RAW_MULTIDIM):
        print("[build_composite_index] Baixando insumos multidimensionais...")
        import pipeline.indicators.fetch_official_multidim as fetcher
        raw_multi = fetcher.fetch_multidim_data()
    else:
        raw_multi = pd.read_csv(RAW_MULTIDIM, encoding="latin1")

    # Mapeamento do código IBGE 6 dígitos
    ibge6_col = raw_multi.columns[1]
    raw_multi["ibge6"] = raw_multi[ibge6_col].astype(str).str.zfill(6)

    # Identificação resiliente de colunas
    col_prenatal = [c for c in raw_multi.columns if "Pré-Natal" in c or "Natal" in c][0]
    col_vacina = [c for c in raw_multi.columns if "Poliomielite" in c or "Vacinal" in c][0]
    col_esf = [c for c in raw_multi.columns if "ESF" in c][0]
    col_leitos = [c for c in raw_multi.columns if "Leitos SUS" in c][0]
    col_medicos = [c for c in raw_multi.columns if "Médicos" in c or "dicos" in c][0]
    col_leitos_priv = [c for c in raw_multi.columns if "Não-SUS" in c or "o-SUS" in c][0]

    # Junção com a dimensão municipal oficial
    df = pd.merge(df_dim, raw_multi[[
        "ibge6", col_prenatal, col_vacina, col_esf, col_leitos, col_medicos, col_leitos_priv
    ]], on="ibge6", how="left")

    df = pd.merge(df, df_d1[[
        "ibge7", "tmi_bruta", "tmi_bayes", "ic_95_min", "ic_95_max", "escore_d1_1"
    ]], on="ibge7", how="left")

    # 1. Dimensão 1: Resultados (Mortalidade Infantil)
    df["d1_nota"] = df["escore_d1_1"]

    # 2. Dimensão 2: Atenção Primária
    # D2.2: Pré-natal 7+ consultas (Meta MS: >= 85% = 100; <= 30% = 0)
    df["d2_2_val"] = df[col_prenatal].fillna(df[col_prenatal].median()).round(1)
    df["escore_d2_2"] = normalizar(df["d2_2_val"], pior=30.0, melhor=85.0)

    # D2.3: Cobertura Vacinal Poliomielite (Meta PNI: >= 95% = 100; <= 50% = 0)
    df["d2_3_val"] = df[col_vacina].fillna(df[col_vacina].median()).round(1)
    df["escore_d2_3"] = normalizar(df["d2_3_val"], pior=50.0, melhor=95.0)

    df["d2_nota"] = ((df["escore_d2_2"] + df["escore_d2_3"]) / 2.0).round(1)

    # 3. Dimensão 3: Acesso e Estrutura
    # D3.1: Leitos SUS por 100k hab (Meta Portaria 1.631: >= 250 = 100; 0 = 0)
    df["d3_1_val"] = df[col_leitos].fillna(0.0).round(1)
    df["escore_d3_1"] = normalizar(df["d3_1_val"], pior=0.0, melhor=250.0)

    # D3.2: Médicos por 1.000 hab (Meta OCDE/CFM: >= 3.0 = 100; <= 0.2 = 0)
    df["d3_2_val"] = df[col_medicos].fillna(df[col_medicos].median()).round(2)
    df["escore_d3_2"] = normalizar(df["d3_2_val"], pior=0.2, melhor=3.0)

    # D3.3: Cobertura eSF % (Meta SAPS: >= 100% = 100; <= 20% = 0)
    df["d3_3_val"] = df[col_esf].fillna(df[col_esf].median()).round(1)
    df["escore_d3_3"] = normalizar(df["d3_3_val"], pior=20.0, melhor=100.0)

    df["d3_nota"] = ((df["escore_d3_1"] + df["escore_d3_2"] + df["escore_d3_3"]) / 3.0).round(1)

    # Camada Privada (Fora da Nota - DEC-001)
    df["leitos_priv_val"] = df[col_leitos_priv].fillna(0.0).round(1)

    # 4. NOTA GERAL SINTÉTICA (Pesos Iguais: 33,33% para cada dimensão)
    df["nota_geral"] = ((df["d1_nota"] + df["d2_nota"] + df["d3_nota"]) / 3.0).round(1)

    # 5. Análise de Sensibilidade e Faixa de Posição Plausível
    # Esquema alternativo 1: Foco em Resultados (D1=50%, D2=30%, D3=20%)
    escore_alt1 = 0.50 * df["d1_nota"] + 0.30 * df["d2_nota"] + 0.20 * df["d3_nota"]
    # Esquema alternativo 2: Foco em Estrutura/APS (D1=20%, D2=40%, D3=40%)
    escore_alt2 = 0.20 * df["d1_nota"] + 0.40 * df["d2_nota"] + 0.40 * df["d3_nota"]

    rank_padrao = df["nota_geral"].rank(ascending=False, method="min").astype(int)
    rank_alt1 = escore_alt1.rank(ascending=False, method="min").astype(int)
    rank_alt2 = escore_alt2.rank(ascending=False, method="min").astype(int)

    df["posicao_nacional"] = rank_padrao
    df["faixa_posicao_min"] = np.minimum(np.minimum(rank_padrao, rank_alt1), rank_alt2)
    df["faixa_posicao_max"] = np.maximum(np.maximum(rank_padrao, rank_alt1), rank_alt2)

    # Ranking Estadual (por UF)
    df["posicao_estadual"] = df.groupby("uf_sigla")["nota_geral"].rank(ascending=False, method="min").astype(int)

    # Ranking por Porte Populacional
    df["posicao_grupo_pares"] = df.groupby("porte_populacional")["nota_geral"].rank(ascending=False, method="min").astype(int)

    # Rankings por Dimensão
    df["rank_d1"] = df["d1_nota"].rank(ascending=False, method="min").astype(int)
    df["rank_d2"] = df["d2_nota"].rank(ascending=False, method="min").astype(int)
    df["rank_d3"] = df["d3_nota"].rank(ascending=False, method="min").astype(int)

    # Salva artefatos processados
    os.makedirs(os.path.dirname(OUT_PARQUET), exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")

    os.makedirs(SITE_PROCESSED, exist_ok=True)
    df.to_parquet(os.path.join(SITE_PROCESSED, "indice_saude_municipal.parquet"), index=False)
    df.to_csv(os.path.join(SITE_PROCESSED, "indice_saude_municipal.csv"), index=False, encoding="utf-8")

    print(f"[build_composite_index] Índice consolidado com sucesso para {len(df)} municípios:")
    print(f"  - Média Nacional Nota Geral: {df['nota_geral'].mean():.1f} pontos")
    print(f"  - Média D1 (Resultados):      {df['d1_nota'].mean():.1f} pontos")
    print(f"  - Média D2 (Primária):        {df['d2_nota'].mean():.1f} pontos")
    print(f"  - Média D3 (Estrutura):       {df['d3_nota'].mean():.1f} pontos")

    return df


if __name__ == "__main__":
    build_composite_index()
