import json
import os
from pathlib import Path


class SettingsManager:
    def __init__(self, filename="settings.json"):
        self.config_dir = Path.home() / ".compyctor"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.filename = self.config_dir / filename
        self.settings = self.load_settings()

    def load_settings(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                return json.load(f)
        return {
            "theme": "dark",
            "always_on_top": False,
        }

    def save_settings(self, key, value):
        self.settings[key] = value
        with open(self.filename, 'w') as f:
            json.dump(self.settings, f, indent=4)