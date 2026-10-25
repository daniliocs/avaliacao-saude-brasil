/**
 * site/assets/js/compare_view.js
 *
 * Tela interativa de Comparação Lado a Lado:
 *   1. Comparar 2 Cidades (Municípios) — compara Nota Geral, D1, D2, D3, posições,
 *      todos os 10 indicadores de desempenho + 4 indicadores de contexto/privado (SIOPS, ANS, CNES).
 *   2. Comparar 2 Estados (UFs + DF) — compara posição estadual, média simples e ponderada,
 *      D1, D2, D3, mediana de TMI, gasto SIOPS, planos privados e Top 5 municípios de cada UF.
 */

import { openDrawer } from "./drawer_municipio.js?v=0.7.4";

let mapaResumoRef = {};
let rankingsRef = {};
let metaBuildRef = null;

let activeMode = "municipios"; // "municipios" | "estados"
let selectedMunA = "3550308";  // São Paulo (SP)
let selectedMunB = "4106902";  // Curitiba (PR)
let selectedUfA = "SC";
let selectedUfB = "SP";

const INDICADORES_META = [
    { id: "D1.1", nome: "D1.1 — Mortalidade Infantil", unidade: "óbitos / 1.000 NV", sentido: "menor_melhor", dim: "D1" },
    { id: "D1.2", nome: "D1.2 — Razão de Mortalidade Materna (Informativo)", unidade: "óbitos / 100k NV", sentido: "menor_melhor", dim: "D1" },
    { id: "D1.3", nome: "D1.3 — Mortalidade Prematura DCNT (30–69a)", unidade: "óbitos / 100k hab", sentido: "menor_melhor", dim: "D1" },
    { id: "D1.4", nome: "D1.4 — Mortalidade por Causas Evitáveis", unidade: "óbitos / 100k hab", sentido: "menor_melhor", dim: "D1" },
    { id: "D2.1", nome: "D2.1 — Internações Sensíveis à APS (ICSAP)", unidade: "int. / 10k hab", sentido: "menor_melhor", dim: "D2" },
    { id: "D2.2", nome: "D2.2 — Pré-natal Adequado (7+ consultas)", unidade: "%", sentido: "maior_melhor", dim: "D2" },
    { id: "D2.3", nome: "D2.3 — Cobertura Vacinal Composta (Pólio/Penta/TV)", unidade: "%", sentido: "maior_melhor", dim: "D2" },
    { id: "D3.1", nome: "D3.1 — Leitos SUS na Região de Saúde", unidade: "leitos / 100k hab", sentido: "maior_melhor", dim: "D3" },
    { id: "D3.2", nome: "D3.2 — Médicos + Enfermeiros (40h/sem)", unidade: "prof. / 1.000 hab", sentido: "maior_melhor", dim: "D3" },
    { id: "D3.3", nome: "D3.3 — Cobertura Estratégia Saúde da Família (eSF)", unidade: "%", sentido: "maior_melhor", dim: "D3" }
];

export function initCompareView(metaBuild, mapaResumo, rankingsData) {
    metaBuildRef = metaBuild;
    if (mapaResumo && Object.keys(mapaResumo).length > 0) {
        mapaResumoRef = mapaResumo;
    }
    if (rankingsData && Object.keys(rankingsData).length > 0) {
        rankingsRef = rankingsData;
    }
    renderCompareView();
}

export function updateCompareData(mapaResumo, rankingsData) {
    if (mapaResumo && Object.keys(mapaResumo).length > 0) {
        mapaResumoRef = mapaResumo;
    }
    if (rankingsData && Object.keys(rankingsData).length > 0) {
        rankingsRef = rankingsData;
    }
    renderCompareView();
}

function getColorForScore(score) {
    if (score === null || score === undefined || isNaN(score)) return "#94a3b8";
    if (score >= 80) return "#15803d";
    if (score >= 65) return "#22c55e";
    if (score >= 50) return "#eab308";
    if (score >= 35) return "#f97316";
    return "#dc2626";
}

function fmtNum(val, digits = 1, suffix = "") {
    if (val === null || val === undefined || isNaN(val)) return "—";
    return Number(val).toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits }) + suffix;
}

export function renderCompareView() {
    const container = document.getElementById("compare-container");
    if (!container) return;

    const hasMunData = Object.keys(mapaResumoRef).length > 0;

    container.innerHTML = `
        <div class="page-container" style="max-width: 1200px;">
            <header class="page-header" style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:1rem;">
                <div>
                    <h1 class="page-title">⚖️ Comparador Lado a Lado: Cidades e Estados</h1>
                    <p class="page-lead" style="margin-top:0.25rem;">
                        Compare diretamente o desempenho geral, as dimensões D1, D2 e D3, todos os indicadores e o contexto financeiro/privado entre dois municípios ou duas Unidades da Federação.
                    </p>
                </div>
                <div class="compare-mode-tabs" role="tablist">
                    <button class="compare-mode-btn ${activeMode === 'municipios' ? 'active' : ''}" data-mode="municipios">
                        🏙️ Comparar 2 Cidades
                    </button>
                    <button class="compare-mode-btn ${activeMode === 'estados' ? 'active' : ''}" data-mode="estados">
                        🗺️ Comparar 2 Estados (UFs)
                    </button>
                </div>
            </header>

            <div id="compare-body-content">
                ${!hasMunData
                    ? `<div class="content-section"><p>Carregando base de dados dos 5.570 municípios...</p></div>`
                    : (activeMode === "municipios" ? renderMunicipiosComparison() : renderEstadosComparison())
                }
            </div>
        </div>
    `;

    container.querySelectorAll(".compare-mode-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            activeMode = btn.dataset.mode;
            renderCompareView();
        });
    });

    if (hasMunData) {
        if (activeMode === "municipios") {
            setupMunicipiosComparisonEvents(container);
        } else {
            setupEstadosComparisonEvents(container);
        }
    }
}

