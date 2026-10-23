#!/usr/bin/env python3
"""
pipeline/01_build_dim_municipio.py

Constrói a tabela dimensional oficial de municípios do Brasil (dim_municipio).
Atende às regras da Seção 1 da Especificação:
- Universo: exatamente 5.570 municípios (série histórica SUS / Censo 2022, incluindo Fernando de Noronha - 2605459).
- Chave primária: ibge7 (código IBGE de 7 dígitos como string).
- Coluna ibge6: 6 dígitos (sem dígito verificador), obrigatória para cruzamento com bases DATASUS.
- Testes automatizados de cardinalidade (assert count == 5570) e unicidade.
"""

import os
import sys
import json
import gzip
import urllib.request
import pandas as pd

API_IBGE_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
RAW_CACHE_PATH = os.path.join("data", "raw", "ibge_municipios_raw.json")
OUTPUT_PARQUET = os.path.join("data", "processed", "dim_municipio.parquet")
OUTPUT_CSV = os.path.join("data", "processed", "dim_municipio.csv")

# Município criado pelo STF/TSE em 2023/2024 com vigência política a partir de 2025.
# Não integra as séries históricas do DATASUS até 2024 (território original em Sorriso e Nova Ubiratã).
# Registrado formalmente em docs/PENDENCIAS.md sob o ID PEND-001.
ID_BOA_ESPERANCA_DO_NORTE = 5101837


