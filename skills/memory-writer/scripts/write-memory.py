#!/usr/bin/env python3
"""
Write daily memory entries from a conversation.

Usage:
  echo "<conversation text>" | python3 write-memory.py
  python3 write-memory.py --force    # skip heartbeat throttle

Reads memory/SELECTION.md for heuristics, calls GPT-4o to filter and format,
appends result to /data/memory/YYYY-MM-DD.md.

Requires: OPENAI_API_KEY in environment.
State: /data/memory/heartbeat-state.json (key: lastMemoryWrite)
"""

import sys
import os
import json
import ssl
import urllib.request
import time
from datetime import date, datetime, timezone, timedelta

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

WORKSPACE       = '/data'
SELECTION_PATH  = os.path.join(WORKSPACE, 'memory', 'SELECTION.md')
STATE_PATH      = os.path.join(WORKSPACE, 'memory', 'heartbeat-state.json')
MEMORY_DIR      = os.path.join(WORKSPACE, 'memory')
MIN_INTERVAL_H  = 4   # hours — heartbeat throttle (on-demand always runs)

GMT3 = timezone(timedelta(hours=-3))


# ─── State ────────────────────────────────────────────────────────────────────

def load_state():
    os.makedirs(MEMORY_DIR, exist_ok=True)
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {}

def save_state(state):
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2)

def too_soon(state):
    last = state.get('lastMemoryWrite')
    return bool(last) and (time.time() - last) / 3600 < MIN_INTERVAL_H


# ─── OpenAI ───────────────────────────────────────────────────────────────────

def call_openai(messages, max_tokens=600):
    key = os.environ.get('OPENAI_API_KEY', '')
    if not key:
        print('ERROR: OPENAI_API_KEY not set', file=sys.stderr)
        return None
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_SSL_CTX))
    req = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=json.dumps({
            'model': 'gpt-4o',
            'max_tokens': max_tokens,
            'temperature': 0.2,
            'messages': messages
        }).encode(),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key}'
        }
    )
    try:
        with opener.open(req, timeout=30) as r:
            return json.loads(r.read())['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f'OpenAI error: {e}', file=sys.stderr)
        return None


# ─── Selection heuristics ─────────────────────────────────────────────────────

def read_selection():
    if not os.path.exists(SELECTION_PATH):
        return '(no selection heuristics found)'
    with open(SELECTION_PATH) as f:
        return f.read()


# ─── Memory file ──────────────────────────────────────────────────────────────

def daily_memory_path():
    today = date.today().strftime('%Y-%m-%d')
    return os.path.join(MEMORY_DIR, f'{today}.md')

def append_to_memory(bullets: list[str]):
    path = daily_memory_path()
    now = datetime.now(GMT3).strftime('%H:%M GMT-3')
    lines = [f'\n[{now}] — memory-writer']
    for b in bullets:
        lines.append(f'- {b.lstrip("- ")}')
    lines.append('')
    with open(path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return path


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    force = '--force' in sys.argv

    state = load_state()
    if not force and too_soon(state):
        last = datetime.fromtimestamp(state['lastMemoryWrite']).strftime('%Y-%m-%d %H:%M')
        print(f'Skipping: last memory write was {last} (min interval: {MIN_INTERVAL_H}h). Use --force to override.')
        return

    conversation = sys.stdin.read().strip()
    if not conversation:
        print('ERROR: no conversation text provided via stdin.', file=sys.stderr)
        sys.exit(1)

    selection = read_selection()

    messages = [
        {
            'role': 'system',
            'content': f"""You extract memory entries from conversations. Apply these selection heuristics strictly:

{selection}

Return a JSON array of strings — each string is one memory bullet.
Return [] if nothing passes the test.
No markdown, no explanation. Only the JSON array."""
        },
        {
            'role': 'user',
            'content': f'Conversation:\n\n{conversation}'
        }
    ]

    raw = call_openai(messages)
    if raw is None:
        sys.exit(1)

    # Parse JSON array
    raw = raw.strip()
    if raw.startswith('```'):
        raw = '\n'.join(raw.split('\n')[1:])
    if raw.endswith('```'):
        raw = raw[:-3].strip()

    try:
        bullets = json.loads(raw)
    except Exception as e:
        print(f'JSON parse error: {e}\nRaw: {raw[:300]}', file=sys.stderr)
        sys.exit(1)

    if not bullets:
        print('Nothing passed the selection test. No memory written.')
        return

    path = append_to_memory(bullets)

    state['lastMemoryWrite'] = time.time()
    save_state(state)

    print(f'Wrote {len(bullets)} entries to {path}')
    for b in bullets:
        print(f'  - {b}')

if __name__ == '__main__':
    main()
