#!/usr/bin/env python3
"""
Build an EPUB from a classified page list.

Usage:
    build_epub.py <pages_json> <output_epub>

pages_json: JSON file produced by digitize-book.sh, format:
[
  {
    "path": "/tmp/digitize-XXX/001.jpg",
    "type": "text" | "image" | "table",
    "page_num": 1,          # detected from OCR (or None)
    "annotations": {        # optional, from detect_annotations.py
      "earmarked": false,
      "underlines": ["text near underline", ...],
      "margin_comments": ["[left margin] pencil note", ...]
    }
  },
  ...
]

Requires: tesseract, pandoc
"""

import sys
import os
import json
import subprocess
import tempfile
import re
import shutil

# ─── OCR helpers ──────────────────────────────────────────────────────────────

def ocr_text(image_path, lang):
    """Plain text OCR with Tesseract (psm 3 = auto)."""
    with tempfile.NamedTemporaryFile(suffix='', delete=False) as f:
        tmp = f.name
    try:
        subprocess.run(
            ['tesseract', image_path, tmp, '-l', lang, '--psm', '3'],
            capture_output=True, check=False
        )
        out = tmp + '.txt'
        if os.path.exists(out):
            with open(out, encoding='utf-8', errors='replace') as f:
                txt = f.read().strip()
            os.unlink(out)
            return txt
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return ''


def ocr_tsv(image_path, lang):
    """TSV OCR; returns raw TSV string."""
    with tempfile.NamedTemporaryFile(suffix='', delete=False) as f:
        tmp = f.name
    try:
        subprocess.run(
            ['tesseract', image_path, tmp, '-l', lang, '--psm', '6', 'tsv'],
            capture_output=True, check=False
        )
        out = tmp + '.tsv'
        if os.path.exists(out):
            with open(out, encoding='utf-8', errors='replace') as f:
                tsv = f.read()
            os.unlink(out)
            return tsv
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return ''


def tsv_to_markdown_table(tsv_text):
    """
    Convert Tesseract TSV to a Markdown table.
    Groups words by line, then treats each line as a row.
    """
    from collections import defaultdict
    rows = defaultdict(list)
    for line in tsv_text.splitlines()[1:]:
        parts = line.split('\t')
        if len(parts) < 12:
            continue
        try:
            conf = int(parts[10])
            word = parts[11].strip()
            block = int(parts[1])
            linenum = int(parts[3])
        except (ValueError, IndexError):
            continue
        if conf > 30 and word:
            rows[(block, linenum)].append(word)

    if not rows:
        return ''

    sorted_rows = [' | '.join(words) for _, words in sorted(rows.items())]
    if not sorted_rows:
        return ''

    # Build markdown table
    header = sorted_rows[0]
    sep = ' | '.join(['---'] * (header.count('|') + 1))
    lines = [f'| {header} |', f'| {sep} |']
    for row in sorted_rows[1:]:
        lines.append(f'| {row} |')
    return '\n'.join(lines)


# ─── Metadata extraction ──────────────────────────────────────────────────────

def extract_page_number(text):
    """Try to find a standalone page number in OCR text."""
    # Look for isolated numbers at start/end of lines
    patterns = [
        r'^\s*[–—-]?\s*(\d{1,4})\s*[–—-]?\s*$',
        r'^\s*Página\s+(\d{1,4})',
        r'^\s*p\.?\s*(\d{1,4})',
    ]
    for line in text.splitlines():
        for pat in patterns:
            m = re.match(pat, line.strip(), re.IGNORECASE)
            if m:
                n = int(m.group(1))
                if 1 <= n <= 9999:
                    return n
    return None


def extract_metadata(pages, lang):
    """
    Scan the first few pages (up to 5) for title and author.
    Returns dict with keys: title, author, language.
    """
    title = 'Untitled Book'
    author = 'Unknown Author'

    text_pages = [p for p in pages if p['type'] == 'text'][:5]
    for page in text_pages:
        text = ocr_text(page['path'], lang)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            continue

        # Heuristic: title is often the longest line in the first 2 pages,
        # author comes after it (shorter line, capitalized)
        if title == 'Untitled Book' and lines:
            candidates = sorted(lines[:15], key=len, reverse=True)
            if candidates:
                title = candidates[0]

        # Look for "by", "por", "di", "de" followed by a name
        for i, line in enumerate(lines):
            m = re.match(r'^(?:by|por|di|de|autor[ae]?s?:?)\s+(.+)$', line, re.IGNORECASE)
            if m:
                author = m.group(1).strip()
                break
            # Capitalized line after a blank (common author position)
            if i > 0 and re.match(r'^[A-ZÁÉÍÓÚÀÂÃÊÔÇ][a-záéíóúàâãêôç]', line):
                if len(line.split()) <= 5:
                    author = line

        if title != 'Untitled Book' and author != 'Unknown Author':
            break

    return {'title': title, 'author': author, 'language': lang}


# ─── Page content builders ───────────────────────────────────────────────────

