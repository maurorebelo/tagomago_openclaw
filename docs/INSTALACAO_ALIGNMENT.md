# OpenClaw installation alignment

Align the VPS OpenClaw setup with what this repo assumes. Scripts and docs live in the repo (GitHub canonical); run the steps on the VPS or via SSH. VPS remains canonical for runtime (config, data).

Reference: [TOOLS.md](../TOOLS.md), [config/README.md](../config/README.md), [SYNC.md](../SYNC.md).

---

## Phase 1: Map current state (read-only on VPS)

Run from repo root (local or any machine with SSH to the VPS). The script runs checks inside the container.

```bash
./scripts/verify-openclaw-state.sh
```

Or manually on the VPS:

```bash
ssh hostinger-vps "docker exec openclaw-b60d-openclaw-1 cat /data/.openclaw/openclaw.json" | jq '.agents.defaults.workspace, .skills.load'
ssh hostinger-vps "docker exec openclaw-b60d-openclaw-1 ls -la /data/skills/"
```

Record: Is `agents.defaults.workspace` equal to `"/data"`? Do you see `twitter-nostr-sync`, `health-analytics` under `/data/skills/`?

---

## Phase 2: Align config and rescan

1. **Set workspace in config**  
   On the VPS, inside the container, run (script lives in repo, so after `git pull` on VPS it’s at `/data/scripts/ensure-workspace-config.js`):

   ```bash
   ssh hostinger-vps "docker exec openclaw-b60d-openclaw-1 node /data/scripts/ensure-workspace-config.js"
   ```

   Or edit `/data/.openclaw/openclaw.json` in the container and set `agents.defaults.workspace` to `"/data"` (see [config/openclaw.json.example](../config/openclaw.json.example)).

2. **Optional: extraDirs**  
   If the Gateway still doesn’t list workspace skills, add or set `skills.load.extraDirs` to include `["/data/skills"]` in `openclaw.json`.

3. **Rescan skills**  
   Restart the Gateway (or use Dashboard “Refresh” if available) so it picks up `/data/skills/`.

4. **Verify in Dashboard**  
   Confirm WORKSPACE SKILLS includes `twitter-nostr-sync` and other deployed skills.

---

## Phase 3: Sanitize and version config

Run on the VPS (inside the container). Scripts are in the repo; after pull, they are under `/data/scripts/`.

```bash
ssh hostinger-vps "docker exec openclaw-b60d-openclaw-1 sh -c 'cd /data && ./scripts/sync-openclaw-config-to-repo.sh'"
```

This writes `config/openclaw.sanitized.json` in the repo (on the VPS at `/data/config/`). Then either:

- From VPS: commit and push from `/data` if git is configured there, or  
- Copy the file to local and commit/push from local so GitHub has the updated shape.

See [config/README.md](../config/README.md).

---

## Phase 4: Document your reference setup

Keep the baseline in [TOOLS.md](../TOOLS.md) under “Reference setup (alignment baseline)”: workspace path, container name, skills path, how you restart the Gateway. Use it for future “my install vs expected” checks.

---

## Phase 5: Validate with one skill

In a channel where the OpenClaw agent runs, ask it to use the twitter-nostr-sync skill, e.g. “What do I need to run the Twitter → Nostr sync?” or “List the steps to run a one-off import from tweets.js on the VPS.” Confirm the agent sees the skill and follows the steps from [skills/twitter-nostr-sync/SKILL.md](../skills/twitter-nostr-sync/SKILL.md).
