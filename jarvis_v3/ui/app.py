"""
ui/app.py  –  JARVIS  ·  Holographic HUD Interface  (v4)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Optional:  pip install customtkinter   (graceful fallback to plain tkinter)
"""

import threading
import os
import sys
import time
import queue

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import tkinter.font as tkfont

from core.ai_brain import AIBrain
from core.executor import CommandExecutor
from core.system_snapshot import load_or_create_snapshot, refresh_snapshot, get_snapshot_summary
from core.discord_friends import get_friends, friends_summary, add_friend_manually
from core.voice import is_available as mic_available, listen_once, start_wake_listener, stop_wake_listener
import config

# ─── Palette ──────────────────────────────────────────────────────────────────
C = {
    "void":        "#050709",
    "bg":          "#080c12",
    "panel":       "#0b1018",
    "glass":       "#0e1520",
    "border":      "#162030",
    "border_hi":   "#1e3050",
    "cyan":        "#00e5ff",
    "cyan_dim":    "#007a99",
    "green":       "#00ff9f",
    "green_dim":   "#007a4d",
    "amber":       "#ffaa00",
    "red":         "#ff3860",
    "purple":      "#b06dff",
    "text":        "#a8c4d8",
    "text_dim":    "#3a5060",
    "text_bright": "#e0f0ff",
    "user_bubble": "#0d1e30",
    "ai_bubble":   "#070e14",
    "cmd":         "#ff8c00",
    "cmd_result":  "#00cc80",
}

FONT_MONO  = "Consolas"
FONT_UI    = "Segoe UI"
FONT_TITLE = "Segoe UI"


# ─── Animated pulse label ─────────────────────────────────────────────────────

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _blend(c1, c2, t):
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return "#{:02x}{:02x}{:02x}".format(
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )


class PulseLabel(tk.Label):
    """Label that softly pulses between two colors."""
    def __init__(self, master, c1, c2, steps=30, delay=40, **kw):
        super().__init__(master, **kw)
        self._c1, self._c2 = c1, c2
        self._steps, self._delay = steps, delay
        self._t = 0
        self._dir = 1
        self._animate()

    def _animate(self):
        self._t += self._dir / self._steps
        if self._t >= 1:
            self._dir = -1
        if self._t <= 0:
            self._dir = 1
        self.configure(fg=_blend(self._c1, self._c2, self._t))
        self.after(self._delay, self._animate)


# ─── Main Application ─────────────────────────────────────────────────────────

