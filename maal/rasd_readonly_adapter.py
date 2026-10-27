"""MA'AL Gate G2 PRE-ACCEPTANCE: pure source-verified read-only adapter.

NO network, Gmail, CAS, SMTP, storage writes, production RASD access,
approval or execution. Historical owner-export fixture only until Gate H.
No model call; a real-model source-policy change requires a new review.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,date,timezone
from hashlib import sha256
from typing import Mapping
from urllib.parse import urlsplit
import re
from maal.decision_contracts import Evidence

FIELDS=frozenset({
 "schema_version","item_id","verification_status","timeliness",
 "publisher","source_url","published_at","published_precision",
 "observed_at","original_capture_sha256","finding",
 "source_conflict_status","authorized_sector_tags"
})
SHAREABLE_KEYS=frozenset({"infrastructure_finance","renewable_energy","policy_monitoring"})
HEX=re.compile(r"^[0-9a-f]{64}$")
MAX_AGE_DAYS=366

class RASDExportHold(ValueError):
    """Safe stop; never promote unverifiable publisher data."""

@dataclass(frozen=True)
class TrustedReceipt:
    """Independently verified Gate E owner receipt; not supplied by untrusted RSS."""
    item_id:str
    publisher:str
    source_url:str
    finding:str
    published_at:date|datetime
    observed_at:datetime
    original_capture_sha256:str

def _date(value, precision):
    try:
        if precision=="DATE_ONLY":
            if not isinstance(value,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",value):
                raise RASDExportHold("publication_precision_mismatch")
            return date.fromisoformat(value)
        if precision=="DATETIME":
            out=datetime.fromisoformat(value)
            if out.tzinfo is None or out.utcoffset() is None:
                raise RASDExportHold("ambiguous_publisher_time")
            return out
    except (TypeError,ValueError) as e:
        raise RASDExportHold("invalid_source_published_at") from e
    raise RASDExportHold("unrecognized_published_precision")

def _utc(value):
    try:
        d=datetime.fromisoformat(value)
        if d.tzinfo is None or d.utcoffset() is None:
            raise RASDExportHold("ambiguous_observation_clock")
        return d.astimezone(timezone.utc)
    except (TypeError,ValueError) as e:
        raise RASDExportHold("invalid_observed_at") from e

def adapt_historical_export(
    export:Mapping,
    *,
    trusted:Mapping[str,TrustedReceipt],
    original_jpeg:bytes,
    now:datetime,
)->Evidence:
    """No path read: bytes of original JPEG must be provided by trusted QA caller."""
    if not isinstance(export,dict) or set(export)!=FIELDS:
        raise RASDExportHold("export_schema_or_extra_fields_denied")
    if export["schema_version"]!="MAAL_RASD_EVIDENCE_V1":
        raise RASDExportHold("unrecognized_schema_version")
    if export["timeliness"]!="HISTORICAL":
        raise RASDExportHold("LIVE_SIGNALS_DISABLED_UNTIL_GATE_H_AND_PRODUCTION_REVIEW")
    if export["verification_status"]!="VERIFIED_ORIGINAL_PAGE":
        raise RASDExportHold("publisher_evidence_unverified")
    if export["source_conflict_status"]!="NONE":
        raise RASDExportHold("unresolved_publisher_conflict")
    labels=export["authorized_sector_tags"]
    if (not isinstance(labels,list) or not labels or
        not all(isinstance(x,str) for x in labels) or
        len(labels)!=len(set(labels)) or not set(labels).issubset(SHAREABLE_KEYS)):
        raise RASDExportHold("unauthorized_or_duplicate_sector")
    identifier=export["item_id"]
    if not isinstance(identifier,str) or identifier not in trusted:
        raise RASDExportHold("unrecognized_independently_verified_receipt")
    t=trusted[identifier]
    url=export["source_url"]
    try:p=urlsplit(url)
    except ValueError as e:raise RASDExportHold("unapproved_original_host") from e
    tp=urlsplit(t.source_url)
    if (p.scheme!="https" or p.hostname!=tp.hostname or p.hostname not in
        {"mped.gov.eg"} or p.username or p.password or p.fragment or p.port not in (None,443)):
        raise RASDExportHold("unapproved_original_host")
    published=_date(export["published_at"],export["published_precision"])
    observed=_utc(export["observed_at"])
    if (not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None):
        raise RASDExportHold("invalid_current_clock")
    current=now.astimezone(timezone.utc)
    if observed>current or (current-observed).days>MAX_AGE_DAYS:
        raise RASDExportHold("observation_future_or_unacceptably_old")
    if (type(t.published_at)!=type(published) or t.published_at!=published or
        t.observed_at.astimezone(timezone.utc)!=observed or
        export["publisher"]!=t.publisher or
        url!=t.source_url or
        export["finding"]!=t.finding):
        raise RASDExportHold("publisher_receipt_conflict")
    digest=export["original_capture_sha256"]
    if (not isinstance(digest,str) or not HEX.fullmatch(digest) or
        digest!=t.original_capture_sha256 or
        not isinstance(original_jpeg,bytes) or len(original_jpeg)<1000 or
        not original_jpeg.startswith(b"\xff\xd8") or
        sha256(original_jpeg).hexdigest()!=digest):
        raise RASDExportHold("original_binary_not_independently_verified")
    e=Evidence(identifier,t.publisher,t.source_url,t.finding,published,
               observed,t.original_capture_sha256,"VERIFIED_ORIGINAL_PAGE")
    e.validate()
    return e

def adapt_historical_batch(
    exports:list[dict],
    *,trusted:Mapping[str,TrustedReceipt],original_jpegs:Mapping[str,bytes],
    now:datetime,
)->tuple[Evidence,...]:
    if not isinstance(exports,list) or not 1<=len(exports)<=15:
        raise RASDExportHold("bounded_batch_required")
    ids=[x.get("item_id") for x in exports if isinstance(x,dict)]
    if len(ids)!=len(exports) or len(ids)!=len(set(ids)):
        raise RASDExportHold("duplicate_or_malformed_evidence_ids")
    items=tuple(adapt_historical_export(x,trusted=trusted,
      original_jpeg=original_jpegs.get(x["item_id"],b""),now=now) for x in exports)
    urls=[x.original_url for x in items]
    if len(set(urls))!=len(urls):
        raise RASDExportHold("conflicting_or_duplicate_original_urls")
    return items
