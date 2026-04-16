# ⚡ JARVIS — Desktop AI Assistant

A powerful AI assistant for Windows that gives Claude real control over your computer.

---

## Features

| Category | Capabilities |
|---|---|
| **Apps & Files** | Run any .exe, open files, launch programs |
| **Discord** | Open Discord, initiate calls, navigate to DMs |
| **Steam** | List installed games, launch by name or App ID |
| **System** | Screenshots, volume control, kill processes, shell commands |
| **Dangerous** | Shutdown, restart, lock workstation |

---

## Quick Start

### 1. Install Python
Download Python 3.10+ from [python.org](https://python.org). Make sure to check **"Add Python to PATH"** during install.

### 2. Get an Anthropic API Key
Sign up at [console.anthropic.com](https://console.anthropic.com) and create an API key.

### 3. Set Your API Key
**Option A — Environment variable (recommended):**
```bat
setx ANTHROPIC_API_KEY "sk-ant-..."
```
Then restart your terminal/PC.

**Option B — Edit `config.py`:**
```python
ANTHROPIC_API_KEY = "sk-ant-..."
```

**Option C — Settings button in the app** (temporary, resets on restart)

### 4. Launch
Double-click `launch.bat` — it installs dependencies and starts the app.

Or manually:
```bat
pip install anthropic
python main.py
```

---

## File Structure

```
jarvis/
├── main.py           # Entry point
├── config.py         # All configuration (API key, paths, etc.)
├── launch.bat        # One-click setup and launch
├── requirements.txt
│
├── core/
│   ├── ai_brain.py   # Claude API + command parser
│   └── executor.py   # All command handlers
│
└── ui/
    └── app.py        # Tkinter GUI
```

---

## How It Works

1. You type a message in the chat
2. The message is sent to Claude (claude-opus-4-5) with a system prompt explaining all available commands
3. Claude responds with natural language + special command tags like `[RUN_EXE:notepad.exe]`
4. The executor parses those tags and runs the actual system commands
5. Results are shown in the chat

### Command Tags (used by the AI automatically)

| Tag | Action |
|---|---|
| `[RUN_EXE:path]` | Launch an .exe file |
| `[OPEN_FILE:path]` | Open a file with default program |
| `[OPEN_URL:url]` | Open URL in browser |
| `[KILL_PROCESS:name]` | Kill a running process |
| `[LIST_FILES:dir]` | List files in a directory |
| `[RUN_CMD:command]` | Run a shell command |
| `[DISCORD_CALL:user_id]` | Call someone on Discord |
| `[DISCORD_MESSAGE:user\|msg]` | Navigate to Discord DM |
| `[OPEN_DISCORD]` | Open Discord |
| `[STEAM_LAUNCH:game]` | Launch a Steam game by name or ID |
| `[STEAM_LIST]` | List installed Steam games |
| `[OPEN_STEAM]` | Open Steam client |
| `[SCREENSHOT]` | Take a screenshot (saved to Desktop) |
| `[VOLUME:0-100]` | Set system volume |
| `[SHUTDOWN]` | Shutdown PC (10s delay) |
| `[RESTART]` | Restart PC (10s delay) |
| `[LOCK]` | Lock workstation |

---

## Discord Notes

Discord has a URI scheme (`discord://`) that JARVIS uses to open Discord and navigate.

- **Calling by User ID**: Works best with numeric Discord User IDs (right-click a user → Copy User ID in Developer Mode)
- **DMs**: JARVIS opens Discord and navigates to the DM screen. Full automated messaging requires a bot token.

To enable Discord Developer Mode: Discord Settings → Advanced → Developer Mode ✓

---

## Steam Notes

JARVIS scans your `steamapps` directory for installed games. It searches:
- `C:\Program Files (x86)\Steam\steamapps\`
- Any additional library folders defined in `libraryfolders.vdf`

You can say things like:
- *"Launch Cyberpunk 2077"*
- *"Open the game with Steam ID 730"* (CS2)
- *"What Steam games do I have installed?"*

---

## Example Commands

Try saying:
- *"Open Notepad"*
- *"Launch my Steam game Elden Ring"*
- *"List my installed Steam games"*
- *"Take a screenshot"*
- *"Set volume to 30%"*
- *"Open Discord and call my friend, their ID is 123456789"*
- *"List the files on my Desktop"*
- *"Open Chrome and go to youtube.com"*
- *"Kill the process explorer.exe"*

---

## Configuration (`config.py`)

```python
ANTHROPIC_API_KEY = "..."   # Your API key
STEAM_PATH = r"C:\..."      # Path to steam.exe
DISCORD_PATH = r"C:\..."    # Path to Discord.exe
ASSISTANT_NAME = "Jarvis"   # Change to your liking
AI_MODEL = "claude-opus-4-5" # Model to use
```

---

## Security Note

JARVIS has real power over your PC. Commands like `[RUN_CMD:...]` and `[SHUTDOWN]` are executed for real. The AI will not run destructive commands unless you explicitly ask it to. Still — be thoughtful about what you ask it to do.
