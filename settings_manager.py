import json
import os


class SettingsManager:
    def __init__(self, filename="settings.json"):
        self.filename = filename
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