"""Gate71: R2-ready CIPHERTEXT envelope checks, NO cloud/network/API calls.

Only the owner's RSA/AES-GCM encrypted JSON may ever be considered for a
future approved private backup. This module DOES NOT validate authenticity
without the private key; genuine local owner decryption remains mandatory.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")
ALLOWED = {"format", "nonce", "wrapped", "ciphertext"}
MAX_ENVELOPE_BYTES = 8_000_000
FORMAT = "RASD_G43_OWNER_ENCRYPTED"


def check_owner_ciphertext(payload: bytes) -> dict:
    if (type(payload) is not bytes or not
            256 <= len(payload) <= MAX_ENVELOPE_BYTES):
        raise ValueError("gate71_ciphertext_size_or_type_invalid")
    try:
        envelope = json.loads(payload.decode("utf-8", "strict"))
        if (type(envelope) is not dict or set(envelope) != ALLOWED or
                envelope["format"] != FORMAT or
                any(type(envelope[x]) is not str for x in
                    ("nonce", "wrapped", "ciphertext"))):
            raise ValueError("invalid")
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        wrapped = base64.b64decode(envelope["wrapped"], validate=True)
        cipher = base64.b64decode(envelope["ciphertext"], validate=True)
        if (len(nonce) != 12 or len(wrapped) not in (256, 384, 512)
                or len(cipher) < 32 or len(cipher) > MAX_ENVELOPE_BYTES):
            raise ValueError("invalid")
    except (UnicodeError, ValueError, KeyError, TypeError, OverflowError):
        raise ValueError("gate71_invalid_owner_encrypted_envelope") from None
    return {"format": FORMAT, "ciphertext_only": True,
            "envelope_bytes": len(payload)}


def prepare_private_ciphertext_backup(payload: bytes, *, day: date) -> dict:
    """A safe, deterministic plan; does not create an object or authorize R2."""
    if type(day) is not date or day >= datetime.now(CAIRO).date():
        raise ValueError("gate71_requires_completed_cairo_day")
    info = check_owner_ciphertext(payload)
    digest = hashlib.sha256(payload).hexdigest()
    return {
        "status": "ENCRYPTED_OWNER_R2_NO_NETWORK_PREFLIGHT_ONLY",
        "cairo_day": day.isoformat(),
        "object_key": (f"rasd/owner-ciphertext/{day.year:04d}/"
                       f"{day.month:02d}/{day.isoformat()}/{digest}.json"),
        "envelope_bytes": info["envelope_bytes"],
        "encrypted_payload_sha256": digest,
        "content_type": "application/json",
        "plaintext_uploaded": False, "private_key_used": False,
        "object_uploaded": False, "restore_verified_remotely": False,
        "production_approved": False, "email_sent": False,
        "scheduler_enabled": False,
    }


def verify_private_ciphertext_roundtrip(
    plan: dict, expected_original: bytes, restored_ciphertext: bytes
) -> dict:
    """A local test only — never assert that remote R2 was actually used."""
    if (type(plan) is not dict or
            plan.get("status") != "ENCRYPTED_OWNER_R2_NO_NETWORK_PREFLIGHT_ONLY"
            or plan.get("object_uploaded") is not False
            or plan.get("production_approved") is not False):
        raise ValueError("gate71_storage_plan_not_safe")
    if type(expected_original) is not bytes or type(restored_ciphertext) is not bytes:
        raise ValueError("gate71_restore_bytes_required")
    check_owner_ciphertext(expected_original)
    check_owner_ciphertext(restored_ciphertext)
    digest = hashlib.sha256(expected_original).hexdigest()
    if (digest != plan.get("encrypted_payload_sha256") or
            len(expected_original) != plan.get("envelope_bytes") or
            hashlib.sha256(restored_ciphertext).hexdigest() != digest or
            restored_ciphertext != expected_original):
        raise ValueError("gate71_restore_ciphertext_identity_mismatch")
    # Never imply authenticity (needs owner's RSA private key), owner visual
    # review, actual remote backup or real operational recovery.
    return {
        "status": "LOCAL_CIPHERTEXT_BYTES_ROUNDTRIP_ONLY",
        "bytes_identical": True,
        "r2_used": False,
        "remote_restore_verified": False,
        "owner_decryption_performed": False,
        "email_sent": False,
        "production_approved": False,
    }
