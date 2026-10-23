# Ficha Técnica: Camada Privada (Saúde Suplementar e Oferta Não-SUS)

## 1. Identificação
- **ID:** PRIV (PRIV.1 e PRIV.2)
- **Nome:** Indicadores de Saúde Suplementar e Infraestrutura Não-SUS
- **Dimensão:** Camada Privada
- **Sentido:** Informativo / Contexto de Mercado (**FORA DA NOTA PRINCIPAL**)
- **Status:** Em validação (`PEND-032`, `DEC-001`)

## 2. Definição Conceitual
Medição da presença do setor de saúde suplementar no território municipal, permitindo analisar em que medida a demanda assistencial da população local é absorvida por planos privados ou depende exclusivamente do SUS.

## 3. Subindicadores
- **PRIV.1 — Taxa de Cobertura de Planos Privados de Assistência Médica:**
  $$\text{Taxa de Cobertura (\%)} = \frac{\text{Número de beneficiários de planos médico-hospitalares residentes}}{\text{População residente total (IBGE)}} \times 100$$
- **PRIV.2 — Leitos Hospitalares Privados Não Conveniados ao SUS:**
  $$\text{Leitos Privados / 1.000 hab} = \frac{\text{Leitos hospitalares privados exclusivamente não-SUS}}{\text{População residente}} \times 1.000$$

## 4. Fontes de Dados
- **Beneficiários:** Agência Nacional de Saúde Suplementar (ANS) — Caderno de Informações da Saúde Suplementar / Dados Abertos ANS.
- **Leitos Não-SUS:** Ministério da Saúde / DATASUS — CNES Leitos.
- **População:** IBGE.

## 5. Justificativa de Exclusão da Nota Geral
O índice foca na qualidade do SUS e das condições de saúde no território. A cobertura privada reflete primariamente a renda média formal e o nível de emprego da população. Criar um índice composto misturando SUS e planos suplementares ocultaria a realidade do sistema público universal.

## 6. Referências
- ANS — Agência Nacional de Saúde Suplementar. Sala de Situação e Tabnet ANS.
