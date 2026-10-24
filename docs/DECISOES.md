# Registro de Decisões Metodológicas e Arquiteturais (ADR)

> Este documento registra as decisões formais de arquitetura, governança e metodologia adotadas no projeto **Índice de Saúde Municipal do Brasil**, conforme a especificação técnica v0.1.

---

### DEC-001: Exclusão da Dimensão 4 (Contexto) e da Camada Privada da Nota Principal
- **Data:** 2026-10-23
- **Status:** Aprovado
- **Contexto:**
  Indicadores de gasto per capita em saúde (SIOPS) e percentual de receita própria aplicada não representam, por si sós, a qualidade da atenção à saúde no território (conforme demonstrado na literatura e em estudos empíricos regionais). Da mesma forma, a cobertura de planos de saúde privados (ANS) e a rede privada não conveniada (CNES) medem capacidade de pagamento e oferta de mercado, e não a eficácia da saúde pública (SUS).
- **Decisão:**
  A Dimensão 4 (Gasto e Contexto) e a Camada Privada de Saúde serão mantidas **estritamente fora do cômputo da Nota Geral do Índice e das dimensões D1, D2 e D3**. Elas serão apresentadas na interface e nos dados como camadas informativas e contextuais independentes.

---

### DEC-002: Adoção de Janelas Móveis Plurianuais (3 a 5 anos) para Indicadores de Resultado
- **Data:** 2026-10-23
- **Status:** Aprovado
- **Contexto:**
  Mais de 70% dos municípios brasileiros possuem menos de 20.000 habitantes. O cálculo de taxas anuais isoladas para eventos raros (como óbitos infantis e maternos) gera volatilidade estocástica extrema: um único óbito em um ano pode dobrar ou triplicar a taxa artificialmente.
- **Decisão:**
  Indicadores de resultado (especialmente D1.1, D1.2, D1.3, D1.4) utilizarão janelas móveis de 3 a 5 anos (definidas por indicador conforme raridade do evento). O ano de referência do índice corresponde à janela consolidada.

---

### DEC-003: Suavização Bayesiana Empírica e Intervalo de Confiança Exibidos com a Taxa Bruta
- **Data:** 2026-10-23
- **Status:** Aprovado
- **Contexto:**
  Apresentar apenas a taxa bruta penaliza e distorce o diagnóstico de municípios com populações reduzidas. Por outro lado, apresentar apenas uma taxa modelada/suavizada retira a transparência do dado observado.
- **Decisão:**
  Para todos os indicadores de taxa em pequenas populações, o pipeline calculará:
  1. A taxa bruta observada;
  2. O intervalo de confiança de 95% (distribuição de Poisson exata ou equivalente);
  3. A taxa suavizada por Bayes Empírico (shrinkage em direção à média de referência).
  Todos os três valores devem ser expostos na interface e nos arquivos de exportação.

---

### DEC-004: Recálculo Integral da Série Histórica em Mudanças de Metodologia
- **Data:** 2026-10-23
- **Status:** Aprovado
- **Contexto:**
  Vários índices governamentais históricos sofrem de quebra de série temporal por alterarem variáveis ou critérios ano a ano sem reprocessar anos anteriores, induzindo o público ao erro ao comparar notas calculadas com regras distintas.
- **Decisão:**
  Qualquer alteração metodológica (inclusão/exclusão de indicador, alteração de limites de referência ou de pesos) gera uma nova versão maior/menor da metodologia e exige o **recálculo retroativo integral de toda a série histórica**. É proibido mesclar dados de metodologias distintas em um mesmo painel temporal.

---

### DEC-005: Proibição de Imputação Silenciosa e Atribuição de "Sem Classificação"
- **Data:** 2026-10-23
- **Status:** Aprovado
- **Contexto:**
  Imputar dados médios ou preencher valores ausentes em registros vitais de saúde pública sem transparência gera diagnósticos territoriais falsos e compromete a confiabilidade das decisões de gestão.
- **Decisão:**
  Municípios com dados insuficientes ou cuja qualidade de registro (ex: proporção excessiva de causas mal definidas no SIM) fique abaixo dos limiares de adequação receberão o status explícito de `"sem_classificacao"`. Em hipótese alguma haverá imputação cega de dados.

---

