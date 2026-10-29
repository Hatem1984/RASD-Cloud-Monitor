"""Non-destructive Chrome owner sign-in usability acceptance on local MA'AL only.

Reads authorized test credentials on the owner's Windows machine; never prints
or stores a password, and never calls approve, execute or a production endpoint.
Browser screenshots use only guest / harmless authenticated status.
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT="http://127.0.0.1:52344/"
OWNER=Path("E:/MAAL/02_PRIVATE_OWNER/MAAL_GATE_F_TEST_CREDENTIALS_20261027.txt")
OUTPUT=Path("E:/MAAL/03_REPORTS_AND_REVIEW/MAAL_COMPETITION_MVP_20261028/login_ux")
OUTPUT.mkdir(parents=True,exist_ok=True)

def account():
    # Local file is read in memory, never attached to CI / log / report files.
    entries=[]
    current={}
    for line in OWNER.read_text(encoding="utf-8-sig").splitlines():
        if ":" not in line:continue
        k,v=line.split(":",1);k=k.strip()
        if k=="Login":
            if current:entries.append(current)
            current={"login":v.strip()}
        elif k in {"Password","Role"}: current[k.lower()]=v.strip()
    if current:entries.append(current)
    valid=[r for r in entries if r.get("role","").upper()=="OWNER"
           and r.get("login") and r.get("password")]
    # The private fixture contains more than one OWNER test tenant. Select
    # only the principal who already owns the existing Gate H draft.
    import sqlite3
    db=sqlite3.connect(
        "file:E:/MAAL/04_HISTORICAL_QA/MAAL_GATE_H_E2E_20261027/operator.sqlite?mode=ro",
        uri=True)
    try:
        actual=db.execute(
            "SELECT login FROM demo_task_owners WHERE draft_id=?",
            ("425b5640-c656-4838-98dc-f2ee477f74da",)).fetchone()
    finally: db.close()
    selected=[r for r in valid if actual and r["login"]==actual[0]]
    if len(selected)!=1:raise RuntimeError("owner_for_original_draft_not_found")
    return selected[0]["login"],selected[0]["password"]

def wait_page(page):
    page.goto(ROOT,wait_until="domcontentloaded",timeout=15000)
    page.wait_for_function(
        "document.querySelectorAll('#agent-journey-steps .customer-answer').length === 6",timeout=12000)
    assert page.locator("#account-entry").is_visible()
    assert page.locator("#account-entry-label").inner_text()=="تسجيل الدخول"
    assert page.locator("#header-logout").is_hidden()
    assert page.locator("#operator-login").count()==1
    assert page.locator("#operator-login").is_hidden()

def open_modal(page):
    page.locator("#account-entry").click()
    assert page.locator("#login-dialog").evaluate("(x)=>x.open") is True
    assert page.locator("#operator-login").is_visible()
    assert page.locator("#operator-username").evaluate("(x)=>x===document.activeElement")
    assert page.locator("#operator-password").get_attribute("type")=="password"
    page.locator("#login-reveal-password").check()
    assert page.locator("#operator-password").get_attribute("type")=="text"
    page.locator("#login-reveal-password").uncheck()
    assert page.locator("#operator-password").get_attribute("type")=="password"

def run():
    errors=[]
    username,password=account()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        desktop=browser.new_context(viewport={"width":1440,"height":900},device_scale_factor=1)
        page=desktop.new_page();page.on("pageerror",lambda e:errors.append(str(e)))
        wait_page(page)
        page.screenshot(path=str(OUTPUT/"desktop-header-guest.png"),full_page=False)
        open_modal(page)
        page.screenshot(path=str(OUTPUT/"desktop-login-modal.png"),full_page=False)
        page.locator("#operator-username").fill("nonexistent-for-ux-qa")
        page.locator("#operator-password").fill("purposefully-invalid")
        page.locator("#login-submit").click()
        page.locator("#login-feedback").wait_for(state="visible")
        assert page.locator("#login-dialog").evaluate("(x)=>x.open")
        assert page.locator("#account-entry-label").inner_text()=="تسجيل الدخول"
        assert page.locator("#operator-password").input_value()==""
        # Valid owner login, no task approval or execution.
        page.locator("#operator-username").fill(username)
        page.locator("#operator-password").fill(password)
        page.locator("#login-submit").click()
        page.locator("#login-dialog").wait_for(state="hidden",timeout=12000)
        assert page.locator("#account-entry-label").inner_text().startswith("قراراتي")
        assert page.locator("#header-logout").is_visible()
        assert page.locator("#operator-authenticated").is_visible()
        assert page.locator("#advanced-operator-review").evaluate("(x)=>x.open")
        assert page.locator("#view-decisions").is_visible()
        assert page.locator("#operator-drafts .operator-draft-item").count()>=1
        current=page.evaluate("""async()=>await(await fetch('/api/operator/state')).json()""")
        assert current["role"]=="OWNER"
        assert any(d["draft_id"]=="425b5640-c656-4838-98dc-f2ee477f74da"
                   and d["state"]=="DRAFT" and not d.get("task_id")
                   for d in current["drafts"])
        page.screenshot(path=str(OUTPUT/"desktop-after-login.png"),full_page=False)
        # Verify session survives harmless page refresh.
        page.reload(wait_until="domcontentloaded")
        page.locator("#header-logout").wait_for(state="visible",timeout=12000)
        page.locator("#header-logout").click()
        page.locator("#header-logout").wait_for(state="hidden",timeout=10000)
        assert page.locator("#account-entry-label").inner_text()=="تسجيل الدخول"
        assert page.locator("#operator-authenticated").is_hidden()
        assert page.evaluate("""async()=>{
          const r=await fetch('/api/operator/state');return r.status}""")==401
        desktop.close()
        mobile=browser.new_context(viewport={"width":390,"height":844},
                                   device_scale_factor=1,is_mobile=True,has_touch=True)
        m=mobile.new_page();m.on("pageerror",lambda e:errors.append(str(e)))
        wait_page(m)
        button=m.locator("#account-entry")
        rect=button.bounding_box()
        assert rect is not None and rect["x"]>=0 and rect["x"]+rect["width"]<=392
        m.screenshot(path=str(OUTPUT/"mobile-header-guest.png"),full_page=False)
        open_modal(m)
        m.screenshot(path=str(OUTPUT/"mobile-login-modal.png"),full_page=False)
        assert m.locator("#login-dialog").evaluate(
            "(x)=>x.getBoundingClientRect().width <= window.innerWidth-10")
        m.keyboard.press("Escape")
        assert not m.locator("#login-dialog").evaluate("(x)=>x.open")
        # A real local OWNER test login must remain easy on narrow phones.
        m.locator("#account-entry").click()
        m.locator("#operator-username").fill(username)
        m.locator("#operator-password").fill(password)
        m.locator("#login-submit").click()
        m.locator("#login-dialog").wait_for(state="hidden",timeout=12000)
        assert m.locator("#account-entry-label").inner_text().startswith("قراراتي")
        assert m.locator("#header-logout").is_visible()
        assert m.locator("#view-decisions").is_visible()
        header=m.locator("#account-entry").bounding_box()
        assert header is not None and header["x"]+header["width"]<=392
        m.screenshot(path=str(OUTPUT/"mobile-after-login.png"),full_page=False)
        m.locator("#header-logout").click()
        m.locator("#header-logout").wait_for(state="hidden",timeout=10000)
        mobile.close()
        browser.close()
    assert not errors,errors
    receipt={"status":"LOGIN_USABILITY_ACCEPTANCE_PASS",
      "desktop_authentic_owner_login":True,"password_exposed":False,
      "original_draft_still_pending":True,"no_approval_or_task_execution":True,
      "mobile_header_login_visible":True,"mobile_owner_login_logout":True,"modal_keyboard_escape":True,
      "wrong_password_error_handled":True,"refresh_session_persists":True,
      "logout_clears_session":True,"javascript_errors":[]}
    (OUTPUT/"ux_acceptance.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt))

if __name__=="__main__":run()
