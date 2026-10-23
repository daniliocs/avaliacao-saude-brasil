#!/usr/bin/env python3
"""
pipeline/validate/quality_gates.py

Implementa as travas automáticas de qualidade (Quality Gates) da Seção 8 da especificação.
Princípio: O pipeline pode atualizar dados automaticamente, mas qualquer anomalia
ou quebra de integridade ABORTA o processo com sys.exit(1), mantendo a release anterior intacta.

Travas implementadas:
1. Validação de esquema e integridade municipal (exatamente 5.570 códigos ibge7 e ibge6 válidos).
2. Faixas de valores plausíveis (taxas não negativas, população > 0, proporções entre 0% e 100%).
3. Completude mínima por indicador.
4. Detecção de variação temporal anômala ano a ano (spikes anômalos que exigem revisão).
5. Verificação e registro de hash criptográfico SHA-256 dos insumos para reprodutibilidade.
"""

import os
import sys
import json
import hashlib
import pandas as pd


def compute_file_sha256(filepath: str) -> str:
    """Calcula o hash SHA-256 de um arquivo em disco."""
    if not os.path.exists(filepath):
        return ""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def gate_schema_municipios(df: pd.DataFrame, expected_count: int = 5570) -> bool:
    """Verifica a integridade da dimensão municipal (5.570 municípios únicos)."""
    print("[QualityGate:Schema] Validando integridade territorial e cardinalidade...")

    if "ibge7" not in df.columns or "ibge6" not in df.columns:
        print("[QualityGate:ERRO] Colunas obrigatórias 'ibge7' ou 'ibge6' ausentes.")
        return False

    count = len(df)
    if count != expected_count:
        print(f"[QualityGate:ERRO] Cardinalidade municipal inválida: {count} != {expected_count}")
        return False

    if df["ibge7"].nunique() != expected_count:
        print(f"[QualityGate:ERRO] Há códigos ibge7 duplicados no dataset.")
        return False

    if df["ibge6"].nunique() != expected_count:
        print(f"[QualityGate:ERRO] Há códigos ibge6 duplicados no dataset.")
        return False

    # Validação de códigos críticos
    if "2605459" not in df["ibge7"].values:
        print("[QualityGate:ERRO] Fernando de Noronha (2605459) ausente da base.")
        return False

    if "5300108" not in df["ibge7"].values:
        print("[QualityGate:ERRO] Brasília (5300108) ausente da base.")
        return False

    print(f"[QualityGate:Schema] OK — {count} municípios validados sem inconsistências.")
    return True


def gate_plausible_ranges(df: pd.DataFrame, rate_columns: list, proportion_columns: list, pop_col: str = None) -> bool:
    """Valida se os valores numéricos respeitam as leis da epidemiologia e demografia."""
    print("[QualityGate:Plausibilidade] Checando limites matemáticos e biológicos...")

    # 1. População estritamente positiva
    if pop_col and pop_col in df.columns:
        invalid_pop = df[df[pop_col] <= 0]
        if not invalid_pop.empty:
            print(f"[QualityGate:ERRO] Encontrados {len(invalid_pop)} municípios com população <= 0:")
            print(invalid_pop[["ibge7", pop_col]].head())
            return False

    # 2. Taxas não negativas
    for col in rate_columns:
        if col in df.columns:
            negative = df[df[col] < 0]
            if not negative.empty:
                print(f"[QualityGate:ERRO] Coluna '{col}' contém {len(negative)} valores negativos:")
                print(negative[["ibge7", col]].head())
                return False

    # 3. Proporções entre 0% e 100% (com tolerância para erros de ponto flutuante)
    for col in proportion_columns:
        if col in df.columns:
            out_of_bounds = df[(df[col] < -0.001) | (df[col] > 100.001)]
            if not out_of_bounds.empty:
                print(f"[QualityGate:ERRO] Proporção '{col}' contém {len(out_of_bounds)} valores fora de [0, 100]:")
                print(out_of_bounds[["ibge7", col]].head())
                return False

    print("[QualityGate:Plausibilidade] OK — Todas as faixas numéricas são plausíveis.")
    return True


def gate_completeness(df: pd.DataFrame, required_columns: list, min_completeness_ratio: float = 0.85) -> bool:
    """Verifica se a completude de preenchimento dos indicadores atinge o limiar mínimo aceitável."""
    print(f"[QualityGate:Completude] Verificando preenchimento mínimo ({min_completeness_ratio * 100:.0f}%)...")
    total_rows = len(df)
    for col in required_columns:
        if col not in df.columns:
            print(f"[QualityGate:ERRO] Coluna necessária '{col}' não encontrada no dataset.")
            return False
        valid_count = df[col].notna().sum()
        ratio = valid_count / total_rows
        if ratio < min_completeness_ratio:
            print(f"[QualityGate:ERRO] Completude de '{col}' é insuficiente: {ratio*100:.2f}% < {min_completeness_ratio*100:.0f}%")
            return False

    print("[QualityGate:Completude] OK — Completude dentro dos limiares requeridos.")
    return True


