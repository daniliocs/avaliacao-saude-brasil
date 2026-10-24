#!/usr/bin/env python3
"""
pipeline/extract/ieps_series.py

Baixa a SÉRIE ANUAL (municípios) de indicadores do IEPS Data (https://iepsdata.org.br), que
consolida bases do Ministério da Saúde. O IEPS é um INTERMEDIÁRIO: cada indicador abaixo declara a
fonte primária de origem, e o registro em sources/registry.yaml informa essa cadeia de proveniência.

Indicadores (nomes da API -> uso):
  cob_esf          D3.3  Cobertura de Estratégia Saúde da Família (%)          [e-Gestor AB / SAPS]
  cob_vac_polio    D2.3  Cobertura vacinal contra poliomielite (%)             [SI-PNI]
  tx_med           D3.2  Médicos por 1.000 hab.                                [CNES]
  tx_leito_sus     D3.1  Leitos SUS por 100.000 hab.                           [CNES]
  tx_leito_nsus    PRIV  Leitos não-SUS por 100.000 hab. (fora da nota)        [CNES]

(D2.2 pré-natal 7+ consultas NÃO vem mais do IEPS: é calculado direto do SINASC — ver d1_sim.py.)

Saída: data/raw/ieps/ieps_{AAAA}.csv  e  data/raw/ieps/manifest_ieps.json (SHA-256 + data de coleta).
"""

import hashlib
import json
import os
import sys
import urllib.request
from datetime import date

INDICADORES = [
    "cob_esf",
    "cob_vac_polio",
    "cob_vac_penta",
    "cob_vac_tvd1",
    "tx_hosp_csap",
    "tx_mort_evit",
    "tx_med",
    "tx_med_ch",
    "tx_enf",
    "tx_enf_ch",
    "tx_leito_sus",
    "tx_leito_nsus",
    "desp_tot_saude_pc_mun_def",
    "pct_desp_recp_saude_mun",
    "cob_priv",
]
RAW_DIR = os.path.join("data", "raw", "ieps")
MANIFEST = os.path.join(RAW_DIR, "manifest_ieps.json")


def url_ano(ano: int) -> str:
    return (
        "https://iepsdata.org.br/wp-json/caleidosapi/get_csv"
        f"?ano={ano}&tipo=municipio&indicador={','.join(INDICADORES)}"
    )


def baixar(ano: int, forcar: bool = False) -> dict:
    destino = os.path.join(RAW_DIR, f"ieps_{ano}.csv")
    url = url_ano(ano)
    precisa_baixar = forcar or not os.path.exists(destino) or os.path.getsize(destino) < 100_000
    if not precisa_baixar:
        with open(destino, "rb") as f:
            head = f.readline().decode("latin1", errors="ignore")
        if "Pentavalente" not in head or "CSAP" not in head:
            precisa_baixar = True
    if not precisa_baixar:
        print(f"[ieps_series] {ano}: cache existente completo ({destino}).")
        with open(destino, "rb") as f:
            blob = f.read()
    else:
        print(f"[ieps_series] {ano}: baixando 15 indicadores...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            blob = resp.read()
        os.makedirs(RAW_DIR, exist_ok=True)
        with open(destino, "wb") as f:
            f.write(blob)
    return {
        "arquivo": destino.replace("\\", "/"),
        "url": url_ano(ano),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "bytes": len(blob),
        "data_coleta": date.today().isoformat(),
    }


def main(anos):
    manifesto = {}
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            manifesto = json.load(f)
    for a in anos:
        manifesto[str(a)] = baixar(a)
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifesto, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or [2019, 2020, 2021, 2022, 2023])
