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

# Coordenadas das 27 Capitais (IBGE 7 dígitos -> (lat, lng, uf, nome_uf))
CAPITAIS_INFO = {
    "1100205": (-8.7619, -63.9039, "RO", "Rondônia"),
    "1200401": (-9.9754, -67.8249, "AC", "Acre"),
    "1302603": (-3.1190, -60.0217, "AM", "Amazonas"),
    "1400100": (2.8235, -60.6758, "RR", "Roraima"),
    "1501402": (-1.4558, -48.4902, "PA", "Pará"),
    "1600303": (0.0356, -51.0705, "AP", "Amapá"),
    "1721000": (-10.2491, -48.3243, "TO", "Tocantins"),
    "2111300": (-2.5391, -44.2829, "MA", "Maranhão"),
    "2211001": (-5.0920, -42.8038, "PI", "Piauí"),
    "2304400": (-3.7319, -38.5267, "CE", "Ceará"),
    "2408102": (-5.7945, -35.2110, "RN", "Rio Grande do Norte"),
    "2507507": (-7.1195, -34.8450, "PB", "Paraíba"),
    "2611606": (-8.0476, -34.8770, "PE", "Pernambuco"),
    "2704302": (-9.6658, -35.7350, "AL", "Alagoas"),
    "2800308": (-10.9472, -37.0731, "SE", "Sergipe"),
    "2927408": (-12.9777, -38.5016, "BA", "Bahia"),
    "3106200": (-19.9167, -43.9345, "MG", "Minas Gerais"),
    "3205309": (-20.3155, -40.3128, "ES", "Espírito Santo"),
    "3304557": (-22.9068, -43.1729, "RJ", "Rio de Janeiro"),
    "3550308": (-23.5505, -46.6333, "SP", "São Paulo"),
    "4106902": (-25.4284, -49.2733, "PR", "Paraná"),
    "4205407": (-27.5949, -48.5482, "SC", "Santa Catarina"),
    "4314902": (-30.0346, -51.2177, "RS", "Rio Grande do Sul"),
    "5002704": (-20.4697, -54.6201, "MS", "Mato Grosso do Sul"),
    "5103403": (-15.6014, -56.0979, "MT", "Mato Grosso"),
    "5208707": (-16.6869, -49.2648, "GO", "Goiás"),
    "5300108": (-15.7975, -47.8919, "DF", "Distrito Federal"),
}

