#!/usr/bin/env python3
"""
pipeline/extract/hpv_infoms.py

Extrai e processa a cobertura vacinal de HPV (Papilomavírus Humano) para adolescentes de 9 a 14 anos,
segregada por sexo (meninas e meninos), a partir dos dados abertos oficiais do Ministério da Saúde
(Painel InfoMS / SEIDIGI / DEMAS / SI-PNI - RNDS).

Fonte:
  - Painel InfoMS: https://infoms.saude.gov.br/extensions/SEIDIGI_DEMAS_VACINACAO_HPV/index.html
  - Base: Coorte acumulada de vacinação contra o HPV (9 a 14 anos), contemplando doses aplicadas
    e população de referência (IBGE).

Regra de Negócio:
  - Os dados de HPV são estritamente INFORMATIVOS (fora da nota D2.3 do índice composto).
  - Servem para visualização detalhada no card do município no frontend.

Saídas:
  - data/raw/pni/infoms_vacinacao_hpv.xlsx (raw baixado)
  - data/raw/pni/hpv_municipios.parquet (processado por município com ibge7)
"""

import json
import os
import re
import sys
import numpy as np
import pandas as pd

RAW_DIR = os.path.join("data", "raw", "pni")
EXCEL_PATH = os.path.join(RAW_DIR, "infoms_vacinacao_hpv.xlsx")
PARQUET_OUT = os.path.join(RAW_DIR, "hpv_municipios.parquet")
IBGE_PATH = os.path.join("data", "raw", "ibge_municipios_raw.json")


def extrair_painel_se_necessario():
    """Se o Excel não existir, utiliza Playwright para baixar diretamente do painel do Ministério da Saúde."""
    if os.path.exists(EXCEL_PATH) and os.path.getsize(EXCEL_PATH) > 100_000:
        print(f"[HPV] Arquivo base já presente em {EXCEL_PATH} ({os.path.getsize(EXCEL_PATH):,} bytes).")
        return

    print("[HPV] Baixando dados diretamente do painel oficial InfoMS via Playwright...")
    from playwright.sync_api import sync_playwright

    os.makedirs(RAW_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        page.goto("https://infoms.saude.gov.br/extensions/SEIDIGI_DEMAS_VACINACAO_HPV/index.html", timeout=90000)
        page.wait_for_timeout(20000)

        with page.expect_download(timeout=120000) as download_info:
            page.evaluate("document.querySelector('#exportar-dados-tabela_municipio').click()")

        download = download_info.value
        download.save_as(EXCEL_PATH)
        browser.close()
    print(f"[HPV] Download salvo em {EXCEL_PATH}.")


def processar_hpv() -> pd.DataFrame:
    """Lê o Excel do InfoMS e gera o DataFrame consolidado por município (IBGE 7 dígitos)."""
    extrair_painel_se_necessario()

    df = pd.read_excel(EXCEL_PATH)
    col_mun = [c for c in df.columns if "Munic" in c][0]
    col_cob = [c for c in df.columns if "Cobertura 9 a 14" in c][0]
    col_doses = [c for c in df.columns if "Doses 9 a 14" in c][0]
    col_pop = [c for c in df.columns if "Popula" in c and "9 a 14" in c][0]

    # Converter colunas numéricas com coerção de strings/dashes ('---') para NaN
    df[col_cob] = pd.to_numeric(df[col_cob], errors="coerce")
    df[col_doses] = pd.to_numeric(df[col_doses], errors="coerce").fillna(0)
    df[col_pop] = pd.to_numeric(df[col_pop], errors="coerce").fillna(0)

    # Extrair código IBGE 6 dígitos
    df["ibge6"] = df[col_mun].astype(str).str.extract(r"^(\d{6})")

    # Mapeamento IBGE6 -> IBGE7
    with open(IBGE_PATH, "r", encoding="utf-8") as f:
        mun_raw = json.load(f)
    ibge6_to_7 = {str(m["id"])[:6]: str(m["id"]) for m in mun_raw}

    df["ibge7"] = df["ibge6"].map(ibge6_to_7)
    df = df.dropna(subset=["ibge7"]).copy()

    # Divisão por sexo
    fem = df[df["Sexo"] == "Feminino"].set_index("ibge7")
    masc = df[df["Sexo"] == "Masculino"].set_index("ibge7")

    todos_ibge7 = sorted(df["ibge7"].unique())
    res = pd.DataFrame(index=todos_ibge7)
    res.index.name = "ibge7"

    # Coberturas e contagens
    res["hpv_cob_meninas"] = (fem[col_cob] * 100).round(1)
    res["hpv_cob_meninos"] = (masc[col_cob] * 100).round(1)
    res["hpv_doses_meninas"] = fem[col_doses].fillna(0).astype(int)
    res["hpv_doses_meninos"] = masc[col_doses].fillna(0).astype(int)
    res["hpv_pop_meninas"] = fem[col_pop].fillna(0).astype(int)
    res["hpv_pop_meninos"] = masc[col_pop].fillna(0).astype(int)

    pop_total = res["hpv_pop_meninas"] + res["hpv_pop_meninos"]
    doses_total = res["hpv_doses_meninas"] + res["hpv_doses_meninos"]

    res["hpv_cob_total"] = np.where(
        pop_total > 0,
        (doses_total / pop_total * 100).round(1),
        np.nan
    )

    res.reset_index(inplace=True)
    res.to_parquet(PARQUET_OUT, index=False)
    print(f"[HPV] Parquet gerado com sucesso: {PARQUET_OUT} ({len(res)} municípios)")
    return res


if __name__ == "__main__":
    df = processar_hpv()
    print(df.head())
    print("\nResumo HPV Meninas e Meninos:")
    print(df[["hpv_cob_meninas", "hpv_cob_meninos", "hpv_cob_total"]].describe())
