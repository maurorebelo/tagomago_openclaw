# Health Analytics no VPS (OpenClaw)

O skill **health-analytics** corre no mesmo workspace que os outros skills. O agente (processo node) deve conseguir executar os scripts Python e ler/escrever a DuckDB.

**O código já está no repo:** ao fazer deploy para a VPS, o skill `skills/health-analytics/` (que inclui `weltory_tips/` dentro do skill) fica disponível no container. O node invoca os scripts quando o utilizador pede import ou análise.

## Caminhos no VPS

- **Workspace no host:** `/docker/openclaw-b60d/data`
- **Skill no host:** `/docker/openclaw-b60d/data/skills/health-analytics/`
- **No container (workspace = /data):** skill em `/data/skills/health-analytics/`, scripts em `/data/skills/health-analytics/scripts/`
- **DuckDB (legível/gravable pelo node):** `data/health/duckdb/health.duckdb` → no container: **`/data/data/health/duckdb/health.duckdb`**
- **ZIPs no container:** `/data/APPLE_HEALTH_data_export.zip`, `/data/WELTORY_data_export.zip` (ou em `data/health/imports/`)

## Garantir que o node consegue escrever na base

O directório da DuckDB deve existir e ter permissões para o user que corre o agente (ex.: `node`):

```bash
# No host (criar dir e dar ownership ao user do container)
sudo mkdir -p /docker/openclaw-b60d/data/data/health/duckdb
sudo chown -R 1000:1000 /docker/openclaw-b60d/data/data/health
```

(Se o container usar outro UID, ajustar. Ver com `docker exec openclaw-b60d-openclaw-1 id`.)

## Como correr no container (para testar)

A partir do **workspace root** no container (`/data`):

```bash
# 1. Criar a base e tabelas (idempotente)
python3 /data/skills/health-analytics/scripts/init_db.py --workspace /data

# 2. Importar um ZIP (Apple Health ou Weltory); isto já chama consolidate no fim
python3 /data/skills/health-analytics/scripts/ingest.py --zip /data/APPLE_HEALTH_data_export.zip --workspace /data

# Ou só Weltory:
python3 /data/skills/health-analytics/scripts/ingest.py --zip /data/WELTORY_data_export.zip --workspace /data

# 3. (Opcional) Reconsolidar sem re-importar
python3 /data/skills/health-analytics/scripts/consolidate.py --db /data/data/health/duckdb/health.duckdb --workspace /data --clear-raw
```

O agente (quando invoca o skill) deve usar estes comandos com `--workspace /data` (ou o path do workspace no container).

## Dependências no container

- **Python 3** com **duckdb**
- Opcional: `pandas`, `lxml` ou `xmltodict` para ingest

Se faltar duckdb:

```bash
docker exec openclaw-b60d-openclaw-1 pip install duckdb
```

## Resumo

- O skill é deployado como um único pacote; na VPS fica em `/data/skills/health-analytics` (inclui `weltory_tips/` e scripts de correlação dentro do skill).
- Garantir que `data/health/duckdb` existe e é writable pelo user do processo (node).
- Correr `init_db.py` uma vez; depois `ingest.py --zip <path>` para cada novo export; o agente pode chamar estes scripts quando o utilizador pedir.
