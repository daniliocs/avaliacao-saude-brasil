#!/usr/bin/env python3
"""
pipeline/indicators/build_composite_index.py

Índice de Saúde Municipal — consolidação (v0.5.0-draft).

Entradas:
  data/processed/indicadores_sim_sinasc.parquet   (D1.1, D1.2, D1.3, D2.2 — microdados primários DATASUS)
  data/raw/ieps/ieps_{ano}.csv                    (D1.4, D2.1, D2.3, D3.1, D3.2, D3.3, D4.1, D4.2, PRIV.1, PRIV.2)
  config/limites_referencia.yaml, config/pesos.yaml, config/janelas.yaml, config/qualidade.yaml

Regras:
  * NENHUMA imputação. Dado ausente => componente ausente (NaN).
  * Dimensão calculada se houver componentes mínimos (pesos.yaml: min_componentes_por_dimensao);
    Nota Geral exige as TRÊS dimensões. Caso contrário status = sem_classificacao + motivo.
  * Normalização relativa por percentis (limites_referencia.yaml), CONGELADA por versão em
    config/limites_calculados.json.
  * Faixa de posição plausível = min/max do ranking sob 3 esquemas de pesos x 3 pares de percentis.
  * D4 e Camada Privada ficam FORA da nota (DEC-001).
"""

from __future__ import annotations

import io
import json
import os
import sys
from datetime import date

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from pipeline.indicators.estatistica import limites_percentis, normalizar  # noqa: E402

DIM_PATH = os.path.join("data", "processed", "dim_municipio.parquet")
SIM_PATH = os.path.join("data", "processed", "indicadores_sim_sinasc.parquet")
SERIE_PATH = os.path.join("data", "processed", "serie_anual_sim_sinasc.parquet")
URG_PATH = os.path.join("data", "processed", "indicadores_urgencia_samu.parquet")
ONCO_PATH = os.path.join("data", "processed", "indicadores_oncologia_tfd.parquet")
IEPS_DIR = os.path.join("data", "raw", "ieps")
LIMITES_CFG = os.path.join("config", "limites_referencia.yaml")
PESOS_CFG = os.path.join("config", "pesos.yaml")
JANELAS_CFG = os.path.join("config", "janelas.yaml")
QUALIDADE_CFG = os.path.join("config", "qualidade.yaml")
VERSAO_TXT = os.path.join("config", "metodologia_versao.txt")
LIMITES_CONGELADOS = os.path.join("config", "limites_calculados.json")

OUT_PARQUET = os.path.join("data", "processed", "indice_saude_municipal.parquet")
OUT_CSV = os.path.join("data", "processed", "indice_saude_municipal.csv")
OUT_INFO = os.path.join("data", "processed", "build_info.json")
SITE_PROCESSED = os.path.join("site", "data", "processed")

# Mapeamento EXPLÍCITO das colunas do IEPS (padrão regex único) -> nome interno.
IEPS_COLUNAS = {
    "cob_esf": r"^Cobertura ESF",
    "cob_vac_polio": r"^Cob\. Vacinal Poliomielite",
    "cob_vac_penta": r"^Cob\. Vacinal Pentavalente",
    "cob_vac_tvd1": r"^Cob\. Vacinal Tr.plice Viral D1",
    "tx_hosp_csap": r"^Hospitaliza..es CSAP",
    "tx_mort_evit": r"^Mortalidade Bruta Causas Evit.veis",
    "tx_leito_sus": r"^Leitos SUS",
    "tx_med": r"^M.dicos \(Por 1\.000",
    "tx_enf": r"^Enfermeiros \(Por 1\.000",
    "tx_med_ch": r"^M.dicos \(Por C\.H\.",
    "tx_enf_ch": r"^Enfermeiros \(Por C\.H\.",
    "tx_leito_nsus": r"^Leitos N.o-SUS",
    "cob_priv": r"^Cobertura de Planos de Sa.de",
    "pct_desp_recp_saude_mun": r"^% da Receita Pr.pria Municipal",
    "desp_tot_saude_pc_mun_def": r"^Despesa Total do Munic.pio com Sa.de",
}

