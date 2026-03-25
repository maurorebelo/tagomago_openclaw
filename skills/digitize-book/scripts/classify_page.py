#!/usr/bin/env python3
"""
Classify a book page image as: text, image, or table.
Usage: classify_page.py <image_path> [lang]
Output: prints one of: text, image, table
"""

import sys
import subprocess
import tempfile
import os
import re

def run_tesseract_tsv(image_path, lang):
    """Run Tesseract and return TSV output."""
    with tempfile.NamedTemporaryFile(suffix='', delete=False) as f:
        tmpbase = f.name
    try:
        subprocess.run(
            ['tesseract', image_path, tmpbase, '-l', lang, '--psm', '6', 'tsv'],
            capture_output=True, check=False
        )
        tsv_path = tmpbase + '.tsv'
        if os.path.exists(tsv_path):
            with open(tsv_path) as f:
                content = f.read()
            os.unlink(tsv_path)
            return content
    except Exception:
        pass
    finally:
        if os.path.exists(tmpbase):
            os.unlink(tmpbase)
    return ''

def count_confident_words(tsv_text):
    """Count words with confidence > 60 from TSV output."""
    count = 0
    for line in tsv_text.splitlines()[1:]:  # skip header
        parts = line.split('\t')
        if len(parts) >= 12:
            try:
                conf = int(parts[10])
                word = parts[11].strip()
                if conf > 60 and word:
                    count += 1
            except (ValueError, IndexError):
                pass
    return count

def detect_table(tsv_text):
    """
    Detect table structure: look for multiple rows with consistent
    column count (3+ columns, 3+ rows with similar x-positions).
    """
    lines = tsv_text.splitlines()[1:]  # skip header
    # Group words by block_num and par_num and line_num
    line_groups = {}
    for line in lines:
        parts = line.split('\t')
        if len(parts) < 12:
            continue
        try:
            level = int(parts[0])
            block = int(parts[1])
            par = int(parts[2])
            linenum = int(parts[3])
            conf = int(parts[10])
            word = parts[11].strip()
        except (ValueError, IndexError):
            continue
        if level == 5 and conf > 40 and word:
            key = (block, par, linenum)
            line_groups.setdefault(key, []).append(word)

    if not line_groups:
        return False

    # Count lines with 2+ words (potential table cells)
    multi_word_lines = [words for words in line_groups.values() if len(words) >= 2]
    if len(multi_word_lines) < 3:
        return False

    # Check for consistent column counts suggesting a table
    col_counts = [len(words) for words in multi_word_lines]
    most_common = max(set(col_counts), key=col_counts.count)
    consistent = sum(1 for c in col_counts if abs(c - most_common) <= 1)

    return most_common >= 2 and consistent >= 3

def classify(image_path, lang='por'):
    tsv = run_tesseract_tsv(image_path, lang)
    word_count = count_confident_words(tsv)

    # Very few words → treat as image (cover, diagram, full-page photo)
    if word_count < 30:
        return 'image'

    # Check for table structure
    if detect_table(tsv):
        return 'table'

    return 'text'

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: classify_page.py <image_path> [lang]', file=sys.stderr)
        sys.exit(1)

    image_path = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else 'por'

    if not os.path.exists(image_path):
        print(f'ERROR: file not found: {image_path}', file=sys.stderr)
        sys.exit(1)

    print(classify(image_path, lang))
