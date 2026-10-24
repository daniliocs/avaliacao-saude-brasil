#!/usr/bin/env python3
"""
pipeline/validate/cross_check_sources.py

Auditoria cruzada entre fontes de dados para o ano de 2022:
1. SIM/SINASC (DATASUS, microdados por residência) vs. Registro Civil IBGE (SIDRA 2654 / 2609):
   - Quantifica o sub-registro cartorário de óbitos infantis por UF e em municípios críticos (ex.: Marabá/PA).
2. SINASC (microdados primários) vs. IEPS Data (repositório intermediário):
   - Verifica a concordância do indicador D2.2 (% de nascidos vivos com 7+ consultas de pré-natal).

Salva relatório auditável em data/processed/relatorio_comparacao_fontes.json.
"""

import json
import os
import numpy as np
import pandas as pd

SERIE_PATH = os.path.join("data", "processed", "serie_anual_sim_sinasc.parquet")
DIM_PATH = os.path.join("data", "processed", "dim_municipio.parquet")
IBGE_OBITOS_PATH = os.path.join("data", "raw", "ibge_obitos_infantis_2022.json")
IBGE_NV_PATH = os.path.join("data", "raw", "ibge_nascidos_vivos_2022.json")
IEPS_2022_PATH = os.path.join("data", "raw", "ieps_indicadores_2022.csv")
OUT_REPORT = os.path.join("data", "processed", "relatorio_comparacao_fontes.json")


