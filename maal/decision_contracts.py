"""MA'AL Gate D: evidence-to-decision data contract (offline, no actions).

This is a proposal validator, NOT an AI analyst, publisher verifier, or
financial model. A VERIFIED_ORIGINAL_PAGE status must come from a separately
tested RASD original-page verifier, not from an AI assertion.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import urlsplit

ALLOWED_PROPOSALS = frozenset({"draft_alert", "draft_task", "draft_report"})


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    publisher: str
    original_url: str
    claim: str
    published_at: date | datetime
    observed_at: datetime
    original_page_sha256: str
    status: str

    def validate(self) -> None:
        parsed = urlsplit(self.original_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("original_evidence_https_required")
        if not all((self.evidence_id.strip(), self.publisher.strip(), self.claim.strip())):
            raise ValueError("evidence_identity_or_claim_missing")
        # Official publisher dates may be day-only. Never invent an hour.
        if isinstance(self.published_at, datetime):
            if (self.published_at.tzinfo is None or
                    self.published_at.utcoffset() is None):
                raise ValueError("ambiguous_evidence_timestamp")
        elif type(self.published_at) is not date:
            raise ValueError("invalid_evidence_publication_date")
        if (self.observed_at.tzinfo is None or
                self.observed_at.utcoffset() is None):
            raise ValueError("ambiguous_evidence_timestamp")
        if self.status != "VERIFIED_ORIGINAL_PAGE":
            raise ValueError("unverified_evidence_cannot_support_decision")
        if len(self.original_page_sha256) != 64 or any(
                c not in "0123456789abcdef" for c in self.original_page_sha256):
            raise ValueError("original_page_checksum_required")


@dataclass(frozen=True)
class BusinessContext:
    company_key: str
    sector: str
    market: str

    def validate(self) -> None:
        if not all((self.company_key.strip(), self.sector.strip(), self.market.strip())):
            raise ValueError("company_context_missing")


@dataclass(frozen=True)
class ProposedAction:
    kind: str
    description: str
    supporting_evidence_ids: tuple[str, ...]
    cost_estimate: Decimal | None = None
    cost_currency: str | None = None
    cost_basis_evidence_id: str | None = None

    def validate(self, available_ids: set[str]) -> None:
        if self.kind not in ALLOWED_PROPOSALS or not self.description.strip():
            raise ValueError("unsafe_or_empty_proposed_action")
        if not self.supporting_evidence_ids or not set(self.supporting_evidence_ids).issubset(available_ids):
            raise ValueError("proposed_action_lacks_verified_evidence")
        if self.cost_estimate is not None:
            if (not self.cost_estimate.is_finite() or self.cost_estimate < 0 or
                    not self.cost_currency or
                    self.cost_basis_evidence_id not in available_ids):
                raise ValueError("ungrounded_financial_estimate")
        elif self.cost_currency is not None or self.cost_basis_evidence_id is not None:
            raise ValueError("partial_financial_estimate")


def draft_decision_brief(context: BusinessContext, evidence: tuple[Evidence, ...],
                         actions: tuple[ProposedAction, ...]) -> dict:
    """Validate an externally prepared proposal; NEVER take an external action."""
    context.validate()
    if not evidence or not actions:
        raise ValueError("decision_requires_evidence_and_options")
    ids = [item.evidence_id for item in evidence]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate_evidence_identity")
    for item in evidence:
        item.validate()
    allowed = set(ids)
    for action in actions:
        action.validate(allowed)
    return {
        "product": "MA'AL",
        "status": "DRAFT_REQUIRES_HUMAN_APPROVAL",
        "business": {
            "company_key": context.company_key,
            "sector": context.sector,
            "market": context.market,
        },
        "facts_from_verified_inputs": [
            {"evidence_id": e.evidence_id, "claim": e.claim,
             "publisher": e.publisher, "original_url": e.original_url,
             "published_at": e.published_at.isoformat(),
             "publication_precision": ("date" if type(e.published_at) is date else "datetime"),
             "observed_at": e.observed_at.isoformat(),
             "original_page_sha256": e.original_page_sha256}
            for e in evidence
        ],
        "proposals_not_executed": [
            {"action_type": a.kind,
             "description": a.description,
             "supporting_evidence_ids": list(a.supporting_evidence_ids),
             "cost_estimate": str(a.cost_estimate) if a.cost_estimate is not None else None,
             "cost_currency": a.cost_currency,
             "cost_basis_evidence_id": a.cost_basis_evidence_id}
            for a in actions
        ],
        "business_impact": "NOT_ESTIMATED_WITHOUT_COMPANY_BASELINE",
        "confidence": "NOT_SCORED",
        "human_approval_required": True,
        "external_actions_executed": False,
        "verification_notice": "Input evidence must be independently validated by RASD.",
    }