def annotations_to_markdown(annotations, footnote_start):
    """
    Convert annotation data to markdown footnote references and definitions.
    Returns (inline_refs, footnote_defs, next_footnote_num).

    inline_refs: markdown to append inline (after the page content)
    footnote_defs: footnote definition lines to collect at document end
    """
    if not annotations:
        return '', [], footnote_start

    inline_refs = []
    defs = []
    n = footnote_start

    ann = annotations

    if ann.get('earmarked'):
        ref = f'[^{n}]'
        inline_refs.append(ref)
        defs.append(f'[^{n}]: *(earmarked page)*')
        n += 1

    for text in ann.get('underlines', []):
        ref = f'[^{n}]'
        inline_refs.append(ref)
        defs.append(f'[^{n}]: **underlined:** "{text}"')
        n += 1

    for comment in ann.get('margin_comments', []):
        ref = f'[^{n}]'
        inline_refs.append(ref)
        defs.append(f'[^{n}]: **note:** {comment}')
        n += 1

    refs_str = ' '.join(inline_refs)
    return refs_str, defs, n


def page_to_markdown(page, lang, assets_dir, footnote_num):
    """
    Convert a single page entry to a markdown string.
    Returns (markdown_text, footnote_defs, next_footnote_num).
    """
    ptype = page['type']
    path = page['path']
    annotations = page.get('annotations')

    ann_refs, ann_defs, next_fn = annotations_to_markdown(annotations, footnote_num)

    if ptype == 'text':
        text = ocr_text(path, lang)
        body = text + (f'\n\n{ann_refs}' if ann_refs else '')
        return body + '\n\n---\n\n', ann_defs, next_fn

    elif ptype == 'table':
        tsv = ocr_tsv(path, lang)
        md_table = tsv_to_markdown_table(tsv)
        if not md_table:
            md_table = ocr_text(path, lang)
        body = md_table + (f'\n\n{ann_refs}' if ann_refs else '')
        return body + '\n\n---\n\n', ann_defs, next_fn

    elif ptype == 'image':
        basename = os.path.basename(path)
        dest = os.path.join(assets_dir, basename)
        if not os.path.exists(dest):
            shutil.copy2(path, dest)
        body = f'![image]({dest})' + (f'\n\n{ann_refs}' if ann_refs else '')
        return body + '\n\n---\n\n', ann_defs, next_fn

    return '', [], next_fn


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print('Usage: build_epub.py <pages_json> <output_epub>', file=sys.stderr)
        sys.exit(1)

    pages_json = sys.argv[1]
    output_epub = sys.argv[2]

    with open(pages_json, encoding='utf-8') as f:
        pages = json.load(f)

    if not pages:
        print('ERROR: no pages in JSON', file=sys.stderr)
        sys.exit(1)

    # Language: infer from first page entry or default to por
    lang = pages[0].get('lang', 'por')

    # ── Sort by detected page number if available, otherwise filename ──
    def sort_key(p):
        pn = p.get('page_num')
        if pn is not None:
            return (0, pn)
        return (1, p['path'])

    pages.sort(key=sort_key)

    # ── Extract metadata from first pages ──
    print('Extracting metadata...', flush=True)
    meta = extract_metadata(pages, lang)
    print(f"  Title : {meta['title']}")
    print(f"  Author: {meta['author']}")

    # ── Build working directory ──
    work_dir = tempfile.mkdtemp(prefix='build-epub-')
    assets_dir = os.path.join(work_dir, 'assets')
    os.makedirs(assets_dir)

    # ── OCR and assemble markdown ──
    print(f'Processing {len(pages)} pages...', flush=True)
    md_parts = []
    all_footnote_defs = []
    cover_image = None
    low_conf_pages = []
    footnote_num = 1
    annotated_pages = 0

    for i, page in enumerate(pages, 1):
        sys.stdout.write(f'\r  Page {i}/{len(pages)}')
        sys.stdout.flush()
        md, fn_defs, footnote_num = page_to_markdown(page, lang, assets_dir, footnote_num)
        if not md.strip():
            low_conf_pages.append(i)
        md_parts.append(md)
        if fn_defs:
            all_footnote_defs.extend(fn_defs)
            annotated_pages += 1

        # First image page is likely the cover
        if cover_image is None and page['type'] == 'image':
            basename = os.path.basename(page['path'])
            cover_image = os.path.join(assets_dir, basename)

    print()  # newline after progress

    # ── Write combined markdown (footnotes appended at end) ──
    md_path = os.path.join(work_dir, 'book.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_parts))
        if all_footnote_defs:
            f.write('\n\n')
            f.write('\n'.join(all_footnote_defs))

    # ── Call pandoc ──
    print('Converting to EPUB with pandoc...', flush=True)
    pandoc_cmd = [
        'pandoc',
        md_path,
        '--from', 'markdown',
        '--to', 'epub',
        '--output', output_epub,
        f'--metadata=title:{meta["title"]}',
        f'--metadata=author:{meta["author"]}',
        f'--metadata=lang:{lang}',
        '--toc',
    ]
    if cover_image and os.path.exists(cover_image):
        pandoc_cmd += ['--epub-cover-image', cover_image]

    result = subprocess.run(pandoc_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print('pandoc error:', result.stderr, file=sys.stderr)
        sys.exit(1)

    # ── Cleanup ──
    shutil.rmtree(work_dir, ignore_errors=True)

    print(f'\nEPUB written to: {output_epub}')
    print(f'Pages: {len(pages)}')
    if annotated_pages:
        print(f'Annotated pages detected: {annotated_pages} (earmarks, underlines, margin notes preserved as footnotes)')
    if low_conf_pages:
        print(f'Low-confidence pages (no text extracted): {low_conf_pages}')


if __name__ == '__main__':
    main()
