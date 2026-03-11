# Pipeline Welltory + Apple Health + sono (estratégia e scripts)

A estratégia recomendada para análise de correlações entre Welltory, Apple Health e sono, com DuckDB como camada intermediária, está documentada e os scripts estão disponíveis no workspace.

## Documento de estratégia

**Path:** `weltory_tips/estrategia_pipeline_duckdb_openclaw.md` (inside the skill: `skills/health-analytics/weltory_tips/`)

Contém:
- Arquitetura em camadas: raw → normalizadas → daily_features → correlações
- Princípio: dados primários (RMSSD, SDNN, HR, sono, atividade) sobre scores derivados (energy, stress, health quando vazios)
- Sono associado à **data de despertar**, não à data de início
- Tabela central: **daily_features** (por date_local: melhor medição Welltory, noite de sono, atividade, features derivadas, lags)
- Features derivadas: baseline HRV, razão HRV, delta HR, sleep score, recovery proxy, stress proxy, activity load, consistência circadiana, lags
- Correlações prioritárias com plausibilidade fisiológica (sono→HRV, atividade→HRV, ritmo circadiano, etc.)
- Ordem operacional: autopopular raw → validar → tabelas normalizadas → daily_features → correlações → interpretar

O agente deve ler esse documento antes de implementar ou executar a pipeline.

## Scripts (em `weltory_tips/` dentro do skill)

| Ficheiro | Uso |
|----------|-----|
| `auto_populate_raw_tables.py` | Autopopulação das tabelas raw_* a partir da DuckDB atual; identificar fontes e mapear; auditoria |
| `01_duckdb_schema.sql` | Schema das tabelas raw, normalizadas e de features |
| `04_validate_autopopulate.sql` | Validação da autopopulação (contagens, cobertura, métricas esperadas) |
| `02_build_daily_features.sql` | Construção de tabelas normalizadas e de daily_features (baselines, proxies, lags) |
| `03_correlation_queries.sql` | Queries de correlação prioritárias; ranking de associações |
| `welltory_apple_health_correlation.py` | Script Python para correlação Welltory ↔ Apple Health |
| `apple health sleep data.txt` | Notas sobre dados de sono do Apple Health |

## Integração com o skill

- **Base DuckDB do skill:** `data/health/duckdb/health.duckdb` (no container: `/data/data/health/duckdb/health.duckdb`; writable by node).
- O **skill health-analytics** implementa o fluxo completo: import (init_db + ingest) → tabelas de origem → consolidate (autopopulate + 02_daily_features) → tabelas consolidadas e `daily_features`. Os scripts do skill estão em `skills/health-analytics/scripts/`; os scripts de análise de correlações estão em `skills/health-analytics/weltory_tips/` (03_correlation_queries.sql, welltory_apple_health_correlation.py). O agente deve usar os scripts do skill para importar e consolidar; para análise de correlações deve executar os scripts em `weltory_tips/` (dentro do skill) conforme descrito no SKILL.
- Ordem recomendada pelo documento: executar autopopulação → validar → schema/normalizadas → daily_features → correlações.

## Referência rápida no SKILL

Quando o utilizador pedir análise de correlações Welltory / Apple Health / sono, ou pipeline de features diárias:

1. Ler `weltory_tips/estrategia_pipeline_duckdb_openclaw.md` (dentro do skill).
2. Usar os scripts em `weltory_tips/` (dentro do skill) na ordem descrita no documento e neste ficheiro.
3. Garantir que a base usada é a do health-skill e que sleep_phases (e demais tabelas) estão carregados conforme references/apple_health_export.md e references/weltory_export.md.
