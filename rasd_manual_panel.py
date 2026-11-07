"""Local two-button manual RASD preview. No background schedules or mail."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from queue import Empty, Queue


ROOT = Path(__file__).resolve().parent
ACTIONS = {
    "web": ["rasd_manual_web.py"],
    "facebook": ["facebook_pilot.py", "--live"],
}


def main() -> None:
    import tkinter as tk
    from tkinter import ttk

    window = tk.Tk()
    window.title("رصد — البحث اليدوي")
    window.geometry("630x310")
    events = Queue()
    running = {"value": False}

    ttk.Label(window, text="رصد | تجارب البحث المنفصلة",
              font=("Tahoma", 16, "bold")).pack(pady=15)
    ttk.Label(window, text="الويب: مسودة RSS فقط | فيسبوك: صفحات Meta المصرح بها",
              font=("Tahoma", 10)).pack(pady=4)
    ttk.Label(window, text="لا يوجد إرسال بريد أو ربط بالسجل الإنتاجي في أي مسار.",
              font=("Tahoma", 10)).pack(pady=4)
    status = tk.StringVar(value="اختر مسار البحث اليدوي.")
    buttons = []

    def launch(mode: str) -> None:
        if running["value"]:
            return
        running["value"] = True
        for button in buttons:
            button.state(["disabled"])
        status.set("جارٍ تشغيل البحث اليدوي...")
        def work() -> None:
            try:
                child_env = os.environ.copy()
                if mode == "web":
                    # The web process never needs the Facebook Page credential.
                    child_env.pop("RASD_FB_PAGE_TOKEN", None)
                result = subprocess.run(
                    [sys.executable, str(ROOT / ACTIONS[mode][0]),
                     *ACTIONS[mode][1:]],
                    cwd=ROOT, capture_output=True, text=True, timeout=180,
                    env=child_env, check=False)
                payload = json.loads(result.stdout.strip().splitlines()[-1])
                if result.returncode == 0:
                    message = (payload.get("status", "تم")
                               + "\n" + payload.get("word", ""))
                elif mode == "facebook":
                    message = ("فيسبوك HOLD: مطلوب Meta Page token "
                               "وقائمة صفحات معتمدة؛ لم يتم بحث أو إرسال.")
                else:
                    message = "بحث الويب HOLD: تعذّر إنشاء المسودة."
            except Exception:
                message = "تعذّر إتمام البحث اليدوي؛ لم يتم إرسال أي بريد."
            events.put(message)
        threading.Thread(target=work, daemon=True).start()

    def web_choices() -> None:
        popup = tk.Toplevel(window)
        popup.title("رصد | الويب")
        popup.geometry("490x175")
        ttk.Label(popup, text="اختار طريقة بحث الويب:",
                  font=("Tahoma", 11, "bold")).pack(pady=12)

        def rss_preview() -> None:
            popup.destroy()
            launch("web")

        def expanded_manual() -> None:
            popup.destroy()
            child_env = os.environ.copy()
            child_env.pop("RASD_FB_PAGE_TOKEN", None)
            try:
                subprocess.Popen(
                    [sys.executable, str(ROOT / "rasd_expanded_web_manual.py")],
                    cwd=ROOT, env=child_env)
                status.set("تم فتح استكشاف مصادر الويب الـ50 يدويًا.")
            except OSError:
                status.set("تعذر فتح نافذة استكشاف مصادر الويب.")

        ttk.Button(popup, text="إنشاء مسودة RSS من المصادر الـ13",
                   command=rss_preview).pack(pady=5)
        ttk.Button(popup, text="البحث اليدوي في سجل المصادر الـ50",
                   command=expanded_manual).pack(pady=5)

    def facebook_choices() -> None:
        popup = tk.Toplevel(window)
        popup.title("رصد | فيسبوك")
        popup.geometry("490x185")
        ttk.Label(popup, text="اختار طريقة متابعة فيسبوك:",
                  font=("Tahoma", 11, "bold")).pack(pady=12)

        def manual_capture() -> None:
            popup.destroy()
            child_env = os.environ.copy()
            child_env.pop("RASD_FB_PAGE_TOKEN", None)
            try:
                subprocess.Popen(
                    [sys.executable, str(ROOT / "facebook_manual_evidence.py")],
                    cwd=ROOT, env=child_env)
                status.set("تم فتح نافذة توثيق لقطات فيسبوك يدويًا.")
            except OSError:
                status.set("تعذر فتح نافذة توثيق فيسبوك.")

        def approved_api() -> None:
            popup.destroy()
            launch("facebook")

        ttk.Button(popup, text="توثيق لقطات شاشة من نتائج بحثك",
                   command=manual_capture).pack(pady=5)
        ttk.Button(popup, text="بحث API في صفحات معتمدة فقط",
                   command=approved_api).pack(pady=5)

    controls = ttk.Frame(window)
    controls.pack(pady=18)
    web_button = ttk.Button(controls, text="بحث الويب", width=23,
                            command=web_choices)
    web_button.pack(side="left", padx=10)
    buttons.append(web_button)
    fb_button = ttk.Button(controls, text="بحث فيسبوك", width=23,
                          command=facebook_choices)
    fb_button.pack(side="left", padx=10)
    buttons.append(fb_button)
    ttk.Label(window, textvariable=status, wraplength=585,
              justify="center", font=("Tahoma", 10)).pack(pady=12)

    def poll() -> None:
        try:
            message = events.get_nowait()
        except Empty:
            pass
        else:
            status.set(message)
            running["value"] = False
            for button in buttons:
                button.state(["!disabled"])
        window.after(150, poll)
    poll()
    window.mainloop()


if __name__ == "__main__":
    main()
