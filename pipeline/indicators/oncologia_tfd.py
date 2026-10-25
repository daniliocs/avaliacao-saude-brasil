"""
pipeline/indicators/oncologia_tfd.py

Processamento dos indicadores oficiais da Linha de Cuidado Oncológico e Alta Complexidade (Fase 2):
- Centros de Assistência de Alta Complexidade em Oncologia (CACON) e UNACON (CNES/DATASUS)
- Distância rodoviária georreferenciada (Haversine x 1.30) e tempo de viagem até o centro oncológico
- Cumprimento da Lei dos 60 Dias (Lei Federal nº 12.732/2012) via Painel-Oncologia DATASUS
- Taxa de Conversão Terapêutica (proporção de pacientes diagnosticados que efetivamente iniciam tratamento no SUS,
  penalizando a fila oculta TRATAMENTO = 5 documentada pelo TCU Acórdão 1.944/2019 e INCA)
- Cumprimento Efetivo da Lei dos 60 Dias sobre TODOS os diagnosticados (incluindo pacientes retidos sem tratamento)
- Tempo mediano real de fila pós-biópsia (em dias, excluindo atos cirúrgicos concomitantes DT_DIAG = DT_TRAT)
- Proporção de pacientes que necessitam de Tratamento Fora de Domicílio (% tratamento fora - TFD)
- Proporção de diagnóstico precoce auditada (Estádios I e II, com filtro de inconsistência de preenchimento padrão Estádio 1)
- Desfecho clínico padronizado e sobrevida estimada (combinando Taxa de Conversão Terapêutica e Desfecho Padronizado D1)
- Escore Sintético de Cuidado Oncológico e Alta Complexidade (0 a 100) calibrado contra o Padrão-Ouro
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd

from pipeline.indicators.urgencia_samu import carregar_coordenadas_municipios


def haversine_vetor(lat1: float, lon1: float, lat2_arr: np.ndarray, lon2_arr: np.ndarray) -> np.ndarray:
    """Distância geodésica Haversine em km entre um ponto e um vetor de coordenadas."""
    r = 6371.0
    p1 = np.radians(lat1)
    p2 = np.radians(lat2_arr)
    dp = np.radians(lat2_arr - lat1)
    dl = np.radians(lon2_arr - lon1)
    a = np.sin(dp / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2.0) ** 2
    return 2.0 * r * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def processar_oncologia_tfd(
    caminho_dim: str = os.path.join("data", "processed", "dim_municipio.parquet"),
    caminho_pobr: str = os.path.join("data", "raw", "oncologia", "painel_oncologia_2021_2023.parquet"),
    caminho_cnes: str = os.path.join("data", "raw", "oncologia", "cnes_oncologia_2023.parquet"),
    caminho_saida: str = os.path.join("data", "processed", "indicadores_oncologia_tfd.parquet"),
) -> pd.DataFrame:
    if not os.path.exists(caminho_dim):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_dim}")
    if not os.path.exists(caminho_pobr):
        raise FileNotFoundError(f"Arquivo Painel-Oncologia não encontrado: {caminho_pobr}. Execute oncologia_ftp.py.")
    if not os.path.exists(caminho_cnes):
        raise FileNotFoundError(f"Arquivo CNES Oncologia não encontrado: {caminho_cnes}. Execute oncologia_ftp.py.")

    dim = pd.read_parquet(caminho_dim)
    dim["lat"], dim["lon"] = carregar_coordenadas_municipios(dim)

    # 1. Mapeamento de Hospitais CACON / UNACON (CNES)
    cnes = pd.read_parquet(caminho_cnes)
    muns_onco = set(cnes["ibge6"].astype(str))
    dim["eh_polo_onco"] = dim["ibge6"].astype(str).isin(muns_onco)
    polos = dim[dim["eh_polo_onco"]].copy()

    # Mapeamento detalhado das habilitações de alta complexidade em oncologia
    cnes["hab"] = cnes["hab"].astype(str)
    cnes["ibge6_str"] = cnes["ibge6"].astype(str)
    polo_habs = cnes.groupby("ibge6_str")["hab"].apply(set).to_dict()
    polo_cnes_cnt = cnes.groupby("ibge6_str")["cnes"].nunique().to_dict()

    # Distância rodoviária estimada até o CACON/UNACON mais próximo
    dist_km = []
    tempo_min = []
    polo_nome = []
    polo_ibge_ref = []

    for _, row in dim.iterrows():
        ibge6_str = str(row["ibge6"])
        if row["eh_polo_onco"]:
            dist_km.append(0.0)
            tempo_min.append(15)
            polo_nome.append(f"{row['nome_municipio']} (Sede Local)")
            polo_ibge_ref.append(ibge6_str)
            continue

        cand = polos[polos["uf_sigla"] == row["uf_sigla"]]
        if len(cand) == 0:
            cand = polos

        d_geod = haversine_vetor(
            float(row["lat"]),
            float(row["lon"]),
            cand["lat"].to_numpy(dtype=float),
            cand["lon"].to_numpy(dtype=float),
        )
        min_idx = int(np.argmin(d_geod))
        d_rod = round(float(d_geod[min_idx]) * 1.30, 1)
        t_est = int(round(20.0 + (d_rod / 70.0) * 60.0))
        p_row = cand.iloc[min_idx]

        dist_km.append(d_rod)
        tempo_min.append(t_est)
        polo_nome.append(f"{p_row['nome_municipio']} - {p_row['uf_sigla']}")
        polo_ibge_ref.append(str(p_row["ibge6"]))

    dim["dist_cacon_km"] = dist_km
    dim["tempo_cacon_min"] = tempo_min
    dim["cacon_referencia"] = polo_nome
    dim["polo_ibge_ref"] = polo_ibge_ref

    # Mapeia tratamentos de ponta para o polo de referência de cada município
    tipo_centro_list = []
    imuno_list = []
    radio_list = []
    cirurg_list = []
    ped_list = []
    hemo_list = []
    centros_cnt_list = []

    for p_ibge in polo_ibge_ref:
        habs = polo_habs.get(p_ibge, set())
        eh_cacon = bool(habs & {"1711", "1712", "1713", "1714"})
        tipo_centro_list.append("CACON (Centro Integral)" if eh_cacon else "UNACON (Unidade Especializada)")
        # 1708, 1711, 1713, 1714, 1718: Quimioterapia de Alta Complexidade habilitada no SUS para Imunoterapia e Terapia Alvo
        imuno_list.append(bool(habs & {"1708", "1711", "1713", "1714", "1718"}))
        # 1707, 1713, 1714, 1717, 1719, 1720, 1722: Radioterapia Megavoltagem, IMRT e Braquiterapia de Alta Taxa
        radio_list.append(bool(habs & {"1707", "1713", "1714", "1717", "1719", "1720", "1722"}))
        # 1715, 1723, 1711, 1712, 1713, 1714: Cirurgia Oncológica Habilitada
        cirurg_list.append(bool(habs & {"1715", "1723", "1711", "1712", "1713", "1714"}))
        # 1709, 1710, 1712, 1714: Oncologia Pediátrica
        ped_list.append(bool(habs & {"1709", "1710", "1712", "1714"}))
        # 1713: Hematologia Oncológica & Transplante de Células-Tronco (TMO)
        hemo_list.append(bool(habs & {"1713"}))
        centros_cnt_list.append(int(polo_cnes_cnt.get(p_ibge, 1)))

    dim["polo_tipo_centro"] = tipo_centro_list
    dim["polo_imunoterapia_alvo"] = imuno_list
    dim["polo_radio_avancada"] = radio_list
    dim["polo_cirurgia_onco"] = cirurg_list
    dim["polo_onco_pediatrica"] = ped_list
    dim["polo_hematologia_tmo"] = hemo_list
    dim["polo_total_centros"] = centros_cnt_list

    # 2. Processamento do Painel-Oncologia DATASUS (Triênio 2021–2023)
    pobr = pd.read_parquet(caminho_pobr)
    pobr["dias"] = pd.to_numeric(pobr["TEMPO_TRAT"], errors="coerce")
    pobr["is_tratado"] = pobr["TRATAMENTO"].isin(["1", "2", "3", "4"]) & pobr["dias"].notna() & (pobr["dias"] >= 0) & (pobr["dias"] <= 365)
    pobr["is_60d"] = pobr["is_tratado"] & (pobr["dias"] <= 60)
    pobr["is_est1"] = pobr["ESTADIAM"] == "1"
    pobr["is_est2"] = pobr["ESTADIAM"] == "2"
    pobr["is_est34"] = pobr["ESTADIAM"].isin(["3", "4"])

    # Contagem sobre TODOS os casos diagnosticados (incluindo TRATAMENTO = 5: sem informação de tratamento)
    # Conforme Nota Técnica do INCA e Acórdão TCU 1.944/2019, ignorar TRATAMENTO = 5 gera grave viés de
    # sobrevivência da fila (ex.: São Luís/MA tem 78,4% dos pacientes diagnosticados sem registro de tratamento).
    mun_diag = pobr.groupby("MUN_RESID").agg(
        diag_total=("TRATAMENTO", "count"),
        trat_total=("is_tratado", "sum"),
        trat_60d=("is_60d", "sum"),
        n_est1=("is_est1", "sum"),
        n_est2=("is_est2", "sum"),
        n_est34=("is_est34", "sum"),
    ).reset_index()

    # Filtro de auditoria de estadiamento:
    # Em alguns serviços locais (ex.: Macapá/AP), o sistema de faturamento preenche 'ESTADIAM = 1' por padrão
    # administrativo (gerando 81% de Estádio I artificial, com Estádio I > 10x Estádio II).
    # Quando n_est1 > 2.0 * n_est2 (com n_est1 > 15), o estadiamento municipal é marcado como inconsistente
    # e suavizado para o prior nacional auditado.
    mun_diag["est_total"] = mun_diag["n_est1"] + mun_diag["n_est2"] + mun_diag["n_est34"]
    mun_diag["est_consistente"] = ~((mun_diag["n_est1"] > 2.0 * mun_diag["n_est2"].clip(lower=1)) & (mun_diag["n_est1"] > 15))
    mun_diag["pct_ini_limpo"] = np.where(
        mun_diag["est_consistente"] & (mun_diag["est_total"] >= 10),
        (mun_diag["n_est1"] + mun_diag["n_est2"]) / mun_diag["est_total"] * 100.0,
        np.nan,
    )
    mun_diag["pct_conversao_bruta"] = np.where(
        mun_diag["diag_total"] > 0,
        mun_diag["trat_total"] / mun_diag["diag_total"] * 100.0,
        np.nan,
    )
    mun_diag["pct_60d_efetivo_bruto"] = np.where(
        mun_diag["diag_total"] > 0,
        mun_diag["trat_60d"] / mun_diag["diag_total"] * 100.0,
        np.nan,
    )

    # Casos válidos com tempo até o tratamento conhecido (0 a 365 dias)
    val = pobr[pobr["dias"].notna() & (pobr["dias"] >= 0) & (pobr["dias"] <= 365)].copy()
    val["ate_60"] = val["dias"] <= 60
    val["fora_mun"] = val["MUN_RESID"] != val["MUN_TRATAM"]
    val["estadio_valido"] = val["ESTADIAM"].isin(["1", "2", "3", "4"])
    val["estadio_inicial"] = val["ESTADIAM"].isin(["1", "2"])

    # Nota Técnica Painel-Oncologia (INCA/MS):
    # Registros com dias == 0 (DT_DIAG == DT_TRAT) correspondem em 94,9% a cirurgias em AIH
    # onde o diagnóstico histopatológico foi registrado concomitantemente ao ato cirúrgico
    # (sem biópsia ambulatorial prévia vinculada no SIA/BPA).
    # Para medir o TEMPO MEDIANO REAL DE ESPERA EM FILA (do diagnóstico prévio até o agendamento
    # de Quimioterapia, Radioterapia ou Cirurgia Eletiva), utilizam-se estritamente os casos com
    # fila pós-biópsia mensurada (dias > 0, isto é, DT_TRAT > DT_DIAG).
    fila = val[val["dias"] > 0].copy()
    fila["fila_ate_60"] = fila["dias"] <= 60

    # Priors nacionais empíricos
    nac_pct_60 = float(val["ate_60"].mean() * 100.0)
    nac_pct_fila_60 = float(fila["fila_ate_60"].mean() * 100.0)
    nac_med_fila = float(fila["dias"].median())
    nac_conv = float(mun_diag["trat_total"].sum() / mun_diag["diag_total"].sum() * 100.0)
    nac_60_ef = float(mun_diag["trat_60d"].sum() / mun_diag["diag_total"].sum() * 100.0)
    nac_ini_clean = float(mun_diag["pct_ini_limpo"].dropna().median())

    # Carrega mapeamento de Região de Saúde (CIR) e notas estruturais/desfecho do índice principal
    path_ind = os.path.join("data", "processed", "indice_saude_municipal.parquet")
    if os.path.exists(path_ind):
        df_ind = pd.read_parquet(path_ind)
        mapa_cir = df_ind.set_index("ibge6")[["regiao_saude_id", "regiao_saude_nome"]].to_dict(orient="index")
        cols_ind = df_ind[["ibge6", "d1_nota", "d2_nota", "d3_nota"]].copy()
        cols_ind["ibge6_str"] = cols_ind["ibge6"].astype(str)
    else:
        mapa_cir = {}
        cols_ind = pd.DataFrame(columns=["ibge6_str", "d1_nota", "d2_nota", "d3_nota"])

    val["regiao_saude_id"] = val["MUN_RESID"].map(lambda x: mapa_cir.get(str(x), {}).get("regiao_saude_id", ""))
    val["regiao_saude_nome"] = val["MUN_RESID"].map(lambda x: mapa_cir.get(str(x), {}).get("regiao_saude_nome", ""))
    fila["regiao_saude_id"] = fila["MUN_RESID"].map(lambda x: mapa_cir.get(str(x), {}).get("regiao_saude_id", ""))

    # Agregação na Região de Saúde (CIR) com suavização Bayesiana em relação ao prior nacional
    cir_val = val[val["regiao_saude_id"] != ""].groupby("regiao_saude_id").agg(
        cir_casos=("dias", "count"),
        cir_ate_60=("ate_60", "sum"),
        cir_estadiados=("estadio_valido", "sum"),
        cir_iniciais=("estadio_inicial", "sum"),
    ).reset_index()

    cir_fila = fila[fila["regiao_saude_id"] != ""].groupby("regiao_saude_id").agg(
        cir_n_fila=("dias", "count"),
        cir_med_fila=("dias", "median"),
        cir_fila_60=("fila_ate_60", "sum"),
    ).reset_index()

    cir_grp = cir_val.merge(cir_fila, on="regiao_saude_id", how="left")
    w_cir_60 = cir_grp["cir_casos"] / (cir_grp["cir_casos"] + 200.0)
    cir_grp["cir_pct_60"] = w_cir_60 * (cir_grp["cir_ate_60"] / cir_grp["cir_casos"] * 100.0) + (1.0 - w_cir_60) * nac_pct_60

    n_cf = cir_grp["cir_n_fila"].fillna(0)
    w_cir_fila = n_cf / (n_cf + 150.0)
    cir_grp["cir_med_dias"] = w_cir_fila * cir_grp["cir_med_fila"].fillna(nac_med_fila) + (1.0 - w_cir_fila) * nac_med_fila
    cir_raw_f60 = np.where(n_cf > 0, cir_grp["cir_fila_60"].fillna(0) / n_cf * 100.0, nac_pct_fila_60)
    cir_grp["cir_pct_fila_60"] = w_cir_fila * cir_raw_f60 + (1.0 - w_cir_fila) * nac_pct_fila_60

    # Identificar se a própria Região de Saúde tem CACON/UNACON
    dim["regiao_saude_id"] = dim["ibge6"].map(lambda x: mapa_cir.get(str(x), {}).get("regiao_saude_id", ""))
    dim["regiao_saude_nome"] = dim["ibge6"].map(lambda x: mapa_cir.get(str(x), {}).get("regiao_saude_nome", ""))
    cirs_com_onco = set(dim[dim["eh_polo_onco"]]["regiao_saude_id"].unique())
    dim["tem_cacon_regiao"] = dim["regiao_saude_id"].isin(cirs_com_onco)

    # Agregação Municipal direta
    mun_val = val.groupby("MUN_RESID").agg(
        casos_total=("dias", "count"),
        casos_ate_60=("ate_60", "sum"),
        casos_fora=("fora_mun", "sum"),
        casos_estadiados=("estadio_valido", "sum"),
        casos_iniciais=("estadio_inicial", "sum"),
    ).reset_index()

    mun_fila = fila.groupby("MUN_RESID").agg(
        casos_fila=("dias", "count"),
        tempo_mediano_fila=("dias", "median"),
        casos_fila_60=("fila_ate_60", "sum"),
    ).reset_index()

    dim["ibge6_str"] = dim["ibge6"].astype(str)
    df = dim.merge(mun_val, left_on="ibge6_str", right_on="MUN_RESID", how="left")
    df = df.merge(mun_fila, left_on="ibge6_str", right_on="MUN_RESID", how="left", suffixes=("", "_f"))
    df = df.merge(mun_diag, left_on="ibge6_str", right_on="MUN_RESID", how="left", suffixes=("", "_d"))
    df = df.merge(
        cir_grp[["regiao_saude_id", "cir_pct_60", "cir_med_dias", "cir_pct_fila_60"]],
        on="regiao_saude_id",
        how="left",
    )
    df = df.merge(cols_ind[["ibge6_str", "d1_nota", "d2_nota", "d3_nota"]], on="ibge6_str", how="left")

    df["casos_total"] = df["casos_total"].fillna(0).astype(int)
    df["casos_diagnosticados"] = df["diag_total"].fillna(0).astype(int)
    df["casos_fila"] = df["casos_fila"].fillna(0).astype(int)
    df["casos_estadiados"] = df["casos_estadiados"].fillna(0).astype(int)

    df["pct_fora"] = np.where(
        df["casos_total"] > 0,
        (df["casos_fora"] / df["casos_total"] * 100.0).round(1),
        np.where(df["eh_polo_onco"], 0.0, 100.0),
    )

    # Suavização Bayesiana Empírica de 2 níveis (Município -> Região de Saúde CIR -> Nacional):
    w_60 = df["casos_total"] / (df["casos_total"] + 150.0)
    raw_60 = np.where(df["casos_total"] > 0, df["casos_ate_60"] / df["casos_total"] * 100.0, df["cir_pct_60"].fillna(nac_pct_60))
    df["pct_60d_onco"] = (w_60 * raw_60 + (1.0 - w_60) * df["cir_pct_60"].fillna(nac_pct_60)).round(1)

    w_diag = df["casos_diagnosticados"] / (df["casos_diagnosticados"] + 150.0)
    df["pct_conversao_trat"] = (w_diag * df["pct_conversao_bruta"].fillna(nac_conv) + (1.0 - w_diag) * nac_conv).round(1)
    df["pct_60d_sobre_diag"] = (w_diag * df["pct_60d_efetivo_bruto"].fillna(nac_60_ef) + (1.0 - w_diag) * nac_60_ef).round(1)

    w_fila = df["casos_fila"] / (df["casos_fila"] + 100.0)
    raw_med = df["tempo_mediano_fila"].fillna(df["cir_med_dias"].fillna(nac_med_fila))
    df["tempo_mediano_onco_dias"] = (w_fila * raw_med + (1.0 - w_fila) * df["cir_med_dias"].fillna(nac_med_fila)).round(1)

    raw_f60 = np.where(df["casos_fila"] > 0, df["casos_fila_60"] / df["casos_fila"] * 100.0, df["cir_pct_fila_60"].fillna(nac_pct_fila_60))
    df["pct_60d_fila_pos_biopsia"] = (w_fila * raw_f60 + (1.0 - w_fila) * df["cir_pct_fila_60"].fillna(nac_pct_fila_60)).round(1)

    # Diagnóstico precoce com filtro de consistência de estadiamento (elimina viés administrativo Estádio 1 default)
    w_est_c = np.where(
        df["est_consistente"].fillna(False),
        df["est_total"].fillna(0) / (df["est_total"].fillna(0) + 150.0),
        0.0,
    )
    df["pct_diagnostico_precoce"] = (w_est_c * df["pct_ini_limpo"].fillna(nac_ini_clean) + (1.0 - w_est_c) * nac_ini_clean).round(1)

    # 3. Desfechos Clínicos: Óbitos Prematuros por Câncer (SIM Triênio 2021–2023)
    sim_dfs = []
    for yr in [2021, 2022, 2023]:
        sim_path = os.path.join("data", "raw", "datasus", f"sim_{yr}.parquet")
        if os.path.exists(sim_path):
            d = pd.read_parquet(sim_path, columns=["CODMUNRES", "CAUSABAS", "IDADE"])
            d["is_cancer"] = d["CAUSABAS"].astype(str).str.startswith("C")
            idade_num = pd.to_numeric(d["IDADE"], errors="coerce").fillna(0)
            d["is_prematuro"] = d["is_cancer"] & (idade_num >= 430) & (idade_num <= 469)
            sim_dfs.append(d[d["is_prematuro"]])

    if sim_dfs:
        sim_prem = pd.concat(sim_dfs, ignore_index=True)
        ob_prem = sim_prem.groupby("CODMUNRES").size().rename("obitos_cancer_prem_trienio").reset_index()
        ob_prem["ibge6_str"] = ob_prem["CODMUNRES"].astype(str)
        df = df.merge(ob_prem[["ibge6_str", "obitos_cancer_prem_trienio"]], on="ibge6_str", how="left")
    else:
        df["obitos_cancer_prem_trienio"] = 0

    df["obitos_cancer_prem_trienio"] = df["obitos_cancer_prem_trienio"].fillna(0)
    df["pop_30_69"] = df["populacao_censo_2022"] * 0.52
    df["tx_morte_prem_bruta"] = ((df["obitos_cancer_prem_trienio"] / 3.0) / df["pop_30_69"] * 100000.0)

    cir_mort = df[df["regiao_saude_id"] != ""].groupby("regiao_saude_id").agg(
        cir_ob=("obitos_cancer_prem_trienio", "sum"),
        cir_pop=("pop_30_69", "sum"),
    ).reset_index()
    cir_mort["cir_tx_prem"] = ((cir_mort["cir_ob"] / 3.0) / cir_mort["cir_pop"] * 100000.0)
    df = df.merge(cir_mort[["regiao_saude_id", "cir_tx_prem"]], on="regiao_saude_id", how="left")

    w_mort = df["pop_30_69"] / (df["pop_30_69"] + 15000.0)
    df["tx_cancer_prem_bayes"] = (
        w_mort * df["tx_morte_prem_bruta"]
        + (1.0 - w_mort) * df["cir_tx_prem"].fillna(df["tx_morte_prem_bruta"].mean())
    ).round(1)

    # 4. Cálculo do Escore de Cuidado Oncológico Calibrado contra o Padrão-Ouro e Consistência Epidemiológica
    # Pilar 1: Agilidade & Acesso Efetivo em 60 Dias (30% de peso)
    # Combina:
    # - 35%: Cumprimento da Lei dos 60 dias entre tratados (benchmark padrão-ouro: 95%)
    # - 35%: Cumprimento EFETIVO em até 60 dias sobre TODOS os diagnosticados (penaliza a fila oculta TRATAMENTO=5
    #        documentada pelo TCU Acórdão 1.944/2019, onde capitais com gargalo severo deixam >70% dos diagnosticados sem tratamento)
    # - 30%: Tempo mediano de fila pós-biópsia (benchmark <= 21 dias, crítico >= 110 dias)
    s_60_trat = np.clip((df["pct_60d_onco"] - 25.0) / (95.0 - 25.0) * 100.0, 0.0, 100.0)
    s_60_efet = np.clip((df["pct_60d_sobre_diag"] - 10.0) / (65.0 - 10.0) * 100.0, 0.0, 100.0)
    s_med_fila = np.clip((110.0 - df["tempo_mediano_onco_dias"]) / (110.0 - 21.0) * 100.0, 0.0, 100.0)
    c_agil = np.clip(0.35 * s_60_trat + 0.35 * s_60_efet + 0.30 * s_med_fila, 0.0, 100.0)

    # Pilar 2: Diagnóstico Precoce Auditado & Rastreamento na Atenção Primária (20% de peso)
    # Combina a proporção de Estádios I e II (auditada contra preenchimento administrativo padrão) e a capacidade de rastreio da APS (D2)
    s_estadio = np.clip((df["pct_diagnostico_precoce"] - 15.0) / (60.0 - 15.0) * 100.0, 0.0, 100.0)
    c_precoce = np.clip(0.65 * s_estadio + 0.35 * df["d2_nota"].fillna(50.0), 0.0, 100.0)

    # Pilar 3: Efetividade Terapêutica & Desfecho Clínico Padronizado (25% de peso)
    # Em vez de premiar taxas brutas de mortalidade por câncer não padronizadas por faixa fina de idade e subnotificação
    # (que distorcem estados mais jovens e com alta proporção de óbitos mal definidos no Norte/Nordeste, conforme INCA e CONCORD-3),
    # avalia:
    # - 45%: Taxa de Conversão Terapêutica (proporção de pacientes diagnosticados que efetivamente conseguem iniciar tratamento)
    # - 55%: Sobrevida e Controle de Mortalidade Evitável Padronizada por Idade e Causas Mal Definidas (D1)
    s_conv = np.clip((df["pct_conversao_trat"] - 18.0) / (75.0 - 18.0) * 100.0, 0.0, 100.0)
    c_desfecho = np.clip(0.45 * s_conv + 0.55 * df["d1_nota"].fillna(50.0), 0.0, 100.0)

    # Pilar 4: Resolutividade Local (Autonomia TFD), Retaguarda Hospitalar (D3) & Terapias de Ponta (25% de peso)
    # Sub-bloco A (35 pts): Resolutividade Local (20 pts * (1 - pct_fora/100)) + Sede de Polo Habilitado (15 pts)
    s_retencao = 20.0 * (1.0 - np.clip(df["pct_fora"], 0.0, 100.0) / 100.0) + np.where(df["eh_polo_onco"], 15.0, 0.0)

    # Sub-bloco B (45 pts): Acesso Regional a Terapias de Ponta decaído pela distância rodoviária
    f_dist = np.exp(-0.008 * df["dist_cacon_km"])
    s_ponta = (
        10.0
        + np.where(df["polo_imunoterapia_alvo"], 12.0, 0.0)
        + np.where(df["polo_radio_avancada"], 8.0, 0.0)
        + np.where(df["polo_cirurgia_onco"], 7.0, 0.0)
        + np.where(df["polo_tipo_centro"].str.startswith("CACON"), 4.0, 0.0)
        + np.where(df["polo_onco_pediatrica"], 2.0, 0.0)
        + np.where(df["polo_hematologia_tmo"], 2.0, 0.0)
    ) * f_dist

    # Sub-bloco C (20 pts): Retaguarda Hospitalar e Densidade Tecnológica (D3 Estrutura/Leitos/UTI)
    s_retaguarda = 0.20 * df["d3_nota"].fillna(50.0)
    c_acesso = np.clip(s_retencao + s_ponta + s_retaguarda, 0.0, 100.0)

    df["escore_oncologia"] = (
        0.30 * c_agil
        + 0.20 * c_precoce
        + 0.25 * c_desfecho
        + 0.25 * c_acesso
    ).round(1)

    df["vintage_oncologia"] = "Triênio 2021–2023 / CNES 202312"
    df["fonte_oncologia"] = "Painel-Oncologia DATASUS (Lei 12.732/2012) + CNES Habilitações + SIM"

    colunas_finais = [
        "ibge7", "ibge6", "nome_municipio", "uf_sigla", "regiao_saude_id", "regiao_saude_nome",
        "eh_polo_onco", "dist_cacon_km", "tempo_cacon_min", "cacon_referencia", "tem_cacon_regiao",
        "casos_total", "casos_diagnosticados", "pct_conversao_trat", "pct_60d_sobre_diag",
        "pct_60d_onco", "tempo_mediano_onco_dias", "pct_fora", "pct_diagnostico_precoce",
        "tx_cancer_prem_bayes", "escore_oncologia", "polo_tipo_centro", "polo_imunoterapia_alvo", "polo_radio_avancada",
        "polo_cirurgia_onco", "polo_onco_pediatrica", "polo_hematologia_tmo", "polo_total_centros",
        "vintage_oncologia", "fonte_oncologia",
    ]

    resultado = df[colunas_finais].copy()
    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    resultado.to_parquet(caminho_saida, index=False)
    print(f"[oncologia_tfd] Indicadores salvos em {caminho_saida} ({len(resultado)} municípios).")
    return resultado


if __name__ == "__main__":
    processar_oncologia_tfd()
