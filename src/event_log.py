"""
Session Event Log - timestamped events recorded alongside a capture session.

External programs (e.g. the NINA plugin) push events - "Autofocus Complete",
"Meridian Flip" - over the Remote Control HTTP API. They are appended to
``events.jsonl`` in the *same* date folder as that night's frames, so the log
travels with the footage it describes and the video export can find it later.

Only accepted while capture is running: an event that arrives with no session
has no frames to attach to, so ``record()`` rejects it (the API turns that into
a 409 the caller can treat as a skip rather than a failure).

Storage is JSON Lines rather than a JSON array because it is append-only and
crash-safe - a session killed mid-write costs the last line, not the whole file.

This module is intentionally Tk-agnostic and thread-safe: events arrive on the
HTTP server's worker threads and are written straight to disk without hopping
onto the Tk main loop.

Record shape (one JSON object per line)::

    {"time": "20260725-230518", "title": "Autofocus Complete",
     "detail": "HFR 2.31 -> 1.62", "category": "autofocus",
     "data": {"hfr_before": 2.31, "hfr_after": 1.62}}

``data`` is free-form and never drawn; it carries structured values for the
event log export and for the future telemetry overlay.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List, Optional

try:
    from src.app_logging import get_logger, trunc
except ImportError:
    from app_logging import get_logger, trunc

LOG = get_logger("events")

# Filename written inside each session's date folder.
EVENTS_FILENAME = "events.jsonl"

# Timestamp format, matching the frame filenames (YYYYMMDD-HHMMSS.jpg) so events
# and frames sort and compare the same way.
TIME_FORMAT = "%Y%m%d-%H%M%S"

# Field caps. Titles/details are drawn on video, so absurd lengths are clamped
# rather than rejected - a truncated caption beats a lost event.
MAX_TITLE = 120
MAX_DETAIL = 200
MAX_CATEGORY = 40

# How many records GET /events returns, newest last. Bounds the response for a
# long night without needing pagination.
RECENT_LIMIT = 200


def _clean(value: Any, limit: int) -> Optional[str]:
    """Coerce a field to a single-line string of at most `limit` chars.

    Control characters (including newlines) are stripped: these strings end up
    in a line-delimited log file and drawn onto video frames, so a stray newline
    would corrupt the record. Returns None for anything not a non-empty string.
    """
    if not isinstance(value, str):
        return None
    text = "".join(ch for ch in value if ch.isprintable()).strip()
    return text[:limit] if text else None


class SessionEvent:
    """One timestamped event belonging to a capture session."""

    __slots__ = ("time", "title", "detail", "category", "data")

    def __init__(self, time: datetime, title: str, detail: Optional[str] = None,
                 category: Optional[str] = None, data: Optional[dict] = None):
        self.time = time
        self.title = title
        self.detail = detail
        self.category = category
        self.data = data

    def to_dict(self) -> dict:
        """Serialise for JSONL / the HTTP response, omitting empty optionals."""
        record = {"time": self.time.strftime(TIME_FORMAT), "title": self.title}
        if self.detail:
            record["detail"] = self.detail
        if self.category:
            record["category"] = self.category
        if self.data:
            record["data"] = self.data
        return record

    @classmethod
    def from_dict(cls, record: dict) -> Optional["SessionEvent"]:
        """Rebuild from a stored record, or None if it isn't usable.

        Returning None rather than raising lets readers skip a corrupt line and
        carry on - one bad record must not fail a whole video export.
        """
        if not isinstance(record, dict):
            return None
        title = _clean(record.get("title"), MAX_TITLE)
        if not title:
            return None
        try:
            when = datetime.strptime(str(record.get("time", "")), TIME_FORMAT)
        except (ValueError, TypeError):
            return None
        data = record.get("data")
        return cls(
            time=when,
            title=title,
            detail=_clean(record.get("detail"), MAX_DETAIL),
            category=_clean(record.get("category"), MAX_CATEGORY),
            data=data if isinstance(data, dict) else None,
        )


class EventLog:
    """Append-only event store scoped to the running capture session.

    The GUI calls begin_session()/end_session() as capture starts and stops, so
    "only while capturing" is an invariant of the store rather than a check
    repeated by every caller.
    """

    def __init__(self, dir_provider: Callable[[], str],
                 log: Optional[Callable[[str, str], None]] = None):
        """
        Args:
            dir_provider: () -> str, the current session's date folder, created
                if needed. In the app this is CaptureEngine.ensure_date_dir,
                which already applies the folder_rollover_hour rule - so the
                rule lives in exactly one place. Called off the Tk thread, so it
                must not touch Tkinter.
            log: optional callable(level: str, message: str) for logging.
        """
        self._dir_provider = dir_provider
        self._log = log or (lambda level, msg: None)
        self._lock = threading.Lock()
        self._active = False
        self._recent: List[SessionEvent] = []

    # -------------------------------------------------------------- lifecycle

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def begin_session(self):
        """Start accepting events. Clears the in-memory list from the last run."""
        LOG.debug("event session opened")
        with self._lock:
            self._active = True
            self._recent = []

    def end_session(self):
        """Stop accepting events. The on-disk log is left in place."""
        with self._lock:
            was_active = self._active
            self._active = False
            count = len(self._recent)
        if was_active:
            LOG.debug("event session closed (%d event(s) recorded)", count)

    # ----------------------------------------------------------------- record

    def record(self, title, detail=None, category=None, when=None, data=None):
        """Validate and append one event.

        Args:
            title: required caption line.
            detail: optional second line.
            category: optional grouping key (e.g. "autofocus", "target").
            when: optional datetime; defaults to now. Callers parse the wire
                format themselves so a bad string is a 400, not a silent "now".
            data: optional dict of structured values (log-only, never drawn).

        Returns:
            (ok: bool, error: str | None, stored: dict | None)
        """
        clean_title = _clean(title, MAX_TITLE)
        if not clean_title:
            return False, "missing title", None

        event = SessionEvent(
            time=when or datetime.now(),
            title=clean_title,
            detail=_clean(detail, MAX_DETAIL),
            category=_clean(category, MAX_CATEGORY),
            data=data if isinstance(data, dict) else None,
        )

        with self._lock:
            if not self._active:
                return False, "not capturing", None
            try:
                self._append(event)
            except OSError as e:
                self._log("ERROR", f"Could not write event log: {e}")
                return False, "could not write event log", None
            self._recent.append(event)
            del self._recent[:-RECENT_LIMIT]

        self._log("INFO", f"Event: {event.title}" + (f" - {event.detail}" if event.detail else ""))
        return True, None, event.to_dict()

    def _append(self, event: SessionEvent):
        """Append one JSON line to the session folder's log (caller holds the lock)."""
        path = Path(self._dir_provider()) / EVENTS_FILENAME
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        # trunc: `data` is the one field not capped by _clean(), and a remote
        # caller can push tens of KB of it - events.jsonl gets it all, but a
        # log line doesn't need to.
        LOG.debug("event appended to %s: %s", path, trunc(event.to_dict()))

    def recent(self) -> list:
        """Serialised events recorded this session, oldest first (for GET /events)."""
        with self._lock:
            return [e.to_dict() for e in self._recent]


def read_events(date_dir, since: Optional[datetime] = None) -> List[SessionEvent]:
    """Read a session folder's event log.

    Args:
        date_dir: folder holding events.jsonl (a night's snapshot folder).
        since: if set, drop events before this time - mirrors the `since` filter
            the video export applies to frames, so a folder holding several
            sessions renders only the matching events.

    Returns:
        List of SessionEvent sorted by time. Missing file -> empty list.
        Unparseable lines are skipped: a corrupt record must not fail an export.
    """
    path = Path(date_dir) / EVENTS_FILENAME
    if not path.exists():
        return []

    events = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue  # truncated/corrupt line - skip it
                event = SessionEvent.from_dict(record)
                if event and (since is None or event.time >= since):
                    events.append(event)
    except OSError:
        return []

    events.sort(key=lambda e: e.time)
    return events
