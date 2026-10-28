"""No-network synthetic only: report uses exact original JPEG and current AI."""
import hashlib
import io
import unittest
from zipfile import ZipFile
from PIL import Image

from maal.competition_report import create_agent_brief_docx


class LinkedAgentWord(unittest.TestCase):
    def setUp(self):
        im=Image.new("RGB",(80,50),"white")
        out=io.BytesIO()
        im.save(out,format="JPEG")
        self.jpeg=out.getvalue()
        digest=hashlib.sha256(self.jpeg).hexdigest()
        self.case={
            "evidence_id":"5eb7494a551cdb399031d2c9",
            "verification_status":"VERIFIED_ORIGINAL_PAGE",
            "verified_receipt":True, "timeliness":"HISTORICAL",
            "evidence_digest":digest, "publisher":"SYNTHETIC TEST Publisher",
            "headline":"SYNTHETIC archived government headline",
            "published_day":"2026-10-17",
            "observed_at":"2026-10-26T15:00:09+00:00",
            "original_url":"https://mped.gov.eg/singlenews?id=7269&lang=ar"
        }
        self.ai={
            "source_id":self.case["evidence_id"],"source_sha256":digest,
            "source_url":self.case["original_url"],
            "quality_approval":"HOLD_HUMAN_REVIEW","actions_executed":False,
            "status":"AI_DRAFT_UNREVIEWED","run_id":"maal-g3-test1234",
            "recorded_at":"2026-10-27T16:00:00+00:00",
            "model":"Qwen3-1.7B-Q4_K_M","inference_seconds":3.5,
            "facts":["SYNTHETIC fact"],"inference":"Hypothetical impact",
            "unknowns":["No confirmed funding"],"alternatives":["Review","Monitor"],
            "recommendation":"Prepare internal review"
        }

    def test_docx_has_exact_original_and_model_identity(self):
        binary=create_agent_brief_docx(self.case,self.ai,self.jpeg)
        self.assertGreater(len(binary),5000)
        from docx import Document
        text=" ".join(x.text for x in Document(io.BytesIO(binary)).paragraphs)
        self.assertIn(self.ai["run_id"],text)
        self.assertIn(self.case["original_url"],text)
        self.assertIn("مَآل",text)
        with ZipFile(io.BytesIO(binary)) as z:
            names=[n for n in z.namelist() if n.startswith("word/media/")]
            self.assertEqual(len(names),1)
            self.assertEqual(hashlib.sha256(z.read(names[0])).hexdigest(),
                             self.case["evidence_digest"])

    def test_wrong_picture_is_never_accepted(self):
        with self.assertRaisesRegex(ValueError,"publisher_original_jpeg_sha256_mismatch"):
            create_agent_brief_docx(self.case,self.ai,b"wrong proof")

    def test_unrelated_model_cannot_be_published(self):
        self.ai["source_sha256"]="b"*64
        with self.assertRaisesRegex(ValueError,"agent_model_source_mismatch"):
            create_agent_brief_docx(self.case,self.ai,self.jpeg)


if __name__=="__main__":
    unittest.main()
