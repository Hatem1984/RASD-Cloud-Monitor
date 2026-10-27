"""MA'AL G3: pluggable evidence-constrained AI draft analyzer.

No live models or paid services enabled automatically. Production actions
are entirely absent from the AI interface. The output is a proposal only.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol, Any
from urllib.request import Request, urlopen
from urllib.error import URLError
from datetime import date, datetime

from maal.decision_contracts import Evidence, BusinessContext

ALLOWED_EVIDENCE_IDS = re.compile(r"^[a-zA-Z0-9._:\-]{5,160}$")
ALLOWED_VERIFIERS = frozenset({"official_publisher_original", "rasd_original_page_screenshot", "await_human_review"})

class ModelUnavailable(RuntimeError):
    pass

class Provider(Protocol):
    def propose(self, prompt: str) -> dict[str, Any]: ...

@dataclass(frozen=True)
class CompanyProfile:
    context: BusinessContext
    objective: str
    relevant_sectors: tuple[str,...]
    synthetic: bool = True

    def validate(self):
        self.context.validate()
        if not self.objective.strip() or len(self.objective) > 500:
            raise ValueError("missing_company_goal")
        if not self.relevant_sectors or not all(s.strip() for s in self.relevant_sectors):
            raise ValueError("missing_company_exposure")
        # No real customer analysis until data permissions and baselines exist.
        if not self.synthetic:
            raise ValueError("real_client_analysis_requires_authorization_and_baseline")

class LocalOllamaProvider:
    """Optional existing localhost Ollama provider, never installed by this module."""
    def __init__(self, model: str):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:\-]{1,90}",model):
            raise ValueError("invalid_local_model_name")
        self.model=model
    def propose(self,prompt: str)->dict:
        payload=json.dumps({
            "model":self.model,"prompt":prompt,"stream":False,
            "format":"json","options":{"temperature":0,"num_predict":900}
        },ensure_ascii=False).encode("utf8")
        request=Request("http://127.0.0.1:11434/api/generate",data=payload,method="POST",
                        headers={"Content-Type":"application/json"})
        try:
            with urlopen(request,timeout=45) as response:
                reply=json.load(response)
        except (OSError,URLError,TimeoutError) as ex:
            raise ModelUnavailable("local_ollama_unavailable_no_ai_result") from ex
        if not isinstance(reply,dict) or not reply.get("response"):
            raise ModelUnavailable("local_ollama_no_valid_response")
        try:return json.loads(reply["response"])
        except (ValueError,TypeError) as ex:
            raise ValueError("model_output_not_json") from ex

def analyze(profile:CompanyProfile, evidences:tuple[Evidence,...], provider:Provider)->dict:
    profile.validate()
    if not evidences:raise ValueError("verified_evidence_required")
    for e in evidences:e.validate()
    ids={e.evidence_id for e in evidences}
    if len(ids)!=len(evidences) or not all(ALLOWED_EVIDENCE_IDS.fullmatch(i) for i in ids):
        raise ValueError("invalid_or_duplicate_evidence_ids")
    inputs=[{
        "evidence_id":e.evidence_id,"claim":e.claim,"publisher":e.publisher,
        "original_url":e.original_url,"published_at":e.published_at.isoformat(),
        "publication_precision":"date" if type(e.published_at) is date else "datetime",
        "observed_at":e.observed_at.isoformat(),"sha256":e.original_page_sha256
    } for e in evidences]
    instructions={
      "task":"Analyze a verified historical signal for a SYNTHETIC company in Arabic.",
      "constraints":[
          "Cite evidence IDs exactly as provided; distinguish fact, inference and unknown.",
          "Do NOT state funding eligibility, financial gains or implementation outcomes.",
          "Do NOT claim an action was approved or executed.",
          "Suggest verifier only from allowed_verifiers, but do not call it.",
          "Return a JSON object only with fields: evidence_ids (array), relevant_to_company (boolean), "
          "facts (array of exact input claims), hypothesis (string), unknowns (array of strings), "
          "alternatives (array of strings), recommendation (string), verify_with (string), "
          "financial_estimate (null), executed (false), approved (false)."
      ],
      "profile":{"company_key":profile.context.company_key,
                 "sector":profile.context.sector,"market":profile.context.market,
                 "goal":profile.objective,"exposures":profile.relevant_sectors,
                 "synthetic":True},
      "verified_inputs":inputs,
      "allowed_verifiers":sorted(ALLOWED_VERIFIERS)
    }
    raw=provider.propose(json.dumps(instructions,ensure_ascii=False))
    if not isinstance(raw,dict) or set(raw)!={
        "evidence_ids","relevant_to_company","facts","hypothesis","unknowns",
        "alternatives","recommendation","verify_with","financial_estimate",
        "executed","approved"}:
        raise ValueError("invalid_ai_output_schema")
    linked=raw["evidence_ids"]
    if not isinstance(linked,list) or not linked or not set(linked).issubset(ids) or len(set(linked))!=len(linked):
        raise ValueError("model_cited_unverified_evidence")
    facts=raw["facts"]
    if not isinstance(facts,list) or not facts or not set(facts).issubset({e.claim for e in evidences}):
        raise ValueError("model_invented_factual_claim")
    if not isinstance(raw["relevant_to_company"],bool):
        raise ValueError("model_relevance_not_boolean")
    for field in ("hypothesis","recommendation"):
        if not isinstance(raw[field],str) or not raw[field].strip() or len(raw[field])>1800:
            raise ValueError("invalid_ai_narrative")
    for field in ("unknowns","alternatives"):
        value=raw[field]
        if not isinstance(value,list) or not value or any(
            not isinstance(x,str) or not x.strip() or len(x)>600 for x in value):
            raise ValueError("missing_ai_uncertainty_or_alternatives")
    if (raw["verify_with"] not in ALLOWED_VERIFIERS
        or raw["financial_estimate"] is not None
        or raw["executed"] is not False or raw["approved"] is not False):
        raise ValueError("ai_attempted_to_exceed_authority")
    return {
        "status":"AI_DRAFT_UNREVIEWED",
        "company_is_synthetic":True,
        "verified_evidence_ids":linked,
        "facts_exact_from_evidence":facts,
        "inference":raw["hypothesis"],
        "unknowns":raw["unknowns"],
        "alternatives":raw["alternatives"],
        "recommendation_draft":raw["recommendation"],
        "verifier_suggested_not_executed":raw["verify_with"],
        "human_approval_required":True,
        "action_executed":False,
        "model_output_requires_factual_human_review":True,
    }
