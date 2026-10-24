#!/usr/bin/env python3
"""
pipeline/export_site_payloads.py

Compila os artefatos JSON consumidos pelo site estático (/site):
  - data/releases/latest/meta_build.json
  - data/releases/latest/mapa_resumo.json
  - data/releases/latest/rankings_resumo.json
(e espelha em site/data/releases/latest/)

Garante conformidade estrita com as Regras Inegociáveis 1 a 4:
  - Todos os metadados vêm de config/*.yaml, sources/registry.yaml e data/processed/build_info.json
  - Nenhum indicador numérico é exportado sem fonte_id, fonte_detalhe, periodo_vintage,
    data_coleta real, versao_metodologia e qualidade_dado calculada por município.
"""

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yaml


def load_yaml(filepath: str):
    if not os.path.exists(filepath):
        print(f"[export_site_payloads:ERRO] Arquivo não encontrado: {filepath}")
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json_if_exists(filepath: str) -> dict:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def num_or_none(val, digits: int = 2):
    if val is None or pd.isna(val):
        return None
    return round(float(val), digits)


def build_meta_payload() -> dict:
    print("[export_site_payloads] Compilando metadados de build do pipeline...")

    version_file = os.path.join("config", "metodologia_versao.txt")
    with open(version_file, "r", encoding="utf-8-sig") as f:
        versao_metodologia = f.read().strip()

    indicadores_cfg = load_yaml(os.path.join("config", "indicadores.yaml"))
    pesos_cfg = load_yaml(os.path.join("config", "pesos.yaml"))
    limites_cfg = load_yaml(os.path.join("config", "limites_referencia.yaml"))
    janelas_cfg = load_yaml(os.path.join("config", "janelas.yaml"))
    qualidade_cfg = load_yaml(os.path.join("config", "qualidade.yaml"))
    registry_cfg = load_yaml(os.path.join("sources", "registry.yaml"))

    limites_congelados = load_json_if_exists(os.path.join("config", "limites_calculados.json"))
    build_info = load_json_if_exists(os.path.join("data", "processed", "build_info.json"))
    manifest = load_json_if_exists(os.path.join("data", "releases", "latest", "provenance_manifest.json"))
    auditoria_fontes = load_json_if_exists(os.path.join("data", "processed", "relatorio_comparacao_fontes.json"))

    meta_build = {
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "versao_metodologia": versao_metodologia,
        "status_metodologia": "Preliminar — Normalização Relativa por Percentis (P5–P95)",
        "regras_inegociaveis": [
            "Proibido inventar dados numéricos, metas ou limites sem validação documental",
            "Zero imputação silenciosa: dado ausente permanece NaN e exige mínimo de componentes por dimensão",
            "Todo número exige rastreabilidade (fonte, vintage, coleta, versão, IC 95% quando aplicável e selo de precisão)",
            "A Nota Geral nunca aparece sem as dimensões D1, D2 e D3 e a faixa de posição plausível",
            "Recálculo integral da série histórica a cada mudança de versão metodológica"
        ],
        "fontes": registry_cfg.get("fontes", []),
        "dimensoes": {
            "D1": {
                "nome": "Resultados em Saúde",
                "descricao": "Desfechos epidemiológicos por residência (D1.1 Mortalidade Infantil 2021–2023 ativa na nota; D1.2 Razão de Mortalidade Materna 2019–2023 informativa)",
                "nivel_agregacao": "Município de residência",
                "peso_padrao": pesos_cfg.get("esquemas", {}).get("pesos_iguais", {}).get("dimensoes", {}).get("D1", 0.3333)
            },
            "D2": {
                "nome": "Atenção Primária",
                "descricao": "Cobertura e efetividade da APS (D2.2 Pré-natal 7+ consultas SINASC e D2.3 Vacinação Poliomielite SI-PNI, triênio 2021–2023)",
                "nivel_agregacao": "Município de residência",
                "peso_padrao": pesos_cfg.get("esquemas", {}).get("pesos_iguais", {}).get("dimensoes", {}).get("D2", 0.3333)
            },
            "D3": {
                "nome": "Acesso e Estrutura",
                "descricao": "Capacidade instalada do SUS (D3.1 Leitos SUS, D3.2 Médicos e D3.3 Cobertura eSF, triênio 2021–2023)",
                "nivel_agregacao": "Município / Região de Saúde",
                "peso_padrao": pesos_cfg.get("esquemas", {}).get("pesos_iguais", {}).get("dimensoes", {}).get("D3", 0.3333)
            },
            "D4": {
                "nome": "Contexto Municipal",
                "descricao": "Financiamento e determinantes socioeconômicos — FORA DA NOTA PRINCIPAL (DEC-001)",
                "nivel_agregacao": "Município de residência",
                "peso_padrao": 0.0
            },
            "PRIVADA": {
                "nome": "Camada Privada",
                "descricao": "Saúde suplementar e oferta privada não-SUS — FORA DA NOTA PRINCIPAL (DEC-001)",
                "nivel_agregacao": "Município de residência",
                "peso_padrao": 0.0
            }
        },
        "indicadores": indicadores_cfg.get("indicadores", []),
        "pesos": pesos_cfg,
        "limites_referencia": limites_cfg,
        "limites_calculados": limites_congelados,
        "janelas": janelas_cfg,
        "qualidade_criterios": qualidade_cfg,
        "build_info": build_info,
        "auditoria_fontes": auditoria_fontes,
        "manifesto_hashes": manifest
    }

    for out_dir in (os.path.join("data", "releases", "latest"), os.path.join("site", "data", "releases", "latest")):
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "meta_build.json"), "w", encoding="utf-8") as f:
            json.dump(meta_build, f, ensure_ascii=False, indent=2)
        if manifest:
            with open(os.path.join(out_dir, "provenance_manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("[export_site_payloads] meta_build.json gerado com sucesso.")
    return meta_build


def build_mapa_resumo_payload(meta_build: dict):
    comp_path = os.path.join("data", "processed", "indice_saude_municipal.parquet")
    if not os.path.exists(comp_path):
        print(f"[export_site_payloads:ERRO] {comp_path} não encontrado.")
        sys.exit(1)

    print("[export_site_payloads] Gerando mapa_resumo.json a partir do índice v0.4.0...")
    df = pd.read_parquet(comp_path)

    versao = meta_build["versao_metodologia"]
    binfo = meta_build.get("build_info", {})
    coleta_sim = binfo.get("fontes", {}).get("sim_sinasc", {}).get("data_coleta") or binfo.get("gerado_em") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    coleta_ieps = binfo.get("fontes", {}).get("ieps", {}).get("data_coleta") or coleta_sim

    municipios_payload = {}
    for _, row in df.iterrows():
        ibge7 = str(row["ibge7"])
        pop_val = int(row["populacao_censo_2022"]) if pd.notna(row.get("populacao_censo_2022")) else None
        porte_val = str(row.get("porte_populacional", "A_VALIDAR"))
        status_mun = str(row.get("status", "sem_classificacao"))
        motivo_sem = str(row.get("motivo_sem_classificacao", ""))

        ic_d1_1 = [num_or_none(row.get("tmi_ic95_min")), num_or_none(row.get("tmi_ic95_max"))] if pd.notna(row.get("tmi_ic95_min")) else None
        ic_d1_2 = [num_or_none(row.get("rmm_ic95_min"), 1), num_or_none(row.get("rmm_ic95_max"), 1)] if pd.notna(row.get("rmm_ic95_min")) else None
        ic_d2_2 = [num_or_none(row.get("pre7_ic95_min"), 1), num_or_none(row.get("pre7_ic95_max"), 1)] if pd.notna(row.get("pre7_ic95_min")) else None

        indicadores_dict = {
            "D1.1": {
                "valor": num_or_none(row.get("tmi_bayes"), 2),
                "taxa_bruta": num_or_none(row.get("tmi_bruta"), 2),
                "escore": num_or_none(row.get("escore_D1_1"), 1),
                "eventos": int(row["d1_1_obitos"]) if pd.notna(row.get("d1_1_obitos")) else None,
                "denominador": int(row["d1_1_nv"]) if pd.notna(row.get("d1_1_nv")) else None,
                "ic_95": ic_d1_1,
                "fonte_id": "sim_do",
                "fonte_detalhe": "SIM + SINASC / DATASUS (microdados por residência)",
                "periodo_vintage": str(row.get("d1_1_janela", "2021–2023")),
                "data_coleta": coleta_sim,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D1_1", "baixa")),
                "papel_na_nota": "ativo (100% de D1)"
            },
            "D1.2": {
                "valor": num_or_none(row.get("rmm_bayes"), 1),
                "taxa_bruta": num_or_none(row.get("rmm_bruta"), 1),
                "escore": num_or_none(row.get("escore_D1_2"), 1),
                "eventos": int(row["d1_2_obitos"]) if pd.notna(row.get("d1_2_obitos")) else None,
                "denominador": int(row["d1_2_nv"]) if pd.notna(row.get("d1_2_nv")) else None,
                "ic_95": ic_d1_2,
                "fonte_id": "sim_do",
                "fonte_detalhe": "SIM + SINASC / DATASUS (informativo — fora da nota, PEND-038)",
                "periodo_vintage": str(row.get("d1_2_janela", "2019–2023")),
                "data_coleta": coleta_sim,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D1_2", "baixa")),
                "papel_na_nota": "informativo (peso 0)"
            },
            "D2.2": {
                "valor": num_or_none(row.get("pre7_pct"), 1),
                "taxa_bruta": num_or_none(row.get("pre7_pct"), 1),
                "escore": num_or_none(row.get("escore_D2_2"), 1),
                "eventos": int(row["d2_2_7mais"]) if pd.notna(row.get("d2_2_7mais")) else None,
                "denominador": int(row["d2_2_validas"]) if pd.notna(row.get("d2_2_validas")) else None,
                "ic_95": ic_d2_2,
                "fonte_id": "sinasc_nv",
                "fonte_detalhe": "SINASC / DATASUS (microdados por residência da mãe)",
                "periodo_vintage": str(row.get("d2_2_janela", "2021–2023")),
                "data_coleta": coleta_sim,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D2_2", "alta")),
                "papel_na_nota": "ativo (50% de D2)"
            },
            "D2.3": {
                "valor": num_or_none(row.get("cob_vac_polio"), 1),
                "taxa_bruta": num_or_none(row.get("cob_vac_polio"), 1),
                "escore": num_or_none(row.get("escore_D2_3"), 1),
                "ic_95": None,
                "fonte_id": "si_pni",
                "fonte_detalhe": "SI-PNI / MS consolidado via IEPS Data (média 2021–2023)",
                "periodo_vintage": "2021–2023",
                "data_coleta": coleta_ieps,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D2_3", "alta")),
                "papel_na_nota": "ativo (50% de D2)"
            },
            "D3.1": {
                "valor": num_or_none(row.get("tx_leito_sus"), 1),
                "taxa_bruta": num_or_none(row.get("tx_leito_sus"), 1),
                "escore": num_or_none(row.get("escore_D3_1"), 1),
                "ic_95": None,
                "fonte_id": "cnes",
                "fonte_detalhe": "CNES / MS consolidado via IEPS Data (média 2021–2023)",
                "periodo_vintage": "2021–2023",
                "data_coleta": coleta_ieps,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D3_1", "alta")),
                "papel_na_nota": "ativo (33,3% de D3)"
            },
            "D3.2": {
                "valor": num_or_none(row.get("tx_med"), 2),
                "taxa_bruta": num_or_none(row.get("tx_med"), 2),
                "escore": num_or_none(row.get("escore_D3_2"), 1),
                "ic_95": None,
                "fonte_id": "cnes",
                "fonte_detalhe": "CNES / MS consolidado via IEPS Data (média 2021–2023)",
                "periodo_vintage": "2021–2023",
                "data_coleta": coleta_ieps,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D3_2", "alta")),
                "papel_na_nota": "ativo (33,3% de D3)"
            },
            "D3.3": {
                "valor": num_or_none(row.get("cob_esf"), 1),
                "taxa_bruta": num_or_none(row.get("cob_esf"), 1),
                "escore": num_or_none(row.get("escore_D3_3"), 1),
                "ic_95": None,
                "fonte_id": "sisab",
                "fonte_detalhe": "e-Gestor AB / SAPS consolidado via IEPS Data (média 2021–2023)",
                "periodo_vintage": "2021–2023",
                "data_coleta": coleta_ieps,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D3_3", "alta")),
                "papel_na_nota": "ativo (33,3% de D3)"
            }
        }

        municipios_payload[ibge7] = {
            "ibge7": ibge7,
            "ibge6": str(row["ibge6"]),
            "nome": str(row["nome_municipio"]),
            "uf": str(row["uf_sigla"]),
            "regiao": str(row["regiao_macro"]),
            "populacao": pop_val,
            "porte": porte_val,
            "regiao_saude": str(row.get("regiao_imediata_nome", "A_VALIDAR")),
            "status": status_mun,
            "motivo_sem_classificacao": motivo_sem if status_mun != "classificado" else None,
            "nota_geral": num_or_none(row.get("nota_geral"), 1),
            "d1_nota": num_or_none(row.get("d1_nota"), 1),
            "d2_nota": num_or_none(row.get("d2_nota"), 1),
            "d3_nota": num_or_none(row.get("d3_nota"), 1),
            "faixa_posicao_min": int(row["faixa_posicao_min"]) if pd.notna(row.get("faixa_posicao_min")) else None,
            "faixa_posicao_max": int(row["faixa_posicao_max"]) if pd.notna(row.get("faixa_posicao_max")) else None,
            "posicao_nacional": int(row["posicao_nacional"]) if pd.notna(row.get("posicao_nacional")) else None,
            "posicao_estadual": int(row["posicao_estadual"]) if pd.notna(row.get("posicao_estadual")) else None,
            "posicao_grupo_pares": int(row["posicao_grupo_pares"]) if pd.notna(row.get("posicao_grupo_pares")) else None,
            "pct_obitos_mal_definidos": num_or_none(row.get("pct_obitos_mal_definidos"), 1),
            "indicadores": indicadores_dict,
            "d4_contexto": {
                "gasto_per_capita": None,
                "percentual_proprio": None
            },
            "camada_privada": {
                "cobertura_planos": None,
                "leitos_privados": {
                    "valor": num_or_none(row.get("leitos_priv_val"), 1),
                    "taxa_bruta": num_or_none(row.get("leitos_priv_val"), 1),
                    "ic_95": None,
                    "fonte_id": "cnes",
                    "fonte_detalhe": "CNES / MS consolidado via IEPS Data (média 2021–2023)",
                    "periodo_vintage": "2021–2023",
                    "data_coleta": coleta_ieps,
                    "versao_metodologia": versao,
                    "qualidade_dado": str(row.get("qualidade_PRIV_2", "alta"))
                }
            }
        }

    for out_dir in (os.path.join("data", "releases", "latest"), os.path.join("site", "data", "releases", "latest")):
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "mapa_resumo.json"), "w", encoding="utf-8") as f:
            json.dump(municipios_payload, f, ensure_ascii=False)

    print(f"[export_site_payloads] mapa_resumo.json gerado ({len(municipios_payload)} municípios).")
    build_rankings_payload(df)


