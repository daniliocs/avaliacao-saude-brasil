/**
 * site/assets/js/drawer_municipio.js
 * 
 * Ficha Lateral do Município (Drawer)
 * Regras Inegociáveis Implementadas:
 * - Regra 3: Rastreabilidade total na UI (via audit_badge.js).
 * - Regra 4: A Nota Geral NUNCA aparece sozinha (D1, D2, D3 e faixa de sensibilidade no mesmo bloco).
 * - D4 (Contexto) e Camada Privada exibidos em blocos separados fora da nota (DEC-001).
 */

import { renderAuditBadge } from "./audit_badge.js?v=0.8.1";

let metaConfigCache = null;
let currentDrawerMunicipio = null;
let currentDrawerIndexMode = "oficial";

export function refreshDrawerIndexMode(indexMode) {
    currentDrawerIndexMode = indexMode || "oficial";
    const drawer = document.getElementById("municipio-drawer");
    if (drawer && drawer.classList.contains("active") && currentDrawerMunicipio) {
        openDrawer(currentDrawerMunicipio, currentDrawerIndexMode);
    }
}

export function initDrawer(metaConfig) {
    metaConfigCache = metaConfig;
    const drawer = document.getElementById("municipio-drawer");
    const backdrop = document.getElementById("drawer-backdrop");
    const btnClose = document.getElementById("btn-close-drawer");
    const dragHandle = drawer ? drawer.querySelector(".drawer-drag-handle") : null;

    if (backdrop) {
        backdrop.addEventListener("click", closeDrawer);
    }
    if (btnClose) {
        btnClose.addEventListener("click", closeDrawer);
    }
    if (dragHandle) {
        dragHandle.addEventListener("click", closeDrawer);
    }

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeDrawer();
        }
    });

    // Gestos de Toque (Mobile / Tablet / Telas Verticais):
    // Swipe-down fecha no modo bottom-sheet (mobile); Swipe-right fecha no modo lateral (desktop)
    if (drawer) {
        let touchStartX = 0;
        let touchStartY = 0;
        let touchStartTime = 0;

        drawer.addEventListener("touchstart", (e) => {
            if (!e.changedTouches || e.changedTouches.length === 0) return;
            touchStartX = e.changedTouches[0].screenX;
            touchStartY = e.changedTouches[0].screenY;
            touchStartTime = Date.now();
        }, { passive: true });

        drawer.addEventListener("touchend", (e) => {
            if (!e.changedTouches || e.changedTouches.length === 0) return;
            const touchEndX = e.changedTouches[0].screenX;
            const touchEndY = e.changedTouches[0].screenY;
            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;
            const elapsed = Date.now() - touchStartTime;

            const isMobile = window.innerWidth <= 768;
            const drawerBody = drawer.querySelector(".drawer-body");
            const atTop = !drawerBody || drawerBody.scrollTop <= 8;

            if (isMobile) {
                // Modo Bottom Sheet: arrastar para baixo fecha se estiver no topo ou iniciado no cabeçalho/alça
                const targetIsHeaderOrHandle = e.target.closest(".drawer-header") || e.target.closest(".drawer-drag-handle");
                if ((targetIsHeaderOrHandle || atTop) && deltaY > 60 && deltaY > Math.abs(deltaX) * 1.1) {
                    closeDrawer();
                }
            } else {
                // Modo Lateral Desktop: arrastar para a direita fecha
                if (deltaX > 75 && deltaX > Math.abs(deltaY) * 1.2) {
                    closeDrawer();
                }
            }
        }, { passive: true });
    }
}

