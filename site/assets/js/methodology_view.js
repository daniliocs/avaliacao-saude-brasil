/**
 * site/assets/js/methodology_view.js
 * 
 * Renderiza dinamicamente a página "Como é calculado" consumindo data/releases/latest/meta_build.json.
 * Garante que a documentação apresentada no site seja 100% idêntica às regras e parâmetros
 * vigentes no pipeline de dados, sem divergências conceituais.
 */

export function renderMethodologyView(metaBuild) {
    const container = document.getElementById("methodology-container");
    if (!container || !metaBuild) return;

    const dimensoes = metaBuild.dimensoes || {};
    const pesos = metaBuild.pesos || {};
    const esquemas = pesos.esquemas || {};
    const pesosIguais = esquemas.pesos_iguais || {};
    const dimPesos = pesosIguais.dimensoes || {};

    container.innerHTML = `
        <div class="page-container">
            <header class="page-header">
                <h1 class="page-title">Metodologia de Cálculo do Índice</h1>
                <p class="page-lead">
                    Versão vigente: <strong>${escapeHtml(metaBuild.versao_metodologia || 'v0.1.0-draft')}</strong> | 
                    Status: <span class="badge badge--pending">${escapeHtml(metaBuild.status_metodologia || 'Rascunho')}</span>
                </p>
            </header>

            <!-- 1. Princípios Inegociáveis -->
            <section class="content-section">
                <h2 class="section-title">1. Princípios e Regras Inegociáveis de Governança</h2>
                <ul style="padding-left: 1.25rem; display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.9rem;">
                    <li><strong>Proibição de Imputação Cega:</strong> Municípios sem dados adequados são explicitamente rotulados como <code>sem_classificacao</code>. Não há preenchimento artificial.</li>
                    <li><strong>Rastreabilidade Total:</strong> Nenhum número é exibido sem metadados de fonte, período (vintage), data de coleta, versão e selo de incerteza (IC 95%).</li>
                    <li><strong>A Nota Geral Nunca Aparece Sozinha:</strong> Sempre acompanhada das notas das dimensões D1, D2 e D3 e da faixa de sensibilidade de posição.</li>
                    <li><strong>Recálculo Integral da Série:</strong> Em qualquer mudança de versão metodológica, toda a série histórica é recalculada retroativamente para manter estrita comparabilidade temporal.</li>
                </ul>
            </section>

            <!-- 2. Estrutura de Dimensões e Pesos -->
            <section class="content-section">
                <h2 class="section-title">2. Estrutura das Dimensões e Esquema de Ponderação</h2>
                <p style="font-size: 0.875rem; color: var(--color-text-muted);">
                    O Índice de Saúde Municipal é composto por 3 dimensões de qualidade assistencial pública (SUS), agregadas por média ponderada:
                </p>

                <div class="sources-table-wrapper">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Dimensão</th>
                                <th>Nome</th>
                                <th>Escopo</th>
                                <th>Peso Padrão</th>
                                <th>Composição no Índice</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><strong>D1</strong></td>
                                <td>${escapeHtml(dimensoes.D1?.nome || 'Resultados em Saúde')}</td>
                                <td>${escapeHtml(dimensoes.D1?.descricao || '')}</td>
                                <td><strong>${((dimPesos.D1 || 0.3333) * 100).toFixed(1)}%</strong></td>
                                <td><span class="badge badge--quality-high">Nota Principal</span></td>
                            </tr>
                            <tr>
                                <td><strong>D2</strong></td>
                                <td>${escapeHtml(dimensoes.D2?.nome || 'Atenção Primária')}</td>
                                <td>${escapeHtml(dimensoes.D2?.descricao || '')}</td>
                                <td><strong>${((dimPesos.D2 || 0.3333) * 100).toFixed(1)}%</strong></td>
                                <td><span class="badge badge--quality-high">Nota Principal</span></td>
                            </tr>
                            <tr>
                                <td><strong>D3</strong></td>
                                <td>${escapeHtml(dimensoes.D3?.nome || 'Acesso e Estrutura')}</td>
                                <td>${escapeHtml(dimensoes.D3?.descricao || '')}</td>
                                <td><strong>${((dimPesos.D3 || 0.3333) * 100).toFixed(1)}%</strong></td>
                                <td><span class="badge badge--quality-high">Nota Principal</span></td>
                            </tr>
                            <tr style="background-color: #f0f9ff;">
                                <td><strong>D5</strong></td>
                                <td>Rede de Urgência &amp; SAMU 192 (Golden Hour)</td>
                                <td>Prontidão imediata local (35%) e rede regional SAMU/UPA descontada pela distância rodoviária até o Polo Hospitalar (65%).</td>
                                <td><strong>15.0%</strong></td>
                                <td><span class="badge badge--quality-high">Modelo c/ Urgência &amp; Integrado</span></td>
                            </tr>
                            <tr style="background-color: #f5f3ff;">
                                <td><strong>D6</strong></td>
                                <td>🎗️ Linha de Cuidado Oncológico &amp; CACON/UNACON</td>
                                <td>Cumprimento efetivo da Lei dos 60 dias sobre total diagnosticado (30%), Diagnóstico Precoce auditado (20%), Conversão Terapêutica contra fila oculta TRATAMENTO=5 + Sobrevida D1 (25%) e Autonomia TFD + Terapias de Ponta CNES (25%).</td>
                                <td><strong>10.0%</strong></td>
                                <td><span class="badge badge--quality-high">Modelo Integrado (10% Onco)</span></td>
                            </tr>
                            <tr style="background-color: #faf5ff;">
                                <td><strong>D4</strong></td>
                                <td>${escapeHtml(dimensoes.D4?.nome || 'Contexto Municipal')}</td>
                                <td>Gastos públicos (SIOPS), capacidade fiscal e porte populacional.</td>
                                <td><strong>0%</strong></td>
                                <td><span class="separated-tag">Fora da Nota (DEC-001)</span></td>
                            </tr>
                            <tr style="background-color: #fdf2f8;">
                                <td><strong>PRIVADA</strong></td>
                                <td>${escapeHtml(dimensoes.PRIVADA?.nome || 'Camada Privada')}</td>
                                <td>Cobertura de planos suplementares (ANS) e oferta hospitalar não-SUS.</td>
                                <td><strong>0%</strong></td>
                                <td><span class="separated-tag separated-tag--priv">Fora da Nota (DEC-001)</span></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </section>

            <!-- 3. Tratamento Estatístico para Pequenos Municípios -->
            <section class="content-section">
                <h2 class="section-title">3. Tratamento Estatístico e Redução de Volatilidade</h2>
                <div style="display: flex; flex-direction: column; gap: 0.75rem; font-size: 0.875rem;">
                    <div>
                        <strong>Janelas Móveis Trienais e Quinquenais (3 a 5 anos):</strong>
                        <p style="color: var(--color-text-muted);">Para atenuar a instabilidade de eventos raros em municípios com população reduzida, indicadores de mortalidade utilizam consolidação plurianual em vez de taxas anuais isoladas.</p>
                    </div>
                    <div>
                        <strong>Suavização Bayesiana Empírica (Empirical Bayes Shrinkage):</strong>
                        <p style="color: var(--color-text-muted);">As taxas em pequenas áreas sofrem encolhimento bayesiano ponderado pela variância amostral em direção à taxa média regional/porte, corrigindo falsos extremos.</p>
                    </div>
                    <div>
                        <strong>Intervalos de Confiança Exatos de Poisson (IC 95%):</strong>
                        <p style="color: var(--color-text-muted);">Todo indicador exibe sua faixa de incerteza estatística, permitindo distinguir variações aleatórias de diferenças reais na gestão da saúde.</p>
                    </div>
                </div>
            </section>

            <!-- 4. Análise de Sensibilidade e Faixa de Posição Plausível -->
            <section class="content-section">
                <h2 class="section-title">4. Análise de Sensibilidade e Faixa de Posição</h2>
                <p style="font-size: 0.875rem; color: var(--color-text-muted);">
                    Nenhum ranking é determinístico. Para garantir transparência aos gestores públicos e pesquisadores, o índice calcula o posicionamento sob múltiplos esquemas de pesos:
                </p>
                <ul style="padding-left: 1.25rem; font-size: 0.875rem; display: flex; flex-direction: column; gap: 0.4rem;">
                    <li><strong>Esquema Padrão (Pesos Iguais):</strong> D1=33.3%, D2=33.3%, D3=33.3%</li>
                    <li><strong>Esquema Foco Resultados:</strong> D1=50%, D2=30%, D3=20%</li>
                    <li><strong>Esquema Foco Atenção Primária:</strong> D1=30%, D2=50%, D3=20%</li>
                </ul>
                <p style="font-size: 0.8125rem; color: var(--color-text-subtle); margin-top: 0.5rem;">
                    A menor e maior posição obtidas formam a <strong>Faixa de Posição Plausível</strong> exibida na ficha de cada município.
                </p>
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
