"""Read-only visual competition acceptance on owner's localhost; no consent spoofing.

Uses current existing branded V0.3, actual Gate E JPEG, fresh recorded Qwen3
receipt. Does NOT approve, execute, send email or claim full end-to-end.
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT = "http://127.0.0.1:52344/"
OUTPUT = Path("E:/MAAL/03_REPORTS_AND_REVIEW/MAAL_COMPETITION_MVP_20261028")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    console_errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(
            viewport={"width":1366,"height":800},device_scale_factor=1,
            record_video_dir=str(OUTPUT/"partial_readonly_video"))
        page=context.new_page()
        page.on("pageerror",lambda e:console_errors.append(str(e)))
        response=page.goto(ROOT,wait_until="domcontentloaded",timeout=20000)
        assert response.status==200
        page.wait_for_function(
            "document.querySelectorAll('#agent-journey-steps .customer-answer').length===6",
            timeout=12000)
        result=page.evaluate("""async()=>{let r=await fetch('/api/agent-journey',{cache:'no-store'});return await r.json()}""")
        assert result["evidence"]["status"]=="VERIFIED_ORIGINAL_PAGE"
        assert result["ai"]["run_id"].startswith("maal-g3-")
        assert result["approval"]["authenticated"] is False
        assert result["approval"]["drafts"]==[]
        assert result["operations"]["external_actions"] is False
        page.screenshot(path=str(OUTPUT/"competition-overview-desktop.png"),full_page=True)
        # Only navigate to the existing owner gate; never approve as the owner.
        page.locator("#agent-journey-review").click()
        assert page.locator("#advanced-operator-review").evaluate("(x)=>x.open")
        assert page.locator("#operator-guest-demo").is_visible()
        page.screenshot(path=str(OUTPUT/"competition-owner-gate-pending.png"),full_page=True)
        mobile=browser.new_context(viewport={"width":390,"height":844},
                                  device_scale_factor=1,is_mobile=True,
                                  has_touch=True)
        mp=mobile.new_page()
        mp.goto(ROOT,wait_until="domcontentloaded",timeout=20000)
        mp.wait_for_function(
            "document.querySelectorAll('#agent-journey-steps .customer-answer').length===6",
            timeout=12000)
        mp.screenshot(path=str(OUTPUT/"competition-overview-mobile.png"),full_page=True)
        mobile.close()
        assert not console_errors, console_errors
        context.close()
        browser.close()
    receipt={
        "status":"READ_ONLY_BROWSER_ACCEPTANCE_PASS",
        "live_source":False,"owner_approval_performed":False,
        "new_action_executed":False,"video_scope":"partial_readonly_not_full_e2e",
        "evidence_id":result["evidence"]["id"],
        "evidence_sha256":result["evidence"]["jpeg_sha256"],
        "model_run_id":result["ai"]["run_id"],
        "screenshots":["competition-overview-desktop.png",
                       "competition-owner-gate-pending.png",
                       "competition-overview-mobile.png"],
        "page_errors":console_errors,
    }
    (OUTPUT/"read_only_browser_acceptance.json").write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=="__main__":
    main()