export function openDrawer(municipioData, indexMode = null) {
    if (!municipioData) return;

    if (indexMode) {
        currentDrawerIndexMode = indexMode;
    }
    currentDrawerMunicipio = municipioData;
    const activeMode = currentDrawerIndexMode || "oficial";

    let displayTitle = "Índice Sintético de Saúde Pública";
    let scoreLabel = "Nota Geral (0–100)";
    let scoreVal = municipioData.nota_geral;
    let posNac = municipioData.posicao_nacional;
    let posEst = municipioData.posicao_estadual;
    let modeBadgeText = "Oficial (3D)";
    let modeBadgeStyle = "background:#0284c7; color:#fff;";

    if (activeMode === "integrado") {
        displayTitle = "Índice Integrado Completo (10% Onco + 15% Urgência)";
        scoreLabel = "Nota Integrada (0–100)";
        scoreVal = (municipioData.nota_integrada !== null && municipioData.nota_integrada !== undefined) 
            ? municipioData.nota_integrada 
            : municipioData.nota_geral;
        posNac = municipioData.posicao_nacional_integrada || municipioData.posicao_nacional;
        posEst = municipioData.posicao_estadual_integrada || municipioData.posicao_estadual;
        modeBadgeText = "🎗️⚡ Integrado (10% Onco)";
        modeBadgeStyle = "background:#7e22ce; color:#fff;";
    } else if (activeMode === "urgencia") {
        displayTitle = "Índice Expandido com Urgência (15% RUE)";
        scoreLabel = "Nota c/ Urgência (0–100)";
        scoreVal = (municipioData.nota_com_urgencia !== null && municipioData.nota_com_urgencia !== undefined) 
            ? municipioData.nota_com_urgencia 
            : municipioData.nota_geral;
        posNac = municipioData.posicao_nacional_urgencia || municipioData.posicao_nacional;
        posEst = municipioData.posicao_estadual_urgencia || municipioData.posicao_estadual;
        modeBadgeText = "⚡ Urgência (15%)";
        modeBadgeStyle = "background:#0284c7; color:#fff;";
    }

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
                <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                    <span class="score-card-title">${displayTitle}</span>
                    <span style="font-size: 0.72rem; font-weight: 700; padding: 2px 7px; border-radius: 4px; ${modeBadgeStyle}">
                        ${modeBadgeText}
                    </span>
                </div>
                <span class="badge ${municipioData.status === 'sem_classificacao' ? 'badge--pending' : 'badge--quality-high'}">
                    ${municipioData.status === 'sem_classificacao' ? 'Sem Classificação' : 'Classificado'}
                </span>
            </div>

            <div class="score-main-row">
                <div>
                    <span style="font-size: 0.75rem; text-transform: uppercase; color: var(--color-text-subtle); font-weight: 700; display: block;">${scoreLabel}</span>
                    ${renderNotaGeral(scoreVal)}
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

            <!-- COMPARATIVO DOS 3 MODELOS COM DESTAQUE NO ATIVO -->
            <div style="margin-top: 0.6rem; padding: 0.5rem 0.65rem; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 0.75rem;">
                <div style="font-weight: 700; color: #1e293b; margin-bottom: 0.35rem; display: flex; align-items: center; justify-content: space-between;">
                    <span>📊 Comparativo dos 3 Modelos de Nota:</span>
                    <span style="font-size: 0.68rem; color: #64748b; font-weight: normal;">Selecione no topo para alternar</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.4rem; text-align: center;">
                    <div style="padding: 0.35rem; border-radius: 6px; ${activeMode === 'oficial' ? 'background:#e0f2fe; border:1.8px solid #0284c7; box-shadow:0 1px 3px rgba(2,132,199,0.2);' : 'background:#ffffff; border:1px solid #e2e8f0;'}">
                        <span style="display:block; font-size:0.68rem; color:#475569; font-weight:${activeMode === 'oficial' ? '700' : '500'};">⚖️ Oficial (3D)</span>
                        <strong style="font-size:0.92rem; color:#0369a1;">${municipioData.nota_geral ? municipioData.nota_geral.toFixed(1) : '—'}</strong>
                        <span style="display:block; font-size:0.65rem; color:#64748b;">#${municipioData.posicao_nacional || '—'}º BR</span>
                    </div>
                    <div style="padding: 0.35rem; border-radius: 6px; ${activeMode === 'urgencia' ? 'background:#e0f2fe; border:1.8px solid #0284c7; box-shadow:0 1px 3px rgba(2,132,199,0.2);' : 'background:#ffffff; border:1px solid #e2e8f0;'}">
                        <span style="display:block; font-size:0.68rem; color:#0369a1; font-weight:${activeMode === 'urgencia' ? '700' : '500'};">⚡ +15% Urgência</span>
                        <strong style="font-size:0.92rem; color:#0369a1;">${municipioData.nota_com_urgencia ? municipioData.nota_com_urgencia.toFixed(1) : '—'}</strong>
                        <span style="display:block; font-size:0.65rem; color:#64748b;">#${municipioData.posicao_nacional_urgencia || '—'}º BR</span>
                    </div>
                    <div style="padding: 0.35rem; border-radius: 6px; ${activeMode === 'integrado' ? 'background:#f3e8ff; border:1.8px solid #7e22ce; box-shadow:0 1px 3px rgba(126,34,206,0.25);' : 'background:#ffffff; border:1px solid #e2e8f0;'}">
                        <span style="display:block; font-size:0.68rem; color:#6b21a8; font-weight:${activeMode === 'integrado' ? '700' : '500'};">🎗️⚡ Integrado (10% Onco)</span>
                        <strong style="font-size:0.92rem; color:#7e22ce;">${municipioData.nota_integrada ? municipioData.nota_integrada.toFixed(1) : '—'}</strong>
                        <span style="display:block; font-size:0.65rem; color:#7e22ce;">#${municipioData.posicao_nacional_integrada || '—'}º BR</span>
                    </div>
                </div>
            </div>

            <!-- Comparações de Ranking -->
            <div class="rankings-grid">
                <div>
                    <span style="color: var(--color-text-subtle);">Ranking Nacional (${modeBadgeText})</span>
                    <span class="rank-val">${posNac ? `#${posNac.toLocaleString("pt-BR")} de 5.570` : '—'}</span>
                </div>
                <div>
                    <span style="color: var(--color-text-subtle);">Ranking Estadual (${municipioData.uf})</span>
                    <span class="rank-val">${posEst ? `#${posEst.toLocaleString("pt-BR")} de ${(municipioData.total_uf || '—').toLocaleString("pt-BR")}` : '—'}</span>
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

        <!-- BLOCO DEDICADO: COBERTURA VACINAL COMPLETA & DESTAQUE HPV (PNI / MINISTÉRIO DA SAÚDE) -->
        ${renderVacinasCard(municipioData)}

        <!-- BLOCO DEDICADO: REDE DE URGÊNCIA & SAMU 192 (RUE) -->
        ${renderUrgenciaSamuCard(municipioData)}

        <!-- BLOCO DEDICADO: LINHA DE CUIDADO ONCOLÓGICO & CACON/UNACON (FASE 2) -->
        ${renderOncologiaCard(municipioData)}

        <!-- BLOCO DEDICADO: SUPORTE DIAGNÓSTICO & INFRAESTRUTURA CNES (EXAMES BÁSICOS E AVANÇADOS) -->
        ${renderCnesInfraCard(municipioData)}

        <!-- BLOCO DEDICADO: CIRURGIAS, ESPECIALISTAS & EXAMES (FASE 3) -->
        ${renderCirurgiasEspecialistasCard(municipioData)}

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

function renderVacinasCard(municipioData) {
    const vac = municipioData.detalhes_vacinas;
    if (!vac) return "";

    const cobComposta = typeof vac.cob_vac_composta === "number" ? vac.cob_vac_composta.toFixed(1) + "%" : "—";
    const escoreD2_3 = municipioData.indicadores?.D2_3?.escore !== undefined 
        ? (typeof municipioData.indicadores.D2_3.escore === "number" ? municipioData.indicadores.D2_3.escore.toFixed(1) : municipioData.indicadores.D2_3.escore)
        : (typeof municipioData.indicadores?.["D2.3"]?.escore === "number" ? municipioData.indicadores["D2.3"].escore.toFixed(1) : "—");

    const formatPct = (val) => typeof val === "number" ? val.toFixed(1) + "%" : "—";
    const statusMeta = (val, meta) => {
        if (typeof val !== "number") return `<span style="color:#64748b;">—</span>`;
        if (val >= meta) return `<span style="color:#15803d; font-weight:700;">✅ Meta (${val.toFixed(1)}%)</span>`;
        const diff = (meta - val).toFixed(1);
        return `<span style="color:#b45309; font-weight:600;">⚠️ Abaixo (${val.toFixed(1)}% / -${diff}%)</span>`;
    };

    // 6 Vacinas Estratégicas do 1º Ano (Composição D2.3)
    const polio = vac.polio;
    const penta = vac.penta;
    const tvd1 = vac.tvd1;
    const pneumo = vac.pneumo;
    const menin = vac.menin;
    const rota = vac.rota;

    // Complementares (Informativas)
    const bcg = vac.bcg;
    const hepa = vac.hepa;
    const hepb = vac.hepb;

    // HPV
    const hpvFem = vac.hpv_meninas;
    const hpvMasc = vac.hpv_meninos;
    const hpvTot = vac.hpv_total;
    const hpvDosesFem = vac.hpv_doses_meninas;
    const hpvDosesMasc = vac.hpv_doses_meninos;
    const hpvDosesTot = (hpvDosesFem || 0) + (hpvDosesMasc || 0);

    return `
        <section class="separated-layer-card separated-layer-card--vacinas" aria-label="Coberturas Vacinais e Imunização PNI">
            <div class="separated-layer-header">
                <div style="display: flex; align-items: center; gap: 0.45rem;">
                    <span style="font-size: 1.25rem;">💉</span>
                    <h4 style="font-size: 0.95rem; font-weight: 700; color: #15803d; margin: 0;">Imunização &amp; Cobertura Vacinal (PNI / DATASUS)</h4>
                </div>
                <span class="separated-tag separated-tag--vacinas">Média D2.3: ${cobComposta}</span>
            </div>

            <p style="font-size: 0.75rem; color: #166534; margin: 0; line-height: 1.4;">
                Avaliação do Programa Nacional de Imunizações (PNI): as <strong>6 vacinas estratégicas do 1º ano de vida</strong> compõem a nota oficial D2.3. As demais vacinas infantis e a imunização de adolescentes contra o HPV são monitoradas de forma puramente informativa.
            </p>

            <!-- PILAR 1: AS 6 VACINAS DO 1º ANO (ENTRAM NA NOTA D2.3) -->
            <div style="margin-top: 0.55rem; padding: 0.55rem 0.65rem; background: #ffffff; border: 1px solid #86efac; border-radius: 6px;">
                <div style="font-size: 0.78rem; font-weight: 700; color: #166534; margin-bottom: 0.35rem; display: flex; align-items: center; justify-content: space-between;">
                    <span>👶 1. Vacinas Estratégicas do 1º Ano de Vida (Composição D2.3):</span>
                    <span style="font-size: 0.72rem; color: #15803d; font-weight: 700;">Escore D2.3: ${escoreD2_3} / 100</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.35rem; font-size: 0.73rem;">
                    <div style="padding: 4px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>🟣 <strong>Poliomielite (VIP):</strong> ${statusMeta(polio, 95)}</span>
                    </div>
                    <div style="padding: 4px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>💉 <strong>Pentavalente:</strong> ${statusMeta(penta, 95)}</span>
                    </div>
                    <div style="padding: 4px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>🩹 <strong>Tríplice Viral D1:</strong> ${statusMeta(tvd1, 95)}</span>
                    </div>
                    <div style="padding: 4px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>🫁 <strong>Pneumocócica 10:</strong> ${statusMeta(pneumo, 95)}</span>
                    </div>
                    <div style="padding: 4px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>🧠 <strong>Meningocócica C:</strong> ${statusMeta(menin, 95)}</span>
                    </div>
                    <div style="padding: 4px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>💧 <strong>Rotavírus Humano:</strong> ${statusMeta(rota, 90)}</span>
                    </div>
                </div>
                <div style="font-size: 0.68rem; color: #64748b; margin-top: 0.35rem;">
                    * Metas PNI: 95% para Polio, Penta, Tríplice Viral, Pneumocócica e Meningo C; 90% para Rotavírus.
                </div>
            </div>

            <!-- PILAR 2: VACINAS COMPLEMENTARES DA PRIMEIRA INFÂNCIA (INFORMATIVAS - FORA DA NOTA) -->
            <div style="margin-top: 0.5rem; padding: 0.5rem 0.65rem; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;">
                <div style="font-size: 0.76rem; font-weight: 700; color: #475569; margin-bottom: 0.35rem; display: flex; align-items: center; justify-content: space-between;">
                    <span>🍼 2. Outras Coberturas Infantis (Acompanhamento Informativo):</span>
                    <span style="font-size: 0.68rem; color: #64748b; background: #f1f5f9; padding: 1px 5px; border-radius: 4px;">Fora da Nota D2.3</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.35rem; font-size: 0.72rem;">
                    <div style="padding: 4px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0; text-align: center;">
                        <span style="display: block; color: #64748b; font-size: 0.68rem;">BCG (Tuberculose)</span>
                        <strong style="color: #0f172a; font-size: 0.85rem;">${formatPct(bcg)}</strong>
                        <span style="display: block; font-size: 0.65rem; color: #64748b;">Meta: 90%</span>
                    </div>
                    <div style="padding: 4px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0; text-align: center;">
                        <span style="display: block; color: #64748b; font-size: 0.68rem;">Hepatite A</span>
                        <strong style="color: #0f172a; font-size: 0.85rem;">${formatPct(hepa)}</strong>
                        <span style="display: block; font-size: 0.65rem; color: #64748b;">Meta: 95%</span>
                    </div>
                    <div style="padding: 4px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0; text-align: center;">
                        <span style="display: block; color: #64748b; font-size: 0.68rem;">Hepatite B (&lt;30d)</span>
                        <strong style="color: #0f172a; font-size: 0.85rem;">${formatPct(hepb)}</strong>
                        <span style="display: block; font-size: 0.65rem; color: #64748b;">Meta: 95%</span>
                    </div>
                </div>
            </div>

            <!-- PILAR 3: DESTAQUE ESPECIAL HPV (9 A 14 ANOS) - MENINAS E MENINOS -->
            <div style="margin-top: 0.55rem; padding: 0.65rem 0.75rem; background: #faf5ff; border: 1.5px solid #c084fc; border-radius: 8px; box-shadow: 0 1px 3px rgba(192, 132, 252, 0.15);">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
                    <div style="display: flex; align-items: center; gap: 0.35rem;">
                        <span style="font-size: 1.1rem;">🌸</span>
                        <strong style="font-size: 0.85rem; color: #6b21a8;">Destaque: Vacinação contra HPV (9 a 14 anos)</strong>
                    </div>
                    <span style="font-size: 0.68rem; font-weight: 700; background: #ede9fe; color: #6b21a8; padding: 2px 6px; border-radius: 999px;">
                        Meta PNI: 90%
                    </span>
                </div>
                
                <p style="font-size: 0.72rem; color: #7e22ce; margin: 0 0 0.5rem 0; line-height: 1.35;">
                    Prevenção de cânceres de colo do útero, pênis, ânus e orofaringe (Ministério da Saúde / InfoMS — Dose única adotada em 2024). Segregação censitária por sexo:
                </p>

                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem;">
                    <!-- CARD MENINAS -->
                    <div style="background: #ffffff; border: 1.2px solid #f0abfc; border-radius: 6px; padding: 0.5rem 0.6rem; text-align: center;">
                        <span style="display: flex; align-items: center; justify-content: center; gap: 4px; font-size: 0.75rem; font-weight: 700; color: #86198f;">
                            👧 Meninas (9 a 14 anos)
                        </span>
                        <div style="font-size: 1.35rem; font-weight: 800; color: #a21caf; margin: 2px 0;">
                            ${formatPct(hpvFem)}
                        </div>
                        <div style="margin-bottom: 3px;">
                            ${typeof hpvFem === "number" && hpvFem >= 90 
                                ? '<span style="color:#15803d; font-size:0.68rem; font-weight:700;">✅ Meta Atingida (≥90%)</span>' 
                                : `<span style="color:#b45309; font-size:0.68rem; font-weight:600;">⚠️ ${typeof hpvFem === "number" ? (90 - hpvFem).toFixed(1) + "% abaixo da meta" : "Sem dado"}</span>`}
                        </div>
                        <div style="font-size: 0.67rem; color: #64748b;">
                            ${typeof hpvDosesFem === "number" ? hpvDosesFem.toLocaleString("pt-BR") + " doses aplicadas" : "—"}
                        </div>
                    </div>

                    <!-- CARD MENINOS -->
                    <div style="background: #ffffff; border: 1.2px solid #93c5fd; border-radius: 6px; padding: 0.5rem 0.6rem; text-align: center;">
                        <span style="display: flex; align-items: center; justify-content: center; gap: 4px; font-size: 0.75rem; font-weight: 700; color: #1d4ed8;">
                            👦 Meninos (9 a 14 anos)
                        </span>
                        <div style="font-size: 1.35rem; font-weight: 800; color: #1d4ed8; margin: 2px 0;">
                            ${formatPct(hpvMasc)}
                        </div>
                        <div style="margin-bottom: 3px;">
                            ${typeof hpvMasc === "number" && hpvMasc >= 90 
                                ? '<span style="color:#15803d; font-size:0.68rem; font-weight:700;">✅ Meta Atingida (≥90%)</span>' 
                                : `<span style="color:#b45309; font-size:0.68rem; font-weight:600;">⚠️ ${typeof hpvMasc === "number" ? (90 - hpvMasc).toFixed(1) + "% abaixo da meta" : "Sem dado"}</span>`}
                        </div>
                        <div style="font-size: 0.67rem; color: #64748b;">
                            ${typeof hpvDosesMasc === "number" ? hpvDosesMasc.toLocaleString("pt-BR") + " doses aplicadas" : "—"}
                        </div>
                    </div>
                </div>

                <!-- CONSOLIDAÇÃO TOTAL HPV -->
                <div style="margin-top: 0.45rem; padding: 0.35rem 0.5rem; background: #ffffff; border-radius: 4px; border: 1px solid #e9d5ff; display: flex; align-items: center; justify-content: space-between; font-size: 0.72rem;">
                    <span style="color: #6b21a8;">👥 <strong>Cobertura Consolidada (Ambos os Sexos):</strong></span>
                    <strong style="color: #581c87; font-size: 0.82rem;">${formatPct(hpvTot)}</strong>
                    <span style="color: #64748b; font-size: 0.67rem;">${typeof hpvDosesTot === "number" && hpvDosesTot > 0 ? hpvDosesTot.toLocaleString("pt-BR") + " doses totais" : ""}</span>
                </div>

                <div style="font-size: 0.67rem; color: #7e22ce; margin-top: 0.35rem; line-height: 1.35;">
                    ℹ️ <em>Informativo — Fora da composição da Nota Geral (D2.3). Fonte: Ministério da Saúde / InfoMS / DEMAS / SEIDIGI (SI-PNI + RNDS 2024).</em>
                </div>
            </div>
        </section>
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
    const distKm = typeof urg.dist_polo_km === "number" ? urg.dist_polo_km : 0;
    const tempoMin = urg.tempo_ambulancia_min ?? 12;
    const poloRef = urg.polo_hospitalar_ref || municipioData.nome;
    const fatorGH = typeof urg.fator_golden_hour === "number" ? (urg.fator_golden_hour * 100).toFixed(0) + "%" : "100%";
    const leitosLocais = urg.leitos_locais_sus ?? 0;
    const prontLocal = typeof urg.escore_prontidao_local === "number" ? urg.escore_prontidao_local.toFixed(1) : "—";
    const distLabel = distKm === 0 ? "0 km (Polo Local)" : `${distKm.toFixed(1)} km (~${tempoMin} min)`;

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

                <div class="urgencia-stat-box" style="border-color: #7dd3fc; background: #f0f9ff;">
                    <span class="urgencia-stat-box__title">⏱️ Distância ao Polo (Golden Hour)</span>
                    <span class="urgencia-stat-box__val">${distLabel}</span>
                    <span class="urgencia-stat-box__sub">Polo: <strong>${poloRef}</strong> &bull; Fator: ${fatorGH}</span>
                </div>

                <div class="urgencia-stat-box" style="border-color: #7dd3fc; background: #f0f9ff;">
                    <span class="urgencia-stat-box__title">🛏️ Leitos SUS &amp; Prontidão Local</span>
                    <span class="urgencia-stat-box__val">${leitosLocais.toLocaleString("pt-BR")} leitos locais</span>
                    <span class="urgencia-stat-box__sub">Escore Prontidão Local: <strong>${prontLocal} / 100</strong></span>
                </div>
            </div>

            <div class="urgencia-compare-pill">
                <strong>⚡ Comparativo de Modelos:</strong><br>
                &bull; <strong>Nota Geral Oficial (Padrão 3D):</strong> ${typeof municipioData.nota_geral === "number" ? municipioData.nota_geral.toFixed(1) : "—"} pts (#${municipioData.posicao_nacional || '—'}º BR)<br>
                &bull; <strong>Nota com Urgência (+15% RUE &amp; Golden Hour):</strong> ${typeof municipioData.nota_com_urgencia === "number" ? municipioData.nota_com_urgencia.toFixed(1) : "—"} pts (#${municipioData.posicao_nacional_urgencia || '—'}º BR) ${diffSign ? `[Variação: ${diffSign} pts]` : ''}
                <div style="font-size:0.7rem; color:var(--color-text-subtle); margin-top:3px;">
                    Fonte: DEMAS / SEIDIGI / Ministério da Saúde (Base Oficial 2024).
                </div>
            </div>
        </section>
    `;
}


function renderOncologiaCard(municipioData) {
    const onco = municipioData.oncologia_tfd;
    if (!onco) return "";

    const escoreVal = typeof onco.escore === "number" ? onco.escore.toFixed(1) : (typeof municipioData.escore_oncologia === "number" ? municipioData.escore_oncologia.toFixed(1) : "—");
    const rankVal = municipioData.rank_onco ? `#${municipioData.rank_onco.toLocaleString("pt-BR")}º no Brasil` : "—";
    
    const isPolo = onco.eh_polo_onco;
    const distKm = typeof onco.dist_cacon_km === "number" ? onco.dist_cacon_km : 0;
    const tempoMin = onco.tempo_cacon_min ?? 15;
    const caconRef = onco.cacon_referencia || "CACON/UNACON de Referência";
    const distLabel = isPolo ? "0 km (Centro CACON/UNACON Local)" : `${distKm.toFixed(1)} km (~${tempoMin} min de viagem)`;

    const pct60d = typeof onco.pct_60d_onco === "number" ? `${onco.pct_60d_onco.toFixed(1)}%` : "—";
    const pctConv = typeof onco.pct_conversao_trat === "number" ? `${onco.pct_conversao_trat.toFixed(1)}%` : "—";
    const pct60dEfet = typeof onco.pct_60d_sobre_diag === "number" ? `${onco.pct_60d_sobre_diag.toFixed(1)}%` : "—";
    const tempoMediano = typeof onco.tempo_mediano_onco_dias === "number" ? `${onco.tempo_mediano_onco_dias.toFixed(0)} dias` : "—";
    const pctFora = typeof onco.pct_tratamento_fora === "number" ? `${onco.pct_tratamento_fora.toFixed(1)}%` : "—";
    const pctPrecoce = typeof onco.pct_diagnostico_precoce === "number" ? `${onco.pct_diagnostico_precoce.toFixed(1)}%` : "—";
    const casosTotal = typeof onco.casos_total === "number" ? onco.casos_total.toLocaleString("pt-BR") : "0";
    const casosDiag = typeof onco.casos_diagnosticados === "number" ? onco.casos_diagnosticados.toLocaleString("pt-BR") : casosTotal;

    const tipoCentro = onco.polo_tipo_centro || (isPolo ? "CACON / UNACON" : "Polo Referenciado");
    const hasImuno = onco.polo_imunoterapia_alvo;
    const hasRadio = onco.polo_radio_avancada;
    const hasCirurg = onco.polo_cirurgia_onco;
    const hasPed = onco.polo_onco_pediatrica;
    const hasHemo = onco.polo_hematologia_tmo;

    let badgeColor = "#7c3aed";
    let badgeBg = "#f5f3ff";
    let badgeBorder = "#ddd6fe";
    let badgeLabel = "Regular";
    if (typeof onco.escore === "number") {
        if (onco.escore >= 80) { badgeLabel = "Excelente"; badgeColor = "#059669"; badgeBg = "#ecfdf5"; badgeBorder = "#a7f3d0"; }
        else if (onco.escore >= 65) { badgeLabel = "Bom"; badgeColor = "#2563eb"; badgeBg = "#eff6ff"; badgeBorder = "#bfdbfe"; }
        else if (onco.escore >= 50) { badgeLabel = "Moderado"; badgeColor = "#d97706"; badgeBg = "#fffbeb"; badgeBorder = "#fde68a"; }
        else { badgeLabel = "Crítico / Desassistido"; badgeColor = "#dc2626"; badgeBg = "#fef2f2"; badgeBorder = "#fecaca"; }
    }

    return `
        <section class="separated-layer-card separated-layer-card--onco" aria-label="Linha de Cuidado Oncológico e Alta Complexidade" style="border-left: 4px solid #7c3aed; background: #faf5ff;">
            <div class="separated-layer-header">
                <div style="display: flex; align-items: center; gap: 0.4rem;">
                    <span style="font-size: 1.15rem;">🎗️</span>
                    <h4 style="font-size: 0.95rem; font-weight: 700; color: #6b21a8; margin: 0;">Linha de Cuidado Oncológico &amp; CACON / UNACON</h4>
                </div>
                <span class="separated-tag" style="background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeBorder}; font-weight: 700;">
                    Escore Onco: ${escoreVal} / 100 (${badgeLabel})
                </span>
            </div>
            
            <p style="font-size: 0.75rem; color: #581c87; margin: 0;">
                Mapeamento da jornada oncológica (Painel-Oncologia Brasil / DATASUS Triênio 2021–2023): cumprimento da Lei dos 60 Dias (Lei 12.732/2012), tempo de espera até o 1º tratamento, dependência de Tratamento Fora de Domicílio (TFD) e distância viária até centros habilitados.
            </p>

            <div class="urgencia-stats-grid">
                <div class="urgencia-stat-box" style="border-color: #ddd6fe; background: #fff;">
                    <span class="urgencia-stat-box__title">⏳ Lei dos 60 Dias (Tratados vs Total)</span>
                    <span class="urgencia-stat-box__val" style="color: ${typeof onco.pct_60d_sobre_diag === 'number' && onco.pct_60d_sobre_diag >= 35 ? '#059669' : '#b45309'};">${pct60d} <span style="font-size:0.75rem; color:#64748b;">(${pct60dEfet} do total)</span></span>
                    <span class="urgencia-stat-box__sub">Acesso efetivo ao tratamento: <strong>${pctConv}</strong> (${casosTotal}/${casosDiag} diag.)</span>
                </div>

                <div class="urgencia-stat-box" style="border-color: #ddd6fe; background: #fff;">
                    <span class="urgencia-stat-box__title">📅 Tempo Mediano de Fila</span>
                    <span class="urgencia-stat-box__val" style="color: #6b21a8;">${tempoMediano}</span>
                    <span class="urgencia-stat-box__sub">Fila pós-biópsia até 1º tratamento (Mediana BR: 74 dias)</span>
                </div>

                <div class="urgencia-stat-box" style="border-color: #ddd6fe; background: #fff;">
                    <span class="urgencia-stat-box__title">🚐 Tratamento Fora do Município (TFD)</span>
                    <span class="urgencia-stat-box__val" style="color: ${isPolo ? '#059669' : '#475569'};">${pctFora}</span>
                    <span class="urgencia-stat-box__sub">${isPolo ? 'Centro Polo com retenção local' : 'Pacientes que precisam viajar para tratar'}</span>
                </div>

                <div class="urgencia-stat-box" style="border-color: #ddd6fe; background: #fff;">
                    <span class="urgencia-stat-box__title">🔬 Diagnóstico Precoce (Estádio I/II)</span>
                    <span class="urgencia-stat-box__val" style="color: #0369a1;">${pctPrecoce}</span>
                    <span class="urgencia-stat-box__sub">Tumores diagnosticados em fases iniciais</span>
                </div>

                <div class="urgencia-stat-box" style="border-color: #ddd6fe; background: #fff;">
                    <span class="urgencia-stat-box__title">🩺 Desfecho: Mortalidade Prematura</span>
                    <span class="urgencia-stat-box__val" style="color: ${typeof onco.tx_cancer_prem_bayes === 'number' && onco.tx_cancer_prem_bayes <= 110 ? '#059669' : '#b45309'};">${typeof onco.tx_cancer_prem_bayes === 'number' ? onco.tx_cancer_prem_bayes.toFixed(1) : '—'}</span>
                    <span class="urgencia-stat-box__sub">Óbitos de 30–69a / 100k hab. (SIM Triênio / CIR)</span>
                </div>

                <div class="urgencia-stat-box" style="border-color: #c084fc; background: #f3e8ff; grid-column: 1 / -1;">
                    <span class="urgencia-stat-box__title">🏥 Centro de Referência: ${caconRef}</span>
                    <span class="urgencia-stat-box__val" style="font-size: 0.92rem; color: #581c87;">${tipoCentro}</span>
                    <span class="urgencia-stat-box__sub">Distância rodoviária: <strong>${distLabel}</strong> &bull; Casos analisados: <strong>${casosTotal}</strong> &bull; Posição Onco: <strong>${rankVal}</strong></span>
                </div>
            </div>

            <!-- BLOCO DE TRATAMENTOS DE PONTA DISPONÍVEIS NO CENTRO DE REFERÊNCIA -->
            <div style="margin-top: 0.6rem; padding: 0.55rem 0.65rem; background: #ffffff; border: 1px solid #d8b4fe; border-radius: 6px;">
                <div style="font-size: 0.78rem; font-weight: 700; color: #581c87; margin-bottom: 0.4rem; display: flex; align-items: center; justify-content: space-between;">
                    <span>🔬 Terapias de Ponta no Centro (${caconRef}):</span>
                    <span style="font-size: 0.68rem; font-weight: 600; color: #7e22ce;">Habilitações CNES/MS</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.35rem; font-size: 0.73rem;">
                    <div style="padding: 3px 6px; border-radius: 4px; background: ${hasImuno ? '#ecfdf5' : '#fef2f2'}; border: 1px solid ${hasImuno ? '#a7f3d0' : '#fecaca'};">
                        <span>🧬 <strong>Imunoterapia:</strong> ${hasImuno ? '<span style="color:#059669; font-weight:700;">✅ Ativa no SUS</span>' : '<span style="color:#dc2626;">⚠️ Polo Terciário</span>'}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: ${hasImuno ? '#ecfdf5' : '#fef2f2'}; border: 1px solid ${hasImuno ? '#a7f3d0' : '#fecaca'};">
                        <span>🎯 <strong>Terapia Alvo:</strong> ${hasImuno ? '<span style="color:#059669; font-weight:700;">✅ Ativa no SUS</span>' : '<span style="color:#dc2626;">⚠️ Polo Terciário</span>'}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: ${hasRadio ? '#ecfdf5' : '#fef2f2'}; border: 1px solid ${hasRadio ? '#a7f3d0' : '#fecaca'};">
                        <span>⚡ <strong>Radioterapia (IMRT):</strong> ${hasRadio ? '<span style="color:#059669; font-weight:700;">✅ Ativa no SUS</span>' : '<span style="color:#dc2626;">⚠️ Sem Radioterapia</span>'}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: ${hasCirurg ? '#ecfdf5' : '#fef2f2'}; border: 1px solid ${hasCirurg ? '#a7f3d0' : '#fecaca'};">
                        <span>🔪 <strong>Cirurgia Oncológica:</strong> ${hasCirurg ? '<span style="color:#059669; font-weight:700;">✅ Alta Complex.</span>' : '<span style="color:#dc2626;">⚠️ Encaminhado</span>'}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: ${hasPed ? '#ecfdf5' : '#f8fafc'}; border: 1px solid ${hasPed ? '#a7f3d0' : '#e2e8f0'};">
                        <span>👶 <strong>Onco Pediátrica:</strong> ${hasPed ? '<span style="color:#059669; font-weight:700;">✅ Habilitada</span>' : '<span style="color:#64748b;">—</span>'}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: ${hasHemo ? '#ecfdf5' : '#f8fafc'}; border: 1px solid ${hasHemo ? '#a7f3d0' : '#e2e8f0'};">
                        <span>🩸 <strong>Hematologia &amp; TMO:</strong> ${hasHemo ? '<span style="color:#059669; font-weight:700;">✅ Habilitada</span>' : '<span style="color:#64748b;">—</span>'}</span>
                    </div>
                </div>
            </div>

            <!-- RAIO-X DO DESTINO DOS PACIENTES DIAGNOSTICADOS (FILA PÓS-60 DIAS E FILA OCULTA TRATAMENTO = 5) -->
            ${(() => {
                const p60 = typeof onco.pct_60d_sobre_diag === "number" ? onco.pct_60d_sobre_diag : 0;
                const pConv = typeof onco.pct_conversao_trat === "number" ? onco.pct_conversao_trat : 0;
                const pAtraso = Math.max(0, Number((pConv - p60).toFixed(1)));
                const pSemTrat = Math.max(0, Number((100 - pConv).toFixed(1)));
                return `
                <div style="margin-top: 0.55rem; padding: 0.55rem 0.65rem; background: #ffffff; border: 1px solid #d8b4fe; border-radius: 6px; font-size: 0.72rem; color: #334155;">
                    <div style="font-weight: 700; color: #581c87; margin-bottom: 0.35rem; display: flex; justify-content: space-between;">
                        <span>📊 Destino dos Pacientes após o Diagnóstico (${casosDiag} casos):</span>
                        <span style="color: #6b21a8;">Auditoria POBR / TCU</span>
                    </div>
                    <div style="display: flex; height: 10px; border-radius: 999px; overflow: hidden; background: #f1f5f9; margin-bottom: 0.45rem; border: 1px solid #cbd5e1;">
                        <div style="width: ${p60}%; background: #10b981;" title="Iniciam em até 60 dias: ${p60.toFixed(1)}%"></div>
                        <div style="width: ${pAtraso}%; background: #f59e0b;" title="Iniciam após 60 dias (atraso): ${pAtraso.toFixed(1)}%"></div>
                        <div style="width: ${pSemTrat}%; background: #ef4444;" title="Sem tratamento registrado no SUS (TRATAMENTO=5): ${pSemTrat.toFixed(1)}%"></div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.3rem; text-align: center; font-size: 0.69rem;">
                        <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 4px; padding: 3px 4px;">
                            <strong style="color: #047857; display: block; font-size: 0.8rem;">${p60.toFixed(1)}%</strong>
                            <span>Trataram ≤ 60d (no prazo)</span>
                        </div>
                        <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 4px; padding: 3px 4px;">
                            <strong style="color: #b45309; display: block; font-size: 0.8rem;">${pAtraso.toFixed(1)}%</strong>
                            <span>Trataram > 60d (fila tardia)</span>
                        </div>
                        <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 4px; padding: 3px 4px;">
                            <strong style="color: #b91c1c; display: block; font-size: 0.8rem;">${pSemTrat.toFixed(1)}%</strong>
                            <span>Sem registro SUS (cód. 5)</span>
                        </div>
                    </div>
                    <div style="margin-top: 0.35rem; font-size: 0.68rem; color: #64748b; line-height: 1.35;">
                        * <strong>Sem registro SUS (<code>TRATAMENTO = 5</code>):</strong> pacientes diagnosticados que falecem na fila antes da 1ª sessão, desistem pelas barreiras de TFD ou migram para rede privada/judicialização (Acórdão TCU 1.944/2019).
                    </div>
                </div>
                `;
            })()}

            <!-- RÉGUA DE CALIBRAÇÃO ABSOLUTA -->
            <div style="margin-top: 0.5rem; padding: 0.45rem 0.65rem; background: #fdf4ff; border: 1px solid #f0abfc; border-radius: 6px; font-size: 0.72rem; color: #581c87; line-height: 1.45;">
                ⚖️ <strong>Régua de Calibração Absoluta:</strong> A nota 100 representa o padrão-ouro inatingível (95%+ tratados em até 30 dias, diagnóstico precoce > 60%, alta conversão terapêutica e sobrevida padronizada, equivalente aos melhores centros mundiais). No SUS, escores acima de 60 já indicam alta eficiência assistencial.
            </div>

            <!-- COMPARATIVO DOS 3 MODELOS DE ÍNDICE -->
            <div class="urgencia-compare-pill" style="border-left: 3px solid #7c3aed; background: #ffffff; margin-top: 0.5rem;">
                <strong>⚡ Comparativo dos Modelos Sintéticos:</strong><br>
                &bull; <strong>Padrão Oficial (3D):</strong> ${typeof municipioData.nota_geral === "number" ? municipioData.nota_geral.toFixed(1) : "—"} pts (#${municipioData.posicao_nacional || '—'}º BR)<br>
                &bull; <strong>Com Urgência (15% RUE):</strong> ${typeof municipioData.nota_com_urgencia === "number" ? municipioData.nota_com_urgencia.toFixed(1) : "—"} pts (#${municipioData.posicao_nacional_urgencia || '—'}º BR)<br>
                &bull; <strong>Integrado Completo (+15% Urgência + 10% Onco):</strong> <strong style="color:#6b21a8; font-size:0.85rem;">${typeof municipioData.nota_integrada === "number" ? municipioData.nota_integrada.toFixed(1) : "—"} pts</strong> (#${municipioData.posicao_nacional_integrada || '—'}º BR)
                <div style="font-size:0.7rem; color:var(--color-text-subtle); margin-top:3px;">
                    Pesos do Modelo Integrado: 25% D1 (Resultados) + 25% D2 (APS) + 25% D3 (Estrutura) + 15% D5 (Urgência) + 10% D6 (Oncologia).
                </div>
            </div>
        </section>
    `;
}

function renderCnesInfraCard(municipioData) {
    const infra = municipioData.cnes_infra;
    if (!infra) return "";

    const escoreVal = typeof infra.escore_infra === "number" ? infra.escore_infra.toFixed(1) : "—";
    const notaBasico = typeof infra.infra_basico === "number" ? infra.infra_basico.toFixed(1) : "—";
    const notaAvancado = typeof infra.infra_avancado === "number" ? infra.infra_avancado.toFixed(1) : "—";
    const notaCapacidade = typeof infra.infra_capacidade === "number" ? infra.infra_capacidade.toFixed(1) : "—";

    const eqRx = infra.eq_raiox ?? 0;
    const eqUs = infra.eq_us ?? 0;
    const eqEcg = infra.eq_ecg ?? 0;
    const eqDesfib = infra.eq_desfib ?? 0;
    const eqMamo = infra.eq_mamografo ?? 0;

    const eqTomo = infra.eq_tomografo ?? 0;
    const eqRm = infra.eq_rm ?? 0;
    const eqHemo = infra.eq_hemodinamica ?? 0;
    const eqEndo = infra.eq_endoscopio ?? 0;

    const accTomo = typeof infra.acc_tomografo === "number" ? (infra.acc_tomografo * 100).toFixed(0) + "%" : "—";
    const accRm = typeof infra.acc_rm === "number" ? (infra.acc_rm * 100).toFixed(0) + "%" : "—";
    const accHemo = typeof infra.acc_hemodinamica === "number" ? (infra.acc_hemodinamica * 100).toFixed(0) + "%" : "—";
    const accEndo = typeof infra.acc_endoscopio === "number" ? (infra.acc_endoscopio * 100).toFixed(0) + "%" : "—";

    const leitosUti = infra.leitos_uti_adulto_sus ?? 0;
    const leitosCir = infra.leitos_cirurgicos_sus ?? 0;
    const psHosp = infra.ps_hospitalar_sus ?? 0;
    const unidMoveis = infra.unid_moveis_urgencia ?? 0;

    const statusBadge = (qty, labelOk, labelFalta) => {
        if (qty > 0) {
            return `<span style="color:#059669; font-weight:700;">✅ ${qty} (${labelOk})</span>`;
        }
        return `<span style="color:#dc2626; font-weight:600;">⚠️ 0 (${labelFalta})</span>`;
    };

    let badgeColor = "#0d9488";
    let badgeBg = "#f0fdfa";
    let badgeBorder = "#99f6e4";
    let badgeLabel = "Regular";
    if (typeof infra.escore_infra === "number") {
        if (infra.escore_infra >= 80) { badgeLabel = "Excelente"; badgeColor = "#059669"; badgeBg = "#ecfdf5"; badgeBorder = "#a7f3d0"; }
        else if (infra.escore_infra >= 60) { badgeLabel = "Bom"; badgeColor = "#0284c7"; badgeBg = "#f0f9ff"; badgeBorder = "#bae6fd"; }
        else if (infra.escore_infra >= 40) { badgeLabel = "Moderado"; badgeColor = "#d97706"; badgeBg = "#fffbeb"; badgeBorder = "#fde68a"; }
        else { badgeLabel = "Deficitário"; badgeColor = "#dc2626"; badgeBg = "#fef2f2"; badgeBorder = "#fecaca"; }
    }

    return `
        <section class="separated-layer-card separated-layer-card--infra" aria-label="Infraestrutura e Suporte Diagnóstico CNES" style="border-left: 4px solid #0d9488; background: #f0fdfa; margin-top: 1rem;">
            <div class="separated-layer-header">
                <div style="display: flex; align-items: center; gap: 0.4rem;">
                    <span style="font-size: 1.15rem;">🔬</span>
                    <h4 style="font-size: 0.95rem; font-weight: 700; color: #0f766e; margin: 0;">Suporte Diagnóstico &amp; Infraestrutura SUS (CNES)</h4>
                </div>
                <span class="separated-tag" style="background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeBorder}; font-weight: 700;">
                    Infra: ${escoreVal} / 100 (${badgeLabel})
                </span>
            </div>
            
            <p style="font-size: 0.75rem; color: #115e59; margin: 0;">
                Auditoria censitária de equipamentos e leitos em uso no SUS (microdados CNES/DATASUS 12/2023): disponibilidade local de exames básicos, acesso regionalizado a exames avançados e retaguarda hospitalar/cirúrgica.
            </p>

            <!-- SUB-PILAR 1: EXAMES BÁSICOS LOCAIS (30%) -->
            <div style="margin-top: 0.6rem; padding: 0.55rem 0.65rem; background: #ffffff; border: 1px solid #99f6e4; border-radius: 6px;">
                <div style="font-size: 0.78rem; font-weight: 700; color: #0f766e; margin-bottom: 0.4rem; display: flex; align-items: center; justify-content: space-between;">
                    <span>🩺 1. Exames Básicos Locais:</span>
                    <span style="font-size: 0.72rem; font-weight: 700; color: #0d9488;">Escore: ${notaBasico} / 100</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.35rem; font-size: 0.73rem;">
                    <div style="padding: 3px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>🩻 <strong>Raio-X SUS:</strong> ${statusBadge(eqRx, "local", "deslocamento")}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>🔊 <strong>Ultrassom SUS:</strong> ${statusBadge(eqUs, "local", "deslocamento")}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>📈 <strong>ECG SUS:</strong> ${statusBadge(eqEcg, "local", "deslocamento")}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>⚡ <strong>Desfibrilador:</strong> ${statusBadge(eqDesfib, "local", "ausente")}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0; grid-column: 1 / -1;">
                        <span>🎗️ <strong>Mamógrafo SUS:</strong> ${statusBadge(eqMamo, "local ativo", "polo regional")}</span>
                    </div>
                </div>
            </div>

            <!-- SUB-PILAR 2: EXAMES AVANÇADOS / ALTA COMPLEXIDADE (40%) -->
            <div style="margin-top: 0.55rem; padding: 0.55rem 0.65rem; background: #ffffff; border: 1px solid #99f6e4; border-radius: 6px;">
                <div style="font-size: 0.78rem; font-weight: 700; color: #0f766e; margin-bottom: 0.4rem; display: flex; align-items: center; justify-content: space-between;">
                    <span>🧠 2. Exames Avançados (Capacidade &amp; Acesso Regional):</span>
                    <span style="font-size: 0.72rem; font-weight: 700; color: #0d9488;">Escore: ${notaAvancado} / 100</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.35rem; font-size: 0.73rem;">
                    <div style="padding: 3px 6px; border-radius: 4px; background: ${eqTomo > 0 ? '#ecfdf5' : '#fffbeb'}; border: 1px solid ${eqTomo > 0 ? '#a7f3d0' : '#fde68a'};">
                        <span>🌀 <strong>Tomógrafo (TC):</strong> ${eqTomo > 0 ? `<strong style="color:#059669;">${eqTomo} local</strong>` : `<span style="color:#b45309;">Acesso: ${accTomo}</span>`}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: ${eqRm > 0 ? '#ecfdf5' : '#fffbeb'}; border: 1px solid ${eqRm > 0 ? '#a7f3d0' : '#fde68a'};">
                        <span>🧲 <strong>Ressonância (RM):</strong> ${eqRm > 0 ? `<strong style="color:#059669;">${eqRm} local</strong>` : `<span style="color:#b45309;">Acesso: ${accRm}</span>`}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: ${eqHemo > 0 ? '#ecfdf5' : '#fffbeb'}; border: 1px solid ${eqHemo > 0 ? '#a7f3d0' : '#fde68a'};">
                        <span>💉 <strong>Hemodinâmica:</strong> ${eqHemo > 0 ? `<strong style="color:#059669;">${eqHemo} local</strong>` : `<span style="color:#b45309;">Acesso: ${accHemo}</span>`}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: ${eqEndo > 0 ? '#ecfdf5' : '#fffbeb'}; border: 1px solid ${eqEndo > 0 ? '#a7f3d0' : '#fde68a'};">
                        <span>🔬 <strong>Endoscópio:</strong> ${eqEndo > 0 ? `<strong style="color:#059669;">${eqEndo} local</strong>` : `<span style="color:#b45309;">Acesso: ${accEndo}</span>`}</span>
                    </div>
                </div>
            </div>

            <!-- SUB-PILAR 3: CAPACIDADE HOSPITALAR & CIRÚRGICA (30%) -->
            <div style="margin-top: 0.55rem; padding: 0.55rem 0.65rem; background: #ffffff; border: 1px solid #99f6e4; border-radius: 6px;">
                <div style="font-size: 0.78rem; font-weight: 700; color: #0f766e; margin-bottom: 0.4rem; display: flex; align-items: center; justify-content: space-between;">
                    <span>🏥 3. Capacidade Hospitalar, Cirúrgica e Remoção:</span>
                    <span style="font-size: 0.72rem; font-weight: 700; color: #0d9488;">Escore: ${notaCapacidade} / 100</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.35rem; font-size: 0.73rem;">
                    <div style="padding: 3px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>🛏️ <strong>UTI Adulto SUS:</strong> ${leitosUti > 0 ? `<strong style="color:#059669;">${leitosUti.toLocaleString('pt-BR')} leitos</strong>` : '<span style="color:#dc2626;">0 leitos locais</span>'}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>🔪 <strong>Leitos Cirúrgicos:</strong> ${leitosCir > 0 ? `<strong style="color:#059669;">${leitosCir.toLocaleString('pt-BR')} leitos</strong>` : '<span style="color:#dc2626;">0 leitos locais</span>'}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>🚨 <strong>PS Hospitalar:</strong> ${psHosp > 0 ? `<strong style="color:#059669;">${psHosp} unidade(s)</strong>` : '<span style="color:#dc2626;">Sem PS hospitalar</span>'}</span>
                    </div>
                    <div style="padding: 3px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0;">
                        <span>🚐 <strong>Ambulâncias CNES:</strong> ${unidMoveis > 0 ? `<strong style="color:#059669;">${unidMoveis} unidade(s)</strong>` : '<span style="color:#dc2626;">Sem frota cadastrada</span>'}</span>
                    </div>
                </div>
            </div>

            <!-- NOTA METODOLÓGICA / DIAGNÓSTICO DO TERRITÓRIO -->
            <div style="margin-top: 0.5rem; padding: 0.45rem 0.65rem; background: #f0fdfa; border: 1px solid #99f6e4; border-radius: 6px; font-size: 0.71rem; color: #115e59; line-height: 1.45;">
                🔍 <strong>Diagnóstico Territorial:</strong> No Brasil, 56% das pequenas cidades (&lt;20k hab.) não possuem sequer Raio-X SUS e 76% das cidades médias (20k-100k hab.) não têm UTI Adulto. O escore de infraestrutura penaliza a ausência de retaguarda imediata e pondera o acesso aos polos terciários pelo decaimento gravitacional da distância rodoviária.
            </div>
        </section>
    `;
}

function renderCirurgiasEspecialistasCard(municipioData) {
    const f3 = municipioData.cirurgias_especialistas;
    if (!f3) return "";

    const escoreF3 = typeof f3.escore_fase3 === "number" ? f3.escore_fase3.toFixed(1) : "—";
    const escoreCir = typeof f3.escore_cirurgico === "number" ? f3.escore_cirurgico.toFixed(1) : "—";
    const escoreEsp = typeof f3.escore_especialistas === "number" ? f3.escore_especialistas.toFixed(1) : "—";
    const escoreBas = typeof f3.escore_exames_basicos === "number" ? f3.escore_exames_basicos.toFixed(1) : "—";
    const escoreAv = typeof f3.escore_exames_avancados === "number" ? f3.escore_exames_avancados.toFixed(1) : "—";

    const centroCirLocal = f3.eh_polo_cirurgico
        ? `<span class="badge badge--quality-high">✅ Centro Cirúrgico Local SUS</span>`
        : `<span class="badge badge--quality-warning">⚠️ Sem Centro Cirúrgico Local</span>`;

    const poloCirDist = f3.eh_polo_cirurgico
        ? `Sede Municipal`
        : `${f3.dist_polo_cirurgico_km || 0} km (${f3.tempo_polo_cirurgico_min || 15} min) até <strong>${f3.polo_cirurgico_ref || 'Polo Regional'}</strong>`;

    const poloTomoDist = f3.dist_tomografo_km === 0
        ? `Equipamento Local SUS`
        : `${f3.dist_tomografo_km || 0} km (${f3.tempo_tomografo_min || 15} min) até <strong>${f3.polo_tomografo_ref || 'Polo TC'}</strong>`;

    const poloRmDist = f3.dist_ressonancia_km === 0
        ? `Equipamento Local SUS`
        : `${f3.dist_ressonancia_km || 0} km (${f3.tempo_ressonancia_min || 15} min) até <strong>${f3.polo_ressonancia_ref || 'Polo RM'}</strong>`;

    const poloEspDist = f3.dist_especialistas_km === 0
        ? `Atendimento Local SUS`
        : `${f3.dist_especialistas_km || 0} km (${f3.tempo_especialistas_min || 15} min) até <strong>${f3.polo_especialistas_ref || 'Polo Especialistas'}</strong>`;

    return `
    <details class="accordion-item" style="border: 1px solid #0284c7; background: #f0f9ff; margin-bottom: 0.85rem;" open>
        <summary class="accordion-header" style="background: #e0f2fe; color: #0369a1; padding: 0.65rem 0.85rem; font-weight: 700; cursor: pointer; display: flex; justify-content: space-between; align-items: center;">
            <div style="display:flex; align-items:center; gap:0.4rem;">
                <span style="font-size:1.15rem;">🏥</span>
                <span>Cirurgias, Especialistas &amp; Suporte de Exames</span>
                <span style="font-size:0.68rem; background:#0284c7; color:#fff; padding:2px 6px; border-radius:10px; font-weight:600;">Fase 3</span>
            </div>
            <span style="font-size: 0.82rem; font-weight: 700; color: #0284c7;">
                Escore: ${escoreF3} / 100
            </span>
        </summary>
        <div class="accordion-body" style="padding: 0.85rem; background: #ffffff;">
            <p style="font-size: 0.78rem; color: var(--color-text-muted); margin-bottom: 0.75rem; line-height: 1.45;">
                Avaliação de acesso a procedimentos cirúrgicos do SUS, tempo de deslocamento até centros cirúrgicos, presença de médicos especialistas e resolutividade de exames diagnósticos básicos e avançados.
            </p>

            <!-- Bloco 1: Atenção Cirúrgica SUS -->
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:0.65rem; margin-bottom:0.65rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
                    <strong style="font-size:0.82rem; color:#0f172a;">🔪 Atenção Cirúrgica SUS</strong>
                    <span style="font-size:0.75rem; font-weight:700; color:#0284c7;">Escore: ${escoreCir}</span>
                </div>
                <div style="font-size:0.78rem; margin-bottom:0.25rem;">
                    Status: ${centroCirLocal}
                </div>
                <div style="font-size:0.76rem; color:#475569; margin-bottom:0.25rem;">
                    Polo Cirúrgico: ${poloCirDist}
                </div>
                <div style="font-size:0.76rem; color:#475569;">
                    Leitos Cirúrgicos SUS Locais: <strong>${f3.leitos_cirurgicos_sus || 0}</strong> ${f3.tx_leitos_cirurgicos_100k ? `(${f3.tx_leitos_cirurgicos_100k} / 100k hab)` : ''}
                </div>
            </div>

            <!-- Bloco 2: Acesso a Médicos Especialistas -->
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:0.65rem; margin-bottom:0.65rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
                    <strong style="font-size:0.82rem; color:#0f172a;">👨‍⚕️ Médicos Especialistas &amp; Consultas</strong>
                    <span style="font-size:0.75rem; font-weight:700; color:#0284c7;">Escore: ${escoreEsp}</span>
                </div>
                <div style="font-size:0.76rem; color:#475569; margin-bottom:0.25rem;">
                    Polo de Especialistas: ${poloEspDist}
                </div>
                <div style="font-size:0.74rem; color:var(--color-text-subtle);">
                    Cobre especialidades essenciais (Clínica Médica, Pediatria, Ginecologia/Obstetrícia, Cirurgia Geral e Ortopedia).
                </div>
            </div>

            <!-- Bloco 3: Suporte Diagnóstico (Exames Básicos e Avançados) -->
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:0.65rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
                    <strong style="font-size:0.82rem; color:#0f172a;">🔬 Suporte de Exames Diagnósticos</strong>
                    <span style="font-size:0.75rem; font-weight:700; color:#0284c7;">Básicos: ${escoreBas} | Avançados: ${escoreAv}</span>
                </div>
                <div style="font-size:0.76rem; color:#475569; margin-bottom:0.25rem;">
                    Tomografia Computadorizada (TC): ${poloTomoDist}
                </div>
                <div style="font-size:0.76rem; color:#475569;">
                    Ressonância Magnética (RM): ${poloRmDist}
                </div>
            </div>
        </div>
    </details>
    `;
}
