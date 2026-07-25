"""
Event Overlays - burn session events into the rendered timelapse as captions.

Two separable pieces:

* ``EventOverlayPlan`` - pure timing logic. Binds each event to a frame and works
  out which captions are visible on any given frame. No image handling, so the
  fiddly part is unit-testable on its own.
* ``draw_captions`` - draws those captions onto a PIL image.

Drawing happens in Python rather than via FFmpeg's ``drawtext`` filter because
the export already copies every frame to a temp folder before encoding (see
``VideoExportController._prepare_temp_images``), so the hook costs nothing
structurally - and because a per-frame telemetry overlay (issue #15 item 4)
needs values that change every frame, which one drawtext filter per event
cannot express.

TIMING, THE PART THAT IS EASY TO GET WRONG
------------------------------------------
Captions hold for a number of *output* video frames, not source frames. With
``speed_multiplier`` N the export keeps only every Nth source frame, so source
frame ``i`` survives when ``i % N == 0`` and lands at output ordinal ``i // N``.
Timing computed on source indices instead would make captions flash by N times
too fast - or vanish entirely if their frames were the dropped ones.
"""

import csv
import os
from bisect import bisect_left
from typing import List, Optional, Sequence

from event_log import SessionEvent, read_events  # noqa: F401  (read_events re-exported)

# Cap on captions drawn at once. A busy few minutes (autofocus + filter change +
# dither) can overlap; beyond this the panel would swallow the frame, so the
# oldest are dropped.
MAX_VISIBLE = 3

# Panel geometry, as fractions of image height so 1080p and 4K look alike.
_MARGIN = 0.030
_TITLE_SIZE = 0.028
_DETAIL_SIZE = 0.023
_PAD = 0.012
_LINE_GAP = 0.006

# Fonts tried in order (Windows). ImageFont.load_default() is the fallback, so a
# missing font degrades the look rather than failing the export.
_FONT_CANDIDATES = ("segoeui.ttf", "arial.ttf", "calibri.ttf", "consola.ttf")
_BOLD_CANDIDATES = ("segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "consolab.ttf")


class Caption:
    """One event resolved to its place in the output video."""

    __slots__ = ("event", "start_ordinal", "end_ordinal")

    def __init__(self, event: SessionEvent, start_ordinal: int, end_ordinal: int):
        self.event = event
        self.start_ordinal = start_ordinal  # first output frame it appears on
        self.end_ordinal = end_ordinal      # last output frame it appears on (inclusive)

    @property
    def title(self) -> str:
        return self.event.title

    @property
    def detail(self) -> Optional[str]:
        return self.event.detail

    def video_seconds(self, framerate: int) -> float:
        """When this caption appears, in seconds into the output video."""
        return self.start_ordinal / float(framerate) if framerate else 0.0


class EventOverlayPlan:
    """Maps session events onto output frames for a specific export.

    Events outside the rendered frame range are dropped: an event from before the
    first frame or after the last has nothing to label.
    """

    def __init__(self, events: Sequence[SessionEvent], frame_times: Sequence,
                 framerate: int, speed_multiplier: int = 1, hold_seconds: float = 4.0):
        """
        Args:
            events: session events, any order (sorted here).
            frame_times: datetime per source frame, ascending, index-aligned with
                the export's image list (ImageCollection.images).
            framerate: output frames per second.
            speed_multiplier: keep every Nth source frame (the export's `select` filter).
            hold_seconds: how long each caption stays on screen, in video seconds.
        """
        self.framerate = max(1, int(framerate))
        self.speed = max(1, int(speed_multiplier))
        self.hold_seconds = max(0.1, float(hold_seconds))
        self._frame_times = list(frame_times)

        # Hold duration in OUTPUT frames - see the module docstring.
        hold_frames = max(1, int(round(self.hold_seconds * self.framerate)))

        self.captions: List[Caption] = []
        for event in sorted(events, key=lambda e: e.time):
            index = self._frame_index_for(event.time)
            if index is None:
                continue
            start = index // self.speed
            self.captions.append(Caption(event, start, start + hold_frames - 1))

    def _frame_index_for(self, when) -> Optional[int]:
        """Source-frame index for an event: the first frame captured at/after it.

        A frame shows the sky *at* its capture moment, so an event is labelled on
        the first frame that could have witnessed it. Events after the last frame
        return None (nothing left to label).
        """
        if not self._frame_times:
            return None
        index = bisect_left(self._frame_times, when)
        return index if index < len(self._frame_times) else None

    def captions_for_index(self, source_index: int) -> List[Caption]:
        """Captions visible on a given source frame, oldest first.

        Returns [] for frames the export drops (speed_multiplier), so callers can
        keep their fast path for untouched frames.
        """
        if source_index % self.speed:
            return []  # dropped by the select filter - never rendered
        ordinal = source_index // self.speed
        visible = [c for c in self.captions if c.start_ordinal <= ordinal <= c.end_ordinal]
        return visible[-MAX_VISIBLE:]

    @property
    def is_empty(self) -> bool:
        """True when no event landed in range - lets the export skip drawing entirely."""
        return not self.captions

    def write_csv(self, path) -> int:
        """Write the rendered events to a CSV beside the video (issue #15 item 5).

        Carries both wall-clock time and the video timecode, which is what makes the
        log usable: it can be lined up against the footage or imported into an editor.

        Returns:
            Number of rows written.
        """
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["wall_clock", "video_timecode", "video_seconds",
                             "category", "title", "detail"])
            for caption in self.captions:
                seconds = caption.video_seconds(self.framerate)
                writer.writerow([
                    caption.event.time.strftime("%Y-%m-%d %H:%M:%S"),
                    format_timecode(seconds),
                    f"{seconds:.2f}",
                    caption.event.category or "",
                    caption.title,
                    caption.detail or "",
                ])
        return len(self.captions)


