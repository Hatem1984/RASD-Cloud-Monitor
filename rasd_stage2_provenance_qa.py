"""Bind each RASD half-hour receipt to a REAL GitHub scheduled Actions run.

Pure, offline-testable contract. File content alone cannot prove its origin:
GitHub API must independently report schedule, original attempt, exact workflow,
same Cairo slot, successful run, and a nonexpired private artifact.
No authentication or SMTP code in this module.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")
PRIVATE_REPO = "Hatem1984/RASD-Pilot"
WORKFLOW_PATH = ".github/workflows/rasd-stage2-collector-no-send.yml"
MAX_ARTIFACT_DELAY = timedelta(minutes=20)


def _clock(value):
    if not isinstance(value, str):
        raise ValueError("qa_clock_missing")
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("qa_clock_naive")
    return instant.astimezone(timezone.utc)


def _slot(instant):
    local = instant.astimezone(CAIRO)
    return local.date().isoformat(), f"{local.hour:02d}:{(local.minute // 30) * 30:02d}"


def validate_scheduled_artifact(receipt: dict, artifact: dict, run: dict) -> bool:
    """Raise on all uncertain provenance; a manual/push/smoke run never counts."""
    if not all(isinstance(x, dict) for x in (receipt, artifact, run)):
        raise ValueError("qa_provenance_shape")
    if (receipt.get("kind") != "QA_REAL_SLOT_OBSERVATION"
            or receipt.get("smtp_sent") is not False
            or receipt.get("original_screenshots_verified") is not False):
        raise ValueError("qa_provenance_not_a_real_safe_slot")
    if (artifact.get("name") != "rasd-stage2-observation"
            or artifact.get("expired") is not False
            or type(artifact.get("id")) is not int):
        raise ValueError("qa_provenance_artifact_identity")
    artifact_workflow = artifact.get("workflow_run")
    if (not isinstance(artifact_workflow, dict)
            or artifact_workflow.get("head_branch") != "main"
            or type(artifact_workflow.get("id")) is not int
            or type(run.get("id")) is not int
            or run["id"] != artifact_workflow["id"]
            or str(run["id"]) != str(receipt.get("github_run_id"))):
        raise ValueError("qa_provenance_run_identity")
    owner = run.get("repository")
    if (run.get("event") != "schedule"
            or run.get("path") != WORKFLOW_PATH
            or run.get("head_branch") != "main"
            or run.get("run_attempt") != 1
            or run.get("status") != "completed"
            or run.get("conclusion") not in ("success", "failure")
            or not isinstance(owner, dict)
            or owner.get("full_name") != PRIVATE_REPO):
        raise ValueError("qa_provenance_run_not_approved_schedule")
    # Source failures must appear as failed Actions runs, while retaining
    # their original HOLD evidence for the daily audit. Historical false-green
    # runs with a HOLD receipt remain HOLD, never become healthy coverage.
    if (run["conclusion"] == "failure"
            and receipt.get("status") not in (
                "HOLD_SOURCE_FAILURE", "HOLD_SCAN_INCOMPLETE",
                "HOLD_MISSED_OR_CROSSED_WINDOW")):
        raise ValueError("qa_provenance_failed_run_without_hold_receipt")
    created = _clock(run.get("created_at"))
    started = _clock(receipt.get("observed_at_utc"))
    finished = _clock(receipt.get("finished_at_utc"))
    artifact_time = _clock(artifact.get("created_at"))
    if not (created <= started <= finished <= artifact_time
            and artifact_time - finished <= MAX_ARTIFACT_DELAY):
        raise ValueError("qa_provenance_out_of_order")
    # A workflow delayed past the actual scheduled slot cannot replace a
    # missing preceding slot, even if RSS happened to be fetched later.
    if (_slot(created) != _slot(started)
            or _slot(started) != (receipt.get("day_cairo"), receipt.get("slot_cairo"))):
        raise ValueError("qa_provenance_late_slot")
    return True
