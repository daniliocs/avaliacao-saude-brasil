/**
 * site/assets/js/drawer_municipio.js
 * 
 * Ficha Lateral do Município (Drawer)
 * Regras Inegociáveis Implementadas:
 * - Regra 3: Rastreabilidade total na UI (via audit_badge.js).
 * - Regra 4: A Nota Geral NUNCA aparece sozinha (D1, D2, D3 e faixa de sensibilidade no mesmo bloco).
 * - D4 (Contexto) e Camada Privada exibidos em blocos separados fora da nota (DEC-001).
 */

import { renderAuditBadge } from "./audit_badge.js?v=0.5.0";

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

            <!-- Dimensões D1, D2, D3 e D5 (Urgência) -->
            <div class="dimensions-trio-grid" style="grid-template-columns: repeat(4, 1fr);">
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
                <div class="dim-item-box" style="border-left: 2px solid #0284c7;">
                    <span class="dim-item-label" style="color:#0369a1;">D5 — Urgência &amp; SAMU</span>
                    <span class="dim-item-value" style="color:#0369a1;">${formatNota(municipioData.d5_nota)}</span>
                </div>
            </div>

            <div style="margin-top: 0.5rem; padding: 0.4rem 0.6rem; background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 6px; font-size: 0.75rem; color: #0369a1; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.3rem;">
                <span><strong>⚡ Simulação com Urgência (10% RUE):</strong> ${municipioData.nota_com_urgencia ? municipioData.nota_com_urgencia.toFixed(1) : '—'} pts</span>
                <span>Posição com Urgência: <strong>#${municipioData.posicao_nacional_urgencia ? municipioData.posicao_nacional_urgencia.toLocaleString('pt-BR') : '—'}º</strong> no Brasil (${municipioData.posicao_estadual_urgencia ? '#' + municipioData.posicao_estadual_urgencia + 'º na UF' : ''})</span>
            </div>

            <!-- Comparações de Ranking -->
            <div class="rankings-grid">
                <div>
                    <span style="color: var(--color-text-subtle);">Ranking Nacional</span>
                    <span class="rank-val">${municipioData.posicao_nacional ? `#${municipioData.posicao_nacional.toLocaleString("pt-BR")} de 5.570` : '—'}</span>
                </div>
                <div>
                    <span style="color: var(--color-text-subtle);">Ranking Estadual (${municipioData.uf})</span>
                    <span class="rank-val">${municipioData.posicao_estadual ? `#${municipioData.posicao_estadual.toLocaleString("pt-BR")} de ${(municipioData.total_uf || '—').toLocaleString("pt-BR")}` : '—'}</span>
                </div>
                <div>
                    <span style="color: var(--color-text-subtle); display: inline-flex; align-items: center; gap: 4px;">
                        Grupo de Pares
                        <span class="info-tooltip-trigger" tabindex="0" role="button" aria-label="Informações sobre o Grupo de Pares" title="O que é o Grupo de Pares?&#10;Compara este município apenas com outros municípios do mesmo porte populacional (${municipioData.porte || 'mesmo porte'}, Censo 2022).&#10;Isso permite uma avaliação mais justa entre cidades de estrutura e capacidade orçamentária semelhantes.">ℹ️</span>
                    </span>
                    <span class="rank-val">${municipioData.posicao_grupo_pares ? `#${municipioData.posicao_grupo_pares.toLocaleString("pt-BR")} de ${(municipioData.total_grupo_pares || '—').toLocaleString("pt-BR")}` : '—'}</span>
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

        <!-- BLOCO DEDICADO: REDE DE URGÊNCIA & SAMU 192 (RUE) -->
        ${renderUrgenciaSamuCard(municipioData)}

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
                    nome: "Leitos Privados Não-SUS por 100 Mil Habitantes",
                    unidade: "leitos/100k hab",
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

