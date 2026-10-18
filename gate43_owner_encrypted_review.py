"""Stage 2 owner-only encrypted review for unified Ministry Word.

The public GitHub Actions artifact is RSA-wrapped AES-GCM CIPHERTEXT only.
No plaintext Word, publisher JPEGs, PDFs, or raster pages leave the runner.
The private RSA key remains OFF GitHub; human review is intentionally pending.
"""
from __future__ import annotations

import base64
import io
import json
import os
import hashlib
import re
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AAD = b"RASD-GATE43-OWNER-MINISTRY-REVIEW-v1"


def pack_owner_review(
    output_dir: Path, audit: dict, destination: Path,
    public_key_path: Path = Path("gate26_owner_review_pubkey.pem"),
    *,
    render_passed: bool = False,
    review_pages_dir: Path | None = None,
) -> dict:
    """Use only existing original-SHA-verified Word, never unreviewed draft."""
    output_dir = Path(output_dir)
    documents = sorted(output_dir.glob("RASD-Unified-*.docx"))
    ready = audit.get("status") == "READY_QA_ONLY"
    if ready:
        if (not render_passed or not audit.get("word_images_verified")
                or not audit.get("all_sources_healthy")
                or audit.get("screenshots_missing") != 0
                or audit.get("screenshots_verified") != audit.get("selected_unique_articles")
                or len(documents) != 1):
            raise ValueError("unified_owner_review_not_fully_verified")
    elif documents:
        raise ValueError("hold_must_not_include_word")
    if (audit.get("email_sent") is not False or
            audit.get("scheduler_enabled") is not False or
            audit.get("source_added_to_production") is not False):
        raise ValueError("owner_review_safety_flag_invalid")
    page_receipts = []
    if review_pages_dir is not None:
        if not ready or not render_passed:
            raise ValueError("review_pages_forbidden_on_hold")
        folder = Path(review_pages_dir)
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError("owner_review_pages_directory_invalid")
        pages = sorted(folder.iterdir())
        if not 1 <= len(pages) <= max(
            3, int(audit.get("selected_unique_articles", 0)) * 4 + 3,
        ):
            raise ValueError("owner_review_page_count_invalid")
        total_bytes = 0
        from PIL import Image
        for i, item in enumerate(pages, 1):
            if (not item.is_file() or item.is_symlink() or
                    item.name != f"page-{i:03d}.png"):
                raise ValueError("owner_review_page_name_invalid")
            payload = item.read_bytes()
            if (not payload.startswith(b"\\x89PNG\\r\\n\\x1a\\n")
                    or not 5000 <= len(payload) <= 9_000_000):
                raise ValueError("owner_review_page_not_valid_png")
            with Image.open(io.BytesIO(payload)) as im:
                if im.format != "PNG" or im.width < 550 or im.height < 550:
                    raise ValueError("owner_review_page_dimensions_invalid")
                im.verify()
            total_bytes += len(payload)
            if total_bytes > 70_000_000:
                raise ValueError("owner_review_total_page_bytes_exceeded")
            page_receipts.append({
                "name": f"review-pages/{item.name}",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            })
    sanitized = {
        key: value for key, value in audit.items()
        if key in {
            "mode", "status", "target_date_cairo", "rss_source_count",
            "official_source_count", "rss_matched_on_day", "official_index_urls",
            "official_pages_checked", "official_same_day", "official_offday",
            "official_pagination_complete", "official_pagination_termination",
            "selected_unique_articles", "screenshots_verified",
            "screenshots_missing", "word_created", "word_images_verified",
            "all_sources_healthy", "source_health", "failures",
            "email_sent", "scheduler_enabled", "source_added_to_production",
        }
    }
    sanitized["private_renderer_passed"] = bool(render_passed)
    sanitized["human_visual_review"] = False
    sanitized["production_delivery_approved"] = False
    sanitized["owner_review_word_included"] = bool(ready)
    sanitized["owner_review_pages_encrypted"] = bool(page_receipts)
    sanitized["owner_review_page_count"] = len(page_receipts)
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
            package.writestr(
                "rasd-owner-review-audit.json",
                json.dumps(sanitized, ensure_ascii=False, sort_keys=True),
            )
            if ready:
                package.write(documents[0], arcname=documents[0].name)
                if page_receipts:
                    package.writestr(
                        "rasd-owner-review-pages-manifest.json",
                        json.dumps({"version": 1, "pages": page_receipts},
                                   sort_keys=True),
                    )
                    for item in page_receipts:
                        package.write(
                            Path(review_pages_dir) / Path(item["name"]).name,
                            arcname=item["name"],
                        )
        raw = buffer.getvalue()
    key = os.urandom(32)
    nonce = os.urandom(12)
    public_key = serialization.load_pem_public_key(
        Path(public_key_path).read_bytes())
    wrapped = public_key.encrypt(
        key, padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(), label=None,
        ))
    encrypted = AESGCM(key).encrypt(nonce, raw, AAD)
    result = {
        "format": "RASD_G43_OWNER_ENCRYPTED",
        "wrapped": base64.b64encode(wrapped).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(encrypted).decode("ascii"),
    }
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, sort_keys=True), encoding="ascii")
    return {
        "encrypted": True, "plaintext_artifact": False,
        "owner_review_word_included": ready, "human_visual_review": False,
        "email_sent": False, "file_size_bytes": destination.stat().st_size,
        "owner_review_pages_encrypted": bool(page_receipts),
        "owner_review_page_count": len(page_receipts),
    }


