"""
Unit tests for src/event_overlay.py (event captions burned into the timelapse).

Most of these pin down timing, which is the part that fails silently: captions
hold for a number of *output* frames, so a plan that reasons in source frames
looks fine until speed_multiplier > 1, at which point captions flash by too fast
or land on frames the export drops.

Frames here are 30s apart, matching the app's default capture interval.
"""

import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from event_log import EVENTS_FILENAME, SessionEvent  # noqa: E402
from event_overlay import (  # noqa: E402
    MAX_VISIBLE, EventOverlayPlan, build_plan, draw_captions, draw_target_label,
    format_timecode,
)

T0 = datetime(2026, 7, 25, 22, 0, 0)
FRAME_INTERVAL = 30  # seconds between captured frames


def frames(count: int):
    """Capture times for `count` frames, 30s apart from T0."""
    return [T0 + timedelta(seconds=FRAME_INTERVAL * i) for i in range(count)]


def event(minutes: float, title="Event", detail=None, category=None):
    return SessionEvent(T0 + timedelta(minutes=minutes), title, detail, category)


class FrameBindingTests(unittest.TestCase):
    """Which frame does an event land on?"""

    def test_event_binds_to_first_frame_at_or_after_it(self):
        # Frame 10 is at T0+5m; an event 10s later belongs to frame 11, the first
        # frame that could have witnessed it.
        plan = EventOverlayPlan([event(5.0), event(5.2)], frames(60), framerate=24)
        self.assertEqual(plan.captions[0].start_ordinal, 10)
        self.assertEqual(plan.captions[1].start_ordinal, 11)

    def test_event_exactly_on_a_frame_uses_that_frame(self):
        plan = EventOverlayPlan([event(5.0)], frames(60), framerate=24)
        self.assertEqual(plan.captions[0].start_ordinal, 10)

    def test_event_before_first_frame_binds_to_first(self):
        early = SessionEvent(T0 - timedelta(minutes=5), "Sequence Started")
        plan = EventOverlayPlan([early], frames(60), framerate=24)
        self.assertEqual(plan.captions[0].start_ordinal, 0)

    def test_event_after_last_frame_is_dropped(self):
        """Nothing left to label - the caption would never be seen."""
        late = SessionEvent(T0 + timedelta(hours=5), "Sequence Complete")
        plan = EventOverlayPlan([late], frames(60), framerate=24)
        self.assertTrue(plan.is_empty)

    def test_no_frames_means_no_captions(self):
        plan = EventOverlayPlan([event(5.0)], [], framerate=24)
        self.assertTrue(plan.is_empty)

    def test_events_sorted_regardless_of_input_order(self):
        plan = EventOverlayPlan(
            [event(20, "Third"), event(5, "First"), event(10, "Second")],
            frames(120), framerate=24,
        )
        self.assertEqual([c.title for c in plan.captions], ["First", "Second", "Third"])


class HoldDurationTests(unittest.TestCase):
    """How long does a caption stay up, and in which units?"""

    def test_hold_is_measured_in_output_frames(self):
        # 4s at 24fps = 96 output frames, inclusive of the first.
        plan = EventOverlayPlan([event(5)], frames(300), framerate=24, hold_seconds=4.0)
        caption = plan.captions[0]
        self.assertEqual(caption.end_ordinal - caption.start_ordinal + 1, 96)

    def test_hold_scales_with_framerate(self):
        plan = EventOverlayPlan([event(5)], frames(300), framerate=30, hold_seconds=4.0)
        caption = plan.captions[0]
        self.assertEqual(caption.end_ordinal - caption.start_ordinal + 1, 120)

    def test_caption_visible_across_its_whole_hold(self):
        plan = EventOverlayPlan([event(5)], frames(300), framerate=24, hold_seconds=4.0)
        self.assertEqual(len(plan.captions_for_index(10)), 1)   # first frame
        self.assertEqual(len(plan.captions_for_index(60)), 1)   # middle
        self.assertEqual(len(plan.captions_for_index(105)), 1)  # last
        self.assertEqual(len(plan.captions_for_index(106)), 0)  # expired
        self.assertEqual(len(plan.captions_for_index(9)), 0)    # not yet

    def test_hold_seconds_floor(self):
        """A zero/negative hold would make captions invisible; clamp instead."""
        plan = EventOverlayPlan([event(5)], frames(300), framerate=24, hold_seconds=0)
        self.assertGreaterEqual(
            plan.captions[0].end_ordinal - plan.captions[0].start_ordinal + 1, 1)


