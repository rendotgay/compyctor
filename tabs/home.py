import os
import subprocess
import sys
import threading
from collections import deque

from PyQt6.QtCore import Qt, QTimer, QSize, QRectF
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QScrollArea, QFrame, QSizePolicy
)

from script_manager import ScriptManager
from utils import get_patches_path

_BTN_SIZE   = 28
_ICON_SIZE  = QSize(14, 14)


def _tint_icon(svg_name: str, color: QColor, size: QSize = _ICON_SIZE) -> QIcon:
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        # __file__ is inside tabs/, so go up one level
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    path = os.path.join(base_path, "assets", "icons", svg_name)
    if not os.path.exists(path):
        return QIcon()

    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return QIcon()

    pixmap = QPixmap(size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, size.width(), size.height()))
    painter.end()

    tinted = QPixmap(size)
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), color)
    painter.end()

    return QIcon(tinted)


class HomeTab(QWidget):
    def __init__(self, controller):
        super().__init__()

        self.controller = controller
        self.scriptManager = ScriptManager()
        self.rows = {}
        self.logs = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(4, 2, 4, 2)
        top_layout.setSpacing(0)

        add_btn = QPushButton("+ Add Script")
        add_btn.setFixedHeight(22)
        add_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        add_btn.clicked.connect(self.open_add_script)
        top_layout.addWidget(add_btn)
        top_layout.addStretch()
        root.addWidget(top_bar)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(line)

        # Scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        self.body_layout.addStretch()

        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll)

        self.build_ui()

        QTimer.singleShot(100, self.run_autostart)

        self._process_timer = QTimer(self)
        self._process_timer.timeout.connect(self.check_processes)
        self._process_timer.start(50)

    def _fg_color(self) -> QColor:
        fg = self.controller.theme_mgr.last_theme_data.get("fg", "#ffffff")
        return QColor(fg)

    def retint_icons(self):
        """Called by App when the theme changes — refreshes all visible row buttons."""
        for name in list(self.rows.keys()):
            self.refresh_row(name)

    def run_autostart(self):
        for script in self.scriptManager.get_scripts():
            if script.get("autostart"):
                self.run_script(script)

    def build_ui(self):
        running = {
            name: row["process"]
            for name, row in self.rows.items()
            if row.get("process") is not None
        }

        while self.body_layout.count() > 1:
            item = self.body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.rows.clear()

        scripts = sorted(self.scriptManager.get_scripts(), key=lambda x: x["name"].lower())
        for i, script in enumerate(scripts):
            row_widget = self._create_row(script)
            self.body_layout.insertWidget(i * 2, row_widget)

            if i < len(scripts) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setFrameShadow(QFrame.Shadow.Sunken)
                self.body_layout.insertWidget(i * 2 + 1, sep)

            if script["name"] in running:
                self.rows[script["name"]]["process"] = running[script["name"]]
                self.refresh_row(script["name"])

    def _create_row(self, script):
        name = script["name"]

        row = QWidget()
        row.setFixedHeight(36)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        label = QLabel(name)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(label)

        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(2)

        self.rows[name] = {
            "script": script,
            "process": None,
            "btn_container": btn_container,
            "btn_layout": btn_layout,
        }

        self.refresh_row(name)
        layout.addWidget(btn_container)
        return row

    def _make_icon_btn(self, svg_name: str, tooltip: str) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(_BTN_SIZE, _BTN_SIZE)
        btn.setToolTip(tooltip)
        icon = _tint_icon(svg_name, self._fg_color())
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(_ICON_SIZE)
        else:
            btn.setText(tooltip[:3])
        return btn

    def _clear_btn_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh_row(self, name):
        if name not in self.rows:
            return

        row = self.rows[name]
        layout = row["btn_layout"]
        self._clear_btn_layout(layout)

        proc = row["process"]
        alive = proc and proc.poll() is None

        if alive:
            stop_btn = self._make_icon_btn("stop.svg", "Stop")
            stop_btn.clicked.connect(lambda _, n=name: self.stop_script(n))
            layout.addWidget(stop_btn)

            restart_btn = self._make_icon_btn("restart.svg", "Restart")
            restart_btn.clicked.connect(lambda _, n=name: self.restart_script(n))
            layout.addWidget(restart_btn)

            log_btn = self._make_icon_btn("log.svg", "View output")
            log_btn.clicked.connect(lambda _, n=name: self.view_output(n))
            layout.addWidget(log_btn)
        else:
            run_btn = self._make_icon_btn("run.svg", "Run")
            run_btn.clicked.connect(lambda _, n=name: self.run_script(self.rows[n]["script"]))
            layout.addWidget(run_btn)

            edit_btn = self._make_icon_btn("edit.svg", "Edit")
            edit_btn.clicked.connect(lambda _, n=name: self.open_edit_script(n))
            layout.addWidget(edit_btn)

            del_btn = self._make_icon_btn("delete.svg", "Delete")
            del_btn.clicked.connect(lambda _, n=name: self.delete_script(n))
            layout.addWidget(del_btn)

    def open_add_script(self):
        from add_script import AddScriptDialog
        dlg = AddScriptDialog(self)
        dlg.exec()
        if dlg.result_data:
            self.save_new_script(dlg.result_data)

    def open_edit_script(self, name):
        from add_script import AddScriptDialog
        script = self.rows[name]["script"]
        dlg = AddScriptDialog(self, existing=script)
        dlg.exec()
        if dlg.result_data:
            self.scriptManager.remove_script(name)
            self.save_new_script(dlg.result_data)

    def save_new_script(self, data):
        self.scriptManager.add_script(
            cwd=data["cwd"],
            script=data["script"],
            name=data["name"],
            python=data["python"],
            args=data["args"],
            autostart=data["autostart"]
        )
        self.build_ui()

    def delete_script(self, name):
        proc = self.rows[name].get("process")
        if proc and proc.poll() is None:
            return
        self.scriptManager.remove_script(name)
        self.build_ui()

    def run_script(self, script):
        name = script["name"]
        self.logs[name] = deque(maxlen=5000)

        cmd = [script["python"], script["script"], *script.get("args", [])]

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["FORCE_COLOR"] = "1"
        env["PY_COLORS"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["COMPYCTOR_FORCE_COLOR"] = "1"
        patches_dir = get_patches_path()
        if os.path.isdir(patches_dir):
            existing_path = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = (
                patches_dir + (os.pathsep + existing_path if existing_path else "")
            )

        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW

        proc = subprocess.Popen(
            cmd,
            cwd=script["cwd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            creationflags=flags,
        )

        self.rows[name]["process"] = proc
        threading.Thread(target=self._read_output, args=(name, proc), daemon=True).start()
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
        self.controller.show_terminal(name, self.logs, self.rows[name]["process"])

    def check_processes(self):
        changed = []
        for name, row in self.rows.items():
            proc = row["process"]
            if proc and proc.poll() is not None:
                row["process"] = None
                changed.append(name)
        for name in changed:
            self.refresh_row(name)