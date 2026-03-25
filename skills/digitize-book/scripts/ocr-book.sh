#!/usr/bin/env bash
# OCR a folder of book page images into a single markdown file.
# Usage: ocr-book.sh <input_folder> <language> <output_file>
# Example: ocr-book.sh /data/ocr_book por /data/book_output.md
# Languages: por, ita, eng, por+ita+eng

set -euo pipefail

INPUT_DIR="${1:-}"
LANG="${2:-por}"
OUTPUT_FILE="${3:-/data/ocr_output.md}"

if [[ -z "$INPUT_DIR" || ! -d "$INPUT_DIR" ]]; then
  echo "ERROR: input folder not found: $INPUT_DIR" >&2
  echo "Usage: ocr-book.sh <input_folder> <language> <output_file>" >&2
  exit 1
fi

if ! command -v tesseract &>/dev/null; then
  echo "ERROR: tesseract not found. Install with: /usr/bin/apt-get install -y tesseract-ocr" >&2
  exit 1
fi

IMAGES=$(find "$INPUT_DIR" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.tiff" -o -iname "*.tif" \) | sort)
COUNT=$(echo "$IMAGES" | grep -c . || true)

if [[ $COUNT -eq 0 ]]; then
  echo "ERROR: no images found in $INPUT_DIR" >&2
  exit 1
fi

echo "Processing $COUNT pages in $INPUT_DIR (lang: $LANG)..."
echo "Output: $OUTPUT_FILE"

> "$OUTPUT_FILE"

PAGE=1
while IFS= read -r IMG; do
  BASENAME=$(basename "$IMG")
  echo "  Page $PAGE/$COUNT: $BASENAME"

  TMPFILE=$(mktemp /tmp/ocr_page_XXXXXX)
  tesseract "$IMG" "$TMPFILE" -l "$LANG" --psm 3 quiet 2>/dev/null
  TEXT_FILE="${TMPFILE}.txt"

  if [[ -f "$TEXT_FILE" ]]; then
    echo -e "\n---\n## Page $PAGE\n" >> "$OUTPUT_FILE"
    cat "$TEXT_FILE" >> "$OUTPUT_FILE"
    rm -f "$TEXT_FILE"
  fi

  rm -f "$TMPFILE"
  PAGE=$((PAGE + 1))
done <<< "$IMAGES"

echo ""
echo "Done. $((PAGE - 1)) pages processed."
echo "Output saved to: $OUTPUT_FILE"
echo ""
echo "Preview (first 20 lines):"
head -20 "$OUTPUT_FILE"