function renderMunicipiosComparison() {
    const munA = mapaResumoRef[selectedMunA] || Object.values(mapaResumoRef)[0];
    const munB = mapaResumoRef[selectedMunB] || Object.values(mapaResumoRef)[1];
    if (!munA || !munB) return `<p>Municípios não encontrados.</p>`;

    const diffRow = (label, valA, valB, sentido = "maior_melhor", digits = 1, unit = "") => {
        const aOk = typeof valA === "number" && !isNaN(valA);
        const bOk = typeof valB === "number" && !isNaN(valB);
        let winA = false;
        let winB = false;
        if (aOk && bOk && Math.abs(valA - valB) > 0.05) {
            if (sentido === "maior_melhor") {
                winA = valA > valB;
                winB = valB > valA;
            } else if (sentido === "menor_melhor") {
                winA = valA < valB;
                winB = valB < valA;
            }
        }
        const pctA = aOk ? Math.min(100, Math.max(6, valA)) : 0;
        const pctB = bOk ? Math.min(100, Math.max(6, valB)) : 0;

        return `
            <div class="compare-metric-row">
                <div class="compare-side compare-side--left ${winA ? 'compare-winner' : ''}">
                    <div class="compare-val-line">
                        <strong style="font-size:1.1rem; color:${getColorForScore(valA)};">${fmtNum(valA, digits, unit)}</strong>
                        ${winA ? `<span class="win-pill">Melhor</span>` : ""}
                    </div>
                    <div class="compare-bar-track compare-bar-track--left">
                        <div class="compare-bar-fill" style="width:${pctA}%; background:${getColorForScore(valA)};"></div>
                    </div>
                </div>
                <div class="compare-center-label">${label}</div>
                <div class="compare-side compare-side--right ${winB ? 'compare-winner' : ''}">
                    <div class="compare-val-line">
                        ${winB ? `<span class="win-pill">Melhor</span>` : ""}
                        <strong style="font-size:1.1rem; color:${getColorForScore(valB)};">${fmtNum(valB, digits, unit)}</strong>
                    </div>
                    <div class="compare-bar-track">
                        <div class="compare-bar-fill" style="width:${pctB}%; background:${getColorForScore(valB)};"></div>
                    </div>
                </div>
            </div>
        `;
    };

    const indRowsHtml = INDICADORES_META.map(meta => {
        const indA = munA.indicadores?.[meta.id] || {};
        const indB = munB.indicadores?.[meta.id] || {};
        const vA = indA.valor;
        const vB = indB.valor;
        const sA = indA.escore;
        const sB = indB.escore;

        let winA = false;
        let winB = false;
        if (typeof vA === "number" && typeof vB === "number" && Math.abs(vA - vB) > 0.01) {
            if (meta.sentido === "maior_melhor") {
                winA = vA > vB;
                winB = vB > vA;
            } else {
                winA = vA < vB;
                winB = vB < vA;
            }
        }

        return `
            <tr>
                <td style="text-align:right; ${winA ? 'background:#f0fdf4; font-weight:700;' : ''}">
                    <div>${fmtNum(vA, meta.id === "D1.1" || meta.id === "D3.2" ? 2 : 1)} <small style="color:var(--color-text-subtle);">${meta.unidade}</small></div>
                    <div style="font-size:0.72rem; color:var(--color-text-subtle);">
                        Escore: <strong>${fmtNum(sA, 1)}</strong> | Bruta: ${fmtNum(indA.taxa_bruta, 1)}
                    </div>
                </td>
                <td style="text-align:center; font-weight:600; background:var(--color-bg);">
                    <div>${meta.nome}</div>
                    <div style="font-size:0.7rem; color:var(--color-text-subtle); font-weight:400;">
                        ${meta.sentido === 'menor_melhor' ? '↓ Menor é melhor' : '↑ Maior é melhor'} &bull; Janela: ${indA.periodo_vintage || '2021–2023'}
                    </div>
                </td>
                <td style="text-align:left; ${winB ? 'background:#f0fdf4; font-weight:700;' : ''}">
                    <div>${fmtNum(vB, meta.id === "D1.1" || meta.id === "D3.2" ? 2 : 1)} <small style="color:var(--color-text-subtle);">${meta.unidade}</small></div>
                    <div style="font-size:0.72rem; color:var(--color-text-subtle);">
                        Escore: <strong>${fmtNum(sB, 1)}</strong> | Bruta: ${fmtNum(indB.taxa_bruta, 1)}
                    </div>
                </td>
            </tr>
        `;
    }).join("");

    // Dimensão 5: Urgência e SAMU 192 (DEMAS/MS)
    const urgA = munA.urgencia_samu || {};
    const urgB = munB.urgencia_samu || {};
    const urgRows = [
        {
            nome: "D5 — Escore da Rede de Urgência & SAMU (0–100)",
            unid: "pts",
            vA: munA.d5_nota,
            vB: munB.d5_nota,
            digits: 1
        },
        {
            nome: "D5.1 — Cobertura Efetiva do SAMU 192",
            unid: "%",
            vA: urgA.cob_samu_efetiva,
            vB: urgB.cob_samu_efetiva,
            digits: 1
        },
        {
            nome: "D5.2 — UPAs 24h em Operação no Município",
            unid: "unidades",
            vA: urgA.upa_mun ?? 0,
            vB: urgB.upa_mun ?? 0,
            digits: 0
        },
        {
            nome: "D5.3 — Ambulâncias Básicas (USB) no Município",
            unid: "unidades",
            vA: urgA.usb_mun ?? 0,
            vB: urgB.usb_mun ?? 0,
            digits: 0
        },
        {
            nome: "D5.4 — UTIs Móveis / Avançadas (USA) no Município",
            unid: "unidades",
            vA: urgA.usa_mun ?? 0,
            vB: urgB.usa_mun ?? 0,
            digits: 0
        },
        {
            nome: "D5.5 — Taxa de Frota SAMU na Região de Saúde",
            unid: "amb. / 100k hab",
            vA: urgA.tx_frota_samu_reg_100k,
            vB: urgB.tx_frota_samu_reg_100k,
            digits: 2
        },
        {
            nome: "D5.6 — Distância Rodoviária ao Polo Hospitalar (↓ menor é melhor)",
            unid: "km",
            vA: urgA.dist_polo_km ?? 0,
            vB: urgB.dist_polo_km ?? 0,
            digits: 1,
            sentido: "menor_melhor"
        },
        {
            nome: "D5.7 — Tempo Estimado de Socorro / Remoção (↓ menor é melhor)",
            unid: "min",
            vA: urgA.tempo_ambulancia_min ?? 12,
            vB: urgB.tempo_ambulancia_min ?? 12,
            digits: 0,
            sentido: "menor_melhor"
        },
        {
            nome: "D5.8 — Leitos Hospitalares SUS no Município",
            unid: "leitos",
            vA: urgA.leitos_locais_sus ?? 0,
            vB: urgB.leitos_locais_sus ?? 0,
            digits: 0
        },
        {
            nome: "D5.9 — Escore de Prontidão Imediata Local (0–100)",
            unid: "pts",
            vA: urgA.escore_prontidao_local,
            vB: urgB.escore_prontidao_local,
            digits: 2
        }
    ];

    const urgRowsHtml = `
        <tr style="background:#eff6ff;">
            <td colspan="3" style="text-align:center; color:#0369a1; font-weight:700; padding:0.45rem; font-size:0.84rem;">
                🚑 Dimensão 5: Rede de Urgência &amp; SAMU 192 (DEMAS/SEIDIGI/MS 2024)
            </td>
        </tr>
        ${urgRows.map(r => {
            const aOk = typeof r.vA === "number" && !isNaN(r.vA);
            const bOk = typeof r.vB === "number" && !isNaN(r.vB);
            const winA = aOk && bOk && (r.sentido === "menor_melhor" ? r.vA < r.vB : r.vA > r.vB);
            const winB = aOk && bOk && (r.sentido === "menor_melhor" ? r.vB < r.vA : r.vB > r.vA);

            return `
                <tr>
                    <td style="text-align:right; font-weight:600; ${winA ? 'background:#f0fdf4;' : ''}">${fmtNum(r.vA, r.digits)} <small style="color:var(--color-text-subtle);">${r.unid}</small></td>
                    <td style="text-align:center; background:#f8fafc; font-weight:600; font-size:0.82rem;">${r.nome}</td>
                    <td style="text-align:left; font-weight:600; ${winB ? 'background:#f0fdf4;' : ''}">${fmtNum(r.vB, r.digits)} <small style="color:var(--color-text-subtle);">${r.unid}</small></td>
                </tr>
            `;
        }).join("")}
    `;

        // Linha de Cuidado Oncológico & CACON/UNACON (Fase 2)
    const oncoA = munA.oncologia_tfd || {};
    const oncoB = munB.oncologia_tfd || {};

    const oncoRows = [
        {
            nome: "ONCO.1 — Escore de Oncologia & Alta Complexidade (0–100)",
            unid: "pts",
            vA: munA.escore_oncologia,
            vB: munB.escore_oncologia,
            digits: 1
        },
        {
            nome: "ONCO.2 — Centro CACON / UNACON de Referência",
            unid: "",
            vA_str: oncoA.cacon_referencia || "—",
            vB_str: oncoB.cacon_referencia || "—",
            is_text: true
        },
        {
            nome: "ONCO.3 — Distância Rodoviária ao CACON/UNACON (↓ menor é melhor)",
            unid: "km",
            vA: oncoA.dist_cacon_km ?? 0,
            vB: oncoB.dist_cacon_km ?? 0,
            digits: 1,
            sentido: "menor_melhor"
        },
        {
            nome: "ONCO.4 — Tempo Estimado até o CACON/UNACON (↓ menor é melhor)",
            unid: "min",
            vA: oncoA.tempo_cacon_min ?? 15,
            vB: oncoB.tempo_cacon_min ?? 15,
            digits: 0,
            sentido: "menor_melhor"
        },
        {
            nome: "ONCO.5 — Lei dos 60 Dias (% Início Tratamento ≤ 60d)",
            unid: "%",
            vA: oncoA.pct_60d_onco,
            vB: oncoB.pct_60d_onco,
            digits: 1
        },
        {
            nome: "ONCO.6 — Tempo Mediano até 1º Tratamento (↓ menor é melhor)",
            unid: "dias",
            vA: oncoA.tempo_mediano_onco_dias,
            vB: oncoB.tempo_mediano_onco_dias,
            digits: 0,
            sentido: "menor_melhor"
        },
        {
            nome: "ONCO.7 — Tratamento Fora do Município - TFD (Deslocamento)",
            unid: "%",
            vA: oncoA.pct_tratamento_fora,
            vB: oncoB.pct_tratamento_fora,
            digits: 1
        },
        {
            nome: "ONCO.8 — Diagnóstico Precoce (Estádios I e II)",
            unid: "%",
            vA: oncoA.pct_diagnostico_precoce,
            vB: oncoB.pct_diagnostico_precoce,
            digits: 1
        },
        {
            nome: "ONCO.9 — Mortalidade Prematura por Câncer (30–69 anos, SIM)",
            unid: "óbitos / 100k hab",
            vA: oncoA.tx_cancer_prem_bayes,
            vB: oncoB.tx_cancer_prem_bayes,
            digits: 1,
            sentido: "menor_melhor"
        },
        {
            nome: "ONCO.10 — Terapias de Ponta (Imunoterapia & Terapia Alvo)",
            unid: "",
            vA_str: oncoA.polo_imunoterapia_alvo ? "✅ Habilitada no SUS" : "⚠️ Requer Polo Terciário",
            vB_str: oncoB.polo_imunoterapia_alvo ? "✅ Habilitada no SUS" : "⚠️ Requer Polo Terciário",
            is_text: true
        },
        {
            nome: "ONCO.9 — Volume Total de Pacientes em Tratamento (Triênio)",
            unid: "casos",
            vA: oncoA.casos_total ?? 0,
            vB: oncoB.casos_total ?? 0,
            digits: 0
        }
    ];

    const oncoRowsHtml = `
        <tr style="background:#faf5ff;">
            <td colspan="3" style="text-align:center; color:#6b21a8; font-weight:700; padding:0.45rem; font-size:0.84rem;">
                🎗️ Linha de Cuidado Oncológico &amp; CACON/UNACON (Painel-Oncologia Brasil 2021–2023)
            </td>
        </tr>
        ${oncoRows.map(r => {
            if (r.is_text) {
                return `
                    <tr>
                        <td style="text-align:right; font-weight:600;">${r.vA_str}</td>
                        <td style="text-align:center; background:#f8fafc; font-weight:600; font-size:0.82rem;">${r.nome}</td>
                        <td style="text-align:left; font-weight:600;">${r.vB_str}</td>
                    </tr>
                `;
            }
            const aOk = typeof r.vA === "number" && !isNaN(r.vA);
            const bOk = typeof r.vB === "number" && !isNaN(r.vB);
            const winA = aOk && bOk && (r.sentido === "menor_melhor" ? r.vA < r.vB : r.vA > r.vB);
            const winB = aOk && bOk && (r.sentido === "menor_melhor" ? r.vB < r.vA : r.vB > r.vA);

            return `
                <tr>
                    <td style="text-align:right; font-weight:600; ${winA ? 'background:#f0fdf4;' : ''}">${fmtNum(r.vA, r.digits)} <small style="color:var(--color-text-subtle);">${r.unid}</small></td>
                    <td style="text-align:center; background:#f8fafc; font-weight:600; font-size:0.82rem;">${r.nome}</td>
                    <td style="text-align:left; font-weight:600; ${winB ? 'background:#f0fdf4;' : ''}">${fmtNum(r.vB, r.digits)} <small style="color:var(--color-text-subtle);">${r.unid}</small></td>
                </tr>
            `;
        }).join("")}
    `;

    // Contexto D4 e Camada Privada
    const ctxRows = [
        {
            nome: "D4.1 — Gasto Per Capita em Saúde Deflacionado (SIOPS)",
            unid: "R$/hab/ano",
            vA: munA.d4_contexto?.gasto_per_capita?.valor,
            vB: munB.d4_contexto?.gasto_per_capita?.valor,
            digits: 2
        },
        {
            nome: "D4.2 — % da Receita Própria Aplicada em Saúde (EC 29)",
            unid: "%",
            vA: munA.d4_contexto?.percentual_proprio?.valor,
            vB: munB.d4_contexto?.percentual_proprio?.valor,
            digits: 1
        },
        {
            nome: "PRIV.1 — Cobertura de Planos Privados de Saúde (ANS)",
            unid: "%",
            vA: munA.camada_privada?.cobertura_planos?.valor,
            vB: munB.camada_privada?.cobertura_planos?.valor,
            digits: 1
        },
        {
            nome: "PRIV.2 — Leitos Privados Não-SUS (CNES)",
            unid: "leitos / 100k hab",
            vA: munA.camada_privada?.leitos_privados?.valor,
            vB: munB.camada_privada?.leitos_privados?.valor,
            digits: 1
        }
    ];

    const ctxRowsHtml = ctxRows.map(r => `
        <tr>
            <td style="text-align:right; font-weight:600;">${fmtNum(r.vA, r.digits)} <small style="color:var(--color-text-subtle);">${r.unid}</small></td>
            <td style="text-align:center; background:#faf5ff; font-weight:600; font-size:0.82rem;">${r.nome} <span class="separated-tag" style="margin-left:4px;">Fora da Nota</span></td>
            <td style="text-align:left; font-weight:600;">${fmtNum(r.vB, r.digits)} <small style="color:var(--color-text-subtle);">${r.unid}</small></td>
        </tr>
    `).join("");

    return `
        <!-- Barra de Seleção de Municípios e Atalhos -->
        <section class="content-section" style="padding:1.15rem;">
            <div class="compare-selectors-grid">
                <div class="compare-selector-box">
                    <label style="font-size:0.75rem; font-weight:700; text-transform:uppercase; color:var(--color-primary-dark); display:block; margin-bottom:0.35rem;">
                        Município A
                    </label>
                    <div class="search-box" style="max-width:100%;">
                        <span class="search-icon">🔍</span>
                        <input type="text" id="comp-input-a" class="search-input" value="${munA.nome} (${munA.uf})" placeholder="Digite o nome ou código IBGE do Município A..." autocomplete="off">
                        <div id="comp-drop-a" class="search-results-dropdown"></div>
                    </div>
                </div>

                <div style="display:flex; align-items:flex-end; justify-content:center; padding-bottom:0.2rem;">
                    <button id="btn-swap-mun" class="btn-ranking-toggle" title="Inverter Municípios A e B">⇄ Inverter</button>
                </div>

                <div class="compare-selector-box">
                    <label style="font-size:0.75rem; font-weight:700; text-transform:uppercase; color:#0f766e; display:block; margin-bottom:0.35rem;">
                        Município B
                    </label>
                    <div class="search-box" style="max-width:100%;">
                        <span class="search-icon">🔍</span>
                        <input type="text" id="comp-input-b" class="search-input" value="${munB.nome} (${munB.uf})" placeholder="Digite o nome ou código IBGE do Município B..." autocomplete="off">
                        <div id="comp-drop-b" class="search-results-dropdown"></div>
                    </div>
                </div>
            </div>

            <div style="display:flex; flex-wrap:wrap; gap:0.4rem; align-items:center; margin-top:0.5rem; font-size:0.75rem;">
                <span style="color:var(--color-text-subtle); font-weight:600;">Comparações rápidas:</span>
                <button class="rank-dim-btn preset-mun-pair" data-a="3550308" data-b="3304557">São Paulo (SP) × Rio de Janeiro (RJ)</button>
                <button class="rank-dim-btn preset-mun-pair" data-a="4106902" data-b="3106200">Curitiba (PR) × Belo Horizonte (MG)</button>
                <button class="rank-dim-btn preset-mun-pair" data-a="2304400" data-b="2927408">Fortaleza (CE) × Salvador (BA)</button>
                <button class="rank-dim-btn preset-mun-pair" data-a="4216255" data-b="1504208">São João do Oeste (SC) × Marabá (PA)</button>
            </div>
        </section>

        <!-- Cabeçalho Comparativo de Resumo -->
        <section class="content-section">
            <div class="compare-cards-duo">
                <div class="compare-city-card">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <h2 style="font-size:1.3rem; font-weight:800; color:var(--color-text-main);">${munA.nome} (${munA.uf})</h2>
                            <p style="font-size:0.8rem; color:var(--color-text-muted);">
                                IBGE: ${munA.ibge7} &bull; População: <strong>${munA.populacao ? munA.populacao.toLocaleString("pt-BR") : "—"} hab.</strong>
                            </p>
                            <p style="font-size:0.76rem; color:var(--color-text-subtle);">
                                Porte: ${munA.porte} &bull; Região de Saúde: <strong>${munA.regiao_saude}</strong>
                            </p>
                        </div>
                        <span style="background:${getColorForScore(munA.nota_geral)}; color:#fff; font-size:1.35rem; font-weight:800; padding:0.35rem 0.75rem; border-radius:8px;">
                            ${fmtNum(munA.nota_geral, 1)}
                        </span>
                    </div>
                    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:0.4rem; margin-top:0.75rem; background:var(--color-bg); padding:0.5rem; border-radius:6px; text-align:center; font-size:0.75rem;">
                        <div><span style="color:var(--color-text-subtle); display:block;">Nacional</span><strong>#${munA.posicao_nacional || '—'}</strong></div>
                        <div><span style="color:var(--color-text-subtle); display:block;">Estadual (${munA.uf})</span><strong>#${munA.posicao_estadual || '—'}</strong></div>
                        <div><span style="color:var(--color-text-subtle); display:block;">Faixa Plausível</span><strong>${munA.faixa_posicao_min || '—'}º–${munA.faixa_posicao_max || '—'}º</strong></div>
                    </div>
                    <button class="btn-open-drawer-comp" data-ibge="${munA.ibge7}" style="margin-top:0.6rem; width:100%; padding:0.4rem; font-size:0.78rem; font-weight:600; border:1px solid var(--color-border); border-radius:6px; background:var(--color-surface); cursor:pointer;">
                        📄 Abrir Ficha Completa de ${munA.nome}
                    </button>
                </div>

                <div class="compare-city-card">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <h2 style="font-size:1.3rem; font-weight:800; color:var(--color-text-main);">${munB.nome} (${munB.uf})</h2>
                            <p style="font-size:0.8rem; color:var(--color-text-muted);">
                                IBGE: ${munB.ibge7} &bull; População: <strong>${munB.populacao ? munB.populacao.toLocaleString("pt-BR") : "—"} hab.</strong>
                            </p>
                            <p style="font-size:0.76rem; color:var(--color-text-subtle);">
                                Porte: ${munB.porte} &bull; Região de Saúde: <strong>${munB.regiao_saude}</strong>
                            </p>
                        </div>
                        <span style="background:${getColorForScore(munB.nota_geral)}; color:#fff; font-size:1.35rem; font-weight:800; padding:0.35rem 0.75rem; border-radius:8px;">
                            ${fmtNum(munB.nota_geral, 1)}
                        </span>
                    </div>
                    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:0.4rem; margin-top:0.75rem; background:var(--color-bg); padding:0.5rem; border-radius:6px; text-align:center; font-size:0.75rem;">
                        <div><span style="color:var(--color-text-subtle); display:block;">Nacional</span><strong>#${munB.posicao_nacional || '—'}</strong></div>
                        <div><span style="color:var(--color-text-subtle); display:block;">Estadual (${munB.uf})</span><strong>#${munB.posicao_estadual || '—'}</strong></div>
                        <div><span style="color:var(--color-text-subtle); display:block;">Faixa Plausível</span><strong>${munB.faixa_posicao_min || '—'}º–${munB.faixa_posicao_max || '—'}º</strong></div>
                    </div>
                    <button class="btn-open-drawer-comp" data-ibge="${munB.ibge7}" style="margin-top:0.6rem; width:100%; padding:0.4rem; font-size:0.78rem; font-weight:600; border:1px solid var(--color-border); border-radius:6px; background:var(--color-surface); cursor:pointer;">
                        📄 Abrir Ficha Completa de ${munB.nome}
                    </button>
                </div>
            </div>

            <h3 class="section-title" style="margin-top:0.5rem;">Comparação de Notas por Dimensão (Escala 0–100)</h3>
            <div style="display:flex; flex-direction:column; gap:0.75rem;">
                ${diffRow("🌟 Nota Geral Consolidada (Padrão Oficial 3D)", munA.nota_geral, munB.nota_geral, "maior_melhor", 1, " pts")}
                ${diffRow("⚡ Nota Expandida com Urgência (+15% RUE & Golden Hour)", munA.nota_com_urgencia, munB.nota_com_urgencia, "maior_melhor", 1, " pts")}
                ${diffRow("D1 — Resultados em Saúde (33,3% ou 30%)", munA.d1_nota, munB.d1_nota, "maior_melhor", 1, " pts")}
                ${diffRow("D2 — Atenção Primária e Prevenção (33,3% ou 30%)", munA.d2_nota, munB.d2_nota, "maior_melhor", 1, " pts")}
                ${diffRow("D3 — Acesso e Capacidade Assistencial (33,3% ou 30%)", munA.d3_nota, munB.d3_nota, "maior_melhor", 1, " pts")}
                ${diffRow("🚑 D5 — Rede de Urgência, SAMU & Distância (15% RUE)", munA.d5_nota, munB.d5_nota, "maior_melhor", 1, " pts")}
                ${diffRow("🎗️ Linha de Cuidado Oncológico & CACON (0–100)", munA.escore_oncologia, munB.escore_oncologia, "maior_melhor", 1, " pts")}
                ${diffRow("🎗️⚡ Nota Integrada (Urgência 15% + Onco 10%)", munA.nota_integrada, munB.nota_integrada, "maior_melhor", 1, " pts")}
            </div>
        </section>

        <!-- Tabela Detalhada Indicador a Indicador -->
        <section class="content-section">
            <h3 class="section-title">Comparação Indicador por Indicador (Triênio 2021–2023 & Urgência 2024)</h3>
            <div class="sources-table-wrapper">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th style="text-align:right; width:34%;">${munA.nome} (${munA.uf})</th>
                            <th style="text-align:center; width:32%;">Indicador / Direção</th>
                            <th style="text-align:left; width:34%;">${munB.nome} (${munB.uf})</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${indRowsHtml}
                        ${urgRowsHtml}
                        ${oncoRowsHtml}
                        ${ctxRowsHtml}
                    </tbody>
                </table>
            </div>
        </section>
    `;
}

