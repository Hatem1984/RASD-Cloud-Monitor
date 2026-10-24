"""Consolidate previously EMAILED original-photo Word bulletins, not re-captured webpages.

One sender's authenticated Gmail Sent mailbox is the immutable original report
archive. The private CAS ledger fixes which Message-IDs and story IDs are eligible.
No deleting, marking read, email sending, or filesystem persistence beyond temp.
"""
from __future__ import annotations

import hashlib
import imaplib
import re
import ssl
from collections import defaultdict
from email import message_from_bytes, policy
from email.utils import getaddresses, parseaddr
from pathlib import Path

from docx import Document
from capture_public import image_quality
from cloud_proof_report import word_images_match_capture_digests
from daily_report import render_docx


def sent_mailbox(client) -> None:
    status, items = client.list()
    if status != "OK" or not items:
        raise RuntimeError("daily_sent_folder_list_hold")
    names = []
    for raw in items:
        if not isinstance(raw, bytes) or b"\\Sent" not in raw:
            continue
        value = raw.decode("utf-8", "replace")
        match = re.search(r'"([^"]+)"\s*$', value)
        if match:
            names.append(match.group(1))
    if len(names) != 1:
        raise RuntimeError("daily_sent_folder_identity_hold")
    folder = '"' + names[0].replace("\\", "\\\\").replace('"', '\\"') + '"'
    status, _ = client.select(folder, readonly=True)
    if status != "OK":
        raise RuntimeError("daily_sent_folder_select_hold")