def format_timecode(seconds: float) -> str:
    """Format seconds as HH:MM:SS.s for the CSV's video timecode column."""
    seconds = max(0.0, float(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{secs:04.1f}"


# --------------------------------------------------------------------- drawing


def _load_font(size: int, bold: bool = False):
    """Best available TrueType font at `size`, falling back to PIL's bitmap font.

    The fallback ignores size, so captions come out small rather than absent - a
    plain-looking overlay beats a failed export on a machine without these fonts.
    """
    from PIL import ImageFont

    for name in (_BOLD_CANDIDATES if bold else _FONT_CANDIDATES):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_size(draw, text: str, font) -> tuple:
    """(width, line_height) for one line of text.

    Height comes from the font's own metrics, not the text's ink bounding box: the
    ink box of "HFR 2.31" has no descender and measures shorter than a line
    containing "g", so stacking by ink height makes rows creep together and the
    text overflows the panel drawn around it. Ascent+descent is constant per font,
    which is what a stacked layout needs.
    """
    try:
        width = int(draw.textlength(text, font=font))
    except AttributeError:  # Pillow < 8
        return draw.textsize(text, font=font)
    try:
        ascent, descent = font.getmetrics()
        height = ascent + descent
    except AttributeError:  # bitmap fallback font has no metrics
        height = draw.textbbox((0, 0), text, font=font)[3]
    return width, height


def draw_captions(image, captions: Sequence[Caption]):
    """Draw captions onto a PIL image, in place. No-op when there are none.

    Renders a translucent panel in the lower-left with one block per caption,
    stacked oldest-first. Sizes scale with image height so the result looks the
    same at 1080p and 4K.
    """
    if not captions:
        return image

    from PIL import Image, ImageDraw

    width, height = image.size
    margin = int(height * _MARGIN)
    pad = int(height * _PAD)
    line_gap = int(height * _LINE_GAP)
    title_font = _load_font(max(11, int(height * _TITLE_SIZE)), bold=True)
    detail_font = _load_font(max(10, int(height * _DETAIL_SIZE)))

    # Measure first so the panel can be sized before anything is drawn. Each line
    # carries its own colour rather than inferring it from the font: when both fonts
    # fall back to load_default() they can be the same object, and detail lines
    # would then be drawn in the title colour.
    measure = ImageDraw.Draw(image)
    blocks = []
    for caption in captions:
        lines = [(caption.title, title_font, (255, 255, 255, 255))]
        if caption.detail:
            lines.append((caption.detail, detail_font, (200, 214, 232, 255)))
        sizes = [_text_size(measure, text, font) for text, font, _ in lines]
        block_w = max(w for w, _ in sizes)
        block_h = sum(h for _, h in sizes) + line_gap * (len(sizes) - 1)
        blocks.append((lines, sizes, block_w, block_h))

    # Panel size mirrors the draw loop below exactly - line_gap *between* lines,
    # block_gap *between* blocks, neither after the last - so the box always fits
    # its contents no matter how many captions are stacked.
    block_gap = line_gap * 2
    panel_w = max(b[2] for b in blocks) + pad * 2
    panel_h = sum(b[3] for b in blocks) + block_gap * (len(blocks) - 1) + pad * 2
    panel_x = margin
    panel_y = max(margin, height - margin - panel_h)

    # Compose the panel on an RGBA layer so it can be genuinely translucent -
    # drawing straight onto the frame would give a solid box.
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    radius = max(4, pad // 2)
    layer_draw.rounded_rectangle(
        [panel_x, panel_y, panel_x + panel_w, panel_y + panel_h],
        radius=radius, fill=(0, 0, 0, 140),
    )

    y = panel_y + pad
    for block_index, (lines, sizes, _block_w, _block_h) in enumerate(blocks):
        for line_index, ((text, font, colour), (_w, h)) in enumerate(zip(lines, sizes)):
            layer_draw.text((panel_x + pad, y), text, font=font, fill=colour)
            y += h
            if line_index < len(lines) - 1:
                y += line_gap
        if block_index < len(blocks) - 1:
            y += block_gap  # breathing room between stacked events

    # Composite, then paste back in the frame's own mode so the caller's image is
    # genuinely mutated (rebinding a converted copy would silently drop the overlay).
    composed = Image.alpha_composite(image.convert("RGBA"), layer)
    image.paste(composed.convert(image.mode), (0, 0))
    return image


def build_plan(date_dirs, frame_times, framerate, speed_multiplier=1,
               hold_seconds=4.0, since=None) -> Optional[EventOverlayPlan]:
    """Load a session's events and build its overlay plan.

    `date_dirs` is one folder or a sequence of them: a session that crossed the
    folder rollover has an events.jsonl in each folder it touched, and a merged
    render needs all of them stitched into one timeline. Folders without a log
    contribute nothing (read_events returns [] for a missing file).

    Returns None when the folder(s) have no usable events, so callers can skip
    the overlay path entirely.
    """
    if isinstance(date_dirs, (str, os.PathLike)):
        date_dirs = [date_dirs]
    events = [event for d in date_dirs for event in read_events(d, since=since)]
    events.sort(key=lambda event: event.time)
    if not events:
        return None
    plan = EventOverlayPlan(events, frame_times, framerate, speed_multiplier, hold_seconds)
    return None if plan.is_empty else plan
