#!/usr/bin/env python3
"""
pipeline/extract/cnes_infra_ftp.py

Extrai do CNES/DATASUS (competência dez/2023) a infraestrutura assistencial por município:
- EQ: equipamentos em uso (Raio-X, US, ECG, mamógrafo, tomógrafo, RM, hemodinâmica...)
- LT: leitos (UTI adulto/ped/neo, cirúrgicos) existentes/SUS
- ST: estabelecimentos (tipo de unidade, urgência/emergência, centro cirúrgico, atendimento SUS)
- SR: serviços especializados (ambulância/remoção 161 etc.)

Saída: data/raw/cnes_infra/cnes_infra_2312.parquet (tabelas compactas) + manifest com SHA-256.
"""
import ftplib
import hashlib
import json
import os
import tempfile
from datetime import date

import numpy as np
import pandas as pd
from pyreaddbc import dbc2dbf

FTP_HOST = "ftp.datasus.gov.br"
BASE = "/dissemin/publicos/CNES/200508_/Dados"
COMPETENCIA = "2312"
OUT_DIR = os.path.join("data", "raw", "cnes_infra")
UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
       "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]

COLS = {
    "EQ": ["CNES", "CODUFMUN", "TIPEQUIP", "CODEQUIP", "QT_EXIST", "QT_USO", "IND_SUS"],
    "LT": ["CNES", "CODUFMUN", "TP_LEITO", "CODLEITO", "QT_EXIST", "QT_SUS"],
    "ST": ["CNES", "CODUFMUN", "TP_UNID", "VINC_SUS", "URGEMERG", "CENTRCIR", "ATENDAMB", "ATENDHOS", "NIV_HIER"],
    "SR": ["CNES", "CODUFMUN", "SERV_ESP", "CLASS_SR", "AMB_SUS", "HOSP_SUS"],
}


def ler_dbf(caminho, colunas):
    with open(caminho, "rb") as f:
        dados = f.read()
    n_reg = int.from_bytes(dados[4:8], "little")
    tam_cab = int.from_bytes(dados[8:10], "little")
    campos, pos = [], 32
    while dados[pos] != 0x0D:
        nome = dados[pos:pos + 11].split(b"\x00")[0].decode("latin1")
        campos.append((nome, f"S{dados[pos + 16]}"))
        pos += 32
    dt = np.dtype([("_del", "S1")] + campos)
    arr = np.frombuffer(dados, dtype=dt, count=n_reg, offset=tam_cab)
    return pd.DataFrame({
        c: (np.char.strip(np.char.decode(arr[c], "latin1")) if c in arr.dtype.names else np.full(n_reg, "", dtype="U1"))
        for c in colunas
    })


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ftp = ftplib.FTP(FTP_HOST, timeout=60)
    ftp.login()
    tmp = tempfile.mkdtemp()
    acum = {k: [] for k in COLS}
    hashes = {}
    for tab, cols in COLS.items():
        ftp.cwd(f"{BASE}/{tab}")
        for uf in UFS:
            fname = f"{tab}{uf}{COMPETENCIA}.dbc"
            dbc, dbf = os.path.join(tmp, fname), os.path.join(tmp, fname.replace(".dbc", ".dbf"))
            with open(dbc, "wb") as f:
                ftp.retrbinary(f"RETR {fname}", f.write)
            hashes[fname] = hashlib.sha256(open(dbc, "rb").read()).hexdigest()
            dbc2dbf(dbc, dbf)
            acum[tab].append(ler_dbf(dbf, cols))
            os.remove(dbc)
            os.remove(dbf)
        print(f"[cnes_infra] {tab} ok")
    ftp.quit()
    for tab, frames in acum.items():
        pd.concat(frames, ignore_index=True).to_parquet(os.path.join(OUT_DIR, f"{tab.lower()}_{COMPETENCIA}.parquet"), index=False)
    with open(os.path.join(OUT_DIR, "manifest_cnes_infra.json"), "w", encoding="utf-8") as f:
        json.dump({"competencia": COMPETENCIA, "data_coleta": date.today().isoformat(),
                   "origem": f"ftp://{FTP_HOST}{BASE}", "sha256": hashes}, f, indent=2)
    print("[cnes_infra] concluído")


if __name__ == "__main__":
    main()
