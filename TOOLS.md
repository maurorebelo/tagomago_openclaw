# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## Twitter → Nostr sync

**Skill:** `skills/twitter-nostr-sync/SKILL.md` — use when the user asks to sync tweets to Nostr, import archive, or run/schedule the sync.

- **SSH host:** `hostinger-vps` (or set `NOSTR_REBROADCAST_SSH`)
- **Container:** `openclaw-b60d-openclaw-1` (or set `NOSTR_REBROADCAST_CONTAINER`)
- **VPS workspace (host path):** `/docker/openclaw-b60d/data` — use for rsync scripts (`VPS_DATA_PATH`); in container this is `/data`.
- **tweets.js on VPS:** `/docker/openclaw-b60d/data/data/tweets.js` (after unzipping archive under `/docker/openclaw-b60d/data/`)
- **Bridge:** wss://bridge.tagomago.me — **Target:** wss://nostr.tagomago.me

**Safety (lesson learned):** Content that wasn’t the user’s reached public relays. **Confirmed cause:** **Republish** — events from the bridge were pushed to public relays without checking `event.pubkey === NOSTR_DAMUS_PUBLIC_HEX_KEY`; fix: `republish-to-public-relays.sh` now keeps only events that pass that check. **Unconfirmed:** Live sync was assumed to use X’s *home* timeline (others’ tweets); the X API doc for “Get Timeline” actually describes the *user’s* timeline (only that user’s posts). Without verifying what `xurl timeline` calls, we can’t be sure the sync was a cause. As a safety measure, `sync.js` now filters with `author_id === xurl whoami.data.id`. We cannot unpublish what was already sent to relays. **To hide erroneous events you signed:** run `node scripts/sync-x-timeline-to-nostr/delete-erroneous-sync-events.js` (see skill); use `--dry-run` first. Events with *other* people’s pubkeys cannot be deleted by you (only those authors can publish NIP-09).

## xurl (X/Twitter) — tokens no segredo

O **xurl** não lê credenciais de variáveis de ambiente genéricas: lê apenas do ficheiro **`~/.xurl`** (YAML). Se os tokens de acesso estão no “segredo” do OpenClaw (Dashboard ou `.env` do container), o xurl só os usa se esse conteúdo **existir no ficheiro** `~/.xurl` dentro do container.

- No container o agente corre com workspace `/data`; se `HOME=/data`, o xurl procura `/data/.xurl`.
- **Para o segredo ser usado:** escrever o conteúdo do segredo em `/data/.xurl` (no container) no formato YAML que o xurl espera — por exemplo no arranque do container (script que faz `echo "$XURL_CONFIG" > /data/.xurl` ou montar um ficheiro do host em `/data/.xurl`). Depois disso o agente pode correr `xurl timeline`, `xurl whoami`, etc., sem pedir credenciais; não é preciso fluxo OAuth interativo se o ficheiro já tiver os tokens de user.
- Se o utilizador disser que “já colocou os tokens no segredo”, o agente deve verificar se `/data/.xurl` existe e tem conteúdo; se não tiver, explicar que o xurl só lê desse ficheiro e que o segredo tem de ser escrito lá (ou montado lá) uma vez.
- **Script env → .xurl:** `scripts/write-xurl-from-env.js` lê X_API_KEY, X_API_KEY_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET (e opcionalmente X_BEARER_TOKEN) e escreve `/data/.xurl` sem shell. Correr após deploy: `ssh hostinger-vps "docker exec openclaw-b60d-openclaw-1 node /data/scripts/write-xurl-from-env.js"`.
- **"Busca o meu último tweet" / "my last tweet":** Conta do humano = a que `xurl whoami` devolve com o auth em `/data/.xurl`. **Procedimento obrigatório:** (1) `xurl whoami` → guardar `data.id`; (2) `xurl timeline -n 1`; (3) só afirmar que é o "teu" tweet se `response.data[0].author_id === whoami.data.id`; caso contrário dizer "a timeline devolvida não é da conta autenticada" e mostrar whoami. **Nunca inventar tweets** — só reportar o output real; se o comando falhar, dizer.
- **Never post to Twitter/X.** xurl in this workspace is **read-only**: only `xurl timeline` and `xurl whoami` are used (by scripts and agent). Do **not** run `xurl post` or any command that creates/posts tweets. If someone asks to post on X, refuse or ask the human to do it themselves; do not use exec to post. (If you need to revoke the app: X → Settings → Security and account access → Apps and sessions → revoke the app that holds the tokens in `/data/.xurl`.)
- **Investigating who ran what:** xurl has no built-in logs. To try to find past usage: (1) On the VPS host, check shell history for the user that runs `docker exec` (e.g. `grep -i xurl ~/.bash_history` or `~/.zsh_history`). (2) Inside the container, if the agent runs as a user with a home dir, check that user’s `~/.bash_history` for `xurl` or `post`. (3) If OpenClaw Gateway has tool-call audit logging enabled (e.g. before_tool_call / tool_result_persist plugins), check those logs. (4) Going forward: use the read-only wrapper so every xurl call is logged and post is blocked — see below.
- **xurl read-only wrapper (audit + block post):** `scripts/xurl-readonly.sh` allows only `xurl whoami` and `xurl timeline ...`; logs every call to `XURL_AUDIT_LOG` (default `/data/.xurl-audit.log`); blocks any other subcommand (e.g. `post`). To install on the VPS container: (1) Copy the real xurl binary to e.g. `/data/bin/xurl-real` (or `/usr/local/bin/xurl-real`). (2) Copy `scripts/xurl-readonly.sh` to `/data/bin/xurl` and chmod +x. (3) Set `XURL_REAL=/data/bin/xurl-real` (or the path you used) and prepend `/data/bin` to PATH so `xurl` resolves to the wrapper. (4) Optionally set `XURL_AUDIT_LOG=/data/.xurl-audit.log`. Then any call to `xurl post` (or similar) is blocked and logged with status BLOCKED; allowed calls are logged with ALLOWED.

