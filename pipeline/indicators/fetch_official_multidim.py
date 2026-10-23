#!/usr/bin/env python3
"""
pipeline/indicators/fetch_official_multidim.py

Ingere indicadores consolidados das fontes oficiais do Ministério da Saúde
(SINASC, CNES, SI-PNI, e-Gestor/SAPS) via repositório auditado do IEPS Data para o ano de 2022,
cobrindo todos os 5.570 municípios do Brasil:

- D2.2: Proporção de Pré-Natal Adequado (7+ consultas) [SINASC]
- D2.3: Cobertura Vacinal de Poliomielite [SI-PNI / DATASUS]
- D3.1: Leitos SUS por 100.000 habitantes [CNES / DATASUS]
- D3.2: Médicos por 1.000 habitantes [CNES / DATASUS]
- D3.3: Cobertura de Estratégia de Saúde da Família (eSF) [e-Gestor / SAPS]
- Camada Privada: Leitos Não-SUS por 100.000 habitantes [CNES]
"""

import os
import io
import urllib.request
import pandas as pd

OUTPUT_RAW = os.path.join("data", "raw", "ieps_indicadores_2022.csv")

INDICATORS = [
    "cob_esf",
    "pct_prenatal_7m",
    "cob_vac_polio",
    "tx_med",
    "tx_leito_sus",
    "tx_leito_nsus"
]

API_URL = f"https://iepsdata.org.br/wp-json/caleidosapi/get_csv?ano=2022&tipo=municipio&indicador={','.join(INDICATORS)}"


def fetch_multidim_data():
    os.makedirs(os.path.dirname(OUTPUT_RAW), exist_ok=True)
    if os.path.exists(OUTPUT_RAW) and os.path.getsize(OUTPUT_RAW) > 100000:
        print(f"[fetch_official_multidim] Dados já existem em cache local: {OUTPUT_RAW}")
        return pd.read_csv(OUTPUT_RAW, encoding="latin1")

    print(f"[fetch_official_multidim] Baixando dados oficiais consolidados 2022 de: {API_URL}")
    req = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()

    with open(OUTPUT_RAW, "wb") as f:
        f.write(data)

    df = pd.read_csv(io.BytesIO(data), encoding="latin1")
    print(f"[fetch_official_multidim] Sucesso: {len(df)} registros baixados e salvos em {OUTPUT_RAW}.")
    return df


if __name__ == "__main__":
    fetch_multidim_data()
