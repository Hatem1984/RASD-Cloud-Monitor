"""Manual owner-approved original-publisher proof -> private Cloudflare R2 archive.

Never creates an R2 account/bucket, enables billing, schedules work or sends
email. Credentials must be provisioned directly as protected GitHub secrets.
A denied publisher still produces HOLD and NO final private manifest.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from cloud_proof_report import build_proof_report
from private_evidence_archive import PrivateEvidenceArchive

EXPECTED_REF = (
    "Hatem1984/RASD-Cloud-Monitor/.github/workflows/"
    "private-proof-manual.yml@refs/heads/main"
)
ONE_RUN_CONFIRMATION = "CONFIRM_ONE_PRIVATE_RASD_ARCHIVE_RUN"
OWNER_UPLOAD_APPROVAL = "YES_I_APPROVE_PRIVATE_RASD_EVIDENCE_STORAGE"


def checked_configuration(environ: dict) -> dict:
    """Reject unsafe event, rerun, branch and missing secrets BEFORE network."""
    expected = {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
        "GITHUB_WORKFLOW_REF": EXPECTED_REF,
        "GITHUB_RUN_ATTEMPT": "1",
        "RASD_ARCHIVE_RUN_CONFIRMATION": ONE_RUN_CONFIRMATION,
        "RASD_PRIVATE_ARCHIVE_ENABLED": OWNER_UPLOAD_APPROVAL,
    }
    if any(environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError("private_archive_requires_fresh_owner_reviewed_dispatch")
    if (environ.get("GITHUB_ACTOR", "").casefold() != "hatem1984" or
            not environ.get("GITHUB_RUN_ID", "").isdigit()):
        raise RuntimeError("private_archive_requires_owner_run")
    account = environ.get("RASD_R2_ACCOUNT_ID", "")
    bucket = environ.get("RASD_R2_BUCKET", "")
    key = environ.get("RASD_R2_ACCESS_KEY_ID", "")
    secret = environ.get("RASD_R2_SECRET_ACCESS_KEY", "")
    if not re.fullmatch(r"[0-9a-f]{32}", account):
        raise RuntimeError("private_archive_account_not_configured")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,62}", bucket):
        raise RuntimeError("private_archive_bucket_not_configured")
    if not key or not secret:
        raise RuntimeError("private_archive_credentials_not_configured")
    return {"endpoint_url": f"https://{account}.r2.cloudflarestorage.com",
            "bucket": bucket, "key": key, "secret": secret}


def run(*, environ=None, s3_factory=None, generator=build_proof_report) -> dict:
    # Both configuration and approval checks finish before any publisher or R2 request.
    settings = checked_configuration(dict(os.environ if environ is None else environ))
    if s3_factory is None:
        import boto3
        from botocore.config import Config
        s3_factory = lambda **kwargs: boto3.client(
            "s3", config=Config(connect_timeout=10, read_timeout=30,
                                retries={"max_attempts": 2, "mode": "standard"}),
            **kwargs,
        )
    client = s3_factory(
        endpoint_url=settings["endpoint_url"], region_name="auto",
        aws_access_key_id=settings["key"],
        aws_secret_access_key=settings["secret"],
    )
    archive = PrivateEvidenceArchive(client, bucket=settings["bucket"])
    result = generator(Path("sources.json"), Path("proof-output"),
                       archive_writer=archive)
    # Never echo the private bucket name or auth; the hash alone proves commit.
    return {k: result[k] for k in (
        "status", "archive_status", "articles", "screenshots_verified",
        "screenshots_missing", "coverage", "word_created",
    )}


def main() -> None:
    try:
        outcome = run()
        print(json.dumps(outcome, ensure_ascii=False), flush=True)
        if outcome["status"] != "READY" or outcome["archive_status"] != "PRIVATE_VERIFIED":
            print("private_archive_hold; no completed original-publisher Word proof",
                  flush=True)
            raise SystemExit(2)
    except SystemExit:
        raise
    except Exception:
        print("private_archive_failed_closed; check protected audit without secrets",
              flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
