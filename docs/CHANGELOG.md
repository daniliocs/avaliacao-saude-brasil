# Changelog

Todas as alterações notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e este projeto segue [Versionamento Semântico](https://semver.org/lang/pt-BR/).

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
