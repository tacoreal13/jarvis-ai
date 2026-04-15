"""
ui/app.py
Main application window and chat interface.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.ai_brain import AIBrain
from core.executor import CommandExecutor
import config


# ─── Color Palette ───────────────────────────────────────────────────────────
COLORS = {
    "bg_dark":     "#0a0c10",
    "bg_panel":    "#0f1318",
    "bg_input":    "#141820",
    "bg_msg_user": "#1a2535",
    "bg_msg_ai":   "#0f1a1a",
    "border":      "#1e2840",
    "accent":      "#00d4ff",
    "accent2":     "#00ff9f",
    "accent3":     "#ff4f7b",
    "text":        "#c8d8e8",
    "text_dim":    "#506070",
    "text_bright": "#ffffff",
    "cmd_tag":     "#ff9f40",
    "success":     "#00ff9f",
    "error":       "#ff4f7b",
    "warning":     "#ffd700",
}


class JarvisApp:
    """Main JARVIS application window."""

    def __init__(self):
        self.brain = AIBrain()
        self.executor = CommandExecutor(log_fn=self._log_system)
        self._streaming = False

        self._build_window()
        self._build_ui()
        self._log_system(f"⚡ {config.ASSISTANT_NAME} initialized. Ready for orders.")
        self._print_welcome()

    # ──────────────────────────────────────────────────────────────────────────
    # Window setup
    # ──────────────────────────────────────────────────────────────────────────

    def _build_window(self):
        self.root = tk.Tk()
        self.root.title(f"⚡ {config.ASSISTANT_NAME}")
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.minsize(700, 500)
        self.root.configure(bg=COLORS["bg_dark"])
        self.root.option_add("*Font", f"{config.FONT_FAMILY} {config.FONT_SIZE}")

        # Try to set a dark taskbar icon style
        try:
            self.root.wm_attributes("-alpha", 0.97)
        except Exception:
            pass

    def _build_ui(self):
        # ── Title bar ─────────────────────────────────────────────────────────
        title_bar = tk.Frame(self.root, bg=COLORS["bg_dark"], height=50)
        title_bar.pack(fill=tk.X, padx=0, pady=0)
        title_bar.pack_propagate(False)

        tk.Label(
            title_bar,
            text=f"⚡ {config.ASSISTANT_NAME.upper()}",
            bg=COLORS["bg_dark"],
            fg=COLORS["accent"],
            font=(config.FONT_FAMILY, 16, "bold"),
        ).pack(side=tk.LEFT, padx=16, pady=10)

        tk.Label(
            title_bar,
            text="DESKTOP AI ASSISTANT",
            bg=COLORS["bg_dark"],
            fg=COLORS["text_dim"],
            font=(config.FONT_FAMILY, 9),
        ).pack(side=tk.LEFT, pady=10)

        # Buttons on the right
        btn_frame = tk.Frame(title_bar, bg=COLORS["bg_dark"])
        btn_frame.pack(side=tk.RIGHT, padx=10)
        self._make_btn(btn_frame, "⚙ Settings", self._show_settings, COLORS["text_dim"])
        self._make_btn(btn_frame, "🗑 Clear", self._clear_chat, COLORS["text_dim"])
        self._make_btn(btn_frame, "📂 Open File", self._browse_file, COLORS["accent"])

        # ── Separator ─────────────────────────────────────────────────────────
        tk.Frame(self.root, bg=COLORS["border"], height=1).pack(fill=tk.X)

        # ── Main area: chat + sidebar ─────────────────────────────────────────
        main = tk.Frame(self.root, bg=COLORS["bg_dark"])
        main.pack(fill=tk.BOTH, expand=True)

        # Chat area
        chat_frame = tk.Frame(main, bg=COLORS["bg_dark"])
        chat_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Chat display
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg=COLORS["bg_panel"],
            fg=COLORS["text"],
            font=(config.FONT_FAMILY, config.FONT_SIZE),
            borderwidth=0,
            relief=tk.FLAT,
            padx=16,
            pady=12,
            insertbackground=COLORS["accent"],
            selectbackground=COLORS["bg_msg_user"],
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        # Configure text tags
        self._setup_text_tags()

        # ── Sidebar ───────────────────────────────────────────────────────────
        sidebar = tk.Frame(main, bg=COLORS["bg_panel"], width=220)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=(1, 0))
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        # ── Status bar ────────────────────────────────────────────────────────
        tk.Frame(self.root, bg=COLORS["border"], height=1).pack(fill=tk.X)

        status_bar = tk.Frame(self.root, bg=COLORS["bg_dark"], height=24)
        status_bar.pack(fill=tk.X)
        status_bar.pack_propagate(False)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(
            status_bar, textvariable=self.status_var,
            bg=COLORS["bg_dark"], fg=COLORS["text_dim"],
            font=(config.FONT_FAMILY, 8), anchor="w"
        ).pack(side=tk.LEFT, padx=10)

        self.token_var = tk.StringVar(value="")
        tk.Label(
            status_bar, textvariable=self.token_var,
            bg=COLORS["bg_dark"], fg=COLORS["text_dim"],
            font=(config.FONT_FAMILY, 8), anchor="e"
        ).pack(side=tk.RIGHT, padx=10)

        # ── Input area ────────────────────────────────────────────────────────
        input_frame = tk.Frame(self.root, bg=COLORS["bg_input"], pady=10)
        input_frame.pack(fill=tk.X, padx=0, pady=0)

        tk.Frame(self.root, bg=COLORS["border"], height=1).pack(fill=tk.X)

        input_container = tk.Frame(input_frame, bg=COLORS["bg_input"])
        input_container.pack(fill=tk.X, padx=12, pady=4)

        self.input_field = tk.Text(
            input_container,
            height=3,
            bg=COLORS["bg_dark"],
            fg=COLORS["text_bright"],
            font=(config.FONT_FAMILY, config.FONT_SIZE),
            borderwidth=1,
            relief=tk.FLAT,
            padx=10,
            pady=8,
            insertbackground=COLORS["accent"],
            wrap=tk.WORD,
        )
        self.input_field.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.input_field.bind("<Return>", self._on_enter)
        self.input_field.bind("<Shift-Return>", lambda e: None)  # allow newline

        send_btn = tk.Button(
            input_container,
            text="SEND\n▶",
            command=self._send_message,
            bg=COLORS["accent"],
            fg=COLORS["bg_dark"],
            font=(config.FONT_FAMILY, 10, "bold"),
            borderwidth=0,
            relief=tk.FLAT,
            padx=16,
            cursor="hand2",
            activebackground=COLORS["accent2"],
            activeforeground=COLORS["bg_dark"],
        )
        send_btn.pack(side=tk.RIGHT, padx=(8, 0), fill=tk.Y)

    def _build_sidebar(self, parent):
        tk.Label(
            parent, text="QUICK ACTIONS",
            bg=COLORS["bg_panel"], fg=COLORS["text_dim"],
            font=(config.FONT_FAMILY, 8, "bold"),
        ).pack(pady=(14, 6), padx=12, anchor="w")

        quick_actions = [
            ("🎮 Open Steam",        "Open Steam for me"),
            ("💬 Open Discord",      "Open Discord"),
            ("📋 List Steam Games",  "List my installed Steam games"),
            ("📸 Screenshot",        "Take a screenshot"),
            ("📂 Desktop Files",     "List files on my Desktop"),
            ("🔊 Volume 50%",        "Set volume to 50%"),
            ("🔊 Volume 100%",       "Set volume to 100%"),
        ]

        for label, command in quick_actions:
            btn = tk.Button(
                parent, text=label,
                command=lambda c=command: self._quick_action(c),
                bg=COLORS["bg_input"],
                fg=COLORS["text"],
                font=(config.FONT_FAMILY, 9),
                borderwidth=0,
                relief=tk.FLAT,
                padx=12,
                pady=6,
                anchor="w",
                cursor="hand2",
                activebackground=COLORS["bg_msg_user"],
                activeforeground=COLORS["accent"],
            )
            btn.pack(fill=tk.X, padx=8, pady=2)

        # System log section
        tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=10)
        tk.Label(
            parent, text="SYSTEM LOG",
            bg=COLORS["bg_panel"], fg=COLORS["text_dim"],
            font=(config.FONT_FAMILY, 8, "bold"),
        ).pack(pady=(0, 4), padx=12, anchor="w")

        self.log_display = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg=COLORS["bg_dark"],
            fg=COLORS["text_dim"],
            font=(config.FONT_FAMILY, 8),
            borderwidth=0,
            relief=tk.FLAT,
            padx=8,
            pady=4,
            height=10,
        )
        self.log_display.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def _setup_text_tags(self):
        self.chat_display.tag_configure("user_label",
            foreground=COLORS["accent"], font=(config.FONT_FAMILY, 9, "bold"))
        self.chat_display.tag_configure("ai_label",
            foreground=COLORS["accent2"], font=(config.FONT_FAMILY, 9, "bold"))
        self.chat_display.tag_configure("user_text",
            foreground=COLORS["text"], background=COLORS["bg_msg_user"],
            lmargin1=8, lmargin2=8, rmargin=8, spacing1=4, spacing3=4)
        self.chat_display.tag_configure("ai_text",
            foreground=COLORS["text"], background=COLORS["bg_msg_ai"],
            lmargin1=8, lmargin2=8, rmargin=8, spacing1=4, spacing3=4)
        self.chat_display.tag_configure("cmd_tag",
            foreground=COLORS["cmd_tag"], font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"))
        self.chat_display.tag_configure("cmd_result",
            foreground=COLORS["success"], font=(config.FONT_FAMILY, 9))
        self.chat_display.tag_configure("error",
            foreground=COLORS["error"], font=(config.FONT_FAMILY, 9))
        self.chat_display.tag_configure("separator",
            foreground=COLORS["border"])

    # ──────────────────────────────────────────────────────────────────────────
    # Message handling
    # ──────────────────────────────────────────────────────────────────────────

    def _send_message(self):
        if self._streaming:
            return
        message = self.input_field.get("1.0", tk.END).strip()
        if not message:
            return
        self.input_field.delete("1.0", tk.END)
        self._display_user_message(message)
        threading.Thread(target=self._process_message, args=(message,), daemon=True).start()

    def _on_enter(self, event):
        # Send on Enter, newline on Shift+Enter
        if not event.state & 0x1:  # Shift not held
            self._send_message()
            return "break"

    def _quick_action(self, command: str):
        self.input_field.delete("1.0", tk.END)
        self.input_field.insert("1.0", command)
        self._send_message()

    def _process_message(self, message: str):
        self._streaming = True
        self.status_var.set("⏳ Thinking...")
        self.root.update_idletasks()

        try:
            # Start AI response display
            self._chat_append("\n", "")
            self._chat_append(f"{config.ASSISTANT_NAME}  ", "ai_label")

            full_response = ""
            for token in self.brain.chat_stream(message):
                full_response += token
                # Display token (hide command tags until full response is parsed)
                self._chat_append(token, "ai_text")
                self.chat_display.see(tk.END)

            self._chat_append("\n", "")

            # Parse and execute commands
            commands = self.brain.extract_commands(full_response)
            if commands:
                for cmd in commands:
                    self._chat_append(f"\n  ⚙ {cmd['tag']}\n", "cmd_tag")
                    result = self.executor.execute(cmd)
                    self._chat_append(f"  → {result}\n", "cmd_result")

            self._chat_append("─" * 60 + "\n", "separator")
            self.status_var.set("Ready")
            self.token_var.set(f"Msgs: {len(self.brain.conversation_history)}")

        except Exception as e:
            self._chat_append(f"\n❌ Error: {e}\n", "error")
            self.status_var.set("Error")
        finally:
            self._streaming = False
            self.chat_display.see(tk.END)

    def _display_user_message(self, message: str):
        self._chat_append(f"\nYou  ", "user_label")
        self._chat_append(f"{message}\n", "user_text")

    def _chat_append(self, text: str, tag: str):
        """Thread-safe text insertion."""
        self.chat_display.configure(state=tk.NORMAL)
        if tag:
            self.chat_display.insert(tk.END, text, tag)
        else:
            self.chat_display.insert(tk.END, text)
        self.chat_display.configure(state=tk.DISABLED)

    def _log_system(self, message: str):
        """Write to the sidebar system log."""
        def _write():
            self.log_display.configure(state=tk.NORMAL)
            self.log_display.insert(tk.END, message + "\n")
            self.log_display.configure(state=tk.DISABLED)
            self.log_display.see(tk.END)
        try:
            self.root.after(0, _write)
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────────
    # Other actions
    # ──────────────────────────────────────────────────────────────────────────

    def _clear_chat(self):
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.configure(state=tk.DISABLED)
        self.brain.reset_conversation()
        self._print_welcome()
        self._log_system("🗑 Conversation cleared.")

    def _browse_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.input_field.delete("1.0", tk.END)
            self.input_field.insert("1.0", f'Open the file "{path}"')
            self._send_message()

    def _show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.geometry("480x360")
        win.configure(bg=COLORS["bg_dark"])

        tk.Label(win, text="⚙ SETTINGS", bg=COLORS["bg_dark"],
                 fg=COLORS["accent"], font=(config.FONT_FAMILY, 13, "bold")).pack(pady=14)

        fields = [
            ("API Key", "ANTHROPIC_API_KEY"),
            ("Steam Path", "STEAM_PATH"),
            ("Discord Path", "DISCORD_PATH"),
        ]
        entries = {}
        for label, attr in fields:
            row = tk.Frame(win, bg=COLORS["bg_dark"])
            row.pack(fill=tk.X, padx=20, pady=4)
            tk.Label(row, text=label + ":", bg=COLORS["bg_dark"],
                     fg=COLORS["text"], width=14, anchor="w").pack(side=tk.LEFT)
            e = tk.Entry(row, bg=COLORS["bg_input"], fg=COLORS["text_bright"],
                         insertbackground=COLORS["accent"], borderwidth=0,
                         font=(config.FONT_FAMILY, 10))
            e.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
            e.insert(0, str(getattr(config, attr, "")))
            entries[attr] = e

        def save():
            for attr, entry in entries.items():
                setattr(config, attr, entry.get())
            # Update brain API key
            self.brain.client = __import__("anthropic").Anthropic(api_key=config.ANTHROPIC_API_KEY)
            messagebox.showinfo("Saved", "Settings saved for this session.\nEdit config.py to make permanent.", parent=win)
            win.destroy()

        tk.Button(win, text="Save", command=save,
                  bg=COLORS["accent"], fg=COLORS["bg_dark"],
                  font=(config.FONT_FAMILY, 10, "bold"), borderwidth=0, padx=20, pady=6,
                  cursor="hand2").pack(pady=16)

    def _print_welcome(self):
        welcome = (
            f"Welcome. I am {config.ASSISTANT_NAME}, your desktop AI assistant.\n"
            "I can run programs, open files, launch Steam games, control Discord,\n"
            "manage your system, and much more. What can I do for you?\n"
        )
        self._chat_append(f"{config.ASSISTANT_NAME}  ", "ai_label")
        self._chat_append(welcome + "\n", "ai_text")
        self._chat_append("─" * 60 + "\n", "separator")

    def _make_btn(self, parent, text, command, fg):
        return tk.Button(
            parent, text=text, command=command,
            bg=COLORS["bg_dark"], fg=fg,
            font=(config.FONT_FAMILY, 9),
            borderwidth=0, relief=tk.FLAT,
            padx=8, pady=4, cursor="hand2",
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["accent"],
        ).pack(side=tk.LEFT, padx=2)

    # ──────────────────────────────────────────────────────────────────────────
    # Run
    # ──────────────────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()
