"""Gate 11: private delivery ledger and Gmail SMTP transport.

Public source code, but ALL delivery state and credentials stay private.
No delivery is attempted without explicit caller authorization.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from monitor import article_id
from capture_public import APPROVED_PUBLISHERS, allowed_url

PRIVATE_REPO = "Hatem1984/RASD-Pilot"
PRIVATE_BRANCH = "rasd-private-delivery-state"
PRIVATE_FILE = "delivery-state.json"
HEX_ID = re.compile(r"^[0-9a-f]{24}$")
RECIPIENT_DIGEST = re.compile(r"^[0-9a-f]{64}$")
MAX_LEDGER_ITEMS = 20000


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_ledger(state: dict) -> dict:
    if not isinstance(state, dict) or set(state) != {"schema_version", "entries", "approved_recipient_sha256"}:
        raise ValueError("invalid_private_ledger_shape")
    if (state["schema_version"] != 2 or not isinstance(state["entries"], dict)
            or not isinstance(state["approved_recipient_sha256"], str)
            or not RECIPIENT_DIGEST.fullmatch(state["approved_recipient_sha256"])):
        raise ValueError("invalid_private_ledger_version")
    if len(state["entries"]) > MAX_LEDGER_ITEMS:
        raise ValueError("private_ledger_capacity_exceeded")
    for key, item in state["entries"].items():
        if not HEX_ID.fullmatch(key) or not isinstance(item, dict):
            raise ValueError("invalid_delivery_entry")
        if item.get("status") not in ("reserved", "smtp_accepted", "hold"):
            raise ValueError("invalid_delivery_status")
        if not isinstance(item.get("reserved_at"), str):
            raise ValueError("invalid_reservation_time")
        if item["status"] == "smtp_accepted":
            if not isinstance(item.get("accepted_at"), str) or not isinstance(item.get("message_id"), str):
                raise ValueError("invalid_smtp_receipt")
    return state


def reserve_entry(state: dict, key: str, clock: str) -> tuple[dict, str]:
    """Never automatically retry an existing reservation or accepted email."""
    validate_ledger(state)
    if not isinstance(key, str) or not HEX_ID.fullmatch(key):
        raise ValueError("invalid_article_id")
    if key in state["entries"]:
        return state, "already_accepted" if state["entries"][key]["status"] == "smtp_accepted" else "manual_review_hold"
    if len(state["entries"]) >= MAX_LEDGER_ITEMS:
        raise ValueError("private_ledger_capacity_exceeded")
    new = json.loads(json.dumps(state))
    new["entries"][key] = {"status": "reserved", "reserved_at": clock}
    return new, "reserved"


def complete_entry(state: dict, key: str, clock: str, message_id: str) -> dict:
    validate_ledger(state)
    entry = state["entries"].get(key)
    if not entry or entry["status"] != "reserved":
        raise ValueError("missing_or_final_reservation")
    if not (message_id.startswith("<rasd-") and message_id.endswith(">")):
        raise ValueError("invalid_message_id")
    result = json.loads(json.dumps(state))
    result["entries"][key] = {**entry, "status": "smtp_accepted",
                               "accepted_at": clock, "message_id": message_id}
    return result


class NoGitHubRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("private_ledger_redirect_forbidden")


class PrivateGitHubLedger:
    """GitHub Contents API, separate PRIVATE repository, compare-and-swap SHA."""
    def __init__(self, token: str):
        if not token or len(token) < 16:
            raise ValueError("missing_private_ledger_credential")
        self._token = token
        self._url = ("https://api.github.com/repos/" + PRIVATE_REPO +
                     "/contents/" + PRIVATE_FILE)

    def _request(self, method: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        url = self._url + ("?ref=" + PRIVATE_BRANCH if method == "GET" else "")
        request = Request(url, method=method, data=data, headers={
            "Authorization": "Bearer " + self._token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "RASD-Gate11-private-ledger",
            "Content-Type": "application/json",
        })
        # Never log requests, exception bodies, token, or private response data.
        try:
            opener = build_opener(NoGitHubRedirect(), HTTPSHandler(context=ssl.create_default_context()))
            with opener.open(request, timeout=20) as response:
                return json.loads(response.read(3_000_000).decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError):
            raise RuntimeError("private_ledger_request_failed") from None

    def read(self) -> tuple[dict, str]:
        item = self._request("GET")
        if item.get("encoding") != "base64" or not item.get("sha"):
            raise RuntimeError("private_ledger_read_invalid")
        try:
            state = json.loads(base64.b64decode(item["content"], validate=False))
            return validate_ledger(state), item["sha"]
        except (ValueError, TypeError, KeyError):
            raise RuntimeError("private_ledger_payload_invalid") from None

    def write(self, state: dict, sha: str) -> None:
        validate_ledger(state)
        content = base64.b64encode((json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode()).decode()
        response = self._request("PUT", {"message": "gate11: update private mail acceptance ledger",
                                         "branch": PRIVATE_BRANCH, "sha": sha, "content": content})
        # A successful HTTP return alone is not evidence that the intended
        # reservation/receipt is now durable. Read it back BEFORE Gmail SMTP.
        if (not isinstance(response, dict)
                or not isinstance(response.get("commit"), dict)
                or not isinstance(response["commit"].get("sha"), str)
                or not response["commit"]["sha"]):
            raise RuntimeError("private_ledger_commit_receipt_invalid")
        actual, actual_sha = self.read()
        if actual != state or not actual_sha or actual_sha == sha:
            raise RuntimeError("private_ledger_commit_not_visible")

    def reserve(self, article_key: str, sender: str) -> str:
        state, sha = self.read()
        recipient = hashlib.sha256(sender.strip().casefold().encode("utf-8")).hexdigest()
        if not hmac.compare_digest(recipient, state["approved_recipient_sha256"]):
            raise ValueError("recipient_not_approved_by_private_ledger")
        updated, action = reserve_entry(state, article_key, now_iso())
        if action == "reserved":
            # Commit must complete BEFORE SMTP transmission.
            self.write(updated, sha)
        return action

    def mark_smtp_accepted(self, article_key: str, message_id: str) -> None:
        state, sha = self.read()
        self.write(complete_entry(state, article_key, now_iso(), message_id), sha)

    def mark_smtp_accepted_many(self, article_keys: list[str],
                                message_id: str) -> None:
        """Atomically accept one Word email containing several news articles.

        Validate ALL article reservations before the single private CAS PUT.
        If CAS/readback fails after SMTP, preserve all reservations for
        owner reconciliation; NEVER automatically send a second copy.
        """
        if (not isinstance(article_keys, list) or not 1 <= len(article_keys) <= 15
                or len(set(article_keys)) != len(article_keys)):
            raise ValueError("invalid_newsroom_email_article_batch")
        state, sha = self.read()
        for key in article_keys:
            if not isinstance(key, str) or not HEX_ID.fullmatch(key):
                raise ValueError("invalid_article_id")
            if (key not in state["entries"] or
                    state["entries"][key].get("status") != "reserved" or
                    state["entries"][key].get("kind") != "interval_item"):
                raise RuntimeError("batch_reservation_not_eligible")
        accepted_at = now_iso()
        final = state
        for key in article_keys:
            final = complete_entry(final, key, accepted_at, message_id)
        try:
            self.write(final, sha)
        except RuntimeError:
            # An accepted SMTP message is never resent. If GitHub returned an
            # ambiguous write/readback failure AFTER persisting the receipt,
            # verify the EXACT per-article acceptance and Message-ID in the
            # durable private ledger. A missing or conflicting result remains
            # a manual HOLD; this code does not retry the POST/PUT or SMTP.
            try:
                current, _ = self.read()
            except (RuntimeError, ValueError):
                raise RuntimeError(
                    "smtp_receipt_persistence_uncertain_manual_reconcile") from None
            if any(
                    current["entries"].get(key, {}).get("status") != "smtp_accepted" or
                    current["entries"][key].get("message_id") != message_id or
                    current["entries"][key].get("accepted_at") != accepted_at
                    for key in article_keys):
                raise RuntimeError(
                    "smtp_receipt_persistence_uncertain_manual_reconcile") from None


def build_email(article: dict, screenshot: bytes, sender: str) -> EmailMessage:
    """Only one sender/recipient; identity is from protected Actions secrets."""
    if not sender or not re.fullmatch(r"[^@\s]+@gmail\.com", sender, re.I):
        raise ValueError("sender_must_be_a_gmail_address")
    if article.get("selection") != "live_feed_discovery" or not article.get("published"):
        raise ValueError("historical_or_undated_article_forbidden")
    url = article.get("url", "")
    key = article.get("id", "")
    headline = article.get("headline", "")
    publisher = article.get("publisher", "")
    if key != article_id(url) or not HEX_ID.fullmatch(key):
        raise ValueError("article_fingerprint_mismatch")
    if publisher not in APPROVED_PUBLISHERS or not allowed_url(url, publisher):
        raise ValueError("untrusted_publisher_for_delivery")
    if not isinstance(headline, str) or not headline.strip() or "\r" in headline or "\n" in headline:
        raise ValueError("invalid_headline")
    if not (screenshot.startswith(b"\xff\xd8") and 8000 <= len(screenshot) <= 3_000_000):
        raise ValueError("missing_or_oversized_verified_jpeg")
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = sender
    msg["Subject"] = "رصد | " + headline.strip()[:160]
    # Stable identity helps audit; it alone does not provide transactional delivery.
    msgid = "<rasd-" + key + "@gmail.com>"
    msg["Message-ID"] = msgid
    msg["X-RASD-Article-ID"] = key
    msg.set_content("خبر جديد من مصدره الأصلي\n\n" + headline.strip() +
                    "\n\nرابط الناشر: " + url +
                    "\n\nالصورة مرفقة من صفحة الناشر الأصلية.\n")
    msg.add_attachment(screenshot, maintype="image", subtype="jpeg",
                       filename="publisher-original.jpg")
    return msg


def gmail_submit(msg: EmailMessage, sender: str, app_password: str,
                 *, smtp_factory=smtplib.SMTP_SSL) -> str:
    """Return SMTP acceptance (NOT inbox delivery). Never silently retry."""
    if not app_password:
        raise ValueError("missing_gmail_credential")
    if msg["From"] != sender or msg["To"] != sender:
        raise ValueError("recipient_not_the_approved_sender")
    if msg.get_all("Cc") or msg.get_all("Bcc"):
        raise ValueError("extra_recipients_forbidden")
    # SMTP errors are not logged, since servers can include addresses in text.
    try:
        with smtp_factory("smtp.gmail.com", 465, timeout=25,
                          context=ssl.create_default_context()) as smtp:
            smtp.login(sender, app_password)
            refused = smtp.send_message(msg, from_addr=sender, to_addrs=[sender])
            if refused:
                raise RuntimeError("smtp_recipient_refused")
    except Exception:
        raise RuntimeError("gmail_smtp_status_uncertain_check_sent_folder") from None
    return str(msg["Message-ID"])


def deliver_reserved(article: dict, image_file: Path, *,
                     sender: str, approved_recipient: str,
                     app_password: str, ledger: PrivateGitHubLedger,
                     smtp_factory=smtplib.SMTP_SSL) -> str:
    """At-most-one automatic SMTP attempt per article in private ledger.

    If SMTP or receipt persistence fails, reservation remains and future runs
    HOLD (requires human reconciliation with Gmail Sent), not resend.
    """
    if sender != approved_recipient or not sender:
        raise ValueError("approved_recipient_mismatch")
    if not image_file.is_file():
        raise ValueError("verified_image_not_available")
    message = build_email(article, image_file.read_bytes(), sender)
    action = ledger.reserve(article["id"], sender)
    if action != "reserved":
        return action
    receipt = gmail_submit(message, sender, app_password, smtp_factory=smtp_factory)
    ledger.mark_smtp_accepted(article["id"], receipt)
    return "smtp_accepted"
