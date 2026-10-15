"""Gate 26: true full RASD proof engine under a *source-limited* opt-in profile.

This is the real cloud_proof_report path (all eligible articles must pass).
Not a synthetic screenshot, not Gmail and not the broader production profile.
Plaintext evidence never leaves the transient runner; use encrypted packing.
"""
from __future__ import annotations
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from cloud_proof_report import build_proof_report

CONFIGS={"shorouk":"sources_shorouk.json"}  # no arbitrary user input
def verify_embedded_evidence(word:Path,result:dict)->bool:
    """Inspect DOCX media bytes against exact capture digest values."""
    if result.get("status")!="READY" or result.get("screenshots_verified",0)<1:
        return False
    entries=result.get("entries",[])
    expected=sorted(row["sha256"] for row in entries if row["status"]=="verified")
    if len(expected)!=result["articles"]:
        return False
    with zipfile.ZipFile(word) as archive:
        if archive.testzip() is not None:
            return False
        image_digests=sorted(hashlib.sha256(archive.read(name)).hexdigest()
            for name in archive.namelist() if name.startswith("word/media/")
            and name.lower().endswith((".jpg",".jpeg")))
        body=archive.read("word/document.xml").decode("utf-8")
        relationships=archive.read("word/_rels/document.xml.rels").decode("utf-8")
    return (image_digests==expected and "تقرير مراجعة مصدر الشروق" in body
            and "www.shorouknews.com/news/view.aspx" in relationships)

def run(output_dir:Path,profile:str="shorouk",**kwargs)->dict:
    if profile not in CONFIGS: raise ValueError("unapproved_source_profile")
    output_dir.mkdir(parents=True,exist_ok=True)
    result=build_proof_report(Path(CONFIGS[profile]),output_dir,**kwargs)
    result={**result,"source_scope":"single_reviewed_shorouk_feed_only",
            "production_daily_approved":False,
            "mail_sent":False,"scheduler_enabled":False}
    if result.get("status")=="READY":
        day=next(output_dir.glob("RASD-Daily-*.docx"),None)
        if day is None or not verify_embedded_evidence(day,result):
            result["status"]="HOLD"
            result["failure"]="word_image_integrity_or_scope_failed"
            result["word_created"]=False
            if day:day.unlink(missing_ok=True)
        else:
            review_path=output_dir/("RASD-Verified-Shorouk-Review-"+day.name[11:])
            day.rename(review_path)
            result["review_word"]=review_path.name
            result["status"]="REVIEW_READY"
            result["word_created"]=True
    # Retain only sanitized evidence status for public workflow logs.
    summary={k:v for k,v in result.items() if k not in ("entries",)}
    (output_dir/"gate26-review-audit.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return summary

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--outdir",type=Path,default=Path("gate26-proof"))
    p.add_argument("--profile",choices=list(CONFIGS),default="shorouk")
    args=p.parse_args()
    try:
        result=run(args.outdir,args.profile)
        print(json.dumps(result,ensure_ascii=False),flush=True)
        if result["status"]!="REVIEW_READY":
            print("::warning::RASD G26 real Word remains HOLD; no complete genuine evidence")
    except Exception:
        print("rasd_g26_failed_closed",flush=True)
        raise SystemExit(1) from None
