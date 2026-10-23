# Índice de Saúde Municipal do Brasil — Especificação v0.1 (rascunho técnico)

> Documento para orientar o desenvolvimento (humano ou agente de IA). **Leia a seção 0 antes de qualquer coisa.**

## 0. Regras inegociáveis (valem para quem implementar)

1. **Nenhum dado, valor, limite, peso, código CID, portaria ou link pode ser inventado.** Tudo que aparece abaixo marcado `[A VALIDAR]` é uma hipótese de trabalho e deve ser confirmado na fonte oficial antes de entrar no código. Se não conseguir confirmar, **pare e registre a pendência** em `docs/PENDENCIAS.md`; não preencha lacunas por conta própria.
2. Cada número exibido no site precisa ter: fonte, período (vintage), data de coleta, versão da metodologia e indicador de qualidade/incerteza.
3. Mudança de metodologia **nunca** é automática. Atualização de dados dentro da metodologia vigente pode ser automática, mas só passando pelas travas da seção 8.
4. Município sem dados suficientes fica **"sem classificação"**. Não imputar em silêncio.
5. O índice mede **qualidade da saúde pública (SUS) no território**, com resultados, atenção primária, acesso e estrutura. Não é avaliação de profissionais nem de unidades individuais.

## 1. Escopo

- **Universo:** todos os 5.570 municípios (classificação IBGE vigente, incluindo o Distrito Estadual de Fernando de Noronha, que o IPS Brasil trata como unidade). `[A VALIDAR: lista oficial IBGE mais recente e eventuais mudanças]`
- **Chave primária:** código IBGE de 7 dígitos. Atenção: os sistemas do DATASUS costumam usar **6 dígitos** (sem o dígito verificador). Criar tabela de-para `dim_municipio` e testar unicidade.
- **Foco:** saúde pública. A saúde privada entra só como **camada informativa separada** (seção 6), fora da nota principal.
- **Granularidade temporal:** série anual. Ano-base de cálculo = janela móvel (ver seção 5.1).

## 2. Arquitetura (site estático + pipeline agendado)

```
Fontes oficiais ──► Pipeline (GitHub Actions, agendado) ──► Parquet/CSV/JSON versionados ──► Site estático (GitHub Pages)
        ▲                      │
        │                      ├─ checagem de frescor e esquema
        │                      ├─ travas de qualidade (seção 8)
        │                      └─ publica release OU aborta e mantém a última versão válida
        └── Monitor de descoberta (abre issue; não altera o índice)
```

- O site **não raspa nada no navegador do usuário**. Todo dado é processado no pipeline e publicado como arquivos estáticos.
- Base técnica: reaproveitar a estrutura do site ICCB Brasil (mapa + índice). `[A VALIDAR: stack real do repositório ICCB]`
- Linguagem do pipeline: Python (pandas/polars + DuckDB/Parquet). Existem bibliotecas abertas para baixar microdados do DATASUS (ex.: PySUS em Python; microdatasus em R). `[A VALIDAR: manutenção atual e compatibilidade]`
- **Risco conhecido:** a documentação do pacote microdatasus avisa que o DATASUS pode restringir acesso FTP a partir de alguns países. Os runners do GitHub Actions ficam fora do Brasil. **Testar cedo** (seção 12, item 1). Plano B: usar o OpenDataSUS, ou espelhar os arquivos pré-processados do IEPS Data.

## 3. Registro de fontes (`sources/registry.yaml`)

Toda fonte é declarada neste arquivo, e **só o que estiver aqui é consumido pelo pipeline**. Campos obrigatórios:

```yaml
- id: sim_do
  nome: Sistema de Informações sobre Mortalidade (SIM) — Declaração de Óbito
  orgao: Ministério da Saúde / DATASUS
  url_documentacao: <preencher>
  url_dados: <preencher>
  formato: dbc | csv | api
  periodicidade_publicacao: <preencher>
  defasagem_tipica: <medir, não presumir>
  licenca_termos_uso: <preencher>
  ultima_verificacao: <data>
  ultimo_periodo_disponivel: <medido automaticamente>
  status: ativo | em_revisao | descontinuado
```

Fontes candidatas: SIM, SINASC, SIH/SUS, SIA/SUS, CNES (estabelecimentos, leitos, profissionais), SI-PNI, SISAB/Siaps (Atenção Primária), IBGE (população, Censo, malha municipal), SIOPS (gasto), ANS (saúde suplementar), IEPS Data (camada pré-processada e documentação de métodos), IPS Brasil (apenas **validação externa**). Todas `[A VALIDAR]` quanto a acesso, licença e defasagem.

## 4. Indicadores candidatos

Estrutura: 4 dimensões. Cada indicador exige ficha em `docs/indicadores/<id>.md` com: definição, numerador, denominador, fonte, sentido (maior = melhor ou pior), nível de agregação (residência), janela, limitações e referência bibliográfica. **Nada entra no índice sem ficha completa.**

