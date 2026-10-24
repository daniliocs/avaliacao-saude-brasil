#!/usr/bin/env python3
"""
pipeline/extract/datasus_ftp.py

Extrai microdados PRIMÁRIOS do DATASUS (FTP oficial ftp.datasus.gov.br):
  - SIM  (óbitos por UF de RESIDÊNCIA):   /dissemin/publicos/SIM/CID10/DORES/DO{UF}{AAAA}.dbc
  - SINASC (nascidos vivos por RESIDÊNCIA): /dissemin/publicos/SINASC/1996_/Dados/DNRES/DN{UF}{AAAA}.dbc

Saída (somente colunas necessárias, 1 arquivo por ano):
  data/raw/datasus/sim_{AAAA}.parquet
  data/raw/datasus/sinasc_{AAAA}.parquet
  data/raw/datasus/manifest_extracao.json  (SHA-256, tamanho e data de coleta de cada .dbc)

Observações técnicas:
  - O descompressor C do pyreaddbc falha com caminhos não-ASCII (ex.: "Códigos"); por isso a
    descompressão ocorre em diretório temporário do sistema.
  - A leitura do DBF é feita com numpy (registros de largura fixa), sem parsing campo a campo.
"""

import ftplib
import hashlib
import json
import os
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import numpy as np
import pandas as pd

FTP_HOST = "ftp.datasus.gov.br"

UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
]

FONTES = {
    "sim": {
        "dir": "/dissemin/publicos/SIM/CID10/DORES",
        "prefixo": "DO",
        "colunas": ["DTOBITO", "IDADE", "SEXO", "CODMUNRES", "CAUSABAS", "TIPOBITO", "OBITOGRAV", "OBITOPUERP"],
    },
    "sinasc": {
        "dir": "/dissemin/publicos/SINASC/1996_/Dados/DNRES",
        "prefixo": "DN",
        "colunas": ["CODMUNRES", "DTNASC", "CONSULTAS", "CONSPRENAT", "PESO", "GESTACAO", "SEMAGESTAC", "PARTO", "IDADEMAE"],
    },
}

RAW_DIR = os.path.join("data", "raw", "datasus")
MANIFEST = os.path.join(RAW_DIR, "manifest_extracao.json")


def sha256_arquivo(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def ler_dbf_numpy(caminho_dbf: str, colunas: list) -> pd.DataFrame:
    """Lê um DBF (dBase III) de registros fixos e devolve somente as colunas pedidas (str)."""
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
        campos.append((nome, tam))
        pos += 32

    dtype = [("_del", "S1")] + [(n, f"S{t}") for n, t in campos]
    assert np.dtype(dtype).itemsize == tam_reg, "Layout DBF inconsistente com o tamanho do registro"
    arr = np.frombuffer(dados, dtype=np.dtype(dtype), count=n_reg, offset=tam_cab)

    saida = {}
    for c in colunas:
        if c in arr.dtype.names:
            saida[c] = np.char.decode(arr[c], "latin1")
            saida[c] = np.char.strip(saida[c])
        else:
            saida[c] = np.full(n_reg, "", dtype="U1")
    return pd.DataFrame(saida)


def baixar_e_decodificar(fonte: str, uf: str, ano: int) -> dict:
    from pyreaddbc import dbc2dbf

    cfg = FONTES[fonte]
    nome = f"{cfg['prefixo']}{uf}{ano}.dbc"
    tmp = tempfile.mkdtemp(prefix="dsus_")
    try:
        dbc = os.path.join(tmp, "a.dbc")
        dbf = os.path.join(tmp, "a.dbf")
        ftp = ftplib.FTP(FTP_HOST, timeout=120)
        ftp.login()
        ftp.cwd(cfg["dir"])
        try:
            with open(dbc, "wb") as fh:
                ftp.retrbinary(f"RETR {nome}", fh.write)
        except ftplib.error_perm:
            return {"arquivo": nome, "ok": False, "motivo": "ausente_no_ftp"}
        finally:
            try:
                ftp.quit()
            except Exception:
                pass
        sha = sha256_arquivo(dbc)
        tam = os.path.getsize(dbc)
        dbc2dbf(dbc, dbf)
        df = ler_dbf_numpy(dbf, cfg["colunas"])
        df["UF_ARQ"] = uf
        return {"arquivo": nome, "ok": True, "sha256": sha, "bytes": tam, "linhas": len(df), "df": df}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def extrair(fonte: str, ano: int, workers: int = 4) -> dict:
    destino = os.path.join(RAW_DIR, f"{fonte}_{ano}.parquet")
    if os.path.exists(destino):
        print(f"[datasus_ftp] {fonte} {ano}: já existe ({destino}); reutilizando.")
        return {"cache": True}

    print(f"[datasus_ftp] {fonte} {ano}: baixando {len(UFS)} UFs...")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(lambda uf: baixar_e_decodificar(fonte, uf, ano), UFS))

    faltantes = [r["arquivo"] for r in res if not r["ok"]]
    if faltantes:
        print(f"[datasus_ftp] {fonte} {ano}: AUSENTES no FTP: {faltantes}. Ano NÃO será gravado.")
        return {"ok": False, "ausentes": faltantes}

    df = pd.concat([r["df"] for r in res], ignore_index=True)
    os.makedirs(RAW_DIR, exist_ok=True)
    df.to_parquet(destino, index=False)
    print(f"[datasus_ftp] {fonte} {ano}: {len(df):,} registros -> {destino}")
    return {
        "ok": True,
        "linhas": int(len(df)),
        "arquivos": {r["arquivo"]: {"sha256": r["sha256"], "bytes": r["bytes"]} for r in res},
    }


def main(anos: list):
    manifesto = {}
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            manifesto = json.load(f)
    for ano in anos:
        for fonte in FONTES:
            r = extrair(fonte, ano)
            if r.get("ok"):
                manifesto[f"{fonte}_{ano}"] = {"data_coleta": date.today().isoformat(), **r}
            elif not r.get("cache"):
                manifesto[f"{fonte}_{ano}"] = {"data_coleta": date.today().isoformat(), **r}
            with open(MANIFEST, "w", encoding="utf-8") as f:
                json.dump(manifesto, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    anos_arg = [int(a) for a in sys.argv[1:]] or [2019, 2020, 2021, 2022, 2023]
    main(anos_arg)