IND_PARA_IEPS = {
    "D1.4": "tx_mort_evit",
    "D2.1": "icsap_10k",
    "D2.3": "cob_vac_composta",
    "D3.1": "tx_leito_sus",
    "D3.2": "tx_prof_ch",
    "D3.3": "cob_esf",
    "D4.1": "desp_tot_saude_pc_mun_def",
    "D4.2": "pct_desp_recp_saude_mun",
    "PRIV.1": "cob_priv",
    "PRIV.2": "tx_leito_nsus",
}


def carregar_yaml(caminho: str) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


def versao_metodologia() -> str:
    with open(VERSAO_TXT, encoding="utf-8-sig") as f:
        return f.read().strip()


def ler_csv_codificacao_robusta(caminho: str) -> pd.DataFrame:
    """Lê CSV tentando UTF-8 estrito e, se falhar, Latin-1 (a API do IEPS varia por ano)."""
    with open(caminho, "rb") as f:
        blob = f.read()
    try:
        texto = blob.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = blob.decode("latin1")
    return pd.read_csv(io.StringIO(texto))


def ler_ieps_ano(ano: int) -> pd.DataFrame:
    caminho = os.path.join(IEPS_DIR, f"ieps_{ano}.csv")
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"{caminho} ausente. Execute pipeline/extract/ieps_series.py {ano}.")
    raw = ler_csv_codificacao_robusta(caminho)
    ren = {}
    for interno, padrao in IEPS_COLUNAS.items():
        achadas = [c for c in raw.columns if pd.Series([c]).str.contains(padrao, regex=True).iloc[0]]
        if len(achadas) != 1:
            raise ValueError(f"IEPS {ano}: coluna '{interno}' ({padrao}) encontrada {len(achadas)}x: {achadas}")
        ren[achadas[0]] = interno
    cod = [c for c in raw.columns if c.startswith("C") and "IBGE" in c]
    if len(cod) != 1:
        raise ValueError(f"IEPS {ano}: coluna de código IBGE ambígua: {cod}")

    # Extrai também Região de Saúde (IBGE) e Nome da Região de Saúde
    reg_id_cols = [c for c in raw.columns if "Regi" in c and "Sa" in c and "IBGE" in c and "Macro" not in c]
    reg_nm_cols = [c for c in raw.columns if "Regi" in c and "Sa" in c and "IBGE" not in c and "Macro" not in c]
    extra_cols = []
    if reg_id_cols and reg_nm_cols:
        ren[reg_id_cols[0]] = "regiao_saude_id_ieps"
        ren[reg_nm_cols[0]] = "regiao_saude_nome_ieps"
        extra_cols = [reg_id_cols[0], reg_nm_cols[0]]

    out = raw[[cod[0]] + list(ren.keys())].rename(columns={cod[0]: "ibge6", **ren})
    out["ibge6"] = out["ibge6"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    # Filtra apenas linhas municipais (6 dígitos numéricos válidos)
    out = out[out["ibge6"].str.match(r"^\d{6}$")].copy()
    out["ano"] = ano

    # Derivadas anuais sem imputação
    out["cob_vac_composta"] = out[["cob_vac_polio", "cob_vac_penta", "cob_vac_tvd1"]].mean(axis=1, skipna=False)
    out["icsap_10k"] = out["tx_hosp_csap"] / 10.0
    out["tx_prof_ch"] = out["tx_med_ch"] + out["tx_enf_ch"]
    out["tx_prof_bruto"] = out["tx_med"] + out["tx_enf"]
    return out


def agregar_ieps(janelas: dict, dim_pop: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Média da janela por indicador, exigindo min_anos_validos (sem imputação)."""
    anos = sorted({a for k in IND_PARA_IEPS for a in janelas[k]["anos"]})
    longo = pd.concat([ler_ieps_ano(a) for a in anos], ignore_index=True)
    saida = pd.DataFrame({"ibge6": sorted(longo["ibge6"].unique())}).set_index("ibge6")

    # Mapeamento de Região de Saúde a partir do último ano disponível
    ult = longo.sort_values("ano").groupby("ibge6").last()
    if "regiao_saude_id_ieps" in ult.columns:
        saida["regiao_saude_id_ieps"] = ult["regiao_saude_id_ieps"].astype(str).str.replace(r"\.0$", "", regex=True)
        saida["regiao_saude_nome_ieps"] = ult["regiao_saude_nome_ieps"].astype(str)

    meta = {}
    cols_extras = ["cob_vac_polio", "cob_vac_penta", "cob_vac_tvd1", "tx_med", "tx_enf", "tx_med_ch", "tx_enf_ch", "tx_prof_bruto"]
    for ind, col in IND_PARA_IEPS.items():
        j = janelas[ind]
        sub = longo[longo["ano"].isin(j["anos"])]
        g = sub.groupby("ibge6")[col]
        n_validos = g.count()
        media = g.mean()
        media[n_validos < j.get("min_anos_validos", 1)] = np.nan
        saida[col] = media
        saida[f"{col}_n_anos"] = n_validos.reindex(saida.index).fillna(0).astype(int)
        meta[ind] = {"anos": j["anos"], "min_anos_validos": j.get("min_anos_validos", 1)}

    # Médias informativas auxiliares do triênio 2021-2023
    sub_tri = longo[longo["ano"].isin([2021, 2022, 2023])]
    for c in cols_extras:
        if c not in saida.columns:
            saida[c] = sub_tri.groupby("ibge6")[c].mean()

    saida_df = saida.reset_index()

    # Calcula taxa regionalizada de Leitos SUS por Região de Saúde (ponderada pela população SUS-dependente da CIR — Proposta B)
    tmp = saida_df.merge(dim_pop[["ibge6", "populacao_censo_2022"]], on="ibge6", how="left")
    tmp["leitos_abs_est"] = tmp["tx_leito_sus"] * tmp["populacao_censo_2022"] / 1e5
    cob_priv_pct = tmp["cob_priv"].fillna(0)
    # População SUS-dependente (descontando beneficiários de planos de saúde privados, mínimo 20% para segurança de cálculo)
    tmp["pop_sus_dependente"] = tmp["populacao_censo_2022"] * (1.0 - cob_priv_pct / 100.0).clip(0.2, 1.0)

    por_reg = tmp.groupby("regiao_saude_id_ieps", dropna=False).agg(
        leitos_reg=("leitos_abs_est", "sum"),
        pop_sus_reg=("pop_sus_dependente", "sum"),
        pop_reg=("populacao_censo_2022", "sum"),
    )
    por_reg["tx_leito_sus_reg"] = np.where(por_reg["pop_sus_reg"] > 0, por_reg["leitos_reg"] / por_reg["pop_sus_reg"] * 1e5, np.nan)
    saida_df = saida_df.merge(por_reg[["tx_leito_sus_reg"]], left_on="regiao_saude_id_ieps", right_index=True, how="left")
    # Se o município não tiver leitos SUS válidos no período, mantém NaN
    saida_df.loc[saida_df["tx_leito_sus"].isna(), "tx_leito_sus_reg"] = np.nan
    saida_df["tx_leito_sus_reg_n_anos"] = saida_df["tx_leito_sus_n_anos"]

    # Proposta B: Ajuste de Atenção Básica pela complementariedade da Saúde Suplementar (evita zerar capitais e metrópoles)
    saida_df["cob_esf_bruta"] = saida_df["cob_esf"]
    saida_df["cob_esf"] = np.minimum(100.0, saida_df["cob_esf_bruta"] + saida_df["cob_priv"].fillna(0) * 0.4).round(1)

    return saida_df, meta


def obter_limites(df: pd.DataFrame, cfg_lim: dict, versao: str) -> dict:
    """Limites congelados por versão: lê config/limites_calculados.json ou calcula e grava."""
    if os.path.exists(LIMITES_CONGELADOS):
        with open(LIMITES_CONGELADOS, encoding="utf-8") as f:
            conj = json.load(f)
        if conj.get("versao") == versao and set(conj.get("limites", {}).keys()) == set(cfg_lim["indicadores"].keys()):
            return conj["limites"]
        print(f"[composite] Limites congelados são da versão {conj.get('versao')} != {versao}: recalculando (nova versão).")
    p_inf, p_sup = cfg_lim["percentil_inferior"], cfg_lim["percentil_superior"]
    limites = {}
    for ind, d in cfg_lim["indicadores"].items():
        pior, melhor = limites_percentis(df[d["coluna"]], d["sentido"], p_inf, p_sup)
        limites[ind] = {"pior": pior, "melhor": melhor, "coluna": d["coluna"], "sentido": d["sentido"],
                        "percentis": [p_inf, p_sup], "n_municipios_base": int(df[d["coluna"]].notna().sum())}
    with open(LIMITES_CONGELADOS, "w", encoding="utf-8") as f:
        json.dump({"versao": versao, "metodo": "percentis", "gerado_em": date.today().isoformat(), "limites": limites},
                  f, indent=2, ensure_ascii=False)
    print(f"[composite] Limites por percentis gravados em {LIMITES_CONGELADOS}")
    return limites


def escores_componentes(df: pd.DataFrame, limites: dict) -> pd.DataFrame:
    for ind, lim in limites.items():
        chave = ind.replace(".", "_")
        df[f"escore_{chave}"] = normalizar(df[lim["coluna"]], lim["pior"], lim["melhor"]).round(2)
    return df


def nota_dimensoes(df: pd.DataFrame, cfg_lim: dict, pesos: dict) -> pd.DataFrame:
    pi = pesos["esquemas"]["pesos_iguais"]["indicadores"]
    ativos = {d: [i for i, v in cfg_lim["indicadores"].items() if v["dimensao"] == d and pi.get(i, 0) > 0] for d in ("D1", "D2", "D3")}
    minimos = pesos["min_componentes_por_dimensao"]
    for dim, inds in ativos.items():
        cols = [f"escore_{i.replace('.', '_')}" for i in inds]
        w = np.array([pi[i] for i in inds], dtype=float)
        mat = df[cols].to_numpy(dtype=float)
        valido = ~np.isnan(mat)
        wsum = (valido * w).sum(axis=1)
        num = np.nansum(mat * w, axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            nota = np.where(wsum > 0, num / wsum, np.nan)
        nota = np.where(valido.sum(axis=1) >= minimos[dim], nota, np.nan)
        df[f"{dim.lower()}_nota"] = np.round(nota, 1)
        df[f"{dim.lower()}_n_componentes"] = valido.sum(axis=1)
        df[f"{dim.lower()}_componentes_ausentes"] = [
            ",".join(i for i, ok in zip(inds, linha) if not ok) for linha in valido
        ]
    return df


def combinar(df: pd.DataFrame, pesos_dim: dict) -> pd.Series:
    d = df[["d1_nota", "d2_nota", "d3_nota"]].to_numpy(dtype=float)
    w = np.array([pesos_dim["D1"], pesos_dim["D2"], pesos_dim["D3"]], dtype=float)
    ok = ~np.isnan(d).any(axis=1)
    return pd.Series(np.where(ok, d @ w / w.sum(), np.nan), index=df.index)


def rank_min(s: pd.Series) -> pd.Series:
    return s.rank(ascending=False, method="min")


def sensibilidade(df: pd.DataFrame, cfg_lim: dict, pesos: dict) -> tuple[pd.Series, pd.Series]:
    """Min/max do ranking nacional sob (3 esquemas de pesos) x (3 pares de percentis)."""
    esquemas = [pesos["esquemas"][k]["dimensoes"] for k in ("pesos_iguais", "foco_resultados", "foco_atencao_primaria")]
    pi = pesos["esquemas"]["pesos_iguais"]["indicadores"]
    ativos = {i: v for i, v in cfg_lim["indicadores"].items() if pi.get(i, 0) > 0}
    minimos = pesos["min_componentes_por_dimensao"]
    ranks = []
    for p_inf, p_sup in cfg_lim["sensibilidade_percentis"]:
        tmp = pd.DataFrame(index=df.index)
        for ind, d in ativos.items():
            pior, melhor = limites_percentis(df[d["coluna"]], d["sentido"], p_inf, p_sup)
            tmp[ind] = normalizar(df[d["coluna"]], pior, melhor)
        dims = {}
        for dim in ("D1", "D2", "D3"):
            inds = [i for i, v in ativos.items() if v["dimensao"] == dim]
            w = np.array([pi[i] for i in inds], dtype=float)
            mat = tmp[inds].to_numpy(dtype=float)
            val = ~np.isnan(mat)
            with np.errstate(invalid="ignore", divide="ignore"):
                n = np.where((val * w).sum(axis=1) > 0, np.nansum(mat * w, axis=1) / (val * w).sum(axis=1), np.nan)
            dims[dim] = np.where(val.sum(axis=1) >= minimos[dim], n, np.nan)
        dd = pd.DataFrame({"d1_nota": dims["D1"], "d2_nota": dims["D2"], "d3_nota": dims["D3"]}, index=df.index)
        for esq in esquemas:
            ranks.append(rank_min(combinar(dd, esq)))
    r = pd.concat(ranks, axis=1)
    return r.min(axis=1), r.max(axis=1)


def selo_qualidade(df: pd.DataFrame, cfg_q: dict) -> pd.DataFrame:
    q = cfg_q["precisao"]

    def por_eventos(n, lim):
        return np.where(n >= lim["alta_min"], "alta", np.where(n >= lim["media_min"], "media", "baixa"))

    df["qualidade_D1_1"] = por_eventos(df["d1_1_obitos"], q["eventos_taxa"]["D1.1"])
    df["qualidade_D1_2"] = por_eventos(df["d1_2_obitos"], q["eventos_taxa"]["D1.2"])
    df["qualidade_D1_3"] = por_eventos(df["d1_3_obitos"], q["eventos_taxa"]["D1.3"])
    p = q["proporcao_base"]["D2.2"]
    s = np.where(df["d2_2_validas"] >= p["alta_min"], "alta", np.where(df["d2_2_validas"] >= p["media_min"], "media", "baixa"))
    df["qualidade_D2_2"] = np.where(df["pre7_pct_ignorado"] > q["ignorado_max_pct"], "alerta", s)
    for ind, col in IND_PARA_IEPS.items():
        n = df[f"{col}_n_anos"]
        df[f"qualidade_{ind.replace('.', '_')}"] = np.where(n >= q["ieps_anos_alta"], "alta", "media")
    return df


def construir() -> pd.DataFrame:
    print("[composite] Carregando insumos (v0.5.0-draft)...")
    versao = versao_metodologia()
    cfg_lim = carregar_yaml(LIMITES_CFG)
    pesos = carregar_yaml(PESOS_CFG)
    janelas = carregar_yaml(JANELAS_CFG)["janelas"]
    cfg_q = carregar_yaml(QUALIDADE_CFG)

    for p in (DIM_PATH, SIM_PATH):
        if not os.path.exists(p):
            print(f"[composite:ERRO] {p} não encontrado.")
            sys.exit(1)

    dim = pd.read_parquet(DIM_PATH)
    sim = pd.read_parquet(SIM_PATH).drop(columns=["ibge7", "uf_sigla"])
    ieps, meta_ieps = agregar_ieps(janelas, dim)

    df = dim.merge(sim, on="ibge6", how="left").merge(ieps, on="ibge6", how="left")
    if os.path.exists(URG_PATH):
        urg = pd.read_parquet(URG_PATH).drop(columns=["ibge6", "nome_municipio", "uf_sigla", "populacao_censo_2022"], errors="ignore")
        df = df.merge(urg, on="ibge7", how="left")
    if os.path.exists(ONCO_PATH):
        onco = pd.read_parquet(ONCO_PATH).drop(columns=["ibge6", "nome_municipio", "uf_sigla", "regiao_saude_id", "regiao_saude_nome"], errors="ignore")
        df = df.merge(onco, on="ibge7", how="left")
    assert len(df) == 5570 and df["ibge7"].is_unique, "Cardinalidade/unicidade violada após junções"

    # Preenche regiao_saude_id e regiao_saude_nome reais (438 Regiões de Saúde do SUS)
    if "regiao_saude_id_ieps" in df.columns:
        df["regiao_saude_id"] = df["regiao_saude_id_ieps"].fillna(df.get("regiao_saude_id", "A_VALIDAR"))
        df["regiao_saude_nome"] = df["regiao_saude_nome_ieps"].fillna(df.get("regiao_saude_nome", "A_VALIDAR"))
        df = df.drop(columns=["regiao_saude_id_ieps", "regiao_saude_nome_ieps"])

    # Mal definidos SIM na janela D1.1 (informativo, qualidade do registro de óbitos)
    serie = pd.read_parquet(SERIE_PATH)
    jan = serie[serie["ano"].isin(janelas["D1.1"]["anos"])].groupby("ibge6")[["obitos_total", "obitos_mal_definidos"]].sum()
    jan["pct_obitos_mal_definidos"] = (jan["obitos_mal_definidos"] / jan["obitos_total"].replace(0, np.nan) * 100).round(2)
    df = df.merge(jan[["pct_obitos_mal_definidos"]], left_on="ibge6", right_index=True, how="left")

    # Proposta A e C: Padronização etária e correção por causas mal definidas em D1.4 (Mortalidade por Causas Evitáveis)
    fator_et = df.get("fator_etario_30_69", pd.Series(1.0, index=df.index)).fillna(1.0)
    pct_mal = df["pct_obitos_mal_definidos"].fillna(0.0)
    fator_md = 1.0 + np.clip(pct_mal / 100.0, 0.0, 0.25)
    df["tx_mort_evit_bruta"] = df["tx_mort_evit"]
    df["tx_mort_evit"] = np.where(df["tx_mort_evit"].notna(), (df["tx_mort_evit_bruta"] * fator_md / fator_et).round(1), np.nan)

    # Ajuste Gravitacional Golden Hour (Decaimento por Distância) em D3.1 (Leitos SUS Efetivos)
    df["tx_leito_sus_reg_bruto"] = df["tx_leito_sus_reg"].round(1)
    if "fator_golden_hour" in df.columns and "leitos_locais_sus" in df.columns:
        fator_leito_local = np.clip(df["leitos_locais_sus"].fillna(0) / 50.0, 0.0, 1.0)
        fator_acesso_hosp = np.clip(0.25 * fator_leito_local + 0.75 * df["fator_golden_hour"].fillna(1.0), 0.0, 1.0)
        df["fator_acesso_hospitalar"] = fator_acesso_hosp.round(4)
        df["tx_leito_sus_reg"] = np.where(
            df["tx_leito_sus_reg_bruto"].notna(),
            (df["tx_leito_sus_reg_bruto"] * fator_acesso_hosp).round(2),
            np.nan,
        )
    else:
        df["fator_acesso_hospitalar"] = 1.0

    limites = obter_limites(df, cfg_lim, versao)
    df = escores_componentes(df, limites)
    df = nota_dimensoes(df, cfg_lim, pesos)
    df = selo_qualidade(df, cfg_q)

    df["nota_geral"] = combinar(df, pesos["esquemas"]["pesos_iguais"]["dimensoes"]).round(1)
    df["status"] = np.where(df["nota_geral"].notna(), "classificado", "sem_classificacao")
    motivos = []
    for _, r in df.iterrows():
        m = [f"{d.upper()} incompleta (ausentes: {r[f'{d}_componentes_ausentes'] or 'n/d'})" for d in ("d1", "d2", "d3") if pd.isna(r[f"{d}_nota"])]
        motivos.append("; ".join(m))
    df["motivo_sem_classificacao"] = motivos

    cls = df["status"] == "classificado"
    n_cls = int(cls.sum())

    df["posicao_nacional"] = np.nan
    df.loc[cls, "posicao_nacional"] = rank_min(df.loc[cls, "nota_geral"])
    df["posicao_estadual"] = np.nan
    df.loc[cls, "posicao_estadual"] = df[cls].groupby("uf_sigla")["nota_geral"].rank(ascending=False, method="min")
    df["posicao_grupo_pares"] = np.nan
    df.loc[cls, "posicao_grupo_pares"] = df[cls].groupby("porte_populacional")["nota_geral"].rank(ascending=False, method="min")
    for d in ("d1", "d2", "d3"):
        df[f"rank_{d}"] = np.nan
        df.loc[df[f"{d}_nota"].notna(), f"rank_{d}"] = rank_min(df.loc[df[f"{d}_nota"].notna(), f"{d}_nota"])

    fmin, fmax = sensibilidade(df[cls], cfg_lim, pesos)
    df["faixa_posicao_min"] = np.nan
    df["faixa_posicao_max"] = np.nan
    df.loc[cls, "faixa_posicao_min"] = np.minimum(fmin, df.loc[cls, "posicao_nacional"])
    df.loc[cls, "faixa_posicao_max"] = np.maximum(fmax, df.loc[cls, "posicao_nacional"])

    for c in ("posicao_nacional", "posicao_estadual", "posicao_grupo_pares", "faixa_posicao_min", "faixa_posicao_max",
              "rank_d1", "rank_d2", "rank_d3"):
        df[c] = df[c].astype("Int64")

    # Fase 1: Escore D5 Urgência & SAMU 192 e Modo de Índice com Urgência (10% de peso)
    if "escore_urgencia_rue" in df.columns:
        df["d5_nota"] = df["escore_urgencia_rue"].round(1)
        df["rank_d5"] = rank_min(df["d5_nota"]).astype("Int64")
        df["nota_com_urgencia"] = np.where(
            df["status"] == "classificado",
            (0.30 * df["d1_nota"] + 0.25 * df["d2_nota"] + 0.30 * df["d3_nota"] + 0.15 * df["d5_nota"]).round(1),
            np.nan
        )
        df["posicao_nacional_urgencia"] = np.nan
        df.loc[cls, "posicao_nacional_urgencia"] = rank_min(df.loc[cls, "nota_com_urgencia"])
        df["posicao_estadual_urgencia"] = np.nan
        df.loc[cls, "posicao_estadual_urgencia"] = df[cls].groupby("uf_sigla")["nota_com_urgencia"].rank(ascending=False, method="min")
        for c in ("posicao_nacional_urgencia", "posicao_estadual_urgencia"):
            df[c] = df[c].astype("Int64")
    else:
        df["d5_nota"] = np.nan
        df["rank_d5"] = pd.Series(pd.NA, dtype="Int64", index=df.index)
        df["nota_com_urgencia"] = df["nota_geral"]
        df["posicao_nacional_urgencia"] = df["posicao_nacional"]
        df["posicao_estadual_urgencia"] = df["posicao_estadual"]

    # Fase 2: Rank de Oncologia e Alta Complexidade
    if "escore_oncologia" in df.columns:
        df["rank_onco"] = rank_min(df["escore_oncologia"]).astype("Int64")
    else:
        df["escore_oncologia"] = np.nan
        df["rank_onco"] = pd.Series(pd.NA, dtype="Int64", index=df.index)

    # Fase 2: Modelo Integrado Completo (Opção 1: 25% D1 + 25% D2 + 25% D3 + 15% D5 + 10% Onco)
    if "escore_oncologia" in df.columns and "d5_nota" in df.columns:
        df["nota_integrada"] = np.where(
            df["status"] == "classificado",
            (0.25 * df["d1_nota"] + 0.25 * df["d2_nota"] + 0.25 * df["d3_nota"] + 0.15 * df["d5_nota"] + 0.10 * df["escore_oncologia"]).round(1),
            np.nan
        )
        df["posicao_nacional_integrada"] = np.nan
        df.loc[cls, "posicao_nacional_integrada"] = rank_min(df.loc[cls, "nota_integrada"])
        df["posicao_estadual_integrada"] = np.nan
        df.loc[cls, "posicao_estadual_integrada"] = df[cls].groupby("uf_sigla")["nota_integrada"].rank(ascending=False, method="min")
        for c in ("posicao_nacional_integrada", "posicao_estadual_integrada"):
            df[c] = df[c].astype("Int64")
    else:
        df["nota_integrada"] = df["nota_geral"]
        df["posicao_nacional_integrada"] = df["posicao_nacional"]
        df["posicao_estadual_integrada"] = df["posicao_estadual"]

    # Camada privada e Contexto D4 (fora da nota)
    df["leitos_priv_val"] = df["tx_leito_nsus"].round(1)
    df["cob_priv_val"] = df["cob_priv"].round(1)
    df["gasto_pc_def_val"] = df["desp_tot_saude_pc_mun_def"].round(2)
    df["pct_rec_propria_val"] = df["pct_desp_recp_saude_mun"].round(1)

    def manifesto(caminho):
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8") as f:
                return json.load(f)
        return {}

    man_ds = manifesto(os.path.join("data", "raw", "datasus", "manifest_extracao.json"))
    man_ieps = manifesto(os.path.join(IEPS_DIR, "manifest_ieps.json"))
    coleta_ds = max((v.get("data_coleta", "") for v in man_ds.values()), default="") or None
    coleta_ieps = max((v.get("data_coleta", "") for v in man_ieps.values()), default="") or None

    info = {
        "versao_metodologia": versao,
        "gerado_em": date.today().isoformat(),
        "n_municipios": int(len(df)),
        "n_classificados": n_cls,
        "n_sem_classificacao": int(len(df) - n_cls),
        "janelas": {k: v["anos"] for k, v in janelas.items()},
        "fontes": {
            "sim_sinasc": {"data_coleta": coleta_ds, "origem": "ftp.datasus.gov.br (microdados por residência)"},
            "ieps": {"data_coleta": coleta_ieps, "origem": "iepsdata.org.br (intermediário)", "indicadores": meta_ieps},
        },
        "limites": limites,
        "medias": {c: float(df[c].mean()) for c in ("nota_geral", "d1_nota", "d2_nota", "d3_nota")},
    }
    os.makedirs(os.path.dirname(OUT_PARQUET), exist_ok=True)
    with open(OUT_INFO, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)

    df.to_parquet(OUT_PARQUET, index=False)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")
    os.makedirs(SITE_PROCESSED, exist_ok=True)
    for nome in ("indice_saude_municipal.parquet", "indice_saude_municipal.csv"):
        src = os.path.join("data", "processed", nome)
        with open(src, "rb") as fi, open(os.path.join(SITE_PROCESSED, nome), "wb") as fo:
            fo.write(fi.read())

    print(f"[composite] {n_cls} classificados / {len(df) - n_cls} sem classificação.")
    print(f"[composite] Médias: Nota {info['medias']['nota_geral']:.1f} | D1 {info['medias']['d1_nota']:.1f} | "
          f"D2 {info['medias']['d2_nota']:.1f} | D3 {info['medias']['d3_nota']:.1f}")
    return df


if __name__ == "__main__":
    construir()