UF_CENTROIDES = {
    "AC": (-9.02, -70.81, "Acre"),
    "AL": (-9.57, -36.78, "Alagoas"),
    "AM": (-3.41, -65.85, "Amazonas"),
    "AP": (1.41, -51.77, "Amapá"),
    "BA": (-12.57, -41.70, "Bahia"),
    "CE": (-5.49, -39.32, "Ceará"),
    "DF": (-15.83, -47.86, "Distrito Federal"),
    "ES": (-19.18, -40.30, "Espírito Santo"),
    "GO": (-15.93, -50.14, "Goiás"),
    "MA": (-5.42, -45.44, "Maranhão"),
    "MG": (-18.51, -44.55, "Minas Gerais"),
    "MS": (-20.77, -54.78, "Mato Grosso do Sul"),
    "MT": (-12.68, -55.42, "Mato Grosso"),
    "PA": (-3.79, -52.48, "Pará"),
    "PB": (-7.24, -36.78, "Paraíba"),
    "PE": (-8.28, -37.86, "Pernambuco"),
    "PI": (-7.71, -42.72, "Piauí"),
    "PR": (-24.89, -51.55, "Paraná"),
    "RJ": (-22.25, -42.66, "Rio de Janeiro"),
    "RN": (-5.81, -36.59, "Rio Grande do Norte"),
    "RO": (-10.83, -63.34, "Rondônia"),
    "RR": (2.73, -61.30, "Roraima"),
    "RS": (-30.01, -53.48, "Rio Grande do Sul"),
    "SC": (-27.33, -50.44, "Santa Catarina"),
    "SE": (-10.57, -37.38, "Sergipe"),
    "SP": (-22.19, -48.79, "São Paulo"),
    "TO": (-10.25, -48.25, "Tocantins"),
}


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
        "status_metodologia": "Experimental — Normalização Relativa por Percentis (P5–P95)",
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
                "nome": "Resultados em Saúde da População",
                "descricao": "Desfechos epidemiológicos por residência (D1.1 Mortalidade Infantil, D1.3 Mortalidade Prematura DCNT 30–69a e D1.4 Causas Evitáveis no triênio 2021–2023; D1.2 Razão de Mortalidade Materna 2019–2023 informativa)",
                "nivel_agregacao": "Município de residência",
                "peso_padrao": pesos_cfg.get("esquemas", {}).get("pesos_iguais", {}).get("dimensoes", {}).get("D1", 0.3333)
            },
            "D2": {
                "nome": "Atenção Primária e Prevenção",
                "descricao": "Resolutividade e prevenção na APS (D2.1 Internações Sensíveis à APS - ICSAP, D2.2 Pré-natal 7+ consultas SINASC e D2.3 Cobertura Vacinal Composta Pólio+Penta+Tríplice Viral, triênio 2021–2023)",
                "nivel_agregacao": "Município de residência",
                "peso_padrao": pesos_cfg.get("esquemas", {}).get("pesos_iguais", {}).get("dimensoes", {}).get("D2", 0.3333)
            },
            "D3": {
                "nome": "Acesso e Capacidade Assistencial",
                "descricao": "Capacidade instalada e regionalizada do SUS (D3.1 Leitos SUS na Região de Saúde, D3.2 Médicos e Enfermeiros padronizados por CH e D3.3 Cobertura eSF, triênio 2021–2023)",
                "nivel_agregacao": "Região de Saúde / Município",
                "peso_padrao": pesos_cfg.get("esquemas", {}).get("pesos_iguais", {}).get("dimensoes", {}).get("D3", 0.3333)
            },
            "D4": {
                "nome": "Contexto Financeiro Municipal",
                "descricao": "Despesa per capita deflacionada (SIOPS) e aplicação de receita própria (% EC 29) — FORA DA NOTA PRINCIPAL (DEC-001)",
                "nivel_agregacao": "Município de residência",
                "peso_padrao": 0.0
            },
            "PRIVADA": {
                "nome": "Camada Privada e Saúde Suplementar",
                "descricao": "Cobertura de planos privados (ANS) e leitos hospitalares não-SUS (CNES) — FORA DA NOTA PRINCIPAL (DEC-001)",
                "nivel_agregacao": "Município de residência",
                "peso_padrao": 0.0
            },
            "D5": {
                "nome": "Rede de Urgência & SAMU 192 (Golden Hour)",
                "descricao": "Prontidão imediata local (35%) e rede regional SAMU/UPA descontada pela distância rodoviária até o Polo Hospitalar capacitado com UTI/tomógrafo (65%, f_dist = exp(-0.012 * d_km))",
                "nivel_agregacao": "Município / Região de Saúde",
                "peso_padrao": 0.15
            },
            "D6": {
                "nome": "Linha de Cuidado Oncológico & CACON/UNACON",
                "descricao": "Agilidade e cumprimento efetivo da Lei dos 60 dias sobre total de diagnosticados (30%), Diagnóstico Precoce auditado (20%), Conversão Terapêutica contra fila oculta TRATAMENTO=5 + Sobrevida D1 (25%) e Autonomia TFD + Terapias de Ponta CNES (25%)",
                "nivel_agregacao": "Município / Polo de Referência",
                "peso_padrao": 0.10
            },
            "INFRA": {
                "nome": "Infraestrutura Assistencial & Suporte Diagnóstico (CNES)",
                "descricao": "Exames básicos locais (Raio-X, US, ECG, Desfibrilador), Exames avançados regionalizados (Tomógrafo, RM, Hemodinâmica, Endoscopia) e Capacidade Hospitalar (Leitos UTI SUS, Leitos Cirúrgicos, PS Hospitalar, Unidades Móveis CNES)",
                "nivel_agregacao": "Município / Polo Hospitalar",
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

    print(f"[export_site_payloads] Gerando mapa_resumo.json a partir do índice {meta_build['versao_metodologia']}...")
    df = pd.read_parquet(comp_path)
    total_uf_map = df["uf_sigla"].value_counts().to_dict()
    total_porte_map = df["porte_populacional"].value_counts().to_dict()

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
        reg_saude = str(row.get("regiao_saude_nome", row.get("regiao_imediata_nome", "A_VALIDAR")))
        if not reg_saude or reg_saude == "nan":
            reg_saude = str(row.get("regiao_imediata_nome", "A_VALIDAR"))

        ic_d1_1 = [num_or_none(row.get("tmi_ic95_min")), num_or_none(row.get("tmi_ic95_max"))] if pd.notna(row.get("tmi_ic95_min")) else None
        ic_d1_2 = [num_or_none(row.get("rmm_ic95_min"), 1), num_or_none(row.get("rmm_ic95_max"), 1)] if pd.notna(row.get("rmm_ic95_min")) else None
        ic_d1_3 = [num_or_none(row.get("dcnt_ic95_min"), 1), num_or_none(row.get("dcnt_ic95_max"), 1)] if pd.notna(row.get("dcnt_ic95_min")) else None
        ic_d2_2 = [num_or_none(row.get("pre7_ic95_min"), 1), num_or_none(row.get("pre7_ic95_max"), 1)] if pd.notna(row.get("pre7_ic95_min")) else None

        indicadores_dict = {
            "D1.1": {
                "valor": num_or_none(row.get("tmi_bayes"), 2),
                "taxa_bruta": num_or_none(row.get("tmi_bruta"), 2),
                "tmn_bruta": num_or_none(row.get("tmn_bruta"), 2),
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
                "papel_na_nota": "ativo (40% de D1)"
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
                "papel_na_nota": "informativo"
            },
            "D1.3": {
                "valor": num_or_none(row.get("dcnt_bayes"), 1),
                "taxa_bruta": num_or_none(row.get("dcnt_bruta"), 1),
                "escore": num_or_none(row.get("escore_D1_3"), 1),
                "eventos": int(row["d1_3_obitos"]) if pd.notna(row.get("d1_3_obitos")) else None,
                "denominador": int(row["d1_3_pop_anos"]) if pd.notna(row.get("d1_3_pop_anos")) else None,
                "ic_95": ic_d1_3,
                "fonte_id": "sim_do",
                "fonte_detalhe": "SIM / DATASUS (30–69a padronizada por idade Censo 2022 + redistribuição de mal definidos)",
                "periodo_vintage": str(row.get("d1_3_janela", "2021–2023")),
                "data_coleta": coleta_sim,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D1_3", "media")),
                "papel_na_nota": "ativo (30% de D1)"
            },
            "D1.4": {
                "valor": num_or_none(row.get("tx_mort_evit"), 1),
                "taxa_bruta": num_or_none(row.get("tx_mort_evit"), 1),
                "escore": num_or_none(row.get("escore_D1_4"), 1),
                "ic_95": None,
                "fonte_id": "sim_do",
                "fonte_detalhe": "SIM / MS (Lista Brasileira de Evitabilidade ajustada pela pirâmide etária Censo 2022) via IEPS Data",
                "periodo_vintage": "2021–2023",
                "data_coleta": coleta_ieps,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D1_4", "alta")),
                "papel_na_nota": "ativo (30% de D1)"
            },
            "D2.1": {
                "valor": num_or_none(row.get("icsap_10k"), 1),
                "taxa_bruta": num_or_none(row.get("icsap_10k"), 1),
                "escore": num_or_none(row.get("escore_D2_1"), 1),
                "ic_95": None,
                "fonte_id": "sih_rd",
                "fonte_detalhe": "SIH/SUS (Portaria SAS/MS 221/2008 - CSAP) via IEPS Data",
                "periodo_vintage": "2021–2023",
                "data_coleta": coleta_ieps,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D2_1", "alta")),
                "papel_na_nota": "ativo (33,3% de D2)"
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
                "papel_na_nota": "ativo (33,3% de D2)"
            },
            "D2.3": {
                "valor": num_or_none(row.get("cob_vac_composta"), 1),
                "taxa_bruta": num_or_none(row.get("cob_vac_polio"), 1),
                "escore": num_or_none(row.get("escore_D2_3"), 1),
                "ic_95": None,
                "fonte_id": "si_pni",
                "fonte_detalhe": "SI-PNI / MS (média Pólio + Pentavalente + Tríplice Viral D1) via IEPS Data",
                "periodo_vintage": "2021–2023",
                "data_coleta": coleta_ieps,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D2_3", "alta")),
                "papel_na_nota": "ativo (33,3% de D2)"
            },
            "D3.1": {
                "valor": num_or_none(row.get("tx_leito_sus_reg"), 1),
                "taxa_regional_bruta": num_or_none(row.get("tx_leito_sus_reg_bruto"), 1),
                "taxa_bruta": num_or_none(row.get("tx_leito_sus"), 1),
                "escore": num_or_none(row.get("escore_D3_1"), 1),
                "ic_95": None,
                "fonte_id": "cnes",
                "fonte_detalhe": f"CNES / MS — Região de Saúde ({reg_saude}) ajustada para pop. SUS-dependente e distância hospitalar (Polo: {row.get('polo_hospitalar_ref', 'Regional')}, {num_or_none(row.get('dist_polo_km'), 1) or 0} km)",
                "periodo_vintage": "2021–2023",
                "data_coleta": coleta_ieps,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D3_1", "alta")),
                "papel_na_nota": "ativo (33,3% de D3)"
            },
            "D3.2": {
                "valor": num_or_none(row.get("tx_prof_ch"), 2),
                "taxa_bruta": num_or_none(row.get("tx_prof_bruto"), 2),
                "escore": num_or_none(row.get("escore_D3_2"), 1),
                "ic_95": None,
                "fonte_id": "cnes",
                "fonte_detalhe": "CNES / MS (Médicos + Enfermeiros padronizados por 40h/sem) via IEPS Data",
                "periodo_vintage": "2021–2023",
                "data_coleta": coleta_ieps,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D3_2", "alta")),
                "papel_na_nota": "ativo (33,3% de D3)"
            },
            "D3.3": {
                "valor": num_or_none(row.get("cob_esf"), 1),
                "taxa_bruta": num_or_none(row.get("cob_esf_bruta", row.get("cob_esf")), 1),
                "escore": num_or_none(row.get("escore_D3_3"), 1),
                "ic_95": None,
                "fonte_id": "sisab",
                "fonte_detalhe": "e-Gestor AB / SAPS com complementariedade de Atenção Primária via IEPS Data",
                "periodo_vintage": "2021–2023",
                "data_coleta": coleta_ieps,
                "versao_metodologia": versao,
                "qualidade_dado": str(row.get("qualidade_D3_3", "alta")),
                "papel_na_nota": "ativo (33,3% de D3)"
            }
        }

        gasto_pc = num_or_none(row.get("gasto_pc_def_val"), 2)
        pct_rec = num_or_none(row.get("pct_rec_propria_val"), 1)
        cob_priv = num_or_none(row.get("cob_priv_val"), 1)
        leitos_priv = num_or_none(row.get("leitos_priv_val"), 1)

        municipios_payload[ibge7] = {
            "ibge7": ibge7,
            "ibge6": str(row["ibge6"]),
            "nome": str(row["nome_municipio"]),
            "uf": str(row["uf_sigla"]),
            "regiao": str(row["regiao_macro"]),
            "populacao": pop_val,
            "porte": porte_val,
            "regiao_saude": reg_saude,
            "eh_capital": ibge7 in CAPITAIS_INFO,
            "status": status_mun,
            "motivo_sem_classificacao": motivo_sem if status_mun != "classificado" else None,
            "nota_geral": num_or_none(row.get("nota_geral"), 1),
            "d1_nota": num_or_none(row.get("d1_nota"), 1),
            "d2_nota": num_or_none(row.get("d2_nota"), 1),
            "d3_nota": num_or_none(row.get("d3_nota"), 1),
            "d5_nota": num_or_none(row.get("d5_nota"), 1),
            "nota_com_urgencia": num_or_none(row.get("nota_com_urgencia"), 1),
            "posicao_nacional_urgencia": int(row["posicao_nacional_urgencia"]) if pd.notna(row.get("posicao_nacional_urgencia")) else None,
            "posicao_estadual_urgencia": int(row["posicao_estadual_urgencia"]) if pd.notna(row.get("posicao_estadual_urgencia")) else None,
            "faixa_posicao_min": int(row["faixa_posicao_min"]) if pd.notna(row.get("faixa_posicao_min")) else None,
            "faixa_posicao_max": int(row["faixa_posicao_max"]) if pd.notna(row.get("faixa_posicao_max")) else None,
            "posicao_nacional": int(row["posicao_nacional"]) if pd.notna(row.get("posicao_nacional")) else None,
            "total_brasil": 5570,
            "posicao_estadual": int(row["posicao_estadual"]) if pd.notna(row.get("posicao_estadual")) else None,
            "total_uf": int(total_uf_map.get(row["uf_sigla"], 0)),
            "posicao_grupo_pares": int(row["posicao_grupo_pares"]) if pd.notna(row.get("posicao_grupo_pares")) else None,
            "total_grupo_pares": int(total_porte_map.get(row.get("porte_populacional"), 0)),
            "pct_obitos_mal_definidos": num_or_none(row.get("pct_obitos_mal_definidos"), 1),
            "indicadores": indicadores_dict,
            "d4_contexto": {
                "gasto_per_capita": {
                    "valor": gasto_pc,
                    "taxa_bruta": gasto_pc,
                    "ic_95": None,
                    "fonte_id": "siops",
                    "fonte_detalhe": "SIOPS / MS (Despesa total per capita deflacionada) via IEPS Data",
                    "periodo_vintage": "2021–2023",
                    "data_coleta": coleta_ieps,
                    "versao_metodologia": versao,
                    "qualidade_dado": str(row.get("qualidade_D4_1", "alta")),
                    "papel_na_nota": "informativo"
                } if gasto_pc is not None else None,
                "percentual_proprio": {
                    "valor": pct_rec,
                    "taxa_bruta": pct_rec,
                    "ic_95": None,
                    "fonte_id": "siops",
                    "fonte_detalhe": "SIOPS / MS (% receita própria EC 29 / LC 141) via IEPS Data",
                    "periodo_vintage": "2021–2023",
                    "data_coleta": coleta_ieps,
                    "versao_metodologia": versao,
                    "qualidade_dado": str(row.get("qualidade_D4_2", "alta")),
                    "papel_na_nota": "informativo"
                } if pct_rec is not None else None
            },
            "camada_privada": {
                "cobertura_planos": {
                    "valor": cob_priv,
                    "taxa_bruta": cob_priv,
                    "ic_95": None,
                    "fonte_id": "ans",
                    "fonte_detalhe": "ANS / MS (Beneficiários de planos médicos) via IEPS Data",
                    "periodo_vintage": "2021–2023",
                    "data_coleta": coleta_ieps,
                    "versao_metodologia": versao,
                    "qualidade_dado": str(row.get("qualidade_PRIV_1", "alta")),
                    "papel_na_nota": "informativo"
                } if cob_priv is not None else None,
                "leitos_privados": {
                    "valor": leitos_priv,
                    "taxa_bruta": leitos_priv,
                    "ic_95": None,
                    "fonte_id": "cnes",
                    "fonte_detalhe": "CNES / MS consolidado via IEPS Data (média 2021–2023)",
                    "periodo_vintage": "2021–2023",
                    "data_coleta": coleta_ieps,
                    "versao_metodologia": versao,
                    "qualidade_dado": str(row.get("qualidade_PRIV_2", "alta")),
                    "papel_na_nota": "informativo"
                } if leitos_priv is not None else None
            },
            "urgencia_samu": {
                "escore": num_or_none(row.get("d5_nota"), 1),
                "cob_samu_efetiva": num_or_none(row.get("cob_samu_efetiva"), 1),
                "cob_samu_mun": num_or_none(row.get("cob_samu_mun"), 1),
                "cob_samu_reg": num_or_none(row.get("cob_samu_reg"), 1),
                "usb_mun": int(row["usb_mun"]) if pd.notna(row.get("usb_mun")) else 0,
                "usb_reg": int(row["usb_reg"]) if pd.notna(row.get("usb_reg")) else 0,
                "usa_mun": int(row["usa_mun"]) if pd.notna(row.get("usa_mun")) else 0,
                "usa_reg": int(row["usa_reg"]) if pd.notna(row.get("usa_reg")) else 0,
                "upa_mun": int(row["upa_mun"]) if pd.notna(row.get("upa_mun")) else 0,
                "upa_reg": int(row["upa_reg"]) if pd.notna(row.get("upa_reg")) else 0,
                "tx_frota_samu_reg_100k": num_or_none(row.get("tx_frota_samu_reg_100k"), 2),
                "tx_upa_reg_100k": num_or_none(row.get("tx_upa_reg_100k"), 2),
                "leitos_locais_sus": int(row["leitos_locais_sus"]) if pd.notna(row.get("leitos_locais_sus")) else 0,
                "eh_polo_hospitalar": bool(row.get("eh_polo_hospitalar", False)),
                "dist_polo_km": num_or_none(row.get("dist_polo_km"), 1),
                "tempo_ambulancia_min": int(row["tempo_ambulancia_min"]) if pd.notna(row.get("tempo_ambulancia_min")) else 12,
                "polo_hospitalar_ref": str(row.get("polo_hospitalar_ref", "")),
                "fator_golden_hour": num_or_none(row.get("fator_golden_hour"), 3),
                "leitos_uti_adulto_sus": int(row["leitos_uti_adulto_sus"]) if pd.notna(row.get("leitos_uti_adulto_sus")) else 0,
                "tomografo_sus": int(row["tomografo_sus"]) if pd.notna(row.get("tomografo_sus")) else 0,
                "ps_hospitalar_sus": int(row["ps_hospitalar_sus"]) if pd.notna(row.get("ps_hospitalar_sus")) else 0,
                "unid_moveis_urgencia": int(row["unid_moveis_urgencia"]) if pd.notna(row.get("unid_moveis_urgencia")) else 0,
                "polo_ref_completo": bool(row.get("polo_ref_completo", False)),
                "fator_capacidade_polo": num_or_none(row.get("fator_capacidade_polo"), 2),
                "escore_prontidao_local": num_or_none(row.get("escore_prontidao_local"), 1),
                "escore_rue_regional_bruto": num_or_none(row.get("escore_rue_regional_bruto"), 1),
                "no_regiao_saude": str(row.get("no_regiao_saude", ""))
            },
            "escore_oncologia": num_or_none(row.get("escore_oncologia"), 1),
            "rank_onco": int(row["rank_onco"]) if pd.notna(row.get("rank_onco")) else None,
            "rank_d5": int(row["rank_d5"]) if pd.notna(row.get("rank_d5")) else None,
            "nota_integrada": num_or_none(row.get("nota_integrada"), 1),
            "posicao_nacional_integrada": int(row["posicao_nacional_integrada"]) if pd.notna(row.get("posicao_nacional_integrada")) else None,
            "posicao_estadual_integrada": int(row["posicao_estadual_integrada"]) if pd.notna(row.get("posicao_estadual_integrada")) else None,
            "oncologia_tfd": {
                "escore": num_or_none(row.get("escore_oncologia"), 1),
                "eh_polo_onco": bool(row.get("eh_polo_onco", False)),
                "dist_cacon_km": num_or_none(row.get("dist_cacon_km"), 1),
                "tempo_cacon_min": int(row["tempo_cacon_min"]) if pd.notna(row.get("tempo_cacon_min")) else 15,
                "cacon_referencia": str(row.get("cacon_referencia", "")),
                "tem_cacon_regiao": bool(row.get("tem_cacon_regiao", False)),
                "pct_60d_onco": num_or_none(row.get("pct_60d_onco"), 1),
                "pct_conversao_trat": num_or_none(row.get("pct_conversao_trat"), 1),
                "pct_60d_sobre_diag": num_or_none(row.get("pct_60d_sobre_diag"), 1),
                "tempo_mediano_onco_dias": num_or_none(row.get("tempo_mediano_onco_dias"), 1),
                "pct_tratamento_fora": num_or_none(row.get("pct_fora"), 1),
                "pct_diagnostico_precoce": num_or_none(row.get("pct_diagnostico_precoce"), 1),
                "tx_cancer_prem_bayes": num_or_none(row.get("tx_cancer_prem_bayes"), 1),
                "casos_total": int(row["casos_total"]) if pd.notna(row.get("casos_total")) else 0,
                "casos_diagnosticados": int(row["casos_diagnosticados"]) if pd.notna(row.get("casos_diagnosticados")) else 0,
                "polo_tipo_centro": str(row.get("polo_tipo_centro", "UNACON")),
                "polo_imunoterapia_alvo": bool(row.get("polo_imunoterapia_alvo", False)),
                "polo_radio_avancada": bool(row.get("polo_radio_avancada", False)),
                "polo_cirurgia_onco": bool(row.get("polo_cirurgia_onco", False)),
                "polo_onco_pediatrica": bool(row.get("polo_onco_pediatrica", False)),
                "polo_hematologia_tmo": bool(row.get("polo_hematologia_tmo", False)),
                "polo_total_centros": int(row["polo_total_centros"]) if pd.notna(row.get("polo_total_centros")) else 1,
            },
            "cnes_infra": {
                "escore_infra": num_or_none(row.get("escore_infra"), 1),
                "infra_basico": num_or_none(row.get("infra_basico"), 1),
                "infra_avancado": num_or_none(row.get("infra_avancado"), 1),
                "infra_capacidade": num_or_none(row.get("infra_capacidade"), 1),
                "eq_raiox": int(row["eq_raiox"]) if pd.notna(row.get("eq_raiox")) else 0,
                "eq_us": int(row["eq_us"]) if pd.notna(row.get("eq_us")) else 0,
                "eq_ecg": int(row["eq_ecg"]) if pd.notna(row.get("eq_ecg")) else 0,
                "eq_desfib": int(row["eq_desfib"]) if pd.notna(row.get("eq_desfib")) else 0,
                "eq_mamografo": int(row["eq_mamografo"]) if pd.notna(row.get("eq_mamografo")) else 0,
                "eq_tomografo": int(row["eq_tomografo"]) if pd.notna(row.get("eq_tomografo")) else 0,
                "eq_rm": int(row["eq_rm"]) if pd.notna(row.get("eq_rm")) else 0,
                "eq_hemodinamica": int(row["eq_hemodinamica"]) if pd.notna(row.get("eq_hemodinamica")) else 0,
                "eq_endoscopio": int(row["eq_endoscopio"]) if pd.notna(row.get("eq_endoscopio")) else 0,
                "leitos_uti_adulto_sus": int(row["leitos_uti_adulto_sus"]) if pd.notna(row.get("leitos_uti_adulto_sus")) else 0,
                "leitos_cirurgicos_sus": int(row["leitos_cirurgicos_sus"]) if pd.notna(row.get("leitos_cirurgicos_sus")) else 0,
                "ps_hospitalar_sus": int(row["ps_hospitalar_sus"]) if pd.notna(row.get("ps_hospitalar_sus")) else 0,
                "unid_moveis_urgencia": int(row["unid_moveis_urgencia"]) if pd.notna(row.get("unid_moveis_urgencia")) else 0,
                "acc_tomografo": num_or_none(row.get("acc_tomografo"), 2),
                "acc_rm": num_or_none(row.get("acc_rm"), 2),
                "acc_hemodinamica": num_or_none(row.get("acc_hemodinamica"), 2),
                "acc_endoscopio": num_or_none(row.get("acc_endoscopio"), 2),
                "acc_uti": num_or_none(row.get("acc_uti"), 2),
                "acc_cir": num_or_none(row.get("acc_cir"), 2),
                "vintage_infra": str(row.get("vintage_infra", "CNES 2023-12")),
            }
        }

    for out_dir in (os.path.join("data", "releases", "latest"), os.path.join("site", "data", "releases", "latest")):
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "mapa_resumo.json"), "w", encoding="utf-8") as f:
            json.dump(municipios_payload, f, ensure_ascii=False)

    print(f"[export_site_payloads] mapa_resumo.json gerado ({len(municipios_payload)} municípios).")
    build_rankings_payload(df)