### D1 — Resultados em saúde (por local de residência)
| id | Indicador | Observação |
|---|---|---|
| D1.1 | Mortalidade infantil (óbitos <1 ano / nascidos vivos × 1.000) | SIM + SINASC |
| D1.2 | Razão de mortalidade materna (óbitos maternos / nascidos vivos × 100.000) | Eventos raros: janela de 5 anos |
| D1.3 | Mortalidade prematura (30–69 anos) por DCNT, taxa padronizada por idade | Grupos de causas e CIDs `[A VALIDAR]` na definição oficial do MS/ODS 3.4 |
| D1.4 | Mortalidade por causas evitáveis por intervenções do SUS | Lista oficial brasileira `[A VALIDAR: versão vigente]` |

### D2 — Atenção Primária (processo)
| id | Indicador | Observação |
|---|---|---|
| D2.1 | Internações por condições sensíveis à APS (ICSAP), taxa por 10 mil hab. | Lista oficial por portaria `[A VALIDAR: portaria e CIDs]`; SIH por residência |
| D2.2 | Pré-natal adequado (proporção de nascidos vivos com 7+ consultas) | SINASC; confirmar variável e critério |
| D2.3 | Cobertura vacinal | SI-PNI; **atenção a mudanças de denominador** `[A VALIDAR]` |
| D2.4 | Desempenho nos indicadores de qualidade do cofinanciamento federal da APS (15 indicadores, 3 blocos, metodologia de 2024) | **Série histórica curta e possível quebra com o modelo anterior (Previne Brasil).** Usar como camada separada até haver série comparável. `[A VALIDAR: dado municipal público, API, período inicial]` |

### D3 — Acesso e estrutura
| id | Indicador | Observação |
|---|---|---|
| D3.1 | Leitos SUS por mil habitantes | CNES; considerar **região de saúde**, não só o município |
| D3.2 | Médicos e enfermeiros por mil hab. (vínculo SUS) | CNES-PF; **contar profissionais únicos** (há duplicidade de vínculos) |
| D3.3 | Cobertura de equipes de saúde da família | `[A VALIDAR: fonte e definição vigente]` |
| D3.4 | Proporção de internações SUS de residentes realizadas no próprio município (indicador de dependência de outros municípios) | SIH; **informativo**, não entra na nota sem decisão metodológica |

### D4 — Contexto (NÃO entra na nota de qualidade)
Gasto per capita em saúde (SIOPS), porte populacional, contexto socioeconômico (para grupos de pares e análise). Estudo recente em municípios do Alto Oeste Potiguar indica que % de receita própria aplicada não serve como medida de qualidade da APS, então gasto fica como **contexto**.

## 5. Tratamento estatístico

### 5.1 Janela e denominadores
- Taxas de resultado em **janela de 3 a 5 anos** (a definir por indicador conforme raridade do evento), nunca ano isolado para municípios pequenos.
- Denominadores populacionais: definir **uma fonte única** e documentar a transição para o Censo 2022 (risco de quebra de série). `[A VALIDAR]`

### 5.2 Municípios pequenos
- Calcular **intervalo de confiança** para cada taxa (Poisson exato ou equivalente) e exibi-lo.
- Aplicar **suavização bayesiana empírica** (shrinkage para a média regional ou do grupo de pares) e **mostrar a taxa bruta e a suavizada**. A escolha do método precisa ser justificada e testada com dados reais antes de fixar.

### 5.3 Qualidade dos dados de origem
- Para SIM/SINASC, calcular e publicar indicadores de qualidade (ex.: proporção de óbitos com causa mal definida, regularidade/cobertura do registro). `[A VALIDAR: indicadores e referências oficiais de adequação]`
- Municípios com dado de baixa qualidade recebem **selo de alerta** e, abaixo de um limiar documentado, ficam sem classificação nesse indicador.

### 5.4 Comparabilidade
- Padronização por idade nas taxas de mortalidade por causa específica.
- Exibir **posição nacional, estadual e em grupo de pares** (porte populacional e região). Definição dos grupos: `[A DECIDIR com justificativa]`.

## 6. Camada privada (informativa, fora da nota)

- Cobertura de planos de saúde por município (ANS) e oferta não-SUS (estabelecimentos e leitos privados via CNES). `[A VALIDAR: granularidade municipal e periodicidade da ANS]`
- **Não** criar nota de "qualidade privada" com dados abertos disponíveis sem evidência de que sustentam isso. Registrar a decisão em `docs/DECISOES.md`.

## 7. Normalização, pesos e agregação

