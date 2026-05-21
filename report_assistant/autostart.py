"""跨平台开机自启管理。

- Windows: 写入 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run 注册表
- macOS: 写入 ~/Library/LaunchAgents/<id>.plist (LaunchAgent)
- Linux: 写入 ~/.config/autostart/<id>.desktop (XDG autostart)

所有路径都是用户级（不需要管理员权限）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


APP_ID = "report-assistant"
APP_NAME = "小T日报助手"


def _launch_command() -> Optional[list[str]]:
    """构造启动命令。"""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    py = sys.executable
    return [py, "-m", "report_assistant.desktop.app"]


def _quote(arg: str) -> str:
    if " " in arg or "\\" in arg:
        return f'"{arg}"'
    return arg


def _command_str() -> str:
    cmd = _launch_command()
    if not cmd:
        return ""
    return " ".join(_quote(a) for a in cmd)


# ── Windows 实现 ──────────────────────────────────

def _win_set(enable: bool) -> None:
    import winreg
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0, winreg.KEY_SET_VALUE,
    )
    try:
        if enable:
            winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, _command_str())
        else:
            try:
                winreg.DeleteValue(key, APP_ID)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)


def _win_get() -> bool:
    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
        )
    except FileNotFoundError:
        return False
    try:
        winreg.QueryValueEx(key, APP_ID)
        return True
    except FileNotFoundError:
        return False
    finally:
        winreg.CloseKey(key)


# ── macOS 实现 ────────────────────────────────────

def _mac_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{APP_ID}.plist"


def _mac_set(enable: bool) -> None:
    p = _mac_plist_path()
    if not enable:
        if p.exists():
            p.unlink()
        return
    cmd = _launch_command() or []
    program_args = "\n".join(f"        <string>{c}</string>" for c in cmd)
    plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Inc.//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{APP_ID}</string>
    <key>ProgramArguments</key>
    <array>
{program_args}
    </array>
    <key>RunAtLoad</key><true/>
</dict>
</plist>
'''
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(plist, encoding="utf-8")


def _mac_get() -> bool:
    return _mac_plist_path().exists()


# ── Linux 实现 ────────────────────────────────────

def _linux_desktop_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / f"{APP_ID}.desktop"


def _linux_set(enable: bool) -> None:
    p = _linux_desktop_path()
    if not enable:
        if p.exists():
            p.unlink()
        return
    cmd = _command_str()
    desktop = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f"Exec={cmd}\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(desktop, encoding="utf-8")


def _linux_get() -> bool:
    return _linux_desktop_path().exists()


# ── 公开 API ──────────────────────────────────────

def set_autostart(enable: bool) -> None:
    """启用/禁用开机自启。"""
    if sys.platform == "win32":
        _win_set(enable)
    elif sys.platform == "darwin":
        _mac_set(enable)
    else:
        _linux_set(enable)


def is_autostart_enabled() -> bool:
    """查询当前是否已启用。"""
    try:
        if sys.platform == "win32":
            return _win_get()
        if sys.platform == "darwin":
            return _mac_get()
        return _linux_get()
    except Exception:
        return False
