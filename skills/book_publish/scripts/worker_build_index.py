#!/usr/bin/env python3
import re
import sys
from pathlib import Path


CHAPTER_RE = re.compile(r"^(##\s+)?((?:I|II|III|IV|V|VI|VII|VIII|IX|X)\.)\s+(.+)$", re.IGNORECASE)


def slugify(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^a-z0-9à-öø-ÿ\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s.strip("-")


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: worker_build_index.py <input.md> <output.md> <index.md>", file=sys.stderr)
        return 1

    src = Path(sys.argv[1])
    out_md = Path(sys.argv[2])
    out_idx = Path(sys.argv[3])

    lines = src.read_text(encoding="utf-8", errors="ignore").splitlines()

    indexed = []
    chapters = []

    for line in lines:
        raw = line.strip()
        if raw.startswith("## "):
            title = raw[3:].strip()
            anchor = slugify(title)
            if anchor:
                indexed.append(f'<a id="{anchor}"></a>')
                indexed.append(line)
                chapters.append((title, anchor))
                continue

        m = CHAPTER_RE.match(raw)
        if m:
            title = f"{m.group(2).upper()} {m.group(3).strip()}"
            anchor = slugify(title)
            indexed.append(f'<a id="{anchor}"></a>')
            indexed.append(f"## {title}")
            chapters.append((title, anchor))
            continue

        indexed.append(line)

    out_md.write_text("\n".join(indexed).strip() + "\n", encoding="utf-8")

    idx = ["# Índice por capítulos\n\n"]
    for title, anchor in chapters:
        idx.append(f"- [{title}](#{anchor})\n")
    if not chapters:
        idx.append("- nenhum capítulo detectado\n")
    out_idx.write_text("".join(idx), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
