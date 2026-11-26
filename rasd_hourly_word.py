"""Detached hourly Word contract. No scheduling, SMTP, ledger writes or activation."""
from datetime import datetime,timedelta,timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from collections import Counter
import hashlib
import re
from tempfile import TemporaryDirectory

from daily_report import CAIRO,cairo_display_time,render_docx,SOURCE_LABELS
from monitor import SOURCE_FAILURE_CODES
from gate11_runner import candidate_from_feed,SAFE_CAPTURE_FAILURE_CODES
from cloud_proof_report import proof_capture,word_images_match_capture_digests
from event_identity import same_event,related_event_pairs
from elbalad_date_evidence import CONFLICT,DISCLOSURE
from rasd_ministry_visual_layout import render_hourly_zero_word

TARGET=10
MAX_WORD_BYTES=8_000_000


def completed_hour(scan):
    if not isinstance(scan,datetime) or scan.tzinfo is None or scan.utcoffset() is None:
        raise ValueError("hourly_scan_clock_unzoned")
    end=scan.astimezone(timezone.utc).replace(minute=0,second=0,microsecond=0)
    return end-timedelta(hours=1),end


def _window_label(stamp):
    # Zone abbreviation distinguishes repeated local clock hours at DST change.
    return cairo_display_time(stamp)+" ("+stamp.astimezone(CAIRO).tzname()+")"


def _source_failure_labels(config,source_records):
    labels=[]
    for feed,record in zip(config["feeds"],source_records):
        if record["status"]!="failed":
            continue
        code=record.get("failure_code","other")
        if code not in SOURCE_FAILURE_CODES:
            code="other"
        reason={
            "rss_original_item_future_date":"تاريخ نشر مستقبلي غير موثوق",
            "rss_original_publisher_date_conflict_hold":"قيد تعارض توقيت الناشر",
            "rss_original_item_date_unverifiable":"تاريخ النشر غير قابل للتحقق",
            "alborsa_listing_coverage_hold":"تعذر إثبات نطاق القائمة الأصلية",
            "http_403":"رفض الوصول",
            "http_429":"تقييد الطلبات",
            "network_timeout":"انتهاء مهلة الاتصال",
            "upstream_network_error":"تعذر الاتصال",
        }.get(code,"تعذر التحقق من المصدر")
        if feed.get("publication_date_conflict_hold") is True:
            reason+="؛ قيد توقيت معتمد"
        labels.append(SOURCE_LABELS.get(feed["name"],feed["name"])+" ("+feed["id"]+"): "+reason)
    return labels


