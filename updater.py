import sys
import os
import requests
import subprocess


class AutoUpdater:
    def __init__(self, current_version, repo_owner, repo_name, settings_mgr):
        self.current_version = current_version
        self.api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
        self.settings_mgr = settings_mgr
        self.latest_release_data = None

        self.latest_version = ""
        self.is_prerelease = False
        self.changelog = ""

    def check_for_update(self) -> bool:
        try:
            from packaging.version import Version, InvalidVersion

            prefs = self.settings_mgr.settings
            official_only = prefs.get("official_releases_only", False)
            skipped_version = prefs.get("skipped_version", "")

            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(self.api_url, headers=headers, timeout=10)

            if response.status_code == 200:
                releases_list = response.json()
                if not releases_list:
                    return False

                target_release = None
                if official_only:
                    for release in releases_list:
                        if not release.get("prerelease", False):
                            target_release = release
                            break
                else:
                    target_release = releases_list[0]

                if not target_release:
                    return False

                self.latest_release_data = target_release
                self.latest_version = self.latest_release_data.get("tag_name", "").strip()
                self.is_prerelease = self.latest_release_data.get("prerelease", False)
                self.changelog = self.latest_release_data.get("body", "No changelog provided.")

                if self.latest_version == skipped_version:
                    return False

                try:
                    latest_semver = Version(self.latest_version)
                    current_semver = Version(self.current_version)
                    return latest_semver > current_semver
                except InvalidVersion:
                    latest_ver = self.latest_version.lstrip('v')
                    current_ver = self.current_version.lstrip('v')
                    return latest_ver > current_ver

        except Exception as e:
            print(f"Update check failed: {e}")
        return False

    def download_and_install(self):
        if not self.latest_release_data:
            return

        assets = self.latest_release_data.get("assets", [])
        download_url = None
        target_filename = "Compyctor.exe" if sys.platform == "win32" else "Compyctor"

        for asset in assets:
            if asset["name"] == target_filename:
                download_url = asset["browser_download_url"]
                break

        if not download_url:
            return

        current_exe = sys.executable
        new_exe_tmp = current_exe + ".new"

        try:
            response = requests.get(download_url, stream=True, timeout=30)
            if response.status_code == 200:
                with open(new_exe_tmp, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                self._trigger_swap_sequence(current_exe, new_exe_tmp)
        except Exception as e:
            print(f"Download failed: {e}")

    def _trigger_swap_sequence(self, current_exe, new_exe):
        if sys.platform == "win32":
            cmd = (
                f'ping 127.0.0.1 -n 4 > nul && '
                f'del /f /q "{current_exe}" && '
                f'move /y "{new_exe}" "{current_exe}" && '
                f'explorer "{current_exe}"'
            )
            subprocess.Popen(f'cmd.exe /c "{cmd}"', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            cmd = f'sleep 2 && rm -f "{current_exe}" && mv -f "{new_exe}" "{current_exe}" && "{current_exe}" &'
            subprocess.Popen(cmd, shell=True)
        os._exit(0)