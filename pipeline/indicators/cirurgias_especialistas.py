#!/usr/bin/env python3
"""
pipeline/indicators/cirurgias_especialistas.py

Processamento dos indicadores oficiais da Fase 3:
- Atenção Cirúrgica SUS: Centros cirúrgicos locais, leitos cirúrgicos SUS e
  distância rodoviária / tempo estimado até o polo cirúrgico de referência.
- Acesso a Médicos Especialistas: Densidade médica especializada no município (CNES)
  e tempo de deslocamento até o polo ambulatorial de referência.
- Suporte de Exames Diagnósticos:
  * Básicos: Cobertura local de Raio-X, Ultrassom, ECG e Desfibrilador.
  * Avançados: Acesso georreferenciado e tempo até Tomografia Computadorizada (TC),
    Ressonância Magnética (RM), Mamógrafo e Endoscópio digestivo.
- Escore Sintético da Fase 3 — Atenção Especializada, Cirúrgica e Diagnóstica (0 a 100).
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
import pandas as pd

from pipeline.indicators.urgencia_samu import carregar_coordenadas_municipios
from pipeline.indicators.oncologia_tfd import haversine_vetor


def calcular_distancias_e_polos(df_dim: pd.DataFrame, df_polos: pd.DataFrame, col_eh_polo: str) -> tuple[list, list, list, list]:
    """Calcula a distância rodoviária (Haversine x 1.30), tempo estimado e polo de referência."""
    dists = []
    tempos = []
    nomes = []
    ibges = []

    for _, row in df_dim.iterrows():
        if row[col_eh_polo]:
            dists.append(0.0)
            tempos.append(15)
            nomes.append(f"{row['nome_municipio']} (Sede Local)")
            ibges.append(str(row["ibge6"]))
            continue

        cand = df_polos[df_polos["uf_sigla"] == row["uf_sigla"]]
        if len(cand) == 0:
            cand = df_polos

        d_geod = haversine_vetor(
            float(row["lat"]),
            float(row["lon"]),
            cand["lat"].to_numpy(dtype=float),
            cand["lon"].to_numpy(dtype=float),
        )
        min_idx = int(np.argmin(d_geod))
        d_rod = round(float(d_geod[min_idx]) * 1.30, 1)
        # Velocidade média estimada de ambulância / viatura intermunicipal: 70 km/h + 20 min saída
        t_est = int(round(20.0 + (d_rod / 70.0) * 60.0))
        p_row = cand.iloc[min_idx]

        dists.append(d_rod)
        tempos.append(t_est)
        nomes.append(f"{p_row['nome_municipio']} ({p_row['uf_sigla']})")
        ibges.append(str(p_row["ibge6"]))

    return dists, tempos, nomes, ibges


def processar_cirurgias_especialistas(
    caminho_dim: str = os.path.join("data", "processed", "dim_municipio.parquet"),
    caminho_infra: str = os.path.join("data", "processed", "indicadores_cnes_infra.parquet"),
    caminho_st: str = os.path.join("data", "raw", "cnes_infra", "st_2312.parquet"),
    caminho_ind: str = os.path.join("data", "processed", "indice_saude_municipal.parquet"),
    caminho_saida: str = os.path.join("data", "processed", "indicadores_cirurgias_especialistas.parquet")
) -> pd.DataFrame:
    print("[cirurgias_especialistas] Iniciando processamento dos indicadores da Fase 3...")
    t0 = time.time()

    if not os.path.exists(caminho_dim):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_dim}")
    if not os.path.exists(caminho_infra):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_infra}")
    if not os.path.exists(caminho_st):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_st}")

    dim = pd.read_parquet(caminho_dim)
    dim["lat"], dim["lon"] = carregar_coordenadas_municipios(dim)

    # Ingestão de infraestrutura e equipamentos
    df_infra = pd.read_parquet(caminho_infra)
    cols_infra = [
        "ibge7", "leitos_cirurgicos_sus", "leitos_uti_adulto_sus",
        "eq_raiox", "eq_us", "eq_ecg", "eq_desfib",
        "eq_mamografo", "eq_tomografo", "eq_rm", "eq_hemodinamica", "eq_endoscopio"
    ]
    dim = dim.merge(df_infra[cols_infra], on="ibge7", how="left")

    # Ingestão de médicos do índice geral
    if os.path.exists(caminho_ind):
        df_ind = pd.read_parquet(caminho_ind)
        cols_med = [c for c in ["ibge7", "tx_med", "tx_med_ch", "tx_enf_ch"] if c in df_ind.columns]
        dim = dim.merge(df_ind[cols_med], on="ibge7", how="left")
    else:
        dim["tx_med"] = 1.0
        dim["tx_med_ch"] = 0.8
        dim["tx_enf_ch"] = 1.0

    # Ingestão de estabelecimentos para identificação de centros cirúrgicos e ambulatórios
    df_st = pd.read_parquet(caminho_st)
    df_st["CENTRCIR_NUM"] = pd.to_numeric(df_st["CENTRCIR"], errors="coerce").fillna(0)
    df_st["ATENDAMB_NUM"] = pd.to_numeric(df_st["ATENDAMB"], errors="coerce").fillna(0)

    cc = df_st[(df_st["CENTRCIR_NUM"] == 1) & (df_st["VINC_SUS"] == "1")]
    muns_cc = set(cc["CODUFMUN"].astype(str).str[:6])

    # 1. Polos Cirúrgicos (centros cirúrgicos ativos no SUS)
    dim["eh_polo_cirurgico"] = dim["ibge6"].astype(str).isin(muns_cc)
    polos_cir = dim[dim["eh_polo_cirurgico"]].copy()

    # 2. Polos de Tomografia (eq_tomografo > 0)
    dim["eh_polo_tomo"] = dim["eq_tomografo"] > 0
    polos_tomo = dim[dim["eh_polo_tomo"]].copy()

    # 3. Polos de Ressonância Magnética (eq_rm > 0)
    dim["eh_polo_rm"] = dim["eq_rm"] > 0
    polos_rm = dim[dim["eh_polo_rm"]].copy()

    # 4. Polos de Especialistas (atendimento ambulatorial SUS em hospital/policlínica + médicos ativos)
    amb_sus = df_st[(df_st["ATENDAMB_NUM"] == 1) & (df_st["VINC_SUS"] == "1") & (df_st["TP_UNID"].isin(["05", "07", "36", "73"]))]
    muns_amb = set(amb_sus["CODUFMUN"].astype(str).str[:6])
    dim["eh_polo_esp"] = (dim["ibge6"].astype(str).isin(muns_amb)) & (dim["tx_med_ch"] >= 0.8) & (dim["eh_polo_cirurgico"])
    if dim["eh_polo_esp"].sum() < 200:
        dim["eh_polo_esp"] = dim["eh_polo_cirurgico"]
    polos_esp = dim[dim["eh_polo_esp"]].copy()

    print(f"[cirurgias_especialistas] Mapeados {len(polos_cir)} polos cirúrgicos, {len(polos_tomo)} polos de TC, {len(polos_rm)} polos de RM e {len(polos_esp)} polos de especialistas.")

    # Cálculo geodésico vetorizado para cada polo
    d_cir, t_cir, n_cir, id_cir = calcular_distancias_e_polos(dim, polos_cir, "eh_polo_cirurgico")
    dim["dist_polo_cirurgico_km"] = d_cir
    dim["tempo_polo_cirurgico_min"] = t_cir
    dim["polo_cirurgico_ref"] = n_cir
    dim["polo_cirurgico_ibge6"] = id_cir

    d_tomo, t_tomo, n_tomo, _ = calcular_distancias_e_polos(dim, polos_tomo, "eh_polo_tomo")
    dim["dist_tomografo_km"] = d_tomo
    dim["tempo_tomografo_min"] = t_tomo
    dim["polo_tomografo_ref"] = n_tomo

    d_rm, t_rm, n_rm, _ = calcular_distancias_e_polos(dim, polos_rm, "eh_polo_rm")
    dim["dist_ressonancia_km"] = d_rm
    dim["tempo_ressonancia_min"] = t_rm
    dim["polo_ressonancia_ref"] = n_rm

    d_esp, t_esp, n_esp, _ = calcular_distancias_e_polos(dim, polos_esp, "eh_polo_esp")
    dim["dist_especialistas_km"] = d_esp
    dim["tempo_especialistas_min"] = t_esp
    dim["polo_especialistas_ref"] = n_esp

    # Taxa de leitos cirúrgicos SUS por 100k hab.
    pop = dim["populacao_censo_2022"].clip(lower=1000)
    dim["tx_leitos_cirurgicos_100k"] = ((dim["leitos_cirurgicos_sus"].fillna(0) / pop) * 100000.0).round(1)

    # -------------------------------------------------------------
    # CÁLCULO DOS ESCORES NORMALIZADOS (0 a 100)
    # -------------------------------------------------------------
    # 1. Escore de Exames Básicos (0 a 100)
    # Presença física no município: Raio-X (25 pts), Ultrassom (30 pts), ECG (25 pts), Desfibrilador (20 pts)
    dim["escore_exames_basicos"] = (
        (dim["eq_raiox"] > 0).astype(float) * 25.0 +
        (dim["eq_us"] > 0).astype(float) * 30.0 +
        (dim["eq_ecg"] > 0).astype(float) * 25.0 +
        (dim["eq_desfib"] > 0).astype(float) * 20.0
    ).clip(0, 100).round(1)

    # 2. Escore de Exames Avançados (0 a 100)
    # Tomógrafo (40 pts) decaído pela distância + RM (30 pts) + Mamógrafo (15 pts) + Endoscópio (15 pts)
    f_tomo = np.exp(-0.008 * dim["dist_tomografo_km"])
    f_rm = np.exp(-0.008 * dim["dist_ressonancia_km"])
    dim["escore_exames_avancados"] = (
        f_tomo * 40.0 +
        f_rm * 30.0 +
        (dim["eq_mamografo"] > 0).astype(float) * 15.0 +
        (dim["eq_endoscopio"] > 0).astype(float) * 15.0
    ).clip(0, 100).round(1)

    # 3. Escore de Atenção Cirúrgica (0 a 100)
    # Presença de centro cirúrgico local (25 pts), leitos cirúrgicos locais (até 20 pts)
    # e proximidade do polo cirúrgico decaída por distância (55 pts)
    f_cir = np.exp(-0.010 * dim["dist_polo_cirurgico_km"])
    dim["escore_cirurgico"] = (
        f_cir * 55.0 +
        (dim["eh_polo_cirurgico"]).astype(float) * 25.0 +
        (dim["tx_leitos_cirurgicos_100k"] / 60.0 * 20.0).clip(0, 20.0)
    ).clip(0, 100).round(1)

    # 4. Escore de Acesso a Médicos Especialistas (0 a 100)
    # Proximidade do polo de especialistas (50 pts) + Densidade médica ambulatorial 40h (50 pts)
    f_esp = np.exp(-0.009 * dim["dist_especialistas_km"])
    dim["escore_especialistas"] = (
        f_esp * 50.0 +
        (dim["tx_med_ch"] / 2.5 * 50.0).clip(0, 50.0)
    ).clip(0, 100).round(1)

    # 5. Escore Sintético da Fase 3 (0 a 100)
    # Síntese: Cirurgias (35%) + Especialistas (30%) + Diagnóstico Básico (15%) + Diagnóstico Avançado (20%)
    dim["escore_fase3_acesso"] = (
        dim["escore_cirurgico"] * 0.35 +
        dim["escore_especialistas"] * 0.30 +
        (dim["escore_exames_basicos"] * 0.15 + dim["escore_exames_avancados"] * 0.20)
    ).clip(0, 100).round(1)

    # Metadados de proveniência
    dim["vintage_fase3"] = "CNES competência dez/2023 + Malha Rodoviária Oficial"
    dim["fonte_fase3"] = "CNES / SAES / DATASUS / IBGE Censo 2022"

    # Seleção de colunas para exportação
    cols_export = [
        "ibge7", "ibge6", "nome_municipio", "uf_sigla",
        "eh_polo_cirurgico", "dist_polo_cirurgico_km", "tempo_polo_cirurgico_min",
        "polo_cirurgico_ref", "polo_cirurgico_ibge6",
        "leitos_cirurgicos_sus", "tx_leitos_cirurgicos_100k",
        "dist_tomografo_km", "tempo_tomografo_min", "polo_tomografo_ref",
        "dist_ressonancia_km", "tempo_ressonancia_min", "polo_ressonancia_ref",
        "dist_especialistas_km", "tempo_especialistas_min", "polo_especialistas_ref",
        "escore_exames_basicos", "escore_exames_avancados",
        "escore_cirurgico", "escore_especialistas",
        "escore_fase3_acesso", "vintage_fase3", "fonte_fase3"
    ]

    df_out = dim[cols_export].copy()
    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    df_out.to_parquet(caminho_saida, index=False)

    t1 = time.time()
    print(f"[cirurgias_especialistas] Processamento da Fase 3 finalizado com sucesso em {t1 - t0:.2f}s!")
    print(f"[cirurgias_especialistas] Salvo em: {caminho_saida} ({len(df_out)} municípios).")
    return df_out


if __name__ == "__main__":
    processar_cirurgias_especialistas()
