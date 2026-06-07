import os
import re

from PyQt6.QtCore import Qt, QRegularExpression, QObject, QEvent, QStringListModel, pyqtSignal
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextCursor, QFileSystemModel, QKeySequence, QShortcut, QCursor, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QPlainTextEdit, QMessageBox, QDialog, QSplitter, QTreeView, QCompleter, QMenu
)

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document, theme_mgr):
        super().__init__(document)
        self.theme_mgr = theme_mgr
        self.rules = []
        self.string_rules = []
        self.comment_rule = None
        self.comment_fmt = None
        self.string_fmt = None
        self.tri_single = QRegularExpression("'''")
        self.tri_double = QRegularExpression('"""')
        self._update_rules()

    def _update_rules(self):
        self.rules = []
        self.string_rules = []
        theme = self.theme_mgr.last_theme_data

        # Fallback syntax colors, try to derive from theme or use standard defaults
        is_light = theme.get("bg", "#000000").startswith("#f") or theme.get("bg", "#000000").startswith("#d")
        
        keyword_color = theme.get("primary", "#c678dd" if not is_light else "#a626a4")
        string_color = theme.get("info", "#98c379" if not is_light else "#50a14f")
        comment_color = theme.get("hover", "#5c6370" if not is_light else "#a0a1a7")
        number_color = theme.get("warning", "#d19a66" if not is_light else "#986801")
        decorator_color = theme.get("primary", "#e5c07b" if not is_light else "#c18401")
        
        keyword_fmt = QTextCharFormat()
        keyword_fmt.setForeground(QColor(keyword_color))
        keyword_fmt.setFontWeight(QFont.Weight.Bold)

        self.string_fmt = QTextCharFormat()
        self.string_fmt.setForeground(QColor(string_color))

        self.comment_fmt = QTextCharFormat()
        self.comment_fmt.setForeground(QColor(comment_color))
        self.comment_fmt.setFontItalic(True)

        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor(number_color))
        
        decorator_fmt = QTextCharFormat()
        decorator_fmt.setForeground(QColor(decorator_color))

        # Keywords
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def",
            "del", "elif", "else", "except", "False", "finally", "for",
            "from", "global", "if", "import", "in", "is", "lambda", "None",
            "nonlocal", "not", "or", "pass", "raise", "return", "True",
            "try", "while", "with", "yield", "match", "case"
        ]
        
        for word in keywords:
            pattern = QRegularExpression(rf"\b{word}\b")
            self.rules.append((pattern, keyword_fmt))

        # Decorators
        self.rules.append((QRegularExpression(r"@[^\s]+"), decorator_fmt))

        # Numbers
        self.rules.append((QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_fmt))

        # Strings
        self.string_rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), self.string_fmt))
        self.string_rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), self.string_fmt))

        # Comments
        self.comment_rule = QRegularExpression(r"#[^\n]*")

    def highlightBlock(self, text):
        # 1. Base Rules
        for pattern, format in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)
                
        # 2. Strings
        string_ranges = []
        for pattern, format in self.string_rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                start = match.capturedStart()
                length = match.capturedLength()
                self.setFormat(start, length, format)
                string_ranges.append((start, start + length))
                
        # 3. Multi-line Strings
        self.setCurrentBlockState(0)
        start_index = 0
        state = self.previousBlockState()
        
        def process_multiline(state_val, regex):
            nonlocal start_index, state
            if state != state_val:
                match = regex.match(text, start_index)
                if not match.hasMatch(): return False
                start_index = match.capturedStart()
                
            match = regex.match(text, start_index + 3)
            if match.hasMatch():
                end_index = match.capturedStart() + 3
                self.setFormat(start_index, end_index - start_index, self.string_fmt)
                string_ranges.append((start_index, end_index))
                start_index = end_index
                state = 0
                return True
            else:
                self.setCurrentBlockState(state_val)
                self.setFormat(start_index, len(text) - start_index, self.string_fmt)
                string_ranges.append((start_index, len(text)))
                return False

        if state == 1:
            process_multiline(1, self.tri_double)
        elif state == 2:
            process_multiline(2, self.tri_single)
            
        while start_index < len(text):
            match_d = self.tri_double.match(text, start_index)
            match_s = self.tri_single.match(text, start_index)
            
            d_idx = match_d.capturedStart() if match_d.hasMatch() else len(text)
            s_idx = match_s.capturedStart() if match_s.hasMatch() else len(text)
            
            if d_idx == len(text) and s_idx == len(text):
                break
                
            if d_idx < s_idx:
                start_index = d_idx
                if not process_multiline(1, self.tri_double): break
            else:
                start_index = s_idx
                if not process_multiline(2, self.tri_single): break

        # 4. Comments (only if not inside a string)
        if self.comment_rule:
            iterator = self.comment_rule.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                start = match.capturedStart()
                in_string = any(s <= start < e for s, e in string_ranges)
                if not in_string:
                    self.setFormat(start, match.capturedLength(), self.comment_fmt)
                    break # Comment consumes rest of line

class ZoomEventFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                delta = event.angleDelta().y()
                parent = obj.parent()
                if hasattr(parent, 'zoomIn'):
                    if delta > 0:
                        parent.zoomIn(1)
                    elif delta < 0:
                        parent.zoomOut(1)
                return True
        return super().eventFilter(obj, event)

class CompleterEditor(QPlainTextEdit):
    middle_clicked = pyqtSignal(str, int)
    back_clicked = pyqtSignal()
    forward_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.completer = None
        self._function_completions = set()

    def setCompleter(self, c):
        if self.completer:
            self.completer.disconnect(self)
        self.completer = c
        if not self.completer:
            return
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated.connect(self.insertCompletion)

    def insertCompletion(self, completion):
        if self.completer.widget() is not self:
            return
        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.MoveOperation.Left)
        tc.movePosition(QTextCursor.MoveOperation.EndOfWord)
        tc.insertText(completion[-extra:])
        
        if completion in self._function_completions:
            tc.insertText("()")
            tc.movePosition(QTextCursor.MoveOperation.Left)
            
        self.setTextCursor(tc)

    def textUnderCursor(self):
        tc = self.textCursor()
        tc.select(QTextCursor.SelectionType.WordUnderCursor)
        return tc.selectedText()

    def focusInEvent(self, e):
        if self.completer:
            self.completer.setWidget(self)
        super().focusInEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.MiddleButton:
            cursor = self.cursorForPosition(e.pos())
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            word = cursor.selectedText()
            if word:
                self.middle_clicked.emit(word, cursor.position())
        elif e.button() == Qt.MouseButton.BackButton:
            self.back_clicked.emit()
        elif e.button() == Qt.MouseButton.ForwardButton:
            self.forward_clicked.emit()
        super().mousePressEvent(e)

    def keyPressEvent(self, e):
        if self.completer and self.completer.popup() and self.completer.popup().isVisible():
            if e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                e.ignore()
                return
                
        is_shortcut = ((e.modifiers() & Qt.KeyboardModifier.ControlModifier) and e.key() == Qt.Key.Key_Space)
        if not self.completer or not is_shortcut:
            super().keyPressEvent(e)

        ctrlOrShift = e.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        if not self.completer or (ctrlOrShift and e.text() == ""):
            return

        has_modifier = (e.modifiers() != Qt.KeyboardModifier.NoModifier) and not ctrlOrShift
        completionPrefix = self.textUnderCursor()

        if not is_shortcut and (has_modifier or e.text() == "" or len(completionPrefix) < 2):
            self.completer.popup().hide()
            return

        if completionPrefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completionPrefix)
            self.completer.popup().setCurrentIndex(self.completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)