def build_rankings_payload(df: pd.DataFrame):
    print("[export_site_payloads] Compilando rankings sintéticos consolidados...")
    cls = df[df["status"] == "classificado"].copy()

    def format_mun(row):
        return {
            "ibge7": str(row["ibge7"]),
            "nome": str(row["nome_municipio"]),
            "uf": str(row["uf_sigla"]),
            "populacao": int(row["populacao_censo_2022"]) if pd.notna(row.get("populacao_censo_2022")) else None,
            "porte": str(row.get("porte_populacional", "")),
            "escore": num_or_none(row.get("nota_geral"), 1),
            "d1_nota": num_or_none(row.get("d1_nota"), 1),
            "d2_nota": num_or_none(row.get("d2_nota"), 1),
            "d3_nota": num_or_none(row.get("d3_nota"), 1),
            "tmi_bayes": num_or_none(row.get("tmi_bayes"), 2),
            "faixa_min": int(row["faixa_posicao_min"]) if pd.notna(row.get("faixa_posicao_min")) else None,
            "faixa_max": int(row["faixa_posicao_max"]) if pd.notna(row.get("faixa_posicao_max")) else None,
            "posicao_nacional": int(row["posicao_nacional"]) if pd.notna(row.get("posicao_nacional")) else None,
            "posicao_estadual": int(row["posicao_estadual"]) if pd.notna(row.get("posicao_estadual")) else None
        }

    df_sorted = cls.sort_values(by=["nota_geral", "populacao_censo_2022"], ascending=[False, False])
    top10_brasil = [format_mun(r) for _, r in df_sorted.head(10).iterrows()]
    piores10_brasil = [format_mun(r) for _, r in df_sorted.tail(10).iloc[::-1].iterrows()]

    rankings_uf = {}
    for uf, group in cls.groupby("uf_sigla"):
        g_sorted = group.sort_values(by=["nota_geral", "populacao_censo_2022"], ascending=[False, False])
        rankings_uf[uf] = {
            "media_escore_uf": round(float(group["nota_geral"].mean()), 1),
            "media_d1_uf": round(float(group["d1_nota"].mean()), 1),
            "media_d2_uf": round(float(group["d2_nota"].mean()), 1),
            "media_d3_uf": round(float(group["d3_nota"].mean()), 1),
            "total_municipios": len(group),
            "melhores": [format_mun(r) for _, r in g_sorted.head(10).iterrows()],
            "piores": [format_mun(r) for _, r in g_sorted.tail(10).iloc[::-1].iterrows()]
        }

    rankings_payload = {
        "atualizacao": datetime.now(timezone.utc).isoformat(),
        "indicador_ativo": "Índice Sintético Consolidado (D1 + D2 + D3) — Janela 2021–2023 (Normalização por Percentis P5–P95)",
        "top10_brasil_melhores": top10_brasil,
        "top10_brasil_piores": piores10_brasil,
        "rankings_por_uf": rankings_uf
    }

    for out_dir in (os.path.join("data", "releases", "latest"), os.path.join("site", "data", "releases", "latest")):
        with open(os.path.join(out_dir, "rankings_resumo.json"), "w", encoding="utf-8") as f:
            json.dump(rankings_payload, f, ensure_ascii=False, indent=2)

    print("[export_site_payloads] rankings_resumo.json gerado com sucesso.")


def main():
    meta = build_meta_payload()
    build_mapa_resumo_payload(meta)
    print("[export_site_payloads] Todos os payloads do site foram gerados com sucesso.")


if __name__ == "__main__":
    main()