def fetch_raw_data() -> list:
    """Obtém os dados brutos da API oficial do IBGE ou utiliza cache local se offline."""
    if os.path.exists(RAW_CACHE_PATH):
        print(f"[dim_municipio] Lendo dados brutos do cache: {RAW_CACHE_PATH}")
        with open(RAW_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"[dim_municipio] Requisitando dados oficiais da API do IBGE: {API_IBGE_MUNICIPIOS}")
    req = urllib.request.Request(
        API_IBGE_MUNICIPIOS,
        headers={"User-Agent": "IndiceSaudeBrasil-Pipeline/0.1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        content = response.read()
        try:
            data = json.loads(content.decode("utf-8"))
        except UnicodeDecodeError:
            data = json.loads(gzip.decompress(content).decode("utf-8"))

    # Salva no cache raw para reprodutibilidade
    os.makedirs(os.path.dirname(RAW_CACHE_PATH), exist_ok=True)
    with open(RAW_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[dim_municipio] Cache bruto gravado com sucesso em: {RAW_CACHE_PATH}")
    return data


POP_CACHE_PATH = os.path.join("data", "raw", "ibge_censo2022_pop.json")

def load_populacao_censo2022() -> dict:
    """Carrega dados oficiais do Censo Demográfico 2022 do IBGE."""
    if os.path.exists(POP_CACHE_PATH):
        with open(POP_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def classificar_porte(pop: int) -> str:
    if pop is None or pop <= 0:
        return "Não informado"
    if pop <= 20000:
        return "Pequeno porte I (até 20 mil hab.)"
    if pop <= 50000:
        return "Pequeno porte II (20 a 50 mil hab.)"
    if pop <= 100000:
        return "Médio porte (50 a 100 mil hab.)"
    if pop <= 500000:
        return "Grande porte (100 a 500 mil hab.)"
    return "Metrópole (> 500 mil hab.)"

def process_dim_municipio(raw_data: list) -> pd.DataFrame:
    """Processa e formata a dimensão de municípios garantindo as regras da especificação."""
    pop_map = load_populacao_censo2022()
    records = []
    for item in raw_data:
        ibge7_int = item["id"]
        # Filtro da série histórica consolidada de 5.570 municípios (PEND-001)
        if ibge7_int == ID_BOA_ESPERANCA_DO_NORTE:
            print(f"[dim_municipio] Isolando município de 2025 {ibge7_int} ({item.get('nome')}) para conformidade com a série histórica SUS de 5.570 municípios.")
            continue

        ibge7_str = str(ibge7_int).zfill(7)
        ibge6_str = ibge7_str[:6]

        # Extração hierárquica resiliente
        nome_mun = item.get("nome", "").strip()
        reg_imediata = item.get("regiao-imediata") or {}
        reg_intermediaria = reg_imediata.get("regiao-intermediaria") or {}
        uf_info = reg_intermediaria.get("UF") or (item.get("microrregiao") or {}).get("mesorregiao", {}).get("UF") or {}

        uf_sigla = uf_info.get("sigla", "")
        uf_codigo = str(uf_info.get("id", ibge7_str[:2]))
        uf_nome = uf_info.get("nome", "")
        regiao_info = uf_info.get("regiao") or {}
        regiao_nome = regiao_info.get("nome", "")

        pop_2022 = pop_map.get(ibge7_str)
        porte = classificar_porte(pop_2022)

        records.append({
            "ibge7": ibge7_str,
            "ibge6": ibge6_str,
            "nome_municipio": nome_mun,
            "uf_sigla": uf_sigla,
            "uf_codigo": uf_codigo,
            "uf_nome": uf_nome,
            "regiao_macro": regiao_nome,
            "regiao_imediata_id": str(reg_imediata.get("id", "")),
            "regiao_imediata_nome": reg_imediata.get("nome", ""),
            "regiao_intermediaria_id": str(reg_intermediaria.get("id", "")),
            "regiao_intermediaria_nome": reg_intermediaria.get("nome", ""),
            "populacao_censo_2022": pop_2022,
            "porte_populacional": porte
        })

    df = pd.DataFrame(records)
    # Ordenação por código IBGE7
    df = df.sort_values("ibge7").reset_index(drop=True)
    return df


def validate_dim_municipio(df: pd.DataFrame) -> None:
    """Aplica testes automatizados de qualidade e cardinalidade conforme a Seção 1."""
    print("[dim_municipio] Executando testes automatizados de validação...")

    # 1. Teste de Cardinalidade Exata (5.570 municípios)
    total_count = len(df)
    assert total_count == 5570, f"FALHA DE CARDINALIDADE: esperado 5570 municípios, obtido {total_count}"

    # 2. Teste de Unicidade de Chaves
    assert df["ibge7"].nunique() == 5570, "FALHA DE UNICIDADE: chaves ibge7 duplicadas encontradas"
    assert df["ibge6"].nunique() == 5570, "FALHA DE UNICIDADE: chaves ibge6 duplicadas encontradas"

    # 3. Teste de Formato das Chaves
    assert (df["ibge7"].str.len() == 7).all(), "FALHA DE FORMATO: todos os ibge7 devem ter exatamente 7 dígitos"
    assert (df["ibge6"].str.len() == 6).all(), "FALHA DE FORMATO: todos os ibge6 devem ter exatamente 6 dígitos"
    assert (df["ibge7"].str[:6] == df["ibge6"]).all(), "FALHA DE INTEGRIDADE: ibge6 deve corresponder aos primeiros 6 dígitos de ibge7"

    # 4. Teste de Casos Críticos
    assert "2605459" in df["ibge7"].values, "FALHA DE ESCOPO: Fernando de Noronha (2605459) deve estar presente"
    assert "5300108" in df["ibge7"].values, "FALHA DE ESCOPO: Brasília (5300108) deve estar presente"

    # 5. Teste de Não-Nulos
    assert not df["nome_municipio"].isna().any(), "FALHA: Nomes de municípios não podem ser nulos"
    assert not df["uf_sigla"].isna().any(), "FALHA: Siglas de UF não podem ser nulas"

    print(f"[dim_municipio] Todos os testes passaram com sucesso! Total validado: {total_count} municípios.")


def main():
    raw_data = fetch_raw_data()
    df = process_dim_municipio(raw_data)
    validate_dim_municipio(df)

    # Persistência dos artefatos processados
    os.makedirs(os.path.dirname(OUTPUT_PARQUET), exist_ok=True)
    df.to_parquet(OUTPUT_PARQUET, index=False)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")

    # Também espelha para site/data/processed/ para suportar GitHub Pages
    site_processed = os.path.join("site", "data", "processed")
    os.makedirs(site_processed, exist_ok=True)
    df.to_parquet(os.path.join(site_processed, "dim_municipio.parquet"), index=False)
    df.to_csv(os.path.join(site_processed, "dim_municipio.csv"), index=False, encoding="utf-8")

    print(f"[dim_municipio] Artefatos gerados com sucesso:")
    print(f"  - Parquet: {OUTPUT_PARQUET} ({os.path.getsize(OUTPUT_PARQUET)} bytes)")
    print(f"  - CSV:     {OUTPUT_CSV} ({os.path.getsize(OUTPUT_CSV)} bytes)")


if __name__ == "__main__":
    main()
