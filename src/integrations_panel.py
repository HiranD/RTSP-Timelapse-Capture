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
from tkinter import ttk

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

        # v3.4.0 (issue #12): a "Remote control" LabelFrame (enable HTTP API + port)
        # will be added here as row=2.

    def _create_discord_section(self, parent: ttk.LabelFrame):
        """Discord webhook upload settings."""
        parent.columnconfigure(1, weight=1)

        # Dependency hint: Discord upload only runs as part of the scheduler's
        # auto-video step, so it requires that option on the Scheduling tab.
        hint = ttk.Label(
            parent,
            text=("Uploads the auto-created video after each night's session. "
                  "Requires “Create video after each night” on the Scheduling tab."),
            font=("Segoe UI", 8),
            foreground="gray",
            wraplength=560,
            justify="left"
        )
        hint.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # Webhook URL
        ttk.Label(parent, text="Discord Webhook URL:").grid(row=1, column=0, sticky="w")
        self.discord_webhook_var = tk.StringVar(value="")
        self.discord_webhook_entry = ttk.Entry(parent, textvariable=self.discord_webhook_var, width=60)
        self.discord_webhook_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0))
        self.discord_webhook_entry.bind("<FocusOut>", self._on_discord_settings_change)
        self.discord_webhook_entry.bind("<Return>", self._on_discord_settings_change)
        ToolTip(self.discord_webhook_entry,
            "Discord webhook URL used to upload the generated timelapse video.\n"
            "Leave blank to disable automatic Discord uploads."
        )

        # Max upload size
        ttk.Label(parent, text="Max upload size (MB):").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.discord_max_size_var = tk.StringVar(value="8")
        self.discord_max_size_entry = ttk.Entry(parent, textvariable=self.discord_max_size_var, width=8)
        self.discord_max_size_entry.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(10, 0))
        self.discord_max_size_entry.bind("<FocusOut>", self._on_discord_settings_change)
        self.discord_max_size_entry.bind("<Return>", self._on_discord_settings_change)
        ToolTip(self.discord_max_size_entry,
            "Maximum file size in megabytes for Discord uploads.\n"
            "If the generated video exceeds this limit, upload will be skipped."
        )

        # Export resolution
        ttk.Label(parent, text="Export resolution:").grid(row=3, column=0, sticky="w", pady=(10, 0))
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
        ToolTip(self.discord_resolution_combo,
            "Resolution for Discord export.\n"
            "Lower resolutions reduce file size significantly.\n"
            "Original uses Video Export tab resolution."
        )

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
            "Automatically re-encode the video with progressively\n"
            "lower quality (CRF) if it exceeds the size limit.\n"
            "Stops when file is under limit or quality is unacceptable."
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
            "Automatically delete the exported video file after a\n"
            "successful upload to the configured Discord webhook.\n"
            "Use with caution: this removes the generated video permanently."
        )

    def _create_application_section(self, parent: ttk.LabelFrame):
        """Application / unattended-startup options."""
        parent.columnconfigure(0, weight=1)

        # Minimize to tray on startup
        self.minimize_to_tray_var = tk.BooleanVar(value=False)
        self.minimize_to_tray_checkbox = ttk.Checkbutton(
            parent,
            text="Minimize to tray on startup",
            variable=self.minimize_to_tray_var,
            command=self._on_minimize_to_tray_toggle
        )
        self.minimize_to_tray_checkbox.grid(row=0, column=0, sticky="w")
        ToolTip(self.minimize_to_tray_checkbox,
            "Start the application minimized to the system tray on launch.\n"
            "Use the tray icon to restore the window."
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
            "Combine with 'Enable automatic scheduling' for a fully\n"
            "unattended rig: after a reboot the app starts and the scheduler\n"
            "re-arms on its own.\n\n"
            "Note: a logged-in desktop session is required, so enable Windows\n"
            "auto-login on a headless machine."
        )

        # Only meaningful on Windows; disable elsewhere.
        if not startup_manager.is_supported():
            self.start_with_windows_checkbox.config(state="disabled")

    # ------------------------------------------------------------- config

    def _load_from_config(self):
        """Load settings from the shared config manager."""
        cfg = self.config_manager.astro_schedule

        self.discord_webhook_var.set(cfg.discord_webhook_url)
        self.discord_max_size_var.set(str(cfg.discord_max_video_size_mb))
        self.discord_resolution_var.set(cfg.discord_export_resolution)
        self.discord_auto_quality_var.set(cfg.discord_auto_quality_reduction)
        self.delete_video_after_discord_var.set(cfg.delete_video_after_discord_upload)

        self.minimize_to_tray_var.set(self.config_manager.ui.minimize_to_tray_on_startup)

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
            cfg.discord_max_video_size_mb = int(self.discord_max_size_var.get())
        except ValueError:
            cfg.discord_max_video_size_mb = 8
        cfg.discord_export_resolution = self.discord_resolution_var.get()
        cfg.discord_auto_quality_reduction = self.discord_auto_quality_var.get()
        cfg.delete_video_after_discord_upload = self.delete_video_after_discord_var.get()

        self.config_manager.ui.minimize_to_tray_on_startup = self.minimize_to_tray_var.get()

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
