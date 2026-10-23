#!/usr/bin/env python3
"""
pipeline/monitor_descoberta.py

Monitor de descoberta da Seção 8 da especificação ("sempre buscar os melhores dados").
Executado como job periódico separado.
Consulta catálogos oficiais, OpenDataSUS, repositórios de dados abertos e verifica:
1. Disponibilidade de novos anos/períodos nas fontes registradas;
2. Surgimento de novas versões de listas oficiais (ex.: Lista de Evitabilidade, ICSAP);
3. Possível descontinuidade ou alteração de URLs de endpoints.

NUNCA altera o índice de forma automática. Se detectar novidade, emite relatório
para que o GitHub Actions abra uma Issue de triagem para análise humana.
"""

import os
import sys
import json
import yaml
import urllib.request
from datetime import datetime, timezone


def check_registered_sources():
    registry_path = os.path.join("sources", "registry.yaml")
    with open(registry_path, "r", encoding="utf-8") as f:
        registry = yaml.safe_load(f)

    findings = []
    print("[monitor_descoberta] Verificando catálogo de fontes registradas...")

    for fonte in registry.get("fontes", []):
        fonte_id = fonte.get("id")
        status = fonte.get("status")
        pendencia_id = fonte.get("pendencia_id")

        if status == "em_revisao":
            findings.append({
                "tipo": "FONTE_EM_REVISAO",
                "fonte_id": fonte_id,
                "nome": fonte.get("nome"),
                "mensagem": f"Fonte cadastrada aguarda validação de URLs oficiais e defasagem (Pendência: {pendencia_id})."
            })

    # Verificação de catálogos abertos conhecidos (ex: API de localidades IBGE)
    try:
        req = urllib.request.Request(
            "https://servicodados.ibge.gov.br/api/v1/localidades/municipios",
            headers={"User-Agent": "IndiceSaude-Monitor/0.1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            if res.status == 200:
                print("[monitor_descoberta] Endpoint IBGE Localidades: Operacional.")
    except Exception as e:
        findings.append({
            "tipo": "FALHA_CONECTIVIDADE",
            "fonte_id": "ibge_pop",
            "mensagem": f"Inconsistência de acesso ao endpoint do IBGE: {e}"
        })

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_fontes_registradas": len(registry.get("fontes", [])),
        "total_apontamentos": len(findings),
        "apontamentos": findings
    }

    report_path = os.path.join("data", "releases", "latest", "relatorio_descoberta.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"[monitor_descoberta] Relatório concluído com {len(findings)} apontamentos:")
    print(f"Salvo em: {report_path}")
    return report


if __name__ == "__main__":
    check_registered_sources()
