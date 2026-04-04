---
name: book_publish
description: Publish book-like Markdown from OCR/PDF with structural cleanup workers. Use when preparing OCR text for ebook publication, fixing broken sentence wraps, removing header/footer/sidenote residue, and building chapter index links anchored to headings instead of page numbers.
---

# Book Publish

Prepare noisy OCR Markdown for publication with deterministic workers.

## Run

```bash
/data/skills/book_publish/scripts/run_pipeline.sh /data/path/to/input.md
```

Outputs:
- if input is under `/data/projects/<project-slug>/...`: `/data/projects/<project-slug>/outputs/`
- otherwise: same folder as input

Files generated:
- `<name>.clean.md` (cleaned manuscript)
- `<name>.index.md` (chapter index with heading anchors)
- `<name>.removed.md` (removed header/footer/sidenote/footnote candidates with references)

## Workers

1. `worker_build_index.py`
- Detect chapter headings from markdown headings and roman numeral chapter lines.
- Inject stable heading anchors.
- Build index links pointing to anchors (not pages).

2. `worker_fix_broken_sentences.py`
- Merge hard line breaks inside paragraphs.
- Specifically merge when a line ends without `.?!:` and the next starts lowercase.

3. `worker_extract_noise.py`
- Remove likely header/footer/page-number and short sidenote/footnote artifacts.
- Store removed lines in a sidecar file with original line references.

## Notes

- Keep all processing local and deterministic first.
- Use LLM polishing only after these workers reduce OCR noise.
