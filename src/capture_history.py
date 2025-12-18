"""
Capture History Manager - Tracks completed capture sessions for calendar display.

Stores session data in capture_history.json to persist captured dates even after
snapshots are deleted (e.g., after auto video creation).
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class CaptureSession:
    """Represents a completed capture session."""
    date: str              # YYYYMMDD format
    start_time: str        # ISO format datetime
    end_time: str          # ISO format datetime
    image_count: int       # Number of images captured
    video_created: bool    # Whether auto-video was created
    status: str            # "completed", "partial", "failed"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CaptureSession':
        """Create from dictionary."""
        return cls(**data)


class CaptureHistoryManager:
    """Manages persistent capture session history."""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize capture history manager.

        Args:
            config_dir: Directory to store history file. Defaults to 'user_data' folder.
        """
        if config_dir is None:
            config_dir = Path.cwd() / 'user_data'

        self.config_dir = Path(config_dir)
        self.history_file = self.config_dir / 'capture_history.json'
        self.sessions: Dict[str, CaptureSession] = {}  # Keyed by date string

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
                    self.sessions[session.date] = session

            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"Warning: Could not load capture history: {e}")
                self.sessions = {}

    def _save(self):
        """Save history to file."""
        try:
            data = {
                'sessions': [s.to_dict() for s in self.sessions.values()]
            }
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save capture history: {e}")

    def add_session(self, session: CaptureSession):
        """
        Add or update a capture session.

        Args:
            session: The capture session to record.
        """
        self.sessions[session.date] = session
        self._save()

    def get_session(self, date: str) -> Optional[CaptureSession]:
        """
        Get a capture session by date.

        Args:
            date: Date string in YYYYMMDD format.

        Returns:
            CaptureSession if found, None otherwise.
        """
        return self.sessions.get(date)

    def has_capture(self, date: str) -> bool:
        """
        Check if a date has a recorded capture session.

        Args:
            date: Date string in YYYYMMDD format.

        Returns:
            True if capture session exists and has images.
        """
        session = self.sessions.get(date)
        if session:
            return session.status == "completed" and session.image_count > 0
        return False

    def get_captured_dates(self) -> List[str]:
        """
        Get all dates with successful captures.

        Returns:
            List of date strings (YYYYMMDD format).
        """
        return [
            date for date, session in self.sessions.items()
            if session.status == "completed" and session.image_count > 0
        ]

    def update_video_created(self, date: str, video_created: bool = True):
        """
        Update a session to mark video as created.

        Args:
            date: Date string in YYYYMMDD format.
            video_created: Whether video was created.
        """
        if date in self.sessions:
            session = self.sessions[date]
            self.sessions[date] = CaptureSession(
                date=session.date,
                start_time=session.start_time,
                end_time=session.end_time,
                image_count=session.image_count,
                video_created=video_created,
                status=session.status
            )
            self._save()

    def record_session(
        self,
        date: str,
        start_time: datetime,
        end_time: datetime,
        image_count: int,
        video_created: bool = False
    ):
        """
        Convenience method to record a capture session.

        Args:
            date: Date string in YYYYMMDD format.
            start_time: When capture started.
            end_time: When capture ended.
            image_count: Number of images captured.
            video_created: Whether video was created.
        """
        status = "completed" if image_count > 0 else "failed"

        session = CaptureSession(
            date=date,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            image_count=image_count,
            video_created=video_created,
            status=status
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
