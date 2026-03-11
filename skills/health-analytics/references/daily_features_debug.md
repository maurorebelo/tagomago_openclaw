# Métrica em falta em daily_features — causas e ordem de debug

## Por que uma métrica pode faltar em daily_features

1. **Não entrou no ingest** — O campo não existe ou não é lido do XML/JSON de origem.
2. **Entrou, mas não foi mapeada** — O ingest escreveu numa coluna/tabela que o autopopulate não considera.
3. **Foi mapeada com nome diferente** — O nome na raw (ex.: `raw_apple_quantities.metric`) não é o que `02_daily_features.sql` usa (ex.: `steps_daily`, `active_kcal_daily`).
4. **Foi para uma tabela raw que _daily_base não consome** — A métrica está numa raw que não entra no JOIN de `_daily_base` (só entram `raw_welltory`, `raw_apple_sleep_sessions`, `raw_apple_quantities`, `raw_apple_mindful_sessions` → hrv_daily, sleep_nights, activity_daily, physiology_daily).

---

## Ordem certa de debug

Seguir exactamente esta ordem:

### 1. Confirmar se o valor existe na fonte

- **Apple Health:** procurar no XML bruto (export.xml / exportar.xml) o `Record` ou tipo em questão.
- **Welltory:** procurar no rr.json (ou data_flow_*.json) o campo/slug.

### 2. Confirmar se o ingest escreve em tabela de origem

- Consultar: `weltory_rr`, `sleep_phases`, `apple_quantity_daily` (ou outra tabela que o ingest preencha).
- Verificar se a coluna existe e tem dados para as datas esperadas.

### 3. Confirmar se o autopopulate lê essa coluna

- Em `weltory_tips/auto_populate_raw_tables.py`: ver o mapeamento **origem → raw_*** (direct_column_mapping para welltory, populate_sleep para sleep, wide_daily_unpivot para quantities, etc.).
- Confirmar que a tabela de origem está entre as que o autopopulate considera e que o nome da coluna está no mapeamento.

### 4. Confirmar o nome final da métrica

- Ver o valor gravado em `wellness.raw_*` (ex.: `raw_apple_quantities.metric`).
- Em `02_daily_features.sql`: ver o que `activity_daily`, `physiology_daily`, `sleep_nights`, `hrv_daily` esperam (ex.: `metric = 'steps_daily'`, `metric = 'active_kcal_daily'`).
- O nome na raw tem de coincidir com o usado no SQL.

### 5. Confirmar se a raw alimenta _daily_base

- Em `02_daily_features.sql`, a tabela `_daily_base` faz LEFT JOIN de:
  - `hrv_daily` (← raw_welltory)
  - `sleep_nights` (← raw_apple_sleep_sessions)
  - `activity_daily` (← raw_apple_quantities)
  - `physiology_daily` (← raw_apple_quantities + raw_apple_mindful_sessions)
- Se a métrica estiver noutra raw (ex.: tabela que não alimenta nenhuma destas), não chega a `daily_features`.
