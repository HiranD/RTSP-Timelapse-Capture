"""
RTSP Capture Engine - Thread-safe capture logic for GUI integration

This module provides a class-based, thread-safe implementation of the RTSP
capture functionality. It runs in a background thread and communicates with
the GUI through callbacks.
"""

import os
import sys
from pathlib import Path


def get_app_base_dir() -> Path:
    """Get the application's base directory (where exe or main script is located)."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - use exe's directory
        return Path(sys.executable).parent
    else:
        # Running from source - use src's parent directory
        return Path(__file__).parent.parent


def resolve_path(path_str: str) -> Path:
    """Resolve a path - if relative, resolve from app base directory."""
    path = Path(path_str)
    if path.is_absolute():
        return path
    else:
        return (get_app_base_dir() / path).resolve()


# OPTIMIZATION: Configure FFmpeg for low-latency RTSP streaming
# Must be set BEFORE importing cv2 to take effect
# Research: https://stackoverflow.com/questions/16658873/
# See docs/IMPROVEMENT_RECOMMENDATIONS.md for details
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = (
    'rtsp_transport;tcp|'      # Use TCP transport (reliable)
    'fflags;nobuffer|'          # Minimize buffering during stream analysis
    'flags;low_delay'           # Force low-delay codec operation
)

import math
import re
import time
import threading
from datetime import datetime, timedelta, date, time as dtime
from enum import Enum
from typing import Callable, Optional
import queue

import cv2
import numpy as np

try:
    from src.app_logging import get_logger
except ImportError:
    from app_logging import get_logger

# File-log detail channel; near-free while file logging is off (see app_logging).
LOG = get_logger("capture")


def sanitize_url(url: str) -> str:
    """Remove the password from an RTSP URL for logging."""
    return re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)


# Used when the camera's stream path is left blank in the configuration.
DEFAULT_STREAM_PATH = "/stream1"

# Escalating waits between reconnect attempts during an outage; the last value
# repeats. Module-level so tests can patch it down to milliseconds.
_RECONNECT_BACKOFF = (5, 10, 30, 60, 120)

# How long a freshly opened stream may take to deliver its first frame before the
# connection is judged dead. Some rigs (high-latency link + H.265 decoder spin-up)
# take a fixed ~6s from open to first frame - deterministically longer than the 5s
# steady-state read timeout, which made every connect "succeed" and then fail one
# second short of the first frame, forever (2026-08-28). Module-level so tests can
# patch it down.
_FIRST_FRAME_GRACE = 15.0


class RTSPBufferlessCapture:
    """
    Bufferless RTSP capture using background thread.

    Continuously reads frames in a background thread and only keeps the latest one.
    This prevents buffer staleness when frames are captured infrequently (e.g., timelapse).

    Expected improvement: Reduces timestamp drift from ~4 minutes to <1 minute.
    """

    def __init__(self, rtsp_url: str, buffer_size: int = 1):
        """
        Initialize bufferless capture.

        Args:
            rtsp_url: RTSP stream URL
            buffer_size: OpenCV buffer size (default 1)
        """
        self.url = rtsp_url
        LOG.debug("opening %s (buffer=%d)", sanitize_url(rtsp_url), buffer_size)
        opened_at = time.time()
        self.cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        LOG.debug("VideoCapture open took %.1fs, isOpened=%s",
                  time.time() - opened_at, self.cap.isOpened())

        if self.cap.isOpened():
            # Configure buffer
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, buffer_size)
            self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
            self.cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)

        self.q = queue.Queue(maxsize=1)  # Only hold 1 frame at a time
        self.stopped = False
        self.read_error = False
        # Reader-loop logging is transition-based (first frame, error<->ok),
        # never per-frame - the loop runs at stream fps all night.
        self._logged_first_frame = False

        # Start background reader thread
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

    def _reader(self):
        """Background thread: continuously read frames and keep only the latest."""
        while not self.stopped:
            ret, frame = self.cap.read()

            if not ret:
                if not self.read_error and not self.stopped:
                    LOG.debug("reader: cap.read() failed - retrying in background")
                self.read_error = True
                time.sleep(0.1)  # Brief pause before retry
                continue

            if not self._logged_first_frame:
                self._logged_first_frame = True
                LOG.debug("reader: first frame received (%dx%d)",
                          frame.shape[1], frame.shape[0])
            elif self.read_error:
                LOG.debug("reader: stream recovered after read failure(s)")
            self.read_error = False

            # Discard old frame if queue is full, keep only newest
            if not self.q.empty():
                try:
                    self.q.get_nowait()  # Remove stale frame
                except queue.Empty:
                    pass

            self.q.put(frame)  # Add fresh frame
        LOG.debug("reader thread exiting")

    def read(self, timeout: float = 5.0) -> tuple[bool, Optional[np.ndarray]]:
        """
        Get the latest available frame (always fresh).

        Args:
            timeout: seconds to wait for a frame. The 5s default suits steady
                state (the reader keeps the queue topped up); the first-frame
                wait after a connect uses shorter slices so the caller can
                stay stop-responsive between reads.

        Returns:
            Tuple of (success, frame)
        """
        if self.stopped or self.read_error:
            return False, None

        try:
            frame = self.q.get(timeout=timeout)
            return True, frame
        except queue.Empty:
            LOG.debug("read: no frame within %.1fs (read_error=%s)",
                      timeout, self.read_error)
            return False, None

    def isOpened(self) -> bool:
        """Check if capture is open and working."""
        return self.cap.isOpened() and not self.stopped and not self.read_error

    def release(self):
        """Stop capture and clean up."""
        LOG.debug("releasing capture")
        self.stopped = True
        if self.thread.is_alive():
            self.thread.join(timeout=2.0)
            if self.thread.is_alive():
                LOG.debug("release: reader thread still blocked after 2s join "
                          "(daemon - will exit on its own)")
        if self.cap:
            self.cap.release()

    def set(self, prop: int, value: float):
        """Pass-through for cv2.VideoCapture.set()."""
        if self.cap:
            return self.cap.set(prop, value)
        return False

    def get(self, prop: int) -> float:
        """Pass-through for cv2.VideoCapture.get()."""
        if self.cap:
            return self.cap.get(prop)
        return 0.0


class CaptureState(Enum):
    """Enumeration of possible capture states"""
    STOPPED = "Stopped"
    STARTING = "Starting..."
    RUNNING = "Running"
    RECONNECTING = "Reconnecting"
    STOPPING = "Stopping..."
    ERROR = "Error"


def effective_date(dt: datetime, rollover_hour: int) -> date:
    """Folder date for a frame captured at `dt`.

    Before the rollover hour a frame belongs to the previous day, so an
    overnight session stays in one date folder. The single home of the
    folder_rollover_hour rule: ensure_date_dir files frames (and the event
    log) with it, and the session-aware render path uses it to map a
    session's start time back to its starting folder.
    """
    if dt.hour < rollover_hour:
        return dt.date() - timedelta(days=1)
    return dt.date()


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
        self.cap: Optional[RTSPBufferlessCapture] = None

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

        LOG.debug("start_capture: interval=%ss, window=%s-%s, rollover=%s, "
                  "proactive_reconnect=%ss, ignore_window=%s",
                  self.config["capture"]["interval_seconds"],
                  self.config["schedule"]["start_time"],
                  self.config["schedule"]["end_time"],
                  self.config["schedule"]["folder_rollover_hour"],
                  self.config["capture"].get("proactive_reconnect_seconds", 0),
                  bool(self.config["schedule"].get("ignore_window")))
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
            # Time the open and the first read separately: the gap between them
            # is exactly what the capture path's first-frame grace must cover,
            # so a remote user's test result doubles as the diagnostic.
            t0 = time.time()
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            open_seconds = time.time() - t0
            if not cap.isOpened():
                return False, "Failed to open RTSP stream"

            # Try to read a frame
            t1 = time.time()
            ret, frame = cap.read()
            first_frame_seconds = time.time() - t1
            cap.release()

            if not ret or frame is None:
                return False, "Connected but failed to read frame"

            return True, (f"Connected successfully! Frame size: {frame.shape[1]}x{frame.shape[0]} "
                          f"(open {open_seconds:.1f}s, first frame +{first_frame_seconds:.1f}s)")

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

            url = self._build_rtsp_url()

            # End time BEFORE the first connect: a camera that is down at
            # session start is retried until the window ends, not just
            # max_retries times. In remote-control mode there is no schedule
            # end - run until explicitly stopped.
            if self.config["schedule"].get("ignore_window"):
                end_dt = datetime.max
                self._log("INFO", "Capture will run until stopped (remote control)")
            else:
                end_dt = self._calculate_end_time()
                self._log("INFO", f"Capture will run until {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")

            # Initial connect: a quick burst of max_retries attempts, then keep
            # trying with backoff rather than declaring the night lost.
            self.cap = self._open_capture(url)
            if self.cap:
                self.connection_start_time = datetime.now()
                self._log("INFO", "Connected to RTSP stream successfully")
                self._update_state(CaptureState.RUNNING)
            elif not self.stop_event.is_set():
                # No early return: on False the while condition below is already
                # false for both causes (stop, window end) and the normal exit
                # path runs.
                self._reconnect_until(url, end_dt)

            # Main capture loop
            while not self.stop_event.is_set() and datetime.now() < end_dt:
                loop_start = time.time()

                # Proactive reconnection to avoid camera timeout - a planned
                # cycle, not an outage; skips this cycle's frame.
                proactive_reconnect = self.config["capture"].get("proactive_reconnect_seconds", 0)
                if proactive_reconnect > 0 and self.connection_start_time and \
                        (datetime.now() - self.connection_start_time).total_seconds() >= proactive_reconnect:
                    self._log("INFO", f"Scheduled reconnection (interval: {proactive_reconnect}s)")
                    if not self._reconnect(url):
                        # The planned cycle found the camera down - now it IS an
                        # outage. Keep trying until stop or window end.
                        if not self._reconnect_until(url, end_dt):
                            break  # stopped or window end - clean exit, never ERROR
                    # Fall through to the shared interval sleep.
                else:
                    try:
                        frame, stream_timestamp = self._grab_frame()

                        # Save frame with stream timestamp if available
                        filepath = self._save_frame(frame, stream_timestamp)
                        self.frame_count += 1

                        # Log saved frame
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

                        if not self._reconnect_until(url, end_dt):
                            break  # stopped or window end - clean exit, never ERROR

                        continue  # reconnected - grab a frame immediately

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
        # Remote-control (e.g. NINA) drives start/stop itself, so ignore the
        # configured schedule window and begin immediately.
        if self.config["schedule"].get("ignore_window"):
            self._log("INFO", "Remote control: ignoring schedule window, starting immediately")
            return True

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
                # Wait until start time today. Round UP: int() truncation woke
                # the thread a fraction before the start time.
                today_start = datetime.combine(now.date(), start_time)
                wait_seconds = math.ceil((today_start - now).total_seconds())
                self._log("INFO", f"Outside schedule window. Waiting {wait_seconds}s until start time {start_str}")
                return not self.stop_event.wait(timeout=wait_seconds)
        else:
            # Same-day schedule (e.g., 08:00 to 18:00)
            today_start = datetime.combine(now.date(), start_time)

            if now < today_start:
                wait_seconds = math.ceil((today_start - now).total_seconds())
                self._log("INFO", f"Waiting {wait_seconds}s until start time {start_str}")
                return not self.stop_event.wait(timeout=wait_seconds)
            else:
                self._log("INFO", f"Start time {start_str} already passed, starting immediately")
                return True

    def _build_rtsp_url(self) -> str:
        """Build the RTSP URL from configuration.

        The configured stream path is used verbatim (it may contain a query string,
        e.g. Dahua's /cam/realmonitor?channel=1&subtype=0). Transport is pinned to
        TCP process-wide via OPENCV_FFMPEG_CAPTURE_OPTIONS, so nothing is appended
        here - appending would corrupt query-string paths.
        """
        camera = self.config["camera"]

        path = str(camera.get("stream_path") or "").strip()
        if not path:
            path = DEFAULT_STREAM_PATH
        if not path.startswith("/"):
            path = "/" + path

        return (
            f"rtsp://{camera['username']}:{camera['password']}"
            f"@{camera['ip_address']}{path}"
        )

    def _sanitize_url(self, url: str) -> str:
        """Remove password from URL for logging."""
        return sanitize_url(url)

    def _open_capture(self, url: str, retries: int = None,
                      quiet: bool = False) -> Optional[RTSPBufferlessCapture]:
        """
        Open RTSP stream with retries and optimized settings for Annke cameras.
        Uses multi-threaded bufferless capture to minimize timestamp drift.

        Args:
            url: RTSP URL
            retries: Number of retry attempts (from config if None)
            quiet: Suppress per-attempt logging - _reconnect_until calls this
                every backoff cycle and owns the log cadence itself.

        Returns:
            RTSPBufferlessCapture object (opened AND frame-verified) or None on
            failure (or stop requested - callers that need to tell the two apart
            re-check stop_event).
        """
        if retries is None:
            retries = self.config["capture"]["max_retries"]

        if not quiet:
            # Log the actual target - a wrong stream path is otherwise invisible (issue #16)
            self._log("INFO", f"Opening stream {self._sanitize_url(url)}")

        for attempt in range(1, retries + 1):
            if self.stop_event.is_set():
                return None

            if not quiet:
                self._log("INFO", f"Connection attempt {attempt}/{retries}...")

            # Create multi-threaded bufferless capture
            buffer_frames = self.config["capture"].get("buffer_frames", 1)
            cap = RTSPBufferlessCapture(url, buffer_size=buffer_frames)

            if cap.isOpened():
                # A connection only counts once it has delivered a frame. An open
                # alone proved nothing on a stream that never fed frames: every
                # reconnect "succeeded" instantly, so the outage backoff never
                # engaged and the camera was reopened every ~12s all night.
                started = time.time()
                if self._await_first_frame(cap):
                    if not quiet:
                        self._log("INFO",
                                  f"Connection successful - first frame in {time.time() - started:.1f}s "
                                  f"(buffer: {buffer_frames} frame)")
                    return cap
                if not quiet and not self.stop_event.is_set():
                    self._log("WARNING",
                              f"Stream opened but no frame within {_FIRST_FRAME_GRACE:.0f}s")

            cap.release()

            if attempt < retries:
                if not quiet:
                    self._log("WARNING", f"Connection failed, retrying in 2s...")
                if self.stop_event.wait(timeout=2.0):
                    return None

        return None

    def _await_first_frame(self, cap) -> bool:
        """Wait up to _FIRST_FRAME_GRACE for a freshly opened stream's first frame.

        Reads in short slices so a stop request is honoured mid-wait. Consuming
        the frame here is fine: the background reader requeues the next one
        within ~1/fps, so the capture loop's own grab stays fresh.

        Returns:
            True once a frame arrived; False on grace expiry or stop request.
        """
        deadline = time.time() + _FIRST_FRAME_GRACE
        while time.time() < deadline:
            if self.stop_event.is_set():
                return False
            ret, _ = cap.read(timeout=1.0)
            if ret:
                return True
            # read() returns instantly while the reader has a pending error -
            # pace the loop (and stay stop-responsive) instead of spinning.
            if self.stop_event.wait(timeout=0.2):
                return False
        return False

    def _reconnect(self, url: str) -> bool:
        """One planned connection cycle (proactive reconnect).

        Not an outage, so no disconnect bookkeeping - disconnect_count counts
        real outages only. On False the caller escalates to _reconnect_until().
        """
        if self.cap:
            self.cap.release()
            self.cap = None

        self.cap = self._open_capture(url, retries=1)
        if self.cap is not None:
            self.connection_start_time = datetime.now()
            return True
        return False

    def _reconnect_until(self, url: str, end_dt: datetime) -> bool:
        """Reconnect with escalating backoff until success, stop, or window end.

        This is what keeps an unattended night alive: a camera that reboots or a
        network that drops for minutes must not end the session - giving up
        after a few quick attempts once cost six hours of footage (2026-07-27).

        Returns:
            True with self.cap set and state RUNNING; False when ended by
            stop_event or end_dt - callers treat both as a normal exit and
            must NEVER turn this into CaptureState.ERROR.
        """
        # Outage bookkeeping - once per outage, not once per attempt, so the
        # disconnect counters and "frequent disconnects" warning stay honest.
        now = datetime.now()
        self.disconnect_count += 1
        if self.connection_start_time is not None:
            uptime = int((now - self.connection_start_time).total_seconds())
            self._log("WARNING", f"Connection lost after {uptime}s - reconnecting (outage #{self.disconnect_count})")
        else:
            self._log("WARNING", f"Camera unreachable - retrying (outage #{self.disconnect_count})")

        if self.last_disconnect_time:
            time_since_last = (now - self.last_disconnect_time).total_seconds()
            if time_since_last < 60:  # Less than 1 minute between disconnects
                self._log("WARNING", f"Frequent disconnects detected ({int(time_since_last)}s since last)")
        self.last_disconnect_time = now

        # Visible over /status while the retry loop runs.
        self.last_error = "Camera unreachable - reconnecting"

        if self.cap:
            self.cap.release()
            self.cap = None

        self._update_state(CaptureState.RECONNECTING)

        attempt = 0
        while not self.stop_event.is_set() and datetime.now() < end_dt:
            attempt += 1
            cap = self._open_capture(url, retries=1, quiet=True)
            if cap is not None:
                self.cap = cap
                # Reset, or the proactive-reconnect check would fire immediately
                # after a long outage.
                self.connection_start_time = datetime.now()
                outage = int((self.connection_start_time - now).total_seconds())
                self._log("INFO", f"Reconnected after {attempt} attempt(s) ({outage}s outage)")
                self._update_state(CaptureState.RUNNING)
                return True

            backoff = _RECONNECT_BACKOFF[min(attempt - 1, len(_RECONNECT_BACKOFF) - 1)]
            # Sparse logging: every attempt while the backoff still escalates,
            # then every 10th - an hours-long outage must not flood the log.
            if attempt <= len(_RECONNECT_BACKOFF) or attempt % 10 == 0:
                self._log("INFO", f"Camera still unreachable (attempt {attempt}) - next retry in {backoff}s")
            if self.stop_event.wait(timeout=backoff):
                break

        return False

    def _grab_frame(self) -> tuple[np.ndarray, Optional[datetime]]:
        """
        Read a frame from the capture device with its stream timestamp.

        Flushes buffered frames first to ensure we get the freshest frame.
        This is critical for timelapse where frames are captured infrequently,
        preventing the issue where old buffered frames are saved instead of current ones.

        Returns:
            Tuple of (frame as numpy array, stream timestamp or None)

        Raises:
            RuntimeError if frame read fails
        """
        if not self.cap or not self.cap.isOpened():
            raise RuntimeError("Capture device not open")

        # Flush buffer by reading and discarding old frames
        # This ensures we get the freshest frame from the camera
        flush_count = self.config["capture"].get("flush_buffer_count", 10)
        if flush_count > 0:
            LOG.debug("grab: flushing %d buffered frame(s)", flush_count)
            for i in range(flush_count):
                ret, _ = self.cap.read()
                if not ret:
                    # If we can't flush, that's okay - just continue with what we have
                    break

        # Now read the fresh frame
        grab_started = time.time()
        ret, frame = self.cap.read()

        if not ret or frame is None:
            raise RuntimeError("Failed to read frame from stream")

        LOG.debug("grab: frame %dx%d in %.2fs",
                  frame.shape[1], frame.shape[0], time.time() - grab_started)

        # Extract frame timestamp from stream metadata
        stream_timestamp = self._get_frame_timestamp()

        return frame, stream_timestamp

    def _get_frame_timestamp(self) -> Optional[datetime]:
        """
        Extract timestamp from RTSP stream metadata.

        IMPORTANT: OpenCV's VideoCapture does not provide access to absolute
        RTSP/RTP timestamps for live streams. CAP_PROP_POS_MSEC only works
        for file playback, not live RTSP streams.

        To get accurate RTSP timestamps, you would need to:
        1. Use FFmpeg directly with metadata extraction
        2. Parse RTP header extension 0xABAC (ONVIF standard)
        3. Extract NTP timestamps from RTCP Sender Reports
        4. Use GStreamer pipeline with metadata access

        For now, this returns None and file naming falls back to system time.
        See docs/IMPROVEMENT_RECOMMENDATIONS.md for implementation details.

        Returns:
            None (always, for OpenCV limitations)
        """
        # OpenCV does not support RTSP stream metadata timestamp extraction
        # This would require FFmpeg/GStreamer integration
        # See Phase 2 improvements in IMPROVEMENT_RECOMMENDATIONS.md
        return None

    def _save_frame(self, frame: np.ndarray, stream_timestamp: Optional[datetime] = None) -> str:
        """
        Save frame to disk as JPEG.

        Args:
            frame: Frame to save
            stream_timestamp: Optional timestamp from stream metadata

        Returns:
            Full path to saved file
        """
        out_dir = self.ensure_date_dir()

        # Use stream timestamp if available, otherwise use system time
        if stream_timestamp:
            filename = stream_timestamp.strftime("%Y%m%d-%H%M%S.jpg")
        else:
            filename = datetime.now().strftime("%Y%m%d-%H%M%S.jpg")

        filepath = os.path.join(out_dir, filename)

        quality = self.config["capture"]["jpeg_quality"]
        cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, quality])

        try:
            size = os.path.getsize(filepath)
        except OSError:
            size = -1
        LOG.debug("saved %s (%d bytes, quality=%d)", filepath, size, quality)

        return filepath

    def ensure_date_dir(self) -> str:
        """
        Get or create the output directory for current date.

        Between midnight and rollover hour, uses previous day's folder.

        Public because the session event log uses it as its directory provider,
        so the folder_rollover_hour rule lives in one place and events always
        land beside the frames they describe. Safe to call from other threads:
        it only reads config and does a mkdir(exist_ok=True).

        Returns:
            Path to date-specific directory
        """
        base_dir = resolve_path(self.config["capture"]["output_folder"])
        rollover_hour = self.config["schedule"]["folder_rollover_hour"]

        path = base_dir / effective_date(datetime.now(), rollover_hour).strftime("%Y%m%d")
        path.mkdir(parents=True, exist_ok=True)

        return str(path)

    def _calculate_end_time(self) -> datetime:
        """
        End of the current capture session: the next future occurrence of the
        configured end time.

        Deliberately NOT derived from "are we before or after the start time":
        this runs right after the start-time wait, which can wake fractionally
        early, and classifying 19:59:59 as "before the window" once made an
        overnight session return yesterday's end - already in the past - so
        the capture loop exited with zero frames.

        Returns:
            Datetime when capture should end
        """
        h, m = map(int, self.config["schedule"]["end_time"].split(":"))
        now = datetime.now()
        candidate = datetime.combine(now.date(), dtime(hour=h, minute=m))

        if candidate <= now:
            candidate += timedelta(days=1)

        return candidate

    def _update_state(self, new_state: CaptureState):
        """Update state and notify callback."""
        if new_state is not self.state:
            LOG.debug("state %s -> %s (frames=%d, failed=%d, disconnects=%d)",
                      self.state.name, new_state.name, self.frame_count,
                      self.failed_frame_count, self.disconnect_count)
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
