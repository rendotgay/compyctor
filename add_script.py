import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog


class AddScriptWindow(tk.Toplevel):
    def __init__(self, parent, on_save):
        super().__init__(parent)

        self.title("Add Script")
        self.geometry("250x220")
        self.minsize(250, 200)

        self.on_save = on_save

        self.cwd_var = tk.StringVar()
        self.script_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.python_var = tk.StringVar()
        self.args_var = tk.StringVar()
        self.autostart_var = tk.BooleanVar()

        self.build_ui()

    def build_ui(self):
        pad = {"padx": 8, "pady": 5}

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True)

        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Name").grid(row=0, column=0, sticky="w", **pad)

        ttk.Entry(frm, textvariable=self.name_var).grid(
            row=0, column=1, sticky="ew", columnspan=2, **pad
        )

        ttk.Label(frm, text="Script").grid(row=1, column=0, sticky="w", **pad)

        ttk.Entry(frm, textvariable=self.script_var).grid(
            row=1, column=1, sticky="ew", **pad
        )

        ttk.Button(
            frm,
            text="Browse",
            command=self.browse_script
        ).grid(row=1, column=2, **pad)

        ttk.Label(frm, text="Working Dir").grid(row=2, column=0, sticky="w", **pad)

        ttk.Entry(frm, textvariable=self.cwd_var).grid(
            row=2, column=1, sticky="ew", **pad
        )

        ttk.Button(
            frm,
            text="Browse",
            command=self.browse_cwd
        ).grid(row=2, column=2, **pad)

        ttk.Label(frm, text="Args").grid(row=3, column=0, sticky="w", **pad)

        ttk.Entry(frm, textvariable=self.args_var).grid(
            row=3, column=1, sticky="ew", columnspan=2, **pad
        )

        ttk.Label(frm, text="Python").grid(row=4, column=0, sticky="w", **pad)

        ttk.Entry(frm, textvariable=self.python_var).grid(
            row=4, column=1, sticky="ew", **pad
        )

        ttk.Button(
            frm,
            text="Browse",
            command=self.browse_python
        ).grid(row=4, column=2, **pad)

        ttk.Checkbutton(
            frm,
            text="Autostart",
            variable=self.autostart_var
        ).grid(row=5, column=0, sticky="w", padx=8, pady=5)

        ttk.Button(
            frm,
            text="Save",
            command=self.save
        ).grid(row=6, column=0, columnspan=3, pady=15)

    def browse_cwd(self):
        path = filedialog.askdirectory()
        if path:
            self.cwd_var.set(path)

    def browse_script(self):
        path = filedialog.askopenfilename(
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )

        if not path:
            return

        p = Path(path)

        self.script_var.set(str(p))
        self.cwd_var.set(str(p.parent))

        if not self.name_var.get():
            self.name_var.set(p.stem)

        if not self.python_var.get():
            if sys.platform == "win32":
                venv_python = p.parent / ".venv" / "Scripts" / "python.exe"
            else:
                venv_python = p.parent / ".venv" / "bin" / "python"

            if venv_python.exists():
                self.python_var.set(str(venv_python))

    def browse_python(self):
        if sys.platform == "win32":
            file_types = [("Python Executable", "*.exe"), ("All Files", "*.*")]
        else:
            file_types = [("All Files", "*.*")]

        path = filedialog.askopenfilename(filetypes=file_types)
        if path:
            self.python_var.set(path)

    def save(self):
        if not self.cwd_var.get() or not self.script_var.get():
            messagebox.showerror("Error", "Working dir and script are required")
            return

        data = {
            "cwd": self.cwd_var.get(),
            "script": self.script_var.get(),
            "name": self.name_var.get() or None,
            "python": self.python_var.get() or None,
            "args": self.args_var.get().split() if self.args_var.get() else [],
            "autostart": self.autostart_var.get()
        }

        self.on_save(data)
        self.destroy()