class SpeedMultiplierTests(unittest.TestCase):
    """The export's `select` filter keeps every Nth frame - timing must follow."""

    def test_start_ordinal_is_the_output_position(self):
        # Source frame 10 becomes output frame 5 at 2x.
        plan = EventOverlayPlan([event(5)], frames(300), framerate=24, speed_multiplier=2)
        self.assertEqual(plan.captions[0].start_ordinal, 5)

    def test_dropped_frames_get_no_captions(self):
        """Odd frames aren't rendered at 2x, so drawing on them would be wasted work."""
        plan = EventOverlayPlan([event(5)], frames(300), framerate=24,
                                speed_multiplier=2, hold_seconds=4.0)
        self.assertEqual(len(plan.captions_for_index(10)), 1)
        self.assertEqual(plan.captions_for_index(11), [])
        self.assertEqual(len(plan.captions_for_index(12)), 1)

    def test_caption_spans_same_video_duration_at_any_speed(self):
        """4 video seconds is 4 video seconds, whatever the speed.

        At 2x the caption covers twice the *range* of source frames, but only half
        of those survive the select filter - so the same number of frames are
        actually drawn on, and the caption occupies the same 4s of finished video.
        """
        kwargs = dict(framerate=24, hold_seconds=4.0)
        normal = EventOverlayPlan([event(5)], frames(600), speed_multiplier=1, **kwargs)
        fast = EventOverlayPlan([event(5)], frames(600), speed_multiplier=2, **kwargs)

        def drawn_indices(plan):
            return [i for i in range(600) if plan.captions_for_index(i)]

        normal_drawn, fast_drawn = drawn_indices(normal), drawn_indices(fast)

        # Same amount of drawing, same on-screen duration in the finished video.
        self.assertEqual(len(normal_drawn), 96)
        self.assertEqual(len(fast_drawn), 96)

        # ...but spread over twice as much captured footage.
        span = lambda drawn: drawn[-1] - drawn[0]  # noqa: E731
        self.assertEqual(span(fast_drawn), span(normal_drawn) * 2)

    def test_event_on_a_dropped_frame_still_appears(self):
        """Source frame 11 is dropped at 2x, but its caption must not vanish with it."""
        plan = EventOverlayPlan([event(5.2, "Autofocus")], frames(300), framerate=24,
                                speed_multiplier=2, hold_seconds=4.0)
        self.assertFalse(plan.is_empty)
        self.assertEqual(plan.captions[0].start_ordinal, 5)
        self.assertEqual([c.title for c in plan.captions_for_index(12)], ["Autofocus"])


class OverlapTests(unittest.TestCase):
    def test_overlapping_events_stack_oldest_first(self):
        plan = EventOverlayPlan(
            [event(5, "First"), event(5.5, "Second")],
            frames(300), framerate=24, hold_seconds=4.0,
        )
        self.assertEqual([c.title for c in plan.captions_for_index(12)], ["First", "Second"])

    def test_stack_capped_keeping_newest(self):
        """Beyond the cap the panel would swallow the frame; oldest drop off."""
        events = [event(5 + n * 0.1, f"Event {n}") for n in range(MAX_VISIBLE + 2)]
        plan = EventOverlayPlan(events, frames(300), framerate=24, hold_seconds=10.0)

        visible = [c.title for c in plan.captions_for_index(40)]
        self.assertEqual(len(visible), MAX_VISIBLE)
        self.assertEqual(visible[-1], f"Event {MAX_VISIBLE + 1}")


