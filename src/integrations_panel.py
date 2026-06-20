"""
Integrations Panel - Optional, set-once integrations and unattended-operation options.

Collects controls that are not part of the per-capture/video/schedule workflow:
- Discord webhook upload of the auto-created nightly video.
- Application options: minimize to tray on startup, start automatically with Windows.

Future (v3.4.0, issue #12): a "Remote control" section exposing a localhost HTTP API
to start/stop capture from external scripts (e.g. NINA) will live on this tab.

Like the other panels, this one self-saves: each control's handler writes to the shared
ConfigManager and persists via save_to_file(). "Start with Windows" is registry-driven
(startup_manager), not stored in config.
"""

import tkinter as tk
from tkinter import ttk, messagebox

try:
    from src.config_manager import ConfigManager
    from src.tooltip import ToolTip
    from src import startup_manager
except ImportError:
    from config_manager import ConfigManager
    from tooltip import ToolTip
    import startup_manager


class IntegrationsPanel(ttk.Frame):
    """Integrations tab: Discord upload + application/startup options."""

    def __init__(self, parent, config_manager: ConfigManager, **kwargs):
        """
        Initialize the integrations panel.

        Args:
            parent: Parent widget (notebook)
            config_manager: Application configuration manager (shared)
        """
        super().__init__(parent, **kwargs)

        self.config_manager = config_manager

        # Log callback to the main GUI (set by the app via set_log_callback).
        self.log_callback = None

        # Remote-control toggle callback (set by the app). Called with the
        # desired enabled state; returns (ok, error) so we can resync on failure.
        self._remote_toggle_cb = None

        self._create_widgets()
        self._load_from_config()

    # ------------------------------------------------------------------ UI

    def _create_widgets(self):
        """Create all panel widgets."""
        self.columnconfigure(0, weight=1)

        # === Discord Upload Section ===
        discord_frame = ttk.LabelFrame(self, text="Discord Upload", padding=10)
        discord_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self._create_discord_section(discord_frame)

        # === Application Section ===
        app_frame = ttk.LabelFrame(self, text="Application", padding=10)
        app_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self._create_application_section(app_frame)

        # === Remote Control Section ===
        remote_frame = ttk.LabelFrame(self, text="Remote Control", padding=10)
        remote_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        self._create_remote_control_section(remote_frame)

    def _create_discord_section(self, parent: ttk.LabelFrame):
        """Discord webhook upload settings."""
        parent.columnconfigure(1, weight=1)

        # Dependency hint: Discord upload only runs as part of the scheduler's
        # auto-video step, so it requires that option on the Scheduling tab.
        hint = ttk.Label(
            parent,
            text="Requires “Create video after each night” on the Scheduling tab.",
            font=("Segoe UI", 8),
            foreground="gray"
        )
        hint.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # Webhook URL
        webhook_tip = (
            "Discord webhook URL used to upload the generated timelapse video. "
            "Leave blank to disable automatic Discord uploads."
        )
        webhook_label = ttk.Label(parent, text="Discord Webhook URL:")
        webhook_label.grid(row=1, column=0, sticky="w")
        self.discord_webhook_var = tk.StringVar(value="")
        self.discord_webhook_entry = ttk.Entry(parent, textvariable=self.discord_webhook_var, width=60)
        self.discord_webhook_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0))
        self.discord_webhook_entry.bind("<FocusOut>", self._on_discord_settings_change)
        self.discord_webhook_entry.bind("<Return>", self._on_discord_settings_change)
        ToolTip(webhook_label, webhook_tip)
        ToolTip(self.discord_webhook_entry, webhook_tip)

        # Max upload size
        max_size_tip = (
            "Largest file size (MB) Discord will accept. If the video is bigger, "
            "upload is skipped — unless 'Auto reduce quality' is on, which "
            "re-encodes it (at lower quality) to fit."
        )
        max_size_label = ttk.Label(parent, text="Max upload size (MB):")
        max_size_label.grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.discord_max_size_var = tk.StringVar(value="8")
        self.discord_max_size_entry = ttk.Entry(parent, textvariable=self.discord_max_size_var, width=8)
        self.discord_max_size_entry.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(10, 0))
        self.discord_max_size_entry.bind("<FocusOut>", self._on_discord_settings_change)
        self.discord_max_size_entry.bind("<Return>", self._on_discord_settings_change)
        ToolTip(max_size_label, max_size_tip)
        ToolTip(self.discord_max_size_entry, max_size_tip)

        # Export resolution
        resolution_tip = (
            "Frame size used only when 'Auto reduce quality' re-encodes an oversized "
            "video. Smaller resolutions shrink the file to meet the size limit with "
            "less visible quality loss than compression alone. 'original' keeps the "
            "source resolution (relies on compression only)."
        )
        resolution_label = ttk.Label(parent, text="Export resolution:")
        resolution_label.grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.discord_resolution_var = tk.StringVar(value="original")
        self.discord_resolution_combo = ttk.Combobox(
            parent,
            textvariable=self.discord_resolution_var,
            values=["original", "720p", "480p", "360p"],
            state="readonly",
            width=12
        )
        self.discord_resolution_combo.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=(10, 0))
        self.discord_resolution_combo.bind("<<ComboboxSelected>>", self._on_discord_settings_change)
        ToolTip(resolution_label, resolution_tip)
        ToolTip(self.discord_resolution_combo, resolution_tip)

        # Auto quality reduction
        self.discord_auto_quality_var = tk.BooleanVar(value=False)
        self.discord_auto_quality_check = ttk.Checkbutton(
            parent,
            text="Auto reduce quality if too large",
            variable=self.discord_auto_quality_var,
            command=self._on_discord_settings_change
        )
        self.discord_auto_quality_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ToolTip(self.discord_auto_quality_check,
            "When a video is over the size limit, re-encode it to fit: quality is "
            "stepped down through CRF 20 → 25 → 28 → 32 → 35 → 40 → 45 (each step "
            "smaller but lossier), at the selected Export resolution, stopping at "
            "the first encode that fits under Max upload size. If even the lowest "
            "quality can't fit, upload is skipped and the original video is kept "
            "locally."
        )

        # Delete video after successful upload
        self.delete_video_after_discord_var = tk.BooleanVar(value=False)
        self.delete_video_after_discord_check = ttk.Checkbutton(
            parent,
            text="Delete video after successful Discord upload",
            variable=self.delete_video_after_discord_var,
            command=self._on_discord_settings_change
        )
        self.delete_video_after_discord_check.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ToolTip(self.delete_video_after_discord_check,
            "Automatically delete the exported video file after a successful upload "
            "to the configured Discord webhook. Use with caution: this removes the "
            "generated video permanently."
        )

    def _create_application_section(self, parent: ttk.LabelFrame):
        """Application / unattended-startup options."""
        parent.columnconfigure(0, weight=1)

        # Minimize to tray
        self.minimize_to_tray_var = tk.BooleanVar(value=False)
        self.minimize_to_tray_checkbox = ttk.Checkbutton(
            parent,
            text="Minimize to tray",
            variable=self.minimize_to_tray_var,
            command=self._on_minimize_to_tray_toggle
        )
        self.minimize_to_tray_checkbox.grid(row=0, column=0, sticky="w")
        ToolTip(self.minimize_to_tray_checkbox,
            "Send the window to the system tray instead of the taskbar. When "
            "enabled, the app starts minimized in the tray on startup, and the "
            "minimize button also hides the window to the tray. Restore it from "
            "the tray icon."
        )

        # Start automatically when Windows starts
        self.start_with_windows_var = tk.BooleanVar(value=False)
        self.start_with_windows_checkbox = ttk.Checkbutton(
            parent,
            text="Start automatically when Windows starts",
            variable=self.start_with_windows_var,
            command=self._on_start_with_windows_toggle
        )
        self.start_with_windows_checkbox.grid(row=1, column=0, sticky="w", pady=(8, 0))
        ToolTip(self.start_with_windows_checkbox,
            "Launch this app automatically when you log in to Windows.\n\n"
            "Combine with 'Enable automatic scheduling' for a fully unattended rig: "
            "after a reboot the app starts and the scheduler re-arms on its own.\n\n"
            "Note: a logged-in desktop session is required, so enable Windows "
            "auto-login on a headless machine."
        )

        # Only meaningful on Windows; disable elsewhere.
        if not startup_manager.is_supported():
            self.start_with_windows_checkbox.config(state="disabled")

    def _create_remote_control_section(self, parent: ttk.LabelFrame):
        """Localhost HTTP API for external control (e.g. NINA). See issue #12."""
        parent.columnconfigure(1, weight=1)

        # What it is / the scheduler exclusivity.
        hint = ttk.Label(
            parent,
            text="Let external scripts (e.g. NINA) start/stop capture and create "
                 "videos over a local-only HTTP API. Mutually exclusive with "
                 "“Enable automatic scheduling”.",
            font=("Segoe UI", 8),
            foreground="gray",
            wraplength=560,
            justify="left",
        )
        hint.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # Enable checkbox
        self.remote_api_enabled_var = tk.BooleanVar(value=False)
        self.remote_api_enabled_check = ttk.Checkbutton(
            parent,
            text="Enable remote control API",
            variable=self.remote_api_enabled_var,
            command=self._on_remote_api_toggle
        )
        self.remote_api_enabled_check.grid(row=1, column=0, columnspan=2, sticky="w")
        ToolTip(self.remote_api_enabled_check,
            "Start a small HTTP server bound to 127.0.0.1 (this machine only).\n"
            "External tools can then POST to /capture/start, /capture/stop and\n"
            "/video/create, or GET /status. Not exposed to the network and there\n"
            "is no auth token — only programs running on this PC can reach it."
        )

        # Lock note (shown when disabled because the scheduler is on).
        self.remote_api_lock_label = ttk.Label(
            parent, text="", font=("Segoe UI", 8), foreground="#CC6600"
        )
        self.remote_api_lock_label.grid(row=2, column=0, columnspan=2, sticky="w")

        # Port
        port_tip = (
            "TCP port for the local API (1024–65535). Default 8787.\n"
            "Change it if another program already uses this port."
        )
        port_label = ttk.Label(parent, text="Port:")
        port_label.grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.remote_api_port_var = tk.StringVar(value="8787")
        self.remote_api_port_entry = ttk.Entry(parent, textvariable=self.remote_api_port_var, width=8)
        self.remote_api_port_entry.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=(10, 0))
        self.remote_api_port_entry.bind("<FocusOut>", self._on_remote_api_port_change)
        self.remote_api_port_entry.bind("<Return>", self._on_remote_api_port_change)
        ToolTip(port_label, port_tip)
        ToolTip(self.remote_api_port_entry, port_tip)

        # Base URL (read-only display)
        url_tip = ("Point your external script at this address, e.g.\n"
                   "curl -X POST http://127.0.0.1:8787/capture/start")
        url_label = ttk.Label(parent, text="Base URL:")
        url_label.grid(row=4, column=0, sticky="w", pady=(10, 0))
        self.remote_base_url_var = tk.StringVar(value="http://127.0.0.1:8787")
        self.remote_base_url_entry = ttk.Entry(
            parent, textvariable=self.remote_base_url_var, state="readonly", width=32
        )
        self.remote_base_url_entry.grid(row=4, column=1, sticky="w", padx=(10, 0), pady=(10, 0))
        ToolTip(url_label, url_tip)
        ToolTip(self.remote_base_url_entry, url_tip)

    # ------------------------------------------------------------- config

    def _load_from_config(self):
        """Load settings from the shared config manager."""
        cfg = self.config_manager.astro_schedule

        self.discord_webhook_var.set(cfg.discord_webhook_url)
        self.discord_max_size_var.set(str(cfg.discord_max_video_size_mb))
        self.discord_resolution_var.set(cfg.discord_export_resolution)
        self.discord_auto_quality_var.set(cfg.discord_auto_quality_reduction)
        self.delete_video_after_discord_var.set(cfg.delete_video_after_discord_upload)

        self.minimize_to_tray_var.set(self.config_manager.ui.minimize_to_tray)

        # Remote control API
        remote = self.config_manager.remote_api
        self.remote_api_enabled_var.set(remote.enabled)
        self.remote_api_port_var.set(str(remote.port))
        self.remote_base_url_var.set(f"http://127.0.0.1:{remote.port}")

        # "Start with Windows" reflects the live registry state, not config.
        self.start_with_windows_var.set(startup_manager.is_enabled())

    def _save_to_config(self):
        """Persist Discord + tray settings to the shared config and disk.

        Note: start-with-Windows is registry-driven (handled in its own toggle)
        and is intentionally not written here.
        """
        cfg = self.config_manager.astro_schedule

        cfg.discord_webhook_url = self.discord_webhook_var.get().strip()
        try:
            size_mb = int(self.discord_max_size_var.get())
        except ValueError:
            size_mb = 8
        cfg.discord_max_video_size_mb = max(1, min(1024, size_mb))
        cfg.discord_export_resolution = self.discord_resolution_var.get()
        cfg.discord_auto_quality_reduction = self.discord_auto_quality_var.get()
        cfg.delete_video_after_discord_upload = self.delete_video_after_discord_var.get()

        self.config_manager.ui.minimize_to_tray = self.minimize_to_tray_var.get()

        # Remote control API
        self.config_manager.remote_api.enabled = self.remote_api_enabled_var.get()
        try:
            port = int(self.remote_api_port_var.get())
        except ValueError:
            port = 8787
        self.config_manager.remote_api.port = max(1024, min(65535, port))

        self.config_manager.save_to_file()

    # ------------------------------------------------------------ handlers

    def _on_discord_settings_change(self, event=None):
        """Handle any Discord setting change."""
        self._save_to_config()

    def _on_minimize_to_tray_toggle(self):
        """Handle tray-on-startup checkbox toggle."""
        self._save_to_config()

    def _on_start_with_windows_toggle(self):
        """Register/unregister the app to launch at Windows logon."""
        want_enabled = self.start_with_windows_var.get()
        if want_enabled:
            success, message = startup_manager.enable()
        else:
            success, message = startup_manager.disable()

        if success:
            self._log("INFO", message)
        else:
            # Resync the checkbox to the registry's actual state and report why.
            self.start_with_windows_var.set(startup_manager.is_enabled())
            self._log("ERROR", message)

    def _on_remote_api_toggle(self):
        """Start/stop the remote control server when the checkbox toggles."""
        enabled = self.remote_api_enabled_var.get()
        self._save_to_config()
        if not self._remote_toggle_cb:
            return
        ok, err = self._remote_toggle_cb(enabled)
        if not ok:
            # Couldn't start (e.g. port already in use): resync + report.
            self.remote_api_enabled_var.set(False)
            self._save_to_config()
            self._log("ERROR", f"Remote API: {err}")
            messagebox.showerror("Remote Control", f"Could not start the remote API:\n{err}")

    def _on_remote_api_port_change(self, event=None):
        """Persist the port, refresh the base-URL display, and bounce if running."""
        self._save_to_config()
        port = self.config_manager.remote_api.port
        self.remote_api_port_var.set(str(port))  # reflect clamping
        self.remote_base_url_var.set(f"http://127.0.0.1:{port}")

        # If the API is currently running, restart it onto the new port.
        if self.remote_api_enabled_var.get() and self._remote_toggle_cb:
            self._remote_toggle_cb(False)
            ok, err = self._remote_toggle_cb(True)
            if not ok:
                self.remote_api_enabled_var.set(False)
                self._save_to_config()
                self._log("ERROR", f"Remote API: {err}")
                messagebox.showerror("Remote Control", f"Could not restart the remote API:\n{err}")

    # --------------------------------------------------------- remote control

    def set_remote_api_callback(self, on_toggle):
        """Wire the Remote Control section to the app (start/stop + mutual lock)."""
        self._remote_toggle_cb = on_toggle

    def set_remote_api_control_enabled(self, enabled: bool):
        """Enable/disable the API enable checkbox (mutual exclusion with scheduler)."""
        if enabled:
            self.remote_api_enabled_check.config(state="normal")
            self.remote_api_lock_label.config(text="")
        else:
            self.remote_api_enabled_check.config(state="disabled")
            self.remote_api_lock_label.config(
                text="Disabled while automatic scheduling is on (Scheduling tab)."
            )

    def sync_remote_api_enabled(self, enabled: bool):
        """Reflect an externally-changed enabled state (e.g. autostart failed)."""
        self.remote_api_enabled_var.set(enabled)
        self.config_manager.remote_api.enabled = enabled
        self.config_manager.save_to_file()

    # ------------------------------------------------------------ logging

    def set_log_callback(self, log):
        """Set the callback used to forward messages to the main GUI log."""
        self.log_callback = log

    def _log(self, level: str, message: str):
        """Forward a message to the main GUI log (or stdout as a fallback)."""
        if self.log_callback:
            self.log_callback(level, f"[Integrations] {message}")
        else:
            print(f"[{level}] [Integrations] {message}")
