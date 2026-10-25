#!/usr/bin/env python3
"""
pipeline/extract/oncologia_ftp.py

Extrai microdados PRIMÁRIOS do Painel-Oncologia do DATASUS (ftp.datasus.gov.br):
- Base Nacional do Painel Oncologia (Lei dos 60 Dias - Lei nº 12.732/2012):
  /dissemin/publicos/painel_oncologia/Dados/POBR{AAAA}.dbc (2021, 2022, 2023)

Saída:
  data/raw/oncologia/painel_oncologia_2021_2023.parquet
  data/raw/oncologia/cnes_oncologia_2023.parquet
  data/raw/oncologia/manifest_oncologia.json
"""

import ftplib
import hashlib
import json
import os
import shutil
import tempfile
from datetime import date
import numpy as np
import pandas as pd
from pyreaddbc import dbc2dbf

FTP_HOST = "ftp.datasus.gov.br"
FTP_DIR_PAINEL = "/dissemin/publicos/painel_oncologia/Dados"
FTP_DIR_CNES_HB = "/dissemin/publicos/CNES/200508_/Dados/HB"

RAW_ONCO_DIR = os.path.join("data", "raw", "oncologia")
MANIFEST_PATH = os.path.join(RAW_ONCO_DIR, "manifest_oncologia.json")

UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"
]

COLUNAS_POBR = [
    "ANO_DIAGN", "MUN_RESID", "MUN_TRATAM", "UF_RESID", "UF_TRATAM",
    "CNES_TRAT", "TRATAMENTO", "DIAGNOSTIC", "ESTADIAM", "TEMPO_TRAT",
    "DT_DIAG", "DT_TRAT"
]


