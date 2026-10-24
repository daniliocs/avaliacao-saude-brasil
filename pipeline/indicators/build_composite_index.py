#!/usr/bin/env python3
"""
pipeline/indicators/build_composite_index.py

Índice de Saúde Municipal — consolidação (v0.4.0).

Entradas:
  data/processed/indicadores_sim_sinasc.parquet   (D1.1, D1.2, D2.2 — microdados primários DATASUS)
  data/raw/ieps/ieps_{ano}.csv                    (D2.3, D3.1, D3.2, D3.3, PRIV.2 — via IEPS Data)
  config/limites_referencia.yaml, config/pesos.yaml, config/janelas.yaml, config/qualidade.yaml

Regras:
  * NENHUMA imputação. Dado ausente => componente ausente (NaN).
  * Dimensão calculada se houver componentes mínimos (pesos.yaml: min_componentes_por_dimensao);
    Nota Geral exige as TRÊS dimensões. Caso contrário status = sem_classificacao + motivo.
  * Normalização relativa por percentis (limites_referencia.yaml), CONGELADA por versão em
    config/limites_calculados.json.
  * Faixa de posição plausível = min/max do ranking sob 3 esquemas de pesos x 3 pares de percentis.
  * D4 e Camada Privada ficam FORA da nota (DEC-001).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from pipeline.indicators.estatistica import limites_percentis, normalizar  # noqa: E402

DIM_PATH = os.path.join("data", "processed", "dim_municipio.parquet")
SIM_PATH = os.path.join("data", "processed", "indicadores_sim_sinasc.parquet")
SERIE_PATH = os.path.join("data", "processed", "serie_anual_sim_sinasc.parquet")
IEPS_DIR = os.path.join("data", "raw", "ieps")
LIMITES_CFG = os.path.join("config", "limites_referencia.yaml")
PESOS_CFG = os.path.join("config", "pesos.yaml")
JANELAS_CFG = os.path.join("config", "janelas.yaml")
QUALIDADE_CFG = os.path.join("config", "qualidade.yaml")
VERSAO_TXT = os.path.join("config", "metodologia_versao.txt")
LIMITES_CONGELADOS = os.path.join("config", "limites_calculados.json")

OUT_PARQUET = os.path.join("data", "processed", "indice_saude_municipal.parquet")
OUT_CSV = os.path.join("data", "processed", "indice_saude_municipal.csv")
OUT_INFO = os.path.join("data", "processed", "build_info.json")
SITE_PROCESSED = os.path.join("site", "data", "processed")

# Mapeamento EXPLÍCITO das colunas do IEPS (padrão regex único) -> nome interno.
IEPS_COLUNAS = {
    "cob_esf": r"^Cobertura ESF",
    "cob_vac_polio": r"^Cob\. Vacinal Poliomielite",
    "tx_leito_sus": r"^Leitos SUS",
    "tx_med": r"^M.dicos",
    "tx_leito_nsus": r"^Leitos N.o-SUS",
}
IND_PARA_IEPS = {"D2.3": "cob_vac_polio", "D3.1": "tx_leito_sus", "D3.2": "tx_med", "D3.3": "cob_esf", "PRIV.2": "tx_leito_nsus"}


def carregar_yaml(caminho: str) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


def versao_metodologia() -> str:
    with open(VERSAO_TXT, encoding="utf-8-sig") as f:
        return f.read().strip()


def ler_csv_codificacao_robusta(caminho: str) -> pd.DataFrame:
    """Lê CSV tentando UTF-8 estrito e, se falhar, Latin-1 (a API do IEPS varia por ano)."""
    with open(caminho, "rb") as f:
        blob = f.read()
    try:
        texto = blob.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = blob.decode("latin1")
    import io
    return pd.read_csv(io.StringIO(texto))


def ler_ieps_ano(ano: int) -> pd.DataFrame:
    caminho = os.path.join(IEPS_DIR, f"ieps_{ano}.csv")
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"{caminho} ausente. Execute pipeline/extract/ieps_series.py {ano}.")
    raw = ler_csv_codificacao_robusta(caminho)
    ren = {}
    for interno, padrao in IEPS_COLUNAS.items():
        achadas = [c for c in raw.columns if pd.Series([c]).str.contains(padrao, regex=True).iloc[0]]
        if len(achadas) != 1:
            raise ValueError(f"IEPS {ano}: coluna '{interno}' ({padrao}) encontrada {len(achadas)}x: {achadas}")
        ren[achadas[0]] = interno
    cod = [c for c in raw.columns if c.startswith("C") and "IBGE" in c]
    if len(cod) != 1:
        raise ValueError(f"IEPS {ano}: coluna de código IBGE ambígua: {cod}")
    out = raw[[cod[0]] + list(ren)].rename(columns={cod[0]: "ibge6", **ren})
    out["ibge6"] = out["ibge6"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    out["ano"] = ano
    return out


def agregar_ieps(janelas: dict) -> tuple[pd.DataFrame, dict]:
    """Média da janela por indicador, exigindo min_anos_validos (sem imputação)."""
    anos = sorted({a for k in IND_PARA_IEPS for a in janelas[k]["anos"]})
    longo = pd.concat([ler_ieps_ano(a) for a in anos], ignore_index=True)
    saida = pd.DataFrame({"ibge6": sorted(longo["ibge6"].unique())}).set_index("ibge6")
    meta = {}
    for ind, col in IND_PARA_IEPS.items():
        j = janelas[ind]
        sub = longo[longo["ano"].isin(j["anos"])]
        g = sub.groupby("ibge6")[col]
        n_validos = g.count()
        media = g.mean()
        media[n_validos < j.get("min_anos_validos", 1)] = np.nan
        saida[col] = media
        saida[f"{col}_n_anos"] = n_validos.reindex(saida.index).fillna(0).astype(int)
        meta[ind] = {"anos": j["anos"], "min_anos_validos": j.get("min_anos_validos", 1)}
    return saida.reset_index(), meta


def obter_limites(df: pd.DataFrame, cfg_lim: dict, versao: str) -> dict:
    """Limites congelados por versão: lê config/limites_calculados.json ou calcula e grava."""
    if os.path.exists(LIMITES_CONGELADOS):
        with open(LIMITES_CONGELADOS, encoding="utf-8") as f:
            conj = json.load(f)
        if conj.get("versao") == versao:
            return conj["limites"]
        print(f"[composite] Limites congelados são da versão {conj.get('versao')} != {versao}: recalculando (nova versão).")
    p_inf, p_sup = cfg_lim["percentil_inferior"], cfg_lim["percentil_superior"]
    limites = {}
    for ind, d in cfg_lim["indicadores"].items():
        pior, melhor = limites_percentis(df[d["coluna"]], d["sentido"], p_inf, p_sup)
        limites[ind] = {"pior": pior, "melhor": melhor, "coluna": d["coluna"], "sentido": d["sentido"],
                        "percentis": [p_inf, p_sup], "n_municipios_base": int(df[d["coluna"]].notna().sum())}
    with open(LIMITES_CONGELADOS, "w", encoding="utf-8") as f:
        json.dump({"versao": versao, "metodo": "percentis", "gerado_em": date.today().isoformat(), "limites": limites},
                  f, indent=2, ensure_ascii=False)
    print(f"[composite] Limites por percentis gravados em {LIMITES_CONGELADOS}")
    return limites


def escores_componentes(df: pd.DataFrame, limites: dict) -> pd.DataFrame:
    for ind, lim in limites.items():
        chave = ind.replace(".", "_")
        df[f"escore_{chave}"] = normalizar(df[lim["coluna"]], lim["pior"], lim["melhor"]).round(2)
    return df


def nota_dimensoes(df: pd.DataFrame, cfg_lim: dict, pesos: dict) -> pd.DataFrame:
    pi = pesos["esquemas"]["pesos_iguais"]["indicadores"]
    # Somente componentes COM PESO entram na nota (e contam para o mínimo); os de peso 0 são informativos.
    ativos = {d: [i for i, v in cfg_lim["indicadores"].items() if v["dimensao"] == d and pi.get(i, 0) > 0] for d in ("D1", "D2", "D3")}
    minimos = pesos["min_componentes_por_dimensao"]
    for dim, inds in ativos.items():
        cols = [f"escore_{i.replace('.', '_')}" for i in inds]
        w = np.array([pi[i] for i in inds], dtype=float)
        mat = df[cols].to_numpy(dtype=float)
        valido = ~np.isnan(mat)
        wsum = (valido * w).sum(axis=1)
        num = np.nansum(mat * w, axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            nota = np.where(wsum > 0, num / wsum, np.nan)
        nota = np.where(valido.sum(axis=1) >= minimos[dim], nota, np.nan)
        df[f"{dim.lower()}_nota"] = np.round(nota, 1)
        df[f"{dim.lower()}_n_componentes"] = valido.sum(axis=1)
        df[f"{dim.lower()}_componentes_ausentes"] = [
            ",".join(i for i, ok in zip(inds, linha) if not ok) for linha in valido
        ]
    return df


def combinar(df: pd.DataFrame, pesos_dim: dict) -> pd.Series:
    d = df[["d1_nota", "d2_nota", "d3_nota"]].to_numpy(dtype=float)
    w = np.array([pesos_dim["D1"], pesos_dim["D2"], pesos_dim["D3"]], dtype=float)
    ok = ~np.isnan(d).any(axis=1)
    return pd.Series(np.where(ok, d @ w / w.sum(), np.nan), index=df.index)


def rank_min(s: pd.Series) -> pd.Series:
    return s.rank(ascending=False, method="min")


def sensibilidade(df: pd.DataFrame, cfg_lim: dict, pesos: dict) -> tuple[pd.Series, pd.Series]:
    """Min/max do ranking nacional sob (3 esquemas de pesos) x (3 pares de percentis)."""
    esquemas = [pesos["esquemas"][k]["dimensoes"] for k in ("pesos_iguais", "foco_resultados", "foco_atencao_primaria")]
    pi = pesos["esquemas"]["pesos_iguais"]["indicadores"]
    ativos = {i: v for i, v in cfg_lim["indicadores"].items() if pi.get(i, 0) > 0}
    minimos = pesos["min_componentes_por_dimensao"]
    ranks = []
    for p_inf, p_sup in cfg_lim["sensibilidade_percentis"]:
        tmp = pd.DataFrame(index=df.index)
        for ind, d in ativos.items():
            pior, melhor = limites_percentis(df[d["coluna"]], d["sentido"], p_inf, p_sup)
            tmp[ind] = normalizar(df[d["coluna"]], pior, melhor)
        dims = {}
        for dim in ("D1", "D2", "D3"):
            inds = [i for i, v in ativos.items() if v["dimensao"] == dim]
            w = np.array([pi[i] for i in inds], dtype=float)
            mat = tmp[inds].to_numpy(dtype=float)
            val = ~np.isnan(mat)
            with np.errstate(invalid="ignore", divide="ignore"):
                n = np.where((val * w).sum(axis=1) > 0, np.nansum(mat * w, axis=1) / (val * w).sum(axis=1), np.nan)
            dims[dim] = np.where(val.sum(axis=1) >= minimos[dim], n, np.nan)
        dd = pd.DataFrame({"d1_nota": dims["D1"], "d2_nota": dims["D2"], "d3_nota": dims["D3"]}, index=df.index)
        for esq in esquemas:
            ranks.append(rank_min(combinar(dd, esq)))
    r = pd.concat(ranks, axis=1)
    return r.min(axis=1), r.max(axis=1)


def selo_qualidade(df: pd.DataFrame, cfg_q: dict) -> pd.DataFrame:
    q = cfg_q["precisao"]

    def por_eventos(n, lim):
        return np.where(n >= lim["alta_min"], "alta", np.where(n >= lim["media_min"], "media", "baixa"))

    df["qualidade_D1_1"] = por_eventos(df["d1_1_obitos"], q["eventos_taxa"]["D1.1"])
    df["qualidade_D1_2"] = por_eventos(df["d1_2_obitos"], q["eventos_taxa"]["D1.2"])
    p = q["proporcao_base"]["D2.2"]
    s = np.where(df["d2_2_validas"] >= p["alta_min"], "alta", np.where(df["d2_2_validas"] >= p["media_min"], "media", "baixa"))
    df["qualidade_D2_2"] = np.where(df["pre7_pct_ignorado"] > q["ignorado_max_pct"], "alerta", s)
    for ind, col in IND_PARA_IEPS.items():
        n = df[f"{col}_n_anos"]
        df[f"qualidade_{ind.replace('.', '_')}"] = np.where(n >= q["ieps_anos_alta"], "alta", "media")
    return df


def construir() -> pd.DataFrame:
    print("[composite] Carregando insumos...")
    versao = versao_metodologia()
    cfg_lim = carregar_yaml(LIMITES_CFG)
    pesos = carregar_yaml(PESOS_CFG)
    janelas = carregar_yaml(JANELAS_CFG)["janelas"]
    cfg_q = carregar_yaml(QUALIDADE_CFG)

    for p in (DIM_PATH, SIM_PATH):
        if not os.path.exists(p):
            print(f"[composite:ERRO] {p} não encontrado.")
            sys.exit(1)

    dim = pd.read_parquet(DIM_PATH)
    sim = pd.read_parquet(SIM_PATH).drop(columns=["ibge7", "uf_sigla"])
    ieps, meta_ieps = agregar_ieps(janelas)

    df = dim.merge(sim, on="ibge6", how="left").merge(ieps, on="ibge6", how="left")
    assert len(df) == 5570 and df["ibge7"].is_unique, "Cardinalidade/unicidade violada após junções"

    # Mal definidos SIM na janela D1.1 (informativo, qualidade do registro de óbitos)
    serie = pd.read_parquet(SERIE_PATH)
    jan = serie[serie["ano"].isin(janelas["D1.1"]["anos"])].groupby("ibge6")[["obitos_total", "obitos_mal_definidos"]].sum()
    jan["pct_obitos_mal_definidos"] = (jan["obitos_mal_definidos"] / jan["obitos_total"].replace(0, np.nan) * 100).round(2)
    df = df.merge(jan[["pct_obitos_mal_definidos"]], left_on="ibge6", right_index=True, how="left")

    limites = obter_limites(df, cfg_lim, versao)
    df = escores_componentes(df, limites)
    df = nota_dimensoes(df, cfg_lim, pesos)
    df = selo_qualidade(df, cfg_q)

    df["nota_geral"] = combinar(df, pesos["esquemas"]["pesos_iguais"]["dimensoes"]).round(1)
    df["status"] = np.where(df["nota_geral"].notna(), "classificado", "sem_classificacao")
    motivos = []
    for _, r in df.iterrows():
        m = [f"{d.upper()} incompleta (ausentes: {r[f'{d}_componentes_ausentes'] or 'n/d'})" for d in ("d1", "d2", "d3") if pd.isna(r[f"{d}_nota"])]
        motivos.append("; ".join(m))
    df["motivo_sem_classificacao"] = motivos

    cls = df["status"] == "classificado"
    n_cls = int(cls.sum())

    df["posicao_nacional"] = np.nan
    df.loc[cls, "posicao_nacional"] = rank_min(df.loc[cls, "nota_geral"])
    df["posicao_estadual"] = np.nan
    df.loc[cls, "posicao_estadual"] = df[cls].groupby("uf_sigla")["nota_geral"].rank(ascending=False, method="min")
    df["posicao_grupo_pares"] = np.nan
    df.loc[cls, "posicao_grupo_pares"] = df[cls].groupby("porte_populacional")["nota_geral"].rank(ascending=False, method="min")
    for d in ("d1", "d2", "d3"):
        df[f"rank_{d}"] = np.nan
        df.loc[df[f"{d}_nota"].notna(), f"rank_{d}"] = rank_min(df.loc[df[f"{d}_nota"].notna(), f"{d}_nota"])

    fmin, fmax = sensibilidade(df[cls], cfg_lim, pesos)
    df["faixa_posicao_min"] = np.nan
    df["faixa_posicao_max"] = np.nan
    df.loc[cls, "faixa_posicao_min"] = np.minimum(fmin, df.loc[cls, "posicao_nacional"])
    df.loc[cls, "faixa_posicao_max"] = np.maximum(fmax, df.loc[cls, "posicao_nacional"])

    for c in ("posicao_nacional", "posicao_estadual", "posicao_grupo_pares", "faixa_posicao_min", "faixa_posicao_max",
              "rank_d1", "rank_d2", "rank_d3"):
        df[c] = df[c].astype("Int64")

    # Camada privada (fora da nota)
    df["leitos_priv_val"] = df["tx_leito_nsus"].round(1)

    # Metadados de build / proveniência
    def manifesto(caminho):
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8") as f:
                return json.load(f)
        return {}

    man_ds = manifesto(os.path.join("data", "raw", "datasus", "manifest_extracao.json"))
    man_ieps = manifesto(os.path.join(IEPS_DIR, "manifest_ieps.json"))
    coleta_ds = max((v.get("data_coleta", "") for v in man_ds.values()), default="") or None
    coleta_ieps = max((v.get("data_coleta", "") for v in man_ieps.values()), default="") or None

    info = {
        "versao_metodologia": versao,
        "gerado_em": date.today().isoformat(),
        "n_municipios": int(len(df)),
        "n_classificados": n_cls,
        "n_sem_classificacao": int(len(df) - n_cls),
        "janelas": {k: v["anos"] for k, v in janelas.items()},
        "fontes": {
            "sim_sinasc": {"data_coleta": coleta_ds, "origem": "ftp.datasus.gov.br (microdados por residência)"},
            "ieps": {"data_coleta": coleta_ieps, "origem": "iepsdata.org.br (intermediário)", "indicadores": meta_ieps},
        },
        "limites": limites,
        "medias": {c: float(df[c].mean()) for c in ("nota_geral", "d1_nota", "d2_nota", "d3_nota")},
    }
    os.makedirs(os.path.dirname(OUT_PARQUET), exist_ok=True)
    with open(OUT_INFO, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)

    df.to_parquet(OUT_PARQUET, index=False)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")
    os.makedirs(SITE_PROCESSED, exist_ok=True)
    for nome in ("indice_saude_municipal.parquet", "indice_saude_municipal.csv"):
        src = os.path.join("data", "processed", nome)
        with open(src, "rb") as fi, open(os.path.join(SITE_PROCESSED, nome), "wb") as fo:
            fo.write(fi.read())

    print(f"[composite] {n_cls} classificados / {len(df) - n_cls} sem classificação.")
    print(f"[composite] Médias: Nota {info['medias']['nota_geral']:.1f} | D1 {info['medias']['d1_nota']:.1f} | "
          f"D2 {info['medias']['d2_nota']:.1f} | D3 {info['medias']['d3_nota']:.1f}")
    return df


if __name__ == "__main__":
    construir()
