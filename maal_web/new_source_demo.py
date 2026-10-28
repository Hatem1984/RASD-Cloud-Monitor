"""Uncut owner-local read-only walkthrough from a NEW official case to draft.

Uses the test OWNER session only for display; NEVER approves or executes.
Browser records one continuous unedited video, while the saved Qwen receipt is
clearly a past REAL local inference, not a live model stream in the recording.
"""
from pathlib import Path
from time import perf_counter
import sqlite3
import json
import hashlib

from playwright.sync_api import sync_playwright
from maal_web.prepare_new_source_draft import owner_account,DB,OLD,FPT

BASE="http://127.0.0.1:52344"
OUT=Path("E:/MAAL/03_REPORTS_AND_REVIEW/MAAL_COMPETITION_MVP_20261028/new_source_demo")
DRAFT="ea78e338-d2a5-4c5e-a5cc-cbd296017c2c"

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect("file:"+str(DB).replace("\\","/")+"?mode=ro",uri=True) as db:
        previous=db.execute("SELECT state FROM drafts WHERE draft_id=?",(OLD,)).fetchone()
        original_count=db.execute("SELECT count(*) FROM tasks WHERE draft_id=?",(OLD,)).fetchone()[0]
        owner=db.execute("SELECT login FROM demo_task_owners WHERE draft_id=?",(OLD,)).fetchone()[0]
        new=db.execute("SELECT state,evidence_id FROM drafts WHERE draft_id=?",(DRAFT,)).fetchone()
        new_count=db.execute("SELECT count(*) FROM tasks WHERE draft_id=?",(DRAFT,)).fetchone()[0]
    assert previous[0]=="EXECUTED" and original_count==1
    assert new==("DRAFT",FPT) and new_count==0
    creds=owner_account(owner)
    errors=[];measurements={}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(
            viewport={"width":1366,"height":860},device_scale_factor=1,
            record_video_dir=str(OUT/"continuous_readonly_video"))
        # Sign in to the existing Gate H test OWNER API BEFORE creating the
        # recording page. No password typed or visible on tape.
        start=perf_counter()
        response=context.request.post(
            BASE+"/api/operator/login",
            headers={"Origin":BASE,"Content-Type":"application/json"},
            data=json.dumps({"login":creds["Login"],"password":creds["Password"]}))
        if response.status!=200:raise RuntimeError("owner_local_auth_failed")
        measurements["owner_local_login_seconds"]=round(perf_counter()-start,3)
        page=context.new_page()
        page.on("pageerror",lambda e:errors.append(str(e)))
        start=perf_counter()
        page.goto(BASE,wait_until="domcontentloaded",timeout=20000)
        page.locator(".new-signal-choice").first.wait_for(timeout=13000)
        measurements["page_and_sources_ready_seconds"]=round(perf_counter()-start,3)
        assert page.locator(".new-signal-choice").count()==3
        page.wait_for_timeout(3000)
        start=perf_counter()
        fpt=page.locator('.new-signal-choice[data-evidence="'+FPT+'"]')
        fpt.click()
        page.locator("#new-signal-evidence h3").wait_for(timeout=5000)
        photo=page.locator(".new-signal-proof")
        assert photo.is_visible()
        assert photo.evaluate("(el)=>el.complete && el.naturalWidth>500")
        assert page.locator(".new-signal-evidence a").get_attribute("href").startswith("https://itida.gov.eg/")
        assert page.locator("#new-signal-draft").is_visible()
        assert "الشركة الافتراضية" in page.locator("#new-signal-analysis").inner_text()
        measurements["new_source_analysis_visible_seconds"]=round(perf_counter()-start,3)
        page.screenshot(path=str(OUT/"new_real_fpt_evidence_and_analysis.png"),full_page=True)
        page.locator("#new-signal-analysis").scroll_into_view_if_needed()
        page.wait_for_timeout(7000)
        page.locator("#new-signal-draft").scroll_into_view_if_needed()
        page.wait_for_timeout(4000)
        # Existing owner draft is retrieved from authenticated Gate H DB.
        page.locator("#new-signal-draft").click()
        page.locator("#operator-authenticated").wait_for(state="visible",timeout=9000)
        assert page.locator("#view-decisions").is_visible()
        target=page.locator('.operator-draft-item[data-draft-id="'+DRAFT+'"]')
        target.wait_for(state="visible",timeout=9000)
        assert target.get_attribute("aria-pressed")=="true"
        assert page.locator("#operator-approve").is_disabled()  # Editorial HOLD enforced
        assert page.locator("#operator-reject").is_enabled()  # Human refusal allowed
        # This is the HUMAN STEP: intentionally DO NOT click approve/execute.
        page.screenshot(path=str(OUT/"new_pending_owner_draft_no_approval.png"),full_page=False)
        page.wait_for_timeout(6500)
        assert not errors,errors
        video=page.video
        context.close()
        path=video.path()
        browser.close()
    with sqlite3.connect("file:"+str(DB).replace("\\","/")+"?mode=ro",uri=True) as db:
        old_after=db.execute("SELECT state FROM drafts WHERE draft_id=?",(OLD,)).fetchone()[0]
        new_after=db.execute("SELECT state FROM drafts WHERE draft_id=?",(DRAFT,)).fetchone()[0]
        task_count=db.execute("SELECT count(*) FROM tasks WHERE draft_id=?",(DRAFT,)).fetchone()[0]
    assert old_after=="EXECUTED" and new_after=="DRAFT" and task_count==0
    movie=Path(path)
    receipt={
        "status":"CONTINUOUS_OWNER_REVIEW_DEMO_PASS",
        "video_scope":"SAVED_REAL_QWEN_INFERENCE_REPLAYED_FROM_VERIFIED_RECEIPT__NO_LIVE_INFERENCE_IN_TAPE",
        "video_path":str(movie),
        "video_sha256":hashlib.sha256(movie.read_bytes()).hexdigest(),
        "source_evidence_id":FPT,
        "new_owner_draft":DRAFT,
        "old_gate_h_unchanged":True,
        "new_approval_performed":False,"new_task_executed":False,
        "measurements":measurements,
        "manual_baseline_seconds":None,"ROI_PERCENT":None,
        "browser_page_errors":errors,
    }
    (OUT/"walkthrough_acceptance.json").write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=="__main__":
    main()
