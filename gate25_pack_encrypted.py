"""Encrypt one private-to-owner original-page pilot into PUBLIC safe ciphertext.

Encryption key is a throwaway public key. The RSA private key is NEVER uploaded
to GitHub, emitted to logs, committed, or inserted into artifacts.
"""
from __future__ import annotations
import base64
import io
import json
import os
import sys
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AAD=b"RASD-GATE25-OWNER-PRIVATE-EVIDENCE-v1"
def pack(source:Path,target:Path,pub:Path):
    files=["audit.json"]
    if (source/"RASD-Gate25-Original-Publisher-Pilot.docx").is_file():
        files += ["original_publisher_page.jpg",
                  "RASD-Gate25-Original-Publisher-Pilot.docx","article.json"]
    with io.BytesIO() as dest:
        with zipfile.ZipFile(dest,"w",zipfile.ZIP_DEFLATED) as z:
            for item in files:
                f=source/item
                if f.is_file():
                    z.write(f,arcname=item)
        raw=dest.getvalue()
    key,nonce=os.urandom(32),os.urandom(12)
    public=serialization.load_pem_public_key(pub.read_bytes())
    wrapped=public.encrypt(key,padding.OAEP(mgf=padding.MGF1(
        algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    enc=AESGCM(key).encrypt(nonce,raw,AAD)
    obj={"format":"RASD_G25_OWNER_ENCRYPTED_v1","wrapped":base64.b64encode(wrapped).decode(),
         "nonce":base64.b64encode(nonce).decode(),
         "ciphertext":base64.b64encode(enc).decode()}
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(obj),encoding="ascii")
    print(json.dumps({"encrypted_bundle_created":True,"plaintext_in_artifact":False,
        "public_result_count":len(files),"bytes":target.stat().st_size}))
if __name__=="__main__":
    pack(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]))
