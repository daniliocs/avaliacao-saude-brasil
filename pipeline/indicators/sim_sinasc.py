#!/usr/bin/env python3
"""
pipeline/indicators/sim_sinasc.py

Calcula, a partir de MICRODADOS PRIMÁRIOS do DATASUS (SIM e SINASC por residência):
  D1.1  Taxa de mortalidade infantil (óbitos <1 ano por 1.000 nascidos vivos)
  D1.2  Razão de mortalidade materna (óbitos maternos por 100.000 nascidos vivos)
  D2.2  % de nascidos vivos com 7+ consultas de pré-natal (entre os com informação válida)

Definições (documentadas em docs/indicadores/):
  - Óbito infantil: SIM, TIPOBITO=2 (não fetal), IDADE com unidade 0/1/2/3 (min/h/dias/meses), IDADE!='000'.
  - Óbito materno: SIM, SEXO=2, CAUSABAS CID-10 O00–O99 exceto O96 e O97 (mortes tardias).
    [LIMITAÇÃO — PEND-036] A definição oficial do MS inclui causas adicionais quando há gravidez/puerpério
    declarados; aqui usa-se o núcleo do capítulo XV, de forma conservadora.
  - Município: código de RESIDÊNCIA (ibge6), nunca de ocorrência.
  - Pré-natal: SINASC CONSULTAS 1=nenhuma, 2=1–3, 3=4–6, 4=7+, 9=ignorado. Denominador = códigos 1–4.

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


def eh_obito_materno(df: pd.DataFrame) -> pd.Series:
    cid = df["CAUSABAS"].astype(str).str.strip().str.upper()
    capitulo_o = cid.str.match(r"^O\d{2}")
    tardia = cid.str.startswith("O96") | cid.str.startswith("O97")
    mulher = df["SEXO"].astype(str).str.strip() == "2"
    return (df["TIPOBITO"].astype(str).str.strip() == "2") & mulher & capitulo_o & ~tardia


def contar_ano(ano: int, validos_ibge6: set) -> tuple[pd.DataFrame, dict]:
    sim = pd.read_parquet(os.path.join(RAW, f"sim_{ano}.parquet"))
    sin = pd.read_parquet(os.path.join(RAW, f"sinasc_{ano}.parquet"))

    sim["ibge6"] = sim["CODMUNRES"].astype(str).str.strip().str[:6]
    sin["ibge6"] = sin["CODMUNRES"].astype(str).str.strip().str[:6]

    mal_def = sim["CAUSABAS"].astype(str).str.upper().str.match(r"^R\d{2}")
    inf = eh_obito_infantil(sim)
    mat = eh_obito_materno(sim)

    obitos = pd.DataFrame({
        "ibge6": sim["ibge6"],
        "obitos_total": 1,
        "obitos_infantis": inf.astype(int),
        "obitos_maternos": mat.astype(int),
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
        "obitos_maternos": int(mat.sum()),
        "pct_consultas_ignoradas": round(float(100 * (1 - cons.isin(["1", "2", "3", "4"]).mean())), 2),
    }
    return serie, qual


def construir() -> pd.DataFrame:
    dim = pd.read_parquet(DIM_PATH)
    validos = set(dim["ibge6"])
    with open(JANELAS, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)["janelas"]

    anos_necessarios = sorted({a for k in ("D1.1", "D1.2", "D2.2") for a in cfg[k]["anos"]})
    faltando = [a for a in anos_necessarios
                if not (os.path.exists(os.path.join(RAW, f"sim_{a}.parquet"))
                        and os.path.exists(os.path.join(RAW, f"sinasc_{a}.parquet")))]
    if faltando:
        print(f"[sim_sinasc:ERRO] Anos ausentes em data/raw/datasus: {faltando}. Execute extract/datasus_ftp.py.")
        sys.exit(1)

    series, quals = [], []
    for ano in anos_necessarios:
        print(f"[sim_sinasc] Contando {ano}...")
        s, q = contar_ano(ano, validos)
        series.append(s)
        quals.append(q)
    serie = pd.concat(series, ignore_index=True)
    serie = serie[serie["ibge6"].isin(validos)]
    serie.to_parquet(OUT_SERIE, index=False)

    base = dim[["ibge7", "ibge6", "uf_sigla"]].copy()

    def somar(anos, cols):
        sub = serie[serie["ano"].isin(anos)].groupby("ibge6")[cols].sum()
        return base[["ibge6"]].merge(sub, left_on="ibge6", right_index=True, how="left").fillna(0)[cols]

    # --- D1.1 ---
    j = cfg["D1.1"]["anos"]
    s = somar(j, ["obitos_infantis", "nascidos_vivos"])
    base["d1_1_obitos"] = s["obitos_infantis"].values.astype(int)
    base["d1_1_nv"] = s["nascidos_vivos"].values.astype(int)
    with np.errstate(divide="ignore", invalid="ignore"):
        base["tmi_bruta"] = np.where(base["d1_1_nv"] > 0, base["d1_1_obitos"] / base["d1_1_nv"] * 1000, np.nan)
    lo, hi = ic_poisson(base["d1_1_obitos"], base["d1_1_nv"], fator=1000.0)
    base["tmi_ic95_min"], base["tmi_ic95_max"] = lo, hi
    base["tmi_bayes"] = suavizar_eb(base["d1_1_obitos"], base["d1_1_nv"], base["uf_sigla"], 1000.0)
    base.loc[base["d1_1_nv"] <= 0, ["tmi_bayes"]] = np.nan
    base["d1_1_janela"] = f"{min(j)}–{max(j)}"

    # --- D1.2 ---
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

    # --- D2.2 ---
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

    base.to_parquet(OUT_IND, index=False)

    with open(OUT_QUAL, "w", encoding="utf-8") as f:
        json.dump({"por_ano": quals, "janelas": {k: cfg[k]["anos"] for k in ("D1.1", "D1.2", "D2.2")}}, f, indent=2, ensure_ascii=False)

    print(f"[sim_sinasc] OK: {len(base)} municípios | TMI mediana {base['tmi_bruta'].median():.2f}‰ | "
          f"Brasil TMI janela {base['d1_1_obitos'].sum() / base['d1_1_nv'].sum() * 1000:.2f}‰ | "
          f"Brasil RMM {base['d1_2_obitos'].sum() / base['d1_2_nv'].sum() * 1e5:.1f}/100 mil NV | "
          f"pré-natal 7+ Brasil {base['d2_2_7mais'].sum() / base['d2_2_validas'].sum() * 100:.1f}%")
    return base


if __name__ == "__main__":
    construir()
