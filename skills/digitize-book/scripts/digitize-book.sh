#!/usr/bin/env bash
# Digitize a book:
#   - ZIP of page images (JPG/PNG/TIFF) -> EPUB (OCR + assembly)
#   - PDF -> EPUB (via Calibre ebook-convert)
# Usage: digitize-book.sh <input_path> [lang] [annotations]
#   input_path   path to ZIP or PDF (e.g. /data/mybook.zip or /data/mybook.pdf)
#   lang         tesseract language code, default: por (por, eng, ita, por+ita+eng)
#   annotations  yes|no (only applies to ZIP/image flow), default: yes
#
# Output: /data/<bookname>.epub

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INPUT_PATH="${1:-}"
LANG="${2:-por}"
ANNOTATIONS="${3:-yes}"  # pass "no" to skip annotation detection

if [[ -z "$INPUT_PATH" ]]; then
  echo "Usage: digitize-book.sh <input_path> [lang] [annotations]" >&2
  exit 1
fi

if [[ ! -f "$INPUT_PATH" ]]; then
  echo "ERROR: file not found: $INPUT_PATH" >&2
  exit 1
fi

# ── Derive names ─────────────────────────────────────────────────────────────
BASENAME="$(basename "$INPUT_PATH")"
BASENAME="${BASENAME%.*}"
BASENAME="$(basename "$BASENAME" .ZIP)"
WORK_DIR="$(mktemp -d /tmp/digitize-${BASENAME}-XXXX)"
PAGES_JSON="${WORK_DIR}/pages.json"
INPUT_LOWER="${INPUT_PATH,,}"

# If input is inside a project folder, write output to that project's outputs dir.
# Otherwise, keep the legacy behavior and write to /data.
if [[ "$INPUT_PATH" =~ ^/data/projects/([^/]+)/ ]]; then
  PROJECT_SLUG="${BASH_REMATCH[1]}"
  OUTPUT_DIR="/data/projects/${PROJECT_SLUG}/outputs"
else
  OUTPUT_DIR="/data"
fi
mkdir -p "$OUTPUT_DIR"
OUTPUT_EPUB="${OUTPUT_DIR}/${BASENAME}.epub"

cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

# ── PDF flow: Calibre direct conversion ──────────────────────────────────────
if [[ "$INPUT_LOWER" == *.pdf ]]; then
  if ! command -v ebook-convert &>/dev/null; then
    echo "ERROR: ebook-convert not found (Calibre is required for PDF -> EPUB)." >&2
    echo "Run: /data/skills/digitize-book/scripts/install_calibre.sh" >&2
    exit 1
  fi

  echo "=== Digitize Book (PDF mode) ==="
  echo "Input  : $INPUT_PATH"
  echo "Output : $OUTPUT_EPUB"
  echo ""
  ebook-convert "$INPUT_PATH" "$OUTPUT_EPUB"
  echo ""
  echo "Done! EPUB available at: $OUTPUT_EPUB"
  exit 0
fi

if [[ "$INPUT_LOWER" != *.zip ]]; then
  echo "ERROR: unsupported input type. Use .zip (page images) or .pdf." >&2
  exit 1
fi

# ── Verify dependencies for ZIP/image flow ───────────────────────────────────
for tool in tesseract pandoc python3 unzip; do
  if ! command -v "$tool" &>/dev/null; then
    echo "ERROR: $tool not found" >&2
    exit 1
  fi
done

echo "=== Digitize Book ==="
echo "Input      : $INPUT_PATH"
echo "Lang       : $LANG"
echo "Annotations: $ANNOTATIONS"
echo "Output     : $OUTPUT_EPUB"
echo ""

# ── Unzip ────────────────────────────────────────────────────────────────────
echo "Unzipping..."
unzip -q "$INPUT_PATH" -d "$WORK_DIR/pages"

# ── Find and sort images ──────────────────────────────────────────────────────
echo "Finding images..."
mapfile -d '' IMAGES < <(find "$WORK_DIR/pages" \
  -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.tiff' -o -iname '*.tif' \) \
  -print0 | sort -z)

TOTAL="${#IMAGES[@]}"
if [[ "$TOTAL" -eq 0 ]]; then
  echo "ERROR: no image files found in zip" >&2
  exit 1
fi

echo "Found $TOTAL images"
echo ""

# ── Classify each page ────────────────────────────────────────────────────────
echo "Classifying pages..."
JSON_ENTRIES=()

for i in "${!IMAGES[@]}"; do
  IMG="${IMAGES[$i]}"
  NUM=$((i + 1))
  printf "\r  Page %d/%d" "$NUM" "$TOTAL"

  TYPE="$("$SCRIPT_DIR/classify_page.py" "$IMG" "$LANG" 2>/dev/null || echo 'text')"

  # Try to detect page number from OCR text (for text pages only)
  PAGE_NUM="null"
  if [[ "$TYPE" == "text" ]]; then
    RAW_TEXT="$(tesseract "$IMG" stdout -l "$LANG" --psm 3 2>/dev/null || true)"
    # Look for isolated numbers (page number heuristic)
    DETECTED_NUM="$(echo "$RAW_TEXT" | grep -oP '^\s*\K\d{1,4}(?=\s*$)' | head -1 || true)"
    if [[ -n "$DETECTED_NUM" && "$DETECTED_NUM" -ge 1 && "$DETECTED_NUM" -le 9999 ]]; then
      PAGE_NUM="$DETECTED_NUM"
    fi
  fi

  # Detect physical annotations (earmarks, underlines, margin comments)
  ANN_JSON="null"
  if [[ "$ANNOTATIONS" != "no" ]]; then
    ANN_RESULT="$("$SCRIPT_DIR/detect_annotations.py" "$IMG" "$LANG" 2>/dev/null || echo 'null')"
    if [[ "$ANN_RESULT" != "null" && "$ANN_RESULT" != "" ]]; then
      ANN_JSON="$ANN_RESULT"
    fi
  fi

  JSON_ENTRIES+=("{\"path\":$(python3 -c "import json,sys;print(json.dumps(sys.argv[1]))" "$IMG"),\"type\":\"$TYPE\",\"page_num\":$PAGE_NUM,\"lang\":\"$LANG\",\"annotations\":$ANN_JSON}")
done

echo ""  # newline after progress

# ── Write pages JSON ──────────────────────────────────────────────────────────
{
  echo "["
  for i in "${!JSON_ENTRIES[@]}"; do
    if [[ $i -lt $((${#JSON_ENTRIES[@]} - 1)) ]]; then
      echo "  ${JSON_ENTRIES[$i]},"
    else
      echo "  ${JSON_ENTRIES[$i]}"
    fi
  done
  echo "]"
} > "$PAGES_JSON"

# ── Count by type ─────────────────────────────────────────────────────────────
TEXT_COUNT=$(grep -c '"type":"text"' "$PAGES_JSON" || true)
IMG_COUNT=$(grep -c '"type":"image"' "$PAGES_JSON" || true)
TABLE_COUNT=$(grep -c '"type":"table"' "$PAGES_JSON" || true)
echo "Classification: $TEXT_COUNT text, $IMG_COUNT image, $TABLE_COUNT table"
echo ""

# ── Build EPUB ────────────────────────────────────────────────────────────────
python3 "$SCRIPT_DIR/build_epub.py" "$PAGES_JSON" "$OUTPUT_EPUB"

echo ""
echo "Done! EPUB available at: $OUTPUT_EPUB"
