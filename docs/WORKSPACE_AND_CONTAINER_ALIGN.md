# Alinhar workspace entre Gateway e agente

Para o Gateway e o agente (e scripts) usarem o **mesmo** workspace.

## Estado actual (alinhado)

- **Workspace root:** `/data` (no container) = `/docker/openclaw-b60d/data` (no host).
- **Config:** Em `/data/.openclaw/openclaw.json` está `agents.defaults.workspace: "/data"`, para o Gateway usar este workspace.
- **Skills:** Todos em `/data/skills/` (nostr-nak, skill-creator, twitter-nostr-sync). No host, colocar/copiar skills em `/docker/openclaw-b60d/data/skills/` para aparecerem no Dashboard.

## 1. Definir o workspace único

- **No container:** `/data` (working dir do container = workspace).
- **No host (VPS):** `/docker/openclaw-b60d/data` (mount para /data no container).

Skills ficam em `workspace/skills/` = `/data/skills/` no container.

## 2. Onde corre o Gateway?

- **Se o Gateway corre no mesmo container que o agente:** o workspace root que o Gateway deve usar é **`/data`**. Garantir que a config do Gateway (variável de ambiente, `openclaw.json`, ou config do compose) tem `workspace` / `cwd` / `workspaceRoot` = `/data`.
- **Se o Gateway corre no host (fora do container):** o workspace root deve ser **`/docker/openclaw-b60d/data`**. A config do Gateway no host deve apontar para esse path.

Resumo: Gateway e agente têm de usar o **mesmo** path que aponta para a mesma pasta (no container = `/data`, no host = `/docker/openclaw-b60d/data`).

## 3. Onde está a config do Gateway?

No container, o ficheiro habitual é `/data/.openclaw/openclaw.json`. Aí pode existir algo como:

```json
{
  "skills": {
    "load": {
      "extraDirs": ["/data/skills"],
      "watch": true
    }
  }
}
```

Se o Gateway não tiver uma opção explícita de “workspace root”, ele pode inferir o workspace do diretório de trabalho (cwd) ao arrancar. Nesse caso:

- **Gateway no container:** arrancar com `cwd` = `/data` (no Docker: `working_dir: /data` ou `WORKSPACE_ROOT=/data` se existir).
- **Gateway no host:** arrancar com `cwd` = `/docker/openclaw-b60d/data`.

Assim, “workspace” = esse cwd, e `skills/` = `cwd/skills/`.

## 4. Checklist para concordarem

1. **Confirmar o mount:** no host, `ls /docker/openclaw-b60d/data/skills/` deve mostrar os skills (nostr-nak, twitter-nostr-sync). No container, `docker exec openclaw-b60d-openclaw-1 ls /data/skills/` deve mostrar o mesmo.
2. **Config do Gateway:** ver onde o processo do Gateway lê “workspace” ou “skills” (openclaw.json, env, compose). Ajustar para o path correto:
   - no container → `/data` (e skills = `/data/skills`);
   - no host → `/docker/openclaw-b60d/data`.
3. **Scripts e agente:** no container, usar sempre paths sob `/data` (ex.: `/data/scripts/`, `/data/skills/`, `/data/twitter-archive-to-nostr/`). No host (SSH, cron no host), usar paths sob `/docker/openclaw-b60d/data`.
4. **Reiniciar o Gateway** após mudar config, para rescannar `skills/`.

Quando o Gateway estiver configurado com o mesmo workspace que o agente (e onde os skills estão), ambos “concordam” e o skill passa a aparecer.
