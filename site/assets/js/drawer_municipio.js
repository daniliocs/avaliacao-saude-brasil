/**
 * site/assets/js/drawer_municipio.js
 * 
 * Ficha Lateral do Município (Drawer)
 * Regras Inegociáveis Implementadas:
 * - Regra 3: Rastreabilidade total na UI (via audit_badge.js).
 * - Regra 4: A Nota Geral NUNCA aparece sozinha (D1, D2, D3 e faixa de sensibilidade no mesmo bloco).
 * - D4 (Contexto) e Camada Privada exibidos em blocos separados fora da nota (DEC-001).
 */

import { renderAuditBadge } from "./audit_badge.js";

let metaConfigCache = null;

export function initDrawer(metaConfig) {
    metaConfigCache = metaConfig;
    const backdrop = document.getElementById("drawer-backdrop");
    const btnClose = document.getElementById("btn-close-drawer");

    if (backdrop) {
        backdrop.addEventListener("click", closeDrawer);
    }
    if (btnClose) {
        btnClose.addEventListener("click", closeDrawer);
    }

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeDrawer();
        }
    });
}

export function openDrawer(municipioData) {
    if (!municipioData) return;

    const drawer = document.getElementById("municipio-drawer");
    const backdrop = document.getElementById("drawer-backdrop");
    const drawerTitle = document.getElementById("drawer-mun-title");
    const drawerMeta = document.getElementById("drawer-mun-meta");
    const drawerBody = document.getElementById("drawer-body");

    if (!drawer || !drawerBody) return;

    // Cabeçalho do Município
    const popFmt = municipioData.populacao ? `${municipioData.populacao.toLocaleString("pt-BR")} habitantes (Censo 2022)` : "População em validação";
    drawerTitle.textContent = `${municipioData.nome} — ${municipioData.uf}`;
    drawerMeta.textContent = `Código IBGE: ${municipioData.ibge7} (DATASUS: ${municipioData.ibge6}) | População: ${popFmt} | Porte: ${municipioData.porte || "A validar"} | Região: ${municipioData.regiao} | Região de Saúde: ${municipioData.regiao_saude || "A validar"}`;

    // Montagem do corpo da gaveta
    drawerBody.innerHTML = `
        <!-- BLOCO OBRIGATÓRIO DA NOTA GERAL E DIMENSÕES (REGRA 4) -->
        <section class="mandatory-score-card" aria-label="Desempenho Geral e Dimensões">
            <div class="score-card-header">
                <span class="score-card-title">Índice Sintético de Saúde Pública</span>
                <span class="badge ${municipioData.status === 'sem_classificacao' ? 'badge--pending' : 'badge--quality-high'}">
                    ${municipioData.status === 'sem_classificacao' ? 'Sem Classificação' : 'Classificado'}
                </span>
            </div>

            <div class="score-main-row">
                <div>
                    <span style="font-size: 0.75rem; text-transform: uppercase; color: var(--color-text-subtle); font-weight: 700; display: block;">Nota Geral (0–100)</span>
                    ${renderNotaGeral(municipioData.nota_geral)}
                </div>
                <div style="text-align: right;">
                    <span style="font-size: 0.75rem; color: var(--color-text-subtle); display: block;">Faixa de Posição Plausível</span>
                    <strong>${renderFaixaPosicao(municipioData.faixa_posicao_min, municipioData.faixa_posicao_max)}</strong>
                </div>
            </div>

            <!-- Dimensões D1, D2 e D3 SEMPRE VISÍVEIS NO MESMO BLOCO -->
            <div class="dimensions-trio-grid">
                <div class="dim-item-box">
                    <span class="dim-item-label">D1 — Resultados</span>
                    <span class="dim-item-value">${formatNota(municipioData.d1_nota)}</span>
                </div>
                <div class="dim-item-box">
                    <span class="dim-item-label">D2 — Atenção Primária</span>
                    <span class="dim-item-value">${formatNota(municipioData.d2_nota)}</span>
                </div>
                <div class="dim-item-box">
                    <span class="dim-item-label">D3 — Estrutura/Acesso</span>
                    <span class="dim-item-value">${formatNota(municipioData.d3_nota)}</span>
                </div>
            </div>

            <!-- Comparações de Ranking -->
            <div class="rankings-grid">
                <div>
                    <span style="color: var(--color-text-subtle);">Ranking Nacional</span>
                    <span class="rank-val">${municipioData.posicao_nacional ? `#${municipioData.posicao_nacional} de 5.570` : '—'}</span>
                </div>
                <div>
                    <span style="color: var(--color-text-subtle);">Ranking Estadual (${municipioData.uf})</span>
                    <span class="rank-val">${municipioData.posicao_estadual ? `#${municipioData.posicao_estadual}` : '—'}</span>
                </div>
                <div>
                    <span style="color: var(--color-text-subtle);">Grupo de Pares</span>
                    <span class="rank-val">${municipioData.posicao_grupo_pares ? `#${municipioData.posicao_grupo_pares}` : '—'}</span>
                </div>
            </div>
        </section>

        <!-- ACORDEÕES DOS INDICADORES DAS DIMENSÕES D1, D2, D3 -->
        <section class="indicator-accordion-group" aria-label="Indicadores por Dimensão">
            <h3 class="section-heading">Indicadores Detalhados com Rastreabilidade</h3>
            
            ${renderDimAccordion("D1", "Resultados em Saúde", ["D1.1", "D1.2", "D1.3", "D1.4"], municipioData)}
            ${renderDimAccordion("D2", "Atenção Primária à Saúde", ["D2.1", "D2.2", "D2.3", "D2.4"], municipioData)}
            ${renderDimAccordion("D3", "Acesso e Infraestrutura", ["D3.1", "D3.2", "D3.3", "D3.4"], municipioData)}
        </section>

        <!-- BLOCO SEPARADO: CONTEXTO MUNICIPAL (D4) - FORA DA NOTA -->
        <section class="separated-layer-card" aria-label="Contexto Municipal">
            <div class="separated-layer-header">
                <h4 style="font-size: 0.95rem; font-weight: 700;">Dimensão 4: Contexto e Financiamento (SIOPS)</h4>
                <span class="separated-tag">Fora da Nota</span>
            </div>
            <p style="font-size: 0.75rem; color: var(--color-text-muted);">
                Conforme DEC-001, gastos e transferências são contextuais e não medem a qualidade assistencial do território.
            </p>
            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                ${renderAuditBadge(municipioData.d4_contexto?.gasto_per_capita, {
                    id: "D4.1",
                    nome: "Gasto Per Capita em Saúde (SIOPS)",
                    unidade: "R$/hab/ano",
                    pendencia_id: "PEND-027"
                })}
                ${renderAuditBadge(municipioData.d4_contexto?.percentual_proprio, {
                    id: "D4.2",
                    nome: "Aplicação de Receita Própria em Saúde (% EC 29)",
                    unidade: "%",
                    pendencia_id: "PEND-027"
                })}
            </div>
        </section>

        <!-- BLOCO SEPARADO: CAMADA PRIVADA (ANS/CNES) - FORA DA NOTA -->
        <section class="separated-layer-card separated-layer-card--priv" aria-label="Camada Privada">
            <div class="separated-layer-header">
                <h4 style="font-size: 0.95rem; font-weight: 700; color: #831843;">Camada Privada de Saúde (ANS / CNES)</h4>
                <span class="separated-tag separated-tag--priv">Fora da Nota</span>
            </div>
            <p style="font-size: 0.75rem; color: #831843;">
                Mede a taxa de cobertura de planos suplementares e infraestrutura exclusivamente privada não conveniada ao SUS.
            </p>
            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                ${renderAuditBadge(municipioData.camada_privada?.cobertura_planos, {
                    id: "PRIV.1",
                    nome: "Taxa de Cobertura de Planos Privados (ANS)",
                    unidade: "%",
                    pendencia_id: "PEND-032"
                })}
                ${renderAuditBadge(municipioData.camada_privada?.leitos_privados, {
                    id: "PRIV.2",
                    nome: "Leitos Privados Não-SUS por Mil Habitantes",
                    unidade: "leitos/mil hab",
                    pendencia_id: "PEND-032"
                })}
            </div>
        </section>
    `;

    // Exibe a gaveta
    drawer.classList.add("active");
    backdrop.classList.add("active");
}

export function closeDrawer() {
    const drawer = document.getElementById("municipio-drawer");
    const backdrop = document.getElementById("drawer-backdrop");
    if (drawer) drawer.classList.remove("active");
    if (backdrop) backdrop.classList.remove("active");
}

function renderNotaGeral(nota) {
    if (nota === null || nota === undefined) {
        return `<span class="nota-geral-badge nota-geral-badge--unclassified">Sem classificação</span>`;
    }
    return `<span class="nota-geral-badge">${nota.toFixed(1)}</span>`;
}

function formatNota(nota) {
    if (nota === null || nota === undefined) return "—";
    return typeof nota === "number" ? nota.toFixed(1) : nota;
}

function renderFaixaPosicao(min, max) {
    if (min === null || max === null || min === undefined || max === undefined) {
        return "Sob análise de sensibilidade";
    }
    return `${min}º a ${max}º lugar`;
}

function renderDimAccordion(dimId, dimNome, indicatorIds, municipioData) {
    const indicadoresMeta = (metaConfigCache?.indicadores || []).reduce((acc, ind) => {
        acc[ind.id] = ind;
        return acc;
    }, {});

    const cardsHtml = indicatorIds.map(id => {
        const item = municipioData.indicadores?.[id];
        const meta = indicadoresMeta[id] || { id, nome: id };
        return renderAuditBadge(item, meta);
    }).join("");

    return `
        <details class="dim-accordion" open>
            <summary class="dim-summary">
                <span>${dimId} — ${dimNome}</span>
            </summary>
            <div class="accordion-content">
                ${cardsHtml}
            </div>
        </details>
    `;
}