function renderUrgenciaSamuCard(municipioData) {
    const urg = municipioData.urgencia_samu;
    if (!urg) return "";

    const escoreVal = typeof urg.escore === "number" ? urg.escore.toFixed(1) : (typeof municipioData.d5_nota === "number" ? municipioData.d5_nota.toFixed(1) : "—");
    const cobEfetiva = typeof urg.cob_samu_efetiva === "number" ? urg.cob_samu_efetiva.toFixed(1) + "%" : "—";
    const cobMun = typeof urg.cob_samu_mun === "number" ? urg.cob_samu_mun.toFixed(1) + "%" : "—";
    const cobReg = typeof urg.cob_samu_reg === "number" ? urg.cob_samu_reg.toFixed(1) + "%" : "—";
    const regNome = urg.no_regiao_saude || municipioData.regiao_saude || "Região de Saúde";

    const diffPts = (typeof municipioData.nota_com_urgencia === "number" && typeof municipioData.nota_geral === "number")
        ? (municipioData.nota_com_urgencia - municipioData.nota_geral).toFixed(1)
        : null;
    const diffSign = diffPts && Number(diffPts) > 0 ? `+${diffPts}` : diffPts;

    return `
        <section class="separated-layer-card separated-layer-card--urgencia" aria-label="Rede de Urgência e SAMU 192">
            <div class="separated-layer-header">
                <div style="display: flex; align-items: center; gap: 0.4rem;">
                    <span style="font-size: 1.15rem;">🚑</span>
                    <h4 style="font-size: 0.95rem; font-weight: 700; color: #0369a1; margin: 0;">Dimensão 5: Rede de Urgência &amp; SAMU 192 (RUE)</h4>
                </div>
                <span class="separated-tag separated-tag--urgencia">Escore: ${escoreVal} / 100</span>
            </div>
            
            <p style="font-size: 0.75rem; color: #0369a1; margin: 0;">
                Mapeamento das Unidades Móveis (USB/USA) e UPAs 24h na malha municipal e na Região de Saúde (<strong>${regNome}</strong>), garantindo socorro a agravos agudos (infartos, AVCs, traumas).
            </p>

            <div class="urgencia-stats-grid">
                <div class="urgencia-stat-box">
                    <span class="urgencia-stat-box__title">📡 Cobertura SAMU 192</span>
                    <span class="urgencia-stat-box__val">${cobEfetiva}</span>
                    <span class="urgencia-stat-box__sub">Local: ${cobMun} &bull; Região: ${cobReg}</span>
                </div>

                <div class="urgencia-stat-box">
                    <span class="urgencia-stat-box__title">🏥 UPAs 24h em Operação</span>
                    <span class="urgencia-stat-box__val">${urg.upa_mun ?? 0} UPA(s)</span>
                    <span class="urgencia-stat-box__sub">Região: ${urg.upa_reg ?? 0} UPAs (${typeof urg.tx_upa_reg_100k === "number" ? urg.tx_upa_reg_100k.toFixed(2) : "0"}/100k hab.)</span>
                </div>

                <div class="urgencia-stat-box">
                    <span class="urgencia-stat-box__title">🚐 Ambulâncias Básicas (USB)</span>
                    <span class="urgencia-stat-box__val">${urg.usb_mun ?? 0} USB</span>
                    <span class="urgencia-stat-box__sub">Região de Saúde: ${urg.usb_reg ?? 0} USBs ativas</span>
                </div>

                <div class="urgencia-stat-box">
                    <span class="urgencia-stat-box__title">🚨 UTIs Móveis / Avançadas (USA)</span>
                    <span class="urgencia-stat-box__val">${urg.usa_mun ?? 0} USA</span>
                    <span class="urgencia-stat-box__sub">Região de Saúde: ${urg.usa_reg ?? 0} USAs ativas</span>
                </div>
            </div>

            <div class="urgencia-compare-pill">
                <strong>⚡ Comparativo de Modelos:</strong><br>
                &bull; <strong>Nota Geral Oficial (Padrão 3D):</strong> ${typeof municipioData.nota_geral === "number" ? municipioData.nota_geral.toFixed(1) : "—"} pts (#${municipioData.posicao_nacional || '—'}º BR)<br>
                &bull; <strong>Nota com Urgência (+10% RUE):</strong> ${typeof municipioData.nota_com_urgencia === "number" ? municipioData.nota_com_urgencia.toFixed(1) : "—"} pts (#${municipioData.posicao_nacional_urgencia || '—'}º BR) ${diffSign ? `[Variação: ${diffSign} pts]` : ''}
                <div style="font-size:0.7rem; color:var(--color-text-subtle); margin-top:3px;">
                    Fonte: DEMAS / SEIDIGI / Ministério da Saúde (Base Oficial 2024).
                </div>
            </div>
        </section>
    `;
}
