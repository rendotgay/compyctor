import json
import os
from pathlib import Path


class ScriptManager:
    def __init__(self, filename="scripts.json"):
        self.config_dir = Path.home() / ".compyctor"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.filename = self.config_dir / filename
        self.data = self.load()

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r") as f:
                return json.load(f)

        return {"scripts": []}

    def save(self):
        with open(self.filename, "w") as f:
            json.dump(self.data, f, indent=4)

    def add_script(self, cwd:str, script, name:str=None, python:str=None, args:list=None, autostart=False):
        cwd_path = Path(cwd)
        if not name:
            name = cwd_path.name
        if not python:
            python = str(cwd_path / ".venv" / "Scripts" / "python.exe")

        script_data = {
            "name": name or script,
            "cwd": cwd,
            "python": python or "python",
            "script": script,
            "args": args or [],
            "autostart": autostart,
            "notify_errors": False,
        }
        self.data["scripts"].append(script_data)
        self.save()

    def remove_script(self, name):
        self.data["scripts"] = [
            s for s in self.data["scripts"]
            if s["name"] != name
        ]
        self.save()

    def get_scripts(self):
        return self.data["scripts"]