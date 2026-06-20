"""
RTSP Timelapse Capture System - GUI Application
Phase 3.5: Video Export Feature Added

A Tkinter-based GUI for managing RTSP camera timelapse captures with live preview
and video export capabilities.
"""

import os
import sys
import json
import mimetypes
import uuid
import urllib.request
import urllib.error
import subprocess
import shutil
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageTk
import numpy as np


def get_app_base_dir() -> Path:
    """Get the application's base directory (where exe or main script is located)."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - use exe's directory
        return Path(sys.executable).parent
    else:
        # Running from source - use src's parent directory
        return Path(__file__).parent.parent


def get_config_path() -> Path:
    """Get the path to the config file."""
    return get_app_base_dir() / "config" / "app_config.json"


def get_resource_path(relative: str) -> Path:
    """Resolve a bundled resource (e.g. assets/icon.ico).

    PyInstaller one-file builds extract bundled data to a temp dir exposed as
    ``sys._MEIPASS`` (not the exe's folder), so check that first. From source,
    resolve relative to the repo root (src's parent).
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return Path(__file__).parent.parent / relative


def get_app_icon_path() -> Path:
    """Path to the application icon (.ico)."""
    return get_resource_path("assets/icon.ico")

from config_manager import ConfigManager
from capture_engine import CaptureEngine, CaptureState
from video_export_panel import VideoExportPanel
from scheduling_panel import SchedulingPanel
from integrations_panel import IntegrationsPanel
from video_export_controller import VideoExportController
from preset_manager import PresetManager
from tooltip import ToolTip
from capture_tooltips import CAPTURE_TOOLTIPS
from capture_history import get_capture_history
import startup_manager

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
        self._set_window_icon()

        # Configuration and engine
        self.config_manager = ConfigManager()
        self.capture_engine = None
        self.is_capturing = False
        self.tray_icon = None
        self.pystray = None
        self._pystray_available = None

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

        # Setup tray icon and optionally start minimized
        self.setup_system_tray()
        if self.config_manager.ui.minimize_to_tray:
            self.root.after(100, self.hide_window_to_tray)

        # When "Minimize to tray" is enabled, the native minimize button hides
        # the window to the tray instead of the taskbar.
        self.root.bind("<Unmap>", self._on_minimize)

        # If "Start with Windows" is on, ensure its registry entry points at this
        # exe — self-heals after an upgrade/move so auto-start keeps working.
        try:
            if startup_manager.sync():
                self.log_message("INFO", "Updated 'Start with Windows' to the current app location.")
        except Exception:
            pass

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

        # Tab 4: Integrations (Discord upload + application/startup options)
        self.integrations_panel = IntegrationsPanel(
            self.notebook,
            config_manager=self.config_manager
        )
        self.notebook.add(self.integrations_panel, text="  Integrations  ")

        # Bind tab change event for auto-save
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Set up scheduling panel callbacks
        self.scheduling_panel.set_callbacks(
            start_capture=self.start_capture,
            stop_capture=self.stop_capture,
            create_video=self._auto_create_video_for_date,
            log=self.log_message
        )

        # Restore scheduler enabled state from last session (must be after set_callbacks)
        self.scheduling_panel.restore_scheduler_state()

        # Route Integrations-tab messages (e.g. start-with-Windows) to the main log
        self.integrations_panel.set_log_callback(self.log_message)

        # Set up video export panel callback to get current snapshots dir from Capture tab
        self.video_export_panel.set_snapshots_dir_callback(
            lambda: self.output_entry.get()
        )

    def _encode_multipart_formdata(self, fields):
        """Encode a multipart/form-data request body.

        Each field is a ``(name, value)`` pair. A simple field's value is
        bytes/str; a file field's value is a ``(filename, content, content_type)``
        tuple. Branch on the value type — both pairs are length 2, so a length
        check cannot tell them apart.
        """
        boundary = uuid.uuid4().hex
        body = bytearray()

        for name, value in fields:
            if isinstance(value, tuple):
                filename, content, content_type = value
                content_bytes = content if isinstance(content, (bytes, bytearray)) else content.encode('utf-8')
                body.extend(f"--{boundary}\r\n".encode('utf-8'))
                body.extend(
                    f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
                    .encode('utf-8')
                )
                body.extend(f"Content-Type: {content_type}\r\n\r\n".encode('utf-8'))
                body.extend(content_bytes)
                body.extend(b"\r\n")
            else:
                value_bytes = value if isinstance(value, (bytes, bytearray)) else str(value).encode('utf-8')
                body.extend(f"--{boundary}\r\n".encode('utf-8'))
                body.extend(f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode('utf-8'))
                body.extend(value_bytes)
                body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode('utf-8'))
        content_type = f"multipart/form-data; boundary={boundary}"
        return bytes(body), content_type

    def _reencode_for_discord(self, output_file: Path, max_size_mb: int) -> Path:
        """
        Re-encode video with progressively lower quality if it exceeds Discord size limit.
        Uses FFmpeg directly with quality degradation sequence.
        
        Args:
            output_file: Original video file path
            max_size_mb: Maximum allowed size in MB
        
        Returns:
            Path to Discord-compatible video (original or re-encoded)
        """
        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        if file_size_mb <= max_size_mb:
            return output_file  # Already under limit

        self.log_message(
            "INFO",
            f"[Discord] Video {file_size_mb:.1f} MB exceeds limit {max_size_mb} MB. Re-encoding..."
        )

        try:
            discord_folder = None
            from ffmpeg_wrapper import FFmpegWrapper

            ffmpeg_wrapper = FFmpegWrapper()
            ffmpeg_path = ffmpeg_wrapper.ffmpeg_path
            
            if not ffmpeg_path:
                raise RuntimeError("FFmpeg not found")

            discord_folder = output_file.parent / ".discord_encode"
            discord_folder.mkdir(parents=True, exist_ok=True)

            # Get Discord settings
            discord_res = self.config_manager.astro_schedule.discord_export_resolution
            resolution_map = {
                "720p": "1280:720",
                "480p": "854:480",
                "360p": "640:360",
                "original": None
            }
            target_scale = resolution_map.get(discord_res)

            # Quality degradation sequence (CRF values: lower = better quality, larger file)
            quality_sequence = [20, 25, 28, 32, 35, 40, 45]

            for crf in quality_sequence:
                discord_file = discord_folder / f"discord_crf{crf}.mp4"
                
                self.log_message(
                    "INFO",
                    f"[Discord] Attempting encode: CRF {crf} {target_scale or 'original resolution'}..."
                )

                # Build FFmpeg command for re-encoding
                cmd = [ffmpeg_path, "-i", str(output_file), "-c:v", "libx264", "-preset", "fast"]
                cmd.extend(["-crf", str(crf)])
                
                # Add resolution scaling if needed
                if target_scale:
                    cmd.extend(["-vf", f"scale={target_scale}"])
                
                cmd.extend(["-c:a", "aac", "-y", str(discord_file)])

                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minute timeout per encoding attempt
                    )

                    if result.returncode != 0:
                        self.log_message(
                            "WARNING",
                            f"[Discord] CRF {crf} encode failed. Trying next quality..."
                        )
                        try:
                            discord_file.unlink(missing_ok=True)
                        except Exception:
                            pass
                        continue

                except subprocess.TimeoutExpired:
                    self.log_message(
                        "WARNING",
                        f"[Discord] CRF {crf} encode timed out. Trying next quality..."
                    )
                    try:
                        discord_file.unlink(missing_ok=True)
                    except Exception:
                        pass
                    continue

                # Check resulting file size
                new_size_mb = discord_file.stat().st_size / (1024 * 1024)
                self.log_message(
                    "INFO",
                    f"[Discord] CRF {crf} result: {new_size_mb:.1f} MB (limit: {max_size_mb} MB)"
                )

                if new_size_mb <= max_size_mb:
                    self.log_message(
                        "INFO",
                        f"[Discord] Re-encoded successfully. Using quality level CRF {crf}"
                    )
                    return discord_file

                # Still too large — drop this copy before trying the next quality step,
                # so oversized encodes don't pile up in .discord_encode/ during the loop.
                try:
                    discord_file.unlink(missing_ok=True)
                except Exception:
                    pass

            # All qualities failed or still too large
            self.log_message(
                "WARNING",
                f"[Discord] Could not reduce video below {max_size_mb} MB. Upload will be skipped."
            )
            
            # Cleanup temp folder
            try:
                shutil.rmtree(discord_folder)
            except Exception:
                pass
            
            return output_file

        except Exception as e:
            self.log_message(
                "ERROR",
                f"[Discord] Re-encoding failed: {str(e)}. Using original file."
            )
            if discord_folder is not None and discord_folder.exists():
                shutil.rmtree(discord_folder, ignore_errors=True)
            return output_file

    def _send_discord_webhook(self, output_file: Path, date_str: str) -> bool:
        """Send the generated video file to a Discord webhook."""
        webhook_url = self.config_manager.astro_schedule.discord_webhook_url.strip()
        if not webhook_url:
            return False

        max_size_mb = self.config_manager.astro_schedule.discord_max_video_size_mb
        if max_size_mb <= 0:
            max_size_mb = 8

        if not output_file.exists():
            self.log_message("ERROR", f"Discord upload failed: video file not found: {output_file}")
            return False

        # Check if auto quality reduction is enabled
        auto_quality_reduce = self.config_manager.astro_schedule.discord_auto_quality_reduction
        file_size_mb = output_file.stat().st_size / (1024 * 1024)

        # The file we actually upload may be a re-encoded temp copy living in a
        # ".discord_encode" scratch folder. Track it so we can always clean up.
        upload_file = output_file
        temp_dir = None

        try:
            # If file is too large and auto-reduce is enabled, try re-encoding
            if auto_quality_reduce and file_size_mb > max_size_mb:
                upload_file = self._reencode_for_discord(output_file, max_size_mb)
                if upload_file != output_file:
                    temp_dir = upload_file.parent
                file_size_mb = upload_file.stat().st_size / (1024 * 1024)

            if file_size_mb > max_size_mb:
                self.log_message(
                    "WARNING",
                    f"Discord upload skipped: {upload_file.name} is {file_size_mb:.1f} MB, exceeds limit {max_size_mb} MB"
                )
                return False

            self.log_message("INFO", f"Uploading video to Discord ({file_size_mb:.1f} MB)...")

            mime_type, _ = mimetypes.guess_type(str(upload_file))
            if not mime_type:
                mime_type = "application/octet-stream"

            with upload_file.open('rb') as f:
                file_bytes = f.read()

            payload = json.dumps({
                "content": f"Timelapse video completed for {date_str}",
                "username": "RTSP Timelapse Bot"
            }).encode('utf-8')

            fields = [
                ("payload_json", ("payload.json", payload, "application/json")),
                ("file", (upload_file.name, file_bytes, mime_type))
            ]
            body, content_type = self._encode_multipart_formdata(fields)

            request = urllib.request.Request(webhook_url, data=body, method="POST")
            request.add_header("Content-Type", content_type)
            request.add_header("User-Agent", "RTSP-Timelapse-Capture")

            with urllib.request.urlopen(request, timeout=60) as response:
                # urlopen raises HTTPError for any non-2xx response (handled by the
                # except below), so reaching here means the upload succeeded.
                self.log_message("INFO", "Discord upload successful")
                # Optionally keep the re-encoded copy that was just uploaded, as a
                # date-stamped file inside .discord_encode (the finally below then
                # only clears the scratch attempts, not this kept copy).
                if (self.config_manager.astro_schedule.discord_keep_reencoded
                        and temp_dir is not None and upload_file != output_file):
                    try:
                        kept = temp_dir / output_file.name
                        upload_file.replace(kept)
                        self.log_message("INFO", f"Kept Discord copy: {kept}")
                    except Exception as e:
                        self.log_message("WARNING", f"Could not keep Discord copy: {e}")
                return True

        except urllib.error.HTTPError as e:
            self.log_message("ERROR", f"Discord upload failed: HTTP {e.code} {e.reason}")
        except urllib.error.URLError as e:
            self.log_message("ERROR", f"Discord upload failed: {e.reason}")
        except Exception as e:
            self.log_message("ERROR", f"Discord upload error: {e}")
        finally:
            # Clean up the re-encode scratch folder: always drop the scratch attempts,
            # then remove the folder only if it is now empty. This preserves any kept
            # date-stamped copies (even if "keep re-encoded" was turned off afterwards)
            # while never leaving stray temp files behind.
            if temp_dir is not None and temp_dir.name == ".discord_encode" and temp_dir.exists():
                try:
                    for f in temp_dir.glob("discord_crf*.mp4"):
                        f.unlink(missing_ok=True)
                    if not any(temp_dir.iterdir()):
                        temp_dir.rmdir()
                except Exception:
                    pass

        return False

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
        self.output_entry.insert(0, self._resolve_output_path(self.config_manager.capture.output_folder))
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
        self.root.bind('<Control-t>', lambda e: self.test_connection())
        self.root.bind('<space>', lambda e: self.toggle_capture() if not self.is_capturing else None)
        self.root.bind('<Escape>', lambda e: self.stop_capture() if self.is_capturing else None)

    def _set_window_icon(self):
        """Set the window/taskbar icon from the bundled .ico (best-effort)."""
        try:
            icon_path = get_app_icon_path()
            if icon_path.exists():
                self.root.iconbitmap(default=str(icon_path))
        except Exception:
            pass

    def _load_pystray(self):
        if self._pystray_available is False:
            return
        if self.pystray is not None:
            return

        try:
            import importlib
            self.pystray = importlib.import_module("pystray")
            self._pystray_available = True
        except Exception as e:
            self.pystray = None
            self._pystray_available = False
            self.log_message("WARNING", f"System tray support unavailable: {e}")

    def _create_tray_image(self):
        # Prefer the real application icon so the tray matches the window/taskbar.
        try:
            icon_path = get_app_icon_path()
            if icon_path.exists():
                with Image.open(str(icon_path)) as im:
                    return im.convert("RGBA")
        except Exception as e:
            self.log_message("WARNING", f"Could not load tray icon, using fallback: {e}")

        # Fallback: a simple generated "RT" badge.
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((4, 4, size - 4, size - 4), fill=(30, 120, 215, 255))

        try:
            font = ImageFont.load_default()
            text = "RT"
            # Center via the "mm" anchor (Pillow >= 8). ImageDraw.textsize was
            # removed in Pillow 10, which requirements.txt pins, so measuring
            # with it would raise and silently skip the label.
            draw.text(
                (size / 2, size / 2),
                text,
                fill="white",
                font=font,
                anchor="mm"
            )
        except Exception:
            pass

        return image

    def setup_system_tray(self):
        """Initialize the system tray icon if tray support is enabled."""
        if not self.config_manager.ui.minimize_to_tray:
            return
        if self.tray_icon is not None:
            return

        self._load_pystray()
        if not self.pystray:
            return

        icon_image = self._create_tray_image()
        menu = self.pystray.Menu(
            self.pystray.MenuItem("Open", self._on_tray_open, default=True),
            self.pystray.MenuItem("Quit", self._on_tray_quit)
        )

        try:
            self.tray_icon = self.pystray.Icon(
                "RTSP Timelapse Capture",
                icon_image,
                "RTSP Timelapse Capture",
                menu=menu
            )
            self.tray_icon.run_detached(lambda icon: setattr(icon, 'visible', True))
        except Exception as e:
            self.log_message("WARNING", f"Could not start tray icon: {e}")
            self.tray_icon = None

    def hide_window_to_tray(self):
        """Minimize the application to the system tray."""
        self.setup_system_tray()
        if not self.tray_icon:
            self.log_message(
                "WARNING",
                "Tray icon unavailable; cannot start minimized to system tray."
            )
            return

        try:
            self.tray_icon.visible = True
        except Exception:
            pass

        self.root.withdraw()
        self.log_message("INFO", "Application started minimized to system tray.")

    def restore_from_tray(self, icon=None, item=None):
        """Restore the application window from the tray."""
        if self.root.state() == 'withdrawn':
            self.root.deiconify()

        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.attributes('-topmost', False)
        self.root.focus_force()

    def _on_minimize(self, event):
        """Divert the native minimize to the tray when 'Minimize to tray' is on."""
        if (event.widget is self.root
                and self.root.state() == 'iconic'
                and self.config_manager.ui.minimize_to_tray):
            self.hide_window_to_tray()

    def _on_tray_open(self, icon, item):
        self.root.after(0, self.restore_from_tray)

    def _on_tray_quit(self, icon, item):
        self.root.after(0, self.on_closing)

    def cleanup_tray(self):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None

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
        # Get current path and create if it doesn't exist
        current_path = self.output_entry.get()
        if current_path:
            path = Path(current_path)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass  # If creation fails, dialog will use default
        directory = filedialog.askdirectory(initialdir=current_path)
        if directory:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, directory)

    def _resolve_output_path(self, path_str: str) -> str:
        """Resolve output path - if relative, resolve from app base directory."""
        path = Path(path_str)
        if path.is_absolute():
            return str(path)
        else:
            return str((get_app_base_dir() / path).resolve())

    def _make_path_relative(self, path_str: str) -> str:
        """Convert absolute path to relative if it's within app base directory."""
        path = Path(path_str)
        if not path.is_absolute():
            return path_str  # Already relative

        base_dir = get_app_base_dir()
        try:
            # Check if path is within base directory
            rel_path = path.relative_to(base_dir)
            return str(rel_path)
        except ValueError:
            # Path is not within base directory, keep absolute
            return path_str

    def load_config(self):
        """Load configuration from default file"""
        config_file = get_config_path()
        if config_file.exists():
            success, message = self.config_manager.load_from_file(str(config_file))
            if not success:
                # Try migrating from old config.py
                self.config_manager.migrate_from_old_config()
        else:
            # Try migrating from old config.py
            self.config_manager.migrate_from_old_config()

    def save_config(self):
        """Auto-save configuration to default file"""
        self.update_config_from_ui()
        config_file = get_config_path()
        # Ensure config directory exists
        config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_manager.save_to_file(str(config_file))

    def _on_tab_changed(self, event=None):
        """Auto-save when switching tabs"""
        self.save_config()

    def update_config_from_ui(self, skip_schedule_times: bool = False):
        """Update ConfigManager from UI inputs

        Args:
            skip_schedule_times: If True, don't update schedule times (used when
                               astronomical scheduler has already set the times)
        """
        self.config_manager.camera.ip_address = self.ip_entry.get()
        self.config_manager.camera.username = self.username_entry.get()
        self.config_manager.camera.password = self.password_entry.get()
        self.config_manager.camera.stream_path = self.stream_path_entry.get()
        self.config_manager.camera.force_tcp = self.force_tcp_var.get()

        if not skip_schedule_times:
            self.config_manager.schedule.start_time = self.start_time_entry.get()
            self.config_manager.schedule.end_time = self.end_time_entry.get()

        self.config_manager.capture.interval_seconds = int(self.interval_entry.get())
        # Save the full path as shown in UI
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
        self.output_entry.insert(0, self._resolve_output_path(self.config_manager.capture.output_folder))

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

    def start_capture(self, from_scheduler: bool = False):
        """Start the capture process

        Args:
            from_scheduler: If True, called from astronomical scheduler (don't override schedule times)
        """
        # Update config from UI (skip schedule times if from scheduler)
        self.update_config_from_ui(skip_schedule_times=from_scheduler)

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

                    # Upload to Discord if webhook is configured
                    try:
                        if self._send_discord_webhook(result.output_file, date_str):
                            self.log_message("INFO", "[Auto Video] Discord upload completed")

                            # Optionally delete the generated video after successful Discord upload
                            try:
                                if self.config_manager.astro_schedule.delete_video_after_discord_upload:
                                    result.output_file.unlink()
                                    self.log_message("INFO", f"[Auto Video] Deleted video after Discord upload: {result.output_file}")
                            except Exception as e:
                                self.log_message("WARNING", f"[Auto Video] Failed to delete video file: {e}")
                    except Exception as e:
                        self.log_message("ERROR", f"[Auto Video] Discord upload failed: {e}")

                    # Update capture history to mark video as created
                    try:
                        capture_history = get_capture_history()
                        capture_history.update_video_created(date_str, True)
                    except Exception as e:
                        self.log_message("WARNING", f"[Auto Video] Could not update capture history: {e}")

                    # Delete snapshot folder if enabled
                    if delete_snapshots:
                        try:
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
        # Confirm first when capturing; only tear down once the user commits to
        # quitting, so Cancel leaves the window, tray icon, and scheduler intact.
        if self.is_capturing:
            if not messagebox.askokcancel("Quit", "Capture is running. Stop and quit?"):
                return
            self.stop_capture()

        # Clean up scheduler and auto-save all settings before closing.
        if hasattr(self, 'scheduling_panel'):
            self.scheduling_panel.cleanup()
        self.save_config()
        self.cleanup_tray()
        self.root.destroy()


def main():
    """Main entry point"""
    root = tk.Tk()
    app = RTSPTimelapseGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