### DEC-006: Arquitetura Estática com Processamento Centralizado e Versionado
- **Data:** 2026-10-23
- **Status:** Aprovado
- **Contexto:**
  APIs governamentais de dados em saúde no Brasil frequentemente sofrem instabilidades, mudanças de formato ou restrições de tráfego. Consultas ao vivo feitas pelo navegador do usuário causariam lentidão, falhas constantes e risco de segurança.
- **Decisão:**
  O site é 100% estático (HTML5/CSS3/Vanilla JS). Nenhuma requisição de raspagem ou processamento é feita no cliente. Todas as fontes são baixadas, validadas e processadas no pipeline (Python/DuckDB/Parquet), gerando artefatos estáticos versionados (`/data/releases/latest/`) consumidos pelo frontend.

---

### DEC-007: Travas Automáticas de Qualidade (Quality Gates) Bloqueantes
- **Data:** 2026-10-23
- **Status:** Aprovado
- **Contexto:**
  Atualizações automatizadas não podem publicar dados corrompidos, incompletos ou divergentes da malha municipal oficial.
- **Decisão:**
  O pipeline de dados é obrigado a rodar validações estritas (cardinalidade de 5.570 municípios, tipos, faixas plausíveis, completude e hashes SHA-256 de entrada). Em caso de qualquer inconsistência, o processo aborta imediatamente com código de erro `sys.exit(1)`, a release anterior válida é mantida intacta e uma Issue é gerada no repositório.

---

### DEC-008: Regra de UI: Nota Geral Nunca Isolada e Rastreabilidade Obrigatória
- **Data:** 2026-10-23
- **Status:** Aprovado
- **Contexto:**
  Índices sintéticos consolidados em uma única nota correm o risco de ocultar problemas críticos em dimensões específicas (ex.: bom resultado impulsionado apenas por estrutura, apesar de mortalidade elevada).
- **Decisão:**
  Na interface, a **Nota Geral de um município nunca será exibida desacompanhada**: ela deve sempre figurar no mesmo bloco com as notas de D1, D2 e D3 e com a faixa de posição plausível (análise de sensibilidade). Além disso, **nenhum indicador numérico pode ser renderizado sem exibir fonte, período vintage, data da coleta, versão metodológica e selo de incerteza/qualidade**.

---

### DEC-009: Migração Definitiva para Microdados Primários do SIM e SINASC (DATASUS FTP) por Residência
- **Data:** 2026-10-24
- **Status:** Aprovado
- **Contexto:**
  A comparação cruzada de 2022 (`data/processed/relatorio_comparacao_fontes.json`) entre o Registro Civil do IBGE (Tabelas SIDRA 2654/2609) e os microdados do SIM/SINASC (DATASUS) revelou sub-registro severo de óbitos infantis em cartório (26.987 no Cartório IBGE vs. 32.238 no SIM, uma diferença de 5.251 óbitos), especialmente nas regiões Norte e Centro-Oeste (apenas 38,1% dos óbitos do SIM registrados em cartório no MT, 47,1% no MA e 52,3% no PA). Esse sub-registro fazia municípios como Marabá (PA) apresentarem aparente TMI de 1,53 no Cartório IBGE quando a TMI real no SIM era 14,75.
- **Decisão:**
  Descontinuar o uso do Registro Civil (Cartório IBGE) para indicadores epidemiológicos e utilizar exclusivamente os microdados primários de Declaração de Óbito por residência (`SIM/CID10/DORES`) e Declaração de Nascido Vivo por residência (`SINASC/DNRES`) extraídos diretamente do FTP do DATASUS para a série 2019–2023.

---

### DEC-010: Normalização Relativa por Percentis Empíricos (P5–P95) Enquanto Metas Normativas Estiverem Pendentes
- **Data:** 2026-10-24
- **Status:** Aprovado
- **Contexto:**
  Em cumprimento à Regra Inegociável 1 (proibição de inventar metas ou limites de referência não validados em portaria/documento oficial) e para eliminar a saturação artificial de notas 100 decorrente de tetos arbitrários, os limites normativos permanecem como `null` (`PEND-033`).
- **Decisão:**
  Enquanto `meta_oficial_confirmada` for `null` em `config/limites_referencia.yaml`, o pipeline adota normalização empírica relativa baseada nos percentis P5 e P95 da distribuição nacional observada na janela vigente, gravando os valores calculados em `config/limites_calculados.json` e realizando análise de sensibilidade cruzando os cortes `[P1, P99]`, `[P5, P95]` e `[P10, P90]` combinados aos esquemas alternativos de pesos para compor `[faixa_posicao_min, faixa_posicao_max]`.
