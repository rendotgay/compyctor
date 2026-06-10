import os
import sys
import re

from PyQt6.QtCore import Qt, QTimer, QObject, QEvent
from PyQt6.QtGui import QColor, QTextCharFormat, QFont, QTextCursor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QCheckBox, QTextEdit, QFrame, QTabWidget, QTextBrowser, QMessageBox
)
from tabs.editor import FileEditorWidget
import urllib.parse

IS_WINDOWS = sys.platform == "win32"

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
_ANSI_SGR_RE = re.compile(r"\x1b\[([0-9;]*)([mK])")
_ANSI_CSI_ANY_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_ANSI_OSC_RE = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")
# Two-char escapes (e.g. ESC =), NOT CSI — must not include '[' (0x5B)
_ANSI_OTHER_RE = re.compile(r"\x1b[@-Z\\]^_`")


def _strip_non_sgr_ansi(text: str) -> str:
    """Remove non-color ANSI sequences that can corrupt UTF-8 display."""
    text = _ANSI_OSC_RE.sub("", text)

    def _csi_repl(m: re.Match) -> str:
        s = m.group(0)
        return s if (s.endswith("m") or s.endswith("K")) else ""

    text = _ANSI_CSI_ANY_RE.sub(_csi_repl, text)
    text = _ANSI_OTHER_RE.sub("", text)
    return text


def _parse_ansi(text: str):
    """
    Yield (fragment: str, fg_color: str | None, bold: bool, ctrl: tuple | None) tuples.
    Handles compound codes like ESC[1;32m and ESC[K.
    """
    text = _strip_non_sgr_ansi(text)
    pos = 0
    current_fg = None
    current_bold = False

    for m in _ANSI_SGR_RE.finditer(text):
        start, end = m.span()
        if start > pos:
            yield text[pos:start], current_fg, current_bold, None
        pos = end

        cmd = m.group(2) if len(m.groups()) > 1 else "m"
        if cmd == "K":
            param = m.group(1) or "0"
            yield "", current_fg, current_bold, ("K", param)
        elif cmd == "m":
            parts = m.group(1).split(";") if m.group(1) else ["0"]
            i = 0
            while i < len(parts):
                code = parts[i]
                if code == "0" or code == "":
                    current_fg = None
                    current_bold = False
                elif code == "1":
                    current_bold = True
                elif code == "22":
                    current_bold = False
                elif code == "38":
                    if i + 2 < len(parts) and parts[i+1] == "5":
                        try:
                            n = int(parts[i+2])
                            current_fg = _256_to_hex(n)
                        except ValueError:
                            pass
                        i += 2
                    elif i + 4 < len(parts) and parts[i+1] == "2":
                        try:
                            r, g, b = int(parts[i+2]), int(parts[i+3]), int(parts[i+4])
                            current_fg = f"#{r:02x}{g:02x}{b:02x}"
                        except ValueError:
                            pass
                        i += 4
                elif code in _ANSI_COLORS:
                    color, bold_flag = _ANSI_COLORS[code]
                    if color:
                        current_fg = color
                i += 1

    if pos < len(text):
        yield text[pos:], current_fg, current_bold, None


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


class ZoomEventFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                delta = event.angleDelta().y()
                if delta > 0:
                    obj.zoomIn(1)
                elif delta < 0:
                    obj.zoomOut(1)
                return True
        return super().eventFilter(obj, event)

