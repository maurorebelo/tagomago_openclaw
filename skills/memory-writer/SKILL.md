---
name: memory-writer
description: "Review a conversation and write memory entries that pass the selection heuristics in memory/SELECTION.md. Use at end of day (heartbeat) or anytime after a substantial conversation to extract decisions, facts, and patterns worth keeping. Writes to memory/YYYY-MM-DD.md. Never overwrites — always appends."
---

# Memory Writer

Extracts what's worth remembering from a conversation and writes it to the daily memory file.

---

## When to use

- **On demand:** After any conversation where real decisions, project updates, or significant facts came up.
- **Heartbeat (end of day, ~21:00 GMT-3):** Routine daily capture.

---

## How to invoke

Pass the conversation summary to the script via stdin:

```bash
echo "<conversation summary>" | python3 /data/skills/memory-writer/scripts/write-memory.py
```

Or the agent can call it directly, passing the session context as text.

The script will:
1. Read `memory/SELECTION.md` for selection heuristics
2. Apply them via GPT-4o to filter and format what's worth keeping
3. Append the result to `/data/memory/YYYY-MM-DD.md` with a timestamp

---

## Output format (appended to daily file)

```
[HH:MM GMT-3] — memory-writer
- <bullet>
- <bullet>
```

---

## Scripts

```
skills/memory-writer/
├── SKILL.md
└── scripts/
    └── write-memory.py
```

## State

Uses `/data/memory/heartbeat-state.json` key `lastMemoryWrite` to track last run (for heartbeat throttling). On-demand calls ignore the throttle.