class JarvisApp:
    """JARVIS — Holographic HUD Interface v4."""

    def __init__(self):
        self.brain    = AIBrain()
        self.executor = CommandExecutor(log_fn=self._log_system)
        self._streaming      = False
        self._snapshot: dict = {}
        self._snapshot_ready = False
        self._mic_active     = False
        self._wake_running   = False
        self._msg_count      = 0

        self._build_window()
        self._build_ui()
        self._log_system("⬡ {} core online".format(config.ASSISTANT_NAME))
        self._print_welcome()
        self._tick_clock()

        threading.Thread(target=self._init_snapshot, daemon=True).start()

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def _init_snapshot(self):
        self._log_system("⬡ loading system snapshot…")
        self._set_status("scanning", "SCANNING SYSTEM…")
        try:
            snap = load_or_create_snapshot(log_fn=self._log_system)
            self._snapshot = snap
            self._inject_snapshot_into_prompt(snap)
            self._snapshot_ready = True

            self._log_system("⬡ loading discord friends cache…")
            friends = get_friends()
            if friends:
                self._log_system("⬡ {} discord friends loaded".format(len(friends)))
            else:
                self._log_system("⚠ no discord friends found — open discord first")
            self._inject_friends_into_prompt(friends)

            n_apps  = len(snap.get("installed_apps", []))
            n_games = len(snap.get("steam_games", []))
            n_fri   = len(friends) if friends else 0
            self._log_system(
                "⬡ snapshot ready  //  apps:{}  steam:{}  friends:{}".format(
                    n_apps, n_games, n_fri)
            )
            self._set_status("ready", "ONLINE")
            self.root.after(0, lambda: self._update_snapshot_sidebar(snap, friends))

            if config.WAKE_WORD_ENABLED:
                self._start_wake_word()
        except Exception as e:
            self._log_system("✖ snapshot error: {}".format(e))
            self._set_status("error", "SNAPSHOT FAILED")

    def _inject_snapshot_into_prompt(self, snap):
        summary = get_snapshot_summary(snap)
        config.SYSTEM_PROMPT = summary + "\n\n" + config.SYSTEM_PROMPT_BASE

    def _inject_friends_into_prompt(self, friends):
        if not friends:
            return
        config.SYSTEM_PROMPT = config.SYSTEM_PROMPT + "\n\n" + friends_summary(friends)

    def _do_refresh_snapshot(self):
        if self._streaming:
            return
        self._log_system("⬡ refreshing snapshot…")
        self._set_status("scanning", "RE-SCANNING…")

        def _run():
            try:
                snap = refresh_snapshot(log_fn=self._log_system)
                self._snapshot = snap
                self._inject_snapshot_into_prompt(snap)
                friends = get_friends(force_refresh=True)
                self._inject_friends_into_prompt(friends)
                self._snapshot_ready = True
                n = len(friends) if friends else 0
                self._log_system("⬡ snapshot refreshed  //  {} friends".format(n))
                self._set_status("ready", "ONLINE")
                self.root.after(0, lambda: self._update_snapshot_sidebar(snap, friends))
            except Exception as e:
                self._log_system("✖ refresh error: {}".format(e))
                self._set_status("error", "REFRESH FAILED")

        threading.Thread(target=_run, daemon=True).start()

    def _update_snapshot_sidebar(self, snap, friends=None):
        n_apps  = len(snap.get("installed_apps", []))
        n_games = len(snap.get("steam_games", []))
        n_fri   = len(friends) if friends else 0
        cpu     = snap.get("hardware", {}).get("cpu", "Unknown")[:26]
        taken   = snap.get("timestamp", "")[:10]

        lines = [
            "CPU   {}".format(cpu),
            "APPS  {}   STEAM  {}".format(n_apps, n_games),
            "DISCORD  {} friends".format(n_fri),
            "SNAP  {}".format(taken),
        ]

        def _u():
            try:
                self.snap_text.configure(state=tk.NORMAL)
                self.snap_text.delete("1.0", tk.END)
                for ln in lines:
                    self.snap_text.insert(tk.END, ln + "\n")
                self.snap_text.configure(state=tk.DISABLED)
            except Exception:
                pass

        self.root.after(0, _u)

    # ── Window & UI construction ───────────────────────────────────────────────

    def _build_window(self):
        self.root = tk.Tk()
        self.root.title(config.ASSISTANT_NAME)
        self.root.geometry("{}x{}".format(config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        self.root.minsize(860, 560)
        self.root.configure(bg=C["void"])
        try:
            self.root.wm_attributes("-alpha", 0.97)
        except Exception:
            pass

    def _build_ui(self):
        self._build_titlebar()

        body = tk.Frame(self.root, bg=C["void"])
        body.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        # Left: chat + input
        left = tk.Frame(body, bg=C["void"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_chat_area(left)
        self._build_input_area(left)

        # Right: sidebar
        sidebar = tk.Frame(body, bg=C["void"], width=224)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

    def _build_titlebar(self):
        bar = tk.Frame(self.root, bg=C["void"], height=52)
        bar.pack(fill=tk.X, padx=6, pady=(6, 0))
        bar.pack_propagate(False)

        # Left: logo
        left = tk.Frame(bar, bg=C["void"])
        left.pack(side=tk.LEFT, fill=tk.Y)

        self._bolt = PulseLabel(
            left, C["cyan"], C["cyan_dim"],
            text="⚡", bg=C["void"],
            font=(FONT_TITLE, 22, "bold"),
            steps=40, delay=35,
        )
        self._bolt.pack(side=tk.LEFT, padx=(6, 4))

        name_block = tk.Frame(left, bg=C["void"])
        name_block.pack(side=tk.LEFT)
        tk.Label(
            name_block, text=config.ASSISTANT_NAME.upper(),
            bg=C["void"], fg=C["text_bright"],
            font=(FONT_TITLE, 15, "bold"),
        ).pack(anchor="w")
        tk.Label(
            name_block, text="DESKTOP AI ASSISTANT  //  HUD v4",
            bg=C["void"], fg=C["text_dim"],
            font=(FONT_MONO, 7),
        ).pack(anchor="w")

        # Right: clock + status + toolbar
        right = tk.Frame(bar, bg=C["void"])
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=4)

        # Clock
        self._clock_var = tk.StringVar(value="")
        tk.Label(
            right, textvariable=self._clock_var,
            bg=C["void"], fg=C["text_dim"],
            font=(FONT_MONO, 8),
        ).pack(side=tk.RIGHT, padx=8, anchor="c")

        # Status pill
        status_pill = tk.Frame(right, bg=C["border"], padx=1, pady=1)
        status_pill.pack(side=tk.RIGHT, anchor="c", padx=(8, 0))
        pill_inner = tk.Frame(status_pill, bg=C["glass"])
        pill_inner.pack()
        self._status_dot = tk.Label(
            pill_inner, text="●", bg=C["glass"],
            font=(FONT_MONO, 8), fg=C["amber"],
        )
        self._status_dot.pack(side=tk.LEFT, padx=(8, 2), pady=4)
        self._status_text = tk.StringVar(value="INITIALIZING")
        tk.Label(
            pill_inner, textvariable=self._status_text,
            bg=C["glass"], fg=C["text_dim"],
            font=(FONT_MONO, 7, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 10), pady=4)

        # Toolbar buttons (reversed so LEFT packing comes out right-to-left)
        btn_specs = [
            ("SETTINGS", self._show_settings,       C["text_dim"]),
            ("CLEAR",    self._clear_chat,           C["text_dim"]),
            ("FILE",     self._browse_file,          C["cyan_dim"]),
            ("RESCAN",   self._do_refresh_snapshot,  C["purple"]),
            ("DEBUG",    self._show_debug,           C["amber"]),
        ]
        for label, cmd, color in reversed(btn_specs):
            self._hud_btn(right, label, cmd, color).pack(side=tk.RIGHT, padx=2, pady=8)

        # Separator
        tk.Frame(self.root, bg=C["border"], height=1).pack(fill=tk.X, padx=6)

    def _build_chat_area(self, parent):
        wrapper = tk.Frame(parent, bg=C["border"], padx=1, pady=1)
        wrapper.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(wrapper, bg=C["bg"])
        inner.pack(fill=tk.BOTH, expand=True)

        fs = int(config.FONT_SIZE) if hasattr(config, "FONT_SIZE") else 10

        self.chat_display = tk.Text(
            inner,
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg=C["bg"],
            fg=C["text"],
            font=(FONT_MONO, fs),
            borderwidth=0, relief=tk.FLAT,
            padx=16, pady=14,
            insertbackground=C["cyan"],
            selectbackground=C["user_bubble"],
            cursor="arrow",
            spacing1=2, spacing3=2,
        )
        sb = tk.Scrollbar(
            inner, orient=tk.VERTICAL, command=self.chat_display.yview,
            bg=C["panel"], troughcolor=C["void"],
            activebackground=C["border_hi"],
            relief=tk.FLAT, width=8, borderwidth=0,
        )
        self.chat_display.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._setup_text_tags()

    def _build_input_area(self, parent):
        tk.Frame(parent, bg=C["border_hi"], height=1).pack(fill=tk.X)

        area = tk.Frame(parent, bg=C["panel"], pady=8)
        area.pack(fill=tk.X)

        row = tk.Frame(area, bg=C["panel"])
        row.pack(fill=tk.X, padx=10)

        # Mic button
        self.mic_btn = tk.Button(
            row, text="🎤",
            command=self._on_mic_click,
            bg=C["panel"], fg=C["text_dim"],
            font=(FONT_UI, 14),
            borderwidth=0, relief=tk.FLAT,
            padx=4, pady=0,
            cursor="hand2",
            activebackground=C["panel"],
            activeforeground=C["cyan"],
        )
        self.mic_btn.pack(side=tk.LEFT, padx=(0, 6), fill=tk.Y)

        # Input box with focus-glow border
        self._input_wrap = tk.Frame(row, bg=C["border_hi"], padx=1, pady=1)
        self._input_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        fs = int(config.FONT_SIZE) if hasattr(config, "FONT_SIZE") else 10
        self.input_field = tk.Text(
            self._input_wrap,
            height=3,
            bg=C["glass"], fg=C["text_bright"],
            font=(FONT_MONO, fs),
            borderwidth=0, relief=tk.FLAT,
            padx=12, pady=8,
            insertbackground=C["cyan"],
            wrap=tk.WORD,
            selectbackground=C["user_bubble"],
        )
        self.input_field.pack(fill=tk.BOTH, expand=True)
        self.input_field.bind("<Return>",       self._on_enter)
        self.input_field.bind("<Shift-Return>", lambda e: None)
        self.input_field.bind("<FocusIn>",
            lambda e: self._input_wrap.configure(bg=C["cyan_dim"]))
        self.input_field.bind("<FocusOut>",
            lambda e: self._input_wrap.configure(bg=C["border_hi"]))

        # Send button
        send = tk.Button(
            row, text="SEND  ▶",
            command=self._send_message,
            bg=C["cyan"], fg=C["void"],
            font=(FONT_MONO, 10, "bold"),
            borderwidth=0, relief=tk.FLAT,
            padx=16, pady=0,
            cursor="hand2",
            activebackground=C["green"],
            activeforeground=C["void"],
        )
        send.pack(side=tk.RIGHT, padx=(8, 0), fill=tk.Y)

        # Status / token hint bar
        hint_row = tk.Frame(area, bg=C["panel"])
        hint_row.pack(fill=tk.X, padx=12, pady=(2, 0))
        self.status_var = tk.StringVar(value="initializing…")
        self.token_var  = tk.StringVar(value="")
        tk.Label(hint_row, textvariable=self.status_var,
                 bg=C["panel"], fg=C["text_dim"],
                 font=(FONT_MONO, 7), anchor="w").pack(side=tk.LEFT)
        tk.Label(hint_row, textvariable=self.token_var,
                 bg=C["panel"], fg=C["text_dim"],
                 font=(FONT_MONO, 7), anchor="e").pack(side=tk.RIGHT)

    def _build_sidebar(self, parent):
        # ── Snapshot info ─────────────────────────────────────────────────────
        self._sidebar_section(parent, "◈ SYSTEM SNAPSHOT", C["purple"])

        snap_wrap = tk.Frame(parent, bg=C["border"], padx=1, pady=1)
        snap_wrap.pack(fill=tk.X, padx=8, pady=(4, 8))

        self.snap_text = tk.Text(
            snap_wrap,
            height=4, bg=C["glass"], fg=C["purple"],
            font=(FONT_MONO, 7),
            borderwidth=0, relief=tk.FLAT,
            padx=8, pady=6,
            state=tk.DISABLED,
            wrap=tk.NONE,
        )
        self.snap_text.pack(fill=tk.X)

        self.snap_text.configure(state=tk.NORMAL)
        self.snap_text.insert(tk.END, "scanning…\n")
        self.snap_text.configure(state=tk.DISABLED)

        # ── Quick actions ─────────────────────────────────────────────────────
        self._sidebar_section(parent, "◈ QUICK ACTIONS", C["cyan_dim"])

        quick_actions = [
            ("🎮  STEAM",            "Open Steam for me"),
            ("💬  DISCORD",          "Open Discord"),
            ("🎮  LIST GAMES",       "List my installed Steam games"),
            ("📸  SCREENSHOT",       "Take a screenshot"),
            ("📂  DESKTOP FILES",    "List files on my Desktop"),
            ("💾  DISK SPACE",       "Show my disk drives and free space"),
            ("🧩  APPS",             "What applications do I have installed?"),
            ("⚙️   PROCESSES",       "What processes are currently running?"),
            ("👥  DISCORD FRIENDS",  "Who are my Discord friends in your cache?"),
            ("🔊  VOLUME 50",        "Set volume to 50%"),
            ("🔊  VOLUME 100",       "Set volume to 100%"),
            ("🔒  LOCK PC",          "Lock my workstation"),
        ]

        qa_frame = tk.Frame(parent, bg=C["void"])
        qa_frame.pack(fill=tk.X, padx=8)

        for label, cmd in quick_actions:
            btn = tk.Button(
                qa_frame, text=label, anchor="w",
                command=lambda c=cmd: self._quick_action(c),
                bg=C["glass"], fg=C["text"],
                font=(FONT_MONO, 7),
                borderwidth=0, relief=tk.FLAT,
                padx=10, pady=4,
                cursor="hand2",
                activebackground=C["user_bubble"],
                activeforeground=C["cyan"],
            )
            btn.pack(fill=tk.X, pady=1)
            btn.bind("<Enter>", lambda e, b=btn: b.configure(fg=C["cyan"]))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(fg=C["text"]))

        # ── System log ────────────────────────────────────────────────────────
        self._sidebar_section(parent, "◈ SYSTEM LOG", C["text_dim"])

        log_wrap = tk.Frame(parent, bg=C["border"], padx=1, pady=1)
        log_wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))

        self.log_display = tk.Text(
            log_wrap,
            wrap=tk.WORD, state=tk.DISABLED,
            bg=C["void"], fg=C["text_dim"],
            font=(FONT_MONO, 7),
            borderwidth=0, relief=tk.FLAT,
            padx=8, pady=6,
        )
        log_sb = tk.Scrollbar(
            log_wrap, orient=tk.VERTICAL, command=self.log_display.yview,
            bg=C["panel"], troughcolor=C["void"],
            relief=tk.FLAT, width=5, borderwidth=0,
        )
        self.log_display.configure(yscrollcommand=log_sb.set)
        log_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # ── Text tags ─────────────────────────────────────────────────────────────

    def _setup_text_tags(self):
        fs = int(config.FONT_SIZE) if hasattr(config, "FONT_SIZE") else 10

        self.chat_display.tag_configure("user_label",
            foreground=C["cyan"],
            font=(FONT_MONO, 8, "bold"),
            spacing1=10)
        self.chat_display.tag_configure("user_text",
            foreground=C["text_bright"],
            background=C["user_bubble"],
            font=(FONT_MONO, fs),
            lmargin1=8, lmargin2=8, rmargin=8,
            spacing1=2, spacing3=6)
        self.chat_display.tag_configure("ai_label",
            foreground=C["green"],
            font=(FONT_MONO, 8, "bold"),
            spacing1=10)
        self.chat_display.tag_configure("ai_text",
            foreground=C["text"],
            background=C["ai_bubble"],
            font=(FONT_MONO, fs),
            lmargin1=8, lmargin2=8, rmargin=8,
            spacing1=2, spacing3=6)
        self.chat_display.tag_configure("cmd_tag",
            foreground=C["cmd"],
            font=(FONT_MONO, fs, "bold"),
            spacing1=2)
        self.chat_display.tag_configure("cmd_result",
            foreground=C["cmd_result"],
            font=(FONT_MONO, fs - 1),
            lmargin1=16, lmargin2=16)
        self.chat_display.tag_configure("error",
            foreground=C["red"],
            font=(FONT_MONO, fs))
        self.chat_display.tag_configure("separator",
            foreground=C["border_hi"],
            font=(FONT_MONO, 6),
            spacing1=4, spacing3=4)
        self.chat_display.tag_configure("welcome",
            foreground=C["text_dim"],
            font=(FONT_MONO, fs - 1),
            lmargin1=8, lmargin2=8)
        self.chat_display.tag_configure("welcome_hi",
            foreground=C["cyan_dim"],
            font=(FONT_MONO, fs - 1),
            lmargin1=8, lmargin2=8)

    # ── Send / process message ────────────────────────────────────────────────

    def _send_message(self):
        if self._streaming:
            return
        message = self.input_field.get("1.0", tk.END).strip()
        if not message:
            return
        self.input_field.delete("1.0", tk.END)
        self._display_user_message(message)
        threading.Thread(
            target=self._process_message, args=(message,), daemon=True
        ).start()

    def _on_enter(self, event):
        if not event.state & 0x1:   # not Shift
            self._send_message()
            return "break"

    def _quick_action(self, command: str):
        self.input_field.delete("1.0", tk.END)
        self.input_field.insert("1.0", command)
        self._send_message()

    def _process_message(self, message: str):
        self._streaming = True
        self._set_status("thinking", "THINKING…")
        self.root.after(0, lambda: self.status_var.set("processing…"))
        try:
            self._chat_append("\n{}  ".format(config.ASSISTANT_NAME), "ai_label")
            full_response = ""
            for chunk in self.brain.chat_stream(message):
                full_response += chunk
                self.root.after(0, lambda c=chunk: self._stream_chunk(c))
            self._chat_append("\n", "ai_text")

            commands = self.brain.extract_commands(full_response)
            if commands:
                for cmd in commands:
                    self._chat_append("  ⬡ {}\n".format(cmd["tag"]), "cmd_tag")
                    result = self.executor.execute(cmd)
                    self._chat_append("  → {}\n".format(result), "cmd_result")

            self._msg_count += 1
            self.root.after(0, lambda: self.token_var.set("msg #{}".format(self._msg_count)))
            self._set_status("ready", "ONLINE")
            self.root.after(0, lambda: self.status_var.set("ready"))
        except Exception as e:
            self._chat_append(
                "\n✖ Error: {}\n"
                "  Check your API key in Settings, or run Debug to test commands.\n".format(e),
                "error",
            )
            self._set_status("error", "ERROR")
            self.root.after(0, lambda: self.status_var.set("error"))
        finally:
            self._streaming = False
            self.root.after(0, lambda: self.chat_display.see(tk.END))

    def _stream_chunk(self, chunk: str):
        self._chat_append(chunk, "ai_text")
        self.chat_display.see(tk.END)

    def _display_user_message(self, message: str):
        self._chat_append("\nYOU  ", "user_label")
        self._chat_append("{}\n".format(message), "user_text")

    def _chat_append(self, text: str, tag: str = ""):
        self.chat_display.configure(state=tk.NORMAL)
        if tag:
            self.chat_display.insert(tk.END, text, tag)
        else:
            self.chat_display.insert(tk.END, text)
        self.chat_display.configure(state=tk.DISABLED)

    def _log_system(self, message: str):
        def _write():
            self.log_display.configure(state=tk.NORMAL)
            ts = time.strftime("%H:%M:%S")
            self.log_display.insert(tk.END, "{}  {}\n".format(ts, message))
            self.log_display.configure(state=tk.DISABLED)
            self.log_display.see(tk.END)
        try:
            self.root.after(0, _write)
        except Exception:
            pass

    # ── Status helpers ────────────────────────────────────────────────────────

    def _set_status(self, mode: str, text: str):
        color_map = {
            "ready":    C["green"],
            "thinking": C["cyan"],
            "scanning": C["amber"],
            "error":    C["red"],
        }
        col = color_map.get(mode, C["amber"])
        def _u():
            try:
                self._status_dot.configure(fg=col)
                self._status_text.set(text)
            except Exception:
                pass
        self.root.after(0, _u)

    def _tick_clock(self):
        self._clock_var.set(time.strftime("%H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    # ── UI helpers ────────────────────────────────────────────────────────────

    def _sidebar_section(self, parent, title, color):
        f = tk.Frame(parent, bg=C["void"])
        f.pack(fill=tk.X, padx=8, pady=(10, 2))
        tk.Label(f, text=title, bg=C["void"], fg=color,
                 font=(FONT_MONO, 7, "bold")).pack(side=tk.LEFT)
        tk.Frame(f, bg=color, height=1).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

    def _hud_btn(self, parent, text, command, fg):
        btn = tk.Button(
            parent, text=text,
            command=command,
            bg=C["glass"], fg=fg,
            font=(FONT_MONO, 7, "bold"),
            borderwidth=1, relief=tk.FLAT,
            padx=8, pady=3,
            cursor="hand2",
            activebackground=C["border"],
            activeforeground=C["text_bright"],
        )
        btn.bind("<Enter>", lambda e: btn.configure(bg=C["border"]))
        btn.bind("<Leave>", lambda e: btn.configure(bg=C["glass"]))
        return btn

    # ── Misc actions ──────────────────────────────────────────────────────────

    def _clear_chat(self):
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.configure(state=tk.DISABLED)
        self.brain.reset_conversation()
        self._print_welcome()
        self._log_system("⬡ conversation cleared")

    def _browse_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.input_field.delete("1.0", tk.END)
            self.input_field.insert("1.0", 'Open the file "{}"'.format(path))
            self._send_message()

    def _print_welcome(self):
        self._chat_append(
            "  ⚡ {}  —  HOLOGRAPHIC HUD v4\n"
            "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n".format(
                config.ASSISTANT_NAME.upper()),
            "separator",
        )
        lines = [
            ("  I know your installed apps, Steam library, running processes,\n"
             "  disk drives, desktop files, and Discord friends.\n\n",      "welcome"),
            ("  Try saying:\n",                                             "welcome"),
            ('  ▸  "Call Alex on Discord"\n',                              "welcome_hi"),
            ('  ▸  "Launch Elden Ring"\n',                                 "welcome_hi"),
            ('  ▸  "What processes are using the most CPU?"\n',            "welcome_hi"),
            ('  ▸  "Take a screenshot"\n\n',                               "welcome_hi"),
            ("  Tip: use DEBUG in the toolbar to run commands without AI credits.\n\n",
             "welcome"),
        ]
        for text, tag in lines:
            self._chat_append(text, tag)
        self._chat_append("  " + "─" * 54 + "\n", "separator")

    # ── Settings window ───────────────────────────────────────────────────────

    def _show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.geometry("540x490")
        win.configure(bg=C["bg"])
        win.resizable(False, False)

        # Header
        hdr = tk.Frame(win, bg=C["panel"], pady=12)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="⚙  SETTINGS",
                 bg=C["panel"], fg=C["cyan"],
                 font=(FONT_MONO, 13, "bold")).pack(padx=20, anchor="w")
        tk.Label(hdr, text="Changes apply to this session only.  Edit config.py to persist.",
                 bg=C["panel"], fg=C["text_dim"],
                 font=(FONT_MONO, 7)).pack(padx=20, anchor="w")
        tk.Frame(win, bg=C["border"], height=1).pack(fill=tk.X)

        body = tk.Frame(win, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        fields = [
            ("API KEY",      "ANTHROPIC_API_KEY"),
            ("MODEL",        "AI_MODEL"),
            ("MAX TOKENS",   "AI_MAX_TOKENS"),
            ("STEAM PATH",   "STEAM_PATH"),
            ("DISCORD PATH", "DISCORD_PATH"),
            ("WAKE WORD",    "WAKE_WORD"),
        ]
        entries = {}
        for label, attr in fields:
            row = tk.Frame(body, bg=C["bg"])
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label, bg=C["bg"], fg=C["text_dim"],
                     font=(FONT_MONO, 7, "bold"), width=14, anchor="w").pack(side=tk.LEFT)
            wrap = tk.Frame(row, bg=C["border_hi"], padx=1, pady=1)
            wrap.pack(side=tk.LEFT, fill=tk.X, expand=True)
            e = tk.Entry(wrap, bg=C["glass"], fg=C["text_bright"],
                         insertbackground=C["cyan"],
                         borderwidth=0, font=(FONT_MONO, 9))
            e.pack(fill=tk.X, padx=4, pady=3)
            e.insert(0, str(getattr(config, attr, "")))
            entries[attr] = e

        # Wake-word toggle
        wake_row = tk.Frame(body, bg=C["bg"])
        wake_row.pack(fill=tk.X, pady=3)
        tk.Label(wake_row, text="ALWAYS-ON", bg=C["bg"], fg=C["text_dim"],
                 font=(FONT_MONO, 7, "bold"), width=14, anchor="w").pack(side=tk.LEFT)
        wake_var = tk.BooleanVar(value=config.WAKE_WORD_ENABLED)
        tk.Checkbutton(wake_row, variable=wake_var,
                       bg=C["bg"], fg=C["text"],
                       selectcolor=C["glass"], activebackground=C["bg"],
                       text="Listen for wake word in background").pack(side=tk.LEFT)

        # Info labels
        snap_path = self._snapshot.get("snapshot_path", "not yet created")
        mic_ok = "✅ pyaudio available" if mic_available() else "⚠ pyaudio not installed"
        tk.Label(body, text="snapshot:  {}".format(snap_path),
                 bg=C["bg"], fg=C["text_dim"],
                 font=(FONT_MONO, 7), wraplength=460, anchor="w").pack(fill=tk.X, pady=(8, 0))
        tk.Label(body, text="mic:  {}".format(mic_ok),
                 bg=C["bg"], fg=C["text_dim"],
                 font=(FONT_MONO, 7), anchor="w").pack(fill=tk.X)

        def save():
            for attr, entry in entries.items():
                val = entry.get()
                if attr == "AI_MAX_TOKENS":
                    try:
                        val = int(val)
                    except ValueError:
                        pass
                setattr(config, attr, val)
            config.WAKE_WORD_ENABLED = wake_var.get()
            if config.WAKE_WORD_ENABLED and not self._wake_running:
                self._start_wake_word()
            elif not config.WAKE_WORD_ENABLED and self._wake_running:
                stop_wake_listener()
                self._wake_running = False
                self._log_system("⬡ wake-word listener stopped")
            self.brain.client = __import__("anthropic").Anthropic(
                api_key=config.ANTHROPIC_API_KEY)
            messagebox.showinfo("Saved", "Settings saved for this session.", parent=win)
            win.destroy()

        tk.Frame(win, bg=C["border"], height=1).pack(fill=tk.X)
        tk.Button(win, text="SAVE  ✓", command=save,
                  bg=C["cyan"], fg=C["void"],
                  font=(FONT_MONO, 9, "bold"),
                  borderwidth=0, relief=tk.FLAT, padx=20, pady=8,
                  cursor="hand2").pack(pady=12)

    # ── Debug window ──────────────────────────────────────────────────────────

    def _show_debug(self):
        win = tk.Toplevel(self.root)
        win.title("Debug — Direct Command Executor")
        win.geometry("660x540")
        win.configure(bg=C["bg"])

        hdr = tk.Frame(win, bg=C["panel"], pady=10)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="⬡  DEBUG — DIRECT COMMAND EXECUTOR",
                 bg=C["panel"], fg=C["amber"],
                 font=(FONT_MONO, 11, "bold")).pack(padx=20, anchor="w")
        tk.Label(hdr, text="Execute command tags directly — no AI credits used.",
                 bg=C["panel"], fg=C["text_dim"],
                 font=(FONT_MONO, 7)).pack(padx=20, anchor="w")
        tk.Frame(win, bg=C["border"], height=1).pack(fill=tk.X)

        body = tk.Frame(win, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # Command input row
        input_row = tk.Frame(body, bg=C["bg"])
        input_row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(input_row, text="COMMAND", bg=C["bg"], fg=C["text_dim"],
                 font=(FONT_MONO, 7, "bold"), width=9, anchor="w").pack(side=tk.LEFT)
        wrap = tk.Frame(input_row, bg=C["border_hi"], padx=1, pady=1)
        wrap.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8))
        cmd_entry = tk.Entry(wrap, bg=C["glass"], fg=C["text_bright"],
                             insertbackground=C["cyan"],
                             borderwidth=0, font=(FONT_MONO, 9))
        cmd_entry.pack(fill=tk.X, padx=4, pady=3)
        cmd_entry.insert(0, "[DISCORD_CALL:FriendName]")

        # Output area
        out_wrap = tk.Frame(body, bg=C["border"], padx=1, pady=1)
        out_wrap.pack(fill=tk.BOTH, expand=True)
        out = tk.Text(out_wrap, wrap=tk.WORD, state=tk.DISABLED, height=10,
                      bg=C["void"], fg=C["text"],
                      font=(FONT_MONO, 8),
                      borderwidth=0, relief=tk.FLAT, padx=10, pady=8)
        out_sb = tk.Scrollbar(out_wrap, orient=tk.VERTICAL, command=out.yview,
                              bg=C["panel"], troughcolor=C["void"],
                              relief=tk.FLAT, width=6, borderwidth=0)
        out.configure(yscrollcommand=out_sb.set)
        out_sb.pack(side=tk.RIGHT, fill=tk.Y)
        out.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def _append(msg, col=None):
            out.configure(state=tk.NORMAL)
            if col:
                tag = "_c_{}".format(col.replace("#", ""))
                out.tag_configure(tag, foreground=col)
                out.insert(tk.END, msg + "\n", tag)
            else:
                out.insert(tk.END, msg + "\n")
            out.configure(state=tk.DISABLED)
            out.see(tk.END)

        def _run():
            raw = cmd_entry.get().strip()
            if not raw:
                return
            _append("\n▶  {}".format(raw), C["amber"])
            cmds = self.brain.extract_commands(raw)
            if not cmds:
                _append("  ✖ no valid command tag found\n"
                        "  format:  [COMMAND_NAME:argument]  e.g. [VOLUME:50]", C["red"])
                return
            for cmd in cmds:
                _append("  ⬡ executing:  {}".format(cmd["tag"]), C["cyan_dim"])
                result = self.executor.execute(cmd)
                _append("  ✓ {}\n".format(result), C["green"])

        run_btn = tk.Button(input_row, text="▶ RUN", command=_run,
                            bg=C["amber"], fg=C["void"],
                            font=(FONT_MONO, 8, "bold"),
                            borderwidth=0, relief=tk.FLAT, padx=10, pady=2,
                            cursor="hand2")
        run_btn.pack(side=tk.LEFT)
        cmd_entry.bind("<Return>", lambda e: _run())

        # Preset buttons
        self._sidebar_section(body, "PRESETS", C["text_dim"])
        pf = tk.Frame(body, bg=C["bg"])
        pf.pack(fill=tk.X, pady=4)

        presets = [
            ("[OPEN_DISCORD]",               "Discord"),
            ("[DISCORD_CALL:FriendName]",    "D-Call"),
            ("[DISCORD_MESSAGE:Name|hey]",   "D-DM"),
            ("[VOLUME:50]",                  "Vol 50"),
            ("[SCREENSHOT]",                 "Screenshot"),
            ("[LOCK]",                       "Lock"),
            ("[OPEN_STEAM]",                 "Steam"),
            ("[STEAM_LIST]",                 "Games"),
            ("[LIST_FILES:C:\\\\]",          "C:\\"),
            ("[RUN_CMD:whoami]",             "whoami"),
        ]
        for i, (tag, label) in enumerate(presets):
            btn = tk.Button(
                pf, text=label,
                command=lambda t=tag: (
                    cmd_entry.delete(0, tk.END), cmd_entry.insert(0, t)),
                bg=C["glass"], fg=C["text_dim"],
                font=(FONT_MONO, 7),
                borderwidth=0, relief=tk.FLAT, padx=6, pady=3,
                cursor="hand2",
                activebackground=C["border"],
                activeforeground=C["amber"],
            )
            btn.grid(in_=pf, row=i // 5, column=i % 5, padx=2, pady=2, sticky="ew")
        for col in range(5):
            pf.columnconfigure(col, weight=1)

        # Pre-fill with friends cache status
        _append("⬡ debug console ready  —  no AI credits used", C["cyan_dim"])
        from core.discord_friends import get_friends as _gf
        friends = _gf()
        if friends:
            _append("⬡ {} discord friends in cache:".format(len(friends)), C["green"])
            for f in friends[:12]:
                name = f.get("display_name") or f.get("username") or "?"
                _append("  •  {}  (id: {})".format(name, f.get("user_id")), C["text_dim"])
            if len(friends) > 12:
                _append("  … and {} more".format(len(friends) - 12), C["text_dim"])
        else:
            _append("⚠ friends cache empty — see troubleshooting.md", C["red"])

        def _open_ts():
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "troubleshooting.md",
            )
            if os.path.isfile(path):
                os.startfile(path)
            else:
                messagebox.showerror(
                    "Not found",
                    "troubleshooting.md not found:\n{}".format(path),
                    parent=win,
                )

        tk.Button(win, text="📖  troubleshooting.md", command=_open_ts,
                  bg=C["bg"], fg=C["text_dim"],
                  font=(FONT_MONO, 7),
                  borderwidth=0, relief=tk.FLAT, padx=8, pady=4,
                  cursor="hand2").pack(anchor="w", padx=16, pady=(0, 8))

    # ── Mic / voice ───────────────────────────────────────────────────────────

    def _on_mic_click(self):
        if self._mic_active or self._streaming:
            return
        if not mic_available():
            messagebox.showwarning(
                "Microphone Not Available",
                "PyAudio is not installed or no microphone found.\n\n"
                "  pip install SpeechRecognition pyaudio\n\n"
                "See troubleshooting.md for details.",
                parent=self.root,
            )
            return
        self._mic_active = True
        self.mic_btn.configure(fg=C["red"], text="⏹")
        self._set_status("scanning", "LISTENING…")
        self.status_var.set("🎤 listening…")

        def _listen():
            text = listen_once(timeout=6.0, phrase_limit=15.0, log_fn=self._log_system)
            self._mic_active = False
            self.root.after(0, lambda: self.mic_btn.configure(fg=C["text_dim"], text="🎤"))
            if text:
                self.root.after(0, lambda: self._voice_send(text))
            else:
                self._set_status("ready", "ONLINE")
                self.root.after(0, lambda: self.status_var.set("ready"))

        threading.Thread(target=_listen, daemon=True).start()

    def _voice_send(self, text: str):
        self.input_field.delete("1.0", tk.END)
        self.input_field.insert("1.0", text)
        self._send_message()

    def _start_wake_word(self):
        if self._wake_running:
            return
        def _on_wake(transcript: str):
            self.root.after(0, lambda: self._voice_send(transcript))
        started = start_wake_listener(_on_wake, log_fn=self._log_system)
        if started:
            self._wake_running = True
            self._log_system('⬡ wake-word active: "{}"'.format(config.WAKE_WORD))

    # ── Entry point ───────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()
