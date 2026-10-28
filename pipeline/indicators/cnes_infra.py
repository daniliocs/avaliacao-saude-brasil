"""
pipeline/indicators/cnes_infra.py

Infraestrutura assistencial SUS por município (CNES/DATASUS, competência 2023-12):
- Exames básicos locais: Raio-X, Ultrassom, ECG, Desfibrilador
- Exames avançados (acesso decaído pela distância ao município prestador mais próximo da UF):
  Tomógrafo, Ressonância, Hemodinâmica, Endoscópio digestivo
- Capacidade hospitalar: Leitos de UTI adulto SUS e Leitos cirúrgicos SUS (relativos a referência
  empírica nacional, sem metas inventadas), Pronto-Socorro hospitalar e unidades móveis de urgência (CNES).

Códigos conforme tabelas auxiliares oficiais TAB_CNES (equipam2508.cnv, Esp_leit.CNV, TP_ESTAB.CNV).
Equipamento = TIPEQUIP(2 dígitos) + CODEQUIP(2 dígitos).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from pipeline.indicators.urgencia_samu import carregar_coordenadas_municipios

RAW = os.path.join("data", "raw", "cnes_infra")
COMP = "2312"
K_DIST = 0.01  # f = exp(-0.01 * d_km): 0.74 a 30 km, 0.37 a 100 km, 0.14 a 200 km

EQUIP = {
    "raiox": {"0104", "0105", "0106", "0108", "0120", "0121", "0122", "0123"},
    "us": {"0113", "0114", "0115"},
    "ecg": {"0441"},
    "desfib": {"0556", "0566"},
    "mamografo": {"0102", "0103", "0117", "0119"},
    "tomografo": {"0111", "0126", "0127", "0128", "0129", "0130"},
    "rm": {"0112", "0132", "0133", "0134", "0135"},
    "hemodinamica": {"0110"},
    "endoscopio": {"0333"},
}
UTI_ADULTO = {"61", "74", "75", "76", "85", "86"}
TP_PS_HOSP = {"05", "07", "15", "20", "21"}
TP_MOVEL_URG = {"42", "40"}


def _hav(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _acesso_por_distancia(df: pd.DataFrame, col_qtd: str) -> np.ndarray:
    """1.0 se há prestador local; senão exp(-K*d*1.3) até o prestador mais próximo da mesma UF (fallback: Brasil)."""
    out = np.zeros(len(df))
    lat, lon = df["lat"].to_numpy(float), df["lon"].to_numpy(float)
    tem = (df[col_qtd] > 0).to_numpy()
    for uf, idx in df.groupby("uf_sigla").indices.items():
        prov = np.where(tem[idx])[0]
        base = idx[prov] if len(prov) else np.where(tem)[0]
        if len(base) == 0:
            continue
        for i in idx:
            if tem[i]:
                out[i] = 1.0
            else:
                d = _hav(lat[i], lon[i], lat[base], lon[base]).min() * 1.30
                out[i] = float(np.exp(-K_DIST * d))
    return out


def processar_cnes_infra(
    caminho_dim=os.path.join("data", "processed", "dim_municipio.parquet"),
    caminho_saida=os.path.join("data", "processed", "indicadores_cnes_infra.parquet"),
) -> pd.DataFrame:
    dim = pd.read_parquet(caminho_dim)
    dim["lat"], dim["lon"] = carregar_coordenadas_municipios(dim)
    dim["ibge6"] = dim["ibge6"].astype(str)

    eq = pd.read_parquet(os.path.join(RAW, f"eq_{COMP}.parquet"))
    lt = pd.read_parquet(os.path.join(RAW, f"lt_{COMP}.parquet"))
    st = pd.read_parquet(os.path.join(RAW, f"st_{COMP}.parquet"))

    # Equipamentos em uso pelo SUS
    eq = eq[eq["IND_SUS"] == "1"].copy()
    eq["cod"] = eq["TIPEQUIP"].str.zfill(2) + eq["CODEQUIP"].str.zfill(2)
    eq["q"] = pd.to_numeric(eq["QT_USO"], errors="coerce").fillna(0)
    res = dim[["ibge6"]].copy().set_index("ibge6")
    for nome, cods in EQUIP.items():
        s = eq[eq["cod"].isin(cods)].groupby("CODUFMUN")["q"].sum()
        res[f"eq_{nome}"] = s.reindex(res.index).fillna(0).astype(int)

    # Leitos SUS
    lt["s"] = pd.to_numeric(lt["QT_SUS"], errors="coerce").fillna(0)
    res["leitos_uti_adulto_sus"] = lt[(lt["TP_LEITO"] == "3") & lt["CODLEITO"].isin(UTI_ADULTO)].groupby("CODUFMUN")["s"].sum().reindex(res.index).fillna(0).astype(int)
    res["leitos_cirurgicos_sus"] = lt[lt["TP_LEITO"] == "1"].groupby("CODUFMUN")["s"].sum().reindex(res.index).fillna(0).astype(int)

    # Estabelecimentos
    st["sus"] = st["VINC_SUS"] == "1"
    ps = st[(st["URGEMERG"] == "1") & st["TP_UNID"].isin(TP_PS_HOSP) & st["sus"]]
    res["ps_hospitalar_sus"] = ps.groupby("CODUFMUN").size().reindex(res.index).fillna(0).astype(int)
    mov = st[st["TP_UNID"].isin(TP_MOVEL_URG)]
    res["unid_moveis_urgencia"] = mov.groupby("CODUFMUN").size().reindex(res.index).fillna(0).astype(int)
    res = res.reset_index()

    df = dim.merge(res, on="ibge6", how="left")
    for c in [c for c in df.columns if c.startswith(("eq_", "leitos_", "ps_", "unid_"))]:
        df[c] = df[c].fillna(0).astype(int)
    pop = df["populacao_censo_2022"].replace(0, np.nan)

    # ---- Escores ----
    # Básico (local, 25 pts cada): quem não tem Raio-X/US/ECG/Desfibrilador SUS obriga deslocamento para diagnóstico simples.
    df["infra_basico"] = 25.0 * ((df["eq_raiox"] > 0).astype(int) + (df["eq_us"] > 0) + (df["eq_ecg"] > 0) + (df["eq_desfib"] > 0))

    # Acesso por item = capacidade local relativa à referência empírica (P90 nacional por 100 mil entre
    # municípios que possuem o recurso, nota 100 = nível dos melhores municípios do país). Sem recurso
    # local, vale no máximo 60% do acesso decaído pela distância (deslocar-se para diagnosticar/operar não é equivalente a ter local).
    refs = {}

    def acesso_item(col, k):
        tx = df[col] / pop * 1e5
        ref = 1.5 * float(df[col].sum() / pop.sum() * 1e5)  # 1,5x a taxa nacional agregada por 100 mil hab.
        refs[k] = round(ref, 2)
        dist = _acesso_por_distancia(df, col)
        return np.where(df[col] > 0, np.clip(tx / ref, 0, 1), 0.6 * dist)

    a_tomo = acesso_item("eq_tomografo", "tomografo")
    a_rm = acesso_item("eq_rm", "rm")
    a_hemo = acesso_item("eq_hemodinamica", "hemodinamica")
    a_endo = acesso_item("eq_endoscopio", "endoscopio")
    for k, v in (("tomografo", a_tomo), ("rm", a_rm), ("hemodinamica", a_hemo), ("endoscopio", a_endo)):
        df[f"acc_{k}"] = np.round(v, 3)
    df["infra_avancado"] = 100.0 * (0.35 * a_tomo + 0.25 * a_hemo + 0.20 * a_rm + 0.20 * a_endo)

    r_uti = acesso_item("leitos_uti_adulto_sus", "uti")
    r_cir = acesso_item("leitos_cirurgicos_sus", "cir")
    df["acc_uti"] = np.round(r_uti, 3)
    df["acc_cir"] = np.round(r_cir, 3)
    # Pronto-socorro hospitalar conta integralmente só se o município também tem UTI local (retaguarda real)
    r_ps = np.where(df["ps_hospitalar_sus"] > 0, np.where(df["leitos_uti_adulto_sus"] > 0, 1.0, 0.5), 0.0)
    df["infra_capacidade"] = 100.0 * (0.45 * r_uti + 0.35 * r_cir + 0.20 * r_ps)
    ref_uti, ref_cir = refs["uti"], refs["cir"]

    df["escore_infra"] = (0.30 * df["infra_basico"] + 0.40 * df["infra_avancado"] + 0.30 * df["infra_capacidade"]).round(1)
    for c in ("infra_basico", "infra_avancado", "infra_capacidade"):
        df[c] = df[c].round(1)
    df["ref_uti_100k"] = round(ref_uti, 2)
    df["ref_cir_100k"] = round(ref_cir, 2)
    df["vintage_infra"] = f"CNES competência {COMP}"

    cols = ["ibge7", "ibge6", "nome_municipio", "uf_sigla"] + \
           [c for c in df.columns if c.startswith(("eq_", "leitos_", "ps_", "unid_", "acc_"))] + \
           ["infra_basico", "infra_avancado", "infra_capacidade", "escore_infra", "ref_uti_100k", "ref_cir_100k", "vintage_infra"]
    out = df[cols].copy()
    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    out.to_parquet(caminho_saida, index=False)
    print(f"[cnes_infra] {len(out)} municípios -> {caminho_saida} (ref UTI/100k={ref_uti:.2f}, cir/100k={ref_cir:.2f})")
    return out


if __name__ == "__main__":
    processar_cnes_infra()
