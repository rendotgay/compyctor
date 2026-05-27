import os
import sys
import re
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QTextCharFormat, QFont, QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QCheckBox, QTextEdit, QFrame
)

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    from windows_toasts import Toast, ToastImage, ToastDisplayImage
else:
    from plyer import notification

# Full ANSI SGR color map
# Keys are SGR codes, values are (color_or_None, is_bold)
_ANSI_COLORS = {
    # Standard foreground
    "30": ("#000000", False),
    "31": ("#cc0000", False),
    "32": ("#4e9a06", False),
    "33": ("#c4a000", False),
    "34": ("#3465a4", False),
    "35": ("#75507b", False),
    "36": ("#06989a", False),
    "37": ("#d3d7cf", False),
    # Bright foreground
    "90": ("#555753", False),
    "91": ("#ef2929", False),
    "92": ("#8ae234", False),
    "93": ("#fce94f", False),
    "94": ("#729fcf", False),
    "95": ("#ad7fa8", False),
    "96": ("#34e2e2", False),
    "97": ("#ffffff", False),
    # Bold
    "1":  (None, True),
    # Reset
    "0":  (None, False),
}

# SGR foreground only; other CSI sequences are stripped (cursor moves, erase, etc.)
_ANSI_SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")
_ANSI_CSI_ANY_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_ANSI_OSC_RE = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")
# Two-char escapes (e.g. ESC =), NOT CSI — must not include '[' (0x5B)
_ANSI_OTHER_RE = re.compile(r"\x1b[@-Z\\]^_`")


def _strip_non_sgr_ansi(text: str) -> str:
    """Remove non-color ANSI sequences that can corrupt UTF-8 display."""
    text = _ANSI_OSC_RE.sub("", text)

    def _csi_repl(m: re.Match) -> str:
        return "" if not m.group(0).endswith("m") else m.group(0)

    text = _ANSI_CSI_ANY_RE.sub(_csi_repl, text)
    text = _ANSI_OTHER_RE.sub("", text)
    return text


def _parse_ansi(text: str):
    """
    Yield (fragment: str, fg_color: str | None, bold: bool) tuples.
    Handles compound codes like ESC[1;32m.
    """
    text = _strip_non_sgr_ansi(text)
    pos = 0
    current_fg = None
    current_bold = False

    for m in _ANSI_SGR_RE.finditer(text):
        start, end = m.span()
        if start > pos:
            yield text[pos:start], current_fg, current_bold
        pos = end

        codes = m.group(1).split(";") if m.group(1) else ["0"]
        for code in codes:
            if code == "0" or code == "":
                current_fg = None
                current_bold = False
            elif code == "1":
                current_bold = True
            elif code == "22":
                current_bold = False
            elif code in _ANSI_COLORS:
                color, bold_flag = _ANSI_COLORS[code]
                if color:
                    current_fg = color

        joined = m.group(1)
        parts = joined.split(";")
        if len(parts) >= 3 and parts[0] == "38" and parts[1] == "5":
            try:
                n = int(parts[2])
                current_fg = _256_to_hex(n)
            except ValueError:
                pass
        elif len(parts) >= 5 and parts[0] == "38" and parts[1] == "2":
            try:
                r, g, b = int(parts[2]), int(parts[3]), int(parts[4])
                current_fg = f"#{r:02x}{g:02x}{b:02x}"
            except ValueError:
                pass

    if pos < len(text):
        yield text[pos:], current_fg, current_bold


def _256_to_hex(n: int) -> str:
    """Convert xterm 256-color index to hex string."""
    if n < 16:
        base = [
            "#000000","#cc0000","#4e9a06","#c4a000",
            "#3465a4","#75507b","#06989a","#d3d7cf",
            "#555753","#ef2929","#8ae234","#fce94f",
            "#729fcf","#ad7fa8","#34e2e2","#ffffff",
        ]
        return base[n]
    if 16 <= n <= 231:
        n -= 16
        b = n % 6; n //= 6
        g = n % 6; r = n // 6
        def c(v): return 0 if v == 0 else 55 + v * 40
        return f"#{c(r):02x}{c(g):02x}{c(b):02x}"
    v = 8 + (n - 232) * 10
    return f"#{v:02x}{v:02x}{v:02x}"


def _terminal_font() -> QFont:
    from PyQt6.QtGui import QFontDatabase
    if IS_WINDOWS:
        available = set(QFontDatabase.families())
        for family in ("Cascadia Mono", "Consolas", "Lucida Console"):
            if family in available:
                return QFont(family, 9)
    return QFont("Monospace", 9)


