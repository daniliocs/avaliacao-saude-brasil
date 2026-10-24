#!/usr/bin/env python3
"""
pipeline/indicators/sim_sinasc.py

Calcula, a partir de MICRODADOS PRIMÁRIOS do DATASUS (SIM e SINASC por residência):
  D1.1  Taxa de mortalidade infantil (óbitos <1 ano por 1.000 nascidos vivos) + mortalidade neonatal (0–27 dias)
  D1.2  Razão de mortalidade materna (óbitos maternos por 100.000 nascidos vivos)
  D1.3  Mortalidade prematura (30–69 anos) por DCNT (I00–I99, C00–C97, E10–E14, J30–J98 exceto J36 por 100.000 hab.)
  D2.2  % de nascidos vivos com 7+ consultas de pré-natal (entre os com informação válida)

Saídas:
  data/processed/serie_anual_sim_sinasc.parquet  (ibge6, ano, contagens brutas) — a "série"
  data/processed/indicadores_sim_sinasc.parquet  (indicadores por janela, IC e suavização)
  data/processed/qualidade_sim_sinasc.json       (cobertura de códigos de município, anos usados)
"""

import json
import os
import sys

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from pipeline.indicators.estatistica import ic_poisson, ic_wilson, suavizar_eb  # noqa: E402

RAW = os.path.join("data", "raw", "datasus")
DIM_PATH = os.path.join("data", "processed", "dim_municipio.parquet")
OUT_SERIE = os.path.join("data", "processed", "serie_anual_sim_sinasc.parquet")
OUT_IND = os.path.join("data", "processed", "indicadores_sim_sinasc.parquet")
OUT_QUAL = os.path.join("data", "processed", "qualidade_sim_sinasc.json")
JANELAS = os.path.join("config", "janelas.yaml")


def eh_obito_infantil(df: pd.DataFrame) -> pd.Series:
    idade = df["IDADE"].astype(str).str.strip()
    return (df["TIPOBITO"].astype(str).str.strip() == "2") & idade.str[:1].isin(["0", "1", "2", "3"]) & (idade != "000")


def eh_obito_neonatal(df: pd.DataFrame) -> pd.Series:
    idade = df["IDADE"].astype(str).str.strip()
    unid = idade.str[:1]
    val = pd.to_numeric(idade.str[1:], errors="coerce")
    nao_fetal = (df["TIPOBITO"].astype(str).str.strip() == "2") & (idade != "000")
    return nao_fetal & (unid.isin(["0", "1"]) | ((unid == "2") & (val <= 27)))


def eh_obito_materno(df: pd.DataFrame) -> pd.Series:
    cid = df["CAUSABAS"].astype(str).str.strip().str.upper()
    capitulo_o = cid.str.match(r"^O\d{2}")
    tardia = cid.str.startswith("O96") | cid.str.startswith("O97")
    mulher = df["SEXO"].astype(str).str.strip() == "2"
    return (df["TIPOBITO"].astype(str).str.strip() == "2") & mulher & capitulo_o & ~tardia


def eh_obito_dcnt_prematuro(df: pd.DataFrame) -> pd.Series:
    """
    Óbitos prematuros (30 a 69 anos) pelos 4 grandes grupos de DCNT (OMS / ODS 3.4 / Plano DANT MS):
      - Aparelho circulatório: I00–I99
      - Neoplasias malignas: C00–C97
      - Diabetes mellitus: E10–E14
      - Doenças respiratórias crônicas: J30–J98 (exceto J36 - abscesso periamigdaliano)
    """
    idade = df["IDADE"].astype(str).str.strip()
    unid = idade.str[:1]
    anos = pd.to_numeric(idade.str[1:], errors="coerce")
    faixa_30_69 = (df["TIPOBITO"].astype(str).str.strip() == "2") & (unid == "4") & (anos >= 30) & (anos <= 69)

    cid3 = df["CAUSABAS"].astype(str).str.strip().str.upper().str[:3]
    circ = cid3.str.match(r"^I\d{2}$")
    neop = cid3.str.match(r"^C([0-8]\d|9[0-7])$")
    diab = cid3.str.match(r"^E1[0-4]$")
    resp = cid3.str.match(r"^J([3-8]\d|9[0-8])$") & (cid3 != "J36")
    return faixa_30_69 & (circ | neop | diab | resp)


