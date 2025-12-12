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
from datetime import datetime, date, timedelta
from typing import Optional, Callable
from pathlib import Path

try:
    from src.twilight_calculator import TwilightCalculator, DarknessWindow
    from src.config_manager import ConfigManager
except ImportError:
    from twilight_calculator import TwilightCalculator, DarknessWindow
    from config_manager import ConfigManager


class AstroScheduler:
    """
    Monitors scheduled dates and automatically controls capture based on twilight times.
    """

    # Check interval in seconds
    CHECK_INTERVAL = 60  # Check every minute

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
        self.stop_event.clear()

        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

        self._log("INFO", "Astronomical scheduler started")

    def stop(self):
        """Stop the scheduler monitoring thread."""
        if not self.running:
            return

        self.running = False
        self.stop_event.set()

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)

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

    def _monitor_loop(self):
        """Main monitoring loop - checks schedule and controls capture."""
        self._log("INFO", "Scheduler monitor loop started")

        while not self.stop_event.is_set():
            try:
                self._check_schedule()
            except Exception as e:
                self._log("ERROR", f"Scheduler error: {e}")

            # Wait for next check interval
            self.stop_event.wait(timeout=self.CHECK_INTERVAL)

        self._log("INFO", "Scheduler monitor loop ended")

    def _check_schedule(self):
        """Check if we should start or stop capture based on schedule."""
        cfg = self.config_manager.astro_schedule

        # Skip if location not set
        if cfg.latitude == 0.0 and cfg.longitude == 0.0:
            return

        # Skip if no scheduled dates
        if not cfg.scheduled_dates:
            return

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        # Check if today is scheduled
        if today_str not in cfg.scheduled_dates:
            # Also check yesterday (for overnight sessions that started yesterday)
            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            if yesterday not in cfg.scheduled_dates:
                # Not scheduled
                if self.capture_active:
                    self._stop_capture_session()
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

    def _stop_capture_session(self):
        """Stop a capture session and trigger post-processing."""
        session_date = self.current_session_date

        self._log("INFO", f"Stopping scheduled capture session for {session_date}")

        if self.on_stop_capture:
            self.on_stop_capture()

        self.capture_active = False

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