function renderEstadosComparison() {
    const porUf = rankingsRef?.rankings_por_uf || {};
    const ufs = Object.keys(porUf).sort();
    if (ufs.length === 0) {
        return `<div class="content-section"><p>Dados estaduais em carregamento...</p></div>`;
    }

    const estA = porUf[selectedUfA] || porUf[ufs[0]];
    const estB = porUf[selectedUfB] || porUf[ufs[1]];

    const optionsA = ufs.map(u => `<option value="${u}" ${u === estA.uf ? "selected" : ""}>${u} — ${porUf[u].nome_uf || u}</option>`).join("");
    const optionsB = ufs.map(u => `<option value="${u}" ${u === estB.uf ? "selected" : ""}>${u} — ${porUf[u].nome_uf || u}</option>`).join("");

    const diffRow = (label, valA, valB, sentido = "maior_melhor", digits = 1, unit = "") => {
        const aOk = typeof valA === "number" && !isNaN(valA);
        const bOk = typeof valB === "number" && !isNaN(valB);
        let winA = false;
        let winB = false;
        if (aOk && bOk && Math.abs(valA - valB) > 0.05) {
            if (sentido === "maior_melhor") {
                winA = valA > valB;
                winB = valB > valA;
            } else if (sentido === "menor_melhor") {
                winA = valA < valB;
                winB = valB < valA;
            }
        }
        const pctA = aOk ? Math.min(100, Math.max(6, valA)) : 0;
        const pctB = bOk ? Math.min(100, Math.max(6, valB)) : 0;

        return `
            <div class="compare-metric-row">
                <div class="compare-side compare-side--left ${winA ? 'compare-winner' : ''}">
                    <div class="compare-val-line">
                        <strong style="font-size:1.1rem; color:${getColorForScore(valA)};">${fmtNum(valA, digits, unit)}</strong>
                        ${winA ? `<span class="win-pill">Melhor</span>` : ""}
                    </div>
                    <div class="compare-bar-track compare-bar-track--left">
                        <div class="compare-bar-fill" style="width:${pctA}%; background:${getColorForScore(valA)};"></div>
                    </div>
                </div>
                <div class="compare-center-label">${label}</div>
                <div class="compare-side compare-side--right ${winB ? 'compare-winner' : ''}">
                    <div class="compare-val-line">
                        ${winB ? `<span class="win-pill">Melhor</span>` : ""}
                        <strong style="font-size:1.1rem; color:${getColorForScore(valB)};">${fmtNum(valB, digits, unit)}</strong>
                    </div>
                    <div class="compare-bar-track">
                        <div class="compare-bar-fill" style="width:${pctB}%; background:${getColorForScore(valB)};"></div>
                    </div>
                </div>
            </div>
        `;
    };

    const top5List = (items) => (items || []).slice(0, 5).map((m, idx) => `
        <div class="ranking-row-item comp-uf-mun" data-ibge="${m.ibge7}" style="display:flex; justify-content:space-between; align-items:center; padding:0.45rem 0.65rem; border:1px solid var(--color-border); border-radius:6px; background:var(--color-surface); cursor:pointer;">
            <div>
                <strong style="color:var(--color-primary-dark); margin-right:4px;">#${idx + 1}</strong>
                <strong>${m.nome}</strong>
                <span style="font-size:0.74rem; color:var(--color-text-subtle); margin-left:4px;">(${m.populacao ? m.populacao.toLocaleString('pt-BR') + ' hab.' : ''})</span>
            </div>
            <span style="background:${getColorForScore(m.escore)}; color:#fff; font-weight:700; font-size:0.78rem; padding:2px 7px; border-radius:4px;">
                ${fmtNum(m.escore, 1)}
            </span>
        </div>
    `).join("");

    return `
        <section class="content-section" style="padding:1.15rem;">
            <div class="compare-selectors-grid">
                <div>
                    <label style="font-size:0.75rem; font-weight:700; text-transform:uppercase; color:var(--color-primary-dark); display:block; margin-bottom:0.35rem;">
                        Estado A (UF)
                    </label>
                    <select id="comp-uf-a" class="filter-select" style="width:100%; font-size:0.95rem; font-weight:600;">
                        ${optionsA}
                    </select>
                </div>

                <div style="display:flex; align-items:flex-end; justify-content:center; padding-bottom:0.2rem;">
                    <button id="btn-swap-uf" class="btn-ranking-toggle">⇄ Inverter UFs</button>
                </div>

                <div>
                    <label style="font-size:0.75rem; font-weight:700; text-transform:uppercase; color:#0f766e; display:block; margin-bottom:0.35rem;">
                        Estado B (UF)
                    </label>
                    <select id="comp-uf-b" class="filter-select" style="width:100%; font-size:0.95rem; font-weight:600;">
                        ${optionsB}
                    </select>
                </div>
            </div>

            <div style="display:flex; flex-wrap:wrap; gap:0.4rem; align-items:center; margin-top:0.5rem; font-size:0.75rem;">
                <span style="color:var(--color-text-subtle); font-weight:600;">Comparações rápidas:</span>
                <button class="rank-dim-btn preset-uf-pair" data-a="SC" data-b="RS">Santa Catarina × Rio Grande do Sul</button>
                <button class="rank-dim-btn preset-uf-pair" data-a="SP" data-b="RJ">São Paulo × Rio de Janeiro</button>
                <button class="rank-dim-btn preset-uf-pair" data-a="PR" data-b="MG">Paraná × Minas Gerais</button>
                <button class="rank-dim-btn preset-uf-pair" data-a="CE" data-b="BA">Ceará × Bahia</button>
            </div>
        </section>

        <section class="content-section">
            <div class="compare-cards-duo">
                <div class="compare-city-card">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <h2 style="font-size:1.35rem; font-weight:800;">${estA.nome_uf} (${estA.uf})</h2>
                            <p style="font-size:0.82rem; color:var(--color-text-muted);">
                                Região ${estA.regiao} &bull; <strong>${estA.total_municipios} municípios</strong> &bull; População: <strong>${estA.populacao_uf?.toLocaleString("pt-BR")} hab.</strong>
                            </p>
                        </div>
                        <span style="background:${getColorForScore(estA.media_escore_uf)}; color:#fff; font-size:1.35rem; font-weight:800; padding:0.35rem 0.75rem; border-radius:8px;">
                            ${fmtNum(estA.media_escore_uf, 1)}
                        </span>
                    </div>
                    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:0.4rem; margin-top:0.75rem; background:var(--color-bg); padding:0.5rem; border-radius:6px; text-align:center; font-size:0.75rem;">
                        <div><span style="color:var(--color-text-subtle); display:block;">Posição entre UFs</span><strong>#${estA.posicao_uf}º de 27</strong></div>
                        <div><span style="color:var(--color-text-subtle); display:block;">Média Ponderada Pop.</span><strong>${fmtNum(estA.media_ponderada_uf, 1)} pts</strong></div>
                        <div title="Mediana da Taxa de Mortalidade Infantil (óbitos de menores de 1 ano por 1.000 nascidos vivos) entre todos os municípios do estado"><span style="color:var(--color-text-subtle); display:block; cursor:help;">Mediana TMI ⓘ</span><strong>${fmtNum(estA.mediana_tmi_uf, 2)}‰</strong></div>
                    </div>
                </div>

                <div class="compare-city-card">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <h2 style="font-size:1.35rem; font-weight:800;">${estB.nome_uf} (${estB.uf})</h2>
                            <p style="font-size:0.82rem; color:var(--color-text-muted);">
                                Região ${estB.regiao} &bull; <strong>${estB.total_municipios} municípios</strong> &bull; População: <strong>${estB.populacao_uf?.toLocaleString("pt-BR")} hab.</strong>
                            </p>
                        </div>
                        <span style="background:${getColorForScore(estB.media_escore_uf)}; color:#fff; font-size:1.35rem; font-weight:800; padding:0.35rem 0.75rem; border-radius:8px;">
                            ${fmtNum(estB.media_escore_uf, 1)}
                        </span>
                    </div>
                    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:0.4rem; margin-top:0.75rem; background:var(--color-bg); padding:0.5rem; border-radius:6px; text-align:center; font-size:0.75rem;">
                        <div><span style="color:var(--color-text-subtle); display:block;">Posição entre UFs</span><strong>#${estB.posicao_uf}º de 27</strong></div>
                        <div><span style="color:var(--color-text-subtle); display:block;">Média Ponderada Pop.</span><strong>${fmtNum(estB.media_ponderada_uf, 1)} pts</strong></div>
                        <div title="Mediana da Taxa de Mortalidade Infantil (óbitos de menores de 1 ano por 1.000 nascidos vivos) entre todos os municípios do estado"><span style="color:var(--color-text-subtle); display:block; cursor:help;">Mediana TMI ⓘ</span><strong>${fmtNum(estB.mediana_tmi_uf, 2)}‰</strong></div>
                    </div>
                </div>
            </div>

            <h3 class="section-title" style="margin-top:0.5rem;">Médias Estaduais por Dimensão (0–100)</h3>
            <div style="display:flex; flex-direction:column; gap:0.75rem;">
                ${diffRow("🌟 Média Estadual da Nota Geral (Padrão 3D)", estA.media_escore_uf, estB.media_escore_uf, "maior_melhor", 1, " pts")}
                ${diffRow("⚡ Média Estadual com Urgência (+15% RUE & Golden Hour)", estA.media_com_urgencia_uf, estB.media_com_urgencia_uf, "maior_melhor", 1, " pts")}
                ${diffRow("👥 Média Estadual Ponderada pela População", estA.media_ponderada_uf, estB.media_ponderada_uf, "maior_melhor", 1, " pts")}
                ${diffRow("D1 — Resultados em Saúde (Média UF)", estA.media_d1_uf, estB.media_d1_uf, "maior_melhor", 1, " pts")}
                ${diffRow("D2 — Atenção Primária (Média UF)", estA.media_d2_uf, estB.media_d2_uf, "maior_melhor", 1, " pts")}
                ${diffRow("D3 — Acesso e Estrutura (Média UF)", estA.media_d3_uf, estB.media_d3_uf, "maior_melhor", 1, " pts")}
                ${diffRow("🚑 D5 — Urgência & SAMU 192 (Média UF)", estA.media_d5_uf, estB.media_d5_uf, "maior_melhor", 1, " pts")}
                ${diffRow("📡 Cobertura Média do SAMU 192 na UF", estA.cob_samu_media_uf, estB.cob_samu_media_uf, "maior_melhor", 1, "%")}
                ${diffRow("🏥 Total de UPAs 24h em Operação na UF", estA.total_upas_uf, estB.total_upas_uf, "maior_melhor", 0, " UPAs")}
                ${diffRow("🚐 Total de Ambulâncias SAMU (USB + USA) na UF", (estA.total_usb_uf || 0) + (estA.total_usa_uf || 0), (estB.total_usb_uf || 0) + (estB.total_usa_uf || 0), "maior_melhor", 0, " amb.")}
            </div>

            <div class="compare-cards-duo" style="margin-top:1rem;">
                <div>
                    <h4 style="font-size:0.92rem; font-weight:700; margin-bottom:0.5rem;">🏆 Top 5 Municípios — ${estA.nome_uf} (${estA.uf})</h4>
                    <div style="display:flex; flex-direction:column; gap:0.4rem;">
                        ${top5List(estA.melhores)}
                    </div>
                </div>
                <div>
                    <h4 style="font-size:0.92rem; font-weight:700; margin-bottom:0.5rem;">🏆 Top 5 Municípios — ${estB.nome_uf} (${estB.uf})</h4>
                    <div style="display:flex; flex-direction:column; gap:0.4rem;">
                        ${top5List(estB.melhores)}
                    </div>
                </div>
            </div>
        </section>
    `;
}

