"""Owner-approved numbered daily Word delivery with fail-closed private CAS.

Production release remains OFF by default. Before any SMTP action:
- all verified, lossless Word volumes exist within bounded attachment sizes;
- every JPEG SHA inside each Word still matches its delivered-original proof;
- master day key and EVERY numbered part are reserved in ONE private CAS;
- existing day, part or article collision blocks all delivery.

Partial SMTP acceptance is a MANUAL RECONCILIATION HOLD: never resend.
No attempt to infer Inbox delivery from SMTP acceptance.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from pathlib import Path

from cloud_proof_report import word_images_match_capture_digests
from delivery_bridge import complete_entry, now_iso, reserve_entry

MAX_VOLUMES = 32
MAX_PART_BYTES = 7_500_000
HEX24 = re.compile(r"[0-9a-f]{24}")
HEX64 = re.compile(r"[0-9a-f]{64}")


def _part_key(master_key: str, part_number: int) -> str:
    if not HEX24.fullmatch(master_key) or not 1 <= part_number <= MAX_VOLUMES:
        raise ValueError("daily_volume_key_invalid")
    return hashlib.sha256(
        (f"rasd-daily-volume-v1:{master_key}:part:{part_number}").encode()
    ).hexdigest()[:24]


def verify_volume_manifest(volumes: list[dict]) -> list[dict]:
    if not isinstance(volumes,list) or not 1 <= len(volumes) <= MAX_VOLUMES:
        raise RuntimeError("daily_volume_count_invalid")
    result=[]
    seen=set()
    total=len(volumes)
    for index,v in enumerate(volumes,start=1):
        if (not isinstance(v,dict)
                or v.get("part")!=index or v.get("parts")!=total
                or not isinstance(v.get("article_ids"),list)
                or not isinstance(v.get("sha256"),list)
                or type(v.get("count")) is not int
                or v["count"]!=len(v["article_ids"])
                or v["count"]!=len(v["sha256"])
                or not 1<=v["count"]<=360):
            raise RuntimeError("daily_volume_manifest_invalid")
        ids=v["article_ids"]
        shas=v["sha256"]
        if (any(not isinstance(x,str) or HEX24.fullmatch(x) is None
                for x in ids)
                or len(set(ids))!=len(ids)
                or any(i in seen for i in ids)
                or any(not isinstance(d,str) or HEX64.fullmatch(d) is None
                       for d in shas)):
            raise RuntimeError("daily_volume_manifest_identity_hold")
        seen.update(ids)
        path=Path(v["path"])
        if (not path.is_file()
                or not 3000<=path.stat().st_size<=MAX_PART_BYTES
                or v.get("bytes")!=path.stat().st_size):
            raise RuntimeError("daily_volume_attachment_size_hold")
        proofs=[{"status":"verified","sha256":d} for d in shas]
        if not word_images_match_capture_digests(path,proofs):
            raise RuntimeError("daily_volume_original_image_mismatch_hold")
        result.append({
            "path":path,"part":index,"parts":total,"count":len(ids),
            "article_ids":ids[:],"sha256":shas[:],
            "word_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    if len(seen)>360:
        raise RuntimeError("daily_volume_total_exceeds_360_hold")
    return result


def reserve_daily_volume_plan(ledger, recipient: str,
                              master_key: str, manifest: list[dict]) -> list[str]:
    if not isinstance(recipient,str) or not recipient.strip():
        raise ValueError("daily_volume_recipient_missing")
    if not HEX24.fullmatch(master_key):
        raise ValueError("daily_volume_rollup_key_invalid")
    state,sha=ledger.read()
    recipient_digest=hashlib.sha256(
        recipient.strip().casefold().encode("utf-8")).hexdigest()
    if not hmac.compare_digest(recipient_digest,
                               state["approved_recipient_sha256"]):
        raise ValueError("recipient_not_approved_by_private_ledger")
    keys=[_part_key(master_key,i) for i in range(1,len(manifest)+1)]
    if master_key in state["entries"] or any(k in state["entries"] for k in keys):
        raise RuntimeError("daily_volume_plan_already_reserved_manual_reconcile")
    stamp=now_iso()
    planned,action=reserve_entry(state,master_key,stamp)
    if action!="reserved":
        raise RuntimeError("daily_volume_plan_already_reserved_manual_reconcile")
    planned["entries"][master_key].update({
        "kind":"daily_volume_plan","parts":len(keys),"part_keys":keys,
        "article_count":sum(v["count"] for v in manifest),
    })
    for index,(key,vol) in enumerate(zip(keys,manifest),start=1):
        planned,action=reserve_entry(planned,key,stamp)
        if action!="reserved":
            raise RuntimeError("daily_volume_part_collision_manual_reconcile")
        planned["entries"][key].update({
            "kind":"daily_volume_part","part":index,"total_parts":len(keys),
            "article_ids":vol["article_ids"],
            "word_sha256":vol["word_sha256"],
        })
    # ONE private CAS/readback before ANY SMTP, not one reservation per part.
    ledger.write(planned,sha)
    return keys


def deliver_numbered_daily_volumes(
    volumes: list[dict], *, ledger, master_key: str,
    sender: str, recipient: str, password: str, title: str,
    send_one_word,
) -> dict:
    """Single approved recipient policy; attachments are 1 Word per message.

    No automatic retries. A failed SMTP or persistence call leaves the day
    reservation in protected state and requires a human to reconcile Sent.
    """
    manifest=verify_volume_manifest(volumes)
    if not isinstance(title,str) or not title.strip():
        raise ValueError("daily_volume_subject_invalid")
    keys=reserve_daily_volume_plan(ledger,recipient,master_key,manifest)
    receipts=[]
    for key,vol in zip(keys,manifest):
        # Check bytes immediately before handing them to SMTP.
        if hashlib.sha256(vol["path"].read_bytes()).hexdigest()!=vol["word_sha256"]:
            raise RuntimeError("daily_volume_attachment_changed_after_reservation")
        index=vol["part"]
        total=vol["parts"]
        subject=f"{title} | الجزء {index} من {total}"
        message=(
            f"رصد — التقرير اليومي المجمع، الجزء {index} من {total}.\n"
            "هذا الملف يضم تغطيات سبق قبول إرسالها بصورها الأصلية. "
            "لا تكتمل مجموعة التقرير اليومي إلا بوصول جميع الأجزاء. "
            "يرجى عدم اعتبار قبول SMTP دليلاً منفردًا على الاستلام."
        )
        receipt=send_one_word(
            vol["path"],sender=sender,recipient=recipient,password=password,
            subject=subject,key=key,body_text=message)
        # Only mark a specific numbered part after its own SMTP acceptance.
        # Failure here is uncertain; DO NOT retry this part or the batch.
        ledger.mark_smtp_accepted(key,receipt)
        receipts.append(receipt)

    state,sha=ledger.read()
    if (state["entries"].get(master_key,{}).get("status")!="reserved"
            or any(state["entries"].get(key,{}).get("status")!="smtp_accepted"
                   or state["entries"][key].get("message_id")!=receipts[i]
                   for i,key in enumerate(keys))):
        raise RuntimeError("daily_volume_receipt_reconciliation_hold")
    # Master is a receipt SUMMARY for several real mails, not one fabricated
    # email. The real Message-IDs of all accepted parts are attached too.
    completed=complete_entry(state,master_key,now_iso(),receipts[-1])
    completed["entries"][master_key].update({
        "kind":"daily_volume_plan",
        "part_message_ids":receipts,
        "all_parts_smtp_accepted":True,
    })
    ledger.write(completed,sha)
    return {
        "status":"daily_volume_parts_smtp_accepted_unconfirmed_inbox",
        "parts":len(keys),"items":sum(x["count"] for x in manifest),
        "smtp_accepted":True,"inbox_delivery_verified":False,
    }
