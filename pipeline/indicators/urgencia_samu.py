"""
pipeline/indicators/urgencia_samu.py

Ingestão e processamento de indicadores oficiais da Rede de Urgência e Emergência (RUE):
- Cobertura Populacional do SAMU 192 (DEMAS/MS - samuppc)
- Frota de Ambulâncias de Suporte Básico (USB) (DEMAS/MS - samunab)
- Frota de Ambulâncias de Suporte Avançado / UTI Móvel (USA) (DEMAS/MS - samunaa)
- Unidades de Pronto Atendimento (UPAs 24h) em Funcionamento (DEMAS/MS - upa)

Gera métricas no nível municipal e no nível da Região de Saúde (CIR).
"""

from __future__ import annotations

import os
import pandas as pd
import numpy as np


def processar_urgencia_samu(
    caminho_dim: str = os.path.join("data", "processed", "dim_municipio.parquet"),
    diretorio_demas: str = os.path.join("data", "raw", "demas_urgencia"),
    caminho_saida: str = os.path.join("data", "processed", "indicadores_urgencia_samu.parquet")
) -> pd.DataFrame:
    """
    Consolida os indicadores de Urgência & SAMU para os 5.570 municípios brasileiros.
    """
    if not os.path.exists(caminho_dim):
        raise FileNotFoundError(f"Arquivo de dimensões municipais não encontrado: {caminho_dim}")

    dim = pd.read_parquet(caminho_dim)
    dim["ibge6_int"] = dim["ibge6"].astype(int)

    # Carregar arquivos brutos do DEMAS
    path_samu = os.path.join(diretorio_demas, "samuppc.csv")
    path_usb = os.path.join(diretorio_demas, "samunab.csv")
    path_usa = os.path.join(diretorio_demas, "samunaa.csv")
    path_upa = os.path.join(diretorio_demas, "upa.csv")

    for p in (path_samu, path_usb, path_usa, path_upa):
        if not os.path.exists(p):
            raise FileNotFoundError(f"Arquivo DEMAS não encontrado: {p}")

    df_samu = pd.read_csv(path_samu, encoding="latin1")
    df_usb = pd.read_csv(path_usb, encoding="latin1")
    df_usa = pd.read_csv(path_usa, encoding="latin1")
    df_upa = pd.read_csv(path_upa, encoding="latin1")

    # Obter competência mais recente disponível
    comp_samu = df_samu["co_anomes"].max()
    comp_usb = df_usb["co_anomes"].max()
    comp_usa = df_usa["co_anomes"].max()
    comp_upa = df_upa["co_anomes"].max()

    c_samu = df_samu[df_samu["co_anomes"] == comp_samu].set_index("co_ibge")
    c_usb = df_usb[df_usb["co_anomes"] == comp_usb].set_index("co_ibge")
    c_usa = df_usa[df_usa["co_anomes"] == comp_usa].set_index("co_ibge")
    c_upa = df_upa[df_upa["co_anomes"] == comp_upa].set_index("co_ibge")

    df = dim.copy()

    # Mapeamento municipal
    df["cob_samu_mun"] = df["ibge6_int"].map(c_samu["vl_indicador_calculado_mun"]).fillna(0.0).astype(float)
    df["cob_samu_reg"] = df["ibge6_int"].map(c_samu["vl_indicador_calculado_rs"]).fillna(0.0).astype(float)
    df["cob_samu_efetiva"] = np.maximum(df["cob_samu_mun"], df["cob_samu_reg"])

    df["usb_mun"] = df["ibge6_int"].map(c_usb["vl_indicador_calculado_mun"]).fillna(0.0).astype(float)
    df["usb_reg"] = df["ibge6_int"].map(c_usb["vl_indicador_calculado_rs"]).fillna(0.0).astype(float)

    df["usa_mun"] = df["ibge6_int"].map(c_usa["vl_indicador_calculado_mun"]).fillna(0.0).astype(float)
    df["usa_reg"] = df["ibge6_int"].map(c_usa["vl_indicador_calculado_rs"]).fillna(0.0).astype(float)

    df["upa_mun"] = df["ibge6_int"].map(c_upa["vl_indicador_calculado_mun"]).fillna(0.0).astype(float)
    df["upa_reg"] = df["ibge6_int"].map(c_upa["vl_indicador_calculado_rs"]).fillna(0.0).astype(float)

    df["co_regiao_saude"] = df["ibge6_int"].map(c_samu["co_regiao_saude"])
    df["no_regiao_saude"] = df["ibge6_int"].map(c_samu["no_regiao_saude"])

    # População total da Região de Saúde (Censo IBGE 2022)
    pop_rs = df.groupby("co_regiao_saude")["populacao_censo_2022"].transform("sum")
    df["pop_regiao_saude"] = pop_rs.replace(0, np.nan)

    # Taxas regionalizadas por 100 mil habitantes
    # Ponderação oficial: 1 USA (UTI Móvel) equivale a ~2.5 USBs em capacidade clínica
    frota_ponderada_reg = df["usb_reg"] + 2.5 * df["usa_reg"]
    df["tx_frota_samu_reg_100k"] = ((frota_ponderada_reg / df["pop_regiao_saude"]) * 100_000).round(2).fillna(0.0)
    df["tx_upa_reg_100k"] = ((df["upa_reg"] / df["pop_regiao_saude"]) * 100_000).round(2).fillna(0.0)

    # Escore sintético de prontidão em urgência (0 a 100):
    # 50% Cobertura Efetiva do SAMU + 35% Densidade de Frota Regional + 15% Presença/Densidade de UPAs
    # Normalização de saturação: P95 de frota regional (~5.5/100k) e P95 de UPA regional (~0.9/100k)
    norm_cob = np.clip(df["cob_samu_efetiva"], 0.0, 100.0)
    norm_frota = np.clip(df["tx_frota_samu_reg_100k"] / 5.0 * 100.0, 0.0, 100.0)
    norm_upa = np.clip(df["tx_upa_reg_100k"] / 0.8 * 100.0, 0.0, 100.0)

    # Para pequenos municípios onde não há UPA na região (ex: áreas de baixa densidade),
    # a prontidão depende principalmente de SAMU e ambulâncias
    df["escore_urgencia_rue"] = (0.50 * norm_cob + 0.35 * norm_frota + 0.15 * norm_upa).round(1)

    # Adicionar metadados de vintage
    df["vintage_urgencia"] = f"Competência {comp_samu}"
    df["fonte_urgencia"] = "DEMAS / SEIDIGI / Ministério da Saúde (Dados Abertos RUE)"

    colunas_finais = [
        "ibge7", "ibge6", "nome_municipio", "uf_sigla", "co_regiao_saude", "no_regiao_saude",
        "populacao_censo_2022", "pop_regiao_saude",
        "cob_samu_mun", "cob_samu_reg", "cob_samu_efetiva",
        "usb_mun", "usb_reg", "usa_mun", "usa_reg",
        "upa_mun", "upa_reg",
        "tx_frota_samu_reg_100k", "tx_upa_reg_100k",
        "escore_urgencia_rue", "vintage_urgencia", "fonte_urgencia"
    ]

    resultado = df[colunas_finais].copy()

    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    resultado.to_parquet(caminho_saida, index=False)
    print(f"[urgencia_samu] Processados {len(resultado)} municípios -> {caminho_saida}")

    return resultado


if __name__ == "__main__":
    processar_urgencia_samu()
