# Apple Health export no VPS — Sleep Phases

## Onde está

- **Zip (host):** `/docker/openclaw-b60d/data/APPLE_HEALTH_data_export.zip`
- **No container:** `/data/APPLE_HEALTH_data_export.zip`
- **Extraído em /tmp (host):** `/tmp/apple_health_tmp/apple_health_export/`
  - **XML principal:** `exportar.xml` (export nativo Apple = XML, não JSON)

## Sleep phases no export

Os dados de sono vêm em **XML**, em registos com `type="HKCategoryTypeIdentifierSleepAnalysis"`. Não há JSON no export nativo; ferramentas como Health Auto Export - JSON+CSV geram JSON a partir deste XML.

### Estatísticas (contagem no XML)

| value (stage) | aprox. registos |
|---------------|------------------|
| HKCategoryValueSleepAnalysisAsleepCore | ~14k |
| HKCategoryValueSleepAnalysisAsleepDeep | ~4.4k |
| HKCategoryValueSleepAnalysisAsleepREM | ~6.4k |
| HKCategoryValueSleepAnalysisAsleepUnspecified | ~17k |
| HKCategoryValueSleepAnalysisAwake | ~5.7k |
| HKCategoryValueSleepAnalysisInBed | ~5.7k |
| **Total Records SleepAnalysis** | **53 528** |

### Atributos de cada `<Record>`

- `type="HKCategoryTypeIdentifierSleepAnalysis"`
- `sourceName` (ex.: "Relógio")
- `device` (XML-escaped)
- `creationDate` (ISO)
- `startDate` (início do intervalo)
- `endDate` (fim do intervalo)
- `value` = uma de:  
  `AsleepCore`, `AsleepDeep`, `AsleepREM`, `AsleepUnspecified`, `Awake`, `InBed`

## Obter dados em JSON

1. **Ferramenta externa:** Health Auto Export - JSON+CSV (gera JSON a partir do XML).
2. **Script no VPS:** parse do `exportar.xml` (ex.: Python + `xml.etree` ou `lxml`), extrair os `Record` com `type="HKCategoryTypeIdentifierSleepAnalysis"` e escrever JSON com `startDate`, `endDate`, `value` (e opcionalmente `sourceName`).

## SQLite alternativo

Existe também `/docker/openclaw-b60d/data/data/health/health.sqlite` no host (possível conversão prévia). Para sleep phases, verificar se existe tabela/views com SleepAnalysis ou equivalentes.

## Carregar sleep phases para DuckDB

Script no repo: `scripts/apple-health-sleep-to-duckdb.py`. Cria a tabela `sleep_phases` em DuckDB e carrega os registos do XML.

**No container (VPS):**

```bash
# Garantir que o zip está em /data e que o script está em /data/scripts/
python3 /data/scripts/apple-health-sleep-to-duckdb.py
```

- O script extrai `exportar.xml` do zip para `/data/apple_health_export/` se ainda não existir.
- A base DuckDB fica em **`/data/health_sleep.duckdb`** (no host: `/docker/openclaw-b60d/data/health_sleep.duckdb`).
- Tabela: `sleep_phases` com colunas `start_date`, `end_date`, `value`, `source_name`, `creation_date`.

**Exemplo de queries:**

```sql
-- No container: duckdb /data/health_sleep.duckdb
SELECT value, count(*) FROM sleep_phases GROUP BY value ORDER BY count(*) DESC;
SELECT * FROM sleep_phases WHERE start_date >= '2025-01-01' LIMIT 10;
```