function setupMunicipiosComparisonEvents(container) {
    const setupAutocomplete = (inputId, dropId, onSelect) => {
        const input = container.querySelector(`#${inputId}`);
        const drop = container.querySelector(`#${dropId}`);
        if (!input || !drop) return;

        input.addEventListener("focus", () => input.select());
        input.addEventListener("input", () => {
            const q = input.value.trim().toLowerCase();
            if (q.length < 2) {
                drop.classList.remove("visible");
                return;
            }
            const matches = Object.values(mapaResumoRef)
                .filter(m => m.nome.toLowerCase().includes(q) || m.ibge7.includes(q))
                .slice(0, 12);
            if (matches.length === 0) {
                drop.innerHTML = `<div class="search-item">Nenhum município encontrado</div>`;
            } else {
                drop.innerHTML = matches.map(m => `
                    <div class="search-item" data-ibge="${m.ibge7}">
                        <strong>${m.nome} (${m.uf})</strong>
                        <span style="font-size:0.75rem; color:var(--color-text-subtle);">Nota: ${fmtNum(m.nota_geral, 1)}</span>
                    </div>
                `).join("");
                drop.querySelectorAll(".search-item").forEach(item => {
                    item.addEventListener("click", () => {
                        onSelect(item.dataset.ibge);
                        drop.classList.remove("visible");
                        renderCompareView();
                    });
                });
            }
            drop.classList.add("visible");
        });
    };

    setupAutocomplete("comp-input-a", "comp-drop-a", (ibge) => { selectedMunA = ibge; });
    setupAutocomplete("comp-input-b", "comp-drop-b", (ibge) => { selectedMunB = ibge; });

    const btnSwap = container.querySelector("#btn-swap-mun");
    if (btnSwap) {
        btnSwap.addEventListener("click", () => {
            const tmp = selectedMunA;
            selectedMunA = selectedMunB;
            selectedMunB = tmp;
            renderCompareView();
        });
    }

    container.querySelectorAll(".preset-mun-pair").forEach(btn => {
        btn.addEventListener("click", () => {
            selectedMunA = btn.dataset.a;
            selectedMunB = btn.dataset.b;
            renderCompareView();
        });
    });

    container.querySelectorAll(".btn-open-drawer-comp").forEach(btn => {
        btn.addEventListener("click", () => {
            const mun = mapaResumoRef[btn.dataset.ibge];
            if (mun) openDrawer(mun);
        });
    });
}

function setupEstadosComparisonEvents(container) {
    const selA = container.querySelector("#comp-uf-a");
    const selB = container.querySelector("#comp-uf-b");

    if (selA) {
        selA.addEventListener("change", () => {
            selectedUfA = selA.value;
            renderCompareView();
        });
    }
    if (selB) {
        selB.addEventListener("change", () => {
            selectedUfB = selB.value;
            renderCompareView();
        });
    }

    const btnSwap = container.querySelector("#btn-swap-uf");
    if (btnSwap) {
        btnSwap.addEventListener("click", () => {
            const tmp = selectedUfA;
            selectedUfA = selectedUfB;
            selectedUfB = tmp;
            renderCompareView();
        });
    }

    container.querySelectorAll(".preset-uf-pair").forEach(btn => {
        btn.addEventListener("click", () => {
            selectedUfA = btn.dataset.a;
            selectedUfB = btn.dataset.b;
            renderCompareView();
        });
    });

    container.querySelectorAll(".comp-uf-mun").forEach(row => {
        row.addEventListener("click", () => {
            const mun = mapaResumoRef[row.dataset.ibge];
            if (mun) openDrawer(mun);
        });
    });
}
