"""MA'AL / RASD: deterministic evidence-bound editorial briefing (NO send).

This is an opt-in quality-review engine. It does not fetch pages, guess facts,
change delivery jobs, call an LLM or approve unverified publisher evidence.
Input can come from a verified local article or an explicitly QA-only archive.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import re

AR_DIGITS=str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹","01234567890123456789")
NUM_RE=re.compile(
    r"(?<![\w])(?:[0-9٠-٩۰-۹][0-9٠-٩۰-۹,٬.]*)\s*"
    r"(?:مليار(?:ات)?|مليون(?:ات)?|ألف|شركة|شركات|%|٪)"
    r"(?:\s*(?:دولار(?:ات)?|جنيه(?:ات)?|مصري(?:ة)?))?"
)
HOSTILE_RE=re.compile(
    r"(?i)(ignore\s+(all\s+)?(previous|prior|system)|"
    r"system\s*prompt|developer\s*instruction|"
    r"role\s*[:=]\s*(?:system|developer)|"
    r"approve\s*[:=]\s*true|executed\s*[:=]\s*true|"
    r"تجاهل\s+(?:كل\s+)?(?:التعليمات|الأوامر|النظام)|"
    r"ألغ[ِىي]\s+(?:الموافقة|القيود)|"
    r"نفذ\s+(?:التحويل|الدفع)\s+(?:فورا|فورًا))"
)
STAGE_GOAL=("نستهدف","مستهدف","تستهدف","نستهدف","استهداف","يستهدف",
            "هدف","تخطط","خطة","جارٍ إعداد","إعداد هيكل","جذب")
FINANCE=("تمويل","صندوق","رأس مال","مخاطر","ائتمان","استثمار")
STARTUPS=("شركة ناشئة","الشركات الناشئة","ريادة الأعمال","شركات ناشئة")
RULES=("تشريع","قانون","لائحة","ترخيص","تراخيص","التراخيص","تنظيم")
ECONOMIC=("نمو","صادرات","تضخم","مؤشر","مؤشرات")

class EditorialHold(ValueError):
    """Hard gate for missing publisher proof, conflicting inputs or unsafe data."""

def _clean_text(value, max_len):
    if not isinstance(value,str) or not 1<=len(value.strip())<=max_len:
        raise EditorialHold("invalid_publisher_text")
    if any(ord(c)<32 and c not in "\t\n\r" for c in value):
        raise EditorialHold("control_characters_in_evidence")
    if HOSTILE_RE.search(value):
        raise EditorialHold("untrusted_instructions_in_source")
    return " ".join(value.split())

def _scope(text):
    if any(x in text for x in STARTUPS) or any(x in text for x in FINANCE):
        return (
          "الشركات التي تبحث عن فرص تمويل أو دعم: يلزم التمييز بين إعلان نية التمويل وإتاحة برنامج يمكن التقدم إليه.",
          "راجع الموقع الرسمي للجهة المعلنة بحثًا عن شروط الأهلية والجهة المسؤولة والتوقيت؛ لا تُسجّل تمويلًا متوقعًا ضمن التدفقات النقدية قبل إعلان معتمد.",
          "لم تثبت أهلية أي شركة، ولا فتح باب التقديم أو صرف المبالغ من هذا الخبر وحده."
        )
    if any(x in text for x in RULES):
        return (
          "الشركات المتأثرة بالتنظيم: قد يستلزم الخبر مراجعة امتثال عندما يصدر نص نافذ، وليس عند مجرد مناقشة.",
          "اطلب رقم التشريع والنص المنشور وتاريخ النفاذ والجهة التنظيمية قبل تغيير إجراءات الشركة.",
          "لا توجد أدلة كافية على نفاذ حكم قانوني أو صدور ترخيص من العنوان وحده."
        )
    if any(x in text for x in ECONOMIC):
        return (
          "المؤسسات التي تراجع خططها: الأرقام والمؤشرات تحتاج فترة قياس وخط أساس قبل استنتاج أثر تشغيلي.",
          "قارن الرقم مع النشرة الإحصائية الأصلية والفترة السابقة قبل تعديل الموازنة أو الأسعار.",
          "لا يثبت الخبر وحده اتجاهًا مستدامًا أو أثرًا ماليًا على مؤسسة بعينها."
        )
    raise EditorialHold("no_business_relevance_grounded_in_source")

def _figures(text):
    result=[]
    for match in NUM_RE.finditer(text):
        anchor=match.group().strip()
        local=text[max(0,match.start()-95):min(len(text),match.end()+35)]
        kind="TARGET_OR_PLAN" if any(word in local for word in STAGE_GOAL) else "REPORTED_FIGURE_NOT_OUTCOME"
        if anchor not in [item["exact_source_span"] for item in result]:
            result.append({"exact_source_span":anchor,"assertion_type":kind,
                           "interpretation":"مستهدف أو خطة معلنة؛ لا يعني صرفًا فعليًا." if kind=="TARGET_OR_PLAN"
                            else "رقم مذكور في المصدر؛ لا نستنتج تحقق نتيجته."})
    return result[:8]

def build_editorial_brief(*, headline:str, publisher_excerpt:str,
                         original_url:str, publisher:str,
                         published_day:str, proof_status:str,
                         approved_hosts:set[str], capture_path=None,
                         capture_sha256=None)->dict:
    """Build an explainable editorial review strictly from given source text.

    VERIFIED_ORIGINAL_PAGE requires a separately checked JPEG + exact digest.
    LOCAL_ARCHIVE_QA uses previously saved Word headline/excerpt only and
    is NEVER deliverable or eligible for claims of fresh verification.
    """
    title=_clean_text(headline,500)
    if not isinstance(publisher_excerpt,str) or len(publisher_excerpt)>6000:
        raise EditorialHold("invalid_excerpt")
    excerpt=_clean_text(publisher_excerpt,6000) if publisher_excerpt.strip() else ""
    name=_clean_text(publisher,180)
    try: date.fromisoformat(published_day)
    except (TypeError,ValueError) as exc: raise EditorialHold("invalid_publication_day") from exc
    url=urlsplit(original_url)
    if (url.scheme!="https" or url.username or url.password or
        url.hostname not in approved_hosts or url.fragment or
        not isinstance(approved_hosts,(set,frozenset))):
        raise EditorialHold("unapproved_original_publisher")
    if proof_status not in ("VERIFIED_ORIGINAL_PAGE","LOCAL_ARCHIVE_QA"):
        raise EditorialHold("source_proof_missing")
    if proof_status=="VERIFIED_ORIGINAL_PAGE":
        if not isinstance(capture_sha256,str) or not re.fullmatch("[0-9a-f]{64}",capture_sha256):
            raise EditorialHold("capture_hash_missing")
        if capture_path is None or not Path(capture_path).is_file():
            raise EditorialHold("original_capture_missing")
        if hashlib.sha256(Path(capture_path).read_bytes()).hexdigest()!=capture_sha256:
            raise EditorialHold("original_capture_digest_mismatch")
    input_text=(title+" "+excerpt).casefold()
    relevance,action,uncertainty=_scope(input_text)
    figures=_figures(title+" "+excerpt)
    return {
        "schema":"RASD_EDITORIAL_BRIEF_V1",
        "qa_only":proof_status!="VERIFIED_ORIGINAL_PAGE",
        "source_verification":proof_status,
        "publisher":name,"published_day":published_day,
        "original_url":original_url,"original_headline":title,
        "source_excerpt_used":bool(excerpt),
        "source_fact":"ورد في عنوان الناشر: «"+title+"».",
        "figures_from_exact_source_spans":figures,
        "potential_business_relevance":relevance,
        "conditional_next_action":action,
        "what_is_not_established":uncertainty,
        "editorial_guardrails":[
            "الهدف أو التصريح لا يساوي تمويلًا مصروفًا أو قرارًا نافذًا.",
            "التحليل لا يؤكد أهلية تمويل أو أثرًا ماليًا على شركة بعينها.",
            "هذا تقييم مشروط بما ظهر في عنوان الناشر ومقتطفه فقط، ولا يحل محل قراءة متن الخبر."
        ],
        "no_external_actions":True,"no_email":True,
        "delivery_approved":False
    }