**Estrutura YAML que o xurl espera para OAuth2 user** (timeline, whoami): cada app pode ter `bearer_token` (app-only) e/ou `oauth2_tokens` (user). Exemplo com user:

```yaml
apps:
  default:
    client_id: "..."
    client_secret: "..."
    default_user: default
    oauth2_tokens:
      default:
        type: oauth2
        oauth2:
          access_token: "..."
          refresh_token: "..."
          expiration_time: 1234567890
    bearer_token:
      type: bearer
      bearer: "AAAA..."
default_app: default
```

Sem `oauth2_tokens` (access_token + refresh_token), o xurl só usa bearer e timeline/whoami dão 403. O segredo deve incluir `oauth2_tokens` para o app/user em uso.

**Como abrir e editar `.xurl` na VPS a partir do Mac (TextEdit)**

1. **Trazer o ficheiro da VPS para o Mac**  
   No terminal do Mac:
   ```bash
   scp hostinger-vps:/docker/openclaw-b60d/data/.xurl ~/Desktop/xurl.yaml
   ```
   (Se der "Permission denied" ou ficheiro não encontrado, na VPS o path pode estar noutro user; usa primeiro `ssh hostinger-vps "cat /docker/openclaw-b60d/data/.xurl" > ~/Desktop/xurl.yaml` para criar o ficheiro no Mac.)

2. **Abrir no TextEdit**  
   No Mac: abrir `~/Desktop/xurl.yaml` com TextEdit (ou arrastar para o TextEdit). Editar o YAML, guardar (Cmd+S).

3. **Enviar o ficheiro de volta para a VPS**  
   No terminal do Mac:
   ```bash
   scp ~/Desktop/xurl.yaml hostinger-vps:/tmp/.xurl
   ssh hostinger-vps "sudo cp /tmp/.xurl /docker/openclaw-b60d/data/.xurl"
   ```
   Assim o container passa a usar o conteúdo que editaste no TextEdit.

**O que colar/editar no YAML**  
O **conteúdo completo** no formato que o xurl espera (ver exemplo acima). Se geraste no Mac com `xurl auth oauth2`, podes usar o teu `~/.xurl` local: copiar para `~/Desktop/xurl.yaml`, abrir no TextEdit, guardar, e depois fazer o scp de volta para a VPS como em 3.

## Nostr — último note

