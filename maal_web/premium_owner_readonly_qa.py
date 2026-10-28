"""Read-only OWNER V0.3 visual acceptance; no approvals or task mutation."""
import json,sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from maal_web.prepare_new_source_draft import DB,OLD,owner_account

BASE="http://127.0.0.1:52344"
OUT=Path("E:/MAAL/03_REPORTS_AND_REVIEW/MAAL_COMPETITION_MVP_20261028/premium_ui_qa")
def state():
    db=sqlite3.connect("file:"+str(DB).replace("\\","/")+"?mode=ro",uri=True)
    try:
        old=db.execute("SELECT login FROM demo_task_owners WHERE draft_id=?",(OLD,)).fetchone()[0]
        rows=db.execute("SELECT draft_id,state FROM drafts ORDER BY draft_id").fetchall()
        tasks=db.execute("SELECT draft_id,count(*) FROM tasks GROUP BY draft_id").fetchall()
        audit=db.execute("SELECT count(*) FROM audit").fetchone()[0]
        return old,rows,tasks,audit
    finally:db.close()
def main():
    initial=state();user=owner_account(initial[0])
    OUT.mkdir(parents=True,exist_ok=True)
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        ctx=browser.new_context(viewport={"width":1440,"height":900})
        login=ctx.request.post(BASE+"/api/operator/login",
            headers={"Origin":BASE,"Content-Type":"application/json"},
            data=json.dumps({"login":user["Login"],"password":user["Password"]}))
        assert login.status==200
        page=ctx.new_page();page.on("pageerror",lambda e:errors.append(str(e)))
        page.goto(BASE,wait_until="domcontentloaded")
        expect(page.locator("#premium-owner-count")).to_have_text("2",timeout=10000)
        page.locator('.nav-link[data-view="decisions"]').click()
        page.locator("#premium-owner-console").evaluate("(e)=>e.open=true")
        assert page.locator("#premium-owner-console").is_visible()
        assert page.locator("#advanced-operator-review").get_attribute("open") is not None
        draft=page.locator('.operator-draft-item[data-draft-id="ea78e338-d2a5-4c5e-a5cc-cbd296017c2c"]')
        draft.wait_for(timeout=10000);draft.click()
        assert page.locator("#operator-approve").is_disabled()
        assert page.locator("#operator-execute").is_disabled()
        assert page.locator("#operator-reject").is_enabled()
        page.screenshot(path=str(OUT/"decisions_owner_after.png"),animations="disabled")
        page.locator('.nav-link[data-view="operations"]').click()
        assert page.locator(".premium-event").count()>=5
        page.screenshot(path=str(OUT/"audit_owner_after.png"),animations="disabled")
        ctx.close();browser.close()
    assert not errors,errors
    assert state()==initial,"owner_tasks_or_audit_changed_during_visual_QA"
    print(json.dumps({"status":"OWNER_REVIEW_READONLY_PASS",
         "existing_drafts":2,"existing_audit_events":initial[3],
         "fpt_approval_blocked":True,"reject_available":True,
         "new_task_executed":False,"db_unchanged":True,
         "browser_errors":errors},ensure_ascii=False))
if __name__=="__main__":main()
