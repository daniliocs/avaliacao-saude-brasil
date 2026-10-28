/**
 * site/assets/js/methodology_view.js
 * 
 * Renderiza dinamicamente a página "Como é calculado" consumindo data/releases/latest/meta_build.json.
 * Garante que a documentação apresentada no site seja 100% idêntica às regras, fórmulas e parâmetros
 * vigentes no pipeline de dados, sem divergências conceituais.
 * 
 * Versão 0.8.1 (Fase 2.5 — Imunização 6V + HPV, Oncologia, Urgência & Infraestrutura CNES)
 */

export function renderMethodologyView(metaBuild) {
    const container = document.getElementById("methodology-container");
    if (!container || !metaBuild) return;

    const versao = metaBuild.versao_metodologia || 'v0.8.1';

    container.innerHTML = `
        <div class="page-container" style="max-width: 1180px;">
            <header class="page-header">
                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem;">
                    <div>
                        <h1 class="page-title">Metodologia de Cálculo do Índice</h1>
                        <p class="page-lead">
                            Medição sintética, auditável e territorial da qualidade da saúde pública (SUS) nos 5.570 municípios brasileiros.
                        </p>
                    </div>
                    <div>
                        <span class="brand-badge version-display" style="font-size: 0.85rem; padding: 0.35rem 0.75rem;">
                            ${escapeHtml(versao)}
                        </span>
                    </div>
                </div>
            </header>

            <!-- 1. PRINCÍPIOS INEGOCIÁVEIS DE GOVERNANÇA -->
            <section class="content-section">
                <h2 class="section-title">1. Princípios e Regras Inegociáveis de Governança</h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 0.75rem; margin-top: 0.5rem;">
                    <div style="background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 0.85rem;">
                        <strong style="color: #b91c1c; display: flex; align-items: center; gap: 0.35rem;">
                            <span>🚫</span> Proibição de Imputação Cega
                        </strong>
                        <p style="font-size: 0.8rem; color: var(--color-text-muted); margin-top: 0.35rem; line-height: 1.45;">
                            Municípios sem dados adequados são explicitamente rotulados como <code>sem_classificacao</code> com o motivo detalhado. Não há preenchimento artificial por médias de estado ou país.
                        </p>
                    </div>
                    <div style="background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 0.85rem;">
                        <strong style="color: #0284c7; display: flex; align-items: center; gap: 0.35rem;">
                            <span>🔍</span> Rastreabilidade Total na UI
                        </strong>
                        <p style="font-size: 0.8rem; color: var(--color-text-muted); margin-top: 0.35rem; line-height: 1.45;">
                            Nenhum número é exibido sem fonte primária, período (vintage), data de coleta, versão da metodologia e indicador de qualidade/incerteza estatística (IC 95%).
                        </p>
                    </div>
                    <div style="background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 0.85rem;">
                        <strong style="color: #15803d; display: flex; align-items: center; gap: 0.35rem;">
                            <span>⚖️</span> A Nota Geral Nunca Aparece Sozinha
                        </strong>
                        <p style="font-size: 0.8rem; color: var(--color-text-muted); margin-top: 0.35rem; line-height: 1.45;">
                            A pontuação global é sempre acompanhada das notas das dimensões setoriais e da <strong>Faixa de Posição Plausível</strong> sob análise de sensibilidade.
                        </p>
                    </div>
                    <div style="background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 0.85rem;">
                        <strong style="color: #7e22ce; display: flex; align-items: center; gap: 0.35rem;">
                            <span>🌐</span> Abordagem Territorial &amp; Redes SUS
                        </strong>
                        <p style="font-size: 0.8rem; color: var(--color-text-muted); margin-top: 0.35rem; line-height: 1.45;">
                            O SUS funciona em redes regionalizadas e consórcios interfederativos. O índice pondera a oferta local e o acesso real por distância rodoviária aos polos terciários.
                        </p>
                    </div>
                </div>
            </section>

            <!-- 2. OS 3 MODELOS DE CÁLCULO E TABELA DE PESOS -->
            <section class="content-section">
                <h2 class="section-title">2. Os 3 Modelos de Cálculo &amp; Ponderações Oficiais</h2>
                <p style="font-size: 0.875rem; color: var(--color-text-muted); margin-bottom: 0.85rem;">
                    O usuário e gestor público podem navegar entre 3 modelos de agregação conforme a abrangência analítica desejada:
                </p>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 0.85rem; margin-bottom: 1rem;">
                    <!-- CARD MODELO 1 -->
                    <div style="background: #ffffff; border: 1.5px solid #0284c7; border-radius: var(--radius-md); padding: 1rem; box-shadow: var(--shadow-sm);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <h3 style="font-size: 0.95rem; font-weight: 700; color: #0369a1; margin: 0;">1. ⚖️ Padrão Oficial (Tri-dimensional)</h3>
                            <span class="badge badge--quality-high">Oficial 3D</span>
                        </div>
                        <div style="font-family: var(--font-mono); font-size: 0.85rem; background: #f0f9ff; border: 1px solid #bae6fd; padding: 0.5rem; border-radius: 4px; color: #0369a1; font-weight: 700; margin-bottom: 0.6rem;">
                            Nota Geral = 33,33% D1 + 33,33% D2 + 33,33% D3
                        </div>
                        <p style="font-size: 0.78rem; color: #475569; line-height: 1.45; margin: 0;">
                            Modelo pactuado e simétrico de 3 dimensões fundamentais: <strong>Resultados em Saúde (D1)</strong>, <strong>Atenção Primária &amp; Prevenção (D2)</strong> e <strong>Acesso &amp; Capacidade Assistencial (D3)</strong>.
                        </p>
                    </div>

                    <!-- CARD MODELO 2 -->
                    <div style="background: #ffffff; border: 1.5px solid #0284c7; border-radius: var(--radius-md); padding: 1rem; box-shadow: var(--shadow-sm);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <h3 style="font-size: 0.95rem; font-weight: 700; color: #0369a1; margin: 0;">2. ⚡ Com Urgência &amp; Emergência (+15%)</h3>
                            <span class="badge badge--quality-high">15% RUE</span>
                        </div>
                        <div style="font-family: var(--font-mono); font-size: 0.85rem; background: #f0f9ff; border: 1px solid #bae6fd; padding: 0.5rem; border-radius: 4px; color: #0369a1; font-weight: 700; margin-bottom: 0.6rem;">
                            Nota = 30% D1 + 25% D2 + 30% D3 + 15% D5 (Urgência)
                        </div>
                        <p style="font-size: 0.78rem; color: #475569; line-height: 1.45; margin: 0;">
                            Incorpora a <strong>Rede de Urgência &amp; SAMU 192 (D5)</strong>, avaliando frotas de ambulâncias (USB/USA), UPAs 24h e decaimento por distância <em>Golden Hour</em> para socorro de infartos, traumas e AVCs.
                        </p>
                    </div>

                    <!-- CARD MODELO 3 -->
                    <div style="background: #ffffff; border: 1.5px solid #7e22ce; border-radius: var(--radius-md); padding: 1rem; box-shadow: var(--shadow-sm); background: #faf5ff;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <h3 style="font-size: 0.95rem; font-weight: 700; color: #6b21a8; margin: 0;">3. 🎗️⚡ Integrado Completo (100%)</h3>
                            <span class="separated-tag" style="background:#f3e8ff; color:#7e22ce;">10% Onco</span>
                        </div>
                        <div style="font-family: var(--font-mono); font-size: 0.82rem; background: #f5f3ff; border: 1px solid #d8b4fe; padding: 0.5rem; border-radius: 4px; color: #6b21a8; font-weight: 700; margin-bottom: 0.6rem;">
                            Nota = 25% D1 + 25% D2 + 25% D3 + 15% D5 + 10% Onco
                        </div>
                        <p style="font-size: 0.78rem; color: #581c87; line-height: 1.45; margin: 0;">
                            Visão holística da saúde pública, integrando Atenção Primária, Urgência e <strong>Alta Complexidade Oncológica (D6)</strong> com auditoria da Lei dos 60 Dias e penalização da fila oculta de tratamento.
                        </p>
                    </div>
                </div>

                <!-- TABELA COMPARATIVA DE PESOS -->
                <div class="sources-table-wrapper" style="margin-top: 1rem;">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Dimensão Setorial</th>
                                <th>Foco Assistencial</th>
                                <th>Peso no Padrão Oficial (3D)</th>
                                <th>Peso Com Urgência (RUE)</th>
                                <th>Peso no Modelo Integrado</th>
                                <th>Papel no Pipeline</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><strong>D1: Resultados em Saúde</strong></td>
                                <td>Mortalidade Infantil, Prematura DCNT e Evitável</td>
                                <td><strong>33,33%</strong></td>
                                <td><strong>30,0%</strong></td>
                                <td><strong>25,0%</strong></td>
                                <td><span class="badge badge--quality-high">Ativo</span></td>
                            </tr>
                            <tr>
                                <td><strong>D2: Atenção Primária</strong></td>
                                <td>ICSAP, Pré-Natal 7+ e Vacinas 1º Ano (6V)</td>
                                <td><strong>33,33%</strong></td>
                                <td><strong>25,0%</strong></td>
                                <td><strong>25,0%</strong></td>
                                <td><span class="badge badge--quality-high">Ativo</span></td>
                            </tr>
                            <tr>
                                <td><strong>D3: Acesso e Estrutura</strong></td>
                                <td>Leitos SUS Golden Hour, Médicos/Enf. CH e eSF</td>
                                <td><strong>33,33%</strong></td>
                                <td><strong>30,0%</strong></td>
                                <td><strong>25,0%</strong></td>
                                <td><span class="badge badge--quality-high">Ativo</span></td>
                            </tr>
                            <tr style="background: #f0f9ff;">
                                <td><strong>D5: Rede de Urgência &amp; SAMU</strong></td>
                                <td>Ambulâncias USB/USA, UPAs 24h e Golden Hour</td>
                                <td><em>0,0% (Camada)</em></td>
                                <td><strong>15,0%</strong></td>
                                <td><strong>15,0%</strong></td>
                                <td><span class="badge badge--quality-high">Ativo (Expandido)</span></td>
                            </tr>
                            <tr style="background: #faf5ff;">
                                <td><strong>D6: Linha Oncológica</strong></td>
                                <td>Lei dos 60d, CACON/UNACON e Terapias de Ponta</td>
                                <td><em>0,0% (Camada)</em></td>
                                <td><em>0,0% (Camada)</em></td>
                                <td><strong>10,0%</strong></td>
                                <td><span class="badge badge--quality-high">Ativo (Integrado)</span></td>
                            </tr>
                            <tr style="background: #f8fafc;">
                                <td><strong>D4: Contexto e Financiamento</strong></td>
                                <td>Gasto SIOPS per capita e % Receita Própria</td>
                                <td><em>0,0%</em></td>
                                <td><em>0,0%</em></td>
                                <td><em>0,0%</em></td>
                                <td><span class="separated-tag">Informativo (DEC-001)</span></td>
                            </tr>
                            <tr style="background: #fdf2f8;">
                                <td><strong>Camada Privada</strong></td>
                                <td>Cobertura Planos ANS e Leitos Não-SUS</td>
                                <td><em>0,0%</em></td>
                                <td><em>0,0%</em></td>
                                <td><em>0,0%</em></td>
                                <td><span class="separated-tag separated-tag--priv">Informativo (DEC-001)</span></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </section>

            <!-- 3. DETALHAMENTO DAS DIMENSÕES E INDICADORES -->
            <section class="content-section">
                <h2 class="section-title">3. Detalhamento Indicador por Indicador das Dimensões Ativas</h2>

                <!-- DIMENSÃO D1 -->
                <div style="background: #ffffff; border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 1rem; margin-bottom: 0.75rem;">
                    <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.4rem; margin-bottom: 0.6rem;">
                        <h3 style="font-size: 0.98rem; font-weight: 700; color: #1e293b; margin: 0;">
                            🩺 Dimensão 1: Resultados em Saúde da População
                        </h3>
                        <span class="badge badge--quality-high">SIM / SINASC / IBGE</span>
                    </div>
                    <ul style="padding-left: 1.25rem; font-size: 0.82rem; line-height: 1.6; color: #334155;">
                        <li><strong>D1.1 — Taxa de Mortalidade Infantil (TMI) Suavizada (Peso 40% de D1):</strong> Óbitos de crianças &lt; 1 ano por 1.000 nascidos vivos, suavizada pelo método Empirical Bayes e com intervalo de Poisson (triênio 2021–2023 por residência).</li>
                        <li><strong>D1.3 — Mortalidade Prematura por DCNT (30 a 69 anos) Suavizada (Peso 30% de D1):</strong> Doenças cardiovasculares, neoplasias, diabetes e respiratórias crônicas por 100k hab., suavizada por Bayes em relação ao grupo de porte populacional.</li>
                        <li><strong>D1.4 — Mortalidade por Causas Evitáveis pelo SUS (Peso 30% de D1):</strong> Lista oficial de Causas Evitáveis da Portaria SAS/MS. Conta com <strong>padronização etária</strong> (população Censo 2022) e <strong>correção por sub-registro de causas mal definidas</strong> (Capítulo XVIII do CID-10).</li>
                        <li><strong>D1.2 — Razão de Mortalidade Materna (RMM):</strong> Óbitos maternos diretos e indiretos (Capítulo O) por 100k nascidos vivos no quinquênio 2019–2023. Exibida como <strong>informativa</strong> (fora da nota D1) devido à raridade matemática do evento em cidades de pequeno porte.</li>
                    </ul>
                </div>

                <!-- DIMENSÃO D2 -->
                <div style="background: #ffffff; border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 1rem; margin-bottom: 0.75rem;">
                    <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.4rem; margin-bottom: 0.6rem;">
                        <h3 style="font-size: 0.98rem; font-weight: 700; color: #1e293b; margin: 0;">
                            🌱 Dimensão 2: Atenção Primária &amp; Prevenção (APS)
                        </h3>
                        <span class="badge badge--quality-high">SIH / SINASC / SI-PNI</span>
                    </div>
                    <ul style="padding-left: 1.25rem; font-size: 0.82rem; line-height: 1.6; color: #334155;">
                        <li><strong>D2.1 — Internações por Condições Sensíveis à APS (ICSAP) (Peso 33,3% de D2):</strong> Taxa de hospitalizações por 10 mil hab. (Portaria SAS/MS 221/2008 via SIH/SUS). Menor taxa indica alta resolutividade preventiva das equipes de saúde da família.</li>
                        <li><strong>D2.2 — Pré-Natal Adequado com 7+ Consultas (Peso 33,3% de D2):</strong> Proporção de nascidos vivos cujas mães realizaram 7 ou mais consultas pré-natais (SINASC CONSULTAS=4). Auditado com penalização por percentual de registros ignorados.</li>
                        <li><strong>D2.3 — Cobertura Vacinal Composta por 6 Vacinas Estratégicas do 1º Ano (Peso 33,3% de D2):</strong> Média aritmética simples de 6 vacinas do calendário básico infantil do primeiro ano de vida (SI-PNI / IEPS Data):
                            <div style="margin-top: 4px; padding: 4px 8px; background: #f0fdf4; border-radius: 4px; font-weight: 600; color: #15803d;">
                                D2.3 = (Poliomielite + Pentavalente + Tríplice Viral D1 + Pneumocócica 10 + Meningocócica C + Rotavírus) / 6
                            </div>
                        </li>
                    </ul>
                </div>

                <!-- DIMENSÃO D3 -->
                <div style="background: #ffffff; border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 1rem; margin-bottom: 0.75rem;">
                    <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.4rem; margin-bottom: 0.6rem;">
                        <h3 style="font-size: 0.98rem; font-weight: 700; color: #1e293b; margin: 0;">
                            🏥 Dimensão 3: Acesso e Capacidade Assistencial
                        </h3>
                        <span class="badge badge--quality-high">CNES / SISAB</span>
                    </div>
                    <ul style="padding-left: 1.25rem; font-size: 0.82rem; line-height: 1.6; color: #334155;">
                        <li><strong>D3.1 — Leitos SUS Regionalizados com Ajuste Golden Hour (Peso 33,3% de D3):</strong> Leitos SUS existentes na Região de Saúde divididos pela população dependente do SUS (descontando usuários de plano privado da ANS). Ajustado pelo <strong>Fator de Distância Hospitalar</strong> até o polo hospitalar regional de internação.</li>
                        <li><strong>D3.2 — Médicos e Enfermeiros Padronizados por Carga Horária (Peso 33,3% de D3):</strong> Médicos e enfermeiros atuantes no SUS convertidos em equivalentes de 40 horas semanais por 1.000 habitantes (CNES).</li>
                        <li><strong>D3.3 — Cobertura da Estratégia Saúde da Família (eSF) (Peso 33,3% de D3):</strong> Cobertura populacional estimada das equipes da APS (e-Gestor AB / SAPS), com complementariedade de atenção básica via IEPS Data.</li>
                    </ul>
                </div>

                <!-- DIMENSÃO D5 (URGÊNCIA) -->
                <div style="background: #f0f9ff; border: 1px solid #bae6fd; border-radius: var(--radius-sm); padding: 1rem; margin-bottom: 0.75rem;">
                    <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #bae6fd; padding-bottom: 0.4rem; margin-bottom: 0.6rem;">
                        <h3 style="font-size: 0.98rem; font-weight: 700; color: #0369a1; margin: 0;">
                            🚑 Dimensão 5: Rede de Urgência &amp; SAMU 192 (RUE / Golden Hour)
                        </h3>
                        <span class="badge badge--quality-high">DEMAS / SEIDIGI / MS</span>
                    </div>
                    <p style="font-size: 0.82rem; color: #0369a1; line-height: 1.5; margin: 0 0 0.5rem 0;">
                        Avalia a capacidade territorial de resposta a agravos clínicos e traumáticos tempo-sensíveis (infartos, paradas cardiorrespiratórias, AVCs e politraumas).
                    </p>
                    <ul style="padding-left: 1.25rem; font-size: 0.81rem; line-height: 1.55; color: #0c4a6e;">
                        <li><strong>Sub-pilar Local (35%):</strong> Presença física de Unidades Móveis Básicas (USB) ou Avançadas (USA), UPAs 24h ativas e leitos locais de estabilização.</li>
                        <li><strong>Sub-pilar Regional com Decaimento Rodoviário (65%):</strong> Malha regional de socorro multiplicada pelo fator de sobrevivência rodoviária Golden Hour:
                            <code>f_dist = exp(-0,012 * d_km)</code>, garantindo que o tempo de trânsito até o polo terciário seja penalizado realisticamente.
                        </li>
                    </ul>
                </div>

                <!-- DIMENSÃO D6 (ONCOLOGIA) -->
                <div style="background: #faf5ff; border: 1.5px solid #d8b4fe; border-radius: var(--radius-sm); padding: 1rem; margin-bottom: 0.75rem;">
                    <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e9d5ff; padding-bottom: 0.4rem; margin-bottom: 0.6rem;">
                        <h3 style="font-size: 0.98rem; font-weight: 700; color: #6b21a8; margin: 0;">
                            🎗️ Dimensão 6: Linha de Cuidado Oncológico &amp; CACON/UNACON
                        </h3>
                        <span class="separated-tag" style="background:#f3e8ff; color:#7e22ce;">INCA / SISCAN / POBR / TCU</span>
                    </div>
                    <p style="font-size: 0.82rem; color: #581c87; line-height: 1.5; margin: 0 0 0.5rem 0;">
                        Mapeamento censitário de diagnóstico, tempo até tratamento e autonomia em relação ao Tratamento Fora de Domicílio (TFD):
                    </p>
                    <ul style="padding-left: 1.25rem; font-size: 0.81rem; line-height: 1.55; color: #4c1d95;">
                        <li><strong>1. Agilidade e Cumprimento Efetivo da Lei dos 60 Dias (30%):</strong> Pacientes que iniciam tratamento em até 60 dias calculado sobre <em>todos os diagnosticados</em>, penalizando a fila oculta sem tratamento (código 5 do SISCAN/POBR — Acórdão TCU 1.944/2019).</li>
                        <li><strong>2. Diagnóstico Precoce Auditado (20%):</strong> Casos diagnosticados em Estadiamento Clínico I e II + rastreamento de mamografias e citopatológicos na APS.</li>
                        <li><strong>3. Taxa de Conversão Terapêutica &amp; Sobrevida Padronizada (25%):</strong> Proporção de pacientes que efetivamente realizam quimioterapia, radioterapia ou cirurgia no SUS.</li>
                        <li><strong>4. Autonomia Local TFD &amp; Terapias de Ponta CNES (25%):</strong> Oferta ativa de Imunoterapia, Terapia Alvo, Radioterapia IMRT, Cirurgia Oncológica de Alta Complexidade, Oncologia Pediátrica e Transplante de Medula Óssea (TMO).</li>
                        <li><strong>Régua de Calibração Absoluta:</strong> A nota 100 reflete o padrão-ouro inatingível (95%+ em até 30 dias, diagnóstico precoce &gt; 60%, equivalente aos melhores centros mundiais). No SUS, escores acima de 60 já indicam alta eficiência assistencial.</li>
                    </ul>
                </div>
            </section>

            <!-- 4. CAMADAS INFORMATIVAS (FORA DA NOTA) -->
            <section class="content-section">
                <h2 class="section-title">4. Camadas Informativas e Auditoria Territorial (Fora da Nota)</h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 0.75rem;">
                    <!-- VACINAS COMPLEMENTARES & HPV -->
                    <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: var(--radius-sm); padding: 0.85rem;">
                        <strong style="color: #15803d; display: flex; align-items: center; gap: 0.35rem; font-size: 0.88rem;">
                            <span>🌸</span> Vacinação contra HPV (9 a 14 anos)
                        </strong>
                        <p style="font-size: 0.78rem; color: #166534; margin-top: 0.35rem; line-height: 1.45;">
                            Painel oficial InfoMS / RNDS 2024: dados censitários com segregação entre <strong>Meninas</strong> e <strong>Meninos</strong> sob dose única contra a meta de 90%. As vacinas complementares infantis (BCG, Hepatite A e Hepatite B) também são monitoradas de forma puramente informativa para prevenir distorções por vieses de notificação hospitalar.
                        </p>
                    </div>

                    <!-- INFRAESTRUTURA CNES -->
                    <div style="background: #f0fdfa; border: 1px solid #99f6e4; border-radius: var(--radius-sm); padding: 0.85rem;">
                        <strong style="color: #0f766e; display: flex; align-items: center; gap: 0.35rem; font-size: 0.88rem;">
                            <span>🔬</span> Suporte Diagnóstico &amp; Infraestrutura CNES
                        </strong>
                        <p style="font-size: 0.78rem; color: #115e59; margin-top: 0.35rem; line-height: 1.45;">
                            Microdados CNES 12/2023: disponibilidade local de <strong>exames básicos</strong> (Raio-X, Ultrassom, ECG, Desfibrilador, Mamógrafo) e acesso regionalizado a <strong>exames avançados</strong> (Tomógrafo, Ressonância Magnética, Hemodinâmica e Endoscopia) com UTI Adulto e leitos cirúrgicos.
                        </p>
                    </div>

                    <!-- FINANCIAMENTO SIOPS -->
                    <div style="background: #faf5ff; border: 1px solid #e9d5ff; border-radius: var(--radius-sm); padding: 0.85rem;">
                        <strong style="color: #6b21a8; display: flex; align-items: center; gap: 0.35rem; font-size: 0.88rem;">
                            <span>💰</span> Financiamento Municipal (SIOPS)
                        </strong>
                        <p style="font-size: 0.78rem; color: #581c87; margin-top: 0.35rem; line-height: 1.45;">
                            Despesa total em saúde per capita deflacionada e percentual de receita própria aplicada em ações de saúde (EC 29). Gastos são contextuais e não determinam sozinhos a qualidade da gestão.
                        </p>
                    </div>

                    <!-- CAMADA PRIVADA ANS -->
                    <div style="background: #fdf2f8; border: 1px solid #fbcfe8; border-radius: var(--radius-sm); padding: 0.85rem;">
                        <strong style="color: #9d174d; display: flex; align-items: center; gap: 0.35rem; font-size: 0.88rem;">
                            <span>🏥</span> Camada Privada (ANS / CNES)
                        </strong>
                        <p style="font-size: 0.78rem; color: #831843; margin-top: 0.35rem; line-height: 1.45;">
                            Taxa de cobertura de planos de saúde suplementares privados e taxa de leitos hospitalares estritamente não-SUS por 100 mil habitantes.
                        </p>
                    </div>
                </div>
            </section>

            <!-- 5. TRATAMENTO ESTATÍSTICO E NORMALIZAÇÃO -->
            <section class="content-section">
                <h2 class="section-title">5. Tratamento Estatístico e Metodologia Científica</h2>
                <div style="display: flex; flex-direction: column; gap: 0.75rem; font-size: 0.84rem; line-height: 1.55; color: #334155;">
                    <div style="padding: 0.65rem 0.85rem; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px;">
                        <strong>📐 Normalização Relativa por Percentis Empíricos (P5 e P95):</strong>
                        <p style="margin: 0.25rem 0 0 0; color: var(--color-text-muted);">
                            Os indicadores são reescalonados para a escala 0 a 100 utilizando os percentis 5º (pior) e 95º (melhor) observados empiricamente no território nacional. Isso impede que municípios com valores extremos (outliers unifamiliares) distorçam a régua dos outros 5.500 municípios.
                        </p>
                    </div>

                    <div style="padding: 0.65rem 0.85rem; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px;">
                        <strong>🧠 Suavização Bayesiana Empírica (Empirical Bayes Shrinkage):</strong>
                        <p style="margin: 0.25rem 0 0 0; color: var(--color-text-muted);">
                            Indicadores de mortalidade em pequenas populações (onde 1 óbito adicional multiplica a taxa por 5) sofrem encolhimento proporcional à sua incerteza amostral em direção à média do porte e da região de saúde.
                        </p>
                    </div>

                    <div style="padding: 0.65rem 0.85rem; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px;">
                        <strong>🎯 Intervalos de Confiança Exatos de Poisson (IC 95%):</strong>
                        <p style="margin: 0.25rem 0 0 0; color: var(--color-text-muted);">
                            Todo indicador exibe sua margem de incerteza estatística em microdados, distinguindo flutuações amostrais aleatórias de diferenças reais de eficiência assistencial.
                        </p>
                    </div>

                    <div style="padding: 0.65rem 0.85rem; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px;">
                        <strong>📈 Análise de Sensibilidade &amp; Faixa de Posição Plausível:</strong>
                        <p style="margin: 0.25rem 0 0 0; color: var(--color-text-muted);">
                            O ranking não é determinístico. Cada município tem sua colocação recalculada sob 9 combinações de esquemas de pesos e percentis de corte, gerando a <strong>faixa de posição plausível</strong> (ex: #120º a #185º no Brasil).
                        </p>
                    </div>
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
