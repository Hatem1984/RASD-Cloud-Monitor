"""Owner-encrypted review artifact. No plaintext screenshots or Word in public CI.

Key must be a one-off public RSA key; private part never enters repository.
"""
from __future__ import annotations
import base64
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AAD=b"RASD-GATE26-OWNER-REVIEW-v1"

def pack(root:Path,dest:Path,public_key:Path):
    manifest=root/"gate26-review-audit.json"
    audit=json.loads(manifest.read_text(encoding="utf-8"))
    files=[manifest]
    if audit.get("status")=="REVIEW_READY":
        name=audit.get("review_word","")
        word=root/name
        if (not name.startswith("RASD-Verified-Shorouk-Review-")
                or not word.is_file() or word.stat().st_size<8000):
            raise ValueError("verified_review_word_missing")
        files.append(word)
    # No raw JPEG captured outside the Word; the strict Word embeds its proof.
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer,"w",zipfile.ZIP_DEFLATED) as z:
            for file in files:
                z.write(file,arcname=file.name)
        payload=buffer.getvalue()
    key=os.urandom(32);nonce=os.urandom(12)
    pub=serialization.load_pem_public_key(public_key.read_bytes())
    wrapped=pub.encrypt(key,padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),label=None))
    encrypted=AESGCM(key).encrypt(nonce,payload,AAD)
    obj={"format":"RASD_G26_ENCRYPTED",
         "wrapped":base64.b64encode(wrapped).decode(),
         "nonce":base64.b64encode(nonce).decode(),
         "ciphertext":base64.b64encode(encrypted).decode()}
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(obj),encoding="ascii")
    return {"encrypted":True,"plaintext_artifact":False,
            "has_review_word":len(files)==2,"size":dest.stat().st_size}

if __name__=="__main__":
    data=pack(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]))
    print(json.dumps(data),flush=True)