def executar_auditoria() -> dict:
    dim = pd.read_parquet(DIM_PATH)
    serie = pd.read_parquet(SERIE_PATH)
    s22 = serie[serie["ano"] == 2022].copy()

    df = dim[["ibge7", "ibge6", "nome_municipio", "uf_sigla", "regiao_macro", "populacao_censo_2022"]].merge(
        s22, on="ibge6", how="left"
    ).fillna({"obitos_infantis": 0, "nascidos_vivos": 0, "cons_validas": 0, "cons_7mais": 0})

    relatorio = {"ano_referencia": 2022}

    # 1. Comparação SIM/SINASC vs. Registro Civil IBGE
    if os.path.exists(IBGE_OBITOS_PATH) and os.path.exists(IBGE_NV_PATH):
        with open(IBGE_OBITOS_PATH, encoding="utf-8") as f:
            ibge_ob = json.load(f)
        with open(IBGE_NV_PATH, encoding="utf-8") as f:
            ibge_nv = json.load(f)

        df["ibge_obitos_2022"] = df["ibge7"].map(ibge_ob).fillna(0).astype(int)
        df["ibge_nv_2022"] = df["ibge7"].map(ibge_nv).fillna(0).astype(int)

        tot_sim = int(df["obitos_infantis"].sum())
        tot_ibge = int(df["ibge_obitos_2022"].sum())
        tot_sinasc = int(df["nascidos_vivos"].sum())
        tot_ibge_nv = int(df["ibge_nv_2022"].sum())

        por_uf = []
        for uf, g in df.groupby("uf_sigla"):
            s_ob = int(g["obitos_infantis"].sum())
            i_ob = int(g["ibge_obitos_2022"].sum())
            s_nv = int(g["nascidos_vivos"].sum())
            i_nv = int(g["ibge_nv_2022"].sum())
            por_uf.append({
                "uf": uf,
                "obitos_sim": s_ob,
                "obitos_cartorio_ibge": i_ob,
                "diferenca_obitos_sim_menos_ibge": s_ob - i_ob,
                "razao_cartorio_sobre_sim": round(i_ob / s_ob, 3) if s_ob > 0 else None,
                "tmi_sim_sinasc": round(s_ob / s_nv * 1000, 2) if s_nv > 0 else None,
                "tmi_cartorio_ibge": round(i_ob / i_nv * 1000, 2) if i_nv > 0 else None,
            })

        por_uf.sort(key=lambda x: (x["razao_cartorio_sobre_sim"] or 1.0))

        # Casos emblemáticos de divergência em municípios > 100 mil hab.
        grandes = df[df["populacao_censo_2022"] >= 100_000].copy()
        grandes["diff_obitos"] = grandes["obitos_infantis"] - grandes["ibge_obitos_2022"]
        grandes["tmi_sim"] = (grandes["obitos_infantis"] / grandes["nascidos_vivos"].replace(0, np.nan) * 1000).round(2)
        grandes["tmi_ibge"] = (grandes["ibge_obitos_2022"] / grandes["ibge_nv_2022"].replace(0, np.nan) * 1000).round(2)
        casos = grandes.sort_values("diff_obitos", ascending=False).head(10)[
            ["ibge7", "nome_municipio", "uf_sigla", "obitos_infantis", "ibge_obitos_2022", "tmi_sim", "tmi_ibge"]
        ].to_dict(orient="records")

        relatorio["sim_sinasc_vs_ibge_cartorio"] = {
            "brasil_obitos_sim": tot_sim,
            "brasil_obitos_cartorio_ibge": tot_ibge,
            "brasil_diferenca_obitos": tot_sim - tot_ibge,
            "brasil_nascidos_sinasc": tot_sinasc,
            "brasil_nascidos_cartorio_ibge": tot_ibge_nv,
            "brasil_tmi_sim_sinasc": round(tot_sim / tot_sinasc * 1000, 2),
            "brasil_tmi_cartorio_ibge": round(tot_ibge / tot_ibge_nv * 1000, 2),
            "ufs_maior_subregistro_cartorario": por_uf[:10],
            "municipios_100k_maior_divergencia": casos,
        }

    # 2. Comparação SINASC primário vs. IEPS Data (Pré-Natal 7+ consultas em 2022)
    if os.path.exists(IEPS_2022_PATH):
        ieps = pd.read_csv(IEPS_2022_PATH, encoding="latin1")
        ibge6_col = [c for c in ieps.columns if "IBGE" in c][0]
        pre_col = [c for c in ieps.columns if "Natal" in c][0]
        ieps["ibge6"] = ieps[ibge6_col].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
        ieps_sub = ieps[["ibge6", pre_col]].rename(columns={pre_col: "pre7_ieps"})

        comp = df.merge(ieps_sub, on="ibge6", how="inner")
        comp["pre7_sinasc_validos"] = np.where(comp["cons_validas"] > 0, comp["cons_7mais"] / comp["cons_validas"] * 100, np.nan)
        comp["pre7_sinasc_total_nv"] = np.where(comp["nascidos_vivos"] > 0, comp["cons_7mais"] / comp["nascidos_vivos"] * 100, np.nan)

        diff_val = (comp["pre7_sinasc_validos"] - comp["pre7_ieps"]).dropna()
        diff_tot = (comp["pre7_sinasc_total_nv"] - comp["pre7_ieps"]).dropna()

        relatorio["sinasc_primario_vs_ieps_prenatal_2022"] = {
            "n_municipios_comparados": int(len(diff_tot)),
            "correlacao_pearson_com_denom_total_nv": round(float(comp[["pre7_sinasc_total_nv", "pre7_ieps"]].corr().iloc[0, 1]), 5),
            "correlacao_pearson_com_denom_validos": round(float(comp[["pre7_sinasc_validos", "pre7_ieps"]].corr().iloc[0, 1]), 5),
            "erro_absoluto_medio_pp_denom_total_nv": round(float(diff_tot.abs().mean()), 3),
            "erro_absoluto_medio_pp_denom_validos": round(float(diff_val.abs().mean()), 3),
            "nota": "O SINASC primário permite distinguir explicitamente consultas ignoradas (código 9) no denominador.",
        }

    os.makedirs(os.path.dirname(OUT_REPORT), exist_ok=True)
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, indent=2, ensure_ascii=False)

    print(f"[cross_check_sources] Relatório salvo em {OUT_REPORT}")
    return relatorio


if __name__ == "__main__":
    r = executar_auditoria()
    print(json.dumps(r, indent=2, ensure_ascii=False))
