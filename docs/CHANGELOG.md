# Changelog

Todas as alterações notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e este projeto segue [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [v0.3.0] - 2026-10-23

### Adicionado
- **Índice Sintético de Saúde Pública Municipal Consolidado (D1, D2 e D3)**:
  - Ingestão de dados oficiais 2022 de múltiplos sistemas nacionais via IEPS Data API (`data/raw/ieps_indicadores_2022.csv`):
    - **D2.2**: Proporção de Nascidos Vivos com 7+ Consultas de Pré-Natal (%) [SINASC];
    - **D2.3**: Cobertura Vacinal contra Poliomielite em menores de 1 ano (%) [SI-PNI / DATASUS];
    - **D3.1**: Leitos de Internação SUS por 100.000 habitantes [CNES / DATASUS];
    - **D3.2**: Médicos por 1.000 habitantes [CNES / DATASUS];
    - **D3.3**: Cobertura Populacional da Estratégia Saúde da Família - ESF (%) [SAPS / SISAB];
    - **Camada Privada**: Leitos Privados Não-SUS por 100.000 habitantes [CNES].
  - Implementação do script de consolidação do índice `pipeline/indicators/build_composite_index.py`:
    - Integração de D1 (Mortalidade Infantil suavizada), D2 (Atenção Primária) e D3 (Estrutura e Acesso);
    - Ponderação estrita de 33,3% para cada dimensão;
    - Normalização dos indicadores para a escala padrão 0–100 conforme metas e diretrizes sanitárias;
    - Geração de `data/processed/indice_saude_municipal.parquet` e `.csv` (espelhados para download no site);
    - Eliminação completa de distorções cartorárias observadas em indicadores isolados (ex.: Marabá/PA, antes #1 em D1 isolado por sub-registro de cartório, posiciona-se em #5.146 com nota 60,5 no índice consolidado, refletindo fidedignamente o déficit assistencial; e municípios com reconhecida excelência como Venda Nova do Imigrante/ES, Luiz Alves/SC e Paranaíta/MT lideram o ranking).
  - Atualização dos Quality Gates em `pipeline/validate/quality_gates.py` para validação matemática de todos os escores consolidados e registro criptográfico no manifesto SHA-256.

### Modificado
- **Interface e Experiência do Usuário (UI/UX)**:
  - **Redução drástica da barra superior**: Altura do cabeçalho enxugada para maximizar a área útil do mapa na tela.
  - **Remoção do banner gigante de aviso**: O aviso de interpretação da Seção 10 foi transferido para um modal dedicado, acessado através do novo botão `"ℹ️ Info"` no cabeçalho.
  - **Rankings Consolidados Multi-dimensionais**: Modal de rankings atualizado com abas para alternar entre "🌟 Nota Geral", "D1: Mortalidade", "D2: Primária" e "D3: Estrutura", exibindo os escores de todas as dimensões em cada linha.
  - **Tooltips do Mapa Coroplético**: Exibição da Nota Geral (0–100) sempre acompanhada do trio D1, D2, D3, além das posições nacional, estadual e no grupo de pares.
  - **Página de Downloads**: Adição de cards em destaque para download direto da base consolidada em `.CSV` e `.Parquet`.

---

## [v0.2.0-fase2] - 2026-10-23

### Adicionado
- **Fase 2: Ingestão e Cálculo do Indicador D1.1 (Mortalidade Infantil)**:
  - Ingestão oficial de dados 2022 via API SIDRA do IBGE: Tabela 2654 (óbitos menores de 1 ano por residência) e Tabela 2609 (nascidos vivos por residência da mãe) cobrindo todos os 5.570 municípios.
  - Implementação do script de cálculo epidemiológico `pipeline/indicators/d1_resultados.py`:
    - Taxa bruta por 1.000 nascidos vivos;
    - Intervalo de confiança exato de Poisson a 95% (`scipy.stats.chi2`);
    - Suavização Bayesiana Empírica (Marshall 1991) agrupada por UF para correção de flutuação em pequenos municípios;
    - Normalização para escala 0–100 baseada em padrão internacional e meta ODS 3.2 (melhor: <= 5,0 óbitos/mil NV; pior: >= 30,0 óbitos/mil NV);
    - Rankings nacionais, estaduais e por grupo de porte populacional com faixa de posição plausível baseada nos ICs.
  - Geração dos artefatos processados em formato aberto: `data/processed/indicador_d1_1.parquet` e `indicador_d1_1.csv` (espelhados para download no site).
  - Geração de `data/releases/latest/rankings_resumo.json` contendo os 10 melhores e piores municípios do Brasil e de cada UF.
  - Otimização do payload `data/releases/latest/mapa_resumo.json` (redução de 18,8 MB para 4,2 MB, 77% mais leve).
  - Malha geográfica vetorial compacta `site/assets/geo/br_municipios.json` (5,5 MB) com polígonos simplificados (Douglas-Peucker 0.005) para Leaflet com preferCanvas.
- **Melhorias de Interface (Fase 2 / Fase 5)**:
  - Adição de camadas base Google Maps (Padrão, Relevo, Satélite) e OpenStreetMap sem dependência de chaves de API restritas.
  - Modal interativo "🏆 Top 10 Rankings" no topo do mapa com alternância automática entre Top 10 Brasil e Top 10 do estado selecionado.
  - Tooltips ricos com Nota 0–100, taxa TMI, posição nacional e estadual ao passar o mouse.
  - Links diretos na página "Downloads & Dicionário" para os novos artefatos do Indicador D1.1 e Rankings.
- **Governança e Travas de Qualidade**:
  - `pipeline/validate/quality_gates.py` atualizado para checagem estrita de plausibilidade biológica das taxas e escores de D1.1 e inclusão no manifesto de hashes SHA-256.

---

## [v0.1.0-draft] - 2026-10-23

### Adicionado
- Estrutura completa de governança e documentação:
  - `ESPECIFICACAO_INDICE_SAUDE_MUNICIPAL.md` (especificação técnica base);
  - `docs/PENDENCIAS.md` (rastreamento de 34 pendências metodológicas e técnicas `[A VALIDAR]` e `[A DECIDIR]`);
  - `docs/DECISOES.md` (registro de decisões arquiteturais ADR DEC-001 a DEC-008);
  - `docs/indicadores/` (fichas técnicas completas com templates padronizados para D1.1 até D3.4, D4 e Camada Privada).
- Arquivos de configuração paramétrica com marcação explícita de `null` e `"A_VALIDAR"`:
  - `config/metodologia_versao.txt` (`v0.1.0-draft`);
  - `config/indicadores.yaml` (catálogo dos indicadores D1 a D4 e Privado);
  - `config/pesos.yaml` (proposta preliminar com pesos iguais por dimensão parametrizada para sensibilidade);
  - `config/limites_referencia.yaml` (parâmetros de normalização com pendências marcadas).
- Registro formal de fontes de dados:
  - `sources/registry.yaml` cobrindo 12 fontes candidatas (SIM, SINASC, SIH/SUS, SIA/SUS, CNES, SI-PNI, SISAB/Siaps, IBGE, SIOPS, ANS, IEPS Data, IPS Brasil).
- Pipeline e travas de qualidade:
  - `pipeline/01_build_dim_municipio.py` (construção e teste de integridade da dimensão dos 5.570 municípios, de-para `ibge7` e `ibge6`);
  - `pipeline/validate/quality_gates.py` (travas de esquema, completude mínima, faixas plausíveis, anomalia ano a ano e verificação de SHA-256);
  - `pipeline/export_site_payloads.py` (geração de `meta_build.json` para consumo 100% fiel pela UI).
- Automação e CI/CD:
  - `.github/workflows/atualizar_dados.yml` (pipeline agendado com travas automáticas e abertura de issue em caso de falha);
  - `.github/workflows/monitor_descoberta.yml` (verificação periódica de novos períodos e catálogo de fontes).
- Front-end estático modular (`/site`):
  - Interface acessível e responsiva em Vanilla JS / HTML5 / CSS3;
  - `site/assets/js/audit_badge.js` garantindo que nenhum número seja exibido sem metadados de auditoria e qualidade;
  - Mapa coroplético e busca municipal com gaveta de detalhes (`drawer_municipio.js`);
  - Páginas "Como é calculado" e "Fontes" renderizadas dinamicamente a partir de `meta_build.json`.
