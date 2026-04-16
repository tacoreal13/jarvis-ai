"""
core/system_snapshot.py
On first launch, JARVIS takes a deep snapshot of the system:
  - Hardware (CPU, RAM, GPU, displays)
  - OS info
  - All running processes
  - Installed applications (registry + common dirs)
  - Steam games
  - Disk drives and top-level directory trees
  - Network interfaces
  - User environment (home folder structure, desktop, documents)
  - Startup items
  - Recent files

The snapshot is saved to snapshot.json in the jarvis directory.
On subsequent launches it is loaded from disk (and optionally refreshed).
"""

import os
import sys
import json
import time
import glob
import platform
import subprocess
import socket
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

SNAPSHOT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "snapshot.json")
SNAPSHOT_VERSION = 3


# ─── Top-level entry point ────────────────────────────────────────────────────

def load_or_create_snapshot(force_refresh: bool = False, log_fn=print) -> dict:
    """
    Return the system snapshot dict.
    Loads from disk if it exists and is recent; otherwise scans now.
    """
    if not force_refresh and os.path.exists(SNAPSHOT_PATH):
        try:
            with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
                snap = json.load(f)
            if snap.get("version") == SNAPSHOT_VERSION:
                log_fn(f"📂 Loaded system snapshot from {SNAPSHOT_PATH}")
                return snap
        except Exception as e:
            log_fn(f"⚠️ Could not load snapshot: {e} — rescanning...")

    log_fn("🔍 First run — scanning your system. This takes a few seconds...")
    snap = _full_scan(log_fn)
    _save_snapshot(snap)
    log_fn(f"✅ Snapshot complete. Saved to {SNAPSHOT_PATH}")
    return snap


def refresh_snapshot(log_fn=print) -> dict:
    """Force a fresh scan and overwrite snapshot.json."""
    return load_or_create_snapshot(force_refresh=True, log_fn=log_fn)


def get_snapshot_summary(snap: dict) -> str:
    """Return a human-readable summary string for the AI system prompt."""
    lines = [
        "=== SYSTEM SNAPSHOT (collected at first launch) ===",
        f"Snapshot taken: {snap.get('timestamp', 'unknown')}",
        "",
        "── HARDWARE ──",
    ]

    hw = snap.get("hardware", {})
    lines.append(f"  CPU: {hw.get('cpu', 'unknown')}")
    lines.append(f"  RAM: {hw.get('ram_gb', '?')} GB total, {hw.get('ram_free_gb', '?')} GB free at scan time")
    lines.append(f"  GPU: {hw.get('gpu', 'unknown')}")
    lines.append(f"  Displays: {hw.get('displays', 'unknown')}")

    os_info = snap.get("os", {})
    lines += [
        "",
        "── OPERATING SYSTEM ──",
        f"  {os_info.get('name', '')} {os_info.get('version', '')} ({os_info.get('arch', '')})",
        f"  Computer name: {os_info.get('hostname', '')}",
        f"  Username: {os_info.get('username', '')}",
        f"  Home: {os_info.get('home', '')}",
    ]

    disks = snap.get("disks", [])
    lines += ["", "── DISKS ──"]
    for d in disks:
        lines.append(f"  {d['drive']}  {d.get('label','')}  {d.get('total_gb','?')} GB total / {d.get('free_gb','?')} GB free  [{d.get('fs','')}]")

    apps = snap.get("installed_apps", [])
    lines += ["", f"── INSTALLED APPLICATIONS ({len(apps)}) ──"]
    for a in apps[:60]:
        lines.append(f"  • {a}")
    if len(apps) > 60:
        lines.append(f"  ... and {len(apps)-60} more (see snapshot.json)")

    steam = snap.get("steam_games", [])
    lines += ["", f"── STEAM GAMES ({len(steam)}) ──"]
    for g in steam:
        lines.append(f"  • {g['name']} (ID: {g['app_id']})")

    procs = snap.get("running_processes_at_scan", [])
    lines += ["", f"── PROCESSES AT SCAN TIME ({len(procs)}) ──"]
    for p in procs[:40]:
        lines.append(f"  {p['pid']:>6}  {p['name']}")
    if len(procs) > 40:
        lines.append(f"  ... {len(procs)-40} more")

    net = snap.get("network", {})
    lines += ["", "── NETWORK ──"]
    for iface, addrs in net.get("interfaces", {}).items():
        lines.append(f"  {iface}: {', '.join(addrs)}")

    env = snap.get("user_environment", {})
    lines += ["", "── USER ENVIRONMENT ──"]
    for folder, contents in env.items():
        lines.append(f"  {folder}: {', '.join(contents[:8])}{'...' if len(contents)>8 else ''}")

    startup = snap.get("startup_items", [])
    if startup:
        lines += ["", f"── STARTUP ITEMS ({len(startup)}) ──"]
        for s in startup[:20]:
            lines.append(f"  • {s}")

    lines.append("")
    lines.append("=== END SNAPSHOT ===")
    return "\n".join(lines)


# ─── Internal scan functions ───────────────────────────────────────────────────

