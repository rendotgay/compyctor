import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

import pystray
from PIL import Image, ImageDraw
from pystray import MenuItem as item

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    from windows_toasts import WindowsToaster, Toast, ToastImage, ToastDisplayImage
else:
    from plyer import notification

from settings_manager import SettingsManager
from tabs.home import HomeTab
from themes import MainStyle, DARK_BG, DARK_FG, DARK_PRIMARY, LIGHT_BG, LIGHT_FG, LIGHT_PRIMARY
from updater import AutoUpdater


def get_asset_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Compyctor v0.1")
        self.geometry("500x200")

        if IS_WINDOWS and os.path.exists(get_asset_path("logo.ico")):
            self.iconbitmap(get_asset_path("logo.ico"))

        self.settings_mgr = SettingsManager()

        if IS_WINDOWS:
            self.toaster = WindowsToaster('Compyctor')

        self.style_system = MainStyle()
        self.current_theme = self.settings_mgr.settings.get("theme", "light")
        self.style_system.theme_use(self.current_theme)

        self.toolbar = ttk.Frame(self)
        self.toolbar.pack(side="top", fill="x")

        self.settings_btn = ttk.Menubutton(self.toolbar, text="Settings")
        self.settings_btn.pack(side="left", padx=4, pady=2)

        self.settings_menu = tk.Menu(self.settings_btn, tearoff=0)
        self.settings_btn["menu"] = self.settings_menu

        self.theme_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label="Theme", menu=self.theme_menu)

        self.theme_var = tk.StringVar(value=self.current_theme)
        self.theme_menu.add_radiobutton(
            label="Light Theme", variable=self.theme_var, value="light", command=lambda: self.change_theme("light")
        )
        self.theme_menu.add_radiobutton(
            label="Dark Theme", variable=self.theme_var, value="dark", command=lambda: self.change_theme("dark")
        )

        self.settings_menu.add_separator()

        self.official_releases_var = tk.BooleanVar(
            value=self.settings_mgr.settings.get("official_releases_only", False))
        self.settings_menu.add_checkbutton(
            label="Official Releases Only",
            variable=self.official_releases_var,
            command=self.toggle_official_releases_preference
        )

        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True)

        self.current = None
        self.home = HomeTab(self.container, self)

        self.show_home()
        self.update_menu_theme(self.current_theme)

        self.updater = AutoUpdater(current_version="0.1", repo_owner="rendotgay", repo_name="compyctor",
                                   settings_mgr=self.settings_mgr)
        self.after(2000, self.run_background_update_check)

        self.tray_icon = None
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.create_tray_icon()

    def toggle_official_releases_preference(self):
        val = self.official_releases_var.get()
        self.settings_mgr.settings["official_releases_only"] = val
        self.settings_mgr.save_settings("official_releases_only", val)

    def run_background_update_check(self):
        import threading
        def worker():
            if self.updater.check_for_update():
                ver_type = " [PRE-RELEASE]" if self.updater.is_prerelease else ""

                msg_title = "Update Available!"
                msg_content = (
                    f"A new update is available for Compyctor!\n\n"
                    f"Current Version: {self.updater.current_version}\n"
                    f"Latest Version: {self.updater.latest_version}{ver_type}\n\n"
                    f"--- Release Notes ---\n"
                    f"{self.updater.changelog}\n\n"
                    f"Would you like to download, install, and restart now?\n"
                    f"(Selecting 'No' skips tracking alerts for this specific update build version)"
                )

                if messagebox.askyesno(msg_title, msg_content):
                    self.updater.download_and_install()
                else:
                    self.settings_mgr.settings["skipped_version"] = self.updater.latest_version
                    self.settings_mgr.save_settings("skipped_version", self.updater.latest_version)

        threading.Thread(target=worker, daemon=True).start()

    def change_theme(self, theme_name):
        self.current_theme = theme_name
        self.style_system.theme_use(theme_name)
        self.theme_var.set(theme_name)
        self.settings_mgr.settings["theme"] = theme_name
        self.settings_mgr.save_settings("theme", theme_name)
        self.update_menu_theme(theme_name)
        if hasattr(self, 'home') and hasattr(self.home, '_canvas'):
            new_bg = ttk.Style().lookup("TFrame", "background")
            self.home._canvas.configure(bg=new_bg)

    def update_menu_theme(self, theme_name):
        if theme_name == "dark":
            bg, fg, primary = DARK_BG, DARK_FG, DARK_PRIMARY
        else:
            bg, fg, primary = LIGHT_BG, LIGHT_FG, LIGHT_PRIMARY

        menu_config = {
            "bg": bg, "fg": fg, "activebackground": primary, "activeforeground": fg,
            "bd": 1, "selectcolor": fg, "relief": "flat", "borderwidth": "0"
        }
        self.settings_menu.configure(**menu_config)
        self.theme_menu.configure(**menu_config)

    def switch(self, frame):
        if self.current: self.current.pack_forget()
        self.current = frame
        self.current.pack(fill="both", expand=True)

    def show_home(self):
        self.switch(self.home)

    def show_terminal(self, name, logs=None, process=None):
        if logs is None: logs = self.home.logs
        if process is None and name in self.home.rows: process = self.home.rows[name]["process"]
        from tabs.output import TerminalTab
        self.switch(TerminalTab(self.container, self, name, logs, process))

    def load_tray_image(self):
        logo_path = get_asset_path("logo.ico")
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path)
                return img.resize((64, 64), Image.Resampling.LANCZOS)
            except Exception:
                pass
        image = Image.new("RGB", (64, 64), (30, 30, 30))
        draw = ImageDraw.Draw(image)
        draw.rectangle((16, 16, 48, 48), fill=(255, 0, 139))
        return image

    def create_tray_icon(self):
        menu = (item("Open", self.show_window), item("Quit", self.quit_from_tray))
        self.tray_icon = pystray.Icon("Compyctor", self.load_tray_image(), "Compyctor", menu)
        import threading
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_to_tray(self):
        self.withdraw()
        if IS_WINDOWS:
            toast = Toast()
            toast.text_fields = ["Compyctor", "Minimized to the system tray."]
            icon_path = get_asset_path("logo.ico")
            if os.path.exists(icon_path):
                toast.AddImage(ToastDisplayImage(ToastImage(icon_path)))
            toast.on_activated = lambda _: self.after(0, self.show_window)
            self.toaster.show_toast(toast)
        else:
            notification.notify(title="Compyctor", message="Minimized to system tray.", app_name="Compyctor")

    def show_window(self, icon=None, item=None):
        self.deiconify()
        self.lift()

    def quit_from_tray(self, icon=None, item=None):
        def check_running():
            procs = []
            for row in self.home.rows.values():
                proc = row.get("process")
                if proc: procs.append(proc)
            return procs

        if len(check_running()) > 0:
            if messagebox.askyesno("Quit", "Stop all running scripts and exit?"):
                try:
                    for row in check_running(): row.terminate()
                except Exception:
                    pass
                if self.tray_icon: self.tray_icon.stop()
                self.destroy()
        else:
            if self.tray_icon: self.tray_icon.stop()
            self.destroy()


if __name__ == "__main__":
    App().mainloop()