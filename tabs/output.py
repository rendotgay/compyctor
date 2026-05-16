import re
import sys
import tkinter as tk
from tkinter import ttk

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    from windows_toasts import Toast
else:
    from plyer import notification

ANSI_PATTERN = re.compile(r"\x1b\[(\d+)(?:;\d+)*m")

ANSI_MAP = {
    "30": "black",
    "31": "red",
    "32": "green",
    "33": "yellow",
    "34": "blue",
    "35": "magenta",
    "36": "cyan",
    "37": "white",

    "90": "gray",
    "91": "red",
    "92": "green",
    "93": "yellow",
    "94": "blue",
    "95": "magenta",
    "96": "cyan",
    "97": "white",
}


class TerminalTab(ttk.Frame):
    def __init__(self, parent, controller, name, logs, process):
        super().__init__(parent)

        self.controller = controller
        self.name = name
        self.logs = logs
        self.process = process

        self.auto_scroll = True

        self.read_index = 0

        self.script_info = self.controller.home.rows[name]["script"]

        top = ttk.Frame(self)
        top.pack(fill="x")

        ttk.Label(top, text=name, font=("", 10, "bold")).pack(side="left", padx=5)

        self.scroll_btn = ttk.Button(
            top,
            text="AutoScroll: ON",
            command=self.toggle_scroll
        )
        self.scroll_btn.pack(side="left", padx=2)

        self.notify_var = tk.BooleanVar(value=self.script_info.get("notify_errors", False))
        self.notify_chk = ttk.Checkbutton(
            top,
            text="Notify on Errors",
            variable=self.notify_var,
            command=self.toggle_error_notifications
        )
        self.notify_chk.pack(side="left", padx=10)

        ttk.Button(
            top,
            text="← Back",
            command=self.go_back
        ).pack(side="right", padx=5, pady=2)

        self.text = tk.Text(
            self,
            wrap="word",
            bg="#111111",
            fg="#ffffff",
            insertbackground="white",
            relief="flat",
            borderwidth=0
        )
        self.text.pack(fill="both", expand=True)

        self.text.configure(state="disabled")

        for code, color in ANSI_MAP.items():
            self.text.tag_configure(f"ansi_{code}", foreground=color)

        self.after(50, self.stream_logs)

    def toggle_error_notifications(self):
        is_checked = self.notify_var.get()
        self.script_info["notify_errors"] = is_checked
        self.controller.home.scriptManager.save()

    def stream_logs(self):
        if not self.winfo_exists():
            return

        buffer = self.logs.get(self.name)

        if buffer:
            while self.read_index < len(buffer):
                line = buffer[self.read_index]
                self.read_index += 1

                if self.notify_var.get():
                    lower_line = line.lower()
                    if "error" in lower_line or "traceback" in lower_line or "exception" in lower_line:
                        self.trigger_error_notification(line.strip())

                self._append(line)

        self.after(50, self.stream_logs)

    def trigger_error_notification(self, log_line):
        if IS_WINDOWS:
            toast = Toast()
            toast.text_fields = [
                f"{self.name} has encountered an error!",
                log_line[:60]
            ]

            def on_click(_):
                self.controller.after(0, self.controller.show_window)
                self.controller.after(50, lambda: self.controller.show_terminal(self.name))

            toast.on_activated = on_click
            self.controller.toaster.show_toast(toast)
        else:
            notification.notify(
                title=f"{self.name} Error!",
                message=log_line[:60],
                app_name="Compyctor"
            )

    def _append(self, text):
        self.text.configure(state="normal")

        i = 0
        current_tag = None

        while i < len(text):
            if text[i:i + 2] == "\x1b[":
                end = i + 2
                while end < len(text) and text[end] != "m":
                    end += 1

                code = text[i + 2:end]

                if code == "0":
                    current_tag = None
                else:
                    current_tag = f"ansi_{code}" if code in ANSI_MAP else None

                i = end + 1
                continue

            self.text.insert("end", text[i], current_tag)
            i += 1

        if self.auto_scroll:
            self.text.see("end")

        self.text.configure(state="disabled")

    def toggle_scroll(self):
        self.auto_scroll = not self.auto_scroll
        label = "AutoScroll: ON" if self.auto_scroll else "AutoScroll: OFF"
        self.scroll_btn.config(text=label)

    def go_back(self):
        self.controller.show_home()