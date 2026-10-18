"""Gate 34: manual, protected, READ-ONLY cloud evidence recovery drill.

Separate from upload and Gmail. Never sends mail, publishes artifacts,
creates buckets, enables billing or turns on recurring execution.
The owner provisions a distinct, bucket-scoped READ-ONLY R2 credential
and an existing manifest identity as protected environment secrets.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date

from private_evidence_archive import PrivateEvidenceArchive
from private_evidence_restore import restore_verified_bundle

EXPECTED_WORKFLOW = (
    "Hatem1984/RASD-Cloud-Monitor/.github/workflows/"
    "private-restore-manual.yml@refs/heads/main"
)
ONE_RUN_CONFIRMATION = "CONFIRM_ONE_READONLY_RASD_RESTORE"
OWNER_APPROVAL = "YES_I_APPROVE_ONE_RASD_PRIVATE_RESTORE"


def checked_configuration(environ: dict) -> dict:
    """Validate owner, manual workflow, scoped credentials and target offline."""
    required = {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
        "GITHUB_WORKFLOW_REF": EXPECTED_WORKFLOW,
        "GITHUB_RUN_ATTEMPT": "1",
        "RASD_RESTORE_RUN_CONFIRMATION": ONE_RUN_CONFIRMATION,
        "RASD_R2_RESTORE_APPROVED": OWNER_APPROVAL,
    }
    if any(environ.get(k) != v for k, v in required.items()):
        raise RuntimeError("private_restore_requires_fresh_owner_approval")
    if (environ.get("GITHUB_ACTOR", "").casefold() != "hatem1984"
            or not environ.get("GITHUB_RUN_ID", "").isdigit()):
        raise RuntimeError("private_restore_requires_owner_dispatch")
    account = environ.get("RASD_R2_RESTORE_ACCOUNT_ID", "")
    bucket = environ.get("RASD_R2_RESTORE_BUCKET", "")
    access_key = environ.get("RASD_R2_RESTORE_ACCESS_KEY_ID", "")
    secret = environ.get("RASD_R2_RESTORE_SECRET_ACCESS_KEY", "")
    day = environ.get("RASD_R2_RESTORE_MANIFEST_DATE", "")
    digest = environ.get("RASD_R2_RESTORE_MANIFEST_SHA256", "")
    if not re.fullmatch(r"[0-9a-f]{32}", account):
        raise RuntimeError("private_restore_account_not_configured")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,62}", bucket):
        raise RuntimeError("private_restore_bucket_not_configured")
    if not access_key or not secret:
        raise RuntimeError("private_restore_readonly_credentials_not_configured")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise RuntimeError("private_restore_date_not_configured")
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError()
    except ValueError:
        raise RuntimeError("private_restore_invalid_target_date") from None
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise RuntimeError("private_restore_manifest_not_configured")
    return {
        "endpoint_url": f"https://{account}.r2.cloudflarestorage.com",
        "bucket": bucket, "key": access_key, "secret": secret,
        "manifest_key": f"rasd/v1/{day}/manifests/{digest}.json",
        "manifest_sha256": digest,
    }


def run(*, environ=None, s3_factory=None, verifier=restore_verified_bundle) -> dict:
    settings = checked_configuration(
        dict(os.environ if environ is None else environ)
    )
    if s3_factory is None:
        import boto3
        from botocore.config import Config
        s3_factory = lambda **kwargs: boto3.client(
            "s3", config=Config(
                connect_timeout=10, read_timeout=30,
                retries={"max_attempts": 2, "mode": "standard"}
            ), **kwargs,
        )
    client = s3_factory(
        endpoint_url=settings["endpoint_url"], region_name="auto",
        aws_access_key_id=settings["key"],
        aws_secret_access_key=settings["secret"],
    )
    store = PrivateEvidenceArchive(client, bucket=settings["bucket"])
    verified = verifier(
        store,
        manifest_key=settings["manifest_key"],
        expected_manifest_sha256=settings["manifest_sha256"],
        # Never return recovered private photo or Word contents to CI logs.
        include_bytes=False,
    )
    if verified.get("status") != "PRIVATE_RESTORE_VERIFIED":
        raise RuntimeError("private_restore_not_verified")
    count = verified.get("articles")
    images = verified.get("screenshots_verified")
    if type(count) is not int or count < 1 or images != count:
        raise RuntimeError("private_restore_incomplete")
    return {
        "status": "PRIVATE_RESTORE_VERIFIED", "articles": count,
        "screenshots_verified": images, "word_integrity_verified": True,
        "read_only": True, "email_sent": False,
        "scheduler_enabled": False, "public_artifact_created": False,
    }


def main() -> None:
    try:
        print(json.dumps(run(), sort_keys=True), flush=True)
    except Exception:
        # Fail closed; no endpoint, bucket, digest, secret or Word content.
        print("private_restore_held; inspect protected job configuration",
              flush=True)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
