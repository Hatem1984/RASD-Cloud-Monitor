"""Export two clearly labelled synthetic RASD demo Word documents, no send."""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw
from docx import Document

from .core import Store


def logo_file(store, tenant, letters, color):
    path=store.files/tenant/"logo.png"
    path.parent.mkdir(parents=True,exist_ok=True)
    im=Image.new("RGB",(420,180),color)
    draw=ImageDraw.Draw(im)
    draw.text((32,30),letters,fill="white")
    draw.text((32,96),"RASD DEMO CLIENT",fill="#f7e4bb")
    im.save(path,format="PNG")
    with store.connect() as con:
        con.execute("UPDATE tenants SET logo_path=? WHERE id=?",(str(path),tenant))


def run(out):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    details={}
    with tempfile.TemporaryDirectory() as temp:
        store=Store(temp)
        info=store.seed_demo(owner_password="SYNTHETIC-EXPORT-ONLY")
        if not info: raise RuntimeError("unexpected_existing_demo")
        for name,tenant,letters,color in (
            ("UNIVERSITY",info["tenants"]["university"],"UNI","#19324b"),
            ("FOOD",info["tenants"]["foods"],"FOOD","#315c54"),
        ):
            logo_file(store,tenant,letters,color)
            sid,_=store.start_scan(tenant)
            store.run_scan(tenant,sid)
            articles=store.articles(tenant)
            for article in articles:
                store.review(tenant,article["id"],"synthetic-demo-export","approved")
            ids=[a["id"] for a in articles]
            report=store.create_report(tenant,ids,
                    "2000-01-01T00:00:00+00:00","2100-01-01T00:00:00+00:00")
            destination=out/("RASD_SYNTHETIC_"+name+".docx")
            shutil.copyfile(report["file_path"],destination)
            manifest=json.loads(report["manifest"])
            doc=Document(destination)
            assert len(doc.inline_shapes)==len(manifest)+1,"logo plus one JPEG per card"
            links=[doc.part.rels[h.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")].target_ref
                   for h in doc.element.body.xpath(".//w:hyperlink")]
            digests=[hashlib.sha256(doc.part.related_parts[
                img.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")].blob).hexdigest()
                for img in doc.element.body.xpath(".//a:blip")]
            assert links==[a["url"] for a in manifest]
            assert digests[1:]==[a["image_sha"] for a in manifest]
            details[name]={"articles":len(manifest),"filesha256":hashlib.sha256(destination.read_bytes()).hexdigest(),
                "actual_publisher_images":0,"demo_images":len(manifest),
                "publishers":len({a["publisher"] for a in manifest}),
                "events":len({a["event_key"] for a in manifest}),
                "name":store.tenant(tenant)["name"]}
        (out/"SYNTHETIC_WORD_ACCEPTANCE.json").write_text(
            json.dumps({"result":"VERIFIED_DEMO_ONLY","documents":details,
                        "smtp_messages_sent":0,"production_cas_writes":0},ensure_ascii=False,indent=2),
            encoding="utf-8")
    print("RASD_SYNTHETIC_WORD_ACCEPTANCE="+json.dumps(details,ensure_ascii=False),flush=True)
    return details


if __name__=="__main__":
    run(sys.argv[1] if len(sys.argv)>1 else "demo-output")
