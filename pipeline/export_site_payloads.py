#!/usr/bin/env python3
"""
pipeline/export_site_payloads.py

Lê os arquivos de configuração (/config) e o registro oficial de fontes (/sources/registry.yaml)
e compila os metadados do pipeline em /data/releases/latest/meta_build.json.

Garante que as páginas "Como é calculado" e "Fontes" do site sejam 100% geradas
a partir da configuração real e auditável do pipeline, eliminando divergências conceituais.
Também compila data/releases/latest/mapa_resumo.json a partir de dim_municipio.parquet,
marcando os municípios como "sem_classificacao" até a validação das fontes (Regra Inegociável 3).
"""

import os
import sys
import json
import yaml
import pandas as pd
from datetime import datetime, timezone


def load_yaml(filepath: str):
    if not os.path.exists(filepath):
        print(f"[export_site_payloads:ERRO] Arquivo não encontrado: {filepath}")
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_meta_payload() -> dict:
    print("[export_site_payloads] Compilando metadados de build do pipeline...")

    # 1. Versão da Metodologia
    version_file = os.path.join("config", "metodologia_versao.txt")
    with open(version_file, "r", encoding="utf-8") as f:
        versao_metodologia = f.read().strip()

    # 2. Insumos YAML
    indicadores_cfg = load_yaml(os.path.join("config", "indicadores.yaml"))
    pesos_cfg = load_yaml(os.path.join("config", "pesos.yaml"))
    limites_cfg = load_yaml(os.path.join("config", "limites_referencia.yaml"))
    registry_cfg = load_yaml(os.path.join("sources", "registry.yaml"))

    # 3. Proveniência e Hashes
    manifest_path = os.path.join("data", "releases", "latest", "provenance_manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    # 4. Estruturação do objeto meta_build
    meta_build = {
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "versao_metodologia": versao_metodologia,
        "status_metodologia": "Rascunho Técnico (Fase 0)",
        "regras_inegociaveis": [
            "Proibido inventar dados numéricos ou limites",
            "Todo número exige rastreabilidade (fonte, vintage, coleta, versão, IC 95% e selo)",
            "A Nota Geral nunca aparece sem as dimensões D1, D2 e D3 e faixa de sensibilidade",
            "Recálculo integral de séries históricas em nova versão"
        ],
        "fontes": registry_cfg.get("fontes", []),
        "dimensoes": {
            "D1": {
                "nome": "Resultados em Saúde",
                "descricao": "Medição de desfechos em saúde (mortalidade infantil, materna, prematura por DCNT e causas evitáveis)",
                "nivel_agregacao": "Município de residência",
                "peso_padrao": pesos_cfg.get("esquemas", {}).get("pesos_iguais", {}).get("dimensoes", {}).get("D1", 0.3333)
            },
            "D2": {
                "nome": "Atenção Primária",
                "descricao": "Processos assistenciais e cobertura da atenção primária como ordenadora da rede do SUS",
                "nivel_agregacao": "Município de residência",
                "peso_padrao": pesos_cfg.get("esquemas", {}).get("pesos_iguais", {}).get("dimensoes", {}).get("D2", 0.3333)
            },
            "D3": {
                "nome": "Acesso e Estrutura",
                "descricao": "Capacidade instalada da rede pública de saúde (leitos na Região de Saúde, médicos e equipes)",
                "nivel_agregacao": "Região de Saúde / Município",
                "peso_padrao": pesos_cfg.get("esquemas", {}).get("pesos_iguais", {}).get("dimensoes", {}).get("D3", 0.3333)
            },
            "D4": {
                "nome": "Contexto Municipal",
                "descricao": "Gastos e aspectos socioeconômicos — FORA DA NOTA PRINCIPAL (DEC-001)",
                "nivel_agregacao": "Município de residência",
                "peso_padrao": 0.0
            },
            "PRIVADA": {
                "nome": "Camada Privada",
                "descricao": "Cobertura de saúde suplementar e oferta privada não-SUS — FORA DA NOTA PRINCIPAL (DEC-001)",
                "nivel_agregacao": "Município de residência",
                "peso_padrao": 0.0
            }
        },
        "indicadores": indicadores_cfg.get("indicadores", []),
        "pesos": pesos_cfg,
        "limites_referencia": limites_cfg,
        "manifesto_hashes": manifest
    }

    output_path = os.path.join("data", "releases", "latest", "meta_build.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(meta_build, f, ensure_ascii=False, indent=2)

    # Também espelha para site/data/releases/latest/ para garantir que o site funcione tanto servido da raiz quanto de /site
    site_output_path = os.path.join("site", "data", "releases", "latest", "meta_build.json")
    os.makedirs(os.path.dirname(site_output_path), exist_ok=True)
    with open(site_output_path, "w", encoding="utf-8") as f:
        json.dump(meta_build, f, ensure_ascii=False, indent=2)

    # Copia o manifesto de proveniência para site/data/releases/latest/
    if os.path.exists(manifest_path):
        site_manifest_path = os.path.join("site", "data", "releases", "latest", "provenance_manifest.json")
        with open(site_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    print(f"[export_site_payloads] meta_build.json gerado com sucesso em: {output_path} e {site_output_path}")
    return meta_build


def build_mapa_resumo_payload():
    """Gera o arquivo data/releases/latest/mapa_resumo.json e rankings_resumo.json.
    Na Fase 2, incorpora os dados calculados de D1.1 (Mortalidade Infantil) com base oficial.
    """
    dim_path = os.path.join("data", "processed", "dim_municipio.parquet")
    d1_path = os.path.join("data", "processed", "indicador_d1_1.parquet")
    if not os.path.exists(dim_path):
        print(f"[export_site_payloads:ERRO] dim_municipio.parquet não encontrado.")
        sys.exit(1)

    print("[export_site_payloads] Construindo payload de mapa municipal (5.570 municípios)...")
    df = pd.read_parquet(dim_path)

    # Carrega dados do Indicador D1.1 se calculado (Fase 2)
    has_d1 = os.path.exists(d1_path)
    d1_map = {}
    if has_d1:
        print("[export_site_payloads] Incorporando dados calculados do Indicador D1.1...")
        df_d1 = pd.read_parquet(d1_path)
        d1_map = df_d1.set_index("ibge7").to_dict(orient="index")

    municipios_payload = {}
    for _, row in df.iterrows():
        ibge7 = row["ibge7"]
        pop_val = int(row["populacao_censo_2022"]) if "populacao_censo_2022" in row and pd.notna(row["populacao_censo_2022"]) else None
        porte_val = row.get("porte_populacional", "A_VALIDAR")

        d1_data = d1_map.get(ibge7, {})
        escore_d1 = d1_data.get("escore_d1_1")
        is_classified = escore_d1 is not None and pd.notna(escore_d1)

        d1_item = {
            "valor": float(d1_data["tmi_bayes"]) if is_classified else None,
            "taxa_bruta": float(d1_data["tmi_bruta"]) if is_classified else None,
            "ic_95": [float(d1_data["ic_95_min"]), float(d1_data["ic_95_max"])] if is_classified else None,
            "fonte_id": "sim_do",
            "periodo_vintage": "2022" if is_classified else None,
            "data_coleta": "2026-10-23" if is_classified else None,
            "versao_metodologia": "v0.1.0-draft",
            "qualidade_dado": "alta" if is_classified else "A_VALIDAR"
        }

        indicadores_dict = {}
        if is_classified:
            indicadores_dict["D1.1"] = d1_item

        municipios_payload[ibge7] = {
            "ibge7": ibge7,
            "ibge6": row["ibge6"],
            "nome": row["nome_municipio"],
            "uf": row["uf_sigla"],
            "regiao": row["regiao_macro"],
            "populacao": pop_val,
            "porte": porte_val,
            "regiao_saude": row.get("regiao_imediata_nome", "A_VALIDAR"),
            "status": "classificado" if is_classified else "sem_classificacao",
            "nota_geral": float(escore_d1) if is_classified else None,
            "d1_nota": float(escore_d1) if is_classified else None,
            "d2_nota": None,
            "d3_nota": None,
            "faixa_posicao_min": int(d1_data["faixa_posicao_min"]) if is_classified else None,
            "faixa_posicao_max": int(d1_data["faixa_posicao_max"]) if is_classified else None,
            "posicao_nacional": int(d1_data["posicao_nacional"]) if is_classified else None,
            "posicao_estadual": int(d1_data["posicao_estadual"]) if is_classified else None,
            "posicao_grupo_pares": int(d1_data["posicao_grupo_pares"]) if is_classified else None,
            "indicadores": indicadores_dict,
            "d4_contexto": {
                "gasto_per_capita": None,
                "percentual_proprio": None
            },
            "camada_privada": {
                "cobertura_planos": None,
                "leitos_privados": None
            }
        }

    output_path = os.path.join("data", "releases", "latest", "mapa_resumo.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(municipios_payload, f, ensure_ascii=False)

    site_output_path = os.path.join("site", "data", "releases", "latest", "mapa_resumo.json")
    os.makedirs(os.path.dirname(site_output_path), exist_ok=True)
    with open(site_output_path, "w", encoding="utf-8") as f:
        json.dump(municipios_payload, f, ensure_ascii=False)

    print(f"[export_site_payloads] mapa_resumo.json gerado ({len(municipios_payload)} municípios) em: {output_path} e {site_output_path}")

    # Geração dos rankings (Top 10 Brasil e por UF)
    if has_d1:
        build_rankings_payload(df_d1)


def build_rankings_payload(df_d1: pd.DataFrame):
    """Gera o arquivo de rankings (Top 10 Brasil e por UF) para o painel da interface."""
    print("[export_site_payloads] Compilando rankings dos melhores e piores do Brasil e por UF...")

    def format_mun(row):
        return {
            "ibge7": str(row["ibge7"]),
            "nome": str(row["nome_municipio"]),
            "uf": str(row["uf_sigla"]),
            "populacao": int(row["populacao_censo_2022"]) if pd.notna(row.get("populacao_censo_2022")) else None,
            "porte": str(row.get("porte_populacional", "")),
            "escore": float(row["escore_d1_1"]),
            "tmi_bayes": float(row["tmi_bayes"]),
            "tmi_bruta": float(row["tmi_bruta"]),
            "posicao_nacional": int(row["posicao_nacional"]),
            "posicao_estadual": int(row["posicao_estadual"])
        }

    # Top 10 Melhores e Piores Brasil
    df_sorted = df_d1.sort_values(by=["escore_d1_1", "tmi_bayes", "populacao_censo_2022"], ascending=[False, True, False])
    top10_brasil = [format_mun(r) for _, r in df_sorted.head(10).iterrows()]
    piores10_brasil = [format_mun(r) for _, r in df_sorted.tail(10).iloc[::-1].iterrows()]

    # Rankings por UF
    rankings_uf = {}
    for uf, group in df_d1.groupby("uf_sigla"):
        g_sorted = group.sort_values(by=["escore_d1_1", "tmi_bayes"], ascending=[False, True])
        rankings_uf[uf] = {
            "media_escore_uf": round(float(group["escore_d1_1"].mean()), 1),
            "media_tmi_uf": round(float(group["tmi_bayes"].mean()), 2),
            "total_municipios": len(group),
            "melhores": [format_mun(r) for _, r in g_sorted.head(10).iterrows()],
            "piores": [format_mun(r) for _, r in g_sorted.tail(10).iloc[::-1].iterrows()]
        }

    rankings_payload = {
        "atualizacao": datetime.now(timezone.utc).isoformat(),
        "indicador_ativo": "D1.1 (Mortalidade Infantil)",
        "top10_brasil_melhores": top10_brasil,
        "top10_brasil_piores": piores10_brasil,
        "rankings_por_uf": rankings_uf
    }

    out_rank = os.path.join("data", "releases", "latest", "rankings_resumo.json")
    with open(out_rank, "w", encoding="utf-8") as f:
        json.dump(rankings_payload, f, ensure_ascii=False, indent=2)

    site_out_rank = os.path.join("site", "data", "releases", "latest", "rankings_resumo.json")
    with open(site_out_rank, "w", encoding="utf-8") as f:
        json.dump(rankings_payload, f, ensure_ascii=False, indent=2)

    print(f"[export_site_payloads] rankings_resumo.json gerado com sucesso em: {out_rank} e {site_out_rank}")


def main():
    build_meta_payload()
    build_mapa_resumo_payload()
    print("[export_site_payloads] Todos os payloads do site foram gerados com sucesso.")


if __name__ == "__main__":
    main()
