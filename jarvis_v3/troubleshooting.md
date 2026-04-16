# JARVIS Troubleshooting Guide

A human-readable guide for when things go wrong. Find your error below.

---

## Table of Contents

1. [Jarvis Won't Start At All](#1-jarvis-wont-start-at-all)
2. [API Key / AI Not Responding](#2-api-key--ai-not-responding)
3. [Discord: Friends List Empty](#3-discord-friends-list-empty)
4. [Discord: Friend Not Found](#4-discord-friend-not-found)
5. [Discord: Call URI Failed](#5-discord-call-uri-failed)
6. [Discord: Can't Call or Message Someone](#6-discord-cant-call-or-message-someone)
7. [Steam / Games Not Launching](#7-steam--games-not-launching)
8. [Voice / Microphone Not Working](#8-voice--microphone-not-working)
9. [Wake Word Not Triggering](#9-wake-word-not-triggering)
10. [Commands Not Executing](#10-commands-not-executing)
11. [Snapshot Scan Failed or Slow](#11-snapshot-scan-failed-or-slow)
12. [App Crashed / Python Errors](#12-app-crashed--python-errors)
13. [Screenshots Not Saving](#13-screenshots-not-saving)
14. [Volume Control Not Working](#14-volume-control-not-working)
15. [File / EXE Not Found Errors](#15-file--exe-not-found-errors)
16. [UI Looks Wrong / Fonts Missing](#16-ui-looks-wrong--fonts-missing)
17. [Settings Not Saving Permanently](#17-settings-not-saving-permanently)

---

## 1. Jarvis Won't Start At All

**Symptom:** Double-clicking `launch.bat` does nothing, or a black window flashes and closes.

**Causes and fixes:**

- **Python not installed or not in PATH**
  Open a terminal and run `python --version`. If you get an error, download Python from https://python.org and check "Add to PATH" during install.

- **Dependencies not installed**
  In the `jarvis_v2` folder, open a terminal and run:
  ```
  pip install -r requirements.txt
  ```
  If you get permission errors, add `--user` to the command.

- **Wrong Python version**
  Jarvis requires Python 3.10 or newer (for `list[dict]` type hints). Run `python --version` to check.

- **Missing `anthropic` package**
  Run `pip install anthropic` manually.

- **`launch.bat` path is wrong**
  Right-click `launch.bat` → Edit and make sure the path to `main.py` is correct for your folder.

- **Antivirus blocking the script**
  Add the Jarvis folder to your antivirus exclusions. Some AVs flag Python scripts that launch subprocesses.

---

## 2. API Key / AI Not Responding

**Symptom:** You send a message and Jarvis freezes, says "Error", or returns nothing.

**Causes and fixes:**

- **API key not set**
  Open `config.py` and replace `"YOUR_API_KEY_HERE"` with your real Anthropic API key. Get one at https://console.anthropic.com. You can also set it in Settings (⚙ button) without editing the file.

- **API key is invalid or expired**
  Go to https://console.anthropic.com → API Keys and create a new one. Paste it into Settings.

- **No internet connection**
  Jarvis calls Anthropic's servers for every message. Check your network.

- **Firewall blocking outbound HTTPS**
  Make sure Python is allowed to make outbound connections on port 443.

- **Rate limit hit**
  Anthropic free-tier accounts have low rate limits. Wait a minute and try again, or upgrade your plan at https://console.anthropic.com.

- **Wrong model name**
  Check `config.py` → `AI_MODEL`. Valid values include `claude-haiku-4-5`, `claude-sonnet-4-6`. If you see a model error, reset this to `claude-haiku-4-5`.

- **Max tokens too low**
  If responses are getting cut off mid-sentence, increase `AI_MAX_TOKENS` in `config.py` or Settings.

---

## 3. Discord: Friends List Empty

**Symptom:** Jarvis says "Discord friends cache is empty" or the Debug window shows 0 friends.

This is the most common Discord issue. Here's why it happens and how to fix it:

**Cause A: Discord was running when Jarvis scanned (most common)**

Discord locks its local database files while it's open. Jarvis can still read them, but may get incomplete data.

**Fix:**
1. Fully quit Discord (right-click the system tray icon → Quit Discord — just clicking X doesn't quit it).
2. In Jarvis, click **🔄 Rescan**.
3. Reopen Discord after the scan finishes.

**Cause B: Discord hasn't synced its local cache yet**

The local cache is only written after Discord has been running for a while and has synced.

**Fix:**
1. Open Discord and leave it open for 2–5 minutes.
2. Browse your friends list while it's open.
3. Quit Discord fully, then click **🔄 Rescan** in Jarvis.

**Cause C: Discord is installed in an unusual location**

Jarvis looks in `%APPDATA%\discord` and `%LOCALAPPDATA%\Discord`. If you use Discord PTB (Public Test Build) or Canary, the folder names are `discordptb` and `discordcanary`.

**Fix:** Open `config.py` and update `DISCORD_PATH` to point to your Discord executable.

**Cause D: Friends cache hasn't been created yet**

First launch or after deleting `discord_friends_cache.json`.

**Fix:** Click **🔄 Rescan**. Check the System Log panel on the right — it will say how many friends were found.

**Cause E: You have no friends on Discord**

Jarvis can only find users you've actually added as friends in Discord. People in mutual servers don't count unless they're on your friends list.

**Manual workaround (always works):**

If automatic detection keeps failing, just tell Jarvis who your friends are:

> "Remember my friend Alex has Discord ID 123456789012345678"

Or in the Debug window, run:
```
[DISCORD_REMEMBER:Alex|123456789012345678]
```

To find someone's Discord ID: in Discord, go to Settings → Advanced → turn on Developer Mode. Then right-click any friend's name → Copy User ID.

---

## 4. Discord: Friend Not Found

**Symptom:** "Could not find a friend matching 'X'" even though they're in Discord.

**Causes and fixes:**

- **Name mismatch**
  Jarvis matches against Discord usernames and display names. Try their exact Discord username (the one without spaces and capital letters, like `cooluser123`), not their server nickname.

- **Cache is stale**
  They may have changed their username since the last scan. Click **🔄 Rescan**.

- **They're not on your friends list**
  Jarvis can only find actual Discord friends. If they're just a server member, you need to add them as a friend first, then rescan.

- **Fuzzy matching threshold**
  Very short names (1–2 characters) or names with special characters may not match well. Try using their exact username.

- **Register them manually**
  Tell Jarvis: "Remember my friend [name] has Discord ID [their ID]"

---

## 5. Discord: Call URI Failed

**Symptom:** "discord:// URI failed" warning, browser opens instead of Discord.

**Causes and fixes:**

- **Discord is not running**
  The `discord://` protocol handler only works when Discord is open. Launch Discord first, then try the call again.

- **Discord URI handler not registered**
  This can happen if Discord was installed via certain methods (e.g., some store installs).

  Fix: Reinstall Discord from https://discord.com/download. The installer registers the URI handler.

- **Discord is updating**
  If Discord is in the middle of an update, it may not respond to URI calls. Wait for it to finish updating.

- **Windows UAC or permissions**
  Try running Jarvis as Administrator (right-click `launch.bat` → Run as administrator).

---

## 6. Discord: Can't Call or Message Someone

**Symptom:** Jarvis opens their profile or DM, but you still have to click the call button manually.

**This is intentional.** Discord does not expose a URI that auto-starts a call without user confirmation. This is a privacy/safety design choice by Discord — they don't want any app to be able to start a call without you clicking something. Jarvis will always open the DM/profile so you can click Call yourself. This is the same behavior as any third-party Discord integration.

If you just want to open Discord to a specific DM quickly, that works automatically.

---

## 7. Steam / Games Not Launching

**Symptom:** "EXE not found" or Steam opens but the game doesn't launch.

**Causes and fixes:**

- **Steam is not installed at the default path**
  Default: `C:\Program Files (x86)\Steam\steam.exe`. If you installed Steam somewhere else, update `STEAM_PATH` in `config.py` or Settings.

- **Game name doesn't match**
  Jarvis searches by game folder name. Try the exact name as it appears in Steam → Library. Or use the Steam App ID directly: "Launch game ID 570" (570 = Dota 2).

- **Steam needs to be running first**
  Some games require Steam to be open before launching. Ask Jarvis to "Open Steam" first, then launch the game.

- **Game is not installed**
  Jarvis can only launch installed games. Make sure the game is downloaded and installed in Steam.

- **Game is in a non-default Steam library**
  If you have games on a different drive, Jarvis may not find them automatically. You can run `[STEAM_LIST]` in the Debug window to see what Jarvis found.

---

## 8. Voice / Microphone Not Working

**Symptom:** Clicking the 🎤 mic button does nothing or shows "PyAudio not installed."

**Fix — install the required packages:**
```
pip install SpeechRecognition pyaudio
```

If `pyaudio` fails to install on Windows, try:
```
pip install pipwin
pipwin install pyaudio
```

Or download a pre-built wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio and install with:
```
pip install PyAudio‑0.2.14‑cpXX‑cpXX‑win_amd64.whl
```
(Replace `cpXX` with your Python version, e.g., `cp311` for Python 3.11.)

**Other causes:**

- **No microphone connected**
  Make sure a mic is plugged in or Bluetooth audio with a mic is connected.

- **Mic permissions blocked**
  Windows 10/11: Settings → Privacy → Microphone → Allow apps to access your microphone → make sure it's On. Also check "Allow desktop apps to access your microphone."

- **Mic is in use by another app**
  Discord, Zoom, or other apps may have exclusive control of the microphone. Close them and try again.

- **Wrong microphone selected**
  If you have multiple audio devices, Windows may be using the wrong one. Set your preferred mic as the default in: Right-click speaker icon → Sound Settings → Input → choose your microphone.

- **Voice recognition service unreachable**
  The mic button uses Google's free speech API. It requires internet. If you're offline, it won't work.

---

## 9. Wake Word Not Triggering

**Symptom:** You say "Jarvis" but nothing happens.

**Prerequisites:** Wake word mode requires `SpeechRecognition` and `pyaudio` installed (see section 8). It's disabled by default — enable it in Settings (⚙) by checking "Always-On Wake."

**Causes and fixes:**

- **Wake word is disabled**
  Open Settings, check "Always-On Wake", and click Save.

- **Wrong wake word**
  Check Settings → Wake Word field. It defaults to `jarvis`. If you changed it, make sure you're saying the new word.

- **Too much background noise**
  The listener uses dynamic noise thresholding. Try in a quieter environment.

- **Mic sensitivity too low**
  The wake listener adjusts automatically, but it can take a few seconds to calibrate after starting. Wait a moment before speaking.

- **Python is using the wrong microphone**
  Same as section 8 — set your preferred mic as the default in Windows Sound Settings.

- **Always-on listener uses CPU**
  If Jarvis feels sluggish while wake-word mode is on, disable it and use the mic button instead.

---

## 10. Commands Not Executing

**Symptom:** Jarvis says it's doing something, but nothing happens on your PC.

**Causes and fixes:**

- **AI generated the command but with wrong formatting**
  Use the **🐛 Debug** window to run commands directly and see the raw output. This tells you if the command itself works outside of AI.

- **[RUN_EXE] path has spaces**
  Paths with spaces need to be quoted. Example: `[RUN_EXE:"C:\Program Files\App\app.exe"]`

- **[RUN_CMD] timed out**
  Commands have a 15-second timeout. Long-running commands will be cut off.

- **Process already running**
  Some apps (like Discord, Steam) may not relaunch if already open. They'll just focus the existing window.

- **Antivirus blocked execution**
  Check Windows Security → Protection History to see if a command was blocked.

- **UAC prompt appeared but Jarvis can't click it**
  Jarvis can't interact with UAC elevation prompts. If an app requires admin to launch, you'll need to run it manually or run Jarvis as Administrator.

- **The AI put the command tag inside a code block**
  Sometimes the AI wraps commands in markdown like \`[RUN_EXE:...]\`. This prevents Jarvis from parsing it. Try rephrasing your request more directly.

---

## 11. Snapshot Scan Failed or Slow

**Symptom:** "Snapshot failed" in status bar, or startup takes a very long time.

**Causes and fixes:**

- **First launch is always slow**
  Jarvis scans your entire system on first run (registry, drives, installed apps). This can take 30–120 seconds. Subsequent launches use the cached snapshot and are fast.

- **Very large Steam library**
  Scanning hundreds of games takes time. Normal behavior.

- **Permission errors on certain folders**
  Some system folders require admin access. Jarvis skips them silently.

- **Antivirus scanning slows file access**
  Add the Jarvis folder to your AV exclusions to speed up scans.

- **Old snapshot being used**
  Snapshots are cached. If you install new apps and Jarvis doesn't know about them, click **🔄 Rescan**.

- **Snapshot file is corrupted**
  Delete `system_snapshot.json` in the Jarvis folder and restart. A new one will be created.

---

## 12. App Crashed / Python Errors

**Symptom:** Jarvis closes unexpectedly or you see a Python traceback.

**How to get the error:**
Run Jarvis from a terminal instead of `launch.bat`:
```
cd path\to\jarvis_v2
python main.py
```
The error message will stay visible in the terminal.

**Common errors:**

- **`ModuleNotFoundError: No module named 'anthropic'`**
  Run: `pip install anthropic`

- **`ModuleNotFoundError: No module named 'pyautogui'`**
  Run: `pip install pyautogui`

- **`TclError: no display name and no $DISPLAY environment variable`**
  You're running Jarvis over SSH without a display. Jarvis requires a graphical desktop.

- **`RuntimeError: main thread is not in main loop`**
  A background thread tried to update the UI. This is a known race condition on startup — restart Jarvis.

- **`json.JSONDecodeError`**
  A cache file is corrupted. Delete `system_snapshot.json` and/or `discord_friends_cache.json` and restart.

- **Any other error**
  Copy the full traceback and search it. Most Python errors have well-documented solutions on Stack Overflow.

---

## 13. Screenshots Not Saving

**Symptom:** "Screenshot saved" but you can't find the file.

**Causes and fixes:**

- **File saved to Desktop**
  Screenshots go to your Desktop by default. Check there.

- **Desktop path is non-standard**
  If your Desktop is in a non-default location (e.g., on a different drive), the screenshot might fail silently. Ask Jarvis: "Where is my Desktop?" to confirm the path.

- **pyautogui not installed**
  Run: `pip install pyautogui`

- **Multi-monitor: wrong screen captured**
  `pyautogui` captures all monitors combined by default.

---

## 14. Volume Control Not Working

**Symptom:** "Volume set to X%" but the volume doesn't change.

**Causes and fixes:**

- **`pycaw` or `comtypes` not available**
  Jarvis uses PowerShell as a fallback for volume control. If that also fails, run:
  ```
  pip install pycaw comtypes
  ```

- **Volume is controlled by the app, not Windows**
  Games and media players often have their own volume separate from Windows master volume. Jarvis controls Windows master volume only.

- **Multiple audio outputs**
  Jarvis controls the default audio output device. If you have headphones and speakers, make sure the right one is set as default in Windows Sound Settings.

---

## 15. File / EXE Not Found Errors

**Symptom:** "EXE not found" or "File not found" when asking Jarvis to open something.

**Causes and fixes:**

- **App was installed after the last scan**
  Click **🔄 Rescan** to update the snapshot.

- **App name doesn't match**
  Jarvis searches by executable filename. Try the exact `.exe` name, e.g., "open chrome.exe" instead of "open Chrome."

- **App is a Microsoft Store app**
  Store apps don't have traditional `.exe` paths. Jarvis can still open them with `[RUN_CMD:start ms-windows-store://...]` or by their protocol URI.

- **Path contains special characters**
  Paths with `&`, `%`, `!` or non-ASCII characters can cause issues in shell commands. Try navigating to the folder first.

- **Network drive is disconnected**
  If the file is on a mapped network drive that's offline, it won't be accessible.

---

## 16. UI Looks Wrong / Fonts Missing

**Symptom:** UI text is garbled, fonts look wrong, or layout is broken.

**Causes and fixes:**

- **Consolas font not available**
  Consolas is a Microsoft font included with Windows. If you're on a non-standard Windows install, it may be missing. Change `FONT_FAMILY` in `config.py` to `"Courier New"` or `"Lucida Console"`.

- **DPI scaling issues**
  On high-DPI displays, set `WINDOW_WIDTH` and `WINDOW_HEIGHT` to larger values in `config.py`.

- **tkinter version mismatch**
  Some older Python builds have outdated tkinter. Update Python to the latest 3.x release.

---

## 17. Settings Not Saving Permanently

**Symptom:** You change settings in the Settings window, but they reset on next launch.

**This is by design.** The Settings window saves changes for the current session only. To make them permanent, edit `config.py` directly in any text editor. Each setting in the file has a comment explaining what it does.

For the API key specifically, you can also set it as a Windows environment variable:
```
setx ANTHROPIC_API_KEY "your-key-here"
```
This is more secure than storing it in `config.py`.

---

## Still Stuck?

1. Run Jarvis from a terminal (`python main.py`) to see the full error message.
2. Use the **🐛 Debug** window to test commands directly — this rules out AI-related issues.
3. Check the **System Log** panel on the right side of Jarvis for clues.
4. Delete cache files and restart: `system_snapshot.json`, `discord_friends_cache.json`.
5. Try running Jarvis as Administrator (some commands need elevated permissions).
