"""
core/ai_brain.py
Handles communication with the Claude AI API and parses command tags.
"""

import re
import anthropic
from typing import Generator
import config


class AIBrain:
    """Manages the AI model and conversation history."""

    # All supported command patterns
    COMMAND_PATTERNS = [
        r"\[RUN_EXE:([^\]]+)\]",
        r"\[OPEN_FILE:([^\]]+)\]",
        r"\[OPEN_URL:([^\]]+)\]",
        r"\[KILL_PROCESS:([^\]]+)\]",
        r"\[LIST_FILES:([^\]]+)\]",
        r"\[RUN_CMD:([^\]]+)\]",
        r"\[DISCORD_CALL:([^\]]+)\]",
        r"\[DISCORD_MESSAGE:([^\]]+)\]",
        r"\[OPEN_DISCORD\]",
        r"\[STEAM_LAUNCH:([^\]]+)\]",
        r"\[STEAM_LIST\]",
        r"\[OPEN_STEAM\]",
        r"\[SCREENSHOT\]",
        r"\[VOLUME:(\d+)\]",
        r"\[SHUTDOWN\]",
        r"\[RESTART\]",
        r"\[LOCK\]",
    ]

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.conversation_history: list[dict] = []

    def reset_conversation(self):
        self.conversation_history.clear()

    def chat(self, user_message: str) -> str:
        """Send a message and get a full response (non-streaming)."""
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        response = self.client.messages.create(
            model=config.AI_MODEL,
            max_tokens=config.AI_MAX_TOKENS,
            system=config.SYSTEM_PROMPT,
            messages=self.conversation_history,
        )

        assistant_message = response.content[0].text
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        return assistant_message

    def chat_stream(self, user_message: str) -> Generator[str, None, None]:
        """Send a message and stream the response token by token."""
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        full_response = ""
        with self.client.messages.stream(
            model=config.AI_MODEL,
            max_tokens=config.AI_MAX_TOKENS,
            system=config.SYSTEM_PROMPT,
            messages=self.conversation_history,
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                yield text

        self.conversation_history.append({
            "role": "assistant",
            "content": full_response
        })

    def extract_commands(self, text: str) -> list[dict]:
        """
        Parse all [COMMAND:args] tags from a response.
        Returns a list of {'tag': str, 'args': str|None} dicts.
        """
        commands = []
        # Match full tags like [CMD:arg] or [CMD]
        pattern = r"\[([A-Z_]+)(?::([^\]]*))?\]"
        for match in re.finditer(pattern, text):
            cmd_name = match.group(1)
            cmd_arg = match.group(2)  # None if no colon/arg
            commands.append({
                "tag": f"[{cmd_name}{':'+cmd_arg if cmd_arg else ''}]",
                "name": cmd_name,
                "args": cmd_arg,
            })
        return commands

    def strip_commands(self, text: str) -> str:
        """Remove all command tags from text for clean display."""
        return re.sub(r"\[[A-Z_]+(?::[^\]]*)?\]", "", text).strip()
