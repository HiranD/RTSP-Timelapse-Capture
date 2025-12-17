"""
RTSP Timelapse Capture System - GUI Application
Phase 3.5: Video Export Feature Added

A Tkinter-based GUI for managing RTSP camera timelapse captures with live preview
and video export capabilities.
"""

import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageTk
import numpy as np

from config_manager import ConfigManager
from capture_engine import CaptureEngine, CaptureState
from video_export_panel import VideoExportPanel
from scheduling_panel import SchedulingPanel
from video_export_controller import VideoExportController
from preset_manager import PresetManager
from tooltip import ToolTip
from capture_tooltips import CAPTURE_TOOLTIPS

# Configure FFmpeg environment for Annke camera compatibility
# These settings improve RTSP stream stability for IP cameras
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = (
    'rtsp_transport;tcp|'           # Force TCP transport for reliability
    'stimeout;5000000|'             # Socket timeout: 5 seconds (in microseconds)
    'rw_timeout;10000000|'          # Read/write timeout: 10 seconds
    'rtsp_flags;prefer_tcp|'        # Prefer TCP over UDP
    'buffer_size;1024000|'          # Increase buffer for network jitter
    'max_delay;500000'              # Max demux delay: 0.5 seconds
)


class RTSPTimelapseGUI:
    """Main GUI application for RTSP timelapse capture"""

    def __init__(self, root):
        self.root = root
        self.root.title("RTSP Timelapse Capture System")
        self.root.geometry("1200x900")
        self.root.minsize(1000, 850)

        # Configuration and engine
        self.config_manager = ConfigManager()
        self.capture_engine = None
        self.is_capturing = False

        # Preview variables
        self.preview_enabled = tk.BooleanVar(value=self.config_manager.ui.preview_enabled)
        self.current_preview_image = None
        self.preview_photo = None

        # Statistics
        self.total_captures = 0
        self.failed_captures = 0
        self.session_start_time = None

        # Load existing config if available
        self.load_config()

        # Build GUI
        self.create_widgets()
        self.setup_callbacks()
        self.setup_keyboard_shortcuts()

        # Update status initially
        self.update_status()

    def create_widgets(self):
        """Create all GUI widgets with tabbed interface"""

        # Configure root grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Tab 1: Capture (existing functionality)
        self.capture_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.capture_tab, text="  Capture  ")
        self.create_capture_tab()

        # Tab 2: Video Export
        self.video_export_panel = VideoExportPanel(
            self.notebook,
            default_snapshots_dir=self.config_manager.capture.output_folder,
            config_manager=self.config_manager
        )
        self.notebook.add(self.video_export_panel, text="  Video Export  ")

        # Tab 3: Scheduling
        self.scheduling_panel = SchedulingPanel(
            self.notebook,
            config_manager=self.config_manager
        )
        self.notebook.add(self.scheduling_panel, text="  Scheduling  ")

        # Set up scheduling panel callbacks
        self.scheduling_panel.set_callbacks(
            start_capture=self.start_capture,
            stop_capture=self.stop_capture,
            create_video=self._auto_create_video_for_date,
            log=self.log_message
        )

    def create_capture_tab(self):
        """Create the capture tab (original main view)"""
        # Main container
        main_frame = self.capture_tab
        main_frame.columnconfigure(1, weight=0)  # Middle column (status/controls) - fixed width
        main_frame.columnconfigure(2, weight=1)  # Right column (preview) - expandable
        main_frame.rowconfigure(2, weight=1)

        # === LEFT COLUMN: Configuration ===
        self.create_config_panel(main_frame)

        # === MIDDLE COLUMN: Status and Controls ===
        middle_frame = ttk.Frame(main_frame)
        middle_frame.grid(row=0, column=1, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0))
        middle_frame.columnconfigure(0, weight=1)
        middle_frame.rowconfigure(1, weight=1)

        self.create_status_panel(middle_frame)
        self.create_control_panel(middle_frame)

        # === RIGHT COLUMN: Preview and Statistics ===
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=2, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=0)

        self.create_preview_panel(right_frame)
        self.create_statistics_panel(right_frame)

        # === BOTTOM: Activity Log ===
        self.create_log_panel(main_frame)

    def create_config_panel(self, parent):
        """Create configuration input panel"""

        config_frame = ttk.LabelFrame(parent, text="Camera Configuration", padding="10")
        config_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), pady=(0, 10))

        row = 0

        # Camera IP
        ttk.Label(config_frame, text="IP Address:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.ip_entry = ttk.Entry(config_frame, width=20)
        self.ip_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        self.ip_entry.insert(0, self.config_manager.camera.ip_address)
        ToolTip(self.ip_entry, CAPTURE_TOOLTIPS["ip_address"])
        row += 1

        # Username
        ttk.Label(config_frame, text="Username:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.username_entry = ttk.Entry(config_frame, width=20)
        self.username_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        self.username_entry.insert(0, self.config_manager.camera.username)
        ToolTip(self.username_entry, CAPTURE_TOOLTIPS["username"])
        row += 1

        # Password
        ttk.Label(config_frame, text="Password:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.password_entry = ttk.Entry(config_frame, width=20, show="*")
        self.password_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        self.password_entry.insert(0, self.config_manager.camera.password)
        ToolTip(self.password_entry, CAPTURE_TOOLTIPS["password"])
        row += 1

        # Stream Path
        ttk.Label(config_frame, text="Stream Path:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.stream_path_entry = ttk.Entry(config_frame, width=20)
        self.stream_path_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        self.stream_path_entry.insert(0, self.config_manager.camera.stream_path)
        ToolTip(self.stream_path_entry, CAPTURE_TOOLTIPS["stream_path"])
        row += 1

        # Force TCP
        self.force_tcp_var = tk.BooleanVar(value=self.config_manager.camera.force_tcp)
        force_tcp_check = ttk.Checkbutton(config_frame, text="Force TCP", variable=self.force_tcp_var)
        force_tcp_check.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        ToolTip(force_tcp_check, CAPTURE_TOOLTIPS["force_tcp"])
        row += 1

        # Separator
        ttk.Separator(config_frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        row += 1

        # Schedule Section
        ttk.Label(config_frame, text="Start Time (HH:MM):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.start_time_entry = ttk.Entry(config_frame, width=20)
        self.start_time_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        self.start_time_entry.insert(0, self.config_manager.schedule.start_time)
        ToolTip(self.start_time_entry, CAPTURE_TOOLTIPS["start_time"])
        row += 1

        ttk.Label(config_frame, text="End Time (HH:MM):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.end_time_entry = ttk.Entry(config_frame, width=20)
        self.end_time_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        self.end_time_entry.insert(0, self.config_manager.schedule.end_time)
        ToolTip(self.end_time_entry, CAPTURE_TOOLTIPS["end_time"])
        row += 1

        # Separator
        ttk.Separator(config_frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        row += 1

        # Capture Settings
        ttk.Label(config_frame, text="Interval (seconds):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.interval_entry = ttk.Entry(config_frame, width=20)
        self.interval_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        self.interval_entry.insert(0, str(self.config_manager.capture.interval_seconds))
        ToolTip(self.interval_entry, CAPTURE_TOOLTIPS["interval"])
        row += 1

        ttk.Label(config_frame, text="Output Folder:").grid(row=row, column=0, sticky=tk.W, pady=2)
        output_frame = ttk.Frame(config_frame)
        output_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        output_frame.columnconfigure(0, weight=1)

        self.output_entry = ttk.Entry(output_frame)
        self.output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.output_entry.insert(0, self.config_manager.capture.output_folder)
        ToolTip(self.output_entry, CAPTURE_TOOLTIPS["output_folder"])

        browse_btn = ttk.Button(output_frame, text="...", width=3, command=self.browse_output_dir)
        browse_btn.grid(row=0, column=1, padx=(5, 0))
        ToolTip(browse_btn, CAPTURE_TOOLTIPS["browse_output"])
        row += 1

        ttk.Label(config_frame, text="JPEG Quality (1-100):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.jpeg_quality_entry = ttk.Entry(config_frame, width=20)
        self.jpeg_quality_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        self.jpeg_quality_entry.insert(0, str(self.config_manager.capture.jpeg_quality))
        ToolTip(self.jpeg_quality_entry, CAPTURE_TOOLTIPS["jpeg_quality"])
        row += 1

        ttk.Label(config_frame, text="Proactive Reconnect (s):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.proactive_reconnect_entry = ttk.Entry(config_frame, width=20)
        self.proactive_reconnect_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        self.proactive_reconnect_entry.insert(0, str(self.config_manager.capture.proactive_reconnect_seconds))
        ToolTip(self.proactive_reconnect_entry, CAPTURE_TOOLTIPS["proactive_reconnect"])
        row += 1

        # Config buttons
        button_frame = ttk.Frame(config_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=(10, 0))

        save_config_btn = ttk.Button(button_frame, text="Save Config", command=self.save_config_ui)
        save_config_btn.pack(side=tk.LEFT, padx=2)
        ToolTip(save_config_btn, CAPTURE_TOOLTIPS["save_config"])

        load_config_btn = ttk.Button(button_frame, text="Load Config", command=self.load_config_ui)
        load_config_btn.pack(side=tk.LEFT, padx=2)
        ToolTip(load_config_btn, CAPTURE_TOOLTIPS["load_config"])

        config_frame.columnconfigure(1, weight=1)

    def create_status_panel(self, parent):
        """Create status display panel"""

        status_frame = ttk.LabelFrame(parent, text="Status", padding="10")
        status_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), pady=(0, 10))

        # Connection status
        ttk.Label(status_frame, text="Connection:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.connection_label = ttk.Label(status_frame, text="Disconnected", foreground="red")
        self.connection_label.grid(row=0, column=1, sticky=tk.W, pady=2, padx=(5, 0))

        # Capture state
        ttk.Label(status_frame, text="State:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.state_label = ttk.Label(status_frame, text="Stopped", foreground="gray")
        self.state_label.grid(row=1, column=1, sticky=tk.W, pady=2, padx=(5, 0))
        ToolTip(self.state_label, CAPTURE_TOOLTIPS["status_state"])

        # Frame count
        ttk.Label(status_frame, text="Frames Captured:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.frames_label = ttk.Label(status_frame, text="0")
        self.frames_label.grid(row=2, column=1, sticky=tk.W, pady=2, padx=(5, 0))
        ToolTip(self.frames_label, CAPTURE_TOOLTIPS["status_frames"])

        # Uptime
        ttk.Label(status_frame, text="Uptime:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.uptime_label = ttk.Label(status_frame, text="0:00:00")
        self.uptime_label.grid(row=3, column=1, sticky=tk.W, pady=2, padx=(5, 0))
        ToolTip(self.uptime_label, CAPTURE_TOOLTIPS["status_uptime"])

        # Last capture
        ttk.Label(status_frame, text="Last Capture:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.last_capture_label = ttk.Label(status_frame, text="Never")
        self.last_capture_label.grid(row=4, column=1, sticky=tk.W, pady=2, padx=(5, 0))
        ToolTip(self.last_capture_label, CAPTURE_TOOLTIPS["status_last_capture"])

        status_frame.columnconfigure(1, weight=1)

    def create_control_panel(self, parent):
        """Create control buttons panel"""

        control_frame = ttk.LabelFrame(parent, text="Controls", padding="10")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Test connection button
        self.test_btn = ttk.Button(control_frame, text="Test Connection", command=self.test_connection)
        self.test_btn.pack(fill=tk.X, pady=5)
        ToolTip(self.test_btn, CAPTURE_TOOLTIPS["test_connection"])

        # Start/Stop button
        self.start_stop_btn = ttk.Button(control_frame, text="Start Capture", command=self.toggle_capture)
        self.start_stop_btn.pack(fill=tk.X, pady=5)
        self.start_stop_tooltip = ToolTip(self.start_stop_btn, CAPTURE_TOOLTIPS["start_capture"])

        # Status indicator
        self.status_indicator = tk.Canvas(control_frame, height=30, bg="white")
        self.status_indicator.pack(fill=tk.X, pady=10)
        self.indicator_circle = self.status_indicator.create_oval(10, 5, 30, 25, fill="gray", outline="darkgray")
        self.indicator_text = self.status_indicator.create_text(40, 15, anchor=tk.W, text="Ready", font=("Arial", 10))

    def create_log_panel(self, parent):
        """Create activity log panel"""

        log_frame = ttk.LabelFrame(parent, text="Activity Log", padding="10")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        # Scrolled text widget for log
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure text tags for different log levels
        self.log_text.tag_config("INFO", foreground="black")
        self.log_text.tag_config("WARNING", foreground="orange")
        self.log_text.tag_config("ERROR", foreground="red")
        self.log_text.tag_config("SUCCESS", foreground="green")

        # Clear log button
        clear_log_btn = ttk.Button(log_frame, text="Clear Log", command=self.clear_log)
        clear_log_btn.grid(row=1, column=0, sticky=tk.E, pady=(5, 0))
        ToolTip(clear_log_btn, CAPTURE_TOOLTIPS["clear_log"])

    def create_preview_panel(self, parent):
        """Create live preview panel"""

        preview_frame = ttk.LabelFrame(parent, text="Live Preview", padding="10")
        preview_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(1, weight=1)

        # Preview controls
        controls_frame = ttk.Frame(preview_frame)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        preview_check = ttk.Checkbutton(controls_frame, text="Enable Preview", variable=self.preview_enabled,
                       command=self.toggle_preview)
        preview_check.pack(side=tk.LEFT)
        ToolTip(preview_check, CAPTURE_TOOLTIPS["enable_preview"])

        # Preview canvas
        self.preview_canvas = tk.Canvas(preview_frame, bg="black", highlightthickness=1, highlightbackground="gray")
        self.preview_canvas.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Bind canvas resize event to update preview
        self.preview_canvas.bind("<Configure>", self.on_canvas_resize)

        # Placeholder text
        self.preview_placeholder = self.preview_canvas.create_text(
            200, 150,
            text="No preview available\n\nStart capture to see live frames",
            fill="white",
            font=("Arial", 12),
            justify=tk.CENTER
        )

    def create_statistics_panel(self, parent):
        """Create statistics display panel"""

        stats_frame = ttk.LabelFrame(parent, text="Session Statistics", padding="10")
        stats_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        # Total captures
        ttk.Label(stats_frame, text="Total Captures:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.total_captures_label = ttk.Label(stats_frame, text="0")
        self.total_captures_label.grid(row=0, column=1, sticky=tk.W, pady=2, padx=(5, 0))
        ToolTip(self.total_captures_label, CAPTURE_TOOLTIPS["stats_total_captures"])

        # Success rate
        ttk.Label(stats_frame, text="Success Rate:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.success_rate_label = ttk.Label(stats_frame, text="100%")
        self.success_rate_label.grid(row=1, column=1, sticky=tk.W, pady=2, padx=(5, 0))
        ToolTip(self.success_rate_label, CAPTURE_TOOLTIPS["stats_success_rate"])

        # Average interval
        ttk.Label(stats_frame, text="Avg Interval:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.avg_interval_label = ttk.Label(stats_frame, text="N/A")
        self.avg_interval_label.grid(row=2, column=1, sticky=tk.W, pady=2, padx=(5, 0))
        ToolTip(self.avg_interval_label, CAPTURE_TOOLTIPS["stats_avg_interval"])

        # Session duration
        ttk.Label(stats_frame, text="Session Duration:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.session_duration_label = ttk.Label(stats_frame, text="0:00:00")
        self.session_duration_label.grid(row=3, column=1, sticky=tk.W, pady=2, padx=(5, 0))
        ToolTip(self.session_duration_label, CAPTURE_TOOLTIPS["stats_session_duration"])

        stats_frame.columnconfigure(1, weight=1)

    def setup_callbacks(self):
        """Set up capture engine callbacks (will be called when engine is created)"""
        pass

    def setup_keyboard_shortcuts(self):
        """Set up keyboard shortcuts"""
        self.root.bind('<Control-s>', lambda e: self.save_config_ui())
        self.root.bind('<Control-o>', lambda e: self.load_config_ui())
        self.root.bind('<Control-t>', lambda e: self.test_connection())
        self.root.bind('<space>', lambda e: self.toggle_capture() if not self.is_capturing else None)
        self.root.bind('<Escape>', lambda e: self.stop_capture() if self.is_capturing else None)

    def log_message(self, level, message):
        """Add a timestamped message to the activity log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_entry, level)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def clear_log(self):
        """Clear the activity log"""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def browse_output_dir(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(initialdir=self.output_entry.get())
        if directory:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, directory)

    def load_config(self):
        """Load configuration from default file"""
        config_file = Path("camera_config.json")
        if config_file.exists():
            success, message = self.config_manager.load_from_file(str(config_file))
            if not success:
                # Try migrating from old config.py
                self.config_manager.migrate_from_old_config()
        else:
            # Try migrating from old config.py
            self.config_manager.migrate_from_old_config()

    def load_config_ui(self):
        """Load configuration from file (user initiated)"""
        filename = filedialog.askopenfilename(
            title="Load Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            success, message = self.config_manager.load_from_file(filename)
            if success:
                self.update_config_ui()
                self.log_message("SUCCESS", f"Configuration loaded from {filename}")
                messagebox.showinfo("Success", message)
            else:
                self.log_message("ERROR", f"Failed to load config: {message}")
                messagebox.showerror("Error", message)

    def save_config_ui(self):
        """Save current configuration to file"""
        # Update config from UI
        self.update_config_from_ui()

        # Validate
        valid, errors = self.config_manager.validate()
        if not valid:
            error_msg = "\n".join(errors)
            self.log_message("ERROR", f"Invalid configuration: {error_msg}")
            messagebox.showerror("Invalid Configuration", error_msg)
            return

        # Save
        filename = filedialog.asksaveasfilename(
            title="Save Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="camera_config.json"
        )
        if filename:
            success, message = self.config_manager.save_to_file(filename)
            if success:
                self.log_message("SUCCESS", f"Configuration saved to {filename}")
                messagebox.showinfo("Success", message)
            else:
                self.log_message("ERROR", f"Failed to save config: {message}")
                messagebox.showerror("Error", message)

    def update_config_from_ui(self):
        """Update ConfigManager from UI inputs"""
        self.config_manager.camera.ip_address = self.ip_entry.get()
        self.config_manager.camera.username = self.username_entry.get()
        self.config_manager.camera.password = self.password_entry.get()
        self.config_manager.camera.stream_path = self.stream_path_entry.get()
        self.config_manager.camera.force_tcp = self.force_tcp_var.get()

        self.config_manager.schedule.start_time = self.start_time_entry.get()
        self.config_manager.schedule.end_time = self.end_time_entry.get()

        self.config_manager.capture.interval_seconds = int(self.interval_entry.get())
        self.config_manager.capture.output_folder = self.output_entry.get()
        self.config_manager.capture.jpeg_quality = int(self.jpeg_quality_entry.get())
        self.config_manager.capture.proactive_reconnect_seconds = int(self.proactive_reconnect_entry.get())

    def update_config_ui(self):
        """Update UI inputs from ConfigManager"""
        self.ip_entry.delete(0, tk.END)
        self.ip_entry.insert(0, self.config_manager.camera.ip_address)

        self.username_entry.delete(0, tk.END)
        self.username_entry.insert(0, self.config_manager.camera.username)

        self.password_entry.delete(0, tk.END)
        self.password_entry.insert(0, self.config_manager.camera.password)

        self.stream_path_entry.delete(0, tk.END)
        self.stream_path_entry.insert(0, self.config_manager.camera.stream_path)

        self.force_tcp_var.set(self.config_manager.camera.force_tcp)

        self.start_time_entry.delete(0, tk.END)
        self.start_time_entry.insert(0, self.config_manager.schedule.start_time)

        self.end_time_entry.delete(0, tk.END)
        self.end_time_entry.insert(0, self.config_manager.schedule.end_time)

        self.interval_entry.delete(0, tk.END)
        self.interval_entry.insert(0, str(self.config_manager.capture.interval_seconds))

        self.output_entry.delete(0, tk.END)
        self.output_entry.insert(0, self.config_manager.capture.output_folder)

        self.jpeg_quality_entry.delete(0, tk.END)
        self.jpeg_quality_entry.insert(0, str(self.config_manager.capture.jpeg_quality))

        self.proactive_reconnect_entry.delete(0, tk.END)
        self.proactive_reconnect_entry.insert(0, str(self.config_manager.capture.proactive_reconnect_seconds))

    def test_connection(self):
        """Test camera connection"""
        self.log_message("INFO", "Testing camera connection...")
        self.test_btn.configure(state=tk.DISABLED)

        # Update config from UI
        self.update_config_from_ui()

        # Create temporary engine for testing
        def test_thread():
            try:
                test_engine = CaptureEngine(self.config_manager.to_dict())
                success, message = test_engine.test_connection()

                # Update UI from main thread
                self.root.after(0, lambda: self.test_connection_complete(success, message))
            except Exception as e:
                self.root.after(0, lambda: self.test_connection_complete(False, str(e)))

        threading.Thread(target=test_thread, daemon=True).start()

    def test_connection_complete(self, success, message):
        """Handle test connection completion"""
        if success:
            self.log_message("SUCCESS", f"Connection test passed: {message}")
            self.connection_label.configure(text="Connected", foreground="green")
            messagebox.showinfo("Connection Test", message)
        else:
            self.log_message("ERROR", f"Connection test failed: {message}")
            self.connection_label.configure(text="Failed", foreground="red")
            messagebox.showerror("Connection Test", message)

        self.test_btn.configure(state=tk.NORMAL)

    def toggle_capture(self):
        """Start or stop capture"""
        if not self.is_capturing:
            self.start_capture()
        else:
            self.stop_capture()

    def start_capture(self):
        """Start the capture process"""
        # Update config from UI
        self.update_config_from_ui()

        # Validate
        valid, errors = self.config_manager.validate()
        if not valid:
            error_msg = "\n".join(errors)
            self.log_message("ERROR", f"Invalid configuration: {error_msg}")
            messagebox.showerror("Invalid Configuration", error_msg)
            return

        # Reset statistics for new session
        self.total_captures = 0
        self.failed_captures = 0
        self.session_start_time = datetime.now()
        self.update_statistics()

        # Create capture engine
        try:
            self.capture_engine = CaptureEngine(self.config_manager.to_dict())

            # Set up callbacks
            self.capture_engine.set_status_callback(self.on_status_update)
            self.capture_engine.set_frame_callback(self.on_frame_captured)
            self.capture_engine.set_log_callback(self.on_log_message)

            # Start capture
            self.capture_engine.start_capture()

            self.is_capturing = True
            self.start_stop_btn.configure(text="Stop Capture")
            self.start_stop_tooltip.update_text(CAPTURE_TOOLTIPS["stop_capture"])
            self.log_message("INFO", "Capture started")

            # Disable config inputs during capture
            self.set_config_inputs_state(tk.DISABLED)

            # Start status update timer
            self.update_status()

        except Exception as e:
            self.log_message("ERROR", f"Failed to start capture: {e}")
            messagebox.showerror("Error", f"Failed to start capture: {e}")

    def stop_capture(self):
        """Stop the capture process"""
        if self.capture_engine:
            self.capture_engine.stop_capture()
            self.capture_engine = None

        self.is_capturing = False
        self.start_stop_btn.configure(text="Start Capture")
        self.start_stop_tooltip.update_text(CAPTURE_TOOLTIPS["start_capture"])
        self.log_message("INFO", "Capture stopped")

        # Re-enable config inputs
        self.set_config_inputs_state(tk.NORMAL)

        # Update status one last time
        self.update_status()

    def set_config_inputs_state(self, state):
        """Enable or disable configuration inputs"""
        inputs = [
            self.ip_entry, self.username_entry, self.password_entry,
            self.stream_path_entry, self.start_time_entry, self.end_time_entry,
            self.interval_entry, self.output_entry, self.jpeg_quality_entry,
            self.proactive_reconnect_entry
        ]
        for widget in inputs:
            widget.configure(state=state)

    def on_status_update(self, state: CaptureState, stats: dict):
        """Callback for status updates from capture engine"""
        # Schedule UI update on main thread
        self.root.after(0, lambda: self.update_status_from_engine(state, stats))

    def on_frame_captured(self, frame):
        """Callback for frame capture"""
        # Update statistics
        self.total_captures += 1

        # Update last capture time and statistics on main thread
        def update_ui():
            self.last_capture_label.configure(text=datetime.now().strftime("%H:%M:%S"))
            self.update_statistics()

            # Update preview if enabled
            if self.preview_enabled.get() and frame is not None:
                self.update_preview(frame)

        self.root.after(0, update_ui)

    def on_log_message(self, level: str, message: str):
        """Callback for log messages from capture engine"""
        # Schedule log update on main thread
        self.root.after(0, lambda: self.log_message(level, message))

    def update_status_from_engine(self, state: CaptureState, stats: dict):
        """Update status display from engine stats"""
        # Update state
        state_text = state.value
        state_colors = {
            "Stopped": "gray",
            "Starting": "orange",
            "Running": "green",
            "Paused": "blue",
            "Error": "red"
        }
        self.state_label.configure(
            text=state_text,
            foreground=state_colors.get(state_text, "gray")
        )

        # Update indicator
        indicator_colors = {
            "Stopped": "gray",
            "Starting": "orange",
            "Running": "green",
            "Paused": "blue",
            "Error": "red"
        }
        self.status_indicator.itemconfig(
            self.indicator_circle,
            fill=indicator_colors.get(state_text, "gray")
        )
        self.status_indicator.itemconfig(self.indicator_text, text=state_text)

        # Update connection status
        if state == CaptureState.RUNNING:
            self.connection_label.configure(text="Connected", foreground="green")
        elif state == CaptureState.ERROR:
            self.connection_label.configure(text="Error", foreground="red")
        elif state == CaptureState.STARTING:
            self.connection_label.configure(text="Connecting...", foreground="orange")
        else:
            self.connection_label.configure(text="Disconnected", foreground="red")

        # Handle automatic stop when capture ends naturally (reached end time or error)
        if (state == CaptureState.STOPPED or state == CaptureState.ERROR) and self.is_capturing:
            # Clean up GUI state
            self.is_capturing = False
            self.start_stop_btn.configure(text="Start Capture")
            self.start_stop_tooltip.update_text(CAPTURE_TOOLTIPS["start_capture"])
            # Re-enable config inputs
            self.set_config_inputs_state(tk.NORMAL)

        # Update stats
        self.frames_label.configure(text=str(stats.get('frame_count', 0)))

        uptime_seconds = stats.get('uptime_seconds', 0)
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)
        self.uptime_label.configure(text=f"{hours}:{minutes:02d}:{seconds:02d}")

    def update_status(self):
        """Periodic status update"""
        if self.is_capturing and self.capture_engine:
            stats = self.capture_engine.get_stats()
            state = self.capture_engine.state
            self.update_status_from_engine(state, stats)
            self.update_statistics()

        # Schedule next update
        if self.is_capturing:
            self.root.after(1000, self.update_status)

    def toggle_preview(self):
        """Toggle preview on/off"""
        if not self.preview_enabled.get():
            # Clear preview
            self.preview_canvas.delete("preview_image")
            if self.preview_placeholder:
                self.preview_canvas.itemconfig(self.preview_placeholder, state="normal")

    def on_canvas_resize(self, event=None):
        """Handle canvas resize - update preview to fit"""
        # Re-render current preview if available
        if self.current_preview_image is not None:
            self.update_preview(self.current_preview_image)

        # Update placeholder position to center
        if self.preview_placeholder:
            canvas_w = self.preview_canvas.winfo_width()
            canvas_h = self.preview_canvas.winfo_height()
            self.preview_canvas.coords(self.preview_placeholder, canvas_w // 2, canvas_h // 2)

    def update_preview(self, frame):
        """Update the preview canvas with new frame - auto-scales to fill canvas"""
        try:
            # Store original frame
            self.current_preview_image = frame

            # Convert BGR to RGB
            frame_rgb = frame[:, :, ::-1].copy()

            # Get canvas size
            canvas_w = self.preview_canvas.winfo_width()
            canvas_h = self.preview_canvas.winfo_height()

            # Skip if canvas not yet sized
            if canvas_w <= 1 or canvas_h <= 1:
                return

            # Calculate scaling to fit canvas while maintaining aspect ratio
            h, w = frame_rgb.shape[:2]
            scale = min(canvas_w / w, canvas_h / h)
            new_w, new_h = int(w * scale), int(h * scale)

            # Resize frame
            pil_image = Image.fromarray(frame_rgb)
            pil_image = pil_image.resize((new_w, new_h), Image.LANCZOS)

            # Convert to PhotoImage
            self.preview_photo = ImageTk.PhotoImage(pil_image)

            # Update canvas - delete old image first
            self.preview_canvas.delete("preview_image")

            # Center the image
            x = canvas_w // 2
            y = canvas_h // 2

            self.preview_canvas.create_image(x, y, image=self.preview_photo, tags="preview_image")

            # Hide placeholder
            if self.preview_placeholder:
                self.preview_canvas.itemconfig(self.preview_placeholder, state="hidden")

        except Exception as e:
            self.log_message("WARNING", f"Preview update failed: {e}")

    def update_statistics(self):
        """Update statistics display"""
        # Get failed count from capture engine if available
        failed_count = 0
        if self.capture_engine:
            stats = self.capture_engine.get_stats()
            failed_count = stats.get('failed_frame_count', 0)
        else:
            failed_count = self.failed_captures

        # Total attempts = successful + failed
        total_attempts = self.total_captures + failed_count

        # Total captures (successful only)
        self.total_captures_label.configure(text=str(self.total_captures))

        # Success rate based on total attempts
        if total_attempts > 0:
            success_rate = (self.total_captures / total_attempts) * 100
            self.success_rate_label.configure(text=f"{success_rate:.1f}%")
        else:
            self.success_rate_label.configure(text="100%")

        # Session duration
        if self.session_start_time:
            duration = (datetime.now() - self.session_start_time).total_seconds()
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            self.session_duration_label.configure(text=f"{hours}:{minutes:02d}:{seconds:02d}")

        # Average interval
        if self.total_captures > 1 and self.session_start_time:
            duration = (datetime.now() - self.session_start_time).total_seconds()
            avg_interval = duration / (self.total_captures - 1)
            self.avg_interval_label.configure(text=f"{avg_interval:.1f}s")

    def _auto_create_video_for_date(self, date_str: str):
        """
        Automatically create a timelapse video for a specific date's captures.

        Args:
            date_str: Date string in YYYYMMDD format
        """
        self.log_message("INFO", f"[Auto Video] Starting video creation for {date_str}")

        try:
            # Get the snapshots folder for this date
            output_folder = Path(self.config_manager.capture.output_folder)
            date_folder = output_folder / date_str

            if not date_folder.exists():
                self.log_message("ERROR", f"[Auto Video] Folder not found: {date_folder}")
                return

            # Get video settings from Video Export tab
            preset_name = self.video_export_panel.preset_var.get()
            if not preset_name:
                preset_name = "Standard 24fps"  # Default fallback

            # Get output folder from Video Export tab's output file path
            video_output_path = self.video_export_panel.output_file_entry.get()
            if video_output_path:
                video_output_folder = str(Path(video_output_path).parent)
            else:
                video_output_folder = "videos"  # Default fallback

            # Initialize preset manager and get preset
            preset_manager = PresetManager()
            settings = preset_manager.get_preset(preset_name)
            if not settings:
                self.log_message("ERROR", f"[Auto Video] Preset not found: {preset_name}")
                return

            # Don't open video automatically when creating via scheduler
            settings.open_when_done = False

            # Create video export controller
            controller = VideoExportController()

            # Check FFmpeg
            ffmpeg_ok, ffmpeg_msg = controller.check_ffmpeg()
            if not ffmpeg_ok:
                self.log_message("ERROR", f"[Auto Video] {ffmpeg_msg}")
                return

            # Scan folder for images
            success, collection, msg = controller.scan_folder(date_folder)
            if not success:
                self.log_message("ERROR", f"[Auto Video] {msg}")
                return

            self.log_message("INFO", f"[Auto Video] Found {collection.total_count} images")

            # Prepare output path
            output_path = Path(video_output_folder)
            if not output_path.is_absolute():
                output_path = Path.cwd() / output_path
            output_path.mkdir(parents=True, exist_ok=True)

            output_file = output_path / f"timelapse_{date_str}.{settings.format}"

            # Prepare and run export
            success, job, msg = controller.prepare_export(settings, collection, output_file)
            if not success:
                self.log_message("ERROR", f"[Auto Video] {msg}")
                return

            # Progress callback for logging
            def progress_callback(status: str, progress: float, info):
                if progress > 0:
                    self.log_message("INFO", f"[Auto Video] {status}: {progress:.0f}%")

            # Check if we should delete snapshots after video creation
            delete_snapshots = self.config_manager.astro_schedule.delete_snapshots_after_video

            # Run export (this runs in current thread, called via after() so it's safe)
            def run_export():
                result = controller.export_video(
                    job,
                    progress_callback=progress_callback,
                    log_callback=lambda msg: self.log_message("INFO", f"[Auto Video] {msg}")
                )

                if result.success:
                    self.log_message("INFO", f"[Auto Video] Video created: {result.output_file}")

                    # Delete snapshot folder if enabled
                    if delete_snapshots:
                        try:
                            import shutil
                            self.log_message("INFO", f"[Auto Video] Deleting snapshot folder: {date_folder}")
                            shutil.rmtree(date_folder)
                            self.log_message("INFO", f"[Auto Video] Snapshot folder deleted successfully")
                        except Exception as e:
                            self.log_message("ERROR", f"[Auto Video] Failed to delete snapshot folder: {e}")
                else:
                    self.log_message("ERROR", f"[Auto Video] Export failed: {result.message}")

            # Run in a thread to avoid blocking UI
            threading.Thread(target=run_export, daemon=True).start()

        except Exception as e:
            self.log_message("ERROR", f"[Auto Video] Failed: {e}")

    def on_closing(self):
        """Handle window close event"""
        # Clean up scheduler
        if hasattr(self, 'scheduling_panel'):
            self.scheduling_panel.cleanup()

        # Save UI preferences
        self.config_manager.ui.preview_enabled = self.preview_enabled.get()
        self.config_manager.save_to_file("camera_config.json")

        if self.is_capturing:
            if messagebox.askokcancel("Quit", "Capture is running. Stop and quit?"):
                self.stop_capture()
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    """Main entry point"""
    root = tk.Tk()
    app = RTSPTimelapseGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
