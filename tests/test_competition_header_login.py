"""No-browser production regression contract for the MA'AL login UX.

Does not read credentials, mutate the Gate H database or reach any live API.
"""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]/"maal_web"

class Elements(HTMLParser):
    def __init__(self):
        super().__init__();self.ids={};self.tags={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);ident=a.get("id")
        if ident:
            self.ids[ident]=self.ids.get(ident,0)+1
            self.tags[ident]=tag

class HeaderLoginContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page=(ROOT/"index.html").read_text("utf8")
        cls.js=(ROOT/"operator.js").read_text("utf8")
        cls.style=(ROOT/"style.css").read_text("utf8")
        cls.dom=Elements();cls.dom.feed(cls.page)

    def test_one_form_dialog_and_header_entry(self):
        for name,tag in {
            "account-entry":"button","account-entry-label":"span",
            "header-logout":"button","login-dialog":"dialog",
            "operator-login":"form","operator-username":"input",
            "operator-password":"input","login-feedback":"div",
            "login-close":"button","login-submit":"button"}.items():
            with self.subTest(name=name):
                self.assertEqual(self.dom.ids.get(name),1)
                self.assertEqual(self.dom.tags[name],tag)
        self.assertLess(self.page.index('id="account-entry"'),
                        self.page.index('id="view-overview"'))
        self.assertEqual(self.page.count('id="operator-login"'),1)

    def test_secure_password_and_semantic_login_dialog(self):
        self.assertIn('type="password" autocomplete="current-password"',self.page)
        self.assertIn('aria-labelledby="login-dialog-title"',self.page)
        self.assertIn('id="login-feedback" class="login-feedback" role="status"',self.page)
        self.assertIn("dialog.showModal()",self.js)
        self.assertIn("dialog.close()",self.js)
        self.assertIn('by("operator-password").value=""',self.js)
        self.assertIn('by("login-reveal-password").checked=false',self.js)

    def test_original_backend_approval_and_audit_are_preserved(self):
        for s in ('"/api/operator/login"','"/api/operator/logout"',
                  '"/api/operator/approve"','"/api/operator/execute"',
                  "app.role!==\"OWNER\"",
                  'by("operator-drafts")',
                  'by("operator-audit")'):
            with self.subTest(feature=s):
                self.assertIn(s,self.js)
        self.assertIn('id="operator-stepup"',self.page)
        self.assertIn('id="operator-approve"',self.page)
        self.assertIn('id="operator-execute"',self.page)

    def test_mobile_topbar_and_accessible_modal_styles(self):
        for s in (".account-entry{",".login-dialog{",
                  "@media(max-width:460px)","min-height:44px"):
            self.assertIn(s,self.style)
        self.assertNotIn('autofocus onload=',self.page)
        self.assertNotIn("localStorage.setItem(",self.js)


if __name__=="__main__":
    unittest.main()
