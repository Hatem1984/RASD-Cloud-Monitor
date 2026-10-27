"""MA'AL Round2 — prove actual connected RASD → Evidence → Editorial → Report (offline).

Uses original implemented PR135 renderer and MA'AL Evidence contract.
Output is a separate QA report, not customer final, not live RASD or AI generation.
"""
from pathlib import Path
from datetime import date,datetime,timezone
import subprocess,sys,json,hashlib
BASE=Path(r"E:\MAAL")
MAAL=BASE/"01_ACTIVE_CODE"/"MAAL_PRODUCT_ACCEPTANCE_R2_20261027"
PR135=BASE/"01_ACTIVE_CODE"/"RASD_EDITORIAL_QUALITY_ISOLATED_20261027"
sys.path.insert(0,str(MAAL))
sys.path.insert(0,str(PR135))
from maal.decision_contracts import Evidence,BusinessContext
from maal_web.server import get_case,CASE_IMAGE
# MA'AL's server puts its own legacy daily_report on sys.path: pin PR135 first.
sys.path.insert(0,str(PR135))
from editorial_quality import build_editorial_brief
from editorial_quality_qa_runner import extract_24_word
from daily_report import render_docx
archive=BASE/"03_REPORTS_AND_REVIEW"/"rasd-stage2-live-20261025"/"RASD-Unified-2026-10-24.docx"
folder=BASE/"03_REPORTS_AND_REVIEW"/"MAAL_PRODUCT_ACCEPTANCE_R2_20261027"/"component_proof"
folder.mkdir(parents=True,exist_ok=True)
source17=get_case()
actual_sha=hashlib.sha256(CASE_IMAGE.read_bytes()).hexdigest()
assert actual_sha==source17["evidence_digest"]
e=Evidence(source17["evidence_id"],source17["publisher"],source17["original_url"],
 source17["finding"],date.fromisoformat(source17["published_day"]),
 datetime.fromisoformat(source17["observed_at"]),actual_sha,"VERIFIED_ORIGINAL_PAGE")
e.validate()
company=BusinessContext("SYNTHETIC-DIGITAL-AI-EGYPT",
 "شركة منتجات رقمية وحلول ذكاء اصطناعي افتراضية","مصر")
verified=build_editorial_brief(headline=source17["headline"],publisher_excerpt=source17["finding"],
 original_url=source17["original_url"],publisher=source17["publisher"],
 published_day=source17["published_day"],proof_status="VERIFIED_ORIGINAL_PAGE",
 approved_hosts={"mped.gov.eg"},capture_path=CASE_IMAGE,capture_sha256=actual_sha)
word24=extract_24_word(archive)
a=word24["articles"][0]
archive_brief=build_editorial_brief(headline=a["headline"],publisher_excerpt="",
 original_url=a["url"],publisher="وزارة التخطيط — الموقع الرسمي",
 published_day="2026-10-24",proof_status="LOCAL_ARCHIVE_QA",
 approved_hosts={"www.mped.gov.eg","mped.gov.eg"})
assert verified["qa_only"] is False and archive_brief["qa_only"] is True
assert any("5 مليارات" in v["exact_source_span"] for v in archive_brief["figures_from_exact_source_spans"])
assert "5,000 شركة" not in str(archive_brief)
# Existing quality Word renderer accepts QA-only with source identity not attributed to live.
report={
 "title":"مَآل | QA تشغيل فعلي لمكونات الأدلة والتحرير — ليس التقرير النهائي",
 "display_window_start":"17 أكتوبر 2026 (أرشيف تاريخي)",
 "display_window_end":"24 أكتوبر 2026 (أرشيف تاريخي)",
 "coverage":"LIMITED_ARCHIVE_QA","verified_links":2,
 "preview_only":True,"window_article_count":2,"truncated":False,
 "editorial_archive_only":True,"editorial_allowed_hosts":["mped.gov.eg","www.mped.gov.eg"],
 "limitations":"عينة تاريخية محدودة، شركة افتراضية "+company.sector+
 ". أصل 17 أكتوبر JPEG موثق؛ 24 أكتوبر عنوان Word فقط وغير مؤهل لدليل الصورة. "+
 "بيان 26 أكتوبر HOLD. ليس رصدًا حيًا أو إرسالا للبريد.",
 "sources":[],
 "articles":[{
  "headline":source17["headline"],"publisher_excerpt":source17["finding"],
  "source":"mped-official","url":source17["original_url"],
  "published_at_cairo":"2026-10-17 (DATE_ONLY)","published_display_cairo":"17 أكتوبر 2026 — يوم فقط"
 },{
  "headline":a["headline"],"publisher_excerpt":"",
  "source":"mped-official","url":a["url"],
  "published_at_cairo":"2026-10-24 (DATE_ONLY)","published_display_cairo":"24 أكتوبر 2026 — يوم فقط"
 }]
}
out=folder/"MAAL_Actual_Component_Generated_QA_20261027.docx"
if out.exists():raise RuntimeError("existing_artifact_no_overwrite")
render_docx(report,out,editorial_mode="qa_only")
from docx import Document
words="\n".join(p.text for p in Document(out).paragraphs)
assert words.count("الحقيقة المثبتة في العنوان:")==2 and words.count("ما الذي لم يُثبت؟")==2
receipt={
 "type":"MAAL_R2_COMPONENT_INTEGRATION_RECEIPT",
 "time_utc":datetime.now(timezone.utc).isoformat(),
 "real_components":[
  "maal.decision_contracts.Evidence.validate",
  "maal.decision_contracts.BusinessContext",
  "maal_web.server.get_case original JPEG verification",
  "PR135 editorial_quality.build_editorial_brief",
  "PR135 daily_report.render_docx(qa_only)"
 ],
 "editorial_commit":subprocess.check_output(["git","-C",str(PR135),"rev-parse","HEAD"],text=True).strip(),
 "source_17":{"level":"VERIFIED_ORIGINAL_PAGE","image_sha256":actual_sha},
 "source_24":{"level":"LOCAL_ARCHIVE_QA","rasd_word_sha256":hashlib.sha256(archive.read_bytes()).hexdigest()},
 "source_26":{"level":"HOLD_NO_ORIGINAL_JPEG","included":False},
 "company_synthetic":True,"source_count":2,
 "new_docx":str(out),"new_docx_sha256":hashlib.sha256(out.read_bytes()).hexdigest(),
 "owner_editorial_report_is_a_distinct_review_artifact":True,
 "fresh_qwen":False,"live_rasd_feed":False,"gmail":False,"cas":False,"action":False,"human_approval":False}
(folder/"MAAL_R2_Component_Receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf8")
print("ROUND2_ACTUAL_EVIDENCE_EDITORIAL_REPORT_CHAIN_PASS",json.dumps({
 "sources":2,"proof17_sha":actual_sha,"proof24":"ARCHIVE_ONLY",
 "qa_report_sha":receipt["new_docx_sha256"],"email":False},ensure_ascii=False))
