# Long-term memory (curated)

2026-03-11: Proactive preference — monitor conversations for stable preferences and facts about the user. When the assistant identifies a repeatable preference or factual detail, it should propose a memory entry to the user; only record the memory after explicit user confirmation. Save proposals and confirmations with timestamps.

(Do not auto-populate personal identity fields without user-provided values.)

2026-03-11 (strong preference): Reply style = conversational, short, direct. Avoid long lists or report-style answers unless the user explicitly requests a report. Treat this as a high-priority behavior constraint for future replies.

2026-03-11 (interaction preference): When user asks to go "one by one", respond exactly one item at a time and in one sentence each; pause after each sentence for the user's confirmation or next instruction. Mark this as high-priority reply behavior.

2026-03-16 (doubt vs instruction): Read from the language: when Mauro sounds unsure or like he's asking to understand (doubt), give clarification; when he sounds like he's telling you what to do (conviction/instruction), act. No fixed rule for every message — infer from how he wrote.

2026-03-18 (xurl / tweets): When asked "list my last tweet", the agent returned a fabricated tweet (William Shatner). It must run `xurl timeline -n 1` and report only the real output; never invent or substitute tweet content. Rules added in TOOLS.md and AGENTS.md (Safety).

2026-03-18 (Nostr / último note): Same pattern as xurl — when asked "my last nostr" or "meu último note", do not ask for npub or offer options. Use the key from the environment (NOSTR_DAMUS_PUBLIC_HEX_KEY / NOSTR_PRIVATE_KEY), run `nak req -k 1 -a <pubkey> -l 1 <relays>`. If nak is not installed, install with `go install github.com/fiatjaf/nak@latest` or tell the user. See TOOLS.md section "Nostr — último note".

2026-03-18 (Twitter + njump): User reported that when they asked to sync Twitter with Nostr, njump.me links or content ended up on their Twitter. The sync scripts in the repo only read from Twitter and write to Nostr; they do not post to Twitter. The agent (OpenClaw) has exec and could have run a post command (e.g. xurl post) with njump links — e.g. if it interpreted "sync" as "announce the sync on Twitter". Never post to Twitter/X; xurl is read-only (AGENTS.md, TOOLS.md). User should revoke the X app in Settings → Apps and sessions if they want to prevent any future posts.

2026-03-16 (concrete example — xurl conversation): When Mauro gave clear instructions ("retrieve my last tweet", "enable auto read public social", "run xurl auth oauth2 for me", "you run for me", "I want you to execute my requests without further infinite confirmation"), the agent kept replying with "which do you prefer?" or two options instead of acting. Wrong pattern: instruction → offer options. Right: instruction → do it, or explain in one sentence why it can't be done here (e.g. "I run inside the container; you're on the host — run this exact command in your shell: …" or "I'll run it in the container and show you the result"). If your environment (container) is different from Mauro's (host terminal), say so upfront and give the command that works in his environment, or run in your environment and report the outcome. Do not answer a direct request with a menu of choices.
