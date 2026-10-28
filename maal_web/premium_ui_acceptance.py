"""Visual acceptance of existing MA'AL V0.3 after approved-brand UX refactor.

Read-only Playwright at 1440/820/390/320. Never triggers approval or execution.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
import json

OUT=Path("E:/MAAL/03_REPORTS_AND_REVIEW/MAAL_COMPETITION_MVP_20261028/premium_ui_qa")
BASE="http://127.0.0.1:52344"
def navigate(page,width,view):
    if width<=1040:
        toggle=page.locator("#premium-navigation-toggle")
        toggle.click()
        expect(toggle).to_have_attribute("aria-expanded","true")
    page.locator('.nav-link[data-view="'+view+'"]').click()
    if width<=1040:
        expect(page.locator("#premium-navigation-toggle")).to_have_attribute("aria-expanded","false")
def run():
    OUT.mkdir(parents=True,exist_ok=True)
    failures=[];rows=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        for width in (1440,820,390,320):
            ctx=browser.new_context(viewport={"width":width,"height":900},reduced_motion="reduce")
            page=ctx.new_page();page.on("pageerror",lambda e:failures.append(str(e)))
            assert page.goto(BASE,wait_until="domcontentloaded",timeout=20000).status==200
            try:
                expect(page.locator("#premium-source-count")).to_have_text("3",timeout=15000)
            except AssertionError:
                print("SOURCE_LOAD_HOLD",width,"STATUS",
                      page.locator("#premium-stage-statement").inner_text(),
                      "CLIENT_ERRORS",failures,flush=True)
                page.screenshot(path=str(OUT/f"load_hold_{width}.png"))
                raise
            assert page.locator("#premium-executive").is_visible()
            assert page.locator("#premium-hold-count").inner_text()=="3"
            assert page.locator(".nav-link").count()==7
            assert page.locator("#account-entry").is_visible()
            if width<=1040:
                toggle=page.locator("#premium-navigation-toggle")
                assert toggle.is_visible()
                expect(toggle).to_have_attribute("aria-expanded","false")
                toggle.focus()
                page.keyboard.press("Enter")
                expect(toggle).to_have_attribute("aria-expanded","true")
                assert page.locator(".nav-link").first.is_visible()
                page.keyboard.press("Escape")
                expect(toggle).to_have_attribute("aria-expanded","false")
                assert toggle.evaluate("(el)=>document.activeElement===el")
            else:
                assert not page.locator("#premium-navigation-toggle").is_visible()
            page.screenshot(path=str(OUT/f"after_{width}.png"),animations="disabled")
            page.locator("#premium-go-signals").click()
            page.locator("#new-signal-choices .new-signal-choice").first.wait_for()
            assert page.locator("#new-signal-choices .new-signal-choice").count()==3
            page.screenshot(path=str(OUT/f"signals_{width}.png"),animations="disabled")
            navigate(page,width,"impact")
            page.locator("#paired-ai-benchmark").evaluate("(el)=>el.open=true")
            page.locator("#paired-benchmark-list button").first.wait_for(timeout=10000)
            assert page.locator("#paired-benchmark-list button").count()>=6
            page.locator("#paired-benchmark-list button").first.click()
            page.screenshot(path=str(OUT/f"analysis_{width}.png"),animations="disabled")
            navigate(page,width,"decisions")
            page.locator("#account-entry").click()
            assert page.locator("#login-dialog").is_visible()
            assert page.locator("#operator-username").is_visible()
            assert page.locator("#login-dialog").get_attribute("aria-labelledby")=="login-dialog-title"
            page.locator("#login-close").click()
            assert not page.locator("#login-dialog").is_visible()
            for view in ("overview","monitor","impact","decisions","operations","report","evidence"):
                navigate(page,width,view)
                assert page.locator("#view-"+view).is_visible()
            overflow=page.evaluate("document.documentElement.scrollWidth-innerWidth")
            rows.append({"width":width,"overflow_px":overflow,"nav":7,"sources":3})
            ctx.close()
        browser.close()
    result={"status":"PASS" if not failures and all(x["overflow_px"]<=2 for x in rows) else "HOLD",
            "screenshots":str(OUT),"results":rows,"page_errors":failures,
            "no_actions_executed":True}
    (OUT/"acceptance.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(result,ensure_ascii=False))
    if result["status"]!="PASS":raise RuntimeError("premium visual QA hold")
if __name__=="__main__":run()
