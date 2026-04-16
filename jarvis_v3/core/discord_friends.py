"""
core/discord_friends.py

Reads Discord's local LevelDB cache to extract the friends list.
Falls back to a manually maintained friends_cache.json if LevelDB fails.

HOW IT WORKS — three strategies tried in order:
  1. leveldb Python package (cleanest, most reliable) — pip install leveldb
  2. Raw .ldb / .log file scan (regex over binary files, no extra deps)
  3. Manually added friends (user calls add_friend_manually / DISCORD_REMEMBER)

WHY THE CACHE IS SOMETIMES EMPTY:
  - Discord locks its LevelDB files while running. Strategy 2 (raw scan)
    can still read locked .ldb files on Windows, but the data may be
    incomplete if Discord hasn't flushed a compaction recently.
  - Best results: close Discord, run Rescan, then reopen Discord.
  - Or: manually register friends with [DISCORD_REMEMBER:name|user_id].

See troubleshooting.md → "Discord: Friends List Empty" for full details.
"""

import os
import re
import json
import glob
import struct
from pathlib import Path
from difflib import SequenceMatcher
from typing import Optional

# ─── Paths ────────────────────────────────────────────────────────────────────

FRIENDS_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "discord_friends_cache.json",
)

DISCORD_LEVELDB_PATHS = [
    os.path.join(os.environ.get("APPDATA", ""),      "discord", "Local Storage", "leveldb"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Discord", "Local Storage", "leveldb"),
    os.path.join(os.environ.get("APPDATA", ""),      "discordptb", "Local Storage", "leveldb"),
    os.path.join(os.environ.get("APPDATA", ""),      "discordcanary", "Local Storage", "leveldb"),
]

# ─── Public API ───────────────────────────────────────────────────────────────

def get_friends(force_refresh: bool = False) -> list[dict]:
    """
    Return list of friend dicts: {user_id, username, display_name, discriminator}
    Tries LevelDB first, then falls back to saved cache.
    """
    if not force_refresh:
        cached = _load_cache()
        if cached:
            return cached

    friends = _read_from_leveldb()

    if friends:
        _save_cache(friends)
        return friends

    return _load_cache() or []


def find_friend(name_query: str, friends: list[dict] = None) -> Optional[dict]:
    """Fuzzy-find a friend by name or display name."""
    if friends is None:
        friends = get_friends()
    if not friends:
        return None

    query = name_query.strip().lower()

    for f in friends:
        if f.get("username", "").lower() == query:
            return f
        if f.get("display_name", "").lower() == query:
            return f

    for f in friends:
        if f.get("username", "").lower().startswith(query):
            return f
        if f.get("display_name", "").lower().startswith(query):
            return f

    best_score = 0.0
    best_friend = None
    for f in friends:
        for field in ("display_name", "username"):
            val = f.get(field, "").lower()
            if not val:
                continue
            score = SequenceMatcher(None, query, val).ratio()
            if score > best_score:
                best_score = score
                best_friend = f

    return best_friend if best_score >= 0.45 else None


def friends_summary(friends: list[dict]) -> str:
    if not friends:
        return "No Discord friends found in local cache."
    lines = [
        f"  {f['display_name'] or f['username']} (@{f['username']}) — ID: {f['user_id']}"
        for f in friends
    ]
    return f"Discord Friends ({len(friends)}):\n" + "\n".join(lines)


# ─── LevelDB reader — strategy 1: leveldb package ────────────────────────────

def _try_leveldb_package(base_path: str) -> list[dict]:
    """Use the optional 'leveldb' pip package for clean key-value reads."""
    try:
        import leveldb  # pip install leveldb
        db = leveldb.LevelDB(base_path)
        friends = []
        for key, value in db.RangeIter():
            try:
                text = value.decode("utf-8", errors="replace")
                extracted = _parse_user_json_blobs(text)
                friends.extend(extracted)
            except Exception:
                pass
        return friends
    except ImportError:
        return []
    except Exception:
        return []


# ─── LevelDB reader — strategy 2: raw .ldb scan ───────────────────────────────

def _read_from_leveldb() -> list[dict]:
    """
    Try all LevelDB paths. For each path, attempt:
      1. leveldb package (cleanest)
      2. Raw binary .ldb / .log scan (no extra deps needed)
    """
    all_friends: dict[str, dict] = {}

    for base_path in DISCORD_LEVELDB_PATHS:
        if not os.path.isdir(base_path):
            continue

        # Strategy 1: leveldb package
        pkg_friends = _try_leveldb_package(base_path)
        for f in pkg_friends:
            uid = f.get("user_id")
            if uid and uid not in all_friends:
                all_friends[uid] = f

        # Strategy 2: raw file scan
        ldb_files = sorted(glob.glob(os.path.join(base_path, "*.ldb")))
        log_files = sorted(glob.glob(os.path.join(base_path, "*.log")))

        # Prefer the most recently modified files (freshest data)
        all_files = sorted(
            ldb_files + log_files,
            key=lambda p: os.path.getmtime(p),
            reverse=True,
        )

        for filepath in all_files:
            try:
                extracted = _extract_users_from_ldb(filepath)
                for f in extracted:
                    uid = f.get("user_id")
                    if uid and uid not in all_friends:
                        all_friends[uid] = f
            except Exception:
                pass

    return list(all_friends.values())


def _extract_users_from_ldb(filepath: str) -> list[dict]:
    """Read raw .ldb / .log bytes and scan for Discord user JSON blobs."""
    try:
        with open(filepath, "rb") as fh:
            raw = fh.read()
    except (PermissionError, OSError):
        return []

    # Decode as latin-1 to preserve all bytes
    text = raw.decode("latin-1", errors="replace")
    return _parse_user_json_blobs(text)


def _parse_user_json_blobs(text: str) -> list[dict]:
    """
    Scan a string for Discord user JSON fragments.

    Discord stores user objects in multiple shapes:
      {"id":"123...","username":"foo",...}
      {"user_id":"123...","username":"foo",...}
      Embedded in relationship objects: {"type":1,"user":{...}}

    We use broad patterns then deduplicate.
    """
    found: dict[str, dict] = {}

    # ── Pattern A: id + username in either order ──────────────────────────
    pat_id_first = re.compile(
        r'"(?:id|user_id)"\s*:\s*"(\d{10,20})"'
        r'.{0,400}?"username"\s*:\s*"([^"]{1,64})"',
        re.DOTALL,
    )
    pat_user_first = re.compile(
        r'"username"\s*:\s*"([^"]{1,64})"'
        r'.{0,400}?"(?:id|user_id)"\s*:\s*"(\d{10,20})"',
        re.DOTALL,
    )

    for m in pat_id_first.finditer(text):
        uid, uname = m.group(1), m.group(2)
        if _valid_username(uname) and uid not in found:
            found[uid] = _make_user(uid, uname)

    for m in pat_user_first.finditer(text):
        uname, uid = m.group(1), m.group(2)
        if _valid_username(uname) and uid not in found:
            found[uid] = _make_user(uid, uname)

    # ── Pattern B: grab global_name / display_name for enrichment ─────────
    # Scan wider blocks to pick up display names where available
    block_re = re.compile(
        r'\{[^{}]{0,30}"(?:id|user_id)"\s*:\s*"(\d{10,20})"(?:[^{}]|\{[^{}]*\}){0,800}\}',
        re.DOTALL,
    )
    gname_re  = re.compile(r'"global_name"\s*:\s*"([^"]{1,64})"')
    dname_re  = re.compile(r'"display_name"\s*:\s*"([^"]{1,64})"')
    discr_re  = re.compile(r'"discriminator"\s*:\s*"(\d{4})"')

    for bm in block_re.finditer(text):
        uid   = bm.group(1)
        block = bm.group(0)
        if uid not in found:
            continue
        gn = gname_re.search(block) or dname_re.search(block)
        if gn:
            found[uid]["display_name"] = gn.group(1)
        dc = discr_re.search(block)
        if dc:
            found[uid]["discriminator"] = dc.group(1)

    # ── Pattern C: relationship objects {"type":1,"user":{...}} ──────────
    # type=1 means Friend, type=2 means Blocked — we only want 1
    rel_re = re.compile(
        r'"type"\s*:\s*1\s*,\s*"(?:id|user_id)"\s*:\s*"(\d{10,20})"'
        r'.{0,600}?"username"\s*:\s*"([^"]{1,64})"',
        re.DOTALL,
    )
    for m in rel_re.finditer(text):
        uid, uname = m.group(1), m.group(2)
        if _valid_username(uname):
            # Mark as confirmed friend
            if uid in found:
                found[uid]["confirmed_friend"] = True
            else:
                entry = _make_user(uid, uname)
                entry["confirmed_friend"] = True
                found[uid] = entry

    return list(found.values())


def _make_user(uid: str, username: str) -> dict:
    return {
        "user_id":       uid,
        "username":      username,
        "display_name":  username,
        "discriminator": "0",
    }


def _valid_username(name: str) -> bool:
    if not name or len(name) < 2:
        return False
    bad = set('{}\\/<>"\x00')
    return not any(c in bad for c in name)


# ─── Cache helpers ────────────────────────────────────────────────────────────

def _load_cache() -> list[dict]:
    try:
        with open(FRIENDS_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_cache(friends: list[dict]):
    try:
        with open(FRIENDS_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(friends, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ─── Manual friends management ────────────────────────────────────────────────

def add_friend_manually(user_id: str, username: str, display_name: str = "") -> bool:
    """Let the user manually register a friend."""
    friends = _load_cache()
    friends = [f for f in friends if f.get("user_id") != user_id]
    friends.append({
        "user_id":       user_id,
        "username":      username,
        "display_name":  display_name or username,
        "discriminator": "0",
        "manually_added": True,
    })
    _save_cache(friends)
    return True


def get_cache_path() -> str:
    """Return the path to the friends cache JSON file."""
    return FRIENDS_CACHE_PATH
