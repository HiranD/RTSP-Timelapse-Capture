"""
Scheduling Panel - Astronomical scheduling tab for long-term capture planning
Allows users to schedule captures based on twilight times and calendar dates.

Features:
- Location settings (latitude/longitude)
- Twilight type selection (civil/nautical/astronomical)
- Start/end offsets
- 2-month calendar for date selection
- Auto video creation settings
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from typing import Optional, Set
from datetime import datetime
from pathlib import Path

try:
    from src.calendar_widget import TwoMonthCalendar
    from src.twilight_calculator import TwilightCalculator
    from src.config_manager import ConfigManager
    from src.preset_manager import PresetManager
    from src.astro_scheduler import AstroScheduler
    from src.tooltip import ToolTip
    from src.scheduling_tooltips import SCHEDULING_TOOLTIPS
except ImportError:
    from calendar_widget import TwoMonthCalendar
    from twilight_calculator import TwilightCalculator
    from config_manager import ConfigManager
    from preset_manager import PresetManager
    from astro_scheduler import AstroScheduler
    from tooltip import ToolTip
    from scheduling_tooltips import SCHEDULING_TOOLTIPS


class SchedulingPanel(ttk.Frame):
    """
    Scheduling tab panel for astronomical capture scheduling.
    """

    def __init__(self, parent, config_manager: ConfigManager, **kwargs):
        """
        Initialize the scheduling panel.

        Args:
            parent: Parent widget (notebook)
            config_manager: Application configuration manager
        """
        super().__init__(parent, **kwargs)

        self.config_manager = config_manager
        self.preset_manager = PresetManager()

        # Twilight calculator (will be created when location is set)
        self.twilight_calc: Optional[TwilightCalculator] = None

        # Scheduler (will be set up by main GUI)
        self.scheduler: Optional[AstroScheduler] = None

        # Callbacks for capture control (set by main GUI)
        self.start_capture_callback = None
        self.stop_capture_callback = None
        self.create_video_callback = None
        self.log_callback = None

        # Create UI
        self._create_widgets()
        self._load_from_config()
        self._update_tonight_display()

    def _create_widgets(self):
        """Create all panel widgets"""
        # Main container with padding
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)  # Calendar row expands
        self.rowconfigure(3, weight=1)  # Log row also expands

        # === Capture Time Settings Section (merged Location + Twilight) ===
        time_settings_frame = ttk.LabelFrame(self, text="Capture Time Settings", padding=10)
        time_settings_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self._create_time_settings_section(time_settings_frame)

        # === Calendar Section ===
        calendar_frame = ttk.LabelFrame(self, text="Schedule Calendar", padding=10)
        calendar_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self._create_calendar_section(calendar_frame)

        # === Auto Video Section ===
        video_frame = ttk.LabelFrame(self, text="Auto Video Creation", padding=10)
        video_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        self._create_video_section(video_frame)

        # === Scheduler Control / Log Section (merged) ===
        log_frame = ttk.LabelFrame(self, text="Scheduler Control / Log", padding=10)
        log_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(5, 10))
        self._create_log_section(log_frame)

    def _create_time_settings_section(self, parent: ttk.LabelFrame):
        """Create combined time settings with radio buttons for twilight vs manual mode"""
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        # === Row 0: Time Mode Radio Buttons ===
        mode_frame = ttk.Frame(parent)
        mode_frame.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(mode_frame, text="Time Mode:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 15))

        self.time_mode_var = tk.StringVar(value="twilight")
        self.twilight_radio = ttk.Radiobutton(
            mode_frame,
            text="Twilight-based",
            variable=self.time_mode_var,
            value="twilight",
            command=self._on_time_mode_change
        )
        self.twilight_radio.pack(side="left", padx=(0, 20))
        ToolTip(self.twilight_radio, SCHEDULING_TOOLTIPS["time_mode_twilight"])

        self.manual_radio = ttk.Radiobutton(
            mode_frame,
            text="Manual",
            variable=self.time_mode_var,
            value="manual",
            command=self._on_time_mode_change
        )
        self.manual_radio.pack(side="left")
        ToolTip(self.manual_radio, SCHEDULING_TOOLTIPS["time_mode_manual"])

        # === Row 1: Two-column layout ===
        columns_frame = ttk.Frame(parent)
        columns_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        columns_frame.columnconfigure(0, weight=3)  # Twilight column takes more space
        columns_frame.columnconfigure(1, weight=0)  # Manual column stays fixed width

        # --- Left Column: Twilight Settings ---
        self.twilight_frame = ttk.LabelFrame(columns_frame, text="Twilight Settings", padding=10)
        self.twilight_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # Row 0: Latitude and Longitude in a frame to keep them together
        location_frame = ttk.Frame(self.twilight_frame)
        location_frame.grid(row=0, column=0, columnspan=7, sticky="w")

        ttk.Label(location_frame, text="Latitude:").pack(side="left")
        self.latitude_var = tk.StringVar(value="0.0")
        self.latitude_entry = ttk.Entry(location_frame, textvariable=self.latitude_var, width=10)
        self.latitude_entry.pack(side="left", padx=(2, 15))
        self.latitude_entry.bind("<FocusOut>", self._on_location_change)
        self.latitude_entry.bind("<Return>", self._on_location_change)
        ToolTip(self.latitude_entry, SCHEDULING_TOOLTIPS["latitude"])

        ttk.Label(location_frame, text="Longitude:").pack(side="left")
        self.longitude_var = tk.StringVar(value="0.0")
        self.longitude_entry = ttk.Entry(location_frame, textvariable=self.longitude_var, width=10)
        self.longitude_entry.pack(side="left", padx=(2, 10))
        self.longitude_entry.bind("<FocusOut>", self._on_location_change)
        self.longitude_entry.bind("<Return>", self._on_location_change)
        ToolTip(self.longitude_entry, SCHEDULING_TOOLTIPS["longitude"])

        # Hemisphere indicator
        self.hemisphere_label = ttk.Label(location_frame, text="", font=("Segoe UI", 8), foreground="gray")
        self.hemisphere_label.pack(side="left")

        # Row 1: Twilight type and offsets in a frame
        twilight_row_frame = ttk.Frame(self.twilight_frame)
        twilight_row_frame.grid(row=1, column=0, columnspan=7, sticky="w", pady=(10, 0))

        ttk.Label(twilight_row_frame, text="Twilight:").pack(side="left")
        self.twilight_type_var = tk.StringVar(value="astronomical")
        self.twilight_combo = ttk.Combobox(
            twilight_row_frame,
            textvariable=self.twilight_type_var,
            values=["civil", "nautical", "astronomical"],
            state="readonly",
            width=12
        )
        self.twilight_combo.pack(side="left", padx=(2, 15))
        self.twilight_combo.bind("<<ComboboxSelected>>", self._on_twilight_change)
        ToolTip(self.twilight_combo, SCHEDULING_TOOLTIPS["twilight_type"])

        ttk.Label(twilight_row_frame, text="Start Offset:").pack(side="left")
        self.start_offset_var = tk.StringVar(value="0")
        self.start_offset_entry = ttk.Entry(twilight_row_frame, textvariable=self.start_offset_var, width=4)
        self.start_offset_entry.pack(side="left", padx=(2, 8))
        self.start_offset_entry.bind("<FocusOut>", self._on_offset_change)
        self.start_offset_entry.bind("<Return>", self._on_offset_change)
        ToolTip(self.start_offset_entry, SCHEDULING_TOOLTIPS["start_offset"])

        ttk.Label(twilight_row_frame, text="End Offset:").pack(side="left")
        self.end_offset_var = tk.StringVar(value="0")
        self.end_offset_entry = ttk.Entry(twilight_row_frame, textvariable=self.end_offset_var, width=4)
        self.end_offset_entry.pack(side="left", padx=(2, 2))
        self.end_offset_entry.bind("<FocusOut>", self._on_offset_change)
        self.end_offset_entry.bind("<Return>", self._on_offset_change)
        ToolTip(self.end_offset_entry, SCHEDULING_TOOLTIPS["end_offset"])

        ttk.Label(twilight_row_frame, text="min", font=("Segoe UI", 8), foreground="gray").pack(side="left")

        # Row 2: Twilight description
        self.twilight_desc_label = ttk.Label(
            self.twilight_frame,
            text="Sun 18° below horizon - true darkness",
            font=("Segoe UI", 8),
            foreground="gray"
        )
        self.twilight_desc_label.grid(row=2, column=0, columnspan=7, sticky="w", pady=(5, 0))

        # Store twilight widgets for enable/disable
        self.twilight_widgets = [
            self.latitude_entry, self.longitude_entry, self.twilight_combo,
            self.start_offset_entry, self.end_offset_entry
        ]

        # --- Right Column: Manual Settings ---
        self.manual_frame = ttk.LabelFrame(columns_frame, text="Manual Settings", padding=10)
        self.manual_frame.grid(row=0, column=1, sticky="ns", padx=(5, 0))

        # Manual start time
        ttk.Label(self.manual_frame, text="Start (HH:MM):").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.manual_start_var = tk.StringVar(value="22:00")
        self.manual_start_entry = ttk.Entry(self.manual_frame, textvariable=self.manual_start_var, width=15)
        self.manual_start_entry.grid(row=0, column=1, sticky="w")
        self.manual_start_entry.bind("<FocusOut>", self._on_manual_time_change)
        self.manual_start_entry.bind("<Return>", self._on_manual_time_change)
        ToolTip(self.manual_start_entry, SCHEDULING_TOOLTIPS["manual_start_time"])

        # Manual end time
        ttk.Label(self.manual_frame, text="End (HH:MM):").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(10, 0))
        self.manual_end_var = tk.StringVar(value="06:00")
        self.manual_end_entry = ttk.Entry(self.manual_frame, textvariable=self.manual_end_var, width=15)
        self.manual_end_entry.grid(row=1, column=1, sticky="w", pady=(10, 0))
        self.manual_end_entry.bind("<FocusOut>", self._on_manual_time_change)
        self.manual_end_entry.bind("<Return>", self._on_manual_time_change)
        ToolTip(self.manual_end_entry, SCHEDULING_TOOLTIPS["manual_end_time"])

        # Info label for manual mode
        self.manual_info_label = ttk.Label(
            self.manual_frame,
            text="Overnight OK",
            font=("Segoe UI", 8),
            foreground="gray"
        )
        self.manual_info_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        # Store manual widgets for enable/disable
        self.manual_widgets = [self.manual_start_entry, self.manual_end_entry]

        # === Row 2: Tonight's window display ===
        tonight_frame = ttk.Frame(parent)
        tonight_frame.grid(row=2, column=0, columnspan=2, sticky="w", pady=(15, 0))

        ttk.Label(tonight_frame, text="Tonight:", font=("Segoe UI", 9, "bold")).pack(side="left")
        self.tonight_label = ttk.Label(
            tonight_frame,
            text="--:-- - --:-- (--h --m)",
            font=("Segoe UI", 10),
            foreground="#0066CC"
        )
        self.tonight_label.pack(side="left", padx=(10, 0))
        ToolTip(self.tonight_label, SCHEDULING_TOOLTIPS["tonight_display"])

    def _create_calendar_section(self, parent: ttk.LabelFrame):
        """Create calendar widget"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Get snapshots directory from config (resolve to absolute path)
        snapshots_dir = Path(self.config_manager.capture.output_folder).resolve()

        self.calendar = TwoMonthCalendar(
            parent,
            snapshots_dir=str(snapshots_dir),
            on_selection_change=self._on_calendar_selection_change
        )
        self.calendar.grid(row=0, column=0, sticky="nsew")
        ToolTip(self.calendar, SCHEDULING_TOOLTIPS["calendar"])

    def _create_video_section(self, parent: ttk.LabelFrame):
        """Create auto video settings widgets"""
        # Row 0: Enable checkbox and delete checkbox
        row_frame = ttk.Frame(parent)
        row_frame.grid(row=0, column=0, sticky="w")

        self.auto_video_var = tk.BooleanVar(value=False)
        auto_video_check = ttk.Checkbutton(
            row_frame,
            text="Create video after each night's session",
            variable=self.auto_video_var,
            command=self._on_auto_video_toggle
        )
        auto_video_check.pack(side="left")
        ToolTip(auto_video_check, SCHEDULING_TOOLTIPS["auto_video"])

        # Delete snapshots checkbox
        self.delete_snapshots_var = tk.BooleanVar(value=False)
        self.delete_snapshots_check = ttk.Checkbutton(
            row_frame,
            text="Delete snapshots after",
            variable=self.delete_snapshots_var
        )
        self.delete_snapshots_check.pack(side="left", padx=(20, 0))
        ToolTip(self.delete_snapshots_check,
            "Automatically delete the snapshot folder after\n"
            "successfully creating the video.\n\n"
            "WARNING: This permanently deletes all captured\n"
            "images for that date. Use with caution!"
        )

        # Initially disable delete checkbox if auto video is off
        self._update_video_widgets_state()

    def _create_log_section(self, parent: ttk.LabelFrame):
        """Create scheduler control and log display"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # === Scheduler Control Row ===
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        self.scheduler_enabled_var = tk.BooleanVar(value=False)
        self.scheduler_checkbox = ttk.Checkbutton(
            control_frame,
            text="Enable automatic scheduling",
            variable=self.scheduler_enabled_var,
            command=self._on_scheduler_toggle
        )
        self.scheduler_checkbox.pack(side="left")
        ToolTip(self.scheduler_checkbox,
            "Enable automatic capture scheduling.\n"
            "When enabled, capture will automatically start\n"
            "at darkness and stop at dawn for scheduled dates."
        )

        # Status indicator
        self.scheduler_status_label = ttk.Label(
            control_frame,
            text="Scheduler: Inactive",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        self.scheduler_status_label.pack(side="right", padx=(20, 0))

        # Separator
        ttk.Separator(parent, orient="horizontal").grid(row=1, column=0, sticky="ew", pady=5)

        # === Log Display ===
        self.log_text = scrolledtext.ScrolledText(
            parent,
            height=10,
            wrap=tk.WORD,
            font=("Consolas", 9),
            state=tk.DISABLED
        )
        self.log_text.grid(row=2, column=0, sticky="nsew")

        # Configure tags for log levels
        self.log_text.tag_configure("INFO", foreground="#000000")
        self.log_text.tag_configure("WARNING", foreground="#CC6600")
        self.log_text.tag_configure("ERROR", foreground="#CC0000")
        self.log_text.tag_configure("timestamp", foreground="#666666")

        # Clear button
        clear_btn = ttk.Button(parent, text="Clear Log", command=self._clear_log)
        clear_btn.grid(row=3, column=0, sticky="e", pady=(5, 0))

        # Update row weight for log area
        parent.rowconfigure(2, weight=1)

    def _clear_log(self):
        """Clear the log text widget"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _log_to_panel(self, level: str, message: str):
        """Add a log message to the panel's log display"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.log_text.insert(tk.END, f"[{level}] ", level)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)  # Auto-scroll to bottom
        self.log_text.config(state=tk.DISABLED)

    def _load_from_config(self):
        """Load settings from config manager"""
        cfg = self.config_manager.astro_schedule

        # Time mode
        self.time_mode_var.set("manual" if cfg.use_manual_times else "twilight")

        # Twilight settings
        self.latitude_var.set(str(cfg.latitude))
        self.longitude_var.set(str(cfg.longitude))
        self.twilight_type_var.set(cfg.twilight_type)
        self.start_offset_var.set(str(cfg.start_offset_minutes))
        self.end_offset_var.set(str(cfg.end_offset_minutes))

        # Manual time settings
        self.manual_start_var.set(cfg.manual_start_time)
        self.manual_end_var.set(cfg.manual_end_time)

        # Auto video settings
        self.auto_video_var.set(cfg.auto_create_video)
        self.delete_snapshots_var.set(cfg.delete_snapshots_after_video)

        # Load scheduled dates into calendar
        if cfg.scheduled_dates:
            self.calendar.set_selected_dates(set(cfg.scheduled_dates))

        # Update twilight calculator
        self._update_twilight_calculator()
        self._update_hemisphere_display()
        self._update_twilight_description()
        self._update_video_widgets_state()
        self._update_time_mode_widgets()

    def _save_to_config(self):
        """Save current settings to config manager"""
        cfg = self.config_manager.astro_schedule

        # Time mode
        cfg.use_manual_times = (self.time_mode_var.get() == "manual")

        # Twilight settings
        try:
            cfg.latitude = float(self.latitude_var.get())
        except ValueError:
            cfg.latitude = 0.0

        try:
            cfg.longitude = float(self.longitude_var.get())
        except ValueError:
            cfg.longitude = 0.0

        cfg.twilight_type = self.twilight_type_var.get()

        try:
            cfg.start_offset_minutes = int(self.start_offset_var.get())
        except ValueError:
            cfg.start_offset_minutes = 0

        try:
            cfg.end_offset_minutes = int(self.end_offset_var.get())
        except ValueError:
            cfg.end_offset_minutes = 0

        # Manual time settings
        cfg.manual_start_time = self.manual_start_var.get()
        cfg.manual_end_time = self.manual_end_var.get()

        # Auto video settings
        cfg.auto_create_video = self.auto_video_var.get()
        cfg.delete_snapshots_after_video = self.delete_snapshots_var.get()
        cfg.scheduled_dates = list(self.calendar.get_selected_dates())

        # Save to file
        self.config_manager.save_to_file()

    def _update_twilight_calculator(self):
        """Update the twilight calculator with current location"""
        try:
            lat = float(self.latitude_var.get())
            lon = float(self.longitude_var.get())
            self.twilight_calc = TwilightCalculator(lat, lon)
        except ValueError:
            self.twilight_calc = None

    def _update_tonight_display(self):
        """Update the tonight's window display"""
        # Check if in manual mode
        if self.time_mode_var.get() == "manual":
            start_time = self.manual_start_var.get()
            end_time = self.manual_end_var.get()

            # Calculate duration for manual times
            try:
                start_parts = start_time.split(":")
                end_parts = end_time.split(":")
                start_mins = int(start_parts[0]) * 60 + int(start_parts[1])
                end_mins = int(end_parts[0]) * 60 + int(end_parts[1])

                # Handle overnight (e.g., 22:00 - 06:00)
                if end_mins < start_mins:
                    duration_mins = (24 * 60 - start_mins) + end_mins
                else:
                    duration_mins = end_mins - start_mins

                hours = duration_mins // 60
                mins = duration_mins % 60
                self.tonight_label.config(text=f"{start_time} - {end_time} ({hours}h {mins}m)")
            except (ValueError, IndexError):
                self.tonight_label.config(text=f"{start_time} - {end_time}")
            return

        # Twilight-based mode
        if self.twilight_calc is None:
            self.tonight_label.config(text="--:-- - --:-- (--h --m)")
            return

        try:
            start_offset = int(self.start_offset_var.get())
        except ValueError:
            start_offset = 0

        try:
            end_offset = int(self.end_offset_var.get())
        except ValueError:
            end_offset = 0

        window = self.twilight_calc.get_tonight_window(
            twilight_type=self.twilight_type_var.get(),
            start_offset_minutes=start_offset,
            end_offset_minutes=end_offset
        )

        if window:
            self.tonight_label.config(
                text=f"{window.get_time_range_str()} ({window.get_duration_str()})"
            )
        else:
            self.tonight_label.config(text="No darkness window (polar day/night)")

    def _update_hemisphere_display(self):
        """Update the hemisphere indicator"""
        try:
            lat = float(self.latitude_var.get())
            if lat > 0:
                self.hemisphere_label.config(text="(Northern Hemisphere)")
            elif lat < 0:
                self.hemisphere_label.config(text="(Southern Hemisphere)")
            else:
                self.hemisphere_label.config(text="(Equator)")
        except ValueError:
            self.hemisphere_label.config(text="")

    def _update_twilight_description(self):
        """Update twilight type description"""
        descriptions = {
            "civil": "Sun 6° below horizon - outdoor activities possible",
            "nautical": "Sun 12° below horizon - horizon visible at sea",
            "astronomical": "Sun 18° below horizon - true darkness"
        }
        desc = descriptions.get(self.twilight_type_var.get(), "")
        self.twilight_desc_label.config(text=desc)

    def _update_video_widgets_state(self):
        """Enable/disable video widgets based on checkbox"""
        state = "normal" if self.auto_video_var.get() else "disabled"
        self.delete_snapshots_check.config(state=state)

    def _update_time_mode_widgets(self):
        """Enable/disable twilight or manual widgets based on selected mode"""
        is_manual = (self.time_mode_var.get() == "manual")

        # Twilight widgets - disabled when in manual mode
        twilight_state = "disabled" if is_manual else "normal"
        for widget in self.twilight_widgets:
            if isinstance(widget, ttk.Combobox):
                widget.config(state="disabled" if is_manual else "readonly")
            else:
                widget.config(state=twilight_state)

        # Manual widgets - disabled when in twilight mode
        manual_state = "normal" if is_manual else "disabled"
        for widget in self.manual_widgets:
            widget.config(state=manual_state)

    # Event handlers

    def _on_location_change(self, event=None):
        """Handle location change"""
        self._update_twilight_calculator()
        self._update_hemisphere_display()
        self._update_tonight_display()
        self._save_to_config()

    def _on_twilight_change(self, event=None):
        """Handle twilight type change"""
        self._update_twilight_description()
        self._update_tonight_display()
        self._save_to_config()

    def _on_offset_change(self, event=None):
        """Handle offset change"""
        self._update_tonight_display()
        self._save_to_config()

    def _on_time_mode_change(self):
        """Handle time mode radio button change"""
        self._update_time_mode_widgets()
        self._update_tonight_display()
        self._save_to_config()

    def _on_manual_time_change(self, event=None):
        """Handle manual time entry change"""
        self._update_tonight_display()
        self._save_to_config()

    def _on_calendar_selection_change(self, dates: Set[str]):
        """Handle calendar selection change"""
        self._save_to_config()

    def _on_auto_video_toggle(self):
        """Handle auto video checkbox toggle"""
        self._update_video_widgets_state()
        self._save_to_config()

    def _on_scheduler_toggle(self):
        """Handle scheduler enable/disable toggle"""
        if self.scheduler_enabled_var.get():
            self._start_scheduler()
        else:
            self._stop_scheduler()

    def _start_scheduler(self):
        """Start the astronomical scheduler"""
        # Check if location is set
        try:
            lat = float(self.latitude_var.get())
            lon = float(self.longitude_var.get())
            if lat == 0.0 and lon == 0.0:
                self._log("WARNING", "Location not set - scheduler may not work correctly")
        except ValueError:
            self._log("ERROR", "Invalid location values")
            self.scheduler_enabled_var.set(False)
            return

        # Create scheduler if not exists
        if self.scheduler is None:
            self.scheduler = AstroScheduler(
                config_manager=self.config_manager,
                on_start_capture=self._on_scheduler_start_capture,
                on_stop_capture=self._on_scheduler_stop_capture,
                on_session_complete=self._on_session_complete,
                on_log=self._log
            )

        # Start the scheduler
        self.scheduler.start()
        self._update_scheduler_status()
        self._log("INFO", "Astronomical scheduler enabled")

    def _stop_scheduler(self):
        """Stop the astronomical scheduler"""
        if self.scheduler:
            # If capture is running due to scheduler, stop it first
            if self.scheduler.capture_active:
                self._log("INFO", "Stopping scheduled capture...")
                if self.stop_capture_callback:
                    self.stop_capture_callback()
            self.scheduler.stop()
        self._update_scheduler_status()
        self._log("INFO", "Astronomical scheduler disabled")

    def _update_scheduler_status(self):
        """Update the scheduler status display"""
        if self.scheduler and self.scheduler.is_running():
            status = self.scheduler.get_status()
            if status.get("capture_active"):
                self.scheduler_status_label.config(
                    text="Scheduler: Capturing",
                    foreground="#00AA00"
                )
            else:
                self.scheduler_status_label.config(
                    text="Scheduler: Active (waiting)",
                    foreground="#0066CC"
                )
        else:
            self.scheduler_status_label.config(
                text="Scheduler: Inactive",
                foreground="gray"
            )

    def _on_scheduler_start_capture(self):
        """Called by scheduler when it's time to start capture"""
        self._update_scheduler_status()
        if self.start_capture_callback:
            # Use after() to call on main thread
            self.after(0, self.start_capture_callback)

    def _on_scheduler_stop_capture(self):
        """Called by scheduler when it's time to stop capture"""
        self._update_scheduler_status()
        if self.stop_capture_callback:
            # Use after() to call on main thread
            self.after(0, self.stop_capture_callback)

    def _on_session_complete(self, date_str: str):
        """Called by scheduler when a capture session completes"""
        self._log("INFO", f"Session complete for {date_str}")

        # Check if auto video creation is enabled
        if self.auto_video_var.get():
            self._log("INFO", f"Auto-creating video for {date_str}")
            if self.create_video_callback:
                # Pass the date string so the callback can find the right folder
                self.after(0, lambda: self.create_video_callback(date_str))

    def _log(self, level: str, message: str):
        """Log a message to both panel log and main GUI log"""
        # Log to panel's log display (use after() for thread safety)
        self.after(0, lambda: self._log_to_panel(level, message))

        # Also log to main GUI if callback set
        if self.log_callback:
            self.log_callback(level, f"[Scheduling] {message}")
        else:
            print(f"[{level}] [Scheduling] {message}")

    # Public methods for main GUI integration

    def set_callbacks(self, start_capture=None, stop_capture=None, create_video=None, log=None):
        """
        Set callbacks for integration with main GUI.

        Args:
            start_capture: Callback to start capture
            stop_capture: Callback to stop capture
            create_video: Callback to create video (receives date_str YYYYMMDD)
            log: Callback to log messages (level, message)
        """
        self.start_capture_callback = start_capture
        self.stop_capture_callback = stop_capture
        self.create_video_callback = create_video
        self.log_callback = log

    def cleanup(self):
        """Clean up resources when panel is destroyed"""
        if self.scheduler:
            self.scheduler.stop()
            self.scheduler = None


def test_scheduling_panel():
    """Test the scheduling panel"""
    root = tk.Tk()
    root.title("Scheduling Panel Test")
    root.geometry("650x700")

    # Create config manager
    config_manager = ConfigManager()

    # Create panel
    panel = SchedulingPanel(root, config_manager)
    panel.pack(fill="both", expand=True)

    root.mainloop()


if __name__ == "__main__":
    test_scheduling_panel()
