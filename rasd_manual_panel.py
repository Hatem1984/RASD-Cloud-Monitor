"""Local two-button manual RASD preview. No background schedules or mail."""
from __future__ import annotations

import json
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
                result = subprocess.run(
                    [sys.executable, str(ROOT / ACTIONS[mode][0]),
                     *ACTIONS[mode][1:]],
                    cwd=ROOT, capture_output=True, text=True, timeout=180,
                    check=False)
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

    controls = ttk.Frame(window)
    controls.pack(pady=18)
    for text, mode in (("بحث الويب", "web"), ("بحث فيسبوك", "facebook")):
        button = ttk.Button(controls, text=text, width=23,
                            command=lambda value=mode: launch(value))
        button.pack(side="left", padx=10)
        buttons.append(button)
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
