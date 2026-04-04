---
name: digitize-book
description: "Convert either (1) a ZIP of scanned book pages (JPG/PNG/TIFF) or (2) a PDF into an EPUB. Use when the user asks to digitize a book, create an ebook from photos, or convert PDF to EPUB. ZIP flow includes OCR, page classification, and physical annotation detection (earmarks, underlines, margin notes) preserved as EPUB footnotes. PDF flow uses Calibre ebook-convert. Supports Portuguese, Italian, and English. Input in /data. Output EPUB in /data."
---

# Digitize Book

Convert either:
- a ZIP of book page images into a fully assembled EPUB with OCR and annotations, or
- a PDF directly to EPUB using Calibre.

## When to use

- User drops a ZIP of book page photos into `/data` (via Mac SSHFS mount or Telegram)
- User says: "digitize this book", "OCR this book", "make an epub from these photos", "convert scanned pages to epub"
- User has a physical book they photographed page by page

## Prerequisites

- **For ZIP/image flow**: `tesseract`, `pandoc`, `python3`, `unzip`
- **For PDF flow**: `ebook-convert` (Calibre)
- Input file in `/data/` as either:
  - ZIP with JPG/JPEG/PNG/TIFF pages in order, or
  - PDF file

### Install Calibre (for PDF -> EPUB)

Run:

```bash
/data/skills/digitize-book/scripts/install_calibre.sh
```

This installer tries, in order:
1. current environment (if root + apt-get),
2. local Docker (`openclaw-b60d-openclaw-1`),
3. VPS via SSH (`hostinger-vps` + docker exec).

## How to run

Single command - call the orchestrator script:

```bash
/data/skills/digitize-book/scripts/digitize-book.sh /data/<bookname>.zip [lang] [annotations]
/data/skills/digitize-book/scripts/digitize-book.sh /data/<bookname>.pdf
```

`lang` defaults to `por`. Options: `por`, `ita`, `eng`, `por+ita+eng`.
`annotations` defaults to `yes`. Pass `no` to skip annotation detection (faster). Ignored for PDF input.

Example:
```bash
/data/skills/digitize-book/scripts/digitize-book.sh /data/fantasia_concretezza.zip por yes
/data/skills/digitize-book/scripts/digitize-book.sh /data/livro.pdf
```

Output:
- if input is under `/data/projects/<project-slug>/...`: `/data/projects/<project-slug>/outputs/<bookname>.epub`
- otherwise: `/data/<bookname>.epub`

## What the pipeline does

### ZIP/image flow

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

### PDF flow

1. **Checks** `ebook-convert` availability
2. **Runs** Calibre conversion from PDF to EPUB
3. **Writes** EPUB to project `outputs/` when input is in a project path, otherwise to `/data`

## Deliver result

After the script finishes:
- Tell the user the EPUB path (e.g. `/data/fantasia_concretezza.epub`)
- For ZIP flow: report total pages and classification breakdown (X text, Y images, Z tables)
- For ZIP flow with annotations: report earmarks/underlines/margin note counts
- For ZIP flow: mention low OCR confidence pages, if any
- For PDF flow: report conversion success and output path

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
    ├── install_calibre.sh      ← Calibre installer (PDF mode dependency)
    ├── digitize-book.sh        ← orchestrator (call this)
    ├── classify_page.py        ← page type classifier (text / image / table)
    ├── detect_annotations.py   ← physical annotation detector (earmarks, underlines, margin notes)
    └── build_epub.py           ← EPUB assembler (pandoc wrapper + footnote renderer)
```

## Notes

- Page ordering (ZIP flow): filename sort order first; detected page numbers are used to reorder when they differ.
- If images were uploaded via Telegram, move them to `/data/` before zipping, or ask the user to drop the ZIP directly.
- OCR quality depends on photo quality — well-lit, straight, high-resolution images give best results.
- Blurry or skewed pages will still be included but flagged as low-confidence.
- ZIP flow EPUB embeds images directly; no external hosting needed.