def contar_ano(ano: int, validos_ibge6: set) -> tuple[pd.DataFrame, dict]:
    sim = pd.read_parquet(os.path.join(RAW, f"sim_{ano}.parquet"))
    sin = pd.read_parquet(os.path.join(RAW, f"sinasc_{ano}.parquet"))

    sim["ibge6"] = sim["CODMUNRES"].astype(str).str.strip().str[:6]
    sin["ibge6"] = sin["CODMUNRES"].astype(str).str.strip().str[:6]

    mal_def = sim["CAUSABAS"].astype(str).str.upper().str.match(r"^R\d{2}")
    inf = eh_obito_infantil(sim)
    neo = eh_obito_neonatal(sim)
    mat = eh_obito_materno(sim)
    dcnt = eh_obito_dcnt_prematuro(sim)

    obitos = pd.DataFrame({
        "ibge6": sim["ibge6"],
        "obitos_total": 1,
        "obitos_infantis": inf.astype(int),
        "obitos_neonatais": neo.astype(int),
        "obitos_maternos": mat.astype(int),
        "obitos_dcnt_30_69": dcnt.astype(int),
        "obitos_mal_definidos": mal_def.astype(int),
    }).groupby("ibge6").sum()

    cons = sin["CONSULTAS"].astype(str).str.strip()
    nasc = pd.DataFrame({
        "ibge6": sin["ibge6"],
        "nascidos_vivos": 1,
        "cons_validas": cons.isin(["1", "2", "3", "4"]).astype(int),
        "cons_7mais": (cons == "4").astype(int),
    }).groupby("ibge6").sum()

    serie = obitos.join(nasc, how="outer").fillna(0).astype(int).reset_index()
    serie["ano"] = ano

    qual = {
        "ano": ano,
        "obitos_total": int(len(sim)),
        "nascidos_vivos": int(len(sin)),
        "obitos_sem_municipio_valido": int((~sim["ibge6"].isin(validos_ibge6)).sum()),
        "nascidos_sem_municipio_valido": int((~sin["ibge6"].isin(validos_ibge6)).sum()),
        "obitos_infantis": int(inf.sum()),
        "obitos_neonatais": int(neo.sum()),
        "obitos_maternos": int(mat.sum()),
        "obitos_dcnt_30_69": int(dcnt.sum()),
        "pct_consultas_ignoradas": round(float(100 * (1 - cons.isin(["1", "2", "3", "4"]).mean())), 2),
    }
    return serie, qual