def sha256_arquivo(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def ler_dbf_pobr(caminho_dbf: str, colunas: list[str]) -> pd.DataFrame:
    with open(caminho_dbf, "rb") as f:
        dados = f.read()
    n_reg = int.from_bytes(dados[4:8], "little")
    tam_cab = int.from_bytes(dados[8:10], "little")
    tam_reg = int.from_bytes(dados[10:12], "little")

    campos = []
    pos = 32
    while dados[pos] != 0x0D:
        nome = dados[pos:pos + 11].split(b"\x00")[0].decode("latin1")
        tam = dados[pos + 16]
        campos.append((nome, f"S{tam}"))
        pos += 32

    dt = np.dtype([("_del", "S1")] + campos)
    assert dt.itemsize == tam_reg, "Tamanho do registro inconsistente com o cabeçalho DBF"
    arr = np.frombuffer(dados, dtype=dt, count=n_reg, offset=tam_cab)

    res = {}
    for col in colunas:
        if col in arr.dtype.names:
            res[col] = np.char.strip(np.char.decode(arr[col], "latin1"))
        else:
            res[col] = np.full(n_reg, "", dtype="U1")
    return pd.DataFrame(res)


def extrair_painel_oncologia_ano(ano: int, ftp: ftplib.FTP, tmp_dir: str) -> tuple[pd.DataFrame, dict]:
    fname = f"POBR{ano}.dbc"
    dbc_path = os.path.join(tmp_dir, fname)
    dbf_path = os.path.join(tmp_dir, f"POBR{ano}.dbf")

    print(f"[oncologia_ftp] Baixando {fname} do FTP DATASUS...")
    ftp.cwd(FTP_DIR_PAINEL)
    with open(dbc_path, "wb") as f:
        ftp.retrbinary(f"RETR {fname}", f.write)

    sha = sha256_arquivo(dbc_path)
    tam_bytes = os.path.getsize(dbc_path)

    print(f"[oncologia_ftp] Descomprimindo {fname} ({tam_bytes / 1e6:.1f} MB)...")
    dbc2dbf(dbc_path, dbf_path)

    df = ler_dbf_pobr(dbf_path, COLUNAS_POBR)
    df["ANO_BASE"] = ano

    os.remove(dbc_path)
    os.remove(dbf_path)

    meta = {
        "arquivo": fname,
        "sha256": sha,
        "bytes": tam_bytes,
        "total_registros": len(df),
        "data_coleta": date.today().isoformat(),
        "origem": f"ftp://{FTP_HOST}{FTP_DIR_PAINEL}/{fname}"
    }
    print(f"[oncologia_ftp] {fname} processado: {len(df):,} registros.")
    return df, meta


def extrair_cnes_habilitacoes_onco(ftp: ftplib.FTP, tmp_dir: str) -> tuple[pd.DataFrame, dict]:
    print("[oncologia_ftp] Extraindo estabelecimentos habilitados em Oncologia (CACON/UNACON) no CNES...")
    ftp.cwd(FTP_DIR_CNES_HB)
    cacons_unacons = []
    total_bytes = 0

    for uf in UFS:
        fname = f"HB{uf}2312.dbc"
        dbc = os.path.join(tmp_dir, fname)
        dbf = os.path.join(tmp_dir, f"HB{uf}2312.dbf")
        try:
            with open(dbc, "wb") as f:
                ftp.retrbinary(f"RETR {fname}", f.write)
        except Exception:
            continue

        total_bytes += os.path.getsize(dbc)
        dbc2dbf(dbc, dbf)

        with open(dbf, "rb") as f:
            d = f.read()
        tam_cab = int.from_bytes(d[8:10], "little")
        n_reg = int.from_bytes(d[4:8], "little")
        campos = []
        pos = 32
        while d[pos] != 0x0D:
            campos.append((d[pos:pos+11].split(b"\x00")[0].decode("latin1"), f"S{d[pos+16]}"))
            pos += 32
        dt = np.dtype([("_del", "S1")] + campos)
        arr = np.frombuffer(d, dtype=dt, count=n_reg, offset=tam_cab)

        habs = np.char.strip(np.char.decode(arr["SGRUPHAB"], "latin1"))
        cnes = np.char.strip(np.char.decode(arr["CNES"], "latin1"))
        mun = np.char.strip(np.char.decode(arr["CODUFMUN"], "latin1"))
        reg = np.char.strip(np.char.decode(arr["REGSAUDE"], "latin1"))

        for i, h in enumerate(habs):
            if h.startswith("17"):
                cacons_unacons.append({"uf": uf, "cnes": cnes[i], "ibge6": mun[i], "regsaude": reg[i], "hab": h})

        os.remove(dbc)
        os.remove(dbf)

    df = pd.DataFrame(cacons_unacons)
    meta = {
        "competencia": "202312",
        "total_registros_hab": len(df),
        "hospitais_unicos": int(df["cnes"].nunique()),
        "municipios_com_onco": int(df["ibge6"].nunique()),
        "data_coleta": date.today().isoformat(),
        "origem": f"ftp://{FTP_HOST}{FTP_DIR_CNES_HB}/HB{{UF}}2312.dbc"
    }
    print(f"[oncologia_ftp] CNES Oncologia: {meta['hospitais_unicos']} hospitais em {meta['municipios_com_onco']} municípios.")
    return df, meta


def executar():
    os.makedirs(RAW_ONCO_DIR, exist_ok=True)
    manifesto = {}
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            manifesto = json.load(f)

    tmp = tempfile.mkdtemp(prefix="dsus_onco_")
    try:
        print(f"[oncologia_ftp] Conectando ao FTP {FTP_HOST}...")
        ftp = ftplib.FTP(FTP_HOST, timeout=120)
        ftp.login()

        # 1. Painel Oncologia (Triênio 2021–2023)
        caminho_pobr_parquet = os.path.join(RAW_ONCO_DIR, "painel_oncologia_2021_2023.parquet")
        if not os.path.exists(caminho_pobr_parquet):
            frames_pobr = []
            for ano in [2021, 2022, 2023]:
                df_ano, meta_ano = extrair_painel_oncologia_ano(ano, ftp, tmp)
                frames_pobr.append(df_ano)
                manifesto[f"POBR{ano}"] = meta_ano
            df_total = pd.concat(frames_pobr, ignore_index=True)
            df_total.to_parquet(caminho_pobr_parquet, index=False)
            print(f"[oncologia_ftp] Consolidado Painel Oncologia triênio 2021–2023: {len(df_total):,} casos -> {caminho_pobr_parquet}")
        else:
            print(f"[oncologia_ftp] Cache existente: {caminho_pobr_parquet}")

        # 2. Habilitações CNES CACON/UNACON
        caminho_cnes_parquet = os.path.join(RAW_ONCO_DIR, "cnes_oncologia_2023.parquet")
        if not os.path.exists(caminho_cnes_parquet):
            df_cnes, meta_cnes = extrair_cnes_habilitacoes_onco(ftp, tmp)
            df_cnes.to_parquet(caminho_cnes_parquet, index=False)
            manifesto["cnes_oncologia_2023"] = meta_cnes
        else:
            print(f"[oncologia_ftp] Cache existente: {caminho_cnes_parquet}")

        ftp.quit()

        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifesto, f, indent=2, ensure_ascii=False)
        print(f"[oncologia_ftp] Manifesto gravado em {MANIFEST_PATH}")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    executar()
