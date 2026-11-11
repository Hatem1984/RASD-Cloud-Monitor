"""Verified 00:00–22:00 Cairo final Word; send is OUTSIDE this module.

Closeout inventories the day's private 30m source observations, reconciles
previously accepted real Word mail, independently re-verifies pending original
publisher pages, and refuses an incomplete or unverified final DOCX. No
synthetic screenshot, silent RSS truncation or mail fallback is possible.
"""
from __future__ import annotations
from collections import Counter
from datetime import date,datetime,time
from pathlib import Path
import hashlib
import json

from docx import Document
from cloud_proof_report import proof_capture,word_images_match_capture_digests
from daily_report import CAIRO,_rtl,render_docx
from event_identity import distinct_events
from rasd_owner_evidence_journal import audit_day
from rasd_halfhour_policy_qa import published_in_cairo,matched_owner_topics
from scheduled_rasd import (
    discover_interval_news,news_for_owner_calendar_rollup,
    validate_story,MAX_ROLLUP,MAX_WORD_BYTES)
from daily_sent_consolidator import consolidate_sent_words

def _verify_complete_sources(health, config):
    expected=[s["id"] for s in config["feeds"]]
    if ([r.get("feed_id") for r in health]!=expected
            or any(r.get("status")!="ok" for r in health)):
        raise RuntimeError("owner_final_live_source_coverage_hold")

def _within_day(article,day):
    pub=published_in_cairo(article)
    return pub.date()==day and time(0,0)<=pub.time().replace(tzinfo=None)<=time(22,0)

def _analysis(articles, settings):
    topics=Counter()
    publishers=Counter()
    for article in articles:
        publishers[article["source"]]+=1
        for label in matched_owner_topics(article,settings):
            topics[label]+=1
    topic_line="، ".join(f"{k}: {v}" for k,v in topics.most_common()) or "لا توجد فئات إضافية مطابقة حاليًا"
    source_line="، ".join(f"{k}: {v}" for k,v in publishers.most_common())
    return (f"تحليل وصفي مبني على {len(articles)} خبرًا موثقًا بلقطات أصلية. "
            f"توزيع موضوعات الرصد: {topic_line}. "
            f"توزيع الأخبار حسب الناشر: {source_line}. "
            "هذا التحليل يعرض التوزيع والتكرار فقط، ولا يستنتج اتجاهًا اقتصاديًا أو "
            "تأثيرًا حكوميًا من العناوين. نطاق الإثبات يقتصر على موجزات RSS "
            "التي تمت مراقبتها؛ لا يثبت وحده حصر كل ما نشرته المواقع.")

