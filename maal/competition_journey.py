"""One source-linked owner journey: verified historical signal -> AI -> owner task.

Read-only composition of independently validated existing Gate E, Qwen3 and
Gate F/H components. No model inference, consent, SMTP, or task execution here.
"""
from __future__ import annotations
from datetime import datetime, timezone
import re

DRAFT_STATES = frozenset(("DRAFT", "APPROVED", "EXECUTED"))
DIGEST = re.compile(r"^[0-9a-f]{64}$")


def assemble_agent_journey(case: dict, ai: dict, operator: dict | None = None) -> dict:
    """The current source / model / owner workflow read the same evidence ID.

    The server independently calls get_case() (original JPEG SHA), then
    get_local_ai_run() (strict contract), then authenticated dashboard().
    Never derive consent from an AI proposal, demo guest state or prior Gate F.
    """
    if (case.get("verification_status") != "VERIFIED_ORIGINAL_PAGE"
            or case.get("verified_receipt") is not True
            or case.get("timeliness") != "HISTORICAL"
            or not DIGEST.fullmatch(str(case.get("evidence_digest", "")))):
        raise ValueError("agent_original_evidence_not_verified")
    if (ai.get("source_id") != case.get("evidence_id")
            or ai.get("source_sha256") != case.get("evidence_digest")
            or ai.get("source_url") != case.get("original_url")
            or ai.get("quality_approval") != "HOLD_HUMAN_REVIEW"
            or ai.get("actions_executed") is not False
            or ai.get("status") != "AI_DRAFT_UNREVIEWED"
            or not str(ai.get("run_id", "")).startswith("maal-g3-")):
        raise ValueError("agent_model_source_mismatch")
    try:
        observed = datetime.fromisoformat(ai["recorded_at"])
    except (ValueError, TypeError, KeyError):
        raise ValueError("invalid_model_receipt_time") from None
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("model_receipt_timezone_required")
    if observed > datetime.now(timezone.utc):
        raise ValueError("future_model_receipt")
    decisions = []
    audit_integrity = "AUTHENTICATION_REQUIRED"
    authenticated = False
    if operator is not None:
        if (operator.get("role") not in ("OWNER", "REVIEWER")
                or operator.get("production") is not False
                or operator.get("audit_integrity") != "CHAIN_VERIFIED"):
            raise ValueError("invalid_operator_state")
        authenticated = True
        audit_integrity = operator["audit_integrity"]
        for row in operator.get("drafts", []):
            if row.get("evidence_id") != case["evidence_id"]:
                continue
            if row.get("state") not in DRAFT_STATES:
                raise ValueError("invalid_draft_state")
            decisions.append({
                "draft_id": row["draft_id"],
                "state": row["state"],
                "description": row["description"],
                "task_id": row.get("task_id"),
                "approved_by": row.get("approved_by"),
                "matches_current_recommendation": row["description"] == ai["recommendation"],
            })
    # Existing historical report is source-image verified, but NOT a new
    # AI-generated report from this model run; make that boundary explicit.
    return {
        "schema": "MAAL_COMPETITION_JOURNEY_V1",
        "mode": "OWNER_LOCAL_HISTORICAL_E2E_REVIEW",
        "live_signal": False,
        "company_is_synthetic": True,
        "evidence": {
            "id": case["evidence_id"], "publisher": case["publisher"],
            "headline": case["headline"], "published_day": case["published_day"],
            "observed_at": case["observed_at"], "source_url": case["original_url"],
            "jpeg_sha256": case["evidence_digest"], "status": "VERIFIED_ORIGINAL_PAGE",
            "image": "/api/case-image",
        },
        "ai": {
            "run_id": ai["run_id"], "model": ai["model"],
            "recorded_at": ai["recorded_at"], "inference_seconds": ai["inference_seconds"],
            "fact": ai["facts"], "impact": ai["inference"],
            "unknowns": ai["unknowns"], "alternatives": ai["alternatives"],
            "recommendation": ai["recommendation"],
            "fresh_since_page_load": False,
            "human_review": "NOT_APPROVED_BY_MODEL",
        },
        "approval": {
            "authenticated": authenticated,
            "state": ("OWNER_REVIEW_REQUIRED" if not decisions
                      else "OWNER_DECISION_RECORDS_AVAILABLE"),
            "drafts": decisions, "audit_integrity": audit_integrity,
            "action_execution_requires_owner": True,
            "production_approval": False,
        },
        "report": {
            "status": "HISTORICAL_SOURCE_WORD_ONLY",
            "source_docx_url": "/api/case-report",
            "ai_run_bound_word_pdf_available": False,
            "production_daily_report_available": False,
        },
        "operations": {"smtp_sent": False, "external_actions": False,
                       "customer_data_live": False, "agent_runtime": "LOCAL_QA"},
    }