def _full_scan(log_fn) -> dict:
    snap = {
        "version": SNAPSHOT_VERSION,
        "timestamp": datetime.now().isoformat(),
        "snapshot_path": SNAPSHOT_PATH,
    }

    log_fn("  🖥  Scanning hardware...")
    snap["hardware"] = _scan_hardware()

    log_fn("  💻  Scanning OS info...")
    snap["os"] = _scan_os()

    log_fn("  💾  Scanning disks...")
    snap["disks"] = _scan_disks()

    log_fn("  📂  Scanning user environment...")
    snap["user_environment"] = _scan_user_environment()

    log_fn("  🧩  Scanning installed applications...")
    snap["installed_apps"] = _scan_installed_apps(log_fn)

    log_fn("  🎮  Scanning Steam games...")
    snap["steam_games"] = _scan_steam_games()

    log_fn("  ⚙️   Scanning running processes...")
    snap["running_processes_at_scan"] = _scan_processes()

    log_fn("  🌐  Scanning network...")
    snap["network"] = _scan_network()

    log_fn("  🚀  Scanning startup items...")
    snap["startup_items"] = _scan_startup_items()

    log_fn("  📄  Scanning recent files...")
    snap["recent_files"] = _scan_recent_files()

    return snap


def _run_ps(command: str, timeout: int = 10) -> str:
    """Run a PowerShell command and return stdout."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _scan_hardware() -> dict:
    hw = {}

    # CPU
    cpu = _run_ps("(Get-WmiObject Win32_Processor).Name")
    hw["cpu"] = cpu or platform.processor() or "unknown"

    # RAM
    try:
        ram_ps = _run_ps("(Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory")
        hw["ram_gb"] = round(int(ram_ps) / (1024**3), 1) if ram_ps.isdigit() else "?"
        free_ps = _run_ps("(Get-WmiObject Win32_OperatingSystem).FreePhysicalMemory")
        hw["ram_free_gb"] = round(int(free_ps) * 1024 / (1024**3), 1) if free_ps.isdigit() else "?"
    except Exception:
        hw["ram_gb"] = "?"
        hw["ram_free_gb"] = "?"

    # GPU
    gpu = _run_ps("(Get-WmiObject Win32_VideoController | Select-Object -First 1).Name")
    hw["gpu"] = gpu or "unknown"

    # Displays
    displays = _run_ps(
        "(Get-WmiObject Win32_DesktopMonitor | ForEach-Object { \"$($_.Name) $($_.ScreenWidth)x$($_.ScreenHeight)\" }) -join ', '"
    )
    hw["displays"] = displays or "unknown"

    # Motherboard
    mb = _run_ps("(Get-WmiObject Win32_BaseBoard).Product")
    hw["motherboard"] = mb or "unknown"

    return hw


def _scan_os() -> dict:
    info = {
        "name": platform.system(),
        "version": platform.version(),
        "release": platform.release(),
        "arch": platform.machine(),
        "hostname": socket.gethostname(),
        "username": os.environ.get("USERNAME", os.environ.get("USER", "unknown")),
        "home": str(Path.home()),
    }

    # Windows edition
    edition = _run_ps("(Get-WmiObject Win32_OperatingSystem).Caption")
    if edition:
        info["edition"] = edition

    return info


def _scan_disks() -> list:
    disks = []
    try:
        ps_out = _run_ps(
            "Get-WmiObject Win32_LogicalDisk | "
            "Select-Object DeviceID, VolumeName, Size, FreeSpace, FileSystem | "
            "ForEach-Object { \"$($_.DeviceID)|$($_.VolumeName)|$($_.Size)|$($_.FreeSpace)|$($_.FileSystem)\" }"
        )
        for line in ps_out.splitlines():
            parts = line.strip().split("|")
            if len(parts) >= 5:
                try:
                    size = int(parts[2]) if parts[2] else 0
                    free = int(parts[3]) if parts[3] else 0
                    disks.append({
                        "drive": parts[0],
                        "label": parts[1],
                        "total_gb": round(size / (1024**3), 1),
                        "free_gb": round(free / (1024**3), 1),
                        "fs": parts[4],
                    })
                except Exception:
                    pass
    except Exception:
        pass

    # Scan top-level directories on each drive
    for disk in disks:
        drive = disk["drive"]
        try:
            entries = os.listdir(drive + "\\")
            disk["top_level"] = entries[:30]
        except Exception:
            disk["top_level"] = []

    return disks


def _scan_user_environment() -> dict:
    home = Path.home()
    env = {}

    important_dirs = {
        "Desktop": home / "Desktop",
        "Documents": home / "Documents",
        "Downloads": home / "Downloads",
        "Pictures": home / "Pictures",
        "Videos": home / "Videos",
        "Music": home / "Music",
        "AppData_Local": home / "AppData" / "Local",
        "AppData_Roaming": home / "AppData" / "Roaming",
    }

    for name, path in important_dirs.items():
        try:
            if path.exists():
                entries = [e.name for e in sorted(path.iterdir())[:20]]
                env[name] = entries
        except Exception:
            pass

    return env


def _scan_installed_apps(log_fn) -> list:
    """Read installed apps from Windows registry and common paths."""
    apps = set()

    # Registry uninstall keys
    reg_keys = [
        r"HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        r"HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
        r"HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
    ]
    for key in reg_keys:
        ps_out = _run_ps(
            f"Get-ItemProperty '{key}' -ErrorAction SilentlyContinue | "
            "Where-Object {{ $_.DisplayName }} | "
            "Select-Object -ExpandProperty DisplayName",
            timeout=20
        )
        for line in ps_out.splitlines():
            name = line.strip()
            if name and len(name) > 1:
                apps.add(name)

    # Common install dirs - just grab folder names as app hints
    common_dirs = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.path.join(Path.home(), "AppData", "Local"),
        os.path.join(Path.home(), "AppData", "Local", "Programs"),
    ]
    for d in common_dirs:
        try:
            for entry in os.scandir(d):
                if entry.is_dir():
                    apps.add(entry.name)
        except Exception:
            pass

    return sorted(apps)


def _scan_steam_games() -> list:
    games = []
    steam_dirs = [
        r"C:\Program Files (x86)\Steam\steamapps",
        r"C:\Program Files\Steam\steamapps",
    ]

    # Parse libraryfolders.vdf for extra library paths
    vdf_paths = [
        r"C:\Program Files (x86)\Steam\steamapps\libraryfolders.vdf",
        r"C:\Program Files\Steam\steamapps\libraryfolders.vdf",
    ]
    import re
    for vdf in vdf_paths:
        if os.path.exists(vdf):
            try:
                with open(vdf, encoding="utf-8") as f:
                    content = f.read()
                paths = re.findall(r'"path"\s+"([^"]+)"', content)
                for p in paths:
                    steam_dirs.append(os.path.join(p.replace("\\\\", "\\"), "steamapps"))
            except Exception:
                pass

    for apps_dir in steam_dirs:
        if not os.path.isdir(apps_dir):
            continue
        for manifest in glob.glob(os.path.join(apps_dir, "appmanifest_*.acf")):
            try:
                with open(manifest, encoding="utf-8") as f:
                    content = f.read()
                app_id = re.search(r'"appid"\s+"(\d+)"', content)
                name = re.search(r'"name"\s+"([^"]+)"', content)
                size = re.search(r'"SizeOnDisk"\s+"(\d+)"', content)
                if app_id and name:
                    games.append({
                        "app_id": app_id.group(1),
                        "name": name.group(1),
                        "size_gb": round(int(size.group(1)) / (1024**3), 2) if size else 0,
                        "path": apps_dir,
                    })
            except Exception:
                pass

    return sorted(games, key=lambda g: g["name"].lower())


def _scan_processes() -> list:
    procs = []
    ps_out = _run_ps(
        "Get-Process | Select-Object Id, Name, CPU, WorkingSet | "
        "ForEach-Object { \"$($_.Id)|$($_.Name)|$([math]::Round($_.WorkingSet/1MB,1))\" }",
        timeout=10
    )
    for line in ps_out.splitlines():
        parts = line.strip().split("|")
        if len(parts) >= 2:
            try:
                procs.append({
                    "pid": int(parts[0]),
                    "name": parts[1],
                    "mem_mb": float(parts[2]) if len(parts) > 2 and parts[2] else 0,
                })
            except Exception:
                pass
    return sorted(procs, key=lambda p: p["name"].lower())


def _scan_network() -> dict:
    net = {"interfaces": {}}
    try:
        import socket
        hostname = socket.gethostname()
        net["hostname"] = hostname
        net["local_ip"] = socket.gethostbyname(hostname)
    except Exception:
        pass

    # PowerShell for richer interface info
    ps_out = _run_ps(
        "Get-NetIPAddress | Where-Object { $_.AddressFamily -eq 'IPv4' } | "
        "ForEach-Object { \"$($_.InterfaceAlias)|$($_.IPAddress)\" }",
        timeout=8
    )
    for line in ps_out.splitlines():
        parts = line.strip().split("|")
        if len(parts) == 2:
            iface, addr = parts
            net["interfaces"].setdefault(iface.strip(), []).append(addr.strip())

    return net


def _scan_startup_items() -> list:
    items = []
    ps_out = _run_ps(
        "Get-CimInstance Win32_StartupCommand | "
        "ForEach-Object { \"$($_.Name): $($_.Command)\" }",
        timeout=10
    )
    for line in ps_out.splitlines():
        if line.strip():
            items.append(line.strip())
    return items


def _scan_recent_files() -> list:
    """Grab recently modified files from common user folders."""
    recent = []
    search_dirs = [
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home() / "Downloads",
    ]
    for d in search_dirs:
        try:
            files = sorted(d.rglob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
            for f in files[:10]:
                if f.is_file():
                    recent.append({
                        "path": str(f),
                        "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    })
        except Exception:
            pass
    return recent[:30]


def _save_snapshot(snap: dict):
    try:
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Could not save snapshot: {e}")
