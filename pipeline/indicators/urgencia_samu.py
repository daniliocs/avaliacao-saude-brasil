"""
pipeline/indicators/urgencia_samu.py

Ingestão e processamento de indicadores oficiais da Rede de Urgência e Emergência (RUE)
com Modelo Gravitacional de Decaimento por Distância ("Hora de Ouro" / Golden Hour):
- Cobertura Populacional do SAMU 192 (DEMAS/MS - samuppc)
- Frota de Ambulâncias de Suporte Básico (USB) (DEMAS/MS - samunab)
- Frota de Ambulâncias de Suporte Avançado / UTI Móvel (USA) (DEMAS/MS - samunaa)
- Unidades de Pronto Atendimento (UPAs 24h) em Funcionamento (DEMAS/MS - upa)
- Leitos Hospitalares SUS Locais (CNES/IEPS) para identificação de Polos Hospitalares
- Distância rodoviária estimada (Haversine x 1.30) até o Polo Hospitalar de Referência
  e fator exponencial de sobrevivência/tempo-dependência: f_dist = exp(-0.012 * d_km)
"""

from __future__ import annotations

import io
import json
import os
import numpy as np
import pandas as pd

# Coordenadas oficiais IBGE para os 6 municípios emancipados ausentes na malha simplificada
COORDENADAS_FALLBACK_IBGE7 = {
    "1504752": (-2.6847, -54.6431),   # Mojuí dos Campos - PA
    "2206720": (-5.3497, -42.8153),   # Nazária - PI
    "4212650": (-28.4247, -48.8956),  # Pescaria Brava - SC
    "4220000": (-28.8344, -49.2361),  # Balneário Rincão - SC
    "4314548": (-29.0978, -51.4503),  # Pinto Bandeira - RS
    "5006275": (-19.0219, -53.0114),  # Paraíso das Águas - MS
}

UF_CENTROIDES_FALLBACK = {
    "AC": (-9.02, -70.81), "AL": (-9.57, -36.78), "AM": (-3.41, -65.85),
    "AP": (1.41, -51.77), "BA": (-12.57, -41.70), "CE": (-5.49, -39.32),
    "DF": (-15.83, -47.86), "ES": (-19.18, -40.30), "GO": (-15.93, -50.14),
    "MA": (-5.42, -45.44), "MG": (-18.51, -44.55), "MS": (-20.77, -54.78),
    "MT": (-12.68, -55.42), "PA": (-3.79, -52.48), "PB": (-7.24, -36.78),
    "PE": (-8.28, -37.86), "PI": (-7.71, -42.72), "PR": (-24.89, -51.55),
    "RJ": (-22.25, -42.66), "RN": (-5.81, -36.59), "RO": (-10.83, -63.34),
    "RR": (2.73, -61.30), "RS": (-30.01, -53.48), "SC": (-27.33, -50.44),
    "SE": (-10.57, -37.38), "SP": (-22.19, -48.79), "TO": (-10.25, -48.25),
}


def carregar_coordenadas_municipios(
    df_dim: pd.DataFrame,
    caminho_geojson: str = os.path.join("site", "assets", "geo", "br_municipios.json")
) -> tuple[pd.Series, pd.Series]:
    """Extrai centroides (lat, lon) de todos os 5.570 municípios a partir da malha GeoJSON."""
    coords = dict(COORDENADAS_FALLBACK_IBGE7)
    if os.path.exists(caminho_geojson):
        with open(caminho_geojson, "r", encoding="utf-8") as f:
            geo = json.load(f)
        for feat in geo.get("features", []):
            ibge7 = str(feat.get("properties", {}).get("id", ""))
            geom = feat.get("geometry") or {}
            gtype = geom.get("type")
            pts = []
            if gtype == "Polygon":
                for ring in geom.get("coordinates", []):
                    pts.extend(ring)
            elif gtype == "MultiPolygon":
                for poly in geom.get("coordinates", []):
                    for ring in poly:
                        pts.extend(ring)
            if pts and ibge7:
                arr = np.asarray(pts, dtype=float)
                coords[ibge7] = (float(arr[:, 1].mean()), float(arr[:, 0].mean()))

    lats, lons = [], []
    for _, row in df_dim.iterrows():
        id7 = str(row["ibge7"])
        if id7 in coords:
            lat, lon = coords[id7]
        else:
            lat, lon = UF_CENTROIDES_FALLBACK.get(str(row["uf_sigla"]), (-15.79, -47.89))
        lats.append(lat)
        lons.append(lon)
    return pd.Series(lats, index=df_dim.index), pd.Series(lons, index=df_dim.index)


