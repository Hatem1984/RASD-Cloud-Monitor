"""Owner-approved expanded RASD development/economy scope (v1).

No AI inference, no fuzzy matching, no third-party search. A piece that DOES
NOT name the Ministry can be discovered only if the ORIGINAL publisher title
contains a specific development/planning or public-investment subject AND the
original title/short publisher excerpt unambiguously locates it in Egypt.

This is discovery-only: original publication date, URL, headline, screenshot,
dedup and daily delivery gates remain mandatory and unchanged.
The gate is disabled by default on production until source QA is approved.
"""
from __future__ import annotations

import os

from monitor import _ministry_term_present

SCOPE_VERSION = "egypt_development_v1"

# Intentionally NOT generic terms ("استثمار", "البنوك", "السياحة", "اقتصاد")
# that would scoop up irrelevant business or sports stories.
PLANNING_SUBJECTS = (
    "الاستثمارات العامة",
    "الاستثمار العام",
    "استثمارات حكومية",
    "الاستثمارات الحكومية",
    "الإنفاق الاستثماري",
    "المخصصات الاستثمارية",
    "الخطة الاستثمارية",
    "خطة التنمية",
    "مشروعات تنموية",
    "المشروعات التنموية",
    "برامج التنمية المحلية",
    "التنمية الإقليمية",
    "تنمية المحافظات",
    "مشروعات البنية التحتية",
    "مشروعات الصرف الصحي",
    "مشروعات التحول الأخضر",
    "المشروعات الخضراء",
    "أهداف التنمية المستدامة",
    "مؤشرات التنمية",
    "مستهدفات النمو الاقتصادي",
    "معدل النمو الاقتصادي",
    "الناتج المحلي الإجمالي",
    "الإصلاحات الهيكلية",
    "التمويل التنموي",
    "خطة الدولة الاستثمارية",
)

EGYPT_CONTEXT = (
    "مصر", "المصري", "المصرية", "الحكومة المصرية", "الدولة المصرية",
    "المحافظات المصرية", "القاهرة", "الجيزة",
    "الإسكندرية", "السويس", "بورسعيد", "الإسماعيلية", "دمياط",
    "الدقهلية", "الشرقية", "الغربية", "المنوفية", "القليوبية",
    "البحيرة", "كفر الشيخ", "الفيوم", "بني سويف", "المنيا",
    "أسيوط", "سوهاج", "قنا", "الأقصر", "أسوان", "مطروح",
    "البحر الأحمر", "الوادي الجديد", "شمال سيناء", "جنوب سيناء",
)


def contextual_title_matches(title: str, publisher_excerpt: str = "") -> bool:
    if not isinstance(title, str) or not isinstance(publisher_excerpt, str):
        return False
    if len(title) > 500 or len(publisher_excerpt) > 1500:
        return False
    return (_ministry_term_present(title, list(PLANNING_SUBJECTS))
            and _ministry_term_present(
                title + " " + publisher_excerpt, list(EGYPT_CONTEXT)))


def scope_active(config: dict) -> bool:
    """Enable only with BOTH reviewed config and owner-controlled job flag."""
    return (config.get("context_scope") == SCOPE_VERSION
            and os.environ.get("RASD_CONTEXT_SCOPE_ENABLED") == "true")
