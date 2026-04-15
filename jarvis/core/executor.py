"""
core/executor.py
Executes all commands parsed from AI responses.
Handles EXE launching, file opening, Discord, Steam, system controls, etc.
"""

import os
import subprocess
import webbrowser
import glob
import json
import time
import platform
from typing import Callable
import config


class CommandExecutor:
    """
    Receives parsed command dicts and routes them to the correct handler.
    log_fn: callable that accepts a string message to display in the UI.
    """

    def __init__(self, log_fn: Callable[[str], None] = print):
        self.log = log_fn
        self._steam_games_cache: dict[str, str] = {}

    # ──────────────────────────────────────────────────────────────────────────
    # Public dispatch
    # ──────────────────────────────────────────────────────────────────────────

    def execute(self, command: dict) -> str:
        """
        Route a command dict to the correct handler.
        Returns a short result string for the AI to incorporate.
        """
        name = command.get("name", "")
        args = command.get("args")

        handlers = {
            "RUN_EXE":         self._run_exe,
            "OPEN_FILE":       self._open_file,
            "OPEN_URL":        self._open_url,
            "KILL_PROCESS":    self._kill_process,
            "LIST_FILES":      self._list_files,
            "RUN_CMD":         self._run_cmd,
            "DISCORD_CALL":    self._discord_call,
            "DISCORD_MESSAGE": self._discord_message,
            "OPEN_DISCORD":    self._open_discord,
            "STEAM_LAUNCH":    self._steam_launch,
            "STEAM_LIST":      self._steam_list,
            "OPEN_STEAM":      self._open_steam,
            "SCREENSHOT":      self._screenshot,
            "VOLUME":          self._set_volume,
            "SHUTDOWN":        self._shutdown,
            "RESTART":         self._restart,
            "LOCK":            self._lock,
        }

        handler = handlers.get(name)
        if handler:
            try:
                return handler(args)
            except Exception as e:
                msg = f"❌ Error executing {name}: {e}"
                self.log(msg)
                return msg
        else:
            return f"⚠️ Unknown command: {name}"

    # ──────────────────────────────────────────────────────────────────────────
    # File & Process handlers
    # ──────────────────────────────────────────────────────────────────────────

    def _run_exe(self, path: str) -> str:
        path = path.strip().strip('"')
        if not os.path.isfile(path):
            # Try searching common locations
            found = self._search_exe(path)
            if found:
                path = found
            else:
                return f"❌ EXE not found: {path}"
        self.log(f"🚀 Launching: {path}")
        subprocess.Popen([path], shell=False)
        return f"Launched {os.path.basename(path)}"

    def _open_file(self, path: str) -> str:
        path = path.strip().strip('"')
        if not os.path.exists(path):
            return f"❌ File not found: {path}"
        self.log(f"📂 Opening file: {path}")
        os.startfile(path)
        return f"Opened {os.path.basename(path)}"

    def _open_url(self, url: str) -> str:
        url = url.strip()
        if not url.startswith("http"):
            url = "https://" + url
        self.log(f"🌐 Opening URL: {url}")
        webbrowser.open(url)
        return f"Opened {url}"

    def _kill_process(self, name: str) -> str:
        name = name.strip()
        self.log(f"🔪 Killing process: {name}")
        result = subprocess.run(
            ["taskkill", "/F", "/IM", name],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return f"Killed {name}"
        return f"❌ Could not kill {name}: {result.stderr.strip()}"

    def _list_files(self, directory: str) -> str:
        directory = directory.strip().strip('"') or os.path.expanduser("~")
        self.log(f"📁 Listing: {directory}")
        try:
            files = os.listdir(directory)
            result = "\n".join(files[:50])  # cap at 50
            return f"Files in {directory}:\n{result}"
        except Exception as e:
            return f"❌ Cannot list {directory}: {e}"

    def _run_cmd(self, command: str) -> str:
        command = command.strip()
        self.log(f"💻 Running command: {command}")
        result = subprocess.run(
            command, shell=True,
            capture_output=True, text=True, timeout=15
        )
        output = (result.stdout + result.stderr).strip()
        return output[:500] if output else "(no output)"

    def _search_exe(self, name: str) -> str | None:
        """Search PATH and common dirs for an exe."""
        search_dirs = [
            os.environ.get("ProgramFiles", ""),
            os.environ.get("ProgramFiles(x86)", ""),
            os.path.expanduser("~\\AppData\\Local"),
            os.environ.get("SystemRoot", "C:\\Windows"),
        ]
        for d in search_dirs:
            if d and os.path.isdir(d):
                for root, _, files in os.walk(d):
                    for f in files:
                        if f.lower() == name.lower() or f.lower() == name.lower() + ".exe":
                            return os.path.join(root, f)
        return None

    # ──────────────────────────────────────────────────────────────────────────
    # Discord handlers
    # ──────────────────────────────────────────────────────────────────────────

    def _open_discord(self, _=None) -> str:
        discord_exe = config.DISCORD_PATH
        # Fallback locations
        fallbacks = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Discord", "app-*", "Discord.exe"),
            r"C:\Users\%USERNAME%\AppData\Local\Discord\app-*\Discord.exe",
        ]
        if not os.path.isfile(discord_exe):
            for pattern in fallbacks:
                matches = glob.glob(os.path.expandvars(pattern))
                if matches:
                    discord_exe = matches[-1]  # Use latest version
                    break
        if discord_exe and os.path.isfile(discord_exe):
            self.log("🎮 Opening Discord...")
            subprocess.Popen([discord_exe])
            time.sleep(3)
            return "Discord opened"
        # Fallback: open Discord via URI
        self.log("🎮 Launching Discord via URI...")
        os.startfile("discord://")
        return "Discord launch attempted via URI"

    def _discord_call(self, user: str) -> str:
        """
        Open a Discord call. Uses discord:// URI scheme.
        Format: discord://discord.com/users/<user_id> for profile calls.
        For channel voice calls: discord://discord.com/channels/<server_id>/<channel_id>
        """
        user = user.strip()
        self.log(f"📞 Calling {user} on Discord...")
        # If it's a numeric ID, use the users URI
        if user.isdigit():
            uri = f"discord://discord.com/users/{user}"
        else:
            # Open Discord and let user handle — we can't resolve usernames to IDs without the API
            self.log(f"⚠️ Tip: For reliable calling, use numeric Discord User IDs.")
            uri = "discord://"
        os.startfile(uri)
        return f"Opened Discord for user: {user}. Navigate to their profile to call."

    def _discord_message(self, args: str) -> str:
        """
        Format: username|message — opens DM channel if possible.
        This opens Discord to a channel by ID: discord://discord.com/channels/@me/<dm_channel_id>
        Full automation requires Discord bot token (see README).
        """
        if "|" in args:
            user, message = args.split("|", 1)
        else:
            user, message = args, ""
        self.log(f"💬 Opening Discord DM for {user.strip()}...")
        os.startfile("discord://")
        return (
            f"Opened Discord. Navigate to {user.strip()}'s DM to send: {message.strip()}\n"
            "Note: Full DM automation requires a Discord user token (see README)."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Steam handlers
    # ──────────────────────────────────────────────────────────────────────────

    def _open_steam(self, _=None) -> str:
        steam = config.STEAM_PATH
        if os.path.isfile(steam):
            self.log("🎮 Opening Steam...")
            subprocess.Popen([steam])
            return "Steam opened"
        os.startfile("steam://")
        return "Steam launch attempted via URI"

    def _steam_launch(self, game: str) -> str:
        game = game.strip()
        self.log(f"🎮 Launching Steam game: {game}")

        # If it's a numeric App ID, launch directly
        if game.isdigit():
            os.startfile(f"steam://rungameid/{game}")
            return f"Launched Steam game ID: {game}"

        # Try to find game in steamapps by name
        app_id = self._find_steam_app_id(game)
        if app_id:
            os.startfile(f"steam://rungameid/{app_id}")
            return f"Launched {game} (App ID: {app_id})"

        # Fallback: search Steam store
        self.log(f"⚠️ Could not find '{game}' in local installs, trying store search...")
        webbrowser.open(f"https://store.steampowered.com/search/?term={game.replace(' ', '+')}")
        return f"Could not find '{game}' locally. Opened Steam store search."

    def _steam_list(self, _=None) -> str:
        self.log("📋 Listing installed Steam games...")
        games = self._get_installed_steam_games()
        if games:
            lines = [f"  • {name} (ID: {app_id})" for name, app_id in sorted(games.items())]
            return "Installed Steam Games:\n" + "\n".join(lines)
        return "No Steam games found. Is Steam installed?"

    def _find_steam_app_id(self, game_name: str) -> str | None:
        games = self._get_installed_steam_games()
        game_lower = game_name.lower()
        # Exact match
        for name, app_id in games.items():
            if name.lower() == game_lower:
                return app_id
        # Partial match
        for name, app_id in games.items():
            if game_lower in name.lower():
                return app_id
        return None

    def _get_installed_steam_games(self) -> dict[str, str]:
        """Read Steam appmanifest files to get installed games."""
        if self._steam_games_cache:
            return self._steam_games_cache

        steam_apps_dirs = [
            config.STEAM_APPS_PATH,
            r"C:\Program Files (x86)\Steam\steamapps",
            r"C:\Program Files\Steam\steamapps",
        ]

        # Also check additional library folders from libraryfolders.vdf
        vdf_paths = [
            r"C:\Program Files (x86)\Steam\steamapps\libraryfolders.vdf",
            r"C:\Program Files\Steam\steamapps\libraryfolders.vdf",
        ]
        for vdf in vdf_paths:
            if os.path.exists(vdf):
                try:
                    with open(vdf, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Extract library paths
                    import re
                    paths = re.findall(r'"path"\s+"([^"]+)"', content)
                    for p in paths:
                        p = p.replace("\\\\", "\\")
                        steam_apps_dirs.append(os.path.join(p, "steamapps"))
                except Exception:
                    pass

        games = {}
        for apps_dir in steam_apps_dirs:
            if not os.path.isdir(apps_dir):
                continue
            for manifest in glob.glob(os.path.join(apps_dir, "appmanifest_*.acf")):
                try:
                    with open(manifest, "r", encoding="utf-8") as f:
                        content = f.read()
                    import re
                    app_id_match = re.search(r'"appid"\s+"(\d+)"', content)
                    name_match = re.search(r'"name"\s+"([^"]+)"', content)
                    if app_id_match and name_match:
                        games[name_match.group(1)] = app_id_match.group(1)
                except Exception:
                    pass

        self._steam_games_cache = games
        return games

    # ──────────────────────────────────────────────────────────────────────────
    # System handlers
    # ──────────────────────────────────────────────────────────────────────────

    def _screenshot(self, _=None) -> str:
        try:
            import pyautogui
            path = os.path.join(os.path.expanduser("~"), "Desktop", "jarvis_screenshot.png")
            pyautogui.screenshot(path)
            self.log(f"📸 Screenshot saved: {path}")
            return f"Screenshot saved to {path}"
        except ImportError:
            # Fallback using PowerShell
            path = os.path.join(os.path.expanduser("~"), "Desktop", "jarvis_screenshot.png")
            ps_cmd = (
                f'Add-Type -AssemblyName System.Windows.Forms; '
                f'$screen = [System.Windows.Forms.Screen]::PrimaryScreen; '
                f'$bmp = New-Object System.Drawing.Bitmap($screen.Bounds.Width, $screen.Bounds.Height); '
                f'$g = [System.Drawing.Graphics]::FromImage($bmp); '
                f'$g.CopyFromScreen($screen.Bounds.Location, [System.Drawing.Point]::Empty, $screen.Bounds.Size); '
                f'$bmp.Save("{path}")'
            )
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
            return f"Screenshot saved to {path}"

    def _set_volume(self, level: str) -> str:
        try:
            level = int(level)
            level = max(0, min(100, level))
            self.log(f"🔊 Setting volume to {level}%")
            ps_cmd = (
                f"$obj = New-Object -com WScript.Shell; "
                f"For ($i = 0; $i -lt 50; $i++) {{ $obj.SendKeys([char]174) }}; "
                f"For ($i = 0; $i -lt {level // 2}; $i++) {{ $obj.SendKeys([char]175) }}"
            )
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
            return f"Volume set to {level}%"
        except Exception as e:
            return f"❌ Volume error: {e}"

    def _shutdown(self, _=None) -> str:
        self.log("⛔ Shutting down in 10 seconds...")
        subprocess.Popen(["shutdown", "/s", "/t", "10"])
        return "Shutdown scheduled in 10 seconds. Run 'shutdown /a' to abort."

    def _restart(self, _=None) -> str:
        self.log("🔄 Restarting in 10 seconds...")
        subprocess.Popen(["shutdown", "/r", "/t", "10"])
        return "Restart scheduled in 10 seconds. Run 'shutdown /a' to abort."

    def _lock(self, _=None) -> str:
        self.log("🔒 Locking workstation...")
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
        return "Workstation locked."
