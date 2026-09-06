"""
Capture History Manager - Tracks completed capture sessions for calendar display.

Stores session data in capture_history.json to persist captured dates even after
snapshots are deleted (e.g., after auto video creation).
"""

import sys
import json
import threading
from dataclasses import dataclass, asdict, fields, replace
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from src.app_logging import get_logger
except ImportError:
    from app_logging import get_logger

LOG = get_logger("history")


def get_app_base_dir() -> Path:
    """Get the application's base directory (where exe or main script is located)."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - use exe's directory
        return Path(sys.executable).parent
    else:
        # Running from source - use src's parent directory
        return Path(__file__).parent.parent


@dataclass
class CaptureSession:
    """Represents a completed capture session."""
    date: str              # YYYYMMDD format
    start_time: str        # ISO format datetime
    end_time: str          # ISO format datetime
    image_count: int       # Number of images captured
    video_created: bool    # Whether auto-video was created
    status: str            # "completed", "partial", "failed"
    # What started the session: "scheduled" | "remote" | "manual". Defaults to
    # "scheduled" because legacy history files predate the field and only the
    # scheduler ever wrote history back then - so the default is factually
    # correct for old entries, not merely safe.
    source: str = "scheduled"

    @property
    def succeeded(self) -> bool:
        """Completed with at least one image - the one rule for whether a
        session earns its day a calendar mark. Shared by the history queries
        and the calendar (TwoMonthCalendar._capture_kind) so they can't drift."""
        return self.status == "completed" and self.image_count > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CaptureSession':
        """Create from dictionary, dropping unknown keys.

        An unknown key used to TypeError the constructor, and the broad except
        in _load() would then silently discard the ENTIRE history - so a file
        written by a newer version must never break an older loader again.
        """
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