def build_hourly_word(raw,config,source_records,scan,destination,*,capture=proof_capture,history=(),qa_window_end=None):
    """Current completed hour only; older candidates accounted separately.
    All input decisions returned, never considered delivered or reserved.
    Synthetic capture injection is for offline tests, not production authorization.
    """
    start,end=completed_hour(scan)
    scan=scan.astimezone(timezone.utc)
    retrospective=qa_window_end is not None
    if retrospective:
        if (not isinstance(qa_window_end,datetime) or qa_window_end.tzinfo is None or qa_window_end.utcoffset() is None):
            raise ValueError("hourly_qa_window_unzoned")
        chosen_end=qa_window_end.astimezone(timezone.utc)
        if (chosen_end> end or chosen_end<scan-timedelta(hours=71) or
                (chosen_end.minute,chosen_end.second,chosen_end.microsecond)!=(0,0,0)):
            raise ValueError("hourly_qa_window_outside_scope")
        start,end=chosen_end-timedelta(hours=1),chosen_end
    if not isinstance(raw,list) or len(raw)>200:
        raise ValueError("hourly_inventory_hold")
    ids=[f["id"] for f in config["feeds"]]
    if ([s.get("feed_id") for s in source_records]!=ids or
            any(s.get("status") not in {"ok","failed"} for s in source_records)):
        raise ValueError("hourly_source_health_hold")
    history=list(history)
    if len(history)>5000 or any(not isinstance(x,dict) or not x.get("id") or
            not x.get("published_at_cairo") for x in history):
        raise ValueError("hourly_history_untrusted")
    prior={x["id"] for x in history}
    decisions=[None]*len(raw)
    eligible=[]
    seen={}
    for index,row in enumerate(raw):
        candidate=candidate_from_feed(row,config,scan)
        if candidate is None:
            decisions[index]="invalid_original_candidate";continue
        stamp=parsedate_to_datetime(candidate["published"]).astimezone(timezone.utc)
        key=candidate["id"]
        if key in prior:
            decisions[index]="repeated_link";continue
        identity=(candidate["url"],candidate["headline"],candidate["source"],stamp)
        if key in seen:
            if seen[key]!=identity:raise ValueError("hourly_conflicting_link_evidence_hold")
            decisions[index]="repeated_link";continue
        seen[key]=identity
        if stamp>=end:
            decisions[index]="outside_completed_hour";continue
        if stamp<start:
            decisions[index]="recovery_separate";continue
        if next(s for s,f in zip(source_records,config["feeds"]) if f["name"]==candidate["source"])["status"]!="ok":
            decisions[index]="source_unavailable";continue
        eligible.append((stamp,index,{**candidate,
            "published_at_cairo":stamp.astimezone(CAIRO).strftime("%Y-%m-%d %H:%M %Z"),
            "published_display_cairo":cairo_display_time(stamp),
            "hourly_scan_display_cairo":cairo_display_time(scan),
            "hourly_publication_bucket":"within_previous_hour"}))
    eligible.sort(key=lambda x:(x[0],x[2]["id"]),reverse=True)
    destination=Path(destination)
    if destination.exists():
        raise ValueError("hourly_destination_exists")
    destination.parent.mkdir(parents=True,exist_ok=True)
    selected=[];receipts=[];publishers=set();holds=[]
    with TemporaryDirectory(prefix="rasd-hourly-word-",dir=destination.parent) as temp:
        root=Path(temp)
        for _,index,item in eligible:
            if len(selected)>=TARGET:
                decisions[index]="target_capacity_deferred";continue
            if item["publisher"] in publishers:
                decisions[index]="publisher_diversity_deferred";continue
            if any(same_event(item,x) for x in (*history,*selected)) or related_event_pairs([item],(*history,*selected)):
                decisions[index]="related_event_review_deferred";continue
            path=root/f"original-{index:03d}.jpg"
            proof=capture(item,config["feeds"],path)
            if proof.get("status")=="hold":
                decisions[index]="original_evidence_hold"
                reason=proof.get("reason")
                holds.append({"reason":reason if reason in SAFE_CAPTURE_FAILURE_CODES else "other"})
                continue
            digest=proof.get("sha256")
            if (proof.get("status")!="verified" or not isinstance(digest,str) or
                    not re.fullmatch("[0-9a-f]{64}",digest) or not path.is_file() or
                    hashlib.sha256(path.read_bytes()).hexdigest()!=digest):
                raise RuntimeError("hourly_image_identity_hold")
            selected.append({**item,"evidence_image_path":str(path),
                             "publication_date_status":proof.get("publication_date_status")})
            receipts.append(proof);publishers.add(item["publisher"])
            decisions[index]="verified_in_hour"
        assert all(decisions)
        counts=Counter(decisions)
        deferred=sum(v for k,v in counts.items() if k.endswith("_deferred"))
        held=counts["original_evidence_hold"]+counts["invalid_original_candidate"]+counts["source_unavailable"]
        limitations=("المستهدف مشروط بتوفر الأخبار الموثقة؛ المواد الأقدم خارج المستهدف، "
                     "ولا تُعد المواد المؤجلة أو المعلقة أخبارًا مسلّمة. لا يثبت الفحص شمول كل المنشورات.")
        if retrospective:
            limitations+=" اختبار استعادي فقط ببيانات الفحص الحالية؛ لا يثبت الاكتشاف أو التغطية أو الإرسال وقت الساعة المختارة."
        if any(x.get("publication_date_status")==CONFLICT for x in selected):
            limitations+=DISCLOSURE
        report={"title":"رصد | تقرير المتابعة الساعية — نسخة اختبار غير مرسلة",
            "display_window_start":_window_label(start),"display_window_end":_window_label(end),
            "hourly_retrospective_qa":retrospective,"hourly_source_failures_display":_source_failure_labels(config,source_records),
            "hourly_scan_display_cairo":cairo_display_time(scan),"hourly_word_contract":True,
            "ministry_media_grid":True,"report_period":"interval","report_kind":"hourly",
            "hourly_in_period":len(selected),"hourly_recovered":0,
            "hourly_recovery_pending":counts["recovery_separate"],"hourly_deferred":deferred,
            "hourly_held":held,"coverage":"SOURCE_LIMITED" if held or deferred or any(s["status"]!="ok" for s in source_records) else "HEALTHY",
            "articles":selected,"sources":source_records,"held_candidates":holds,"verified_links":len(selected),
            "limitations":limitations}
        staged=root/"hourly.docx"
        if selected:
            render_docx(report,staged)
            if not word_images_match_capture_digests(staged,receipts):
                raise RuntimeError("hourly_word_image_identity_hold")
        else:
            render_hourly_zero_word(report,staged)
        if not 3000<=staged.stat().st_size<=MAX_WORD_BYTES:
            raise RuntimeError("hourly_word_size_hold")
        staged.replace(destination)
    return {"status":"READY_QA_ONLY","fresh":len(selected),"target":TARGET,"deficit":TARGET-len(selected),
            "publishers":len(publishers),"decisions":decisions,"counts":dict(counts),"coverage":report["coverage"],
            "source_failures":sum(s["status"]!="ok" for s in source_records),
            "retrospective_qa":retrospective,"start_utc":start.isoformat(),"end_utc":end.isoformat(),"scan_utc":scan.isoformat(),
            "email_sent":False,"private_state_used":False,"schedule_changed":False}
