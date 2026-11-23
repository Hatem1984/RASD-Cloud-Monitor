"""Live first-party RSS -> genuine publisher screenshot -> Word QA (NO SEND).

Ephemeral GitHub runner. This assesses the availability of the currently
approved RASD publisher originals and real Word JPEG hashes. It does NOT
claim the samples were all published inside the most recent completed hour.
No SMTP, private ledger, recipient, Google credentials or artifact upload.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from daily_report import CAIRO, cairo_display_time
from scheduled_rasd import (
    discover_interval_news, prepare_source_limited_verified_word)
from cloud_proof_report import word_images_match_capture_digests


def main():
    if os.getenv("RASD_AUTOMATION_ENABLED") != "false":
        raise RuntimeError("live_original_word_qa_requires_no_send_mode")
    cfg=json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    now=datetime.now(timezone.utc)
    health=[]
    matches=discover_interval_news(
        cfg,now,allow_degraded=True,source_records=health)
    # Inspect limited, distinct publishers for last-72h compatibility.
    picked=[]
    seen=set()
    for row in matches:
        if row["source"] not in seen:
            picked.append(row)
            seen.add(row["source"])
        if len(picked)==3:
            break
    print("RASD_LIVE_RESEARCH_SOURCE_HEALTH="+json.dumps({
        "at_cairo":now.astimezone(CAIRO).isoformat(),
        "feeds_checked":len(health),
        "feeds":[{"id":entry["feed_id"],
                  "status":entry["status"],
                  "validated_rss_links":entry.get("verified_links",0),
                  "failure_code":entry.get("failure_code","none")}
                 for entry in health],
        "relevant_last72h":len(matches),
        "distinct_publishers_sampled":len(picked),
        "not_hourly_acceptance":True,
        "smtp_attempted":False,
    },ensure_ascii=True,sort_keys=True),flush=True)
    if not picked:
        print("RASD_LIVE_IMAGE_WORD_RESULT=HOLD_NO_RELEVANT_ORIGINALS",flush=True)
        return
    with tempfile.TemporaryDirectory(prefix="rasd-real-publisher-photo-no-send-") as d:
        target=Path(d)
        held=[]
        try:
            word,selected,count,limited=prepare_source_limited_verified_word(
                picked,cfg,target,
                title="رصد | فحص حقيقي لصفحات الناشرين — بدون إرسال",
                start=cairo_display_time(now),
                end=cairo_display_time(now),
                source_records=health,
                held_items=held,
                report_kind="half_hourly")
        except RuntimeError as error:
            if str(error)!="no_original_publisher_page_verified":
                raise
            print("RASD_LIVE_IMAGE_WORD_RESULT="+json.dumps({
                "result":"HOLD_NO_ORIGINAL_JPEG",
                "requested":len(picked),
                "held_reasons":[{"source":e["source"],"reason":e["reason"]}
                                 for e in held],
                "smtp_attempted":False
            },ensure_ascii=True),flush=True)
            return
        doc=Document(word)
        links={rel.target_ref for rel in doc.part.rels.values()
               if rel.reltype.endswith("/hyperlink")}
        if (len(doc.inline_shapes)!=len(selected)
                or any(row["url"] not in links for row in selected)
                or any(row["headline"] not in
                       "\n".join(p.text for p in doc.paragraphs)
                       for row in selected)):
            raise RuntimeError("live_original_word_title_url_image_mismatch_hold")
        proofs=[]
        from hashlib import sha256
        for row in selected:
            src=Path(row["evidence_image_path"])
            proofs.append({
                "status":"verified","sha256":sha256(src.read_bytes()).hexdigest()})
        if not word_images_match_capture_digests(word,proofs):
            raise RuntimeError("live_original_word_SHA256_identity_hold")
        print("RASD_LIVE_IMAGE_WORD_RESULT="+json.dumps({
            "result":"VERIFIED_PARTIAL" if limited else "VERIFIED",
            "requested":len(picked),"verified_word_articles":len(selected),
            "embedded_jpegs":len(doc.inline_shapes),
            "sha256_exact_match":True,
            "original_links_and_titles_exact":True,
            "photo_held":[{"source":e["source"],"reason":e["reason"]}
                          for e in held],
            "word_bytes":word.stat().st_size,
            "smtp_attempted":False,
            "private_ledger_mutated":False,
        },ensure_ascii=True),flush=True)


if __name__=="__main__":
    main()