def unpack_owner_review(payload: Path, private_key: Path, destination: Path) -> list[str]:
    """Local owner operation only. NEVER run in GitHub Actions."""
    content = json.loads(Path(payload).read_text(encoding="ascii"))
    if content.get("format") != "RASD_G43_OWNER_ENCRYPTED":
        raise ValueError("wrong_encrypted_review_format")
    private = serialization.load_pem_private_key(
        Path(private_key).read_bytes(), password=None)
    key = private.decrypt(
        base64.b64decode(content["wrapped"]),
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                     algorithm=hashes.SHA256(), label=None))
    raw = AESGCM(key).decrypt(
        base64.b64decode(content["nonce"]),
        base64.b64decode(content["ciphertext"]), AAD)
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    if len(raw) > 100_000_000:
        raise ValueError("owner_review_decrypted_archive_too_large")
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        members = package.namelist()
        names = set(members)
        valid = {"rasd-owner-review-audit.json",
                 "rasd-owner-review-pages-manifest.json"}
        if (len(members) != len(names) or
                "rasd-owner-review-audit.json" not in names or
                any(not (
                    name in valid or
                    (name.startswith("RASD-Unified-")
                     and name.endswith(".docx") and "/" not in name
                     and "\\\\" not in name and ".." not in name) or
                    re.fullmatch(r"review-pages/page-[0-9]{3}\\.png", name)
                ) for name in members)):
            raise ValueError("unexpected_review_archive_member")
        if sum(info.file_size for info in package.infolist()) > 100_000_000:
            raise ValueError("owner_review_zip_bomb_rejected")
        pages = sorted(name for name in names if name.startswith("review-pages/"))
        has_manifest = "rasd-owner-review-pages-manifest.json" in names
        if bool(pages) != has_manifest:
            raise ValueError("owner_review_page_manifest_missing")
        if pages:
            manifest = json.loads(package.read(
                "rasd-owner-review-pages-manifest.json"))
            receipts = manifest.get("pages")
            if (manifest.get("version") != 1 or
                    not isinstance(receipts, list) or
                    len(receipts) != len(pages) or not 1 <= len(pages) <= 63):
                raise ValueError("owner_review_page_manifest_invalid")
            for name, receipt in zip(pages, receipts):
                data = package.read(name)
                if (receipt.get("name") != name or
                        receipt.get("bytes") != len(data) or
                        receipt.get("sha256") != hashlib.sha256(data).hexdigest()):
                    raise ValueError("owner_review_page_integrity_mismatch")
        extracted = {}
        for name in members:
            extracted[name] = package.read(name)
    # Materialize only after every member and SHA has passed validation.
    for name, content in extracted.items():
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return members


if __name__ == "__main__":
    import argparse
    cli = argparse.ArgumentParser()
    cli.add_argument("--decrypt", action="store_true")
    cli.add_argument("--payload", type=Path)
    cli.add_argument("--private-key", type=Path)
    cli.add_argument("--destination", type=Path)
    options = cli.parse_args()
    if not (options.decrypt and options.payload and options.private_key
            and options.destination):
        cli.error("Only manual local --decrypt --payload --private-key --destination supported")
    print(json.dumps({
        "review_files": unpack_owner_review(
            options.payload, options.private_key, options.destination)
    }))