def original_sent_word(client, message_id: str, sender: str,
                       recipient: str, *, max_bytes: int = 8_000_000) -> bytes:
    if not re.fullmatch(r"<rasd-[0-9a-f]{24}@gmail\.com>", message_id):
        raise RuntimeError("daily_sent_message_identity_hold")
    status, ids = client.uid("SEARCH", None, "HEADER", "Message-ID",
                             '"' + message_id + '"')
    if status != "OK" or not ids or not ids[0]:
        raise RuntimeError("daily_sent_message_not_found")
    found = ids[0].split()
    if len(found) != 1 or not found[0].isdigit():
        raise RuntimeError("daily_sent_message_ambiguous")
    status, responses = client.uid("FETCH", found[0], "(RFC822)")
    if status != "OK" or not responses:
        raise RuntimeError("daily_sent_message_fetch_hold")
    binaries = [row[1] for row in responses
                if isinstance(row, tuple) and len(row) == 2
                and isinstance(row[1], bytes)]
    if len(binaries) != 1 or len(binaries[0]) > 16_000_000:
        raise RuntimeError("daily_sent_message_size_hold")
    msg = message_from_bytes(binaries[0], policy=policy.default)
    if (msg.get("Message-ID") != message_id
            or parseaddr(str(msg.get("From", "")))[1].lower() != sender.lower()
            or [x.lower() for _, x in getaddresses(
                msg.get_all("To", []))] != [recipient.lower()]
            or msg.get("X-RASD-Delivery-ID") != message_id[6:30]):
        raise RuntimeError("daily_sent_message_headers_hold")
    if not msg.is_multipart():
        raise RuntimeError("daily_sent_attachment_missing")
    attachments = [
        part.get_payload(decode=True) for part in msg.walk()
        if part.get_content_disposition() == "attachment"
        and part.get_filename() == "RASD-News-With-Original-Screenshots.docx"
        and part.get_content_type() ==
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    if (len(attachments) != 1 or not isinstance(attachments[0], bytes)
            or not 3000 <= len(attachments[0]) <= max_bytes):
        raise RuntimeError("daily_sent_attachment_identity_hold")
    return attachments[0]


def extract_sent_originals(word_bytes: bytes, expected: list[dict],
                           output: Path) -> list[tuple[dict, str, str]]:
    if not expected or len(expected) > 15:
        raise RuntimeError("daily_sent_batch_count_hold")
    filename = output / "private-sent-original.docx"
    filename.write_bytes(word_bytes)
    try:
        document = Document(filename)
        pairs = []
        for i, paragraph in enumerate(document.paragraphs):
            match = re.fullmatch(r"([1-9][0-9]?)\. (.+)", paragraph.text.strip())
            if match:
                pairs.append((i, int(match.group(1)), match.group(2)))
        if ([n for _, n, _ in pairs] != list(range(1, len(expected) + 1))
                or [name for _, _, name in pairs] !=
                    [a["headline"] for a in expected]):
            raise RuntimeError("daily_sent_original_headlines_hold")
        urls = {
            rel.target_ref for rel in document.part.rels.values()
            if rel.reltype.endswith("/hyperlink")
        }
        if any(a["url"] not in urls for a in expected):
            raise RuntimeError("daily_sent_original_urls_hold")
        pictures = []
        for index, paragraph in enumerate(document.paragraphs):
            for node in paragraph._p.xpath(".//a:blip"):
                key = node.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                if key not in document.part.related_parts:
                    raise RuntimeError("daily_sent_image_relationship_hold")
                pictures.append((index, document.part.related_parts[key].blob))
        if len(pictures) != len(expected):
            raise RuntimeError("daily_sent_image_count_hold")
        result = []
        for i, (paragraph_index, blob) in enumerate(pictures):
            begin = pairs[i][0]
            end = pairs[i+1][0] if i+1 < len(pairs) else len(document.paragraphs)
            if not begin < paragraph_index < end:
                raise RuntimeError("daily_sent_image_order_hold")
            if len(blob) < 8000 or not blob.startswith(b"\xff\xd8"):
                raise RuntimeError("daily_sent_jpeg_signature_hold")
            destination = output / ("daily-original-" + expected[i]["id"] + ".jpg")
            destination.write_bytes(blob)
            if not image_quality(destination)["accepted"]:
                raise RuntimeError("daily_sent_jpeg_visual_hold")
            result.append((expected[i], str(destination),
                           hashlib.sha256(blob).hexdigest()))
        return result
    finally:
        filename.unlink(missing_ok=True)


def consolidate_sent_words(
    stories: list[dict], private_state: dict, output: Path, *,
    sender: str, recipient: str, app_password: str, title: str,
    start: str, end: str, config: dict,
    client_factory=None,
) -> tuple[Path, list[dict]]:
    """One Word from ONLY the original JPEGs of previously SMTP-accepted Word mails.

    Private ledger entry order is the original per-message story order. We
    explicitly verify the ordered headlines, hyperlinks and image relationships
    before releasing any merged report or reserving the daily email key.
    """
    if not stories or len(stories) > 60:
        raise RuntimeError("daily_consolidation_item_count_hold")
    wanted = {a["id"]: a for a in stories}
    if len(wanted) != len(stories):
        raise RuntimeError("daily_consolidation_duplicate_article_hold")
    accepted = defaultdict(list)
    for key, record in private_state["entries"].items():
        if key in wanted:
            if (record.get("status") != "smtp_accepted"
                    or record.get("kind") != "interval_item"
                    or record.get("news") != wanted[key]):
                raise RuntimeError("daily_consolidation_ledger_integrity_hold")
            accepted[record["message_id"]].append(record["news"])
    if sum(map(len, accepted.values())) != len(stories):
        raise RuntimeError("daily_consolidation_incomplete_private_ledger")
    output.mkdir(parents=True, exist_ok=True)
    images = []
    if client_factory is None:
        client_factory = lambda: imaplib.IMAP4_SSL(
            "imap.gmail.com", 993, ssl_context=ssl.create_default_context(),
            timeout=25)
    try:
        client = client_factory()
        try:
            status, _ = client.login(sender, app_password)
            if status != "OK":
                raise RuntimeError("daily_imap_login_hold")
            sent_mailbox(client)
            for msgid, group in accepted.items():
                data = original_sent_word(client, msgid, sender, recipient)
                images.extend(extract_sent_originals(data, group, output))
        finally:
            try:
                client.logout()
            except Exception:
                pass
    except RuntimeError:
        raise
    except (imaplib.IMAP4.error, OSError, TimeoutError):
        # Never echo SMTP/IMAP responses, raw messages or app credentials.
        raise RuntimeError("daily_imap_archive_unavailable_hold") from None
    if len(images) != len(stories):
        raise RuntimeError("daily_consolidation_missing_original_images")
    # Build the ONE daily report from the already-sent original JPEG bytes.
    by_id = {a["id"]: (filename, digest) for a, filename, digest in images}
    assembled = [{**item, "evidence_image_path": by_id[item["id"]][0]}
                 for item in stories]
    proof = [{"status": "verified", "sha256": by_id[a["id"]][1]}
             for a in stories]
    report = {
        "title": title,
        "display_window_start": start, "display_window_end": end,
        "coverage": "CONSOLIDATED_PREVIOUSLY_SENT_ORIGINALS",
        "verified_links": len(stories), "articles": assembled,
        "sources": [],
        "limitations": (
            "هذا التقرير المجمع يضم الأخبار المرسلة سابقًا خلال نافذة الرصد،"
            " مرة واحدة لكل رابط خبر، بالصور الأصلية المستخرجة من ملفات Word"
            " المرسلة فعليًا عبر البريد. لم تُلتقط الصور مجددًا من الناشرين."
            " التحليل الوارد تفسير تحريري محدود، وليس إثباتًا لقرارات أو نتائج."
            " المصادر هي قنوات RSS المعتمدة، وقد توجد أخبار خارج نطاقها."
        ),
    }
    word = output / "RASD-Daily-All-Delivered-News-Originals.docx"
    render_docx(report, word)
    if not word_images_match_capture_digests(word, proof):
        word.unlink(missing_ok=True)
        raise RuntimeError("daily_consolidated_original_digest_hold")
    if not 3000 <= word.stat().st_size <= 8_000_000:
        word.unlink(missing_ok=True)
        raise RuntimeError("daily_consolidated_word_size_hold")
    return word, proof
