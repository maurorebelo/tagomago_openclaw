#!/usr/bin/env bash
set -euo pipefail

IN="${1:-}"
if [[ -z "$IN" || ! -f "$IN" ]]; then
  echo "Usage: run_pipeline.sh <input.md>" >&2
  exit 1
fi

BASE="${IN%.md}"
BASE_NAME="$(basename "${BASE}")"
WORK_DIR="$(dirname "${IN}")"

if [[ "$IN" =~ ^/data/projects/([^/]+)/ ]]; then
  PROJECT_SLUG="${BASH_REMATCH[1]}"
  OUT_DIR="/data/projects/${PROJECT_SLUG}/outputs"
else
  OUT_DIR="${WORK_DIR}"
fi
mkdir -p "$OUT_DIR"

STEP1="${WORK_DIR}/${BASE_NAME}.step1.md"
STEP2="${WORK_DIR}/${BASE_NAME}.step2.md"
OUT="${OUT_DIR}/${BASE_NAME}.clean.md"
IDX="${OUT_DIR}/${BASE_NAME}.index.md"
REMOVED="${OUT_DIR}/${BASE_NAME}.removed.md"

python3 /data/skills/book_publish/scripts/worker_fix_broken_sentences.py "$IN" "$STEP1"
python3 /data/skills/book_publish/scripts/worker_extract_noise.py "$STEP1" "$STEP2" "$REMOVED"
python3 /data/skills/book_publish/scripts/worker_build_index.py "$STEP2" "$OUT" "$IDX"

rm -f "$STEP1" "$STEP2"

echo "CLEAN: $OUT"
echo "INDEX: $IDX"
echo "REMOVED: $REMOVED"
