#!/usr/bin/env python3
"""
Detect physical annotations in a book page photo:
  - Earmarks (folded corners)
  - Underlined text
  - Margin handwritten comments (pencil notes) — read via GPT-4o vision if OPENAI_API_KEY is set,
    falls back to Tesseract otherwise

Usage:
    detect_annotations.py <image_path> [lang]

Output (JSON to stdout):
{
  "earmarked": true | false,
  "underlines": [ "approximate text near underline", ... ],
  "margin_comments": [ "transcribed margin text", ... ]
}
"""

import sys
import os
import json
import subprocess
import tempfile
import base64
import urllib.request
import urllib.error

try:
    from PIL import Image, ImageFilter
    import numpy as np
except ImportError:
    print(json.dumps({"earmarked": False, "underlines": [], "margin_comments": [],
                      "error": "PIL/numpy not available"}))
    sys.exit(0)


# ─── Image helpers ────────────────────────────────────────────────────────────

def load_gray(image_path):
    img = Image.open(image_path).convert('L')
    # Downscale for speed if very large
    w, h = img.size
    if max(w, h) > 2000:
        scale = 2000 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img, np.array(img)


# ─── Earmark detection ────────────────────────────────────────────────────────

def detect_earmark(gray_arr, corner_frac=0.10, dark_thresh=80, fill_thresh=0.15):
    """
    Check each corner for a triangular dark region (folded page corner).
    A fold creates a shadow/dark triangle at the corner.
    Returns True if any corner looks earmarked.
    """
    h, w = gray_arr.shape
    ch = max(int(h * corner_frac), 30)
    cw = max(int(w * corner_frac), 30)

    corners = [
        gray_arr[:ch, :cw],          # top-left
        gray_arr[:ch, w - cw:],      # top-right
        gray_arr[h - ch:, :cw],      # bottom-left
        gray_arr[h - ch:, w - cw:],  # bottom-right
    ]

    for corner in corners:
        dark_pixels = np.sum(corner < dark_thresh)
        total = corner.size
        if total > 0 and (dark_pixels / total) > fill_thresh:
            return True

    return False


# ─── Underline detection ──────────────────────────────────────────────────────

def detect_underlines(image_path, gray_arr, lang):
    """
    Detect horizontal lines drawn under text.
    Strategy:
      1. Find horizontal lines via morphological erosion (long thin horizontal structures)
      2. Exclude printed lines (page borders, table rules) by checking they are not at the
         very top/bottom margins
      3. For each detected underline, use Tesseract to find the text just above it
    Returns list of text strings near underlines.
    """
    h, w = gray_arr.shape

    # Binarize (invert: marks become white on black)
    binary = (gray_arr < 128).astype(np.uint8)

    # Horizontal kernel: 1 row, ~5% of width minimum
    min_len = max(int(w * 0.05), 20)
    kernel = np.ones((1, min_len), dtype=np.uint8)

    # Erode horizontally to find long horizontal runs
    # Manual row erosion: for each row, find runs of 1s longer than min_len
    underline_rows = []
    margin_top = int(h * 0.05)
    margin_bot = int(h * 0.95)

    for y in range(margin_top, margin_bot):
        row = binary[y]
        # Find runs of dark pixels (in original: below 128)
        run = 0
        max_run = 0
        for px in row:
            if px == 1:
                run += 1
                max_run = max(max_run, run)
            else:
                run = 0
        if max_run >= min_len:
            # Check it's a thin line (not a solid block): rows above/below are mostly white
            above = gray_arr[max(0, y - 3):y, :]
            below = gray_arr[y + 1:min(h, y + 4), :]
            above_dark = np.sum(above < 128) / above.size if above.size > 0 else 0
            below_dark = np.sum(below < 128) / below.size if below.size > 0 else 0
            if above_dark < 0.3 and below_dark < 0.3:
                underline_rows.append(y)

    if not underline_rows:
        return []

    # Cluster nearby rows into single underlines
    clusters = []
    current = [underline_rows[0]]
    for y in underline_rows[1:]:
        if y - current[-1] <= 5:
            current.append(y)
        else:
            clusters.append(current)
            current = [y]
    clusters.append(current)

    # For each underline cluster, OCR the text band just above it
    found_texts = []
    img_full = Image.open(image_path).convert('L')
    orig_h, orig_w = np.array(img_full).shape
    scale_y = orig_h / h
    scale_x = orig_w / w

    for cluster in clusters:
        line_y = int(np.mean(cluster))
        # Text band: from ~2 lines above the underline (approx 30px in scaled coords)
        band_top = max(0, line_y - 60)
        band_bot = line_y

        # Scale back to original image coords
        orig_top = int(band_top * scale_y)
        orig_bot = int(band_bot * scale_y)

        if orig_bot - orig_top < 5:
            continue

        crop = img_full.crop((0, orig_top, orig_w, orig_bot))
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            crop_path = f.name
        crop.save(crop_path)

        try:
            result = subprocess.run(
                ['tesseract', crop_path, 'stdout', '-l', lang, '--psm', '7'],
                capture_output=True, text=True, timeout=10
            )
            text = result.stdout.strip()
            if text and len(text) > 3:
                found_texts.append(text)
        except Exception:
            pass
        finally:
            if os.path.exists(crop_path):
                os.unlink(crop_path)

    return found_texts


