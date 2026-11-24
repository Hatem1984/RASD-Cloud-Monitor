"""Verified offline backup and isolated restore for RASD manual enterprise trials.

Never reads the ministry sender/CAS; refuses in-flight scans, symlinks, path
traversal and restore over an existing client. Only locally operated by owner.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import io
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime,timezone
from pathlib import Path

from .enterprise import EnterpriseStore


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_backup(data_dir: str|Path,archive: str|Path) -> dict:
    base=Path(data_dir).resolve()
    db=base/"rasd_demo.sqlite"
    private=base/"private_files"
    output=Path(archive).resolve()
    if not db.is_file() or not private.is_dir():
        raise ValueError("manual_tenant_database_not_found")
    if output.is_relative_to(private) or output==db:
        raise ValueError("backup_must_be_outside_private_files")
    output.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(db)) as src:
        if src.execute("SELECT COUNT(*) FROM scans WHERE status='running'").fetchone()[0]:
            raise RuntimeError("active_manual_scan_backup_hold")
    with tempfile.TemporaryDirectory(prefix=".rasd-backup-") as tmp:
        copy=Path(tmp)/"database.sqlite"
        with closing(sqlite3.connect(db)) as source, closing(sqlite3.connect(copy)) as target:
            source.backup(target)
        files={"database.sqlite":copy.read_bytes()}
        for item in sorted(private.rglob("*")):
            if item.is_symlink():
                raise RuntimeError("private_symlink_backup_hold")
            if not item.is_file():
                continue
            rel=item.relative_to(base).as_posix()
            if not rel.startswith("private_files/"):
                raise RuntimeError("archive_path_outside_client")
            files[rel]=item.read_bytes()
        meta={"format":"RASD_PRIVATE_BACKUP_V1","created_at":datetime.now(timezone.utc).isoformat(),
              "source_root":str(base),"entries":{name:{"size":len(blob),"sha256":sha(blob)}
                                         for name,blob in files.items()}}
        with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive_file:
            archive_file.writestr("manifest.json",json.dumps(meta,ensure_ascii=False,indent=2))
            for name,blob in files.items():
                archive_file.writestr(name,blob)
    return {"archive":str(output),"files":len(files),"sha256":sha(output.read_bytes()),
            "source_db_sha256":meta["entries"]["database.sqlite"]["sha256"]}


def restore_backup(archive: str|Path|bytes,destination: str|Path) -> dict:
    """Restore from a disk ZIP or from authenticated decrypted ZIP bytes in RAM."""
    memory_archive=isinstance(archive,(bytes,bytearray))
    source=None if memory_archive else Path(archive).resolve()
    dest=Path(destination).resolve()
    if memory_archive and len(archive)>250_000_000:
        raise ValueError("backup_memory_size_limit")
    if source is not None and not source.is_file():
        raise ValueError("backup_file_not_found")
    if dest.exists() and any(dest.iterdir()):
        raise ValueError("restore_destination_must_be_empty")
    with zipfile.ZipFile(io.BytesIO(archive) if memory_archive else source,"r") as z:
        names=z.namelist()
        if len(names)>2000 or "manifest.json" not in names or len(names)!=len(set(names)):
            raise ValueError("archive_member_count_or_duplicate_invalid")
        meta=json.loads(z.read("manifest.json"))
        if meta.get("format")!="RASD_PRIVATE_BACKUP_V1":
            raise ValueError("backup_format_mismatch")
        expected=meta.get("entries",{})
        if not isinstance(expected,dict) or set(names)-{"manifest.json"}!=set(expected):
            raise ValueError("backup_manifest_entries_mismatch")
        total=0
        for name in expected:
            if name!="database.sqlite" and not name.startswith("private_files/"):
                raise ValueError("backup_path_unexpected")
            pure=Path(name)
            if any(x in ("..","") for x in pure.parts) or pure.is_absolute() or "\\" in name:
                raise ValueError("backup_path_traversal")
            info=z.getinfo(name)
            if info.file_size>50_000_000 or info.compress_size>50_000_000:
                raise ValueError("single_file_too_large")
            total+=info.file_size
            if total>250_000_000:
                raise ValueError("backup_total_size_limit")
            content=z.read(name)
            if len(content)!=expected[name]["size"] or sha(content)!=expected[name]["sha256"]:
                raise RuntimeError("backup_sha256_integrity_failure")
        # Do not mutate target before all bytes pass validation.
        dest.mkdir(parents=True,exist_ok=True)
        try:
            for name in expected:
                path=dest/("rasd_demo.sqlite" if name=="database.sqlite" else name)
                if not path.resolve().is_relative_to(dest):
                    raise PermissionError("restore_path_boundary")
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(z.read(name))
            old=Path(meta["source_root"]).resolve()
            newfiles=(dest/"private_files").resolve()
            # SQL manifests historically save absolute paths. Rebase ONLY those
            # inside the verified old private_files root; otherwise HOLD.
            with closing(sqlite3.connect(dest/"rasd_demo.sqlite")) as db:
                for table,col in (("reports","file_path"),("articles","image_path"),("tenants","logo_path")):
                    for rid,path in db.execute(f"SELECT rowid,{col} FROM {table} WHERE {col} IS NOT NULL").fetchall():
                        original=Path(path).resolve()
                        oldfiles=(old/"private_files").resolve()
                        if not original.is_relative_to(oldfiles):
                            raise PermissionError("restore_historical_path_outside_private_root")
                        newpath=newfiles/original.relative_to(oldfiles)
                        if not newpath.is_file():
                            raise RuntimeError("restore_referenced_file_missing")
                        db.execute(f"UPDATE {table} SET {col}=? WHERE rowid=?",(str(newpath),rid))
                # Restored sessions must never inherit old authenticated access.
                db.execute("DELETE FROM sessions")
                db.commit()
            st=EnterpriseStore(dest)
            for tenant in st.memberships({"id":"", "platform_owner":True}):
                for report in st.list_reports(tenant["id"]):
                    file=st.secure_file(tenant["id"],report["file_path"])
                    if sha(file.read_bytes())!=report["file_sha"]:
                        raise RuntimeError("restored_word_sha_mismatch")
        except Exception:
            # Only scratch destination we just created; source remains unchanged.
            shutil.rmtree(dest,ignore_errors=True)
            raise
    return {"restored_path":str(dest),"files":len(expected),
            "archive_sha256":sha(archive if memory_archive else source.read_bytes()),
            "tenants":len(st.memberships({"id":"", "platform_owner":True}))}


def main():
    p=argparse.ArgumentParser(description="RASD manual local-only verifiable backup")
    command=p.add_subparsers(dest="action",required=True)
    a=command.add_parser("create")
    a.add_argument("--data",required=True);a.add_argument("--out",required=True)
    a=command.add_parser("restore")
    a.add_argument("--archive",required=True);a.add_argument("--out",required=True)
    args=p.parse_args()
    outcome=(create_backup(args.data,args.out) if args.action=="create"
             else restore_backup(args.archive,args.out))
    print(json.dumps(outcome,ensure_ascii=False))


if __name__=="__main__":
    main()
