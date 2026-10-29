"""Freeze current source/Qwen Word/PDF in private owner-local QA directory.

Requires Windows Word COM; never uploads files or writes production state.
"""
from pathlib import Path
import json
from maal_web.server import get_case,get_local_ai_run,CASE_IMAGE,MODEL_RUN
from maal.competition_report_bundle import freeze_bundle


def main():
    case=get_case()
    model=get_local_ai_run()
    target=MODEL_RUN.parent/"reports"
    manifest=freeze_bundle(case,model,CASE_IMAGE.read_bytes(),target)
    print(json.dumps({
        "status":"SOURCE_LINKED_REPORT_FROZEN_REVIEW_ONLY",
        "run_id":manifest["run_id"],
        "evidence_sha256":manifest["original_jpeg_sha256"],
        "docx_sha256":manifest["docx_sha256"],
        "pdf_sha256":manifest["pdf_sha256"],
        "pages":manifest["pdf_page_count"],
        "images":manifest["pdf_image_count"],
        "folder":str(target/manifest["run_id"]),
    },ensure_ascii=False))


if __name__=="__main__":
    main()
