"""AES-256-GCM authenticated private backup; recovery key stored separately.

The ZIP and SQLite snapshot are assembled in RAM. Never publish either the
encrypted private backup or its key to GitHub or project artifacts.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import os
import secrets
import sqlite3
import zipfile
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .backup import restore_backup,sha

MAGIC=b"RASD-AES256-GCM-BACKUP-v1\n"
KEY_PREFIX="RASD-AES256-GCM-KEY-v1:"
MAX_ARCHIVE_BYTES=250_000_000


def create_encrypted_backup(data_dir: str|Path,archive: str|Path,key_file: str|Path):
    root=Path(data_dir).resolve()
    db=root/"rasd_demo.sqlite"
    files=root/"private_files"
    target=Path(archive).resolve()
    key_path=Path(key_file).resolve()
    if not db.is_file() or not files.is_dir():
        raise ValueError("manual_tenant_database_not_found")
    if target.exists() or key_path.exists():
        raise FileExistsError("new_unique_archive_and_key_names_required")
    if target==key_path or target.is_relative_to(root) or key_path.is_relative_to(root):
        raise ValueError("backup_and_key_must_live_outside_tenant_data")
    if target.parent==key_path.parent:
        raise ValueError("key_must_be_in_separate_directory_from_archive")
    with closing(sqlite3.connect(db)) as source, closing(sqlite3.connect(":memory:")) as snapshot:
        if source.execute("SELECT COUNT(*) FROM scans WHERE status='running'").fetchone()[0]:
            raise RuntimeError("active_manual_scan_backup_hold")
        source.backup(snapshot)
        db_data=snapshot.serialize()
    blobs={"database.sqlite":db_data}
    total=len(db_data)
    for item in sorted(files.rglob("*")):
        if item.is_symlink():
            raise PermissionError("backup_symlink_hold")
        if not item.is_file():
            continue
        rel=item.relative_to(root).as_posix()
        if not rel.startswith("private_files/"):
            raise PermissionError("backup_path_boundary")
        length=item.stat().st_size
        if length>50_000_000:
            raise ValueError("single_backup_component_too_large")
        total+=length
        if total>MAX_ARCHIVE_BYTES:
            raise ValueError("backup_components_limit")
        blobs[rel]=item.read_bytes()
    meta={"format":"RASD_PRIVATE_BACKUP_V1",
          "created_at":datetime.now(timezone.utc).isoformat(),
          "source_root":str(root),
          "entries":{name:{"size":len(blob),"sha256":sha(blob)}
                     for name,blob in blobs.items()}}
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr("manifest.json",json.dumps(meta,ensure_ascii=False))
        for name,blob in blobs.items():
            z.writestr(name,blob)
    clear=buf.getvalue()
    if len(clear)>MAX_ARCHIVE_BYTES:
        raise ValueError("compressed_backup_limit")
    key=AESGCM.generate_key(bit_length=256)
    nonce=secrets.token_bytes(12)
    encoded=MAGIC+nonce+AESGCM(key).encrypt(nonce,clear,MAGIC)
    target.parent.mkdir(parents=True,exist_ok=True)
    key_path.parent.mkdir(parents=True,exist_ok=True)
    created_key=False
    created_archive=False
    try:
        with os.fdopen(os.open(key_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),"w",
                       encoding="ascii") as out:
            created_key=True
            out.write(KEY_PREFIX+base64.b64encode(key).decode("ascii")+"\n")
        with open(target,"xb") as out:
            created_archive=True
            out.write(encoded)
            out.flush()
            os.fsync(out.fileno())
    except Exception:
        if created_archive:
            target.unlink(missing_ok=True)
        if created_key:
            key_path.unlink(missing_ok=True)
        raise
    return {"encrypted_archive":str(target),"archive_sha256":sha(encoded),
            "files":len(blobs),"key_created_separately":True,
            "key_file_location":str(key_path),"aes":"AES-256-GCM",
            "plaintext_staged_on_disk":False}


def restore_encrypted_backup(archive: str|Path,key_file: str|Path,destination: str|Path):
    path=Path(archive).resolve()
    keypath=Path(key_file).resolve()
    if not path.is_file() or not keypath.is_file():
        raise ValueError("encrypted_backup_or_key_not_found")
    content=path.read_bytes()
    if len(content)>MAX_ARCHIVE_BYTES or not content.startswith(MAGIC) or len(content)<len(MAGIC)+28:
        raise ValueError("encrypted_backup_format_or_size_invalid")
    line=keypath.read_text(encoding="ascii").strip()
    if not line.startswith(KEY_PREFIX):
        raise ValueError("recovery_key_file_invalid")
    try:
        key=base64.b64decode(line[len(KEY_PREFIX):],validate=True)
    except Exception:
        raise ValueError("recovery_key_file_invalid") from None
    if len(key)!=32:
        raise ValueError("recovery_key_length_invalid")
    nonce=content[len(MAGIC):len(MAGIC)+12]
    try:
        clear=AESGCM(key).decrypt(nonce,content[len(MAGIC)+12:],MAGIC)
    except InvalidTag:
        raise RuntimeError("backup_authentication_failure_wrong_key_or_tamper") from None
    result=restore_backup(clear,destination)
    return {"restored_path":result["restored_path"],"files":result["files"],
            "tenants":result["tenants"],"encrypted_archive_sha256":sha(content),
            "word_sha_verified":True,"private_key_not_in_archive":True}


def main():
    parser=argparse.ArgumentParser(description="RASD PRIVATE AES-256-GCM backup, no SMTP")
    sub=parser.add_subparsers(dest="action",required=True)
    create=sub.add_parser("create")
    create.add_argument("--data",required=True)
    create.add_argument("--out",required=True)
    create.add_argument("--key-file",required=True)
    restore=sub.add_parser("restore")
    restore.add_argument("--archive",required=True)
    restore.add_argument("--key-file",required=True)
    restore.add_argument("--out",required=True)
    args=parser.parse_args()
    res=(create_encrypted_backup(args.data,args.out,args.key_file)
         if args.action=="create" else
         restore_encrypted_backup(args.archive,args.key_file,args.out))
    print(json.dumps(res,ensure_ascii=False))


if __name__=="__main__":
    main()
