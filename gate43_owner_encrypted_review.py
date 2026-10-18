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
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
            package.writestr(
                "rasd-owner-review-audit.json",
                json.dumps(sanitized, ensure_ascii=False, sort_keys=True),
            )
            if ready:
                package.write(documents[0], arcname=documents[0].name)
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
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        members = package.namelist()
        if len(members) != len(set(members)) or any(
            "/" in name or "\\" in name or name.startswith(".")
            or name not in ("rasd-owner-review-audit.json",)
            and not (name.startswith("RASD-Unified-") and name.endswith(".docx"))
            for name in members
        ):
            raise ValueError("unexpected_review_archive_member")
        for name in members:
            (dest / name).write_bytes(package.read(name))
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