def prepare_owner_closeout(*,config:dict,baseline_config:dict,
                           owner_settings:dict,config_version:int,
                           day:date,now:datetime,ledger_state:dict,
                           private_journal:dict,output:Path,
                           sender:str,recipient:str,password:str,
                           approved_copy:str|None=None,
                           discover=discover_interval_news,
                           capture=proof_capture,
                           consolidate=consolidate_sent_words) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("owner_final_clock_requires_timezone")
    local=now.astimezone(CAIRO)
    if local.date()!=day or local.time()<time(22,0):
        return {"status":"WAIT_FOR_22_CAIRO","smtp_allowed":False}
    if owner_settings.get("scan_minutes")!=30 or owner_settings.get("send_at")!="22:00":
        raise RuntimeError("owner_final_schedule_settings_hold")
    health_ids=[f["id"] for f in config["feeds"]]
    audit=audit_day(private_journal,day,health_ids)
    if not audit.get("complete"):
        return {"status":"HOLD_EVIDENCE_SLOT_COVERAGE","smtp_allowed":False,
                "audit":{k:audit.get(k) for k in ("missing_slots","failed_slots","status")}}
    if any(row.get("config_version")>config_version for row in private_journal["slots"].values()):
        raise RuntimeError("owner_final_future_config_version_hold")
    live_health=[]
    latest=discover(config,now,allow_degraded=True,source_records=live_health,age_hours=24)
    _verify_complete_sources(live_health,config)
    story_by_id={}
    for candidate in [*audit["articles"],*latest]:
        if not _within_day(candidate,day):
            continue
        if not matched_owner_topics(candidate,owner_settings):
            # Previously matched terms may have been changed; accepted ledger
            # items are added separately, but never silently drop observed IDs.
            if candidate["id"] not in {a["id"] for a in audit["articles"]}:
                continue
        validate_story(candidate,baseline_config)
        old=story_by_id.get(candidate["id"])
        if old is not None and (old["url"]!=candidate["url"] or
                                old["headline"]!=candidate["headline"]):
            raise RuntimeError("owner_final_article_identity_drift_hold")
        story_by_id[candidate["id"]]=candidate
    # Daily report must not omit ANY previously accepted article from this day,
    # even when the owner updated keywords during the day.
    already=news_for_owner_calendar_rollup(ledger_state,day.isoformat(),baseline_config)
    for article in already:
        if article["id"] not in story_by_id:
            raise RuntimeError("owner_final_sent_story_absent_from_journal_hold")
    if len(story_by_id)>MAX_ROLLUP:
        raise RuntimeError("rollup_exceeds_60_verified_items_manual_review")
    sent_ids={a["id"] for a in already}
    # A RESERVED uncertain half-hour news item must never be treated as
    # either successfully sent or safe to retransmit in the final.
    new=[]
    for key,story in story_by_id.items():
        if key in sent_ids:
            continue
        if key in ledger_state["entries"]:
            raise RuntimeError("owner_final_uncertain_interval_story_hold")
        new.append(story)
    sent_order=sorted(already,key=lambda x:(published_in_cairo(x),x["id"]))
    new.sort(key=lambda x:(published_in_cairo(x),x["id"]))
    combined_order=sorted([*sent_order,*new],key=lambda x:(published_in_cairo(x),x["id"]))
    chosen,duplicates=distinct_events(combined_order)
    # Never drop a sent article silently. Conservative event duplicates among
    # already delivered stories remain visible and explicitly counted.
    if duplicates:
        return {"status":"HOLD_REPEATED_EVENTS_REQUIRE_REVIEW",
                "smtp_allowed":False,"duplicate_events":len(duplicates)}
    if not combined_order:
        return {"status":"NO_NEW_VERIFIED_NEWS_NO_DAILY_EMAIL","count":0,
                "smtp_allowed":False}
    output.mkdir(parents=True,exist_ok=True)
    artifacts={}
    # Recover originals from *actual* authenticated Gmail Sent Word attachments.
    if sent_order:
        sentdir=output/"sent"
        word,proofs=consolidate(sent_order,ledger_state,sentdir,
            sender=sender,recipient=recipient,app_password=password,
            title="رصد | استعادة أدلة الأخبار المرسلة في اليوم",
            start=f"{day.isoformat()} 00:00 القاهرة",
            end=f"{day.isoformat()} 22:00 القاهرة",
            config=baseline_config,approved_copy=approved_copy)
        if not word_images_match_capture_digests(word,proofs):
            raise RuntimeError("owner_final_sent_word_evidence_hold")
        for story,proof in zip(sent_order,proofs):
            p=sentdir/("daily-original-"+story["id"]+".jpg")
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=proof["sha256"]:
                raise RuntimeError("owner_final_sent_image_digest_hold")
            artifacts[story["id"]]=(p,proof["sha256"])
    # For missed/late stories, capture the ORIGINAL page before forming the
    # single final report. Any failure blocks the entire final email.
    for index,story in enumerate(new):
        path=output/f"final-fresh-{index:03d}.jpg"
        proof=capture(story,baseline_config["feeds"],path)
        if proof.get("status")!="verified":
            return {"status":"HOLD_FINAL_FRESH_ORIGINAL_IMAGE",
                    "smtp_allowed":False,"held_count":1,
                    "pending_count":len(new)}
        digest=proof.get("sha256")
        if (not isinstance(digest,str) or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest()!=digest):
            raise RuntimeError("owner_final_fresh_digest_hold")
        artifacts[story["id"]]=(path,digest)
    merged=[{**s,"evidence_image_path":str(artifacts[s["id"]][0])} for s in combined_order]
    aligned=[{"status":"verified","sha256":artifacts[s["id"]][1]}
             for s in combined_order]
    report={"title":f"رصد | التقرير المجمع — {day.isoformat()} — مراجعة الأدلة",
            "display_window_start":f"{day.isoformat()} 00:00 القاهرة",
            "display_window_end":f"{day.isoformat()} 22:00 القاهرة",
            "coverage":"VERIFIED_OBSERVED_RSS_SLOTS_NOT_FULL_WEB",
            "verified_links":len(merged),"articles":merged,
            "sources":[{"feed_id":x["feed_id"],"status":"ok",
                        "verified_links":x.get("verified_links",0),
                        "error_type":None} for x in live_health],
            "scope_note":"أُنجز فحص كل نصف ساعة للمصادر المهيأة، وأعيدت مطابقة الأدلة الأصلية.",
            "limitations":"التغطية مقيّدة بالمصادر المعتمدة وما ظهر في موجزاتها خلال الفحص الدوري. لا تعني حصر كل المقالات المنشورة خارج RSS."}
    word=output/"RASD-Owner-Daily-Original-Verified-QA.docx"
    render_docx(report,word)
    doc=Document(word)
    h=doc.add_paragraph()
    _rtl(h)
    h.add_run("التحليل الإجمالي").bold=True
    para=doc.add_paragraph()
    _rtl(para)
    para.add_run(_analysis(combined_order,owner_settings))
    temp=output/"_final-verified-postprocess.docx"
    doc.save(temp)
    if not word_images_match_capture_digests(temp,aligned):
        temp.unlink(missing_ok=True)
        raise RuntimeError("owner_final_word_image_identity_hold")
    if not 3_000<=temp.stat().st_size<=MAX_WORD_BYTES:
        temp.unlink(missing_ok=True)
        raise RuntimeError("owner_final_word_size_hold")
    temp.replace(word)
    return {"status":"READY_VERIFIED_DAILY_QA_NO_SEND",
            "smtp_allowed":False,"word":str(word),
            "count":len(merged),"fresh_ids":[x["id"] for x in new],
            "sent_archive_ids":[x["id"] for x in sent_order],
            "original_image_digests":[x["sha256"] for x in aligned],
            "audit_status":audit["status"]}