- **"Qual o meu último note Nostr?" / "my last nostr":** Conta do humano = chave em USER.md (npub17kj… / NOSTR_DAMUS_PUBLIC_HEX_KEY). **Não pedir npub nem oferecer opções** — executar. (1) Pubkey: `NOSTR_DAMUS_PUBLIC_HEX_KEY`. (2) Consultar **sempre** os relays onde os teus notes estão: `wss://nostr.tagomago.me` e `wss://bridge.tagomago.me` (o live sync X→Nostr publica aí). Exemplo: `nak req -k 1 -a <pubkey_hex> -l 5 wss://nostr.tagomago.me wss://bridge.tagomago.me` e mostrar o mais recente (maior created_at). Mostrar só o output real; nunca inventar. Ao responder, não acrescentar menu do tipo "Quer que eu baixe/arquive/procure?" — parar após mostrar o note.
- **nak no ambiente:** Nesta instalação o nak está disponível (imagem com `/usr/local/bin/nak`, volume com `/data/go/bin` ou symlink em `/data/linuxbrew/.linuxbrew/bin`). Se o agente achar que nak está em falta, primeiro verificar com `nak --help` ou `/usr/local/bin/nak --help`; se mesmo assim falhar, executar `go install github.com/fiatjaf/nak@latest` e usar `$GOPATH/bin` (ex. `/data/go/bin`) no PATH — **não pedir autorização ao humano** para instalar; executar e depois prosseguir com o pedido (ex. último note).

## VPS tools (not in default Hostinger install)

- **nak** (Nostr CLI): para "meu último note", sync bridge→relay, etc. Usa NOSTR_DAMUS_PUBLIC_HEX_KEY (ou pubkey derivada da chave privada) para consultas por autor. **Como descobrir se a imagem é tua:** no VPS, `ls /docker/openclaw-b60d/custom-image/Dockerfile` — se existir, a imagem é build custom (base Hostinger + esse Dockerfile). Para nak ficar permanente: no Dockerfile adicionar instalação de Go e `go install github.com/fiatjaf/nak@latest`, depois copiar o binário para `/usr/local/bin` (fora de `/data`, para não depender do volume). Rebuild: `cd /docker/openclaw-b60d/custom-image && docker build -t openclaw-b60d-openclaw:with-tools .` e recriar o container.
- **gog** (skill no dashboard): skill built-in do OpenClaw (vem no pacote). No dashboard, Skills → marcar **gog**. Depende do binário `gog`, que no VPS está instalado via Linuxbrew (fórmula gogcli) em `/data/linuxbrew`; config em `/data/.config/gogcli`. Ou seja: a *skill* é a "gog" no OpenClaw; o *binário* é gogcli no /data.

## Workspace alignment (VPS: Gateway + agent)

- **Workspace root:** `/data` (container) = `/docker/openclaw-b60d/data` (host). Config: `agents.defaults.workspace: "/data"` em `/data/.openclaw/openclaw.json`.
- **Skills:** em `/data/skills/`. No host, colocar skills em `/docker/openclaw-b60d/data/skills/` para aparecerem no Dashboard.
- Gateway e agente devem usar o mesmo path; se o Gateway corre no container, `cwd` = `/data`. Reiniciar o Gateway após mudar config para rescannar skills.
- **Permissões do workspace (evitar EACCES):** O agente pode correr como utilizador não-root dentro do container; se os ficheiros em `/data` no host forem de root, dá EACCES ao escrever. No host: `sudo chown -R ubuntu:ubuntu /docker/openclaw-b60d/data` (ou 1000:1000). Não alterar `user:` no docker-compose — forçar UID 1000 no compose pode impedir o OpenClaw de arrancar. Se após git pull ou operações com sudo os ficheiros ficarem root, repetir o chown.

## Reference setup (alignment baseline)

Use this as the baseline when comparing “my install vs expected” (see [docs/INSTALACAO_ALIGNMENT.md](docs/INSTALACAO_ALIGNMENT.md)).

| Item | Value |
|------|--------|
| **Workspace (container)** | `/data` |
| **Workspace (host)** | `/docker/openclaw-b60d/data` |
| **Container name** | `openclaw-b60d-openclaw-1` |
| **Skills path (container)** | `/data/skills/` |
| **Config** | `/data/.openclaw/openclaw.json` |
| **Restart Gateway** | Restart the OpenClaw Gateway process/container after changing config so it rescans skills. (Document here how you do it on your VPS if different from default.) |

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