class FileEditorWidget(QWidget):
    def __init__(self, controller, cwd=None, on_pop_out=None):
        super().__init__()
        self.controller = controller
        self.cwd = cwd
        self.on_pop_out = on_pop_out
        self.current_path = None
        self.original_content = ""
        self.file_cache = {}
        self.nav_history_back = []
        self.nav_history_forward = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)

        # File Browser (Left Side)
        self.file_model = QFileSystemModel()
        
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_model)
        
        if self.cwd and os.path.exists(self.cwd):
            self.file_model.setRootPath(self.cwd)
            self.tree_view.setRootIndex(self.file_model.index(self.cwd))
        else:
            self.file_model.setRootPath("")
        self.tree_view.setHeaderHidden(True)
        # Hide size, type, date columns
        for i in range(1, 4):
            self.tree_view.hideColumn(i)
        self.tree_view.clicked.connect(self._on_tree_clicked)
        self.splitter.addWidget(self.tree_view)

        # Editor Area (Right Side)
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(4, 2, 4, 2)
        toolbar_layout.setSpacing(4)

        self.path_label = QLabel("<b>No file loaded</b>")
        toolbar_layout.addWidget(self.path_label)

        toolbar_layout.addStretch()

        try:
            import sys
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_dir = os.path.join(base_path, "assets", "icons")

        self.save_btn = QPushButton()
        self.save_btn.setIcon(QIcon(os.path.join(icon_dir, "save.svg")))
        self.save_btn.setToolTip("Save")
        self.save_btn.setFixedSize(24, 24)
        self.save_btn.clicked.connect(self.save_file)
        toolbar_layout.addWidget(self.save_btn)

        self.revert_btn = QPushButton()
        self.revert_btn.setIcon(QIcon(os.path.join(icon_dir, "undo.svg")))
        self.revert_btn.setToolTip("Revert")
        self.revert_btn.setFixedSize(24, 24)
        self.revert_btn.clicked.connect(self.revert_file)
        toolbar_layout.addWidget(self.revert_btn)

        if self.on_pop_out:
            self.popout_btn = QPushButton("Pop Out")
            self.popout_btn.setFixedHeight(22)
            self.popout_btn.clicked.connect(self._handle_popout)
            toolbar_layout.addWidget(self.popout_btn)

        editor_layout.addWidget(toolbar)

        # Editor
        self.text_edit = CompleterEditor()
        self.text_edit.middle_clicked.connect(self._on_middle_clicked)
        self.text_edit.back_clicked.connect(self.go_back)
        self.text_edit.forward_clicked.connect(self.go_forward)
        
        # Use terminal font
        from tabs.output import _terminal_font
        self.text_edit.setFont(_terminal_font())
        
        self.highlighter = PythonHighlighter(self.text_edit.document(), self.controller.theme_mgr)
        editor_layout.addWidget(self.text_edit)
        
        # Autocomplete
        self.completer = QCompleter()
        self.completer_model = QStringListModel()
        self.completer.setModel(self.completer_model)
        self.text_edit.setCompleter(self.completer)
        self._update_completions()
        
        # Zoom Events
        self._zoom_filter = ZoomEventFilter(self.text_edit)
        self.text_edit.viewport().installEventFilter(self._zoom_filter)
        
        z_in1 = QShortcut(QKeySequence("Ctrl+="), self.text_edit)
        z_in1.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        z_in1.activated.connect(lambda: self.text_edit.zoomIn(1))
        
        z_in2 = QShortcut(QKeySequence("Ctrl++"), self.text_edit)
        z_in2.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        z_in2.activated.connect(lambda: self.text_edit.zoomIn(1))
        
        z_out = QShortcut(QKeySequence("Ctrl+-"), self.text_edit)
        z_out.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        z_out.activated.connect(lambda: self.text_edit.zoomOut(1))
        
        # Duplicate Line
        dup_action = QShortcut(QKeySequence("Ctrl+D"), self)
        dup_action.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        dup_action.activated.connect(self._duplicate_line_or_selection)

        self.splitter.addWidget(editor_container)
        self.splitter.setSizes([200, 600])
        
        # Theme refresh
        self.controller.theme_mgr.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self):
        self.highlighter._update_rules()
        self.highlighter.rehighlight()

    def has_any_unsaved_changes(self) -> bool:
        self._save_current_to_cache()
        for data in self.file_cache.values():
            if data["content"] != data["original"]:
                return True
        return False

    def _save_current_to_cache(self):
        if not self.current_path: return
        content = self.text_edit.toPlainText()
        if self.current_path not in self.file_cache:
            self.file_cache[self.current_path] = {}
        self.file_cache[self.current_path]["content"] = content

    def _push_history(self):
        if self.current_path:
            pos = self.text_edit.textCursor().position()
            if self.nav_history_back and self.nav_history_back[-1] == (self.current_path, pos):
                return
            self.nav_history_back.append((self.current_path, pos))
            self.nav_history_forward.clear()

    def go_back(self):
        if not self.nav_history_back: return
        if self.current_path:
            self.nav_history_forward.append((self.current_path, self.text_edit.textCursor().position()))
        path, pos = self.nav_history_back.pop()
        self._load_history_state(path, pos)

    def go_forward(self):
        if not self.nav_history_forward: return
        if self.current_path:
            self.nav_history_back.append((self.current_path, self.text_edit.textCursor().position()))
        path, pos = self.nav_history_forward.pop()
        self._load_history_state(path, pos)

    def _load_history_state(self, path, pos):
        if self.current_path != path:
            self.load_file(path)
        cursor = self.text_edit.textCursor()
        cursor.setPosition(pos)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.centerCursor()

    def load_file(self, path: str, line_num: int = 1):
        if not os.path.exists(path):
            QMessageBox.warning(self, "Error", f"File not found:\n{path}")
            return False

        if os.path.isdir(path):
            return False

        self._save_current_to_cache()

        try:
            mtime = os.path.getmtime(path)
            
            if path in self.file_cache:
                cached = self.file_cache[path]
                if cached.get("mtime", 0) < mtime:
                    with open(path, "r", encoding="utf-8") as f:
                        disk_content = f.read()
                    
                    if cached["content"] == cached["original"]:
                        cached["original"] = disk_content
                        cached["content"] = disk_content
                        cached["mtime"] = mtime
                    else:
                        reply = QMessageBox.question(
                            self, "File Modified",
                            f"The file {os.path.basename(path)} was modified externally.\nDo you want to reload it and lose your local changes?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.No
                        )
                        if reply == QMessageBox.StandardButton.Yes:
                            cached["original"] = disk_content
                            cached["content"] = disk_content
                        cached["mtime"] = mtime
                            
                content = cached["content"]
                original = cached["original"]
            else:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                original = content
                self.file_cache[path] = {"content": content, "original": original, "mtime": mtime}

            self.original_content = original
            self.text_edit.setPlainText(content)
            self.current_path = path
            self.path_label.setText(f"<b>{os.path.basename(path)}</b>")
            self.path_label.setToolTip(path)
            
            # Scroll to line
            self.scroll_to_line(line_num)
            return True
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load file:\n{e}")
            return False

    def scroll_to_line(self, line_num: int):
        if not self.current_path:
            return
            
        doc = self.text_edit.document()
        block = doc.findBlockByNumber(line_num - 1)
        if block.isValid():
            cursor = QTextCursor(block)
            self.text_edit.setTextCursor(cursor)
            self.text_edit.centerCursor()

    def save_file(self):
        self._save_current_to_cache()
        saved_count = 0
        for path, data in self.file_cache.items():
            if data["content"] != data["original"]:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(data["content"])
                    data["original"] = data["content"]
                    data["mtime"] = os.path.getmtime(path)
                    saved_count += 1
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to save {os.path.basename(path)}:\n{e}")

        if saved_count > 0:
            self._update_completions()
            QMessageBox.information(self, "Saved", f"Saved {saved_count} file(s) successfully.")
            if self.current_path in self.file_cache:
                self.original_content = self.file_cache[self.current_path]["original"]
        else:
            QMessageBox.information(self, "Saved", "No changes to save.")

    def revert_file(self):
        reply = QMessageBox.question(
            self, "Revert All", "Are you sure you want to revert ALL files to their saved states?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.file_cache.clear()
            path = self.current_path
            self.current_path = None
            if path:
                self.load_file(path)

    def _handle_popout(self):
        if self.on_pop_out:
            self.on_pop_out()

    def _on_tree_clicked(self, index):
        path = self.file_model.filePath(index)
        if os.path.isfile(path):
            self._push_history()
            self.load_file(path)

    def _duplicate_line_or_selection(self):
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            text = text.replace('\u2029', '\n')
            end = cursor.selectionEnd()
            cursor.setPosition(end)
            cursor.insertText(text)
            cursor.setPosition(end, QTextCursor.MoveMode.MoveAnchor)
            cursor.setPosition(end + len(text), QTextCursor.MoveMode.KeepAnchor)
            self.text_edit.setTextCursor(cursor)
        else:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            text = cursor.selectedText()
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
            cursor.insertText("\n" + text)

    def _update_completions(self):
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def",
            "del", "elif", "else", "except", "False", "finally", "for",
            "from", "global", "if", "import", "in", "is", "lambda", "None",
            "nonlocal", "not", "or", "pass", "raise", "return", "True",
            "try", "while", "with", "yield", "match", "case"
        ]
        builtins = [
            "print", "len", "range", "enumerate", "zip", "list", "dict", "set", "tuple",
            "str", "int", "float", "bool", "type", "isinstance", "issubclass", "super",
            "Exception", "ValueError", "TypeError", "open"
        ]
        
        funcs = set()
        if self.cwd and os.path.exists(self.cwd):
            for f in os.listdir(self.cwd):
                if f.endswith(".py"):
                    try:
                        with open(os.path.join(self.cwd, f), "r", encoding="utf-8") as file:
                            content = file.read()
                            matches = re.findall(r"^def\s+([a-zA-Z_]\w*)\s*\(", content, re.MULTILINE)
                            funcs.update(matches)
                    except Exception:
                        pass
        
        self.text_edit._function_completions = funcs.union(builtins)
        
        words = sorted(list(set(keywords + builtins + list(funcs))))
        self.completer_model.setStringList(words)

    def _on_middle_clicked(self, word, pos):
        doc = self.text_edit.document()
        block = doc.findBlock(pos)
        line_text = block.text().strip()
        
        is_definition = False
        if re.search(rf"^(def|class)\s+{word}\b", line_text) or re.search(rf"^{word}\s*=", line_text):
            is_definition = True
            
        definitions = []
        usages = []
        if not self.cwd or not os.path.exists(self.cwd): return
        
        for f in os.listdir(self.cwd):
            if not f.endswith(".py"): continue
            path = os.path.join(self.cwd, f)
            
            if path in self.file_cache:
                content = self.file_cache[path]["content"]
            else:
                try:
                    with open(path, "r", encoding="utf-8") as file:
                        content = file.read()
                except Exception:
                    continue
                    
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if not re.search(rf"\b{word}\b", line): continue
                
                is_def = bool(re.search(rf"^\s*(def|class)\s+{word}\b", line) or re.search(rf"^\s*{word}\s*=", line))
                item = (path, i+1, line.strip())
                if is_def:
                    definitions.append(item)
                else:
                    usages.append(item)
                    
        if not is_definition and definitions:
            if len(definitions) == 1:
                self._push_history()
                self.load_file(definitions[0][0], definitions[0][1])
            else:
                self._show_usage_menu(definitions)
        else:
            if not usages:
                QMessageBox.information(self, "No Usages", f"No usages found for '{word}'.")
            elif len(usages) == 1:
                self._push_history()
                self.load_file(usages[0][0], usages[0][1])
            else:
                self._show_usage_menu(usages)

    def _show_usage_menu(self, items):
        menu = QMenu(self)
        from tabs.output import _terminal_font
        menu.setFont(_terminal_font())
        for path, line_num, text in items:
            filename = os.path.basename(path)
            snippet = text[:50] + "..." if len(text) > 50 else text
            filename_part = f"{filename}:{line_num}"
            filename_part = filename_part.ljust(25)
            action = menu.addAction(f"{filename_part} | {snippet}")
            action.triggered.connect(lambda checked, p=path, l=line_num: self._jump_to(p, l))
        menu.exec(QCursor.pos())
        
    def _jump_to(self, path, line_num):
        self._push_history()
        self.load_file(path, line_num)
