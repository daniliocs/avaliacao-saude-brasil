/**
 * site/assets/js/downloads_view.js
 * 
 * Renderiza a página "Downloads & Dicionário"
 * Oferece links para download dos arquivos consolidados do pipeline
 * e o dicionário de variáveis completo.
 */

export function renderDownloadsView(metaBuild) {
    const container = document.getElementById("downloads-container");
    if (!container) return;

    container.innerHTML = `
        <div class="page-container">
            <header class="page-header">
                <h1 class="page-title">Downloads de Dados e Dicionário de Variáveis</h1>
                <p class="page-lead">
                    Acesso aberto e direto aos artefatos consolidados gerados pelo pipeline automatizado.
                </p>
            </header>

            <!-- Arquivos para Download -->
            <section class="content-section">
                <h2 class="section-title">Artefatos da Última Release</h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem;">
                    <div style="border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 1rem; background: var(--color-bg);">
                        <h3 style="font-size: 1rem; font-weight: 700;">Dimensão Municipal (CSV)</h3>
                        <p style="font-size: 0.8125rem; color: var(--color-text-muted); margin: 0.35rem 0 0.85rem 0;">
                            Tabela com os 5.570 municípios, chaves ibge7, ibge6, UFs e regiões.
                        </p>
                        <a href="data/processed/dim_municipio.csv" download class="badge badge--quality-high" style="text-decoration: none; padding: 0.4rem 0.8rem; display: inline-block;">Download .CSV</a>
                    </div>

                    <div style="border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 1rem; background: var(--color-bg);">
                        <h3 style="font-size: 1rem; font-weight: 700;">Dimensão Municipal (Parquet)</h3>
                        <p style="font-size: 0.8125rem; color: var(--color-text-muted); margin: 0.35rem 0 0.85rem 0;">
                            Formato colunar de alta performance para análise em Python/DuckDB/R.
                        </p>
                        <a href="data/processed/dim_municipio.parquet" download class="badge badge--quality-high" style="text-decoration: none; padding: 0.4rem 0.8rem; display: inline-block;">Download .Parquet</a>
                    </div>

                    <div style="border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 1rem; background: var(--color-bg);">
                        <h3 style="font-size: 1rem; font-weight: 700;">Payload do Mapa (JSON)</h3>
                        <p style="font-size: 0.8125rem; color: var(--color-text-muted); margin: 0.35rem 0 0.85rem 0;">
                            Dataset integral estruturado consumido pelo mapa e gaveta municipal.
                        </p>
                        <a href="data/releases/latest/mapa_resumo.json" download class="badge badge--quality-high" style="text-decoration: none; padding: 0.4rem 0.8rem; display: inline-block;">Download .JSON</a>
                    </div>

                    <div style="border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 1rem; background: var(--color-bg);">
                        <h3 style="font-size: 1rem; font-weight: 700;">Manifesto de Proveniência (SHA-256)</h3>
                        <p style="font-size: 0.8125rem; color: var(--color-text-muted); margin: 0.35rem 0 0.85rem 0;">
                            Hashes criptográficos de todos os insumos para reprodução auditável.
                        </p>
                        <a href="data/releases/latest/provenance_manifest.json" download class="badge badge--pending" style="text-decoration: none; padding: 0.4rem 0.8rem; display: inline-block;">Download .JSON</a>
                    </div>
                </div>
            </section>

            <!-- Dicionário de Variáveis -->
            <section class="content-section">
                <h2 class="section-title">Dicionário de Variáveis dos Datasets</h2>
                <div class="sources-table-wrapper">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Variável</th>
                                <th>Tipo</th>
                                <th>Descrição Conceitual</th>
                                <th>Dimensão</th>
                                <th>Fonte Oficial</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><code>ibge7</code></td>
                                <td>String(7)</td>
                                <td>Código oficial IBGE de 7 dígitos do município (Chave Primária)</td>
                                <td>Dimensional</td>
                                <td>IBGE</td>
                            </tr>
                            <tr>
                                <td><code>ibge6</code></td>
                                <td>String(6)</td>
                                <td>Código sem dígito verificador para junção com microdados do DATASUS</td>
                                <td>Dimensional</td>
                                <td>DATASUS</td>
                            </tr>
                            <tr>
                                <td><code>nota_geral</code></td>
                                <td>Float (0–100)</td>
                                <td>Nota sintética ponderada de saúde pública municipal</td>
                                <td>Índice</td>
                                <td>Cálculo próprio</td>
                            </tr>
                            <tr>
                                <td><code>d1_nota</code></td>
                                <td>Float (0–100)</td>
                                <td>Escore sintético da Dimensão 1 (Resultados em Saúde)</td>
                                <td>D1</td>
                                <td>SIM / SINASC</td>
                            </tr>
                            <tr>
                                <td><code>d2_nota</code></td>
                                <td>Float (0–100)</td>
                                <td>Escore sintético da Dimensão 2 (Atenção Primária)</td>
                                <td>D2</td>
                                <td>SIH / SINASC / PNI</td>
                            </tr>
                            <tr>
                                <td><code>d3_nota</code></td>
                                <td>Float (0–100)</td>
                                <td>Escore sintético da Dimensão 3 (Acesso e Estrutura)</td>
                                <td>D3</td>
                                <td>CNES / SISAB</td>
                            </tr>
                            <tr>
                                <td><code>faixa_posicao</code></td>
                                <td>String</td>
                                <td>Intervalo de classificação após teste de sensibilidade de pesos</td>
                                <td>Sensibilidade</td>
                                <td>Cálculo próprio</td>
                            </tr>
                            <tr>
                                <td><code>status</code></td>
                                <td>String</td>
                                <td>Classificação ('classificado' ou 'sem_classificacao')</td>
                                <td>Qualidade</td>
                                <td>Quality Gates</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    `;
}
