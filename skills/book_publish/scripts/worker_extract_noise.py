#!/usr/bin/env python3
import re
import sys
from collections import Counter
from pathlib import Path


PAGE_NUM_RE = re.compile(r"^\s*\d{1,4}\s*$")


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def is_noise_line(line: str, repeated: set[str]) -> bool:
    s = line.strip()
    if not s:
        return False
    if s == "---":
        return False
    if PAGE_NUM_RE.fullmatch(s):
        return True
    if normalize(s) in repeated:
        return True
    # Likely running headers/footers.
    if len(s) <= 40 and s.isupper() and not s.startswith("#"):
        return True
    # Isolated OCR debris.
    if re.fullmatch(r"[\W_]{1,8}", s):
        return True
    # Footnote-style starts like "1 " short snippet.
    if re.match(r"^\d+[\)\.]?\s+\S+", s) and len(s.split()) <= 8:
        return True
    return False


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: worker_extract_noise.py <input.md> <output.md> <removed.md>", file=sys.stderr)
        return 1

    src = Path(sys.argv[1])
    out_md = Path(sys.argv[2])
    out_removed = Path(sys.argv[3])

    lines = src.read_text(encoding="utf-8", errors="ignore").splitlines()
    norm_counts = Counter(normalize(l) for l in lines if l.strip())
    repeated = {k for k, v in norm_counts.items() if v >= 3 and len(k) <= 80}

    kept = []
    removed = []

    for idx, line in enumerate(lines, start=1):
        if is_noise_line(line, repeated):
            removed.append((idx, line))
        else:
            kept.append(line)

    out_md.write_text("\n".join(kept).strip() + "\n", encoding="utf-8")

    rep = ["# Removed OCR noise\n\n"]
    for ln, txt in removed:
        rep.append(f"- L{ln}: {txt}\n")
    if len(removed) == 0:
        rep.append("- none\n")
    out_removed.write_text("".join(rep), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
