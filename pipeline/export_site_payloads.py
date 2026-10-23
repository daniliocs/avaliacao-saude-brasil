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
    """Gera o arquivo data/releases/latest/mapa_resumo.json com os 5.570 municípios.
    Conforme as Regras 1 e 3, dados de saúde ainda em validação ficam explicitamente
    marcados como status 'sem_classificacao' e metadados null.
    """
    dim_path = os.path.join("data", "processed", "dim_municipio.parquet")
    if not os.path.exists(dim_path):
        print(f"[export_site_payloads:ERRO] dim_municipio.parquet não encontrado.")
        sys.exit(1)

    print("[export_site_payloads] Construindo payload de mapa municipal (5.570 municípios)...")
    df = pd.read_parquet(dim_path)

    municipios_payload = {}
    for _, row in df.iterrows():
        ibge7 = row["ibge7"]
        municipios_payload[ibge7] = {
            "ibge7": ibge7,
            "ibge6": row["ibge6"],
            "nome": row["nome_municipio"],
            "uf": row["uf_sigla"],
            "regiao": row["regiao_macro"],
            "porte": "A_VALIDAR", # Definido após consolidação do Censo
            "regiao_saude": row.get("regiao_imediata_nome", "A_VALIDAR"),
            # Campos do Índice (Regras 1 e 3: Não inventar valores; aguardando validação)
            "status": "sem_classificacao",
            "nota_geral": None,
            "d1_nota": None,
            "d2_nota": None,
            "d3_nota": None,
            "faixa_posicao_min": None,
            "faixa_posicao_max": None,
            "posicao_nacional": None,
            "posicao_estadual": None,
            "posicao_grupo_pares": None,
            "indicadores": {
                "D1.1": {"valor": None, "taxa_bruta": None, "ic_95": None, "fonte_id": "sim_do", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"},
                "D1.2": {"valor": None, "taxa_bruta": None, "ic_95": None, "fonte_id": "sim_do", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"},
                "D1.3": {"valor": None, "taxa_bruta": None, "ic_95": None, "fonte_id": "sim_do", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"},
                "D1.4": {"valor": None, "taxa_bruta": None, "ic_95": None, "fonte_id": "sim_do", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"},
                "D2.1": {"valor": None, "taxa_bruta": None, "ic_95": None, "fonte_id": "sih_rd", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"},
                "D2.2": {"valor": None, "taxa_bruta": None, "ic_95": None, "fonte_id": "sinasc_nv", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"},
                "D2.3": {"valor": None, "taxa_bruta": None, "ic_95": None, "fonte_id": "si_pni", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"},
                "D2.4": {"valor": None, "taxa_bruta": None, "ic_95": None, "fonte_id": "sisab", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"},
                "D3.1": {"valor": None, "taxa_bruta": None, "ic_95": None, "fonte_id": "cnes", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"},
                "D3.2": {"valor": None, "taxa_bruta": None, "ic_95": None, "fonte_id": "cnes", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"},
                "D3.3": {"valor": None, "taxa_bruta": None, "ic_95": None, "fonte_id": "sisab", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"},
                "D3.4": {"valor": None, "taxa_bruta": None, "ic_95": None, "fonte_id": "sih_rd", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"}
            },
            "d4_contexto": {
                "gasto_per_capita": {"valor": None, "fonte_id": "siops", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"},
                "percentual_proprio": {"valor": None, "fonte_id": "siops", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"}
            },
            "camada_privada": {
                "cobertura_planos": {"valor": None, "fonte_id": "ans", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"},
                "leitos_privados": {"valor": None, "fonte_id": "cnes", "periodo_vintage": None, "data_coleta": None, "versao_metodologia": "v0.1.0-draft", "qualidade_dado": "A_VALIDAR"}
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


def main():
    build_meta_payload()
    build_mapa_resumo_payload()
    print("[export_site_payloads] Todos os payloads do site foram gerados com sucesso.")


if __name__ == "__main__":
    main()
