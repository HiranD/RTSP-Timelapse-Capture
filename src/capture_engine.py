"""
RTSP Capture Engine - Thread-safe capture logic for GUI integration

This module provides a class-based, thread-safe implementation of the RTSP
capture functionality. It runs in a background thread and communicates with
the GUI through callbacks.
"""

import os
import time
import threading
from datetime import datetime, timedelta, time as dtime
from enum import Enum
from typing import Callable, Optional
import queue

import cv2
import numpy as np


class CaptureState(Enum):
    """Enumeration of possible capture states"""
    STOPPED = "Stopped"
    STARTING = "Starting..."
    RUNNING = "Running"
    STOPPING = "Stopping..."
    ERROR = "Error"


class CaptureEngine:
    """
    Thread-safe RTSP capture engine.

    Manages persistent RTSP connection, periodic snapshots, and provides
    callbacks for status updates and frame delivery to the GUI.
    """

    def __init__(self, config: dict):
        """
        Initialize the capture engine.

        Args:
            config: Configuration dictionary with camera, schedule, and capture settings
        """
        self.config = config
        self.state = CaptureState.STOPPED
        self.capture_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.cap: Optional[cv2.VideoCapture] = None

        # Callbacks
        self.status_callback: Optional[Callable] = None
        self.frame_callback: Optional[Callable] = None
        self.log_callback: Optional[Callable] = None

        # Statistics
        self.frame_count = 0
        self.failed_frame_count = 0
        self.session_start_time: Optional[datetime] = None
        self.last_error: Optional[str] = None

        # Connection stability tracking
        self.disconnect_count = 0
        self.last_disconnect_time: Optional[datetime] = None
        self.connection_start_time: Optional[datetime] = None

    def set_status_callback(self, callback: Callable[[CaptureState, dict], None]):
        """
        Set callback for status updates.

        Args:
            callback: Function(state, stats_dict) called on status changes
        """
        self.status_callback = callback

    def set_frame_callback(self, callback: Callable[[np.ndarray], None]):
        """
        Set callback for frame delivery (for preview).

        Args:
            callback: Function(frame) called with each captured frame
        """
        self.frame_callback = callback

    def set_log_callback(self, callback: Callable[[str, str], None]):
        """
        Set callback for log messages.

        Args:
            callback: Function(level, message) called for logging
                     level: "INFO", "WARNING", "ERROR"
        """
        self.log_callback = callback

    def start_capture(self) -> bool:
        """
        Start the capture process in a background thread.

        Returns:
            True if started successfully, False otherwise
        """
        if self.state != CaptureState.STOPPED:
            self._log("WARNING", "Capture already running or starting")
            return False

        self.stop_event.clear()
        self.frame_count = 0
        self.failed_frame_count = 0
        self.session_start_time = datetime.now()
        self.last_error = None

        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()

        return True

    def stop_capture(self):
        """Stop the capture process gracefully."""
        if self.state == CaptureState.STOPPED:
            return

        self._update_state(CaptureState.STOPPING)
        self._log("INFO", "Stopping capture...")
        self.stop_event.set()

        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=5.0)

    def test_connection(self) -> tuple[bool, str]:
        """
        Test RTSP connection without starting capture.

        Returns:
            Tuple of (success: bool, message: str)
        """
        url = self._build_rtsp_url()
        self._log("INFO", f"Testing connection to {self._sanitize_url(url)}")

        try:
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                return False, "Failed to open RTSP stream"

            # Try to read a frame
            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                return False, "Connected but failed to read frame"

            return True, f"Connected successfully! Frame size: {frame.shape[1]}x{frame.shape[0]}"

        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def get_stats(self) -> dict:
        """
        Get current capture statistics.

        Returns:
            Dictionary with frame_count, failed_frame_count, uptime, state, etc.
        """
        uptime_seconds = 0
        if self.session_start_time:
            uptime_seconds = int((datetime.now() - self.session_start_time).total_seconds())

        return {
            "state": self.state.value,
            "frame_count": self.frame_count,
            "failed_frame_count": self.failed_frame_count,
            "uptime_seconds": uptime_seconds,
            "last_error": self.last_error
        }

    # -------------------------------------------------------------------------
    # Private methods
    # -------------------------------------------------------------------------

    def _capture_loop(self):
        """Main capture loop running in background thread."""
        try:
            self._update_state(CaptureState.STARTING)
            self._log("INFO", "Initializing capture engine...")

            # Check if we should wait for start time
            if not self._wait_for_start_time():
                self._update_state(CaptureState.STOPPED)
                return

            # Connect to camera
            url = self._build_rtsp_url()
            self.cap = self._open_capture(url)

            if not self.cap:
                self._log("ERROR", "Failed to connect to camera after retries")
                self._update_state(CaptureState.ERROR)
                return

            self.connection_start_time = datetime.now()
            self._log("INFO", "Connected to RTSP stream successfully")
            self._update_state(CaptureState.RUNNING)

            # Calculate end time for overnight schedules
            end_dt = self._calculate_end_time()
            self._log("INFO", f"Capture will run until {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")

            # Main capture loop
            while not self.stop_event.is_set() and datetime.now() < end_dt:
                loop_start = time.time()

                # Check for proactive reconnection to avoid camera timeout
                proactive_reconnect = self.config["capture"].get("proactive_reconnect_seconds", 0)
                if proactive_reconnect > 0 and self.connection_start_time:
                    uptime = (datetime.now() - self.connection_start_time).total_seconds()
                    if uptime >= proactive_reconnect:
                        self._log("INFO", f"Proactive reconnection (connected for {int(uptime)}s, limit: {proactive_reconnect}s)")
                        if not self._reconnect(url):
                            self._update_state(CaptureState.ERROR)
                            break
                        # Don't capture this cycle - reconnection takes time
                        # Sleep for remaining interval and continue to next cycle
                        elapsed = time.time() - loop_start
                        interval = self.config["capture"]["interval_seconds"]
                        remain = interval - elapsed
                        if remain > 0:
                            if self.stop_event.wait(timeout=remain):
                                break
                        continue

                try:
                    frame = self._grab_frame()

                    # Save frame
                    filepath = self._save_frame(frame)
                    self.frame_count += 1
                    self._log("INFO", f"Saved frame {self.frame_count}: {os.path.basename(filepath)}")

                    # Send frame to preview callback
                    if self.frame_callback:
                        self.frame_callback(frame.copy())

                    # Update status
                    self._notify_status()

                except Exception as ex:
                    self._log("ERROR", f"Frame capture error: {ex}")
                    self.last_error = str(ex)
                    self.failed_frame_count += 1

                    # Update status to reflect failed frame
                    self._notify_status()

                    # Try to reconnect
                    if not self._reconnect(url):
                        self._update_state(CaptureState.ERROR)
                        break

                    continue

                # Sleep for the remaining interval time
                elapsed = time.time() - loop_start
                interval = self.config["capture"]["interval_seconds"]
                remain = interval - elapsed

                if remain > 0:
                    # Use stop_event.wait() instead of time.sleep() for responsive stopping
                    if self.stop_event.wait(timeout=remain):
                        break

            # Clean shutdown
            if datetime.now() >= end_dt:
                self._log("INFO", f"Capture completed - reached end time")
            else:
                self._log("INFO", "Capture stopped by user")

            # Log connection stability summary
            if self.disconnect_count > 0:
                total_time = (datetime.now() - self.session_start_time).total_seconds()
                avg_uptime = total_time / (self.disconnect_count + 1) if self.disconnect_count > 0 else total_time
                self._log("INFO", f"Connection summary: {self.disconnect_count} disconnects, avg uptime: {int(avg_uptime)}s between disconnects")

        except Exception as ex:
            self._log("ERROR", f"Capture loop error: {ex}")
            self.last_error = str(ex)
            self._update_state(CaptureState.ERROR)

        finally:
            if self.cap:
                self.cap.release()
                self.cap = None
            self._update_state(CaptureState.STOPPED)

    def _wait_for_start_time(self) -> bool:
        """
        Wait until the configured start time if it hasn't passed yet.
        Properly handles overnight schedules.

        Returns:
            True if we should proceed, False if user stopped during wait
        """
        start_str = self.config["schedule"]["start_time"]
        end_str = self.config["schedule"]["end_time"]

        start_h, start_m = map(int, start_str.split(":"))
        end_h, end_m = map(int, end_str.split(":"))

        now = datetime.now()
        current_time = now.time()
        start_time = dtime(hour=start_h, minute=start_m)
        end_time = dtime(hour=end_h, minute=end_m)

        # Check if this is an overnight schedule
        if end_time < start_time:
            # Overnight schedule (e.g., 22:40 to 07:00)
            if current_time < end_time:
                # We're in the early morning, still within schedule
                self._log("INFO", f"Within overnight schedule window, starting immediately")
                return True
            elif current_time >= start_time:
                # We're in the evening, within schedule
                self._log("INFO", f"Within overnight schedule window, starting immediately")
                return True
            else:
                # We're between end and start (e.g., between 07:00 and 22:40)
                # Wait until start time today
                today_start = datetime.combine(now.date(), start_time)
                wait_seconds = int((today_start - now).total_seconds())
                self._log("INFO", f"Outside schedule window. Waiting {wait_seconds}s until start time {start_str}")
                return not self.stop_event.wait(timeout=wait_seconds)
        else:
            # Same-day schedule (e.g., 08:00 to 18:00)
            today_start = datetime.combine(now.date(), start_time)

            if now < today_start:
                wait_seconds = int((today_start - now).total_seconds())
                self._log("INFO", f"Waiting {wait_seconds}s until start time {start_str}")
                return not self.stop_event.wait(timeout=wait_seconds)
            else:
                self._log("INFO", f"Start time {start_str} already passed, starting immediately")
                return True

    def _build_rtsp_url(self) -> str:
        """Build RTSP URL from configuration with Annke-optimized parameters."""
        camera = self.config["camera"]
        base = f"rtsp://{camera['username']}:{camera['password']}@{camera['ip_address']}/stream1"

        # Force TCP transport for reliability (Annke cameras work better with TCP)
        if camera.get("force_tcp", True):
            base += "?tcp"

        return base

    def _sanitize_url(self, url: str) -> str:
        """Remove password from URL for logging."""
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)

    def _open_capture(self, url: str, retries: int = None) -> Optional[cv2.VideoCapture]:
        """
        Open RTSP stream with retries and optimized settings for Annke cameras.

        Args:
            url: RTSP URL
            retries: Number of retry attempts (from config if None)

        Returns:
            VideoCapture object or None on failure
        """
        if retries is None:
            retries = self.config["capture"]["max_retries"]

        for attempt in range(1, retries + 1):
            if self.stop_event.is_set():
                return None

            self._log("INFO", f"Connection attempt {attempt}/{retries}...")

            # Create capture with FFmpeg backend and optimized options
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

            if cap.isOpened():
                # Configure buffer - smaller buffer for IP cameras to reduce latency
                buffer_frames = self.config["capture"].get("buffer_frames", 1)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, buffer_frames)

                # Set timeout for read operations (milliseconds)
                # This prevents hanging on disconnections
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)  # 10 second timeout
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)  # 10 second read timeout

                # For Annke cameras: Enable FFmpeg options for better stability
                # These are already set in the environment variable approach

                self._log("INFO", f"Connection successful (buffer: {buffer_frames} frames, timeouts: 10s)")
                return cap

            cap.release()

            if attempt < retries:
                self._log("WARNING", f"Connection failed, retrying in 2s...")
                if self.stop_event.wait(timeout=2.0):
                    return None

        return None

    def _reconnect(self, url: str) -> bool:
        """
        Attempt to reconnect to RTSP stream with connection stability tracking.

        Returns:
            True if reconnected, False otherwise
        """
        # Track disconnect event
        now = datetime.now()
        self.disconnect_count += 1

        # Log connection uptime if we know when it started
        uptime_msg = ""
        if self.connection_start_time:
            uptime = (now - self.connection_start_time).total_seconds()
            uptime_msg = f" (was connected for {int(uptime)}s)"

        self._log("WARNING", f"Connection lost{uptime_msg}, attempting to reconnect... (disconnect #{self.disconnect_count})")

        # Track time between disconnects for pattern analysis
        if self.last_disconnect_time:
            time_since_last = (now - self.last_disconnect_time).total_seconds()
            if time_since_last < 60:  # Less than 1 minute between disconnects
                self._log("WARNING", f"Frequent disconnects detected ({int(time_since_last)}s since last)")

        self.last_disconnect_time = now

        # Release old connection
        if self.cap:
            self.cap.release()
            self.cap = None

        # Attempt reconnection with more retries for Annke cameras
        self.cap = self._open_capture(url, retries=3)

        if self.cap is not None:
            self.connection_start_time = datetime.now()
            return True
        else:
            return False

    def _grab_frame(self) -> np.ndarray:
        """
        Read a frame from the capture device.

        Flushes buffered frames first to ensure we get the freshest frame.
        This is critical for timelapse where frames are captured infrequently,
        preventing the issue where old buffered frames are saved instead of current ones.

        Returns:
            Frame as numpy array

        Raises:
            RuntimeError if frame read fails
        """
        if not self.cap or not self.cap.isOpened():
            raise RuntimeError("Capture device not open")

        # Flush buffer by reading and discarding old frames
        # This ensures we get the freshest frame from the camera
        flush_count = self.config["capture"].get("flush_buffer_count", 10)
        if flush_count > 0:
            for i in range(flush_count):
                ret, _ = self.cap.read()
                if not ret:
                    # If we can't flush, that's okay - just continue with what we have
                    break

        # Now read the fresh frame
        ret, frame = self.cap.read()

        if not ret or frame is None:
            raise RuntimeError("Failed to read frame from stream")

        return frame

    def _save_frame(self, frame: np.ndarray) -> str:
        """
        Save frame to disk as JPEG.

        Args:
            frame: Frame to save

        Returns:
            Full path to saved file
        """
        out_dir = self._ensure_date_dir()
        filename = datetime.now().strftime("%Y%m%d-%H%M%S.jpg")
        filepath = os.path.join(out_dir, filename)

        quality = self.config["capture"]["jpeg_quality"]
        cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, quality])

        return filepath

    def _ensure_date_dir(self) -> str:
        """
        Get or create the output directory for current date.

        Between midnight and rollover hour, uses previous day's folder.

        Returns:
            Path to date-specific directory
        """
        base_dir = self.config["capture"]["output_folder"]
        now = datetime.now()
        rollover_hour = self.config["schedule"]["folder_rollover_hour"]

        if now.hour < rollover_hour:
            effective_date = now.date() - timedelta(days=1)
        else:
            effective_date = now.date()

        path = os.path.join(base_dir, effective_date.strftime("%Y%m%d"))
        os.makedirs(path, exist_ok=True)

        return path

    def _calculate_end_time(self) -> datetime:
        """
        Calculate the end time for the current capture session.
        Properly handles overnight schedules (e.g., 22:40 to 07:00).

        Returns:
            Datetime when capture should end
        """
        start_str = self.config["schedule"]["start_time"]
        end_str = self.config["schedule"]["end_time"]

        start_h, start_m = map(int, start_str.split(":"))
        end_h, end_m = map(int, end_str.split(":"))

        now = datetime.now()

        # Create time objects for comparison
        start_time = dtime(hour=start_h, minute=start_m)
        end_time = dtime(hour=end_h, minute=end_m)
        current_time = now.time()

        # Calculate today's end datetime
        today_end = datetime.combine(now.date(), end_time)

        # Check if this is an overnight schedule (end < start)
        if end_time < start_time:
            # Overnight schedule (e.g., 22:40 to 07:00)
            if current_time >= start_time:
                # We're after start time, so end is tomorrow
                return today_end + timedelta(days=1)
            else:
                # We're before start time, so end is today
                return today_end
        else:
            # Same-day schedule (e.g., 08:00 to 18:00)
            if current_time < end_time:
                # End is today
                return today_end
            else:
                # End is tomorrow
                return today_end + timedelta(days=1)

    def _next_occurrence(self, time_str: str) -> datetime:
        """
        Calculate next occurrence of HH:MM time.

        Args:
            time_str: Time in HH:MM format

        Returns:
            Next datetime matching the time
        """
        h, m = map(int, time_str.split(":"))
        now = datetime.now()
        candidate = datetime.combine(now.date(), dtime(hour=h, minute=m))

        if candidate <= now:
            candidate += timedelta(days=1)

        return candidate

    def _update_state(self, new_state: CaptureState):
        """Update state and notify callback."""
        self.state = new_state
        self._notify_status()

    def _notify_status(self):
        """Send status update via callback."""
        if self.status_callback:
            self.status_callback(self.state, self.get_stats())

    def _log(self, level: str, message: str):
        """Send log message via callback."""
        if self.log_callback:
            self.log_callback(level, message)
