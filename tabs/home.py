import os
import subprocess
import threading
from collections import deque
from tkinter import ttk
import tkinter as tk

from add_script import AddScriptWindow
from script_manager import ScriptManager


class HomeTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)

        self.controller = controller
        self.scriptManager = ScriptManager()

        self.rows = {}
        self.logs = {}

        self.top_bar = ttk.Frame(self)
        self.top_bar.grid(row=0, column=0, columnspan=2, sticky="ew")

        ttk.Button(
            self.top_bar,
            text="+ Add Script",
            command=self.open_add_script
        ).pack(side="left", padx=4, pady=4)

        bg = ttk.Style().lookup("TFrame", "background")

        self._canvas = tk.Canvas(self, highlightthickness=0, bg=bg)
        self._scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._canvas.grid(row=1, column=0, sticky="nsew")
        self._scrollbar.grid(row=1, column=1, sticky="ns")

        self.body = ttk.Frame(self._canvas)
        self.body.columnconfigure(0, weight=1)
        self.body.columnconfigure(1, weight=0)

        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self.body, anchor="nw"
        )

        self.body.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._canvas.bind("<Enter>", self._bind_mousewheel)
        self._canvas.bind("<Leave>", self._unbind_mousewheel)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.build_ui()

        self.after(100, self.run_autostart)
        self.after(500, self.check_processes)

    def _on_inner_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def _bind_mousewheel(self, _event=None):
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Button-4>", self._on_mousewheel)
        self._canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event=None):
        self._canvas.unbind_all("<MouseWheel>")
        self._canvas.unbind_all("<Button-4>")
        self._canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def run_autostart(self):
        for script in self.scriptManager.get_scripts():
            if script.get("autostart"):
                self.run_script(script)

    def create_row(self, i, script):
        label = ttk.Label(self.body, text=script["name"])
        label.grid(row=i, column=0, padx=4, pady=4, sticky="w")

        container = ttk.Frame(self.body)
        container.grid(row=i, column=1, padx=4, pady=4, sticky="e")

        self.rows[script["name"]] = {
            "script": script,
            "process": None,
            "container": container
        }

        self.refresh_row(script["name"])

    def open_add_script(self):
        AddScriptWindow(self, self.save_new_script)

    def delete_script(self, name):
        row = self.rows[name]
        proc = row["process"]

        if proc and proc.poll() is None:
            return  # don't delete running scripts

        self.scriptManager.remove_script(name)
        self.build_ui()

    def save_new_script(self, data):
        self.scriptManager.add_script(cwd=data["cwd"], script=data["script"], name=data["name"], python=data["python"],
                                      args=data["args"], autostart=data["autostart"])
        self.build_ui()

    def build_ui(self):
        if not hasattr(self, "body") or not self.body.winfo_exists():
            return

        running_processes = {}
        for name, row in self.rows.items():
            if row.get("process") is not None:
                running_processes[name] = row["process"]

        for widget in self.body.winfo_children():
            widget.destroy()

        self.rows.clear()

        sorted_scripts = sorted(self.scriptManager.get_scripts(), key=lambda x: x["name"].lower())
        for i, script in enumerate(sorted_scripts):
            self.create_row(i, script)

            if script["name"] in running_processes:
                self.rows[script["name"]]["process"] = running_processes[script["name"]]
                self.refresh_row(script["name"])

    def run_script(self, script):
        name = script["name"]

        self.logs[name] = deque(maxlen=5000)

        cmd = [
            script["python"],
            script["script"],
            *script.get("args", [])
        ]

        env_config = os.environ.copy()
        env_config["PYTHONUNBUFFERED"] = "1"
        env_config["FORCE_COLOR"] = "1"
        env_config["PY_COLORS"] = "1"

        proc = subprocess.Popen(
            cmd,
            cwd=script["cwd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env_config
        )

        self.rows[name]["process"] = proc

        threading.Thread(
            target=self._read_output,
            args=(name, proc),
            daemon=True
        ).start()

        self.refresh_row(name)

    def _read_output(self, name, proc):
        for line in proc.stdout:
            self.logs[name].append(line)

    def stop_script(self, name):
        proc = self.rows[name]["process"]

        if proc:
            proc.terminate()
            self.rows[name]["process"] = None

        self.refresh_row(name)

    def restart_script(self, name):
        self.stop_script(name)
        self.run_script(self.rows[name]["script"])

    def view_output(self, name):
        self.controller.show_terminal(
            name,
            self.logs,
            self.rows[name]["process"]
        )

    def refresh_row(self, name):
        if name not in self.rows:
            return

        row = self.rows[name]

        if not row["container"].winfo_exists():
            return

        proc = row["process"]
        container = row["container"]

        for widget in container.winfo_children():
            widget.destroy()

        alive = proc and proc.poll() is None

        if alive:
            ttk.Button(
                container,
                text="⏹",
                command=lambda n=name: self.stop_script(n)
            ).pack(side="left")

            ttk.Button(
                container,
                text="🗘",
                command=lambda n=name: self.restart_script(n)
            ).pack(side="left")

            ttk.Button(
                container,
                text="📄",
                command=lambda n=name: self.view_output(n)
            ).pack(side="left")
        else:
            ttk.Button(
                container,
                text="▶",
                command=lambda n=name: self.run_script(self.rows[n]["script"])
            ).pack(side="left", padx=4)

            ttk.Button(
                container,
                text="🗑",
                command=lambda n=name: self.delete_script(n)
            ).pack(side="left")

    def check_processes(self):
        changed = False

        for name, row in self.rows.items():
            proc = row["process"]

            if proc and proc.poll() is not None:
                row["process"] = None
                changed = True

        if changed:
            for name in self.rows:
                self.refresh_row(name)

        self.after(500, self.check_processes)