def gate_anomalous_yearly_variation(df_current: pd.DataFrame, df_previous: pd.DataFrame, indicator_cols: list, max_ratio_change: float = 3.0) -> bool:
    """Detecta variações anômalas (ex.: salto triplo em taxas estocásticas) que exigem auditoria humana."""
    print("[QualityGate:VariacaoAnomala] Comparando série temporal ano a ano...")
    if df_previous is None or df_previous.empty:
        print("[QualityGate:VariacaoAnomala] Base anterior inexistente (primeira execução). Trava liberada com aviso.")
        return True

    merged = pd.merge(df_current, df_previous, on="ibge7", suffixes=("_curr", "_prev"))
    for col in indicator_cols:
        curr_col = f"{col}_curr"
        prev_col = f"{col}_prev"
        if curr_col in merged.columns and prev_col in merged.columns:
            # Avalia apenas onde ambos são maiores que zero para evitar divisão por zero
            valid_mask = (merged[curr_col] > 0) & (merged[prev_col] > 0)
            subset = merged[valid_mask]
            ratio = subset[curr_col] / subset[prev_col]
            anomalies = subset[(ratio > max_ratio_change) | (ratio < (1.0 / max_ratio_change))]
            if len(anomalies) > 0.05 * len(subset): # Mais de 5% de anomalias abruptas
                print(f"[QualityGate:ERRO] Coluna '{col}' apresentou {len(anomalies)} saltos temporais anômalos (> {max_ratio_change}x).")
                print("Publicação suspensa para auditoria humana.")
                return False

    print("[QualityGate:VariacaoAnomala] OK — Variação anual dentro dos parâmetros aceitáveis.")
    return True


def gate_reproducibility_hashes(input_files: list, manifest_output_path: str = None) -> dict:
    """Gera e registra os hashes SHA-256 de todos os insumos para reprodutibilidade estrita."""
    print("[QualityGate:Reprodutibilidade] Calculando hashes SHA-256 dos insumos...")
    manifest = {}
    for filepath in input_files:
        if os.path.exists(filepath):
            sha = compute_file_sha256(filepath)
            manifest[filepath] = {
                "sha256": sha,
                "bytes": os.path.getsize(filepath)
            }
            print(f"  {filepath}: {sha[:16]}... ({os.path.getsize(filepath)} bytes)")
        else:
            print(f"[QualityGate:ALERTA] Arquivo de insumo não encontrado: {filepath}")

    if manifest_output_path:
        os.makedirs(os.path.dirname(manifest_output_path), exist_ok=True)
        with open(manifest_output_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"[QualityGate:Reprodutibilidade] Manifesto de proveniência salvo em: {manifest_output_path}")

    return manifest


def run_all_gates(dim_municipio_path: str = "data/processed/dim_municipio.parquet") -> None:
    """Executa a suíte completa de quality gates. Aborta com código 1 em qualquer falha."""
    print("\n=======================================================")
    print(" INICIANDO EXECUÇÃO DAS TRAVAS DE QUALIDADE (SEÇÃO 8)  ")
    print("=======================================================\n")

    if not os.path.exists(dim_municipio_path):
        print(f"[QualityGate:FATAL] Arquivo dimensional não encontrado: {dim_municipio_path}")
        sys.exit(1)

    df_dim = pd.read_parquet(dim_municipio_path)

    # 1. Gate de esquema
    if not gate_schema_municipios(df_dim, expected_count=5570):
        print("[QualityGate:FATAL] Falha no gate de esquema municipal. ABORTANDO.")
        sys.exit(1)

    # 2. Gate de não-nulos em identificadores
    if not gate_completeness(df_dim, ["ibge7", "ibge6", "nome_municipio", "uf_sigla"], min_completeness_ratio=1.0):
        print("[QualityGate:FATAL] Falha de completude nas colunas dimensionais. ABORTANDO.")
        sys.exit(1)

    # 3. Gate de validação do Indicador D1.1 (se gerado)
    d1_parquet = "data/processed/indicador_d1_1.parquet"
    if os.path.exists(d1_parquet):
        print("[QualityGate:Indicadores] Validando indicador D1.1 (Mortalidade Infantil)...")
        df_d1 = pd.read_parquet(d1_parquet)
        if len(df_d1) != 5570:
            print(f"[QualityGate:FATAL] Indicador D1.1 não possui 5.570 municípios: {len(df_d1)}")
            sys.exit(1)
        if not gate_plausible_ranges(df_d1, rate_columns=["tmi_bruta", "tmi_bayes"], proportion_columns=["escore_d1_1"]):
            print("[QualityGate:FATAL] Valores implausíveis encontrados no indicador D1.1. ABORTANDO.")
            sys.exit(1)
        if not gate_completeness(df_d1, ["tmi_bayes", "escore_d1_1", "posicao_nacional"], min_completeness_ratio=1.0):
            print("[QualityGate:FATAL] Completude incompleta no indicador D1.1. ABORTANDO.")
            sys.exit(1)
        print("[QualityGate:Indicadores] OK — Indicador D1.1 validado com 100% de integridade epidemiológica.")

    # 4. Gate de reprodutibilidade e proveniência
    input_artifacts = [
        "config/indicadores.yaml",
        "config/pesos.yaml",
        "config/limites_referencia.yaml",
        "sources/registry.yaml",
        "data/processed/dim_municipio.parquet"
    ]
    if os.path.exists(d1_parquet):
        input_artifacts.append(d1_parquet)

    manifest_path = "data/releases/latest/provenance_manifest.json"
    gate_reproducibility_hashes(input_artifacts, manifest_path)

    print("\n[QualityGate:SUCESSO] Todas as travas foram validadas com sucesso. Publicação liberada.\n")


if __name__ == "__main__":
    run_all_gates()
