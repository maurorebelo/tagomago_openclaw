# Weltory export: estrutura JSON, métricas da UI (stress, energy, health)

## Onde está

- **Container:** `/data/WELTORY_data_export.zip`
- **Host (VPS):** `/docker/openclaw-b60d/data/WELTORY_data_export.zip`
- **Conteúdo:** apenas ficheiros **JSON** (sem XML). Principais: `profile.json`, `rr.json`, e muitos `data_flow_*.json`.

## Métricas da UI: onde estão nos dados

A UI do Weltory mostra **stress**, **energy**, **health** (e focus, etc.). Neste export essas métricas aparecem em **dois sítios**:

### 1. `rr.json` (série temporal por medição) — **aqui há dados**

Lista de medições (ex.: 2597 entradas). Cada elemento é um objeto com os campos que a UI usa:

| Campo no JSON | Métrica na UI | Exemplo |
|---------------|----------------|---------|
| `context_arousal_percent` | Stress (HRV) | 76.0 |
| `stress_category` | Categoria stress | "HIGH_BOIL", "LOW_GREEN", etc. |
| `context_energy_percent` | Energy (HRV) | 34.0 |
| `energy_category` | Categoria energy | "LOW_YELLOW", etc. |
| `energy_trend` | Tendência energy | 3.0 |
| `resilience` | Health | 94.0 |
| `productivity_percent` | Produtividade | 58.0 |

Outros campos úteis por linha: `id`, `time_start`, `time_end`, `duration`, `bpm`, `meanrr`, `rmssd`, `sdnn`, `time_of_day` (morning/evening/…), `device_name`, `source_name`, `is_sleeping`, `measurement_quality`, `rr_stream_for_nf` (array de intervalos RR em ms).

**Ingestão:** carregar `rr.json` para a mesma DuckDB (ex.: tabela `weltory_rr` ou `weltory_measurements`). Colunas mínimas sugeridas: `id`, `time_start`, `time_end`, `duration`, `bpm`, `context_arousal_percent`, `context_energy_percent`, `resilience`, `stress_category`, `energy_category`, `time_of_day`, `source_name`, `device_name`. Assim as queries podem responder a “stress/energy/health ao longo do tempo”.

### 2. `data_flow_*.json` (uma série por ficheiro) — **neste export, items vazio**

Cada ficheiro tem a forma:

```json
[
  {
    "title": "Stress (HRV)",
    "slug": "rr_context_arousal_percent",
    "data": {
      "success": true,
      "result": {
        "items": []
      }
    }
  }
]
```

- **title:** nome da métrica como na UI (Stress (HRV), Energy (HRV), Health, Morning stress, Day energy, etc.).
- **slug:** identificador interno; corresponde muitas vezes a um campo de `rr.json` (ex.: `rr_context_arousal_percent` → `context_arousal_percent`, `rr_resilience` → `resilience`).
- **data.result.items:** série temporal da métrica. **Neste export está vazio** em todos os data_flow_*.json. Quando houver dados, cada item em `items` tende a ter pelo menos data e valor (ex.: `date`, `value` ou `time_start`, `value`).

**Ingestão quando items não for vazio:** para cada `data_flow_*.json` com `data.result.items` não vazio, inserir na DuckDB (ex.: tabela por slug ou tabela única `weltory_data_flow` com colunas `slug`, `date`, `value` e metadados). Assim a skill pode usar tanto `rr.json` como `data_flow_*` conforme o que estiver preenchido.

## Mapeamento UI → ficheiros

- **Stress:** `rr.json` → `context_arousal_percent`, `stress_category`; ou `data_flow_stress_hrv_.json` / `data_flow_morning_stress.json`, etc., via `items`.
- **Energy:** `rr.json` → `context_energy_percent`, `energy_category`, `energy_trend`; ou `data_flow_energy_hrv_.json`, `data_flow_day_energy.json`, etc.
- **Health:** `rr.json` → `resilience`; ou `data_flow_health.json` (slug `rr_resilience`).
- **Focus:** `data_flow_focus.json`, `data_flow_morning_focus.json`, etc. (neste export, items vazio).

## profile.json

Objeto com dados de perfil: `full_name`, `email`, `created_at`, `user_team`, `height`, `weight`, `age`. Útil para contexto; pode ir para uma tabela `weltory_profile` ou ser ignorado na ingestão de séries.

## Resumo para o agente

- **Stress / Energy / Health da UI:** neste export estão em **`rr.json`** (campos `context_arousal_percent`, `context_energy_percent`, `resilience`, mais `stress_category`, `energy_category`, etc.).
- **Estrutura de rr.json:** lista de objetos; cada um = uma medição com `time_start`, `time_end`, métricas HRV e as colunas da tabela acima.
- **data_flow_*.json:** mesma métricas por “flow”; quando `data.result.items` tiver dados, ingerir para a mesma DuckDB.
- **Base:** usar a mesma DuckDB do health-skill (`data/data/health/duckdb/health.duckdb`). Criar tabelas como `weltory_rr` (ou `weltory_measurements`) e, se necessário, `weltory_data_flow` quando houver items.