class TargetLabelTests(unittest.TestCase):
    """The target is state, not a moment: a standing corner label, not a caption."""

    def _plan(self, *targets, extra=()):
        events = [event(m, t, category="target") for m, t in targets] + list(extra)
        return EventOverlayPlan(events, frames(300), framerate=24, hold_seconds=4.0)

    def test_none_before_the_first_target(self):
        plan = self._plan((5, "Target: M31"))
        self.assertIsNone(plan.target_at_index(9))
        self.assertEqual(plan.target_at_index(10), "M31")

    def test_persists_long_after_the_change(self):
        """The whole point of a label over a caption - it doesn't expire."""
        plan = self._plan((5, "Target: M31"))
        self.assertEqual(plan.target_at_index(299), "M31")

    def test_switches_at_the_right_frame(self):
        plan = self._plan((5, "Target: M31"), (50, "Target: NGC 7000"))
        self.assertEqual(plan.target_at_index(99), "M31")
        self.assertEqual(plan.target_at_index(100), "NGC 7000")

    def test_prefix_stripped_for_the_label(self):
        """The plugin sends "Target: X" because that reads as a caption; the corner
        label has its own context, so the prefix would be redundant."""
        self.assertEqual(self._plan((5, "Target: G069.0+02.7")).target_at_index(10),
                         "G069.0+02.7")

    def test_name_without_a_prefix_survives(self):
        self.assertEqual(self._plan((5, "M31")).target_at_index(10), "M31")

    def test_consecutive_duplicates_collapse(self):
        plan = self._plan((5, "Target: M31"), (10, "Target: M31"))
        self.assertEqual(len(plan._target_names), 1)

    def test_targets_are_not_in_the_caption_stack(self):
        plan = self._plan((5, "Target: M31"), extra=[event(5, "Autofocus Complete")])
        titles = [c.title for c in plan.captions_for_index(10)]
        self.assertEqual(titles, ["Autofocus Complete"])

    def test_target_only_session_is_not_empty(self):
        """Otherwise the export would skip drawing and the label would never appear."""
        plan = self._plan((5, "Target: M31"))
        self.assertFalse(plan.is_empty)

    def test_targets_still_reach_the_csv(self):
        """Moving out of the caption stack must not drop them from the session log."""
        plan = self._plan((5, "Target: M31"), extra=[event(6, "Meridian Flip")])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.events.csv"
            self.assertEqual(plan.write_csv(path), 2)
            with open(path, encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual([r["title"] for r in rows], ["Target: M31", "Meridian Flip"])
        self.assertEqual(rows[0]["category"], "target")

    def test_no_targets_at_all(self):
        plan = EventOverlayPlan([event(5, "Autofocus Complete")], frames(300), framerate=24)
        self.assertIsNone(plan.target_at_index(10))


class TargetDrawingTests(unittest.TestCase):
    def test_draws_bottom_right_and_mutates(self):
        from PIL import Image

        image = Image.new("RGB", (1280, 720), (20, 30, 50))
        before = image.tobytes()
        draw_target_label(image, "G069.0+02.7")
        self.assertNotEqual(image.tobytes(), before)

        # Bottom-right: the lower-right quadrant must change, the upper-left must not.
        w, h = image.size
        self.assertNotEqual(image.crop((w // 2, h // 2, w, h)).tobytes(),
                            Image.new("RGB", (w // 2, h // 2), (20, 30, 50)).tobytes())
        self.assertEqual(image.crop((0, 0, w // 2, h // 2)).tobytes(),
                         Image.new("RGB", (w // 2, h // 2), (20, 30, 50)).tobytes())

    def test_no_target_is_a_no_op(self):
        from PIL import Image

        image = Image.new("RGB", (640, 360), (20, 30, 50))
        before = image.tobytes()
        draw_target_label(image, None)
        draw_target_label(image, "")
        self.assertEqual(image.tobytes(), before)

    def test_scales_across_frame_sizes(self):
        from PIL import Image

        for size in ((320, 180), (1920, 1080), (3840, 2160)):
            image = Image.new("RGB", size, (20, 30, 50))
            before = image.tobytes()
            draw_target_label(image, "M31")
            self.assertNotEqual(image.tobytes(), before, f"nothing drawn at {size}")

    def test_coexists_with_captions(self):
        """Both are drawn on the same frame without one wiping the other."""
        from PIL import Image

        plan = EventOverlayPlan(
            [event(5, "Target: M31", category="target"),
             event(5, "Autofocus Complete", "HFR 2.31 -> 1.62", "autofocus")],
            frames(300), framerate=24, hold_seconds=4.0,
        )
        image = Image.new("RGB", (1280, 720), (20, 30, 50))
        draw_captions(image, plan.captions_for_index(10))
        after_captions = image.tobytes()
        draw_target_label(image, plan.target_at_index(10))
        self.assertNotEqual(image.tobytes(), after_captions)


class TimecodeAndCsvTests(unittest.TestCase):
    def test_format_timecode(self):
        self.assertEqual(format_timecode(0), "00:00:00.0")
        self.assertEqual(format_timecode(83.5), "00:01:23.5")
        self.assertEqual(format_timecode(3661.2), "01:01:01.2")
        self.assertEqual(format_timecode(-5), "00:00:00.0")

    def test_video_seconds_matches_output_position(self):
        plan = EventOverlayPlan([event(5)], frames(300), framerate=24)
        # Source frame 10 -> output frame 10 -> 10/24 s into the video.
        self.assertAlmostEqual(plan.captions[0].video_seconds(24), 10 / 24.0)

    def test_csv_has_wall_clock_and_video_timecode(self):
        plan = EventOverlayPlan(
            [event(5, "Autofocus Complete", "HFR 2.31 -> 1.62", "autofocus")],
            frames(300), framerate=24,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "timelapse.events.csv"
            self.assertEqual(plan.write_csv(path), 1)

            with open(path, encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["wall_clock"], "2026-07-25 22:05:00")
        self.assertEqual(rows[0]["video_timecode"], format_timecode(10 / 24.0))
        self.assertEqual(rows[0]["category"], "autofocus")
        self.assertEqual(rows[0]["title"], "Autofocus Complete")
        self.assertEqual(rows[0]["detail"], "HFR 2.31 -> 1.62")

    def test_csv_omits_events_outside_the_render(self):
        """The CSV describes the video, so it lists what's actually in it."""
        included = event(5, "Included")
        excluded = SessionEvent(T0 + timedelta(hours=9), "After the last frame")
        plan = EventOverlayPlan([included, excluded], frames(60), framerate=24)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.events.csv"
            self.assertEqual(plan.write_csv(path), 1)
            with open(path, encoding="utf-8", newline="") as f:
                titles = [row["title"] for row in csv.DictReader(f)]

        self.assertEqual(titles, ["Included"])


class BuildPlanTests(unittest.TestCase):
    """build_plan() reads a session folder and returns None when there's nothing to draw."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_events(self, *records):
        with open(self.dir / EVENTS_FILENAME, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

    def test_returns_none_when_no_log(self):
        self.assertIsNone(build_plan(self.dir, frames(60), framerate=24))

    def test_returns_none_when_no_event_in_range(self):
        self._write_events({"time": "20270101-000000", "title": "Next year"})
        self.assertIsNone(build_plan(self.dir, frames(60), framerate=24))

    def test_builds_plan_from_log(self):
        self._write_events(
            {"time": "20260725-220500", "title": "Autofocus Complete",
             "detail": "HFR 2.31 -> 1.62", "category": "autofocus"},
            {"time": "20260725-221000", "title": "Meridian Flip"},
        )
        plan = build_plan(self.dir, frames(120), framerate=24)
        self.assertEqual([c.title for c in plan.captions],
                         ["Autofocus Complete", "Meridian Flip"])

    def test_since_filters_out_an_earlier_session(self):
        """Two sessions can share a date folder; only this one's events belong."""
        self._write_events(
            {"time": "20260725-180000", "title": "Earlier test run"},
            {"time": "20260725-220500", "title": "Tonight"},
        )
        plan = build_plan(self.dir, frames(120), framerate=24,
                          since=datetime(2026, 7, 25, 21, 0, 0))
        self.assertEqual([c.title for c in plan.captions], ["Tonight"])


class DrawingTests(unittest.TestCase):
    """Smoke tests - the drawing is visual, so these check it runs and mutates."""

    def setUp(self):
        self.plan = EventOverlayPlan(
            [event(5, "Autofocus Complete", "HFR 2.31 -> 1.62", "autofocus")],
            frames(300), framerate=24, hold_seconds=4.0,
        )
        self.captions = self.plan.captions_for_index(10)

    def test_draws_and_mutates_in_place(self):
        from PIL import Image

        image = Image.new("RGB", (1280, 720), (20, 30, 50))
        before = image.tobytes()
        returned = draw_captions(image, self.captions)

        self.assertIsNotNone(returned)
        self.assertNotEqual(image.tobytes(), before, "overlay did not reach the caller's image")

    def test_no_captions_leaves_image_untouched(self):
        from PIL import Image

        image = Image.new("RGB", (640, 360), (20, 30, 50))
        before = image.tobytes()
        draw_captions(image, [])
        self.assertEqual(image.tobytes(), before)

    def test_handles_small_and_large_frames(self):
        from PIL import Image

        for size in ((320, 180), (1920, 1080), (3840, 2160)):
            image = Image.new("RGB", size, (20, 30, 50))
            before = image.tobytes()
            draw_captions(image, self.captions)
            self.assertNotEqual(image.tobytes(), before, f"nothing drawn at {size}")

    def test_stacked_captions_draw(self):
        from PIL import Image

        plan = EventOverlayPlan(
            [event(5, "First", "detail one"), event(5.2, "Second", "detail two")],
            frames(300), framerate=24, hold_seconds=4.0,
        )
        image = Image.new("RGB", (1280, 720), (20, 30, 50))
        before = image.tobytes()
        draw_captions(image, plan.captions_for_index(12))
        self.assertNotEqual(image.tobytes(), before)


if __name__ == "__main__":
    unittest.main()
