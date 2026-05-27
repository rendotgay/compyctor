import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QFileDialog, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt


class AddScriptDialog(QDialog):
    def __init__(self, parent=None, existing: dict = None):
        super().__init__(parent)

        self.result_data = None
        self._existing = existing

        title = "Edit Script" if existing else "Add Script"
        self.setWindowTitle(title)
        self.setFixedSize(320, 230)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._build_ui()

        if existing:
            self._populate(existing)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(4)

        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(5)
        grid.setColumnStretch(1, 1)

        def lbl(text):
            l = QLabel(text)
            l.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return l

        # Name
        self.name_edit = QLineEdit()
        grid.addWidget(lbl("Name"), 0, 0)
        grid.addWidget(self.name_edit, 0, 1, 1, 2)

        # Script
        self.script_edit = QLineEdit()
        script_browse = QPushButton("Browse")
        script_browse.setFixedWidth(58)
        script_browse.clicked.connect(self._browse_script)
        grid.addWidget(lbl("Script"), 1, 0)
        grid.addWidget(self.script_edit, 1, 1)
        grid.addWidget(script_browse, 1, 2)

        # Working dir
        self.cwd_edit = QLineEdit()
        cwd_browse = QPushButton("Browse")
        cwd_browse.setFixedWidth(58)
        cwd_browse.clicked.connect(self._browse_cwd)
        grid.addWidget(lbl("Working Dir"), 2, 0)
        grid.addWidget(self.cwd_edit, 2, 1)
        grid.addWidget(cwd_browse, 2, 2)

        # Args
        self.args_edit = QLineEdit()
        grid.addWidget(lbl("Args"), 3, 0)
        grid.addWidget(self.args_edit, 3, 1, 1, 2)

        # Python
        self.python_edit = QLineEdit()
        python_browse = QPushButton("Browse")
        python_browse.setFixedWidth(58)
        python_browse.clicked.connect(self._browse_python)
        grid.addWidget(lbl("Python"), 4, 0)
        grid.addWidget(self.python_edit, 4, 1)
        grid.addWidget(python_browse, 4, 2)

        root.addLayout(grid)

        # Autostart checkbox
        self.autostart_chk = QCheckBox("Autostart")
        root.addWidget(self.autostart_chk)

        # Save button
        save_btn = QPushButton("Save")
        save_btn.setFixedHeight(26)
        save_btn.clicked.connect(self._save)
        root.addWidget(save_btn)

    def _populate(self, script: dict):
        self.name_edit.setText(script.get("name", ""))
        self.script_edit.setText(script.get("script", ""))
        self.cwd_edit.setText(script.get("cwd", ""))
        self.args_edit.setText(" ".join(script.get("args", [])))
        self.python_edit.setText(script.get("python", ""))
        self.autostart_chk.setChecked(script.get("autostart", False))

    def _browse_script(self):
        if sys.platform == "win32":
            filters = "Python Files (*.py);;All Files (*.*)"
        else:
            filters = "Python Files (*.py);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select Script", "", filters)
        if not path:
            return

        p = Path(path)
        self.script_edit.setText(str(p))
        self.cwd_edit.setText(str(p.parent))

        if not self.name_edit.text():
            self.name_edit.setText(p.stem)

        if not self.python_edit.text():
            if sys.platform == "win32":
                venv_python = p.parent / ".venv" / "Scripts" / "python.exe"
            else:
                venv_python = p.parent / ".venv" / "bin" / "python"
            if venv_python.exists():
                self.python_edit.setText(str(venv_python))

    def _browse_cwd(self):
        path = QFileDialog.getExistingDirectory(self, "Select Working Directory")
        if path:
            self.cwd_edit.setText(path)

    def _browse_python(self):
        if sys.platform == "win32":
            filters = "Python Executable (*.exe);;All Files (*.*)"
        else:
            filters = "All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select Python Executable", "", filters)
        if path:
            self.python_edit.setText(path)

    def _save(self):
        if not self.cwd_edit.text() or not self.script_edit.text():
            QMessageBox.critical(self, "Error", "Working dir and script are required.")
            return

        args_str = self.args_edit.text().strip()
        self.result_data = {
            "cwd": self.cwd_edit.text(),
            "script": self.script_edit.text(),
            "name": self.name_edit.text() or None,
            "python": self.python_edit.text() or None,
            "args": args_str.split() if args_str else [],
            "autostart": self.autostart_chk.isChecked(),
        }
        self.accept()