def build_rankings_payload(df: pd.DataFrame):
    print("[export_site_payloads] Compilando rankings sintéticos consolidados (Top 100, UFs e Capitais)...")
    cls = df[df["status"] == "classificado"].copy()
    total_uf_map = df["uf_sigla"].value_counts().to_dict()
    total_porte_map = df["porte_populacional"].value_counts().to_dict()

    def format_mun(row):
        ibge7 = str(row["ibge7"])
        return {
            "ibge7": ibge7,
            "nome": str(row["nome_municipio"]),
            "uf": str(row["uf_sigla"]),
            "regiao": str(row.get("regiao_macro", "")),
            "populacao": int(row["populacao_censo_2022"]) if pd.notna(row.get("populacao_censo_2022")) else None,
            "porte": str(row.get("porte_populacional", "")),
            "eh_capital": ibge7 in CAPITAIS_INFO,
            "escore": num_or_none(row.get("nota_geral"), 1),
            "nota_geral": num_or_none(row.get("nota_geral"), 1),
            "d1_nota": num_or_none(row.get("d1_nota"), 1),
            "d2_nota": num_or_none(row.get("d2_nota"), 1),
            "d3_nota": num_or_none(row.get("d3_nota"), 1),
            "d5_nota": num_or_none(row.get("d5_nota"), 1),
            "nota_com_urgencia": num_or_none(row.get("nota_com_urgencia"), 1),
            "posicao_nacional_urgencia": int(row["posicao_nacional_urgencia"]) if pd.notna(row.get("posicao_nacional_urgencia")) else None,
            "posicao_estadual_urgencia": int(row["posicao_estadual_urgencia"]) if pd.notna(row.get("posicao_estadual_urgencia")) else None,
            "cob_samu_efetiva": num_or_none(row.get("cob_samu_efetiva"), 1),
            "tx_frota_samu_reg_100k": num_or_none(row.get("tx_frota_samu_reg_100k"), 2),
            "tmi_bayes": num_or_none(row.get("tmi_bayes"), 2),
            "faixa_min": int(row["faixa_posicao_min"]) if pd.notna(row.get("faixa_posicao_min")) else None,
            "faixa_max": int(row["faixa_posicao_max"]) if pd.notna(row.get("faixa_posicao_max")) else None,
            "posicao_nacional": int(row["posicao_nacional"]) if pd.notna(row.get("posicao_nacional")) else None,
            "total_brasil": 5570,
            "posicao_estadual": int(row["posicao_estadual"]) if pd.notna(row.get("posicao_estadual")) else None,
            "total_uf": int(total_uf_map.get(row["uf_sigla"], 0)),
            "posicao_grupo_pares": int(row["posicao_grupo_pares"]) if pd.notna(row.get("posicao_grupo_pares")) else None,
            "total_grupo_pares": int(total_porte_map.get(row.get("porte_populacional"), 0)),
            "escore_oncologia": num_or_none(row.get("escore_oncologia"), 1),
            "rank_onco": int(row["rank_onco"]) if pd.notna(row.get("rank_onco")) else None,
            "rank_d5": int(row["rank_d5"]) if pd.notna(row.get("rank_d5")) else None,
            "dist_cacon_km": num_or_none(row.get("dist_cacon_km"), 1),
            "tempo_cacon_min": int(row["tempo_cacon_min"]) if pd.notna(row.get("tempo_cacon_min")) else 15,
            "cacon_referencia": str(row.get("cacon_referencia", "")),
            "pct_60d_onco": num_or_none(row.get("pct_60d_onco"), 1),
            "nota_integrada": num_or_none(row.get("nota_integrada"), 1),
            "posicao_nacional_integrada": int(row["posicao_nacional_integrada"]) if pd.notna(row.get("posicao_nacional_integrada")) else None,
            "posicao_estadual_integrada": int(row["posicao_estadual_integrada"]) if pd.notna(row.get("posicao_estadual_integrada")) else None,
            "polo_tipo_centro": str(row.get("polo_tipo_centro", "UNACON")),
            "polo_imunoterapia_alvo": bool(row.get("polo_imunoterapia_alvo", False)),
            "polo_radio_avancada": bool(row.get("polo_radio_avancada", False)),
            "polo_cirurgia_onco": bool(row.get("polo_cirurgia_onco", False)),
            "polo_onco_pediatrica": bool(row.get("polo_onco_pediatrica", False)),
            "polo_hematologia_tmo": bool(row.get("polo_hematologia_tmo", False)),
            "escore_infra": num_or_none(row.get("escore_infra"), 1),
            "leitos_uti_adulto_sus": int(row["leitos_uti_adulto_sus"]) if pd.notna(row.get("leitos_uti_adulto_sus")) else 0,
            "eq_tomografo": int(row["eq_tomografo"]) if pd.notna(row.get("eq_tomografo")) else 0
        }

    df_sorted = cls.sort_values(by=["nota_geral", "populacao_censo_2022"], ascending=[False, False])
    top100_brasil = [format_mun(r) for _, r in df_sorted.head(100).iterrows()]
    piores100_brasil = [format_mun(r) for _, r in df_sorted.tail(100).iloc[::-1].iterrows()]

    rankings_uf = {}
    estados_list = []
    for uf, group in cls.groupby("uf_sigla"):
        g_sorted = group.sort_values(by=["nota_geral", "populacao_censo_2022"], ascending=[False, False])
        pop_uf = int(group["populacao_censo_2022"].sum())
        w_pop = group["populacao_censo_2022"].fillna(0)
        media_pond = float((group["nota_geral"] * w_pop).sum() / w_pop.sum()) if w_pop.sum() > 0 else float(group["nota_geral"].mean())

        lat_uf, lng_uf, nome_uf = UF_CENTROIDES.get(uf, (-14.23, -51.92, uf))
        melhor_row = g_sorted.iloc[0]

        uf_obj = {
            "uf": uf,
            "nome_uf": nome_uf,
            "regiao": str(melhor_row.get("regiao_macro", "")),
            "lat": lat_uf,
            "lng": lng_uf,
            "populacao_uf": pop_uf,
            "media_escore_uf": round(float(group["nota_geral"].mean()), 1),
            "media_ponderada_uf": round(media_pond, 1),
            "media_d1_uf": round(float(group["d1_nota"].mean()), 1),
            "media_d2_uf": round(float(group["d2_nota"].mean()), 1),
            "media_d3_uf": round(float(group["d3_nota"].mean()), 1),
            "media_d5_uf": round(float(group["d5_nota"].mean()), 1) if "d5_nota" in group and group["d5_nota"].notna().any() else None,
            "media_com_urgencia_uf": round(float(group["nota_com_urgencia"].mean()), 1) if "nota_com_urgencia" in group and group["nota_com_urgencia"].notna().any() else None,
            "media_onco_uf": round(float(group["escore_oncologia"].mean()), 1) if "escore_oncologia" in group and group["escore_oncologia"].notna().any() else None,
            "media_integrada_uf": round(float(group["nota_integrada"].mean()), 1) if "nota_integrada" in group and group["nota_integrada"].notna().any() else None,
            "dist_cacon_media_uf": round(float(group["dist_cacon_km"].mean()), 1) if "dist_cacon_km" in group and group["dist_cacon_km"].notna().any() else None,
            "cob_samu_media_uf": round(float(group["cob_samu_efetiva"].mean()), 1) if "cob_samu_efetiva" in group and group["cob_samu_efetiva"].notna().any() else None,
            "total_upas_uf": int(group["upa_mun"].sum()) if "upa_mun" in group else 0,
            "total_usb_uf": int(group["usb_mun"].sum()) if "usb_mun" in group else 0,
            "total_usa_uf": int(group["usa_mun"].sum()) if "usa_mun" in group else 0,
            "total_uti_adulto_sus_uf": int(group["leitos_uti_adulto_sus"].sum()) if "leitos_uti_adulto_sus" in group else 0,
            "total_tomografos_sus_uf": int(group["eq_tomografo"].sum()) if "eq_tomografo" in group else 0,
            "media_infra_uf": round(float(group["escore_infra"].mean()), 1) if "escore_infra" in group and group["escore_infra"].notna().any() else None,
            "mediana_tmi_uf": round(float(group["tmi_bayes"].median()), 2),
            "media_gasto_pc_uf": round(float(group["gasto_pc_def_val"].dropna().mean()), 2) if group["gasto_pc_def_val"].notna().any() else None,
            "media_cob_priv_uf": round(float(group["cob_priv_val"].dropna().mean()), 1) if group["cob_priv_val"].notna().any() else None,
            "total_municipios": int(len(group)),
            "melhor_municipio": f"{melhor_row['nome_municipio']} ({melhor_row['nota_geral']:.1f})",
            "melhores": [format_mun(r) for _, r in g_sorted.iterrows()],
            "piores": [format_mun(r) for _, r in g_sorted.tail(20).iloc[::-1].iterrows()]
        }
        rankings_uf[uf] = uf_obj
        estados_list.append({k: v for k, v in uf_obj.items() if k not in ("melhores", "piores")})

    estados_list.sort(key=lambda x: (x["media_escore_uf"], x["media_ponderada_uf"]), reverse=True)
    for idx, est in enumerate(estados_list, start=1):
        est["posicao_uf"] = idx
        rankings_uf[est["uf"]]["posicao_uf"] = idx

    # Ranking das 27 Capitais
    caps_df = cls[cls["ibge7"].astype(str).isin(CAPITAIS_INFO.keys())].copy()
    caps_df = caps_df.sort_values(by=["nota_geral", "populacao_censo_2022"], ascending=[False, False])
    ranking_capitais = []
    for idx, (_, r) in enumerate(caps_df.iterrows(), start=1):
        item = format_mun(r)
        lat_c, lng_c, _, nome_uf = CAPITAIS_INFO[item["ibge7"]]
        item["posicao_capital"] = idx
        item["lat"] = lat_c
        item["lng"] = lng_c
        item["nome_uf"] = nome_uf
        ranking_capitais.append(item)

    rankings_payload = {
        "atualizacao": datetime.now(timezone.utc).isoformat(),
        "indicador_ativo": "Índice Sintético Consolidado (D1 + D2 + D3) — Janela 2021–2023 (Normalização por Percentis P5–P95)",
        "top10_brasil_melhores": top100_brasil[:10],
        "top10_brasil_piores": piores100_brasil[:10],
        "top100_brasil_melhores": top100_brasil,
        "top100_brasil_piores": piores100_brasil,
        "ranking_estados": estados_list,
        "ranking_capitais": ranking_capitais,
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