# ─── Vision API (GPT-4o) for handwriting ─────────────────────────────────────

def read_handwriting_with_vision(image_path, side):
    """
    Send a margin image crop to GPT-4o vision and ask it to transcribe handwriting.
    Returns the transcribed text string, or None if unavailable/failed.
    """
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        return None

    # Encode image as base64
    with open(image_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')

    # Detect mime type
    mime = 'image/jpeg'
    if image_path.lower().endswith('.png'):
        mime = 'image/png'

    prompt = (
        f'This is a crop of the {side} margin of a physical book page. '
        'The reader made handwritten pencil notes or underlines. '
        'Transcribe exactly what is written. '
        'If there are multiple notes, list each on its own line. '
        'If nothing legible is written, reply with exactly: (blank)'
    )

    payload = json.dumps({
        'model': 'gpt-4o',
        'max_tokens': 300,
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'image_url', 'image_url': {
                    'url': f'data:{mime};base64,{img_b64}',
                    'detail': 'high'
                }}
            ]
        }]
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        text = result['choices'][0]['message']['content'].strip()
        if text and text.lower() != '(blank)':
            return text
        return None
    except Exception:
        return None


def read_handwriting_with_tesseract(image_path, side, lang):
    """Fallback: Tesseract OCR for margin strips."""
    try:
        result = subprocess.run(
            ['tesseract', image_path, 'stdout', '-l', lang, '--psm', '6', '--oem', '1'],
            capture_output=True, text=True, timeout=15
        )
        text = result.stdout.strip()
        if text and len(text) > 3:
            words = [w for w in text.split() if len(w) >= 3]
            if len(words) >= 1:
                return text
    except Exception:
        pass
    return None


# ─── Margin comment detection ─────────────────────────────────────────────────

def detect_margin_comments(image_path, gray_arr, lang):
    """
    Detect handwritten notes in left and right margin strips.
    Margin = outer ~15% of width on each side.
    Uses GPT-4o vision if OPENAI_API_KEY is available, falls back to Tesseract.
    """
    h, w = gray_arr.shape
    margin_w = max(int(w * 0.15), 40)

    img_full = Image.open(image_path).convert('RGB')
    orig_arr = np.array(img_full)
    orig_h_full, orig_w_full = orig_arr.shape[:2]
    scale_x = orig_w_full / w

    strips = [
        ('left',  img_full.crop((0, 0, int(margin_w * scale_x), orig_h_full))),
        ('right', img_full.crop((int((w - margin_w) * scale_x), 0, orig_w_full, orig_h_full))),
    ]

    has_vision = bool(os.environ.get('OPENAI_API_KEY', ''))
    comments = []

    for side, strip in strips:
        strip_gray = np.array(strip.convert('L'))
        # Skip if strip is mostly white (blank margin — no notes)
        dark_ratio = np.sum(strip_gray < 180) / strip_gray.size
        if dark_ratio < 0.01:
            continue

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            strip_path = f.name
        strip.save(strip_path, quality=90)

        try:
            if has_vision:
                text = read_handwriting_with_vision(strip_path, side)
                method = 'vision'
            else:
                text = None
                method = 'tesseract'

            # Fall back to Tesseract if vision unavailable or returned nothing
            if text is None:
                text = read_handwriting_with_tesseract(strip_path, side, lang)
                method = 'tesseract'

            if text:
                comments.append(f'[{side} margin/{method}] {text}')
        finally:
            if os.path.exists(strip_path):
                os.unlink(strip_path)

    return comments


# ─── Main ─────────────────────────────────────────────────────────────────────

def analyze(image_path, lang='por'):
    img, gray = load_gray(image_path)

    earmarked = detect_earmark(gray)
    underlines = detect_underlines(image_path, gray, lang)
    margin_comments = detect_margin_comments(image_path, gray, lang)

    return {
        'earmarked': earmarked,
        'underlines': underlines,
        'margin_comments': margin_comments,
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: detect_annotations.py <image_path> [lang]', file=sys.stderr)
        sys.exit(1)

    image_path = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else 'por'

    if not os.path.exists(image_path):
        print(f'ERROR: file not found: {image_path}', file=sys.stderr)
        sys.exit(1)

    result = analyze(image_path, lang)
    print(json.dumps(result, ensure_ascii=False, indent=2))
