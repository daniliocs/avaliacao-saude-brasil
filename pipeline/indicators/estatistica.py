"""
pipeline/indicators/estatistica.py

Funções estatísticas puras e testáveis, compartilhadas pelos indicadores:
  - IC exato de Poisson (taxa por fator)         -> ic_poisson
  - IC de Wilson (proporção, em %)               -> ic_wilson
  - Suavização Bayesiana Empírica (Marshall 1991, shrinkage para a taxa do grupo) -> suavizar_eb
  - Normalização 0–100 com limites explícitos    -> normalizar
  - Limites por percentis (relativos)            -> limites_percentis
Nenhuma função aqui contém limite, meta ou parâmetro de saúde embutido.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import chi2, norm


def ic_poisson(k, n, alpha: float = 0.05, fator: float = 1000.0):
    """IC exato de Poisson para a taxa k/n*fator. Aceita escalares ou arrays; n<=0 -> NaN."""
    k = np.asarray(k, dtype=float)
    n = np.asarray(n, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        low = np.where(k > 0, chi2.ppf(alpha / 2, 2 * np.where(k > 0, k, 1)) / (2 * n) * fator, 0.0)
        high = chi2.ppf(1 - alpha / 2, 2 * (k + 1)) / (2 * n) * fator
    low = np.where(n > 0, low, np.nan)
    high = np.where(n > 0, high, np.nan)
    return low, high


def ic_wilson(sucessos, total, alpha: float = 0.05):
    """IC de Wilson (em %) para proporção sucessos/total. total<=0 -> NaN."""
    s = np.asarray(sucessos, dtype=float)
    n = np.asarray(total, dtype=float)
    z = norm.ppf(1 - alpha / 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = s / n
        centro = (p + z**2 / (2 * n)) / (1 + z**2 / n)
        meia = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    low = np.where(n > 0, (centro - meia) * 100, np.nan)
    high = np.where(n > 0, (centro + meia) * 100, np.nan)
    return np.clip(low, 0, 100), np.clip(high, 0, 100)


def suavizar_eb(eventos: pd.Series, base: pd.Series, grupo: pd.Series, fator: float = 1000.0) -> pd.Series:
    """
    Estimador empírico de Bayes (Marshall 1991) com encolhimento para a taxa do grupo (ex.: UF).
    Retorna taxa suavizada por `fator`. Municípios com base=0 recebem a taxa do grupo.
    A relação esperada: pequenos denominadores -> mais encolhimento; grandes -> ≈ taxa bruta.
    """
    df = pd.DataFrame({"e": eventos.astype(float), "n": base.astype(float), "g": grupo})
    out = pd.Series(np.nan, index=df.index, dtype=float)
    for _, sub in df.groupby("g"):
        tot_n = sub["n"].sum()
        if tot_n <= 0:
            continue
        mu = sub["e"].sum() / tot_n
        n_bar = sub["n"].mean()
        taxa = sub["e"] / sub["n"].replace(0, np.nan)
        var_amostral = (sub["n"] * (taxa - mu) ** 2).fillna(0).sum() / tot_n
        s2 = max(0.0, var_amostral - (mu / n_bar if n_bar > 0 else 0.0))
        denom = s2 + mu / sub["n"].replace(0, np.nan)
        w = (s2 / denom).fillna(0.0).clip(0.0, 1.0)
        out.loc[sub.index] = (w * taxa.fillna(mu) + (1 - w) * mu) * fator
    return out


def normalizar(serie: pd.Series, pior: float, melhor: float) -> pd.Series:
    """
    Normaliza linearmente para 0–100 entre `pior` (=0) e `melhor` (=100), saturando nos extremos.
    Funciona nos dois sentidos (pior<melhor: maior melhor; pior>melhor: menor melhor).
    NaN permanece NaN (sem imputação).
    """
    if pior == melhor:
        raise ValueError("Limites idênticos: normalização indefinida.")
    score = 100.0 * (serie - pior) / (melhor - pior)
    return score.clip(0.0, 100.0)


def limites_percentis(serie: pd.Series, sentido: str, p_inf: float = 5.0, p_sup: float = 95.0) -> tuple[float, float]:
    """
    Limites (pior, melhor) por percentis da distribuição observada.
    sentido='maior_melhor' -> pior=p_inf, melhor=p_sup ; 'menor_melhor' -> pior=p_sup, melhor=p_inf.
    """
    v = serie.dropna()
    if len(v) < 100:
        raise ValueError("Amostra insuficiente para estimar limites por percentis.")
    lo, hi = np.percentile(v, [p_inf, p_sup])
    if lo == hi:
        raise ValueError("Distribuição degenerada: percentis idênticos.")
    if sentido == "maior_melhor":
        return float(lo), float(hi)
    if sentido == "menor_melhor":
        return float(hi), float(lo)
    raise ValueError(f"Sentido inválido: {sentido}")
