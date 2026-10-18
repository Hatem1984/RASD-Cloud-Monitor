"""Ephemeral renderer QA for a real RASD Arabic Word report.

Never publishes publisher images, rendered PDF, raster pages, or Word.
Requires LibreOffice + Poppler on an isolated runner. This is automated
render/layout preflight, NOT a substitute for human page-by-page review.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from docx import Document
from PIL import Image


def _run(command: list[str], *, timeout=80):
    return subprocess.run(command, check=True, capture_output=True,
                          text=True, timeout=timeout)


def rendered_word_preflight(word: Path, *, expected_articles: int) -> dict:
    if (not isinstance(expected_articles, int) or isinstance(expected_articles, bool)
            or not 1 <= expected_articles <= 15):
        raise ValueError("qa_article_count_invalid")
    word = Path(word)
    if not word.is_file() or word.suffix.lower() != ".docx":
        raise ValueError("qa_word_not_available")
    if not shutil.which("libreoffice") or not shutil.which("pdftoppm"):
        raise RuntimeError("qa_renderer_or_poppler_not_installed")
    doc = Document(word)
    if len(doc.inline_shapes) != expected_articles:
        raise ValueError("qa_original_publisher_image_count_mismatch")
    # Inspect Word's native layout constraints before conversion.
    from docx.shared import Inches
    for shape in doc.inline_shapes:
        if not (Inches(0.6) <= shape.width <= Inches(5.6) + 2000
                and Inches(0.6) <= shape.height <= Inches(6.2) + 2000):
            raise ValueError("qa_picture_bounds_exceeded")
    with tempfile.TemporaryDirectory(prefix="rasd-private-page-render-") as tmp:
        scratch = Path(tmp)
        profile = (scratch / "lo-profile").as_uri()
        _run([
            "libreoffice", "-env:UserInstallation=" + profile,
            "--headless", "--convert-to", "pdf",
            "--outdir", str(scratch), str(word.resolve()),
        ], timeout=110)
        pdfs = list(scratch.glob("*.pdf"))
        if len(pdfs) != 1 or pdfs[0].stat().st_size < 5000:
            raise ValueError("qa_offline_pdf_render_failed")
        pdf = pdfs[0]
        _run(["pdftoppm", "-png", "-scale-to", "950",
              str(pdf), str(scratch / "page")], timeout=120)
        pages = sorted(scratch.glob("page-*.png"))
        if not pages or len(pages) > max(3, expected_articles * 4 + 3):
            raise ValueError("qa_rendered_page_count_invalid")
        coverage = []
        for page in pages:
            with Image.open(page) as raw:
                gray = raw.convert("L")
                if raw.width < 550 or raw.height < 550:
                    raise ValueError("qa_page_raster_too_small")
                pixels = list(gray.resize((190, 250)).getdata())
                # Detect blank/solid-image pages with unexpected rendering.
                ink = sum(1 for v in pixels if v < 215) / len(pixels)
                if not 0.002 <= ink <= 0.80:
                    raise ValueError("qa_blank_or_unreadable_rendered_page")
                coverage.append(round(ink, 4))
        return {
            "status": "RENDER_CHECK_PASSED_NOT_HUMAN_REVIEW",
            "rendered_page_count": len(pages),
            "article_image_count": len(doc.inline_shapes),
            "minimum_page_ink_ratio": min(coverage),
            "maximum_page_ink_ratio": max(coverage),
            "ephemeral_render_destroyed": True,
            "publisher_image_or_pdf_uploaded": False,
            "human_visual_review": False,
        }


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("word", type=Path)
    parser.add_argument("--articles", type=int, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(rendered_word_preflight(
            args.word, expected_articles=args.articles), sort_keys=True))
    except Exception:
        print(json.dumps({"status": "HOLD", "reason": "render_preflight_failed",
                          "publisher_image_or_pdf_uploaded": False}))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
