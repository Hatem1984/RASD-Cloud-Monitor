"""Actual Chromium client journey for manual RASD demo, NO MAIL, NO NETWORK FEEDS.

Run only in an isolated Actions job with playwright chromium installed.
Produces solely fictional DEMO Word samples and UI screenshots.
"""
import hashlib
import json
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from docx import Document
from playwright.sync_api import sync_playwright

from rasd_app.core import Store
from rasd_app.server import App


def checked_report(report, expected_tenant):
    settings=json.loads(report["settings"])
    assert settings["name"]==expected_tenant
    manifest=json.loads(report["manifest"])
    doc=Document(report["file_path"])
    links=[]
    for h in doc.element.body.xpath(".//w:hyperlink"):
        links.append(doc.part.rels[h.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")].target_ref)
    imgs=[hashlib.sha256(doc.part.related_parts[
            x.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")].blob).hexdigest()
          for x in doc.element.body.xpath(".//a:blip")]
    assert [m["url"] for m in manifest]==links,(manifest,links)
    assert [m["image_sha"] for m in manifest]==imgs,(manifest,imgs)
    assert hashlib.sha256(Path(report["file_path"]).read_bytes()).hexdigest()==report["file_sha"]
    assert all(m["image_state"]=="demo_illustration" for m in manifest)
    return len(manifest)


def login(page,url,email,password):
    page.goto(url,wait_until="domcontentloaded")
    page.locator('#login-form input[name="email"]').fill(email)
    page.locator('#login-form input[name="password"]').fill(password)
    page.locator('#login-form button[type="submit"]').click()
    page.locator("#shell:not(.hidden)").wait_for(timeout=10000)


def wait_scan(page):
    page.get_by_text("نتيجة الفحص اليدوي").wait_for(timeout=15000)
    page.locator("#dialog-body .summary-grid").wait_for()
    text=page.locator("#dialog-body").inner_text()
    page.locator("#close-dialog").click()
    return text


def review_all(page,expected):
    page.locator('button[data-tab="articles"]').click()
    page.locator('tr [data-action="article-detail"]').first.wait_for(timeout=7000)
    cards=page.locator('tr [data-action="article-detail"]')
    ids=cards.evaluate_all("(nodes) => nodes.map(n => n.dataset.id)")
    assert len(ids)==expected,(expected,ids)
    for aid in ids:
        # Select BY STABLE ARTICLE ID, not the first row after async render.
        button=page.locator('tr [data-action="article-detail"][data-id="'+aid+'"]')
        button.wait_for()
        button.click()
        page.locator("#review-form").wait_for()
        page.locator('#review-form button[value="approved"]').click()
        page.locator("#dialog").wait_for(state="hidden", timeout=10000)
    page.locator("#filter-state").select_option("pending")
    page.locator('button[data-action="filter-articles"]').click()
    page.get_by_text("لا توجد أخبار بهذه الفلاتر").wait_for(timeout=10000)


def report_from_browser(page,out:Path,prefix):
    page.locator('button[data-tab="reports"]').click()
    page.locator('[data-action="create-report"]').click()
    page.locator("#report-form").wait_for()
    if prefix=="RASD_DEMO_UNIVERSITY":
        order=page.locator("#report-form .report-row input[name='items']")
        before=order.evaluate_all("(nodes)=>nodes.map(x=>x.value)")
        assert len(before)==4
        page.locator("#report-form .report-row [data-move='up']").nth(1).click()
        after=order.evaluate_all("(nodes)=>nodes.map(x=>x.value)")
        assert after[0]==before[1] and after[1]==before[0]
    page.locator("#report-form button.primary").click()
    page.locator("#dialog-body a.primary").wait_for(timeout=12000)
    assert "فتح رابط الناشر الأصلي" in page.locator("#dialog-body").inner_text()
    with page.expect_download(timeout=12000) as download:
        page.locator("#dialog-body a.primary").click()
    target=out/(prefix+".docx")
    download.value.save_as(target)
    page.locator("#close-dialog").click()
    page.locator('tr [data-action="report-detail"]').first.wait_for()
    return target


def main():
    output=Path(sys.argv[1] if len(sys.argv)>1 else "demo-output")
    output.mkdir(parents=True,exist_ok=True)
    errors=[]
    with tempfile.TemporaryDirectory() as temp:
        app=App(Path(temp)/"server")
        password="DEMO-LOCAL-OWNER-2026!"
        info=app.store.seed_demo(owner_password=password)
        assert info is not None
        uni=info["tenants"]["university"]
        food=info["tenants"]["foods"]
        empty=info["tenants"]["empty"]
        app.store.add_member(food,"food-analyst@example.test","FOOD-ANALYST-LOCAL-2026","analyst")
        srv=ThreadingHTTPServer(("127.0.0.1",0),app.handler())
        thread=threading.Thread(target=srv.serve_forever,daemon=True)
        thread.start()
        url="http://127.0.0.1:"+str(srv.server_port)
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
                ctx=browser.new_context(accept_downloads=True,viewport={"width":1365,"height":860},
                                         locale="ar-EG",device_scale_factor=1)
                page=ctx.new_page()
                page.on("pageerror",lambda err:errors.append(str(err)))
                login(page,url,info["owner_email"],password)
                page.locator("#tenant-switch").select_option(uni)
                page.locator('[data-action="start-scan"]').first.click()
                result=wait_scan(page)
                assert "مصدر متعذر" in result and "4" in result
                page.screenshot(path=str(output/"01-university-dashboard.png"),full_page=True)
                # A dashboard EVENT means a group, not a publisher URL.
                # Prove 3 independent publisher links behind a single event.
                page.locator('[data-action="event-groups"]').click()
                page.get_by_text("الأحداث والتغطيات").wait_for()
                assert "3 روابط تغطية" in page.locator("#dialog-body").inner_text()
                page.locator('[data-action="event-filter"]').first.click()
                page.locator('tr [data-action="article-detail"]').first.wait_for()
                assert page.locator('tr [data-action="article-detail"]').count()==3
                page.locator('[data-action="clear-articles"]').first.click()
                page.locator('tr [data-action="article-detail"]').first.wait_for()
                assert page.locator('tr [data-action="article-detail"]').count()==4
                review_all(page,4)
                page.screenshot(path=str(output/"02-university-news.png"),full_page=True)
                uni_doc=report_from_browser(page,output,"RASD_DEMO_UNIVERSITY")
                page.screenshot(path=str(output/"03-university-report.png"),full_page=True)
                assert uni_doc.stat().st_size>10000
                uni_rows=app.store.list_reports(uni)
                assert len(uni_rows)==1
                uni_count=checked_report(uni_rows[0],"جامعة الريادة — تجريبي")
                assert uni_count==4

                page.locator("#tenant-switch").select_option(food)
                page.locator('[data-action="start-scan"]').first.click()
                result=wait_scan(page)
                assert "3" in result and "مصادر نجحت" in result
                review_all(page,3)
                food_doc=report_from_browser(page,output,"RASD_DEMO_FOOD")
                page.screenshot(path=str(output/"04-food-report.png"),full_page=True)
                food_rows=app.store.list_reports(food)
                assert len(food_rows)==1
                food_count=checked_report(food_rows[0],"شركة الغذاء — تجريبي")
                assert food_count==3
                assert all("foods" in a["url"] for a in app.store.articles(food))
                assert all("university" in a["url"] for a in app.store.articles(uni))

                # Genuine empty tenant: zero accepted articles but UI stays useful.
                page.locator("#tenant-switch").select_option(empty)
                page.locator('[data-action="start-scan"]').first.click()
                zero=wait_scan(page)
                assert "0" in zero
                page.screenshot(path=str(output/"05-empty-tenant.png"),full_page=True)

                # Newly created tenant using the same browser controls.
                page.locator('[data-action="new-tenant"]').first.click()
                page.locator('#new-tenant-form input[name="name"]').fill("مركز الأبحاث — جديد")
                page.locator("#new-tenant-form button.primary").click()
                # The login panel also owns a hidden h1. Wait for the
                # actual new tenant identity instead of the first h1 in DOM.
                page.locator("#current-name").get_by_text("مركز الأبحاث — جديد").wait_for(timeout=12000)
                page.screenshot(path=str(output/"06-new-tenant-settings.png"),full_page=True)
                new_tenant=next(x["id"] for x in app.store.memberships(
                    app.store.session_user(next(iter([]),""))) if x["name"]=="never") if False else None
                # Login as a separate food analyst. Their tenant selector must
                # not contain any of the other tenants, even if a URL is guessed.
                second=browser.new_context(accept_downloads=False)
                page2=second.new_page()
                page2.on("pageerror",lambda err:errors.append(str(err)))
                login(page2,url,"food-analyst@example.test","FOOD-ANALYST-LOCAL-2026")
                options=page2.locator("#tenant-switch option").all_text_contents()
                assert options==["شركة الغذاء — تجريبي"],options
                forbidden=page2.request.get(url+"/api/tenants/"+uni+"/reports/"+uni_rows[0]["id"]+"/download")
                # Browser API context is separate from page cookies, so use
                # actual page fetch with credentials to prove the direct link ACL.
                assert page2.evaluate("""async url => {
                    const r=await fetch(url,{credentials:'same-origin'});
                    return r.status;
                }""",url+"/api/tenants/"+uni+"/reports/"+uni_rows[0]["id"]+"/download")==403
                page2.screenshot(path=str(output/"07-food-analyst-isolation.png"),full_page=True)
                mobile=browser.new_context(viewport={"width":390,"height":844},device_scale_factor=1)
                mob=mobile.new_page()
                mob.on("pageerror",lambda err:errors.append(str(err)))
                login(mob,url,info["owner_email"],password)
                mob.screenshot(path=str(output/"08-mobile-dashboard.png"),full_page=True)
                assert mob.evaluate("document.documentElement.scrollWidth <= window.innerWidth+2")
                assert not errors,errors
                report={"success":True,"checks":["browser owner login","source partial success","4 university coverages",
                    "3 food coverages","review via browser","Word download for both tenants",
                    "Word URLs/image JPEG SHA exact","new tenant creation","empty tenant",
                    "other-tenant direct Word URL forbidden","mobile no horizontal scroll"],
                    "university":{"coverages":uni_count,"word_sha":hashlib.sha256(uni_doc.read_bytes()).hexdigest()},
                    "food":{"coverages":food_count,"word_sha":hashlib.sha256(food_doc.read_bytes()).hexdigest()},
                    "screenshots":len(list(output.glob("*.png"))),
                    "smtp_sent":False,"production_ledger_changed":False,"data_kind":"SYNTHETIC DEMO"}
                (output/"BROWSER_ACCEPTANCE.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
                print("RASD_BROWSER_REAL_CHROMIUM_ACCEPTANCE="+json.dumps(report,ensure_ascii=False),flush=True)
                browser.close()
        finally:
            srv.shutdown()
            srv.server_close()


if __name__=="__main__":
    main()
