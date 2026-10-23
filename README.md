# Índice de Saúde Municipal do Brasil

> Medição sintética e transparente da qualidade da saúde pública (SUS) no território dos 5.570 municípios brasileiros.

**Versão da Metodologia:** `v0.1.0-draft`  
**Status Atual:** Fase 0 (Governança, Estruturação e Validação de Fontes)  
**Especificação Técnica:** [`ESPECIFICACAO_INDICE_SAUDE_MUNICIPAL.md`](file:///c:/Users/danil/Documents/Códigos/Avaliacao%20saude%20Brasil/ESPECIFICACAO_INDICE_SAUDE_MUNICIPAL.md)

---

## ⚖️ Regras Inegociáveis de Execução

1. **Proibido Inventar Dados:** Nenhum valor numérico de saúde, limite de referência, peso definitivo, código CID, número de portaria, URL não verificada ou população fictícia é incluído no código. Tudo o que não estiver confirmado na fonte oficial permanece como `null` ou `"A_VALIDAR"` e registrado formalmente em [`docs/PENDENCIAS.md`](file:///c:/Users/danil/Documents/Códigos/Avaliacao%20saude%20Brasil/docs/PENDENCIAS.md).
2. **Rastreabilidade Total na UI:** Nenhum número é renderizado na interface sem seus metadados de auditoria: `fonte`, `período (vintage)`, `data_coleta`, `versao_metodologia` e `indicador de qualidade/incerteza (IC 95% + selo)`. Se qualquer um estiver ausente, exibe o estado `"Sem classificação / Aguardando validação de fonte"`.
3. **A Nota Geral Nunca Aparece Sozinha:** A Nota Geral do município é sempre acompanhada das notas das dimensões D1, D2 e D3 e da faixa de posição plausível (análise de sensibilidade).
4. **D4 (Contexto) e Camada Privada Fora da Nota:** Gasto público em saúde (SIOPS) e cobertura de saúde suplementar (ANS) são informativos e mantidos estritamente fora do cômputo da nota de qualidade pública ([DEC-001](file:///c:/Users/danil/Documents/Códigos/Avaliacao%20saude%20Brasil/docs/DECISOES.md)).
5. **Recálculo Integral da Série:** Qualquer alteração metodológica exige o recálculo retroativo de toda a série histórica. Metodologias distintas nunca são misturadas na mesma série ([DEC-004](file:///c:/Users/danil/Documents/Códigos/Avaliacao%20saude%20Brasil/docs/DECISOES.md)).

---

## 📁 Estrutura do Repositório

```
├── .github/workflows/
│   ├── atualizar_dados.yml        # CI agendado com travas automáticas e abertura de issue
│   └── monitor_descoberta.yml     # Monitor de descoberta de novos períodos e catálogos
├── config/
│   ├── indicadores.yaml           # Catálogo paramétrico de indicadores (D1 a D4 e Privada)
│   ├── pesos.yaml                 # Esquemas de ponderação (pesos iguais e sensibilidade)
│   ├── limites_referencia.yaml    # Limites para normalização 0-100 (ODS/OMS)
│   └── metodologia_versao.txt     # Versão semântica da metodologia (v0.1.0-draft)
├── data/
│   ├── raw/                       # Dados brutos em cache (não versionados se pesados)
│   ├── processed/
│   │   ├── dim_municipio.parquet  # Tabela com os 5.570 municípios validados
│   │   └── dim_municipio.csv      # Versão CSV aberta
│   └── releases/latest/
│       ├── meta_build.json        # Metadados do pipeline consumidos pelo front-end
│       ├── mapa_resumo.json       # Dados municipais estruturados para o mapa e drawer
│       └── provenance_manifest.json # Hashes SHA-256 de proveniência dos insumos
├── docs/
│   ├── DECISOES.md                # Registro de Decisões Metodológicas e Arquiteturais (ADRs)
│   ├── PENDENCIAS.md              # Registro estruturado de itens [A VALIDAR] e [A DECIDIR]
│   ├── CHANGELOG.md               # Histórico versionado de alterações
│   └── indicadores/               # Fichas técnicas (D1.1 até D3.4, D4 e Camada Privada)
├── pipeline/
│   ├── 01_build_dim_municipio.py  # Constrói dim_municipio (5.570 municípios, ibge7 e ibge6)
│   ├── export_site_payloads.py    # Gera meta_build.json e mapa_resumo.json a partir de configs
│   ├── monitor_descoberta.py      # Rotina do monitor de descoberta de dados
│   └── validate/
│       └── quality_gates.py       # Travas de integridade (abortam com sys.exit(1) em falhas)
├── site/                          # Front-end estático (HTML5, Vanilla JS ES Modules, Leaflet)
│   ├── index.html                 # Ponto de entrada com as 4 visões do sistema
│   └── assets/
│       ├── css/style.css          # Design system responsivo mobile-first
│       └── js/
│           ├── app.js             # Controlador central de navegação e inicialização
│           ├── audit_badge.js     # Renderizador com rastreabilidade obrigatória
│           ├── map.js             # Mapa coroplético Leaflet com seletores de camada
│           ├── drawer_municipio.js # Ficha lateral (Nota Geral + D1/D2/D3 + Acordeões)
│           ├── methodology_view.js # Vista dinâmica "Como é calculado"
│           ├── sources_view.js    # Vista dinâmica "Fontes & Proveniência"
│           └── downloads_view.js  # Vista de downloads e dicionário de variáveis
└── sources/
    └── registry.yaml              # Registro oficial de fontes (SIM, SINASC, SIH, CNES, etc.)
```

---

## 🚀 Como Executar o Pipeline Localmente

### 1. Pré-requisitos
- Python 3.10+
- Dependências: `pip install -r requirements.txt`

### 2. Construir a Dimensão Municipal (5.570 municípios)
```bash
python pipeline/01_build_dim_municipio.py
```

### 3. Executar as Travas de Qualidade (Quality Gates)
```bash
python pipeline/validate/quality_gates.py
```

### 4. Compilar os Payloads Estáticos do Front-End
```bash
python pipeline/export_site_payloads.py
```

### 5. Visualizar o Site
```bash
python -m http.server 8000
```
Acesse `http://localhost:8000/site/` no seu navegador.
