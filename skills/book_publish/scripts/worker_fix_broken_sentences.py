#!/usr/bin/env python3
import re
import sys
from pathlib import Path


def should_merge(prev_line: str, next_line: str) -> bool:
    p = prev_line.rstrip()
    n = next_line.lstrip()
    if not p or not n:
        return False
    if p.startswith("#") or n.startswith("#"):
        return False
    if re.fullmatch(r"\d{1,4}", p.strip()):
        return False
    if p[-1] in ".?!:;":
        return False
    if re.match(r"^[a-zà-öø-ÿ]", n):
        return True
    # Also merge when previous line clearly continues.
    if p[-1] in ",(-":
        return True
    return False


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: worker_fix_broken_sentences.py <input.md> <output.md>", file=sys.stderr)
        return 1

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    lines = src.read_text(encoding="utf-8", errors="ignore").splitlines()

    out = []
    i = 0
    in_frontmatter = False
    while i < len(lines):
        cur = lines[i]
        if cur.strip() == "---":
            in_frontmatter = not in_frontmatter
            out.append(cur)
            i += 1
            continue
        if in_frontmatter:
            out.append(cur)
            i += 1
            continue

        j = i + 1
        # Allow one or more blank lines between wrapped sentence fragments.
        while j < len(lines) and lines[j].strip() == "":
            j += 1

        if j < len(lines) and should_merge(cur, lines[j]):
            merged = cur.rstrip() + " " + lines[j].lstrip()
            out.append(re.sub(r"\s{2,}", " ", merged))
            i = j + 1
            continue

        out.append(cur)
        i += 1

    text = "\n".join(out) + "\n"
    text = re.sub(r"\n{3,}", "\n\n", text)
    dst.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
