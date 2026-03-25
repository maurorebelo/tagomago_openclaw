# HEARTBEAT.md

## Daily memory write (end of day, ~21:00 GMT-3)

Use the `memory-writer` skill. Pipe today's conversation summary to the script:

```bash
echo "<session summary>" | python3 /data/skills/memory-writer/scripts/write-memory.py
```

Can also be triggered on demand anytime after a substantial conversation. Use `--force` to bypass the 4h throttle.

---

## User profiler scans (background, no confirmation needed)

Run only if the state file (`/data/memory/profiler-state.json`) shows the last scan was past the threshold.

- **Nostr scan** (twice/week): `skills/user-profiler/scripts/scan-nostr.py`
- **Blog scan** (weekly): `skills/user-profiler/scripts/scan-blog.py`
- **Notion scan** (twice/week): `skills/user-profiler/scripts/scan-notion.py`

Report briefly at next conversation: "Nostr scan: N reinforcements, N contradictions, N candidates."

---

## Stay quiet when

- It's between 23:00–08:00 GMT-3 and nothing is urgent
- Nothing new since last check
