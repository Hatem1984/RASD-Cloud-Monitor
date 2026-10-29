"""Immutable per-Qwen-run Word/PDF bundle; all source bytes remain on E: QA.

Never serves historical static reports as new model output. The owner-local
report requires true original JPEG SHA and the current saved model run.
"""
from pathlib import Path
from hashlib import sha256
import json


def _hash(data): return sha256(data).hexdigest()


def freeze_bundle(case, ai, original_image: bytes, output_root: Path) -> dict:
    """Owner-local CLI only; no public GitHub artifacts or any mail."""
    from maal.competition_report import create_agent_brief_docx
    from zipfile import ZipFile
    from io import BytesIO
    from docx import Document
    docx_data = create_agent_brief_docx(case, ai, original_image)
    folder = Path(output_root)/ai["run_id"]
    folder.mkdir(parents=True,exist_ok=False)
    word=folder/"MAAL-Source-Qwen-Review.docx"
    pdf=folder/"MAAL-Source-Qwen-Review.pdf"
    word.write_bytes(docx_data)
    import win32com.client
    app=win32com.client.DispatchEx("Word.Application")
    app.Visible=False
    app.DisplayAlerts=0
    try:
        document=app.Documents.Open(str(word.resolve()),ReadOnly=True)
        try: document.ExportAsFixedFormat(str(pdf.resolve()),17)
        finally: document.Close(False)
    finally:
        app.Quit()
    pdf_bytes=pdf.read_bytes()
    if not pdf_bytes.startswith(b"%PDF") or not 5000<=len(pdf_bytes)<=8_000_000:
        raise ValueError("pdf_generation_hold")
    # Require actual original photo embedded in source Word, not just metadata.
    with ZipFile(BytesIO(docx_data)) as z:
        media=[n for n in z.namelist() if n.startswith("word/media/") and not n.endswith("/")]
        if len(media)!=1 or _hash(z.read(media[0]))!=case["evidence_digest"]:
            raise ValueError("word_original_image_digest_hold")
    import pymupdf
    rendered=pymupdf.open(str(pdf))
    try:
        text=" ".join(page.get_text() for page in rendered)
        page_count=len(rendered)
        page_images=sum(len(page.get_images()) for page in rendered)
    finally: rendered.close()
    if (ai["run_id"] not in text or page_images<1 or
        "مَآل" not in text or page_count>8):
        raise ValueError("pdf_model_or_source_visual_integrity_hold")
    manifest={
        "schema":"MAAL_LINKED_QWEN_SOURCE_REPORT_V1",
        "mode":"HISTORICAL_QA_HUMAN_REVIEW_PENDING",
        "run_id":ai["run_id"],
        "evidence_id":case["evidence_id"],
        "original_jpeg_sha256":case["evidence_digest"],
        "docx_sha256":_hash(docx_data),
        "pdf_sha256":_hash(pdf_bytes),
        "pdf_page_count":page_count,
        "pdf_image_count":page_images,
        "human_editorial_approval":False,
        "emailed":False,
        "live_news":False,
    }
    (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest


def read_bound_bundle(case, ai, output_root: Path):
    """Return pre-generated PDF/DOCX bytes only if source/model/manifest match."""
    folder=Path(output_root)/ai["run_id"]
    manifest=json.loads((folder/"manifest.json").read_text("utf-8"))
    if (manifest.get("schema")!="MAAL_LINKED_QWEN_SOURCE_REPORT_V1"
        or manifest.get("mode")!="HISTORICAL_QA_HUMAN_REVIEW_PENDING"
        or manifest.get("run_id")!=ai["run_id"]
        or manifest.get("evidence_id")!=case["evidence_id"]
        or manifest.get("original_jpeg_sha256")!=case["evidence_digest"]
        or manifest.get("human_editorial_approval") is not False
        or manifest.get("emailed") is not False):
        raise ValueError("report_model_evidence_binding_hold")
    content={}
    for typ,name in (("docx","MAAL-Source-Qwen-Review.docx"),
                     ("pdf","MAAL-Source-Qwen-Review.pdf")):
        blob=(folder/name).read_bytes()
        if _hash(blob)!=manifest[typ+"_sha256"]:
            raise ValueError("report_file_digest_mismatch")
        content[typ]=blob
    # Guard the original publisher's exact bytes in Word on every download.
    from zipfile import ZipFile
    from io import BytesIO
    with ZipFile(BytesIO(content["docx"])) as doc:
        names=[n for n in doc.namelist() if n.startswith("word/media/") and not n.endswith("/")]
        if len(names)!=1 or _hash(doc.read(names[0]))!=case["evidence_digest"]:
            raise ValueError("report_original_media_identity_hold")
    return manifest,content
