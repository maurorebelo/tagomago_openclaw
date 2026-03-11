# Apple Health export: paths, formato, mesma DuckDB

## Onde está o export (neste setup)

- **Container:** `/data/APPLE_HEALTH_data_export.zip`
- **Host (VPS):** `/docker/openclaw-b60d/data/APPLE_HEALTH_data_export.zip`
- **Conteúdo do zip:** ficheiro principal é **XML** (export nativo Apple), não JSON: `apple_health_export/exportar.xml`

Ferramentas como Health Auto Export geram JSON a partir deste XML; o export bruto da Apple é sempre XML. A skill deve **ler XML** (exportar.xml) para sleep phases e para quaisquer outros dados do Apple Health — não assumir JSON.

## Base DuckDB única

Toda a ingestão (sleep phases, heart rate, steps, etc.) deve ir para **a mesma** base DuckDB:

- **Path (neste setup, legível pelo agente):** `data/data/health/duckdb/health.duckdb` (no container: `/data/data/health/duckdb/health.duckdb`; owner node para o processo do agente).
- Evitar bases em `data/health/duckdb/` com owner root (ficam inacessíveis ao agente). Usar a base em `data/data/health/duckdb/`.
- Alternativa noutros setups: `data/health/health.duckdb` — alinhar com `init_db.py` e diretórios existentes.

Não criar bases separadas (ex.: `health_sleep.duckdb`); usar sempre esta base para Apple Health e Weltory.

## Sleep phases (fases de sono)

- **Origem no XML:** elementos `<Record type="HKCategoryTypeIdentifierSleepAnalysis">` com atributo `value` igual a uma de:
  - `HKCategoryValueSleepAnalysisAsleepCore` (Core)
  - `HKCategoryValueSleepAnalysisAsleepDeep` (Deep)
  - `HKCategoryValueSleepAnalysisAsleepREM` (REM)
  - `HKCategoryValueSleepAnalysisAwake` (Awake)
  - `HKCategoryValueSleepAnalysisInBed` (In Bed)
  - `HKCategoryValueSleepAnalysisAsleepUnspecified`
- **Atributos úteis:** `startDate`, `endDate`, `value`, `sourceName`, `creationDate`, `device`, `sourceVersion`
- **Tabela na DuckDB:** `sleep_phases` (colunas: `start_date`, `end_date`, `value`, `source_name`, `creation_date`, `device`, `source_version`)

Script de exemplo que carrega sleep do XML para esta base: `scripts/apple-health-sleep-to-duckdb.py` (workspace root); usa `iterparse` no `exportar.xml` e faz INSERT em `sleep_phases`.

## Outros dados em XML (não JSON)

Qualquer outro tipo de dado do Apple Health no export (heart rate, steps, workouts, etc.) está também em **XML** no mesmo `exportar.xml` (ou noutros ficheiros dentro do zip). A skill deve:

1. Procurar o zip em `/data` (ou path de imports: `data/health/imports/`).
2. Extrair e parsear **XML** (ex.: `exportar.xml`), não apenas JSON.
3. Inserir/upsert na **mesma** base DuckDB, nas tabelas apropriadas (ver schema.md).

## Weltory

O export **Weltory** (zip em `/data/WELTORY_data_export.zip`) contém apenas ficheiros **JSON** (profile.json, rr.json, data_flow_*.json). Não há XML. As métricas da UI (stress, energy, health) estão em **rr.json** (campos `context_arousal_percent`, `context_energy_percent`, `resilience`, etc.); os `data_flow_*.json` têm a mesma lógica mas com `data.result.items` (neste export, vazio). Ingestão: ler rr.json (e data_flow quando items não for vazio) e carregar na mesma DuckDB. Ver [references/weltory_export.md](references/weltory_export.md).

## Resumo para o agente

- **Apple Health:** zip em `/data/APPLE_HEALTH_data_export.zip`; XML em `apple_health_export/exportar.xml`. Formato: **XML** (nativo Apple); não assumir JSON.
- **Weltory:** zip em `/data/WELTORY_data_export.zip`; apenas **JSON** (sem XML).
- **Base:** uma só DuckDB — `data/data/health/duckdb/health.duckdb` (correr ingestão como user `node` para escrever nesta base).
- **Sleep:** tabela `sleep_phases` (colunas: start_date, end_date, value, source_name, creation_date, device, source_version); origem = `Record` com `type="HKCategoryTypeIdentifierSleepAnalysis"`.
- **Outros dados Apple:** ler do mesmo XML e carregar para a mesma base. Para **quantity types** (passos, exercício, energia): ver [references/apple_health_quantities.md](references/apple_health_quantities.md) — extrair StepCount, AppleExerciseTime, ActiveEnergyBurned, BasalEnergyBurned; agregar por dia; tabela `apple_quantity_daily`.
