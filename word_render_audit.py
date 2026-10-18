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
import unicodedata
import tempfile
from pathlib import Path

from docx import Document
from PIL import Image


def _run(command: list[str], *, timeout=80):
    return subprocess.run(command, check=True, capture_output=True,
                          text=True, timeout=timeout)


def _review_original_picture_dimensions(doc, *, expected_articles: int) -> None:
    """Fail closed on tiny pictures even if the JPEG SHA is correct.

    A 1200x4800 full-page capture shrunk to 6.2 inches high becomes just
    1.55 inches wide in Word, which is mechanically valid but unreadable.
    Do not crop or resize/reencode evidence to 'pass' this check.
    """
    from docx.shared import Inches
    if len(doc.inline_shapes) != expected_articles:
        raise ValueError("qa_original_publisher_image_count_mismatch")
    for shape in doc.inline_shapes:
        if not (Inches(3.0) <= shape.width <= Inches(5.6) + 2000
                and Inches(0.6) <= shape.height <= Inches(6.2) + 2000):
            raise ValueError("qa_publisher_picture_too_narrow_or_outside_page")


_ARABIC_TASHKEEL_AND_TATWEEL = re.compile(
    r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]")
_ARABIC_ALEF_FOR_RENDER = str.maketrans(
    {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})


def _arabic_headline_tokens(
    text: str, *, pdf_extraction: bool = False,
) -> set[str]:
    # Compare typographic variants ONLY in rendered PDF QA. Never rewrite
    # publisher titles, Word document text, dates, links, or screenshot bytes.
    normalized = unicodedata.normalize("NFKC", text)
    normalized = _ARABIC_TASHKEEL_AND_TATWEEL.sub(
        "", normalized).translate(_ARABIC_ALEF_FOR_RENDER)
    tokens = set(re.findall(r"[\u0621-\u064a\u066e-\u06d3]{3,}",
                            normalized))
    if not pdf_extraction:
        return tokens
    # Reproducible LibreOffice/Poppler Arabic text-layer artifact:
    # source "الاقتصادية" -> pdftotext "االقتصادية", and
    # source "والاقتصاد" -> pdftotext "واالقتصاد".
    # Allow ONLY one duplicated initial Alef immediately before "ال",
    # optionally after one common Arabic proclitic. The rest of each FULL
    # original title token must still be present in a single PDF extraction.
    return {re.sub(r"^([وفبكل]?)اال", r"\1ال", token) for token in tokens}


def _verify_original_headlines_in_pdf(doc, pdf_text: str, count: int) -> None:
    """Ensure Arabic report headlines survive LibreOffice rendering.

    This is a mechanical text-layer check, not human visual acceptance.
    It never OCRs a private publisher screenshot or copies article content
    into CI logs; failures are generic, never show the source paragraph.
    """
    visible = _arabic_headline_tokens(pdf_text, pdf_extraction=True)
    if len(visible) < 3:
        raise ValueError("qa_rendered_arabic_text_layer_missing")
    seen = 0
    for paragraph in doc.paragraphs:
        if not re.match(r"^\s*\d{1,2}\.\s+", paragraph.text):
            continue
        seen += 1
        important = _arabic_headline_tokens(paragraph.text)
        # Verify EVERY meaningful Arabic token from this complete title.
        # Previously checking only the two longest words could approve
        # another story sharing "وزارة التخطيط" while omitting its subject.
        # Never combine fragments across distinct PDF extraction modes.
        if len(important) < 2 or not important.issubset(visible):
            raise ValueError("qa_rendered_original_headline_missing")
    if seen != count:
        raise ValueError("qa_original_report_headline_count_mismatch")


