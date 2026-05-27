import json
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPalette, QPixmap, QPolygon
from PyQt6.QtWidgets import QApplication


def _base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent

THEMES_DIR = _base_dir() / "themes"

_LOG_DEFAULTS = {
    "info": "#ffffff",
    "warning": "#ffaa00",
    "error": "#ff4444",
}


def load_theme_data(name: str) -> dict:
    path = THEMES_DIR / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def get_log_colors(name: str) -> dict:
    data = load_theme_data(name)
    return {k: data.get(k, _LOG_DEFAULTS[k]) for k in _LOG_DEFAULTS}


def normalize_theme_name(name: str, available: list[str]) -> str:
    if not name:
        return available[0] if available else "Light"
    for theme in available:
        if theme.lower() == name.lower():
            return theme
    return available[0] if available else name


_ARROW_CACHE = Path(os.getenv("APPDATA", os.path.expanduser("~"))) / "funnymonkey" / ".arrow_cache"


def _render_arrow_png(path: Path, color: QColor, up: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = 12, 8
    pix = QPixmap(w, h)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    if up:
        points = QPolygon([QPoint(0, h), QPoint(w // 2, 0), QPoint(w, h)])
    else:
        points = QPolygon([QPoint(0, 0), QPoint(w // 2, h), QPoint(w, 0)])
    painter.drawPolygon(points)
    painter.end()
    pix.save(str(path), "PNG")


def _arrow_image_uri(color: str, up: bool = False) -> str:
    """PNG chevrons on disk — Qt on Windows often won't paint data-URI SVG in QSS."""
    safe = color.lstrip("#").lower()
    suffix = "up" if up else "down"
    png_path = _ARROW_CACHE / f"{suffix}_{safe}.png"
    qcolor = QColor(color)
    if not qcolor.isValid():
        qcolor = QColor("#ffffff")
    if not png_path.exists():
        _render_arrow_png(png_path, qcolor, up=up)
    return f"url({png_path.resolve().as_uri()})"


def _subtle_border(field_bg: QColor, bg: QColor) -> str:
    """Border color that scales contrast dynamically based on overall theme brightness."""
    if bg.lightness() > 128:
        # Light theme: generate a crisp, high-visibility dark outline frame
        return bg.darker(135).name()

    # Dark theme fallback
    if field_bg.lightness() > bg.lightness():
        return field_bg.darker(115).name()
    return field_bg.lighter(108).name()


class ThemeManager(QObject):
    theme_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._themes: dict[str, dict] = {}
        self._theme_names: list[str] = []
        self._current = ""
        for path in sorted(THEMES_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            name = path.stem
            self._themes[name] = data
            self._theme_names.append(name)

    @property
    def available_themes(self) -> list[str]:
        return list(self._theme_names)

    @property
    def current_theme(self) -> str:
        return self._current

    def normalize_theme_name(self, name: str) -> str:
        return normalize_theme_name(name, self._theme_names)

    def apply(self, app: QApplication, name: str) -> str:
        name = normalize_theme_name(name, self._theme_names)
        data = self._themes.get(name)
        if not data:
            return self._current

        bg = QColor(data["bg"])
        fg = QColor(data["fg"])
        field_bg = QColor(data["field_bg"])
        primary = QColor(data["primary"])
        hover = QColor(data["hover"])
        border = _subtle_border(field_bg, bg)

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, bg)
        palette.setColor(QPalette.ColorRole.WindowText, fg)
        palette.setColor(QPalette.ColorRole.Base, field_bg)
        palette.setColor(QPalette.ColorRole.AlternateBase, bg)
        palette.setColor(QPalette.ColorRole.Text, fg)
        palette.setColor(QPalette.ColorRole.Button, field_bg)
        palette.setColor(QPalette.ColorRole.ButtonText, fg)
        palette.setColor(QPalette.ColorRole.Highlight, primary)
        palette.setColor(QPalette.ColorRole.HighlightedText, fg)
        palette.setColor(QPalette.ColorRole.PlaceholderText, fg)
        palette.setColor(QPalette.ColorRole.Link, primary)
        palette.setColor(QPalette.ColorRole.LinkVisited, primary)
        app.setPalette(palette)

        # Dynamically evaluate scrollbar tracks instead of using hardcoded dark values
        if bg.lightness() > 128:
            scroll_bg = field_bg.darker(120).name()
        else:
            scroll_bg = "#454545"

        arrow_uri = _arrow_image_uri(data["fg"], up=False)
        arrow_up_uri = _arrow_image_uri(data["fg"], up=True)

        app.setStyleSheet(f"""
            QWidget {{
                background-color: {data['bg']};
            }}
            QLabel, QCheckBox, QTabBar, QToolBar, QMenu {{
                color: {data['fg']};
            }}
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background-color: {data['field_bg']};
                color: {data['fg']};
                border: 1px solid {border};
                padding: 3px 5px;
                selection-background-color: {data['primary']};
                selection-color: {data['fg']};
            }}
            QTextEdit {{
                background-color: {data['field_bg']};
                border: 1px solid {border};
                padding: 3px 5px;
                selection-background-color: {data['primary']};
                selection-color: {data['fg']};
            }}
            QGroupBox {{
                border: 1px solid {border};
                margin-top: 6px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                padding: 0 3px;
            }}
            QTextEdit#logView {{
                background-color: {data['field_bg']};
                border: 1px solid {border};
                padding: 4px;
                selection-background-color: {data['primary']};
                selection-color: {data['fg']};
            }}
            QLineEdit:focus, QTextEdit:focus,
            QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
                border: 1px solid {data['primary']};
            }}
            QTextEdit#logView:focus {{
                border: 1px solid {data['primary']};
            }}
            QComboBox QAbstractItemView {{
                background-color: {data['field_bg']};
                color: {data['fg']};
                border: 1px solid {border};
                selection-background-color: {data['primary']};
                selection-color: {data['fg']};
            }}
            QComboBox {{
                padding-right: 22px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid {border};
                background: {data['field_bg']};
            }}
            QComboBox::down-arrow {{
                width: 12px;
                height: 8px;
                margin: auto;
                image: {arrow_uri};
            }}
            QSpinBox, QDoubleSpinBox {{
                padding-right: 18px;
            }}
            QSpinBox::up-button, QDoubleSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid {border};
                background: {data['field_bg']};
            }}
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid {border};
                background: {data['field_bg']};
            }}
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
                width: 12px;
                height: 8px;
                image: {arrow_up_uri};
            }}
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
                width: 12px;
                height: 8px;
                image: {arrow_uri};
            }}
            QPushButton {{
                background-color: {data['field_bg']};
                color: {data['fg']};
                border: 1px solid {border};
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {data['hover']};
                color: {data['fg']};
            }}
            QPushButton:pressed {{
                background-color: {data['primary']};
                color: {data['fg']};
            }}
            QTreeView, QTreeWidget {{
                background-color: {data['field_bg']};
                color: {data['fg']};
                border: 1px solid {border};
                alternate-background-color: {data['bg']};
                selection-background-color: {data['primary']};
                selection-color: {data['fg']};
                outline: none;
            }}
            QTreeView::item:focus, QTreeWidget::item:focus {{
                outline: none;
            }}
            QTreeWidget#kvpEditorTree::item {{
                min-height: 24px;
                border-bottom: 1px solid {border};
            }}
            QTreeWidget#kvpEditorTree QLineEdit {{
                padding: 0px;
                border: none;
                background: transparent;
            }}
            QHeaderView::section {{
                background-color: {data['field_bg']};
                color: {data['fg']};
                border: 1px solid {border};
                padding: 4px;
            }}
            QScrollBar:vertical {{
                background: {data['bg']};
                width: 14px;
                border: none;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {scroll_bg};
                min-height: 20px;
                border-radius: 4px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {data['hover']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background: none;
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollBar:horizontal {{
                background: {data['bg']};
                height: 14px;
                border: none;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {scroll_bg};
                min-width: 20px;
                border-radius: 4px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {data['hover']};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                background: none;
                width: 0px;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
            QTabWidget::pane {{
                border: 1px solid {border};
                background: {data['bg']};
            }}
            QTabBar::tab {{
                background: {data['field_bg']};
                color: {data['fg']};
                padding: 6px 12px;
                border: 1px solid {border};
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {data['primary']};
                color: {data['fg']};
                border: 1px solid {data['primary']};
            }}
            QTabBar::tab:hover {{
                background: {data['hover']};
                color: {data['fg']};
            }}
            QTabBar::tab:selected:hover {{
                background: {data['primary']};
            }}
            QCheckBox {{
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid {border};
                background: {data['field_bg']};
            }}
            QCheckBox::indicator:checked {{
                background: {data['primary']};
                border: 1px solid {data['primary']};
            }}
            QCheckBox::indicator:hover {{
                border: 1px solid {data['hover']};
            }}
            QProgressBar {{
                border: 1px solid {border};
                background: {data['field_bg']};
                text-align: center;
                color: {data['fg']};
            }}
            QProgressBar::chunk {{
                background: {data['primary']};
            }}
            QToolBar {{
                background: {data['bg']};
                border: none;
                spacing: 4px;
            }}
            QMenu {{
                background-color: {data['field_bg']};
                color: {data['fg']};
                border: 1px solid {border};
            }}
            QMenu::item:selected {{
                background-color: {data['primary']};
                color: {data['fg']};
            }}
            QScrollArea {{
                border: none;
                background: {data['bg']};
            }}
            QLabel#sectionHeader {{
                font-weight: bold;
            }}
            QToolButton {{
                background: {data['field_bg']};
                border: 1px solid {border};
                color: {data['fg']};
            }}
            QToolButton:hover {{
                background: {data['hover']};
            }}
        """)

        self._current = name
        self._last_data = data
        self.theme_changed.emit(name)
        return name

    @property
    def last_theme_data(self) -> dict:
        return getattr(self, "_last_data", {})