"""
Windows startup manager.

Registers / unregisters the application to launch automatically when the user
logs in, using the per-user HKCU "Run" key. No admin rights and no extra
dependencies are required (uses the standard-library ``winreg`` module).

The registry is the single source of truth: ``is_enabled()`` reads the live
value, so the UI reflects reality even if the entry is changed externally
(e.g. via regedit or another tool).

Pairs with the persistent "Enable automatic scheduling" toggle: when both are
on, a boot -> login -> app launch -> scheduler re-arms, fully unattended.
Note that a GUI app needs a logged-in desktop session, so a headless rig must
have Windows auto-login enabled.
"""

import sys
import platform
from pathlib import Path

# Registry value name and the standard per-user "Run" key.
APP_NAME = "RTSP_Timelapse"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_supported() -> bool:
    """Return True only on Windows (where the Run key exists)."""
    return platform.system() == "Windows"


def _launch_command() -> str:
    """Build the command string to register in the Run key.

    Frozen (PyInstaller exe): just the quoted executable path.
    From source: the Python interpreter plus the launcher script. Prefer
    ``pythonw.exe`` so no console window flashes at logon.
    """
    if getattr(sys, "frozen", False):
        # Running as the bundled .exe - launch it directly.
        return f'"{sys.executable}"'

    # Running from source - launch run_gui.py with (windowed) Python.
    python = sys.executable
    pythonw = Path(python).with_name("pythonw.exe")
    if pythonw.exists():
        python = str(pythonw)
    # run_gui.py lives at the repo root (parent of this src/ package).
    launcher = Path(__file__).resolve().parent.parent / "run_gui.py"
    if not launcher.exists():
        # Don't register a command that would silently fail at every boot.
        raise FileNotFoundError(f"Launcher not found: {launcher}")
    return f'"{python}" "{launcher}"'


def is_enabled() -> bool:
    """Return True if the app is registered to start with Windows."""
    if not is_supported():
        return False

    import winreg  # local import: only available on Windows

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        # Either the Run key or our value does not exist.
        return False
    except OSError:
        return False


def _stored_command():
    """Return the command currently registered under the Run key, or None."""
    if not is_supported():
        return None

    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return value
    except (FileNotFoundError, OSError):
        return None


def enable() -> tuple[bool, str]:
    """Register the app to launch at logon. Returns (success, message)."""
    if not is_supported():
        return False, "Start with Windows is only available on Windows."

    import winreg

    try:
        # _launch_command() may raise FileNotFoundError (an OSError subclass)
        # if the source launcher is missing — caught here so the caller can
        # revert the checkbox rather than register a broken entry.
        command = _launch_command()
        # Creates the key if missing, opens it for writing otherwise.
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        return True, "App will start automatically when Windows starts."
    except OSError as e:
        return False, f"Could not enable start with Windows: {e}"


def disable() -> tuple[bool, str]:
    """Remove the logon entry. Returns (success, message)."""
    if not is_supported():
        return False, "Start with Windows is only available on Windows."

    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, APP_NAME)
        return True, "App will no longer start automatically with Windows."
    except FileNotFoundError:
        # Already absent - treat as success (desired end state reached).
        return True, "App will no longer start automatically with Windows."
    except OSError as e:
        return False, f"Could not disable start with Windows: {e}"


def sync() -> bool:
    """Ensure the auto-start command points at the current executable.

    Self-heals the registry path after the app is moved/upgraded to a new folder,
    so "Start with Windows" survives upgrades without a manual re-toggle. Returns
    True if it updated a stale entry. Best-effort: never raises.
    """
    if not is_supported():
        return False
    # Only self-heal for the frozen exe — a source/dev run must NOT overwrite a
    # real exe-based entry with a dev launcher command.
    if not getattr(sys, "frozen", False):
        return False
    try:
        if not is_enabled():
            return False
        if _stored_command() == _launch_command():
            return False
        enable()  # rewrites APP_NAME with the current exe command
        return True
    except Exception:
        return False
