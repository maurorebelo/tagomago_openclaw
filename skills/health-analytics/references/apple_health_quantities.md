# Apple Health XML – o que o agente deve testar (quantity types)

Para além de **sleep phases** (`HKCategoryTypeIdentifierSleepAnalysis`), o agente deve extrair do mesmo **export.xml** os seguintes *Quantity* types para alimentar `activity_daily` / `daily_features`.

## 1. Abrir o XML

- Ficheiro: **export.xml** (ou exportar.xml) dentro do ZIP Apple Health.
- Usar stream parse (ex.: `iterparse`) para não carregar o XML todo em memória.

## 2. Procurar `Record` com estes `type`

| type (no XML) | Uso |
|---------------|-----|
| `HKQuantityTypeIdentifierStepCount` | Passos |
| `HKQuantityTypeIdentifierAppleExerciseTime` | Minutos de exercício |
| `HKQuantityTypeIdentifierActiveEnergyBurned` | Energia activa (kcal) |
| `HKQuantityTypeIdentifierBasalEnergyBurned` | Energia basal (kcal) |

## 3. De cada `Record` extrair

- **startDate**
- **endDate**
- **value** (número)

## 4. Mapear type → métrica diária

| type | Métrica (para agregação) |
|------|--------------------------|
| StepCount | steps |
| AppleExerciseTime | exercise_minutes |
| ActiveEnergyBurned | active_kcal |
| BasalEnergyBurned | basal_kcal |

## 5. Data local

- **date_local** = `DATE(startDate)`  
  (usar o dia do startDate; normalizar timezone se necessário.)

## 6. Agregar por dia

Por cada `date_local`:

- **steps_daily** = SUM(steps)
- **exercise_minutes_daily** = SUM(exercise_minutes)
- **active_kcal_daily** = SUM(active_kcal)
- **basal_kcal_daily** = SUM(basal_kcal)

## Onde guardar

- Tabela de origem para o pipeline: **apple_quantity_daily**  
  Colunas: `date_local`, `steps_daily`, `exercise_minutes_daily`, `active_kcal_daily`, `basal_kcal_daily`.  
- O script **auto_populate_raw_tables** (em `weltory_tips/` dentro do skill) lê esta tabela em formato “wide” e preenche **wellness.raw_apple_quantities**; o **02_daily_features.sql** agrega de `raw_apple_quantities` para **activity_daily** e **daily_features**.

## Resumo para o agente

1. Abrir export.xml (do ZIP Apple Health).
2. Procurar `Record` com `type` igual a um dos quatro quantity types acima.
3. Extrair startDate, endDate, value.
4. Mapear type → steps | exercise_minutes | active_kcal | basal_kcal.
5. Obter date_local = DATE(startDate).
6. Agregar por dia e inserir em **apple_quantity_daily**.
