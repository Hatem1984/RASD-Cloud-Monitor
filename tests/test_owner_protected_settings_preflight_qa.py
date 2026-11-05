"""Protected cloud QA reader: GET only, no SMTP/network/production writes."""
import base64,io,json,unittest
from pathlib import Path
from rasd_settings_bridge_qa import _hash
import rasd_protected_settings_preflight as p

class _Response:
    def __init__(self,data):self.data=data
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.data[:n]
class _Opener:
    def __init__(self,manifest):
        encoded=base64.b64encode(json.dumps(manifest,ensure_ascii=False).encode()).decode()
        self.data=json.dumps({"type":"file","encoding":"base64","content":encoded}).encode()
        self.request=None
    def open(self,req,timeout):
        self.request=req
        assert req.get_method()=="GET"
        assert "RASD-Pilot" in req.full_url
        assert "qa-active" in req.full_url
        return _Response(self.data)
def manifest():
    baseline=json.loads(p.BASELINE.read_text("utf-8"))
    topics=[{"label":"وزير التخطيط","aliases":["وزير التخطيط"],"match":"any","enabled":True}]
    sources=[{"id":f["id"],"name":f["name"],"url":f["url"],"enabled":True} for f in baseline["feeds"]]
    settings={"topics":topics,"sources":sources,"start":"00:00","end":"22:00",
              "report_title":"رصد | اليوم","report_type":"شامل","detail":"متوسط",
              "analysis_instructions":"","include":{"headlines":True,"links":True,"screenshots":True,"analysis":True},
              "scan_minutes":30,"send_mode":"daily","send_at":"22:00"}
    return {"scope":"QA_PREVIEW_NO_SEND","schema_version":1,
            "active_version":27,"settings":settings,"sha256":_hash(settings)}
class ProtectedQA(unittest.TestCase):
    def test_valid_read_only_private_qa_manifest(self):
        fake=_Opener(manifest())
        r=p.run(token="x"*40,opener=fake)
        self.assertTrue(r["qa_only"])
        self.assertFalse(r["send_allowed"])
        self.assertEqual(r["sources"],13)
        self.assertEqual(fake.request.get_method(),"GET")
    def test_no_token_holds(self):
        with self.assertRaisesRegex(RuntimeError,"reader_unavailable"):
            p.run(token="",opener=_Opener(manifest()))
    def test_cannot_claim_qa_scope_as_production(self):
        m=manifest();m["scope"]="ACTIVE_APPROVED"
        with self.assertRaisesRegex(RuntimeError,"qa_scope_hold"):
            p.run(token="x"*40,opener=_Opener(m))
    def test_modified_manifest_fails_integrity(self):
        m=manifest();m["settings"]["topics"][0]["aliases"][0]="غير صحيح"
        with self.assertRaisesRegex(RuntimeError,"digest_hold"):
            p.run(token="x"*40,opener=_Opener(m))
    def test_secrets_never_allowed_in_owner_settings(self):
        m=manifest();m["settings"]["smtp_password"]="any"
        with self.assertRaisesRegex(RuntimeError,"sensitive_setting"):
            p.run(token="x"*40,opener=_Opener(m))
if __name__=="__main__":unittest.main()
