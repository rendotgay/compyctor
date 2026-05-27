import os
import sys
import threading

from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QAction, QColor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMenu, QMessageBox, QStackedWidget,
    QSystemTrayIcon, QStyle, QToolBar, QStyleFactory
)

from utils import get_asset_path

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    from windows_toasts import WindowsToaster, Toast, ToastImage, ToastDisplayImage
else:
    from plyer import notification

from settings_manager import SettingsManager
from themes import ThemeManager
from tabs.home import HomeTab
from updater import AutoUpdater

VERSION = "0.2.0"

_COOLDOWN_OPTIONS = [5, 10, 30, 60, 300]


class UpdateSignals(QObject):
    update_available = pyqtSignal(str, str, str, bool)


class App(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"Compyctor v{VERSION}")
        self.resize(520, 240)

        icon_path = get_asset_path("logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.settings_mgr = SettingsManager()
        self.theme_mgr = ThemeManager()

        if IS_WINDOWS:
            self.toaster = WindowsToaster('Compyctor')

        current_theme = self.settings_mgr.settings.get("theme", "dark")
        current_theme = self.theme_mgr.normalize_theme_name(current_theme)
        self.theme_mgr.apply(QApplication.instance(), current_theme)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.home = HomeTab(self)
        self.stack.addWidget(self.home)
        self.stack.setCurrentWidget(self.home)

        self._build_toolbar()
        self._build_tray()

        # Re-tint toolbar icons whenever the theme changes
        self.theme_mgr.theme_changed.connect(self._on_theme_changed)

        self.updater = AutoUpdater(
            current_version=VERSION,
            repo_owner="rendotgay",
            repo_name="compyctor",
            settings_mgr=self.settings_mgr
        )
        self._update_signals = UpdateSignals()
        self._update_signals.update_available.connect(self._on_update_available)
        QTimer.singleShot(2000, self._run_background_update_check)

    # ── Toolbar ──────────────────────────────────────────────────────────────

    def _fg_color(self) -> QColor:
        fg = self.theme_mgr.last_theme_data.get("fg", "#ffffff")
        return QColor(fg)

    def _build_toolbar(self):
        self._toolbar = QToolBar("Main")
        self._toolbar.setMovable(False)
        self._toolbar.setFloatable(False)
        self._toolbar.setIconSize(QSize(16, 16))
        self._toolbar.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self._toolbar.setStyleSheet("QToolBar { padding: 1px 2px; spacing: 0px; }")
        self.addToolBar(self._toolbar)

        self._settings_action = QAction("Settings", self)
        self._settings_action.triggered.connect(self._show_settings_menu)
        self._toolbar.addAction(self._settings_action)

        self._settings_menu = self._build_settings_menu()

    def _build_settings_menu(self):
        menu = QMenu(self)

        # Theme submenu
        theme_menu = QMenu("Theme", self)
        menu.addMenu(theme_menu)

        current = self.theme_mgr.current_theme
        self._theme_actions = {}
        for name in self.theme_mgr.available_themes:
            action = theme_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name.lower() == current.lower())
            action.triggered.connect(lambda checked, n=name: self._change_theme(n))
            self._theme_actions[name] = action

        menu.addSeparator()

        # Notify cooldown submenu
        cooldown_menu = QMenu("Error Notify Cooldown", self)
        menu.addMenu(cooldown_menu)

        current_cooldown = self.settings_mgr.settings.get("notify_cooldown", 10)
        self._cooldown_actions = {}
        for seconds in _COOLDOWN_OPTIONS:
            if seconds < 60:
                label = f"{seconds}s"
            elif seconds == 60:
                label = "1 min"
            else:
                label = f"{seconds // 60} min"
            action = cooldown_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(seconds == current_cooldown)
            action.triggered.connect(lambda checked, s=seconds: self._change_cooldown(s))
            self._cooldown_actions[seconds] = action

        menu.addSeparator()

        official_only = self.settings_mgr.settings.get("official_releases_only", False)
        self._official_action = menu.addAction("Official Releases Only")
        self._official_action.setCheckable(True)
        self._official_action.setChecked(official_only)
        self._official_action.triggered.connect(self._toggle_official_releases)

        menu.addSeparator()

        self._quit_action = menu.addAction("Quit")
        self._quit_action.triggered.connect(self._quit)

        return menu

    def _show_settings_menu(self):
        widget = self._toolbar.widgetForAction(self._settings_action)
        if widget:
            pos = widget.mapToGlobal(widget.rect().bottomLeft())
        else:
            pos = self._toolbar.mapToGlobal(self._toolbar.rect().bottomLeft())
        self._settings_menu.exec(pos)

    def _on_theme_changed(self, _name: str):
        self.home.retint_icons()

    def _change_theme(self, name):
        self.theme_mgr.apply(QApplication.instance(), name)
        self.settings_mgr.save_settings("theme", name)
        for n, action in self._theme_actions.items():
            action.setChecked(n == name)

    def _change_cooldown(self, seconds):
        self.settings_mgr.save_settings("notify_cooldown", seconds)
        for s, action in self._cooldown_actions.items():
            action.setChecked(s == seconds)

    def _toggle_official_releases(self):
        val = self._official_action.isChecked()
        self.settings_mgr.save_settings("official_releases_only", val)

    # ── Tray ─────────────────────────────────────────────────────────────────

    def _build_tray(self):
        icon_path = get_asset_path("logo.ico")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("Compyctor")

        tray_menu = QMenu()
        tray_menu.addAction("Open").triggered.connect(self.show_window)
        tray_menu.addAction("Quit").triggered.connect(self._quit)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_window()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit(self):
        running = [
            row["process"]
            for row in self.home.rows.values()
            if row.get("process") and row["process"].poll() is None
        ]
        if running:
            reply = QMessageBox.question(
                self, "Quit", "Stop all running scripts and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            for proc in running:
                try:
                    proc.terminate()
                except Exception:
                    pass
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        if IS_WINDOWS:
            toast = Toast()
            toast.text_fields = ["Compyctor", "Minimized to the system tray."]
            icon_path = get_asset_path("logo.ico")
            if os.path.exists(icon_path):
                toast.AddImage(ToastDisplayImage(ToastImage(icon_path)))
            toast.on_activated = lambda _: QTimer.singleShot(0, self.show_window)
            self.toaster.show_toast(toast)
        else:
            notification.notify(
                title="Compyctor",
                message="Minimized to system tray.",
                app_name="Compyctor"
            )

    # ── Navigation ───────────────────────────────────────────────────────────

    def show_home(self):
        while self.stack.count() > 1:
            w = self.stack.widget(1)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.stack.setCurrentWidget(self.home)
        self.resize(520, 240)

    def show_terminal(self, name, logs=None, process=None):
        if logs is None:
            logs = self.home.logs
        if process is None and name in self.home.rows:
            process = self.home.rows[name].get("process")

        from tabs.output import TerminalTab
        terminal = TerminalTab(self, name, logs, process)

        while self.stack.count() > 1:
            w = self.stack.widget(1)
            self.stack.removeWidget(w)
            w.deleteLater()

        self.stack.addWidget(terminal)
        self.stack.setCurrentWidget(terminal)
        self.setMinimumSize(520, 240)
        self.resize(700, 450)

    # ── Updater ──────────────────────────────────────────────────────────────

    def _run_background_update_check(self):
        def worker():
            if self.updater.check_for_update():
                self._update_signals.update_available.emit(
                    self.updater.current_version,
                    self.updater.latest_version,
                    self.updater.changelog,
                    self.updater.is_prerelease,
                )
        threading.Thread(target=worker, daemon=True).start()

    def _on_update_available(self, current, latest, changelog, is_prerelease):
        ver_type = " [PRE-RELEASE]" if is_prerelease else ""
        msg = (
            f"A new update is available for Compyctor!\n\n"
            f"Current Version: {current}\n"
            f"Latest Version: {latest}{ver_type}\n\n"
            f"--- Release Notes ---\n"
            f"{changelog}\n\n"
            f"Would you like to download, install, and restart now?\n"
            f"(Selecting 'No' skips tracking alerts for this specific update build version)"
        )
        reply = QMessageBox.question(
            self, "Update Available!", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.updater.download_and_install()
        else:
            self.settings_mgr.save_settings("skipped_version", latest)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if "Fusion" in QStyleFactory.keys():
        app.setStyle(QStyleFactory.create("Fusion"))
    app.setQuitOnLastWindowClosed(False)
    window = App()
    window.show()
    sys.exit(app.exec())