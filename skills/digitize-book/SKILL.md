---
name: digitize-book
description: "Convert a ZIP of book page photos (JPGs) into an EPUB. Use when the user uploads a ZIP of scanned book pages, asks to digitize a book, create an ebook from photos, or convert scanned pages to EPUB. Also detects physical annotations (earmarks, underlined text, pencil margin notes) and preserves them as EPUB footnotes. Supports Portuguese, Italian, and English. Input: ZIP dropped into /data. Output: EPUB in /data."
---

# Digitize Book

Convert a ZIP of JPG book pages into a fully assembled EPUB with text, embedded images, and tables.
Uses local Tesseract OCR (no external API) and pandoc (no external API).

## When to use

- User drops a ZIP of book page photos into `/data` (via Mac SSHFS mount or Telegram)
- User says: "digitize this book", "OCR this book", "make an epub from these photos", "convert scanned pages to epub"
- User has a physical book they photographed page by page

## Prerequisites (verified ✓)

- **Tesseract** at `/usr/bin/tesseract` — OCR engine
- **pandoc** at `/usr/bin/pandoc` — EPUB assembler
- **python3** — page classifier and build script
- ZIP file in `/data/` containing JPG/JPEG/PNG pages named in order (e.g. `001.jpg`, `002.jpg`)

## How to run

Single command — call the orchestrator script:

```bash
/data/skills/digitize-book/scripts/digitize-book.sh /data/<bookname>.zip [lang] [annotations]
```

**lang** defaults to `por`. Options: `por`, `ita`, `eng`, `por+ita+eng`.
**annotations** defaults to `yes`. Pass `no` to skip annotation detection (faster).

Example:
```bash
/data/skills/digitize-book/scripts/digitize-book.sh /data/fantasia_concretezza.zip por yes
```

Output: `/data/fantasia_concretezza.epub`

## What the pipeline does

1. **Unzips** the ZIP into a temp folder
2. **Sorts** images by filename (natural order)
3. **Classifies** each page as `text`, `image`, or `table`:
   - `image` → < 30 confident words detected (cover, diagram, full-page photo)
   - `table` → grid structure detected (3+ rows × 2+ cols)
   - `text` → everything else
4. **Detects physical annotations** on each page:
   - **Earmarks** (folded corners) — flagged in footnote as *(earmarked page)*
   - **Underlined text** — detected via horizontal line analysis; the underlined text is quoted in a footnote
   - **Margin comments** (pencil notes) — OCR'd from the margin strip; preserved as footnotes
5. **Detects page numbers** from OCR text and reorders if they differ from filename order
6. **OCRs text pages** with Tesseract (psm 3, auto layout)
7. **Converts table pages** to Markdown table format via TSV output
8. **Embeds image pages** directly in the EPUB
9. **Extracts metadata** (title, author) from the first pages
10. **Assembles** all pages into a single Markdown file, with annotation footnotes at the end
11. **Calls pandoc** to produce the final EPUB with cover, TOC, metadata, and footnotes

## Deliver result

After the script finishes:
- Tell the user the EPUB path (e.g. `/data/fantasia_concretezza.epub`)
- Report: total pages, classification breakdown (X text, Y images, Z tables)
- If annotations were detected: how many pages had earmarks, underlines, or margin notes
- If any pages had low OCR confidence, mention them

## Language codes

| Language   | Code          |
|------------|---------------|
| Portuguese | `por`         |
| Italian    | `ita`         |
| English    | `eng`         |
| Mixed      | `por+ita+eng` |

## Script structure

```
skills/digitize-book/
├── SKILL.md                    ← this file
└── scripts/
    ├── digitize-book.sh        ← orchestrator (call this)
    ├── classify_page.py        ← page type classifier (text / image / table)
    ├── detect_annotations.py   ← physical annotation detector (earmarks, underlines, margin notes)
    └── build_epub.py           ← EPUB assembler (pandoc wrapper + footnote renderer)
```

## Notes

- Page ordering: filename sort order first; detected page numbers are used to reorder when they differ.
- If images were uploaded via Telegram, move them to `/data/` before zipping, or ask the user to drop the ZIP directly.
- OCR quality depends on photo quality — well-lit, straight, high-resolution images give best results.
- Blurry or skewed pages will still be included but flagged as low-confidence.
- The EPUB embeds images directly; no external hosting needed.