def _verify_headlines_in_independent_pdf_extractions(
    doc, *, layout_text: str, raw_text: str, expected_articles: int,
) -> str:
    """Both extraction modes operate on the SAME private rendered PDF.

    A Poppler layout export can mis-group RTL Arabic glyphs. The raw mode
    can preserve source word grouping differently. Require at least one
    FULL, independently extracted article-heading token validation.
    NEVER accept missing titles, replace original text or expose publisher
    words in logs; only return the name of the successful mode.
    """
    try:
        _verify_original_headlines_in_pdf(
            doc, layout_text, expected_articles)
        return "layout"
    except ValueError as exc:
        if str(exc) != "qa_rendered_original_headline_missing":
            raise
    _verify_original_headlines_in_pdf(
        doc, raw_text, expected_articles)
    return "raw"


def rendered_word_preflight(
    word: Path, *, expected_articles: int,
    review_pages_dir: Path | None = None,
) -> dict:
    if (not isinstance(expected_articles, int) or isinstance(expected_articles, bool)
            or not 1 <= expected_articles <= 15):
        raise ValueError("qa_article_count_invalid")
    word = Path(word)
    if not word.is_file() or word.suffix.lower() != ".docx":
        raise ValueError("qa_word_not_available")
    if not shutil.which("libreoffice") or not shutil.which("pdftoppm") or not shutil.which("pdftotext"):
        raise RuntimeError("qa_renderer_or_poppler_not_installed")
    doc = Document(word)
    _review_original_picture_dimensions(doc, expected_articles=expected_articles)
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
        # Check that each source-backed Arabic headline actually survived
        # layout conversion, independently of Word's XML text presence.
        pdf_text = _run(["pdftotext", "-layout", str(pdf), "-"],
                        timeout=45).stdout
        # Both independent Poppler extraction modes read the same private
        # PDF: never combine partial matches across modes to falsely pass.
        try:
            _verify_original_headlines_in_pdf(
                doc, pdf_text, expected_articles)
            verified_text_mode = "layout"
        except ValueError as exc:
            if str(exc) != "qa_rendered_original_headline_missing":
                raise
            pdf_raw = _run(["pdftotext", "-raw", str(pdf), "-"],
                           timeout=45).stdout
            verified_text_mode = _verify_headlines_in_independent_pdf_extractions(
                doc, layout_text=pdf_text, raw_text=pdf_raw,
                expected_articles=expected_articles)
        # Use higher-resolution local page raster for a human reviewer
        # when pages are staged for the encrypted owner-only package.
        # Mechanical-only smoke checks keep their lighter 950px render.
        review_scale = "1600" if review_pages_dir is not None else "950"
        _run(["pdftoppm", "-png", "-scale-to", review_scale,
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
        # Copy only already-validated, private raster images. Neither the
        # Word nor the intermediate PDF is exposed by this helper.
        # The caller MUST encrypt this folder into the owner's package and
        # MUST NOT publish it as plaintext in GitHub Actions.
        if review_pages_dir is not None:
            destination = Path(review_pages_dir)
            if destination.exists():
                raise ValueError("qa_review_pages_destination_already_exists")
            destination.mkdir(parents=True)
            try:
                for index, source in enumerate(pages, 1):
                    target = destination / f"page-{index:03d}.png"
                    shutil.copyfile(source, target)
            except Exception:
                for item in destination.iterdir():
                    item.unlink()
                destination.rmdir()
                raise
        return {
            "status": "RENDER_CHECK_PASSED_NOT_HUMAN_REVIEW",
            "rendered_page_count": len(pages),
            "article_image_count": len(doc.inline_shapes),
            "arabic_headlines_rendered": expected_articles,
            "arabic_text_extraction_mode": verified_text_mode,
            "publisher_screenshot_minimum_word_width_inches": 3.0,
            "minimum_page_ink_ratio": min(coverage),
            "maximum_page_ink_ratio": max(coverage),
            "ephemeral_render_destroyed": True,
            "publisher_image_or_pdf_uploaded": False,
            "private_owner_review_pages_staged": review_pages_dir is not None,
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