class TerminalTab(QWidget):
    def __init__(self, controller, name, logs, process):
        super().__init__()

        self.controller = controller
        self.name = name
        self.logs = logs
        self.process = process
        self.auto_scroll = True
        self.read_index = 0

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

        self.restart_btn = self.controller.home._make_icon_btn("restart.svg", "Restart")
        self.restart_btn.clicked.connect(self._restart_script)
        top_layout.addWidget(self.restart_btn)

        self.stop_btn = self.controller.home._make_icon_btn("stop.svg", "Stop")
        self.stop_btn.clicked.connect(self._toggle_process)
        top_layout.addWidget(self.stop_btn)

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

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.terminal_container = QWidget()
        term_layout = QVBoxLayout(self.terminal_container)
        term_layout.setContentsMargins(0, 0, 0, 0)
        term_layout.setSpacing(0)

        self.text = QTextBrowser()
        self.text.setReadOnly(True)
        self.text.setObjectName("logView")
        self.text.setFont(_terminal_font())
        self.text.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self.text.setOpenLinks(False)
        self.text.anchorClicked.connect(self._on_anchor_clicked)
        term_layout.addWidget(self.text)

        self._zoom_filter = ZoomEventFilter(self.text)
        self.text.viewport().installEventFilter(self._zoom_filter)
        
        z_in1 = QShortcut(QKeySequence("Ctrl+="), self.text)
        z_in1.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        z_in1.activated.connect(lambda: self.text.zoomIn(1))
        
        z_in2 = QShortcut(QKeySequence("Ctrl++"), self.text)
        z_in2.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        z_in2.activated.connect(lambda: self.text.zoomIn(1))
        
        z_out = QShortcut(QKeySequence("Ctrl+-"), self.text)
        z_out.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        z_out.activated.connect(lambda: self.text.zoomOut(1))

        self.editor = FileEditorWidget(self.controller, cwd=self.script_info.get("cwd"), on_pop_out=self._pop_out_editor)

        self.tabs.addTab(self.terminal_container, "Output")
        self.tabs.addTab(self.editor, "Code Editor")

        self._stream_timer = QTimer(self)
        self._stream_timer.timeout.connect(self._stream_logs)
        self._stream_timer.start(50)

    def _restart_script(self):
        self.controller.home.restart_script(self.name)

    def _toggle_process(self):
        proc = self.controller.home.rows[self.name].get("process")
        alive = proc and proc.poll() is None
        if alive:
            self.controller.home.stop_script(self.name)
        else:
            self.controller.home.run_script(self.script_info)

    def _toggle_error_notifications(self, checked):
        self.script_info["notify_errors"] = checked
        self.controller.home.scriptManager.save()

    def _toggle_scroll(self, checked):
        self.auto_scroll = checked
        self.scroll_btn.setText("AutoScroll: ON" if checked else "AutoScroll: OFF")

    def _go_back(self):
        if hasattr(self, 'editor') and self.editor.has_any_unsaved_changes():
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved files. Do you want to save them before leaving?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )
            if reply == QMessageBox.StandardButton.Save:
                self.editor.save_file()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
                
        self._stream_timer.stop()
        self.controller.show_home()

    def _stream_logs(self):
        proc = self.controller.home.rows[self.name].get("process")
        alive = proc and proc.poll() is None
        
        target_tooltip = "Stop" if alive else "Run"
        if self.stop_btn.toolTip() != target_tooltip:
            self.stop_btn.setToolTip(target_tooltip)
            from tabs.home import _tint_icon
            fg = self.controller.theme_mgr.last_theme_data.get("fg", "#ffffff")
            svg_name = "stop.svg" if alive else "run.svg"
            self.stop_btn.setIcon(_tint_icon(svg_name, QColor(fg)))

        buffer = self.logs.get(self.name)
        if not buffer:
            return

        buf_len = len(buffer)
        if buf_len < self.read_index:
            self.read_index = 0
            self.text.clear()

        if self.read_index >= buf_len:
            return

        batch = []
        end = buf_len
        for i in range(self.read_index, end):
            batch.append(buffer[i])
        self.read_index = end

        sb = self.text.verticalScrollBar()
        scroll_pos = sb.value()

        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        for item in batch:
            if isinstance(item, tuple):
                line, is_stderr = item
            else:
                line, is_stderr = item, False
            self._append_line(cursor, line, is_stderr)

        self.text.setTextCursor(cursor)

        if self.auto_scroll:
            sb.setValue(sb.maximum())
        else:
            sb.setValue(scroll_pos)

    def _append_line(self, cursor: QTextCursor, text: str, is_stderr: bool = False):
        """Parse ANSI codes and insert colored spans into the QTextEdit."""
        default_fg = self.controller.theme_mgr.last_theme_data.get("fg", "#e8e8e8")
        if is_stderr:
            default_fg = self.controller.theme_mgr.last_theme_data.get("error", "#ff4444")

        for fragment, fg, bold, ctrl in _parse_ansi(text):
            if ctrl:
                if ctrl[0] == "K":
                    param = ctrl[1]
                    if param == "0":
                        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                        cursor.removeSelectedText()
                    elif param == "1":
                        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
                        cursor.removeSelectedText()
                    elif param == "2":
                        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                        cursor.removeSelectedText()
                continue

            if not fragment:
                continue

            parts = fragment.split('\r')
            for i, part in enumerate(parts):
                if i > 0:
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                
                if not part:
                    continue

                fmt = QTextCharFormat()
                fmt.setForeground(QColor(default_fg))
                if fg:
                    fmt.setForeground(QColor(fg))
                if bold:
                    fmt.setFontWeight(QFont.Weight.Bold)
                else:
                    fmt.setFontWeight(QFont.Weight.Normal)
                
                if not cursor.atBlockEnd():
                    lines = part.split('\n')
                    for j, line in enumerate(lines):
                        if j > 0:
                            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
                            cursor.insertText('\n', fmt)
                        if line:
                            pos = cursor.position()
                            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                            remaining = len(cursor.selectedText())
                            cursor.setPosition(pos)
                            chars_to_replace = min(len(line), remaining)
                            if chars_to_replace > 0:
                                cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, chars_to_replace)
                                cursor.removeSelectedText()
                            self._insert_text_with_traceback(cursor, line, fmt)
                else:
                    self._insert_text_with_traceback(cursor, part, fmt)

    def _insert_text_with_traceback(self, cursor: QTextCursor, text: str, fmt: QTextCharFormat):
        m = re.search(r'File "([^"]+)", line (\d+)', text)
        if m:
            path = m.group(1)
            line_num = m.group(2)
            
            link_fmt = QTextCharFormat(fmt)
            link_fmt.setAnchor(True)
            safe_path = urllib.parse.quote(path)
            link_fmt.setAnchorHref(f"traceback:///?path={safe_path}&line={line_num}")
            link_fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
            
            cursor.insertText(text[:m.start()], fmt)
            cursor.insertText(text[m.start():m.end()], link_fmt)
            cursor.insertText(text[m.end():], fmt)
        else:
            cursor.insertText(text, fmt)

    def _on_anchor_clicked(self, url):
        if url.scheme() == "traceback":
            from urllib.parse import parse_qs
            query = parse_qs(url.query())
            path = urllib.parse.unquote(query.get("path", [""])[0])
            line_num = int(query.get("line", ["1"])[0])
            
            if self.editor.load_file(path, line_num):
                self.tabs.setCurrentWidget(self.editor)

    def _pop_out_editor(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout
        self.tabs.removeTab(self.tabs.indexOf(self.editor))
        
        self.popout_window = QDialog(self)
        self.popout_window.setWindowTitle("Code Editor")
        self.popout_window.resize(800, 600)
        
        layout = QVBoxLayout(self.popout_window)
        layout.setContentsMargins(0, 0, 0, 0)
        self.editor.popout_btn.hide()
        layout.addWidget(self.editor)
        self.editor.show()
        
        self.popout_window.finished.connect(self._on_popout_closed)
        self.popout_window.show()

    def _on_popout_closed(self):
        self.editor.popout_btn.show()
        self.tabs.addTab(self.editor, "Code Editor")