1. **Normalização:** escala 0–100 com **limites de referência fixos** (metas ODS/OMS ou percentis históricos documentados), e não min-max sobre a distribuição do ano, para a nota não mudar só porque outros municípios mudaram. `[A VALIDAR: cada limite com sua fonte]`
2. **Agregação:** média ponderada dentro de cada dimensão e entre dimensões. Os pesos são **proposta inicial a decidir**: começar com pesos iguais dentro das dimensões e comparar com PCA e com pesos de especialistas.
3. **Análise de sensibilidade obrigatória:** publicar quanto o ranking muda entre esquemas de peso, e incluir a **faixa de posição plausível** de cada município.
4. **Notas por dimensão sempre visíveis** (a nota geral nunca aparece sozinha).
5. **Série comparável:** ao mudar de versão metodológica, **recalcular toda a série histórica** com a nova versão. Valores de versões diferentes não se misturam (problema observado em índices como o IMRS, que muda de indicadores a cada atualização).

## 8. Atualização automática com travas

**Princípio:** o pipeline pode atualizar dados; só um humano muda a metodologia.

Agendamento (cron mensal ou semanal) executa: detectar novo período nas fontes → baixar → validar → recalcular → publicar. **Travas** (qualquer falha aborta a publicação e mantém a última versão válida, abrindo um issue):

- Esquema: colunas, tipos e códigos de município esperados (5.570 únicos).
- Completude mínima por indicador (limiar documentado).
- Faixas plausíveis (ex.: taxa negativa ou população zero = erro).
- Variação ano a ano anômala por indicador (limiar documentado) → exige revisão humana.
- Reprodutibilidade: mesmos insumos geram mesmo resultado (hash dos arquivos de entrada registrado).

**Frescor:** cada indicador mostra o período mais recente usado e um selo "defasado" quando passa do esperado para aquela fonte (medir a defasagem típica, não presumir).

**Monitor de descoberta (o "sempre buscar os melhores dados"):** job separado que consulta catálogos (IEPS Data, OpenDataSUS, portais oficiais, normas do MS sobre indicadores) e **abre um issue com candidatos** (novo indicador, nova versão de lista oficial, fonte descontinuada). Candidato só vira indicador depois de ficha, validação e aprovação humana, com nova versão de metodologia.

**Releases versionados:** `metodologia vX.Y` + `dados AAAA-MM-DD`. Changelog público.

## 9. Validação do índice

- Correlação com o componente de saúde do IPS Brasil e com expectativa de vida/mortalidade geral. `[A VALIDAR: dados do IPS disponíveis para uso e licença]`
- Teste de casos: municípios conhecidos como muito bons/ruins e casos de borda (muito pequenos, polos regionais, capitais).
- Baixa correlação não invalida o índice, mas exige explicação documentada.

## 10. Requisitos do site

- Mapa coroplético nacional + busca por município + filtros (UF, porte, região de saúde).
- **Ficha do município:** nota geral, notas por dimensão, cada indicador com valor, intervalo de confiança, período, fonte e selo de qualidade; posição nacional/estadual/pares; comparação com a média do grupo.
- **Página "Como é calculado":** fórmulas, normalização, pesos, tratamento de dados ausentes, análise de sensibilidade, limitações. Gerada a partir dos mesmos arquivos de configuração do pipeline, para nunca divergir do cálculo real.
- **Página "Fontes":** gerada a partir de `sources/registry.yaml`, com link, período, data da última coleta e licença.
- **Aviso de interpretação:** diferenças pequenas de nota não são diferenças reais; o índice descreve o território, não uma unidade de saúde.
- Download de dados (CSV/JSON) com dicionário de variáveis.
- Acessibilidade e desempenho em celular (malha municipal simplificada).

## 11. Estrutura sugerida do repositório

```
/sources/registry.yaml
/pipeline/ (extract/, transform/, indicators/, index/, validate/)
/config/ (indicadores.yaml, pesos.yaml, limites_referencia.yaml, metodologia_versao.txt)
/data/ (raw/ [não versionar se pesado], processed/, releases/)
/docs/ (indicadores/, DECISOES.md, PENDENCIAS.md, CHANGELOG.md)
/site/
/.github/workflows/ (atualizar_dados.yml, monitor_descoberta.yml)
```

## 12. Fases e critérios de aceite

| Fase | Entrega | Aceite |
|---|---|---|
| 0 | Verificações da seção 13 concluídas | Planilha de pendências zerada ou decidida |
| 1 | `dim_municipio` com 5.570 municípios + população | Chaves únicas, de-para 6→7 dígitos testado |
| 2 | Pipeline de 2–3 indicadores de resultado (D1.1, D1.3) para todos os municípios | Reproduzível no GitHub Actions; log de proveniência |
| 3 | Demais indicadores com ficha | Nenhum indicador sem ficha |
| 4 | Cálculo do índice + sensibilidade + validação | Relatório de sensibilidade publicado |
| 5 | Site (mapa, ficha, metodologia, fontes) | Todo número tem fonte e período na tela |
| 6 | Automação com travas + monitor de descoberta | Falha simulada aborta e mantém versão anterior |

## 13. Lista de verificação pendente (resolver antes da Fase 1)

Ver tabela no chat com onde, como e o que trazer. Resultados devem ser registrados em `docs/PENDENCIAS.md`, com link da fonte e data da consulta.
