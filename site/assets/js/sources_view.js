/**
 * site/assets/js/sources_view.js
 * 
 * Renderiza dinamicamente a página "Fontes & Proveniência" a partir de meta_build.json
 * (derivado de sources/registry.yaml).
 * Garante que apenas fontes oficialmente registradas e catalogadas sejam apresentadas.
 */

export function renderSourcesView(metaBuild) {
    const container = document.getElementById("sources-container");
    if (!container || !metaBuild) return;

    const fontes = metaBuild.fontes || [];

    const rowsHtml = fontes.map(fonte => {
        const isEmRevisao = fonte.status === "em_revisao";
        const statusBadge = isEmRevisao 
            ? `<span class="badge badge--pending">Em Revisão</span>` 
            : `<span class="badge badge--quality-high">Ativo</span>`;

        return `
            <tr>
                <td>
                    <strong>${escapeHtml(fonte.id)}</strong>
                    <div style="font-size: 0.75rem; color: var(--color-text-subtle);">${escapeHtml(fonte.orgao || '')}</div>
                </td>
                <td>
                    <div style="font-weight: 600;">${escapeHtml(fonte.nome)}</div>
                    ${fonte.url_documentacao && fonte.url_documentacao !== 'A_VALIDAR' ? 
                        `<a href="${escapeHtml(fonte.url_documentacao)}" target="_blank" rel="noopener" style="font-size: 0.75rem; color: var(--color-primary);">Documentação Oficial ↗</a>` : 
                        `<span style="font-size: 0.75rem; color: var(--color-warning);">URL Documentação: A Validar</span>`
                    }
                </td>
                <td><span style="font-family: var(--font-mono); font-size: 0.8rem;">${escapeHtml(fonte.formato || 'A_VALIDAR')}</span></td>
                <td>${escapeHtml(fonte.periodicidade_publicacao || 'A_VALIDAR')}</td>
                <td>${escapeHtml(fonte.defasagem_tipica || 'A_VALIDAR')}</td>
                <td>${statusBadge}</td>
                <td>
                    ${fonte.pendencia_id ? `<span class="badge badge--pending">${escapeHtml(fonte.pendencia_id)}</span>` : '—'}
                </td>
            </tr>
        `;
    }).join("");

    container.innerHTML = `
        <div class="page-container">
            <header class="page-header">
                <h1 class="page-title">Registro Oficial de Fontes e Proveniência</h1>
                <p class="page-lead">
                    Catálogo de fontes de dados públicas do Sistema Único de Saúde (SUS) e órgãos oficiais integrados ao pipeline.
                    Apenas dados devidamente cadastrados em <code>sources/registry.yaml</code> são consumidos pelo sistema.
                </p>
            </header>

            <section class="content-section">
                <h2 class="section-title">Fontes Cadastradas no Pipeline (${fontes.length} fontes)</h2>
                <div class="sources-table-wrapper">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>ID / Órgão</th>
                                <th>Sistema / Documentação</th>
                                <th>Formato</th>
                                <th>Periodicidade</th>
                                <th>Defasagem Típica</th>
                                <th>Status</th>
                                <th>Rastreamento</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                    </table>
                </div>
            </section>
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
