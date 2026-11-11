"""Owner-driven expanded WEB research: 50 approved research origins, not feeds.

This opens a site-scoped search in the operator's browser. It does not scrape
the engine, scrape publishers, activate 37 unverified sources, send email or
claim any article screenshot is verified. The production 13 RSS feeds stay put.
"""
from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from research_source_queries import load_registry, build_query

ROOT = Path(__file__).resolve().parent


def research_search_url(source_id: str, term: str, *,
                        registry: dict | None = None,
                        keywords: list[str] | None = None) -> str:
    catalog = registry if registry is not None else load_registry()
    sources = catalog["sources"]
    match = [entry for entry in sources if entry["id"] == source_id]
    if len(match) != 1:
        raise ValueError("web_research_source_not_approved")
    source = match[0]
    # Source host validated by existing original 50-origin generator.
    build_query(source)
    words = keywords if keywords is not None else json.loads(
        (ROOT / "sources_newsroom_active.json").read_text(
            encoding="utf-8"))["keywords"]
    if term not in words:
        raise ValueError("web_research_keyword_not_approved")
    return "https://www.google.com/search?" + urlencode({
        "q": f'site:{source["publisher_host"]} "{term}"'
    })


def main() -> None:
    import tkinter as tk
    from tkinter import ttk, messagebox

    catalog = load_registry()
    sources = sorted(catalog["sources"], key=lambda e: e["priority"])
    keywords = json.loads(
        (ROOT / "sources_newsroom_active.json").read_text(
            encoding="utf-8"))["keywords"]
    root = tk.Tk()
    root.title("رصد | استكشاف مصادر الويب الـ50")
    root.geometry("735x315")
    ttk.Label(root, text="رصد — استكشاف مواقع الويب يدويًا",
              font=("Tahoma", 15, "bold")).pack(pady=14)
    ttk.Label(root, text="13 مصدر RSS في التشغيل الحالي، و37 مصدرًا للبحث والمراجعة فقط.",
              font=("Tahoma", 10)).pack(pady=7)
    labels = [
        f'{s["priority"]}. {s["name_ar"]} — '
        + ("RSS نشط" if s["research_status"] == "active_native_rss"
           else "مرشح غير مفعل")
        for s in sources
    ]
    source_choice = ttk.Combobox(root, values=labels,
                                 state="readonly", width=74)
    source_choice.current(0)
    source_choice.pack(pady=7)
    keyword_choice = ttk.Combobox(root, values=keywords,
                                  state="readonly", width=68)
    keyword_choice.current(0)
    keyword_choice.pack(pady=7)
    status = tk.StringVar(value="اختار المصدر والكلمة، ثم افتح نتائج البحث بنفسك.")

    def open_browser() -> None:
        index = source_choice.current()
        if index < 0:
            return
        try:
            url = research_search_url(
                sources[index]["id"], keyword_choice.get(),
                registry=catalog, keywords=keywords)
            if urlsplit(url).hostname != "www.google.com":
                raise ValueError("web_search_host_hold")
        except (ValueError, OSError, TypeError):
            messagebox.showerror("رصد", "المصدر أو الكلمة غير معتمدين.")
            return
        webbrowser.open(url)
        status.set("فتحت بحثًا يدويًا في متصفحك. نتائج المحرك ليست أدلة أصلية؛ "
                   "افتح الخبر على موقع الناشر قبل اعتماده.")

    ttk.Button(root, text="بحث في الويب بالمصدر المحدد",
               command=open_browser).pack(pady=10)
    ttk.Label(root, textvariable=status, wraplength=690,
              justify="center").pack(pady=8)
    ttk.Label(root, text="لا جمع آلي، ولا إرسال بريد، ولا إدخال مصادر مرشحة إلى تقرير الوزارة.",
              font=("Tahoma", 9)).pack(pady=2)
    root.mainloop()


if __name__ == "__main__":
    main()
