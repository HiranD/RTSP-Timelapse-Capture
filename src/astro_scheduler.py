"""
Astronomical Scheduler - Monitors scheduled dates and twilight times
Automatically starts/stops capture based on darkness windows.

Features:
- Monitors scheduled dates from config
- Calculates twilight times for current location
- Auto-starts capture when darkness begins
- Auto-stops capture when darkness ends
- Triggers video export after session completes
"""

import threading
import time
from datetime import datetime, date
from typing import Optional, Callable
from pathlib import Path

try:
    from src.twilight_calculator import TwilightCalculator, DarknessWindow
    from src.config_manager import ConfigManager
    from src.capture_engine import effective_date
except ImportError:
    from twilight_calculator import TwilightCalculator, DarknessWindow
    from config_manager import ConfigManager
    from capture_engine import effective_date


class AstroScheduler:
    """
    Monitors scheduled dates and automatically controls capture based on twilight times.
    """

    # Check interval in seconds
    CHECK_INTERVAL = 15  # Check every 15 seconds for responsive start/stop

    def __init__(
        self,
        config_manager: ConfigManager,
        on_start_capture: Optional[Callable[[], None]] = None,
        on_stop_capture: Optional[Callable[[], None]] = None,
        on_session_complete: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize the astronomical scheduler.

        Args:
            config_manager: Application configuration manager
            on_start_capture: Callback to start capture
            on_stop_capture: Callback to stop capture
            on_session_complete: Callback when session completes (receives date string YYYYMMDD)
            on_log: Callback for log messages (level, message)
        """
        self.config_manager = config_manager
        self.on_start_capture = on_start_capture
        self.on_stop_capture = on_stop_capture
        self.on_session_complete = on_session_complete
        self.on_log = on_log

        # State
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Current session tracking
        self.current_session_date: Optional[str] = None
        self.capture_active = False
        self.current_window: Optional[DarknessWindow] = None

    def start(self):
        """Start the scheduler monitoring thread."""
        if self.running:
            return

        self.running = True
        # Fresh event per run so a previous (stopping) thread keeps its own
        # signalled event and exits, even though stop() no longer joins it.
        self.stop_event = threading.Event()

        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, args=(self.stop_event,), daemon=True
        )
        self.monitor_thread.start()

        self._log("INFO", "Astronomical scheduler started")

    def stop(self):
        """Stop the scheduler monitoring thread.

        Signals the monitor thread and returns immediately — we deliberately do
        NOT join here. stop() is called from the GUI thread (the "Enable
        automatic scheduling" toggle), and joining would freeze the UI until the
        daemon thread unwinds, visible as a lag before the checkbox clears. The
        thread is a daemon and exits on its own once its stop_event is set; each
        run owns its event (see start()), so this can't race a later restart.
        """
        if not self.running:
            return

        self.running = False
        self.stop_event.set()
        self.monitor_thread = None

        self._log("INFO", "Astronomical scheduler stopped")

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self.running

    def get_status(self) -> dict:
        """Get current scheduler status."""
        return {
            "running": self.running,
            "capture_active": self.capture_active,
            "current_session_date": self.current_session_date,
            "current_window": self.current_window
        }

    def get_tonight_window(self) -> Optional[DarknessWindow]:
        """Get the darkness window for tonight based on current config."""
        cfg = self.config_manager.astro_schedule

        if cfg.latitude == 0.0 and cfg.longitude == 0.0:
            return None

        calc = TwilightCalculator(cfg.latitude, cfg.longitude)
        return calc.get_tonight_window(
            twilight_type=cfg.twilight_type,
            start_offset_minutes=cfg.start_offset_minutes,
            end_offset_minutes=cfg.end_offset_minutes
        )

    def _monitor_loop(self, stop_event: threading.Event):
        """Main monitoring loop - checks schedule and controls capture.

        Uses the per-run ``stop_event`` passed in by start() (not
        ``self.stop_event``) so a stopping thread always watches its own event
        and exits cleanly even after a new run has begun.
        """
        self._log("INFO", "Scheduler monitor loop started")

        while not stop_event.is_set():
            try:
                self._check_schedule()
            except Exception as e:
                self._log("ERROR", f"Scheduler error: {e}")

            # Wait for next check interval
            stop_event.wait(timeout=self.CHECK_INTERVAL)

        self._log("INFO", "Scheduler monitor loop ended")

    def _check_schedule(self):
        """Check if we should start or stop capture based on schedule."""
        cfg = self.config_manager.astro_schedule

        now = datetime.now()

        # Which night does "now" belong to? Decided by the same rollover rule
        # that files frames into date folders (effective_date): before the
        # rollover hour, "now" is still the previous evening's night. Gating on
        # the owning date - instead of calendar-today plus an is-a-session-
        # already-active check - is what lets a session START mid-window after
        # midnight: the scheduler enabled, the date ticked, or the app
        # restarted at 01:00 must still capture the rest of that night.
        rollover = self.config_manager.schedule.folder_rollover_hour
        owning_date = effective_date(now, rollover).strftime("%Y-%m-%d")

        if owning_date not in cfg.scheduled_dates:
            # This night isn't scheduled (or its date was unticked/the calendar
            # cleared mid-capture): stop any active session, start nothing.
            if self.capture_active:
                self._stop_capture_session()
            return

        # Check which mode we're using
        if cfg.use_manual_times:
            # Manual time mode - use fixed start/end times. The owning date
            # labels the session, so an after-midnight start still files under
            # the evening it belongs to.
            self._check_manual_schedule(now, owning_date)
        else:
            # Twilight-based mode - use astronomical calculations
            self._check_twilight_schedule(now)

    def _check_manual_schedule(self, now: datetime, owning_date_str: str):
        """Check manual time-based schedule.

        `owning_date_str` is the night's owning date (YYYY-MM-DD, per the
        folder rollover rule) - after midnight that's yesterday, so the
        session is labelled with the evening it belongs to.
        """
        cfg = self.config_manager.astro_schedule

        start_time_str = cfg.manual_start_time
        end_time_str = cfg.manual_end_time

        # Check if within manual time window
        in_window = self._is_within_manual_window(now, start_time_str, end_time_str)

        if in_window:
            if not self.capture_active:
                # Start capture with manual times
                self.config_manager.schedule.start_time = start_time_str
                self.config_manager.schedule.end_time = end_time_str
                self._start_capture_session_manual(owning_date_str, start_time_str, end_time_str)
        else:
            if self.capture_active:
                # Stop capture - outside manual window
                self._stop_capture_session()

    def _is_within_manual_window(self, now: datetime, start_str: str, end_str: str) -> bool:
        """Check if current time is within manual start/end window."""
        try:
            start_parts = start_str.split(":")
            end_parts = end_str.split(":")
            start_hour, start_min = int(start_parts[0]), int(start_parts[1])
            end_hour, end_min = int(end_parts[0]), int(end_parts[1])

            current_mins = now.hour * 60 + now.minute
            start_mins = start_hour * 60 + start_min
            end_mins = end_hour * 60 + end_min

            # Handle overnight windows (e.g., 22:00 - 06:00)
            if end_mins < start_mins:
                # Overnight window
                return current_mins >= start_mins or current_mins < end_mins
            else:
                # Same day window (e.g., 10:00 - 14:00)
                return start_mins <= current_mins < end_mins

        except (ValueError, IndexError):
            self._log("ERROR", f"Invalid manual time format: {start_str} - {end_str}")
            return False

    def _start_capture_session_manual(self, date_str: str, start_time: str, end_time: str):
        """Start a capture session with manual times."""
        self.capture_active = True
        self.current_session_date = date_str.replace("-", "")

        self._log("INFO", f"Starting scheduled capture session for {self.current_session_date}")
        self._log("INFO", f"Manual window: {start_time} - {end_time}")

        # Update the capture schedule times in config
        self.config_manager.schedule.start_time = start_time
        self.config_manager.schedule.end_time = end_time

        if self.on_start_capture:
            self.on_start_capture()

    def _check_twilight_schedule(self, now: datetime):
        """Check twilight-based schedule."""
        cfg = self.config_manager.astro_schedule

        # Skip if location not set
        if cfg.latitude == 0.0 and cfg.longitude == 0.0:
            return

        # Get tonight's darkness window
        calc = TwilightCalculator(cfg.latitude, cfg.longitude)
        window = calc.get_tonight_window(
            twilight_type=cfg.twilight_type,
            start_offset_minutes=cfg.start_offset_minutes,
            end_offset_minutes=cfg.end_offset_minutes
        )

        if not window:
            self._log("WARNING", "Could not calculate darkness window (polar day/night?)")
            return

        self.current_window = window

        # Check if we're within the darkness window
        if window.is_active_now():
            if not self.capture_active:
                # Start capture
                self._start_capture_session(window)
        else:
            if self.capture_active:
                # Stop capture - darkness ended
                self._stop_capture_session()

    def _start_capture_session(self, window: DarknessWindow):
        """Start a capture session."""
        self.capture_active = True
        self.current_session_date = window.date.strftime("%Y%m%d")

        self._log("INFO", f"Starting scheduled capture session for {self.current_session_date}")
        self._log("INFO", f"Darkness window: {window.get_time_range_str()} ({window.get_duration_str()})")

        # Update the capture schedule times in config to match twilight times
        self.config_manager.schedule.start_time = window.darkness_start.strftime("%H:%M")
        self.config_manager.schedule.end_time = window.darkness_end.strftime("%H:%M")

        if self.on_start_capture:
            self.on_start_capture()

    def notify_start_failed(self):
        """The start callback could not actually start capture.

        capture_active is flagged optimistically before on_start_capture runs;
        if the downstream start fails (bad config, engine error) the scheduler
        would otherwise believe capture is running forever - "Capturing" with
        zero frames - and never retry. Resetting the session bookkeeping here
        (WITHOUT firing on_session_complete: no session ran, so no auto-video)
        lets the next monitor poll try again.
        """
        self.capture_active = False
        self.current_session_date = None
        self.current_window = None
        self._log("WARNING", "Capture failed to start - will retry on the next check")

    def _stop_capture_session(self):
        """Stop a capture session and trigger post-processing."""
        session_date = self.current_session_date

        self._log("INFO", f"Stopping scheduled capture session for {session_date}")

        # Clear the flag BEFORE notifying the UI: on_stop_capture() triggers the
        # status-label refresh, which must read the post-stop state ("waiting"),
        # not the stale "Capturing".
        self.capture_active = False

        if self.on_stop_capture:
            self.on_stop_capture()

        # Trigger session complete callback (for auto video creation)
        if session_date and self.on_session_complete:
            self._log("INFO", f"Session complete - triggering post-processing for {session_date}")
            self.on_session_complete(session_date)

        self.current_session_date = None
        self.current_window = None

    def _log(self, level: str, message: str):
        """Log a message."""
        if self.on_log:
            self.on_log(level, f"[Scheduler] {message}")
        else:
            print(f"[{level}] [Scheduler] {message}")


def test_scheduler():
    """Test the scheduler."""
    from config_manager import ConfigManager

    config = ConfigManager()

    # Set up test location (London)
    config.astro_schedule.latitude = 51.5074
    config.astro_schedule.longitude = -0.1278
    config.astro_schedule.twilight_type = "astronomical"

    # Schedule today
    today = date.today().strftime("%Y-%m-%d")
    config.astro_schedule.scheduled_dates = [today]

    def on_start():
        print(">>> CAPTURE STARTED")

    def on_stop():
        print(">>> CAPTURE STOPPED")

    def on_complete(date_str):
        print(f">>> SESSION COMPLETE: {date_str}")

    def on_log(level, msg):
        print(f"[{level}] {msg}")

    scheduler = AstroScheduler(
        config,
        on_start_capture=on_start,
        on_stop_capture=on_stop,
        on_session_complete=on_complete,
        on_log=on_log
    )

    # Get tonight's window
    window = scheduler.get_tonight_window()
    if window:
        print(f"\nTonight's window: {window.get_time_range_str()} ({window.get_duration_str()})")
        print(f"Currently in darkness: {window.is_active_now()}")

    print("\nStarting scheduler (Ctrl+C to stop)...")
    scheduler.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        scheduler.stop()


if __name__ == "__main__":
    test_scheduler()