def construir() -> pd.DataFrame:
    dim = pd.read_parquet(DIM_PATH)
    validos = set(dim["ibge6"])
    with open(JANELAS, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)["janelas"]

    anos_necessarios = sorted({a for k in ("D1.1", "D1.2", "D1.3", "D2.2") for a in cfg[k]["anos"]})
    faltando = [a for a in anos_necessarios
                if not (os.path.exists(os.path.join(RAW, f"sim_{a}.parquet"))
                        and os.path.exists(os.path.join(RAW, f"sinasc_{a}.parquet")))]
    if faltando:
        print(f"[sim_sinasc:ERRO] Anos ausentes em data/raw/datasus: {faltando}. Execute extract/datasus_ftp.py.")
        sys.exit(1)

    if os.path.exists(OUT_SERIE) and os.path.exists(OUT_QUAL):
        serie_exist = pd.read_parquet(OUT_SERIE)
        if {"obitos_dcnt_30_69", "obitos_neonatais"}.issubset(serie_exist.columns) and set(anos_necessarios).issubset(set(serie_exist["ano"].unique())):
            print(f"[sim_sinasc] Reutilizando série anual já consolidada ({OUT_SERIE})...")
            serie = serie_exist[serie_exist["ibge6"].isin(validos)].copy()
            with open(OUT_QUAL, encoding="utf-8") as fq:
                quals = json.load(fq).get("por_ano", [])
        else:
            serie = None
    else:
        serie = None

    if serie is None:
        series, quals = [], []
        for ano in anos_necessarios:
            print(f"[sim_sinasc] Contando {ano}...")
            s, q = contar_ano(ano, validos)
            series.append(s)
            quals.append(q)
        serie = pd.concat(series, ignore_index=True)
        serie = serie[serie["ibge6"].isin(validos)]
        serie.to_parquet(OUT_SERIE, index=False)

    base = dim[["ibge7", "ibge6", "uf_sigla", "populacao_censo_2022"]].copy()

    def somar(anos, cols):
        sub = serie[serie["ano"].isin(anos)].groupby("ibge6")[cols].sum()
        return base[["ibge6"]].merge(sub, left_on="ibge6", right_index=True, how="left").fillna(0)[cols]

    # --- D1.1 (Mortalidade Infantil + Neonatal) ---
    j = cfg["D1.1"]["anos"]
    s = somar(j, ["obitos_infantis", "obitos_neonatais", "nascidos_vivos"])
    base["d1_1_obitos"] = s["obitos_infantis"].values.astype(int)
    base["d1_1_obitos_neonatais"] = s["obitos_neonatais"].values.astype(int)
    base["d1_1_nv"] = s["nascidos_vivos"].values.astype(int)
    with np.errstate(divide="ignore", invalid="ignore"):
        base["tmi_bruta"] = np.where(base["d1_1_nv"] > 0, base["d1_1_obitos"] / base["d1_1_nv"] * 1000, np.nan)
        base["tmn_bruta"] = np.where(base["d1_1_nv"] > 0, base["d1_1_obitos_neonatais"] / base["d1_1_nv"] * 1000, np.nan)
    lo, hi = ic_poisson(base["d1_1_obitos"], base["d1_1_nv"], fator=1000.0)
    base["tmi_ic95_min"], base["tmi_ic95_max"] = lo, hi
    base["tmi_bayes"] = suavizar_eb(base["d1_1_obitos"], base["d1_1_nv"], base["uf_sigla"], 1000.0)
    base.loc[base["d1_1_nv"] <= 0, ["tmi_bayes"]] = np.nan
    base["d1_1_janela"] = f"{min(j)}–{max(j)}"

    # --- D1.2 (Razão de Mortalidade Materna) ---
    j = cfg["D1.2"]["anos"]
    s = somar(j, ["obitos_maternos", "nascidos_vivos"])
    base["d1_2_obitos"] = s["obitos_maternos"].values.astype(int)
    base["d1_2_nv"] = s["nascidos_vivos"].values.astype(int)
    with np.errstate(divide="ignore", invalid="ignore"):
        base["rmm_bruta"] = np.where(base["d1_2_nv"] > 0, base["d1_2_obitos"] / base["d1_2_nv"] * 1e5, np.nan)
    lo, hi = ic_poisson(base["d1_2_obitos"], base["d1_2_nv"], fator=1e5)
    base["rmm_ic95_min"], base["rmm_ic95_max"] = lo, hi
    base["rmm_bayes"] = suavizar_eb(base["d1_2_obitos"], base["d1_2_nv"], base["uf_sigla"], 1e5)
    base.loc[base["d1_2_nv"] <= 0, ["rmm_bayes"]] = np.nan
    base["d1_2_janela"] = f"{min(j)}–{max(j)}"

    # --- D1.3 (Mortalidade Prematura 30–69 anos por DCNT) ---
    j = cfg["D1.3"]["anos"]
    s = somar(j, ["obitos_dcnt_30_69"])
    base["d1_3_obitos"] = s["obitos_dcnt_30_69"].values.astype(int)
    base["d1_3_pop_anos"] = (base["populacao_censo_2022"].fillna(0).astype(np.int64) * len(j))
    with np.errstate(divide="ignore", invalid="ignore"):
        base["dcnt_bruta"] = np.where(base["d1_3_pop_anos"] > 0, base["d1_3_obitos"] / base["d1_3_pop_anos"] * 1e5, np.nan)
    lo, hi = ic_poisson(base["d1_3_obitos"], base["d1_3_pop_anos"], fator=1e5)
    base["dcnt_ic95_min"], base["dcnt_ic95_max"] = lo, hi
    base["dcnt_bayes"] = suavizar_eb(base["d1_3_obitos"], base["d1_3_pop_anos"], base["uf_sigla"], 1e5)
    base.loc[base["d1_3_pop_anos"] <= 0, ["dcnt_bayes"]] = np.nan
    base["d1_3_janela"] = f"{min(j)}–{max(j)}"

    # --- D2.2 (Pré-natal 7+ consultas) ---
    j = cfg["D2.2"]["anos"]
    s = somar(j, ["cons_7mais", "cons_validas", "nascidos_vivos"])
    base["d2_2_validas"] = s["cons_validas"].values.astype(int)
    base["d2_2_7mais"] = s["cons_7mais"].values.astype(int)
    base["d2_2_nv"] = s["nascidos_vivos"].values.astype(int)
    with np.errstate(divide="ignore", invalid="ignore"):
        base["pre7_pct"] = np.where(base["d2_2_validas"] > 0, base["d2_2_7mais"] / base["d2_2_validas"] * 100, np.nan)
        base["pre7_pct_ignorado"] = np.where(base["d2_2_nv"] > 0, (1 - base["d2_2_validas"] / base["d2_2_nv"]) * 100, np.nan)
    lo, hi = ic_wilson(base["d2_2_7mais"], base["d2_2_validas"])
    base["pre7_ic95_min"], base["pre7_ic95_max"] = lo, hi
    base["d2_2_janela"] = f"{min(j)}–{max(j)}"

    base = base.drop(columns=["populacao_censo_2022"])
    base.to_parquet(OUT_IND, index=False)

    with open(OUT_QUAL, "w", encoding="utf-8") as f:
        json.dump({"por_ano": quals, "janelas": {k: cfg[k]["anos"] for k in ("D1.1", "D1.2", "D1.3", "D2.2")}}, f, indent=2, ensure_ascii=False)

    print(f"[sim_sinasc] OK: {len(base)} municípios | TMI mediana {base['tmi_bruta'].median():.2f}‰ | "
          f"Brasil TMI janela {base['d1_1_obitos'].sum() / base['d1_1_nv'].sum() * 1000:.2f}‰ | "
          f"Brasil DCNT 30-69 {base['dcnt_bruta'].median():.1f}/100k | "
          f"Brasil RMM {base['d1_2_obitos'].sum() / base['d1_2_nv'].sum() * 1e5:.1f}/100 mil NV | "
          f"pré-natal 7+ Brasil {base['d2_2_7mais'].sum() / base['d2_2_validas'].sum() * 100:.1f}%")
    return base


if __name__ == "__main__":
    construir()