def carregar_taxa_leitos_sus_local(
    diretorio_ieps: str = os.path.join("data", "raw", "ieps"),
    anos: tuple[int, ...] = (2021, 2022, 2023)
) -> pd.Series:
    """Lê a taxa média local de Leitos SUS (por 100 mil hab) no triênio 2021-2023 por ibge6."""
    frames = []
    for ano in anos:
        caminho = os.path.join(diretorio_ieps, f"ieps_{ano}.csv")
        if not os.path.exists(caminho):
            continue
        with open(caminho, "rb") as f:
            blob = f.read()
        try:
            txt = blob.decode("utf-8-sig")
        except UnicodeDecodeError:
            txt = blob.decode("latin1")
        raw = pd.read_csv(io.StringIO(txt))
        cod_cols = [c for c in raw.columns if c.startswith("C") and "IBGE" in c]
        leito_cols = [c for c in raw.columns if pd.Series([c]).str.contains(r"^Leitos SUS", regex=True).iloc[0]]
        if cod_cols and leito_cols:
            sub = raw[[cod_cols[0], leito_cols[0]]].rename(columns={cod_cols[0]: "ibge6", leito_cols[0]: "tx_leito_sus"})
            sub["ibge6"] = sub["ibge6"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
            sub = sub[sub["ibge6"].str.match(r"^\d{6}$")].copy()
            frames.append(sub)
    if not frames:
        return pd.Series(dtype=float)
    concat = pd.concat(frames, ignore_index=True)
    return concat.groupby("ibge6")["tx_leito_sus"].mean()


def _haversine_vetor(lat1: float, lon1: float, lat2_arr: np.ndarray, lon2_arr: np.ndarray) -> np.ndarray:
    """Distância geodésica Haversine em km entre um ponto e um vetor de coordenadas."""
    r = 6371.0
    p1 = np.radians(lat1)
    p2 = np.radians(lat2_arr)
    dp = np.radians(lat2_arr - lat1)
    dl = np.radians(lon2_arr - lon1)
    a = np.sin(dp / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2.0) ** 2
    return 2.0 * r * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def processar_urgencia_samu(
    caminho_dim: str = os.path.join("data", "processed", "dim_municipio.parquet"),
    diretorio_demas: str = os.path.join("data", "raw", "demas_urgencia"),
    caminho_saida: str = os.path.join("data", "processed", "indicadores_urgencia_samu.parquet")
) -> pd.DataFrame:
    """
    Consolida os indicadores de Urgência & SAMU e o Fator de Distância (Golden Hour)
    para os 5.570 municípios brasileiros.
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

    # Leitos SUS locais (CNES/IEPS) e Coordenadas Municipais para cálculo de Distância ao Polo
    tx_leito_map = carregar_taxa_leitos_sus_local()
    df["tx_leito_sus_local"] = df["ibge6"].astype(str).map(tx_leito_map).fillna(0.0)
    df["leitos_locais_sus"] = np.round(df["tx_leito_sus_local"] * df["populacao_censo_2022"] / 100_000.0).astype(int)

    df["lat"], df["lon"] = carregar_coordenadas_municipios(df)

    # Infraestrutura real CNES (UTI adulto SUS, tomógrafo SUS, PS hospitalar, unidades móveis de urgência)
    caminho_infra = os.path.join("data", "processed", "indicadores_cnes_infra.parquet")
    if os.path.exists(caminho_infra):
        infra = pd.read_parquet(caminho_infra)[["ibge7", "leitos_uti_adulto_sus", "eq_tomografo", "ps_hospitalar_sus", "unid_moveis_urgencia"]]
        infra["ibge7"] = infra["ibge7"].astype(str)
        df = df.merge(infra.rename(columns={"eq_tomografo": "tomografo_sus"}), on="ibge7", how="left")
        for c in ("leitos_uti_adulto_sus", "tomografo_sus", "ps_hospitalar_sus", "unid_moveis_urgencia"):
            df[c] = df[c].fillna(0).astype(int)
    else:
        for c in ("leitos_uti_adulto_sus", "tomografo_sus", "ps_hospitalar_sus", "unid_moveis_urgencia"):
            df[c] = 0

    # Definição de Polo Hospitalar e de Urgência (recalibrada v0.8.0):
    # Município com >= 50 leitos SUS locais (ou >= 30 + UPA/USA) E retaguarda real de alta complexidade:
    # UTI adulto SUS ou tomógrafo SUS. Polo sem UTI/tomógrafo não resolve trauma, AVC ou IAM e deixa de ser referência
    # sempre que existir polo capacitado na UF (fallback ao critério antigo apenas se a UF não tiver nenhum).
    polo_antigo = (
        (df["leitos_locais_sus"] >= 50)
        | ((df["leitos_locais_sus"] >= 30) & ((df["upa_mun"] >= 1) | (df["usa_mun"] >= 1)))
    )
    retaguarda = (df["leitos_uti_adulto_sus"] >= 1) | (df["tomografo_sus"] >= 1)
    capacitado = polo_antigo & retaguarda
    ufs_com_capacitado = set(df.loc[capacitado, "uf_sigla"])
    df["eh_polo_hospitalar"] = np.where(df["uf_sigla"].isin(ufs_com_capacitado), capacitado, polo_antigo)
    df["polo_completo"] = (df["leitos_uti_adulto_sus"] >= 1) & (df["tomografo_sus"] >= 1)

    polos_df = df[df["eh_polo_hospitalar"]].copy()
    polos_grandes_df = df[(df["leitos_locais_sus"] >= 100) & df["eh_polo_hospitalar"]].copy()

    dist_polo_km = []
    tempo_ambulancia_min = []
    polo_hospitalar_ref = []
    polo_ref_completo = []

    for _, row in df.iterrows():
        if row["eh_polo_hospitalar"]:
            dist_polo_km.append(0.0)
            tempo_ambulancia_min.append(12)
            polo_hospitalar_ref.append(f"{row['nome_municipio']} (Sede Local)")
            polo_ref_completo.append(bool(row["polo_completo"]))
            continue

        # Candidatos: Polos da mesma Região de Saúde + Grandes Polos (>= 100 leitos) da mesma UF
        cand_cir = polos_df[polos_df["co_regiao_saude"] == row["co_regiao_saude"]]
        cand_uf_grande = polos_grandes_df[polos_grandes_df["uf_sigla"] == row["uf_sigla"]]
        cand = pd.concat([cand_cir, cand_uf_grande]).drop_duplicates(subset=["ibge7"])
        if len(cand) == 0:
            cand = polos_df[polos_df["uf_sigla"] == row["uf_sigla"]]
        if len(cand) == 0:
            cand = polos_df

        d_geod = _haversine_vetor(
            float(row["lat"]),
            float(row["lon"]),
            cand["lat"].to_numpy(dtype=float),
            cand["lon"].to_numpy(dtype=float),
        )
        min_idx = int(np.argmin(d_geod))
        # Fator 1.30 de sinuosidade rodoviária média (literatura IPEA/IBGE REGIC)
        d_rod = round(float(d_geod[min_idx]) * 1.30, 1)
        p_row = cand.iloc[min_idx]

        # Tempo estimado em minutos: 12 min acionamento/estabilização + deslocamento a 70 km/h
        t_min = int(round(12.0 + (d_rod / 70.0) * 60.0))
        dist_polo_km.append(d_rod)
        tempo_ambulancia_min.append(t_min)
        polo_hospitalar_ref.append(f"{p_row['nome_municipio']} - {p_row['uf_sigla']}")
        polo_ref_completo.append(bool(p_row["polo_completo"]))

    df["dist_polo_km"] = dist_polo_km
    df["tempo_ambulancia_min"] = tempo_ambulancia_min
    df["polo_hospitalar_ref"] = polo_hospitalar_ref
    df["polo_ref_completo"] = polo_ref_completo

    # Fator exponencial da "Hora de Ouro" (Golden Hour Decay):
    # f_dist(d) = exp(-0.012 * d_km) -> 1.00 em 0km, 0.79 em 20km, 0.55 em 50km, 0.30 em 100km
    df["fator_golden_hour"] = np.clip(np.exp(-0.012 * df["dist_polo_km"]), 0.0001, 1.0).round(4)
    # Fator de capacidade resolutiva do polo de referência: polo sem UTI+tomógrafo SUS entrega só 70% do valor da rede
    df["fator_capacidade_polo"] = np.where(df["polo_ref_completo"], 1.0, 0.7)

    # 1. Componente Regional Bruto da RUE (0 a 100):
    # Saturação da frota = P90 nacional da taxa regional (derivada dos dados; antes 5,0/100k saturava regiões pequenas)
    # Suavização Bayesiana Empírica das taxas regionais (mesma metodologia do projeto): regiões de saúde pequenas
    # têm taxa por 100 mil inflada por 1 ou 2 veículos; encolhe-se para a taxa nacional agregada com peso pop/(pop+300 mil).
    w_reg = (df["pop_regiao_saude"].fillna(0) / (df["pop_regiao_saude"].fillna(0) + 300_000.0))
    nac_frota = float(((df["usb_mun"] + 2.5 * df["usa_mun"]).sum() / df["populacao_censo_2022"].sum()) * 100_000)
    nac_upa = float((df["upa_mun"].sum() / df["populacao_censo_2022"].sum()) * 100_000)
    df["tx_frota_samu_reg_100k"] = (w_reg * df["tx_frota_samu_reg_100k"] + (1 - w_reg) * nac_frota).round(2)
    df["tx_upa_reg_100k"] = (w_reg * df["tx_upa_reg_100k"] + (1 - w_reg) * nac_upa).round(2)

    ref_frota = float(df.loc[df["tx_frota_samu_reg_100k"] > 0, "tx_frota_samu_reg_100k"].quantile(0.90))
    norm_cob_reg = np.clip(df["cob_samu_efetiva"], 0.0, 100.0)
    norm_frota_reg = np.clip(df["tx_frota_samu_reg_100k"] / ref_frota * 100.0, 0.0, 100.0)
    norm_upa_reg = np.clip(df["tx_upa_reg_100k"] / 0.8 * 100.0, 0.0, 100.0)
    df["escore_rue_regional_bruto"] = (
        0.45 * norm_cob_reg + 0.35 * norm_frota_reg + 0.20 * norm_upa_reg
    ).round(1)

    # 2. Componente de Prontidão Imediata Local (0 a 100):
    # - 25 pts: Cobertura local do SAMU 192
    # - 25 pts: Base local de ambulância (USB/USA do SAMU ou unidade móvel de urgência/remoção no CNES)
    # - 25 pts: Suporte avançado 24h local (USA, UPA 24h ou Pronto-Socorro hospitalar SUS)
    # - 25 pts: Retaguarda hospitalar real: 10 leitos SUS (sat. 50) + 10 UTI adulto SUS (sat. 10 leitos) + 5 tomógrafo SUS
    pts_samu_local = 0.25 * np.clip(df["cob_samu_mun"], 0.0, 100.0)
    pts_base_ambulancia = np.where((df["usb_mun"] >= 1) | (df["usa_mun"] >= 1) | (df["unid_moveis_urgencia"] >= 1), 25.0, 0.0)
    tem_avancado_a = (df["usa_mun"] >= 1) | (df["ps_hospitalar_sus"] >= 1)
    tem_avancado_b = df["upa_mun"] >= 1
    pts_suporte_avancado = np.where(
        tem_avancado_a & tem_avancado_b, 25.0,
        np.where(tem_avancado_a | tem_avancado_b, 20.0, 0.0),
    )
    pts_leitos_locais = (
        10.0 * np.clip(df["leitos_locais_sus"] / 50.0, 0.0, 1.0)
        + 10.0 * np.clip(df["leitos_uti_adulto_sus"] / 10.0, 0.0, 1.0)
        + 5.0 * (df["tomografo_sus"] >= 1)
    )
    df["escore_prontidao_local"] = (
        pts_samu_local + pts_base_ambulancia + pts_suporte_avancado + pts_leitos_locais
    ).round(1)

    # 3. Escore Sintético Final de Urgência & Emergência (D5) ajustado pela Distância (Golden Hour) e pela capacidade do polo:
    # 35% Prontidão Imediata Local + 65% Rede Regional descontada por distância até o Polo e por sua capacidade resolutiva
    df["escore_urgencia_rue"] = np.clip(
        0.35 * df["escore_prontidao_local"]
        + 0.65 * (df["escore_rue_regional_bruto"] * df["fator_golden_hour"] * df["fator_capacidade_polo"]),
        0.0,
        100.0,
    ).round(1)

    # Adicionar metadados de vintage
    df["vintage_urgencia"] = f"Competência {comp_samu}"
    df["fonte_urgencia"] = "DEMAS / SEIDIGI / MS + Malha Geodésica IBGE (Modelo Golden Hour)"

    colunas_finais = [
        "ibge7", "ibge6", "nome_municipio", "uf_sigla", "co_regiao_saude", "no_regiao_saude",
        "populacao_censo_2022", "pop_regiao_saude",
        "cob_samu_mun", "cob_samu_reg", "cob_samu_efetiva",
        "usb_mun", "usb_reg", "usa_mun", "usa_reg",
        "upa_mun", "upa_reg",
        "tx_frota_samu_reg_100k", "tx_upa_reg_100k",
        "leitos_locais_sus", "eh_polo_hospitalar",
        "dist_polo_km", "tempo_ambulancia_min", "polo_hospitalar_ref", "fator_golden_hour",
        "leitos_uti_adulto_sus", "tomografo_sus", "ps_hospitalar_sus", "unid_moveis_urgencia",
        "polo_ref_completo", "fator_capacidade_polo",
        "escore_rue_regional_bruto", "escore_prontidao_local",
        "escore_urgencia_rue", "vintage_urgencia", "fonte_urgencia"
    ]

    resultado = df[colunas_finais].copy()

    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    resultado.to_parquet(caminho_saida, index=False)
    print(f"[urgencia_samu] Processados {len(resultado)} municípios (Polos: {int(df['eh_polo_hospitalar'].sum())}) -> {caminho_saida}")

    return resultado


if __name__ == "__main__":
    processar_urgencia_samu()