class CaptureHistoryManager:
    """Manages persistent capture session history.

    Sessions are kept per date as a LIST: a short manual test and the real
    scheduled night can share a date, and the calendar needs both (the color
    depends on whether ANY session that day was scheduled, and the hover
    tooltip lists them all). The on-disk shape is unchanged - a flat
    "sessions" list - so files round-trip with older versions.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize capture history manager.

        Args:
            config_dir: Directory to store history file. Defaults to 'user_data' folder.
        """
        if config_dir is None:
            config_dir = get_app_base_dir() / 'user_data'

        self.config_dir = Path(config_dir)
        self.history_file = self.config_dir / 'capture_history.json'
        self.sessions: Dict[str, List[CaptureSession]] = {}  # Keyed by date string

        # Three threads write history: the Tk main thread (manual/remote stops),
        # the scheduler's monitor thread (_on_session_complete), and the video
        # export worker (update_video_created after a render). Every public
        # accessor takes it, readers included: one rule for touching
        # self.sessions instead of a per-method reliance on the GIL. Not
        # re-entrant - _save() is called with the lock already held and must
        # never take it itself.
        self._lock = threading.Lock()

        self._ensure_config_dir()
        self._load()

    def _ensure_config_dir(self):
        """Ensure config directory exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _load(self):
        """Load history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)

                sessions_list = data.get('sessions', [])
                for session_data in sessions_list:
                    session = CaptureSession.from_dict(session_data)
                    self.sessions.setdefault(session.date, []).append(session)

                # Chronological per date (ISO strings sort correctly); files are
                # hand-editable, so don't trust the stored order.
                for day_sessions in self.sessions.values():
                    day_sessions.sort(key=lambda s: s.start_time)

            except (json.JSONDecodeError, KeyError, TypeError) as e:
                LOG.warning("could not load capture history from %s: %s",
                            self.history_file, e)
                print(f"Warning: Could not load capture history: {e}")
                self.sessions = {}

    def _save(self):
        """Save history to file. Callers must hold self._lock."""
        try:
            data = {
                'sessions': [s.to_dict()
                             for day_sessions in self.sessions.values()
                             for s in day_sessions]
            }
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            LOG.warning("could not save capture history to %s: %s", self.history_file, e)
            print(f"Warning: Could not save capture history: {e}")

    def add_session(self, session: CaptureSession):
        """
        Add a capture session. Sessions on the same date accumulate.

        Args:
            session: The capture session to record.
        """
        LOG.debug("recording session %s: %d image(s), status=%s, video_created=%s, source=%s",
                  session.date, session.image_count, session.status,
                  session.video_created, session.source)
        with self._lock:
            self.sessions.setdefault(session.date, []).append(session)
            self._save()

    def get_session(self, date: str) -> Optional[CaptureSession]:
        """
        Get the most recent capture session for a date.

        Compatibility shim from the one-session-per-date era; new callers that
        care about the whole day should use get_sessions_for_date().

        Args:
            date: Date string in YYYYMMDD format.

        Returns:
            CaptureSession if found, None otherwise.
        """
        with self._lock:
            day_sessions = self.sessions.get(date)
            return day_sessions[-1] if day_sessions else None

    def get_sessions_for_date(self, date: str) -> List[CaptureSession]:
        """
        Get all capture sessions for a date, chronological.

        Args:
            date: Date string in YYYYMMDD format.

        Returns:
            List of sessions (possibly empty). A copy - safe to iterate while
            other threads record.
        """
        with self._lock:
            return list(self.sessions.get(date, []))

    def has_capture(self, date: str) -> bool:
        """
        Check if a date has any successful recorded capture session.

        Args:
            date: Date string in YYYYMMDD format.

        Returns:
            True if any session that day completed with images.
        """
        with self._lock:
            return any(s.succeeded for s in self.sessions.get(date, []))

    def has_scheduled_capture(self, date: str) -> bool:
        """
        Check if a date has a successful SCHEDULED capture session.

        Single-query form of the calendar's color rule: any successful
        scheduled session makes the day "captured (scheduled)"; a day with only
        manual/remote sessions gets its own color. The calendar itself applies
        the same rule to the list it fetches once per cell
        (TwoMonthCalendar._capture_kind).

        Args:
            date: Date string in YYYYMMDD format.
        """
        with self._lock:
            return any(s.succeeded and s.source == "scheduled"
                       for s in self.sessions.get(date, []))

    def get_captured_dates(self) -> List[str]:
        """
        Get all dates with successful captures.

        Returns:
            List of date strings (YYYYMMDD format).
        """
        with self._lock:
            return [date for date, day_sessions in self.sessions.items()
                    if any(s.succeeded for s in day_sessions)]

    def update_video_created(self, date: str, video_created: bool = True):
        """
        Mark the most recent completed session of a date as having a video.

        The render that just finished was built from frames, which a trailing
        0-frame failed session doesn't have - so prefer the last *completed*
        session, falling back to the last entry. dataclasses.replace() keeps
        every other field (the old field-by-field rebuild silently dropped any
        field added later, e.g. `source`).

        Args:
            date: Date string in YYYYMMDD format.
            video_created: Whether video was created.
        """
        with self._lock:
            day_sessions = self.sessions.get(date)
            if not day_sessions:
                return
            # Pick by position, walking back from the end. list.index() would
            # compare dataclass fields, so two value-identical sessions on one
            # date could send the mark to the earlier twin instead of the most
            # recent one chosen here.
            idx = next((i for i in range(len(day_sessions) - 1, -1, -1)
                        if day_sessions[i].status == "completed"),
                       len(day_sessions) - 1)
            day_sessions[idx] = replace(day_sessions[idx], video_created=video_created)
            self._save()

    def record_session(
        self,
        date: str,
        start_time: datetime,
        end_time: datetime,
        image_count: int,
        video_created: bool = False,
        source: str = "scheduled"
    ):
        """
        Convenience method to record a capture session.

        Args:
            date: Date string in YYYYMMDD format.
            start_time: When capture started.
            end_time: When capture ended.
            image_count: Number of images captured.
            video_created: Whether video was created.
            source: What started the session: "scheduled" | "remote" | "manual".
        """
        status = "completed" if image_count > 0 else "failed"

        session = CaptureSession(
            date=date,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            image_count=image_count,
            video_created=video_created,
            status=status,
            source=source
        )
        self.add_session(session)


# Singleton instance for easy access
_instance: Optional[CaptureHistoryManager] = None


def get_capture_history() -> CaptureHistoryManager:
    """Get the singleton capture history manager instance."""
    global _instance
    if _instance is None:
        _instance = CaptureHistoryManager()
    return _instance
