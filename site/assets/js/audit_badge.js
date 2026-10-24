/**
 * site/assets/js/audit_badge.js
 * 
 * Regra Inegociável 3: Rastreabilidade Total na UI.
 * Nenhum componente visual no front-end pode renderizar um número sem exibir junto:
 * - fonte
 * - período (vintage)
 * - data_coleta
 * - versao_metodologia
 * - indicador de qualidade/incerteza (IC 95% + selo)
 * 
 * Se qualquer um desses metadados for null ou indefinido, o componente renderiza obrigatoriamente
 * o estado "Sem classificação / Aguardando validação de fonte".
 */

/**
 * Renderiza o bloco de auditoria e qualidade de um indicador.
 * 
 * @param {Object} item Objeto contendo os dados do indicador
 * @param {number|null} item.valor Valor calculado / taxa suavizada
 * @param {number|null} item.taxa_bruta Taxa observada bruta
 * @param {Array<number>|null} item.ic_95 Intervalo de confiança [min, max]
 * @param {string|null} item.fonte_id Identificador da fonte registrada
 * @param {string|null} item.periodo_vintage Ano ou triênio de referência do dado
 * @param {string|null} item.data_coleta Data ISO de extração
 * @param {string|null} item.versao_metodologia Versão da metodologia
 * @param {string|null} item.qualidade_dado Selo de adequação ('alta', 'alerta', 'A_VALIDAR')
 * @param {Object} [metaConfig] Metadados complementares (nome do indicador, unidade, etc)
 * @returns {string} Fragmento HTML do componente
 */
export function renderAuditBadge(item, metaConfig = {}) {
    const nomeIndicador = metaConfig.nome || metaConfig.id || "Indicador";
    const unidade = metaConfig.unidade || "";
    const pendenciaId = metaConfig.pendencia_id || "";

    // Checagem rigorosa: Se o valor for null ou qualquer metadado crítico for nulo/inválido
    const isUnclassified = !item ||
        item.valor === null ||
        item.valor === undefined ||
        !item.fonte_id ||
        !item.periodo_vintage ||
        !item.data_coleta ||
        !item.versao_metodologia ||
        item.qualidade_dado === "A_VALIDAR" ||
        item.qualidade_dado === null;

    if (isUnclassified) {
        return `
            <div class="audit-card audit-card--unclassified" data-indicator="${metaConfig.id || ''}">
                <div class="audit-card__header">
                    <span class="audit-card__title">${escapeHtml(nomeIndicador)}</span>
                    <span class="badge badge--pending" title="Aguardando validação oficial da fonte">Aguardando Validação</span>
                </div>
                <div class="audit-card__body">
                    <div class="audit-unclassified-notice">
                        <span class="audit-icon" aria-hidden="true">⚠️</span>
                        <div>
                            <strong>Sem classificação / Aguardando validação de fonte</strong>
                            <p class="audit-subtext">Este indicador permanece desprovido de escore numérico conforme a Seção 0 da especificação (Proibido inventar dados sem fonte oficial confirmada).</p>
                        </div>
                    </div>
                </div>
                <div class="audit-card__footer">
                    <span class="meta-tag"><strong>Fonte preliminar:</strong> ${escapeHtml(item?.fonte_id || metaConfig.fontes?.join(', ') || 'A validar')}</span>
                    ${pendenciaId ? `<span class="meta-tag meta-tag--pendencia"><a href="https://github.com" target="_blank" rel="noopener">Pendência: ${escapeHtml(pendenciaId)}</a></span>` : ''}
                </div>
            </div>
        `;
    }

    // Se todos os metadados estiverem válidos e confirmados
    const valorFormatado = typeof item.valor === "number" ? item.valor.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 2 }) : item.valor;
    const taxaBrutaFormatada = typeof item.taxa_bruta === "number" ? item.taxa_bruta.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 2 }) : "—";
    
    let icFormatado = "—";
    if (Array.isArray(item.ic_95) && item.ic_95.length === 2 && item.ic_95[0] !== null) {
        icFormatado = `[${item.ic_95[0].toFixed(1)} – ${item.ic_95[1].toFixed(1)}]`;
    }

    let seloQualidade = "badge--quality-warning";
    let textoQualidade = "Alerta de Qualidade";
    if (item.qualidade_dado === "alta") {
        seloQualidade = "badge--quality-high";
        textoQualidade = "Precisão Alta";
    } else if (item.qualidade_dado === "media") {
        seloQualidade = "badge--quality-high";
        textoQualidade = "Precisão Moderada";
    } else if (item.qualidade_dado === "baixa") {
        seloQualidade = "badge--quality-warning";
        textoQualidade = "Baixa Precisão (poucos eventos)";
    }

    const fonteExibicao = item.fonte_detalhe
        ? `${item.fonte_id} (${item.fonte_detalhe})`
        : item.fonte_id;

    const papelBadge = item.papel_na_nota === "informativo"
        ? `<span class="badge badge--pending" style="margin-left: 0.4rem;">Informativo (peso 0)</span>`
        : "";

    return `
        <div class="audit-card" data-indicator="${metaConfig.id || ''}">
            <div class="audit-card__header">
                <span class="audit-card__title">${escapeHtml(nomeIndicador)}${papelBadge}</span>
                <span class="badge ${seloQualidade}">${textoQualidade}</span>
            </div>
            
            <div class="audit-card__metrics">
                <div class="metric-block metric-block--main">
                    <span class="metric-label">Valor / Taxa Suavizada</span>
                    <span class="metric-value">${valorFormatado} <small>${escapeHtml(unidade)}</small></span>
                </div>
                <div class="metric-block">
                    <span class="metric-label">Taxa Bruta</span>
                    <span class="metric-value">${taxaBrutaFormatada}</span>
                </div>
                <div class="metric-block">
                    <span class="metric-label">IC 95%</span>
                    <span class="metric-value">${icFormatado}</span>
                </div>
            </div>

            <div class="audit-card__provenance">
                <div class="provenance-grid">
                    <div><strong>Fonte:</strong> <span class="provenance-val">${escapeHtml(fonteExibicao)}</span></div>
                    <div><strong>Período (Vintage):</strong> <span class="provenance-val">${escapeHtml(item.periodo_vintage)}</span></div>
                    <div><strong>Data de Coleta:</strong> <span class="provenance-val">${escapeHtml(item.data_coleta)}</span></div>
                    <div><strong>Versão Metodologia:</strong> <span class="provenance-val">${escapeHtml(item.versao_metodologia)}</span></div>
                </div>
            </div>
        </div>
    `;
}

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
