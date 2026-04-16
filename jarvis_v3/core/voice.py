"""
core/voice.py

Microphone input + optional always-on wake-word listening for JARVIS.

Two modes (controlled by config.WAKE_WORD_ENABLED):

  False (default) — Button-to-talk mode.
      Call listen_once() when the user clicks the mic button.
      No background thread, no extra CPU.

  True  — Always-on wake-word mode.
      Call start_wake_listener(callback) to run a background thread.
      When the wake word is detected, callback(transcript) is called
      with whatever the user said *after* the wake word.
      Call stop_wake_listener() to shut it down cleanly.

Both modes use the SpeechRecognition library with Google's free
speech API — no API key needed for basic use.

Requirements:
    pip install SpeechRecognition pyaudio
"""

import threading
import queue
import time
import logging
from typing import Callable, Optional

import config

logger = logging.getLogger(__name__)

# ─── Lazy imports so the app still boots if PyAudio isn't installed ───────────

def _import_speech():
    try:
        import speech_recognition as sr
        return sr
    except ImportError:
        return None


# ─── Public API ───────────────────────────────────────────────────────────────

def is_available() -> bool:
    """Return True if speech_recognition + pyaudio are installed."""
    sr = _import_speech()
    if sr is None:
        return False
    try:
        sr.Microphone()
        return True
    except Exception:
        return False


def listen_once(
    timeout: float = 5.0,
    phrase_limit: float = 12.0,
    log_fn: Callable[[str], None] = print,
) -> Optional[str]:
    """
    Listen for a single utterance and return the transcript.
    Returns None on failure or silence.

    timeout     — seconds to wait for speech to start
    phrase_limit — max seconds of speech to capture
    """
    sr = _import_speech()
    if sr is None:
        log_fn("❌ Voice: SpeechRecognition not installed. Run: pip install SpeechRecognition pyaudio")
        return None

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True

    try:
        with sr.Microphone() as source:
            log_fn("🎤 Listening… (speak now)")
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            try:
                audio = recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_limit,
                )
            except sr.WaitTimeoutError:
                log_fn("🎤 No speech detected — mic timed out.")
                return None

        log_fn("🔄 Recognising speech…")
        text = recognizer.recognize_google(audio, language=config.VOICE_LANGUAGE)
        log_fn(f"🎤 Heard: {text}")
        return text

    except sr.UnknownValueError:
        log_fn("🎤 Could not understand audio.")
        return None
    except sr.RequestError as e:
        log_fn(f"❌ Voice recognition request failed: {e}")
        return None
    except OSError as e:
        log_fn(f"❌ Microphone error: {e} — check that a mic is connected and not in use.")
        return None
    except Exception as e:
        log_fn(f"❌ Voice error: {e}")
        return None


# ─── Always-on wake-word listener ────────────────────────────────────────────

_wake_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


def start_wake_listener(
    on_command: Callable[[str], None],
    log_fn: Callable[[str], None] = print,
) -> bool:
    """
    Start a background thread that listens for config.WAKE_WORD.
    When the wake word is heard, captures the follow-up phrase
    and calls on_command(transcript).

    Returns True if started successfully, False if unavailable.
    """
    global _wake_thread, _stop_event

    if not is_available():
        log_fn("❌ Wake word: PyAudio/SpeechRecognition not available.")
        return False

    _stop_event.clear()
    _wake_thread = threading.Thread(
        target=_wake_loop,
        args=(on_command, log_fn),
        daemon=True,
        name="jarvis-wake-listener",
    )
    _wake_thread.start()
    log_fn(f"👂 Wake-word listener active — say \"{config.WAKE_WORD}\" to activate.")
    return True


def stop_wake_listener():
    """Signal the background wake-word thread to stop."""
    global _stop_event
    _stop_event.set()


def _wake_loop(on_command: Callable[[str], None], log_fn: Callable[[str], None]):
    sr = _import_speech()
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.energy_threshold = 300
    recognizer.pause_threshold = 0.8

    wake = config.WAKE_WORD.lower().strip()

    log_fn(f"👂 Wake-word loop started ('{wake}')")

    while not _stop_event.is_set():
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                try:
                    audio = recognizer.listen(
                        source,
                        timeout=1.0,
                        phrase_time_limit=8.0,
                    )
                except sr.WaitTimeoutError:
                    continue

            try:
                text = recognizer.recognize_google(
                    audio, language=config.VOICE_LANGUAGE
                ).lower()
            except (sr.UnknownValueError, sr.RequestError):
                continue

            if wake in text:
                # Strip the wake word itself and leading punctuation/spaces
                command = text.split(wake, 1)[-1].strip(" ,.")
                log_fn(f"🎤 Wake word detected! Command: '{command}'")
                if command:
                    on_command(command)
                else:
                    # Wake word alone — prompt for a follow-up
                    log_fn("🎤 Listening for command after wake word…")
                    followup = listen_once(timeout=4.0, phrase_limit=10.0, log_fn=log_fn)
                    if followup:
                        on_command(followup)

        except OSError as e:
            log_fn(f"❌ Wake-word mic error: {e}")
            time.sleep(3)
        except Exception as e:
            log_fn(f"❌ Wake-word loop error: {e}")
            time.sleep(1)

    log_fn("👂 Wake-word listener stopped.")