class TerminalTab(QWidget):
    def __init__(self, controller, name, logs, process):
        super().__init__()

        self.controller = controller
        self.name = name
        self.logs = logs
        self.process = process
        self.auto_scroll = True
        self.read_index = 0
        self._last_notification_time = 0.0
        self._NOTIFY_COOLDOWN = 10.0

        self.script_info = self.controller.home.rows[name]["script"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(4, 2, 4, 2)
        top_layout.setSpacing(4)

        name_label = QLabel(f"<b>{name}</b>")
        top_layout.addWidget(name_label)

        self.scroll_btn = QPushButton("AutoScroll: ON")
        self.scroll_btn.setFixedHeight(22)
        self.scroll_btn.setCheckable(True)
        self.scroll_btn.setChecked(True)
        self.scroll_btn.toggled.connect(self._toggle_scroll)
        top_layout.addWidget(self.scroll_btn)

        self.notify_chk = QCheckBox("Notify on Errors")
        self.notify_chk.setChecked(self.script_info.get("notify_errors", False))
        self.notify_chk.toggled.connect(self._toggle_error_notifications)
        top_layout.addWidget(self.notify_chk)

        top_layout.addStretch()

        back_btn = QPushButton("← Back")
        back_btn.setFixedHeight(22)
        back_btn.clicked.connect(self._go_back)
        top_layout.addWidget(back_btn)

        layout.addWidget(top)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setObjectName("logView")
        self.text.setFont(_terminal_font())
        self.text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.text)

        self._stream_timer = QTimer(self)
        self._stream_timer.timeout.connect(self._stream_logs)
        self._stream_timer.start(50)

    def _toggle_error_notifications(self, checked):
        self.script_info["notify_errors"] = checked
        self.controller.home.scriptManager.save()

    def _toggle_scroll(self, checked):
        self.auto_scroll = checked
        self.scroll_btn.setText("AutoScroll: ON" if checked else "AutoScroll: OFF")

    def _go_back(self):
        self._stream_timer.stop()
        self.controller.show_home()

    def _stream_logs(self):
        buffer = self.logs.get(self.name)
        if not buffer:
            return

        buf_len = len(buffer)
        if self.read_index >= buf_len:
            return

        batch = []
        end = min(self.read_index + 200, buf_len)
        for i in range(self.read_index, end):
            batch.append(buffer[i])
        self.read_index = end

        sb = self.text.verticalScrollBar()
        scroll_pos = sb.value()

        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        for line in batch:
            if self.notify_chk.isChecked():
                ll = line.lower()
                if "error" in ll or "traceback" in ll or "exception" in ll:
                    now = time.monotonic()
                    if now - self._last_notification_time >= self._NOTIFY_COOLDOWN:
                        self._last_notification_time = now
                        self._trigger_error_notification(line.strip())

            self._append_line(cursor, line)

        self.text.setTextCursor(cursor)

        if self.auto_scroll:
            sb.setValue(sb.maximum())
        else:
            sb.setValue(scroll_pos)

    def _append_line(self, cursor: QTextCursor, text: str):
        """Parse ANSI codes and insert colored spans into the QTextEdit."""
        default_fg = self.controller.theme_mgr.last_theme_data.get("fg", "#e8e8e8")

        for fragment, fg, bold in _parse_ansi(text):
            if not fragment:
                continue
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(default_fg))
            if fg:
                fmt.setForeground(QColor(fg))
            if bold:
                fmt.setFontWeight(QFont.Weight.Bold)
            else:
                fmt.setFontWeight(QFont.Weight.Normal)
            cursor.insertText(fragment, fmt)

    def _trigger_error_notification(self, log_line):
        from gui import get_asset_path
        if IS_WINDOWS:
            toast = Toast()
            toast.text_fields = [f"{self.name} has encountered an error!", log_line[:60]]
            icon_path = get_asset_path("logo.ico")
            if os.path.exists(icon_path):
                toast.AddImage(ToastDisplayImage(ToastImage(icon_path)))
            toast.on_activated = lambda _: (
                QTimer.singleShot(0, self.controller.show_window),
                QTimer.singleShot(50, lambda: self.controller.show_terminal(self.name)),
            )
            self.controller.toaster.show_toast(toast)
        else:
            icon_path = get_asset_path("logo.png")
            notification.notify(
                title=f"{self.name} Error!",
                message=log_line[:60],
                app_icon=icon_path if os.path.exists(icon_path) else None,
                app_name="Compyctor"
            )
