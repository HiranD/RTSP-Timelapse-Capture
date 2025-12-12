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
        self.rowconfigure(3, weight=1)  # Calendar row expands
        self.rowconfigure(5, weight=1)  # Log row also expands

        # === Location Section ===
        location_frame = ttk.LabelFrame(self, text="Location", padding=10)
        location_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self._create_location_section(location_frame)

        # === Twilight Settings Section ===
        twilight_frame = ttk.LabelFrame(self, text="Twilight Settings", padding=10)
        twilight_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self._create_twilight_section(twilight_frame)

        # === Scheduler Control Section ===
        scheduler_frame = ttk.LabelFrame(self, text="Scheduler Control", padding=10)
        scheduler_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        self._create_scheduler_section(scheduler_frame)

        # === Calendar Section ===
        calendar_frame = ttk.LabelFrame(self, text="Schedule Calendar", padding=10)
        calendar_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
        self._create_calendar_section(calendar_frame)

        # === Auto Video Section ===
        video_frame = ttk.LabelFrame(self, text="Auto Video Creation", padding=10)
        video_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=5)
        self._create_video_section(video_frame)

        # === Log Section ===
        log_frame = ttk.LabelFrame(self, text="Scheduler Log", padding=10)
        log_frame.grid(row=5, column=0, sticky="nsew", padx=10, pady=(5, 10))
        self._create_log_section(log_frame)

    def _create_location_section(self, parent: ttk.LabelFrame):
        """Create location settings widgets"""
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)

        # Latitude
        ttk.Label(parent, text="Latitude:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.latitude_var = tk.StringVar(value="0.0")
        self.latitude_entry = ttk.Entry(parent, textvariable=self.latitude_var, width=15)
        self.latitude_entry.grid(row=0, column=1, sticky="w", padx=(0, 20))
        self.latitude_entry.bind("<FocusOut>", self._on_location_change)
        self.latitude_entry.bind("<Return>", self._on_location_change)
        ToolTip(self.latitude_entry, SCHEDULING_TOOLTIPS["latitude"])

        # Longitude
        ttk.Label(parent, text="Longitude:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.longitude_var = tk.StringVar(value="0.0")
        self.longitude_entry = ttk.Entry(parent, textvariable=self.longitude_var, width=15)
        self.longitude_entry.grid(row=0, column=3, sticky="w")
        self.longitude_entry.bind("<FocusOut>", self._on_location_change)
        self.longitude_entry.bind("<Return>", self._on_location_change)
        ToolTip(self.longitude_entry, SCHEDULING_TOOLTIPS["longitude"])

        # Hemisphere indicator
        self.hemisphere_label = ttk.Label(parent, text="", font=("Segoe UI", 8))
        self.hemisphere_label.grid(row=0, column=4, sticky="w", padx=(20, 0))

    def _create_twilight_section(self, parent: ttk.LabelFrame):
        """Create twilight settings widgets"""
        # Row 0: Twilight type
        ttk.Label(parent, text="Twilight Type:").grid(row=0, column=0, sticky="w", padx=(0, 5))

        self.twilight_type_var = tk.StringVar(value="astronomical")
        twilight_combo = ttk.Combobox(
            parent,
            textvariable=self.twilight_type_var,
            values=["civil", "nautical", "astronomical"],
            state="readonly",
            width=15
        )
        twilight_combo.grid(row=0, column=1, sticky="w", padx=(0, 20))
        twilight_combo.bind("<<ComboboxSelected>>", self._on_twilight_change)
        ToolTip(twilight_combo, SCHEDULING_TOOLTIPS["twilight_type"])

        # Twilight description
        self.twilight_desc_label = ttk.Label(
            parent,
            text="Sun 18° below horizon - true darkness",
            font=("Segoe UI", 8),
            foreground="gray"
        )
        self.twilight_desc_label.grid(row=0, column=2, columnspan=3, sticky="w")

        # Row 1: Offsets - use frames to keep input and "min" together
        start_offset_frame = ttk.Frame(parent)
        start_offset_frame.grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Label(start_offset_frame, text="Start Offset:").pack(side="left", padx=(0, 5))
        self.start_offset_var = tk.StringVar(value="0")
        start_offset_entry = ttk.Entry(start_offset_frame, textvariable=self.start_offset_var, width=6)
        start_offset_entry.pack(side="left")
        start_offset_entry.bind("<FocusOut>", self._on_offset_change)
        start_offset_entry.bind("<Return>", self._on_offset_change)
        ToolTip(start_offset_entry, SCHEDULING_TOOLTIPS["start_offset"])
        ttk.Label(start_offset_frame, text="min").pack(side="left", padx=(3, 30))

        ttk.Label(start_offset_frame, text="End Offset:").pack(side="left", padx=(0, 5))
        self.end_offset_var = tk.StringVar(value="0")
        end_offset_entry = ttk.Entry(start_offset_frame, textvariable=self.end_offset_var, width=6)
        end_offset_entry.pack(side="left")
        end_offset_entry.bind("<FocusOut>", self._on_offset_change)
        end_offset_entry.bind("<Return>", self._on_offset_change)
        ToolTip(end_offset_entry, SCHEDULING_TOOLTIPS["end_offset"])
        ttk.Label(start_offset_frame, text="min").pack(side="left", padx=(3, 0))

        # Row 2: Tonight's window display
        tonight_frame = ttk.Frame(parent)
        tonight_frame.grid(row=2, column=0, columnspan=6, sticky="w", pady=(15, 0))

        ttk.Label(tonight_frame, text="Tonight:", font=("Segoe UI", 9, "bold")).pack(side="left")
        self.tonight_label = ttk.Label(
            tonight_frame,
            text="--:-- - --:-- (--h --m)",
            font=("Segoe UI", 10),
            foreground="#0066CC"
        )
        self.tonight_label.pack(side="left", padx=(10, 0))
        ToolTip(self.tonight_label, SCHEDULING_TOOLTIPS["tonight_display"])

    def _create_scheduler_section(self, parent: ttk.LabelFrame):
        """Create scheduler control widgets"""
        # Enable scheduler checkbox and start/stop button
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill="x")

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

    def _create_calendar_section(self, parent: ttk.LabelFrame):
        """Create calendar widget"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Get snapshots directory from config
        snapshots_dir = self.config_manager.capture.output_folder

        self.calendar = TwoMonthCalendar(
            parent,
            snapshots_dir=snapshots_dir,
            on_selection_change=self._on_calendar_selection_change
        )
        self.calendar.grid(row=0, column=0, sticky="nsew")
        ToolTip(self.calendar, SCHEDULING_TOOLTIPS["calendar"])

    def _create_video_section(self, parent: ttk.LabelFrame):
        """Create auto video settings widgets"""
        # Row 0: Enable checkbox
        self.auto_video_var = tk.BooleanVar(value=False)
        auto_video_check = ttk.Checkbutton(
            parent,
            text="Create video after each night's session",
            variable=self.auto_video_var,
            command=self._on_auto_video_toggle
        )
        auto_video_check.grid(row=0, column=0, columnspan=4, sticky="w")
        ToolTip(auto_video_check, SCHEDULING_TOOLTIPS["auto_video"])

        # Row 1: Preset selection
        self.preset_label = ttk.Label(parent, text="Preset:")
        self.preset_label.grid(row=1, column=0, sticky="w", padx=(20, 5), pady=(5, 0))

        self.preset_var = tk.StringVar(value="Standard 24fps")
        self.preset_combo = ttk.Combobox(
            parent,
            textvariable=self.preset_var,
            values=self.preset_manager.list_presets(),
            state="readonly",
            width=25
        )
        self.preset_combo.grid(row=1, column=1, sticky="w", pady=(5, 0))
        ToolTip(self.preset_combo, SCHEDULING_TOOLTIPS["video_preset"])

        # Row 2: Output folder
        self.output_label = ttk.Label(parent, text="Output:")
        self.output_label.grid(row=2, column=0, sticky="w", padx=(20, 5), pady=(5, 0))

        output_frame = ttk.Frame(parent)
        output_frame.grid(row=2, column=1, columnspan=3, sticky="ew", pady=(5, 0))

        self.output_var = tk.StringVar(value="videos")
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_var, width=35)
        self.output_entry.pack(side="left", padx=(0, 5))
        ToolTip(self.output_entry, SCHEDULING_TOOLTIPS["video_output"])

        self.browse_btn = ttk.Button(output_frame, text="Browse", command=self._browse_output_folder)
        self.browse_btn.pack(side="left")

        # Row 3: Delete snapshots after video creation
        self.delete_snapshots_var = tk.BooleanVar(value=False)
        self.delete_snapshots_check = ttk.Checkbutton(
            parent,
            text="Delete snapshot folder after video creation",
            variable=self.delete_snapshots_var,
            command=self._on_auto_video_toggle
        )
        self.delete_snapshots_check.grid(row=3, column=0, columnspan=4, sticky="w", padx=(20, 0), pady=(5, 0))
        ToolTip(self.delete_snapshots_check,
            "Automatically delete the snapshot folder after\n"
            "successfully creating the video.\n\n"
            "WARNING: This permanently deletes all captured\n"
            "images for that date. Use with caution!"
        )

        # Initially disable preset/output if auto video is off
        self._update_video_widgets_state()

    def _create_log_section(self, parent: ttk.LabelFrame):
        """Create scheduler log display"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Create scrolled text widget for log
        self.log_text = scrolledtext.ScrolledText(
            parent,
            height=6,
            wrap=tk.WORD,
            font=("Consolas", 9),
            state=tk.DISABLED
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        # Configure tags for log levels
        self.log_text.tag_configure("INFO", foreground="#000000")
        self.log_text.tag_configure("WARNING", foreground="#CC6600")
        self.log_text.tag_configure("ERROR", foreground="#CC0000")
        self.log_text.tag_configure("timestamp", foreground="#666666")

        # Clear button
        clear_btn = ttk.Button(parent, text="Clear Log", command=self._clear_log)
        clear_btn.grid(row=1, column=0, sticky="e", pady=(5, 0))

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

        self.latitude_var.set(str(cfg.latitude))
        self.longitude_var.set(str(cfg.longitude))
        self.twilight_type_var.set(cfg.twilight_type)
        self.start_offset_var.set(str(cfg.start_offset_minutes))
        self.end_offset_var.set(str(cfg.end_offset_minutes))
        self.auto_video_var.set(cfg.auto_create_video)
        self.preset_var.set(cfg.video_preset)
        self.output_var.set(cfg.video_output_folder)
        self.delete_snapshots_var.set(cfg.delete_snapshots_after_video)

        # Load scheduled dates into calendar
        if cfg.scheduled_dates:
            self.calendar.set_selected_dates(set(cfg.scheduled_dates))

        # Update twilight calculator
        self._update_twilight_calculator()
        self._update_hemisphere_display()
        self._update_twilight_description()
        self._update_video_widgets_state()

    def _save_to_config(self):
        """Save current settings to config manager"""
        cfg = self.config_manager.astro_schedule

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

        cfg.auto_create_video = self.auto_video_var.get()
        cfg.video_preset = self.preset_var.get()
        cfg.video_output_folder = self.output_var.get()
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
        self.preset_combo.config(state="readonly" if self.auto_video_var.get() else "disabled")
        self.output_entry.config(state=state)
        self.delete_snapshots_check.config(state=state)
        self.browse_btn.config(state=state)

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

    def _browse_output_folder(self):
        """Open folder browser for output directory"""
        current = self.output_var.get()
        initial_dir = current if Path(current).exists() else "."

        folder = filedialog.askdirectory(
            title="Select Video Output Folder",
            initialdir=initial_dir
        )

        if folder:
            self.output_var.set(folder)
            self._save_to_config()


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
