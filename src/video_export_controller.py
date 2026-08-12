"""
Video Export Controller - Business logic for video export
Phase 3.5: Video Export Feature

Handles image scanning, export preparation, and video creation orchestration.
"""

import os
import shutil
import threading
import time
from pathlib import Path
from typing import Optional, Tuple, List, Callable, Dict, Any, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import re

from ffmpeg_wrapper import FFmpegWrapper, ProgressInfo
from preset_manager import VideoExportSettings
from event_overlay import build_plan, draw_captions, draw_target_label
from event_log import EVENTS_FILENAME

# A .temp_export_* folder older than this is an abandoned leftover (its export is
# long over) and gets swept before the next export. Generous on purpose: no encode
# runs this long, so a live export's folder is never touched.
STALE_TEMP_AGE_SECONDS = 3600


@dataclass
class ImageCollection:
    """Container for scanned image information"""
    images: List[Path]
    total_count: int
    first_timestamp: Optional[datetime]
    last_timestamp: Optional[datetime]
    duration_seconds: float
    total_size_bytes: int
    source_folder: Path
    # Capture time per image, index-aligned with `images` (None where the filename
    # didn't parse). Event overlays bind events to frames through this.
    timestamps: List[Optional[datetime]] = field(default_factory=list)
    # Every folder that contributed frames, ascending. A session that crossed the
    # folder rollover spans more than one; single-folder scans hold just their own.
    # Consumers should read `source_folders or [source_folder]` for back-compat.
    source_folders: List[Path] = field(default_factory=list)

    def get_date_range_str(self) -> str:
        """Get formatted date range string"""
        if self.first_timestamp and self.last_timestamp:
            start = self.first_timestamp.strftime("%Y-%m-%d %H:%M:%S")
            end = self.last_timestamp.strftime("%Y-%m-%d %H:%M:%S")
            return f"{start} to {end}"
        return "Unknown"

    def get_duration_str(self) -> str:
        """Get formatted duration string"""
        hours = int(self.duration_seconds // 3600)
        minutes = int((self.duration_seconds % 3600) // 60)
        seconds = int(self.duration_seconds % 60)
        return f"{hours}h {minutes}m {seconds}s"

    def get_size_str(self) -> str:
        """Get formatted total size string"""
        mb = self.total_size_bytes / (1024 * 1024)
        if mb >= 1024:
            gb = mb / 1024
            return f"{gb:.2f} GB"
        return f"{mb:.2f} MB"


@dataclass
class ExportJob:
    """Container for export job configuration"""
    settings: VideoExportSettings
    image_collection: ImageCollection
    output_file: Path
    temp_folder: Optional[Path]
    use_temp_copies: bool
    # Session events resolved onto this export's frames, or None when the session
    # logged none. Present regardless of draw_captions - it also drives the CSV.
    overlay_plan: Optional[Any] = None
    # Whether to burn the captions into the frames (config: ui.event_overlay).
    draw_captions: bool = False
    # Whether to write <video>.events.csv beside the render (config: ui.event_csv).
    write_events_csv: bool = False


@dataclass
class ExportResult:
    """Container for export result"""
    success: bool
    message: str
    output_file: Optional[Path]
    duration_seconds: float
    output_size_bytes: int


class VideoExportController:
    """Handles video export logic and orchestration"""

    def __init__(self, ffmpeg_wrapper: Optional[FFmpegWrapper] = None):
        """
        Initialize controller

        Args:
            ffmpeg_wrapper: FFmpegWrapper instance (creates new one if None)
        """
        self.ffmpeg_wrapper = ffmpeg_wrapper or FFmpegWrapper()
        self.is_exporting = False
        self.cancel_requested = False
        self.current_thread: Optional[threading.Thread] = None

    def check_ffmpeg(self) -> Tuple[bool, str]:
        """
        Check if FFmpeg is available

        Returns:
            (is_available, message) tuple
        """
        is_installed, version = self.ffmpeg_wrapper.check_installation()
        if is_installed:
            return True, f"FFmpeg ready: {version}"
        else:
            return False, "FFmpeg not found. Please install FFmpeg to use video export."

    def scan_folder(self, folder_path: Path, since: Optional[datetime] = None) -> Tuple[bool, Optional[ImageCollection], str]:
        """
        Scan folder for images and extract metadata

        Args:
            folder_path: Path to folder containing images
            since: If set, only include frames captured at/after this time
                (filenames are YYYYMMDD-HHMMSS). Lets a single session be rendered
                even when several sessions share one date folder.

        Returns:
            (success, ImageCollection, message) tuple
        """
        try:
            folder = Path(folder_path)

            if not folder.exists():
                return False, None, f"Folder not found: {folder_path}"

            if not folder.is_dir():
                return False, None, f"Not a directory: {folder_path}"

            # Find all jpg files
            images = sorted(folder.glob("*.jpg"))

            if len(images) == 0:
                return False, None, f"No .jpg files found in {folder_path}"

            # Optionally keep only frames captured at/after `since`.
            if since is not None:
                filtered = []
                for img in images:
                    ts = self._extract_timestamp(img)
                    if ts is not None and ts >= since:
                        filtered.append(img)
                images = filtered
                if not images:
                    return False, None, f"No images captured at/after {since:%Y%m%d-%H%M%S}"

            # Extract timestamps from filenames (format: YYYYMMDD-HHMMSS.jpg).
            # Kept per-image as well as first/last: event overlays need to know
            # when each individual frame was captured.
            timestamps = [self._extract_timestamp(img) for img in images]
            first_timestamp = timestamps[0]
            last_timestamp = timestamps[-1]

            # Calculate duration
            duration_seconds = 0
            if first_timestamp and last_timestamp:
                duration_seconds = (last_timestamp - first_timestamp).total_seconds()

            # Calculate total size
            total_size = sum(img.stat().st_size for img in images)

            collection = ImageCollection(
                images=images,
                total_count=len(images),
                first_timestamp=first_timestamp,
                last_timestamp=last_timestamp,
                duration_seconds=duration_seconds,
                total_size_bytes=total_size,
                source_folder=folder,
                timestamps=timestamps,
                source_folders=[folder]
            )

            return True, collection, f"Found {len(images)} images"

        except Exception as e:
            return False, None, f"Error scanning folder: {str(e)}"

    def scan_folders(self, folder_paths: Sequence[Path],
                     since: Optional[datetime] = None) -> Tuple[bool, Optional[ImageCollection], str]:
        """Scan several date folders and merge them into one collection.

        The session-aware render path uses this when a session may span the
        folder rollover boundary: every folder from the session's start onward
        is scanned with the same `since` filter and stitched into one video.

        A folder that contributes nothing (missing, no .jpg files, or nothing
        at/after `since`) is skipped rather than treated as an error - only an
        overall empty result fails.

        Returns:
            (success, ImageCollection, message) tuple, same contract as scan_folder.
        """
        merged_images: List[Path] = []
        merged_timestamps: List[Optional[datetime]] = []
        contributing: List[Path] = []
        for folder_path in folder_paths:
            ok, collection, _msg = self.scan_folder(folder_path, since=since)
            if not ok:
                continue
            merged_images.extend(collection.images)
            merged_timestamps.extend(collection.timestamps)
            contributing.append(Path(folder_path))

        if not merged_images:
            if since is not None:
                return False, None, (f"No images captured at/after {since:%Y%m%d-%H%M%S} "
                                     f"in {len(folder_paths)} folder(s)")
            return False, None, f"No .jpg files found in {len(folder_paths)} folder(s)"

        # Order by capture time when every frame has one - always true with `since`,
        # which drops unparseable names. Otherwise keep folder order (ascending
        # folders, name-sorted within each): a partial sort would misorder frames.
        if all(ts is not None for ts in merged_timestamps):
            pairs = sorted(zip(merged_images, merged_timestamps), key=lambda pair: pair[1])
            merged_images = [img for img, _ in pairs]
            merged_timestamps = [ts for _, ts in pairs]

        first_timestamp = merged_timestamps[0]
        last_timestamp = merged_timestamps[-1]
        duration_seconds = 0
        if first_timestamp and last_timestamp:
            duration_seconds = (last_timestamp - first_timestamp).total_seconds()

        merged = ImageCollection(
            images=merged_images,
            total_count=len(merged_images),
            first_timestamp=first_timestamp,
            last_timestamp=last_timestamp,
            duration_seconds=duration_seconds,
            total_size_bytes=sum(img.stat().st_size for img in merged_images),
            source_folder=contributing[0],
            timestamps=merged_timestamps,
            source_folders=contributing
        )

        message = f"Found {len(merged_images)} images"
        if len(contributing) > 1:
            message += f" across {len(contributing)} folders"
        return True, merged, message

    def _extract_timestamp(self, image_path: Path) -> Optional[datetime]:
        """
        Extract timestamp from image filename

        Expected format: YYYYMMDD-HHMMSS.jpg or similar

        Args:
            image_path: Path to image file

        Returns:
            datetime object or None if couldn't parse
        """
        try:
            # Try to match YYYYMMDD-HHMMSS pattern
            match = re.search(r'(\d{8})-(\d{6})', image_path.stem)
            if match:
                date_str = match.group(1)
                time_str = match.group(2)
                datetime_str = f"{date_str}{time_str}"
                return datetime.strptime(datetime_str, "%Y%m%d%H%M%S")
        except Exception:
            pass

        return None

    def prepare_export(
        self,
        settings: VideoExportSettings,
        image_collection: ImageCollection,
        output_file: Path,
        since: Optional[datetime] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        event_overlay: bool = False,
        event_overlay_seconds: float = 4.0,
        event_csv: bool = False
    ) -> Tuple[bool, Optional[ExportJob], str]:
        """
        Prepare for export (validate, create temp folder if needed)

        Args:
            settings: Video export settings (encoding choices, from the preset)
            image_collection: Collection of images to export
            output_file: Output video file path
            since: same `since` used to scan the folder, so the overlay covers
                only the events belonging to this session
            log_callback: optional callback for informational messages
            event_overlay: burn session events in as captions. Passed separately
                rather than living on `settings` because it's an app preference in
                config/app_config.json, not a preset field - callers read it from
                config so both the manual and unattended render paths agree.
            event_overlay_seconds: caption hold time, in seconds of finished video
            event_csv: write <video>.events.csv beside the render. Independent of
                event_overlay - the log is useful without captions, and vice versa.

        Returns:
            (success, ExportJob, message) tuple
        """
        try:
            # Validate settings
            if settings.framerate <= 0:
                return False, None, "Invalid framerate"

            if settings.quality < 0 or settings.quality > 51:
                return False, None, "Quality (CRF) must be between 0 and 51"

            # Check output folder exists
            output_folder = output_file.parent
            if not output_folder.exists():
                output_folder.mkdir(parents=True, exist_ok=True)

            # Build the event-caption plan before deciding on temp copies - whether
            # anything gets drawn determines whether temp copies are mandatory.
            overlay_plan = self._build_overlay_plan(
                image_collection, since, settings.framerate, settings.speed_multiplier,
                event_overlay, event_overlay_seconds, event_csv, log_callback)

            # Determine if we need temp folder
            temp_folder = None
            use_temp_copies = settings.preserve_originals

            # Captions are drawn onto the copies, so overlays require the temp-copy
            # path. Every built-in preset already enables it, so this is a safety net
            # for a hand-edited preset rather than a normal occurrence - but it is
            # logged, because silently ignoring the overlay setting would be worse.
            draws_captions = overlay_plan is not None and event_overlay
            if draws_captions and not use_temp_copies:
                use_temp_copies = True
                if log_callback:
                    log_callback("Event overlays need temporary copies - "
                                 "'preserve originals' enabled for this export")

            # Same kind of safety net for merged collections: the non-temp path
            # feeds ffmpeg a single %06d pattern inside source_folder, which can't
            # represent frames living in more than one folder.
            source_folders = image_collection.source_folders or [image_collection.source_folder]
            if len(source_folders) > 1 and not use_temp_copies:
                use_temp_copies = True
                if log_callback:
                    log_callback("Multi-folder render needs temporary copies - "
                                 "'preserve originals' enabled for this export")

            if use_temp_copies:
                # Sweep leftovers whose cleanup lost the race against an external
                # handle (see _cleanup_temp), then create this export's own folder.
                self._sweep_stale_temp_folders(output_folder, log_callback)
                # Create temp folder in same directory as output
                temp_folder = output_folder / f".temp_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                temp_folder.mkdir(parents=True, exist_ok=True)

            job = ExportJob(
                settings=settings,
                image_collection=image_collection,
                output_file=output_file,
                temp_folder=temp_folder,
                use_temp_copies=use_temp_copies,
                overlay_plan=overlay_plan,
                draw_captions=draws_captions,
                write_events_csv=event_csv
            )

            return True, job, "Export prepared"

        except Exception as e:
            return False, None, f"Error preparing export: {str(e)}"

    def _build_overlay_plan(
        self,
        image_collection: ImageCollection,
        since: Optional[datetime],
        framerate: int,
        speed_multiplier: int,
        event_overlay: bool,
        hold_seconds: float,
        event_csv: bool,
        log_callback: Optional[Callable[[str], None]]
    ):
        """Build the event plan for this export, or None if there's nothing to use it for.

        Built when *either* consumer wants it: captions burn it into the frames, and
        the companion CSV is useful on its own for correlating a session against the
        footage. With both off there's nothing to do, so the event log isn't even read.
        """
        if not event_overlay and not event_csv:
            return None

        # Every frame needs a capture time for events to be bound to it. The app's own
        # filenames always parse; a foreign .jpg dropped into the folder may not, and a
        # partial list would misalign captions - so skip overlays and say why.
        timestamps = image_collection.timestamps
        if len(timestamps) != image_collection.total_count or not all(timestamps):
            if log_callback:
                log_callback("Event overlays skipped: some frames have no timestamp in "
                             "their filename (expected YYYYMMDD-HHMMSS.jpg)")
            return None

        try:
            plan = build_plan(
                image_collection.source_folders or [image_collection.source_folder],
                timestamps,
                framerate=framerate,
                speed_multiplier=speed_multiplier,
                hold_seconds=hold_seconds,
                since=since,
            )
        except Exception as e:
            # An unreadable event log must not fail the video the user actually asked for.
            if log_callback:
                log_callback(f"Event overlays skipped: could not read event log ({e})")
            return None

        if plan is None and log_callback and event_overlay:
            log_callback("Event overlays enabled, but this session logged no events in range")
        return plan

    def export_video(
        self,
        job: ExportJob,
        progress_callback: Optional[Callable[[str, float, Optional[ProgressInfo]], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> ExportResult:
        """
        Execute video export (blocking call)

        Args:
            job: Export job configuration
            progress_callback: Callback(status_text, progress_percent, ffmpeg_progress_info)
            log_callback: Callback for log messages

        Returns:
            ExportResult object
        """
        start_time = datetime.now()
        self.is_exporting = True
        self.cancel_requested = False

        try:
            # Step 1: Prepare images (copy/rename if needed)
            if progress_callback:
                progress_callback("Preparing images...", 0, None)

            if job.use_temp_copies:
                success, msg = self._prepare_temp_images(job, progress_callback, log_callback)
                if not success:
                    return ExportResult(False, msg, None, 0, 0)

                input_pattern = str(job.temp_folder / "%06d.jpg")
            else:
                # Use original images directly (assumes they're already numbered)
                input_pattern = str(job.image_collection.source_folder / "%06d.jpg")

            if self.cancel_requested:
                self._cleanup_temp(job, log_callback)
                return ExportResult(False, "Export cancelled by user", None, 0, 0)

            # Step 2: Build FFmpeg command
            if progress_callback:
                progress_callback("Building FFmpeg command...", 10, None)

            if log_callback:
                log_callback("Building FFmpeg command...")

            command = self.ffmpeg_wrapper.build_command(
                input_pattern=input_pattern,
                output_file=str(job.output_file),
                framerate=job.settings.framerate,
                quality=job.settings.quality,
                resolution=job.settings.resolution if job.settings.resolution != 'original' else None,
                speed_multiplier=job.settings.speed_multiplier,
                add_timestamp=job.settings.add_timestamp,
                codec=job.settings.codec
            )

            if log_callback:
                log_callback(f"FFmpeg command: {' '.join(command)}")

            # Step 3: Run FFmpeg
            if progress_callback:
                progress_callback("Encoding video...", 15, None)

            if log_callback:
                log_callback("Starting FFmpeg encoding...")

            # Calculate total frames to process
            total_frames = job.image_collection.total_count // job.settings.speed_multiplier

            def ffmpeg_progress_callback(info: ProgressInfo):
                """Wrapper for FFmpeg progress"""
                if self.cancel_requested:
                    return

                # Map frame progress to 15-95% range
                percent = 15 + (info.progress_percent * 0.8)
                status = f"Encoding: frame {info.frame}/{total_frames} ({info.fps:.1f} fps)"

                if progress_callback:
                    progress_callback(status, percent, info)

            success, msg = self.ffmpeg_wrapper.run(
                command=command,
                progress_callback=ffmpeg_progress_callback,
                total_frames=total_frames
            )

            if not success:
                self._cleanup_temp(job, log_callback)
                return ExportResult(False, f"FFmpeg failed: {msg}", None, 0, 0)

            if self.cancel_requested:
                self._cleanup_temp(job, log_callback)
                return ExportResult(False, "Export cancelled by user", None, 0, 0)

            # Step 4: Finalize
            if progress_callback:
                progress_callback("Finalizing...", 95, None)

            # Companion event log beside the video (issue #15 item 5).
            self._write_event_csv(job, log_callback)

            # Clean up temp folder if used
            if job.temp_folder and job.temp_folder.exists():
                if log_callback:
                    log_callback("Cleaning up temporary files...")
                self._cleanup_temp(job, log_callback)

            # Get output file size
            output_size = job.output_file.stat().st_size if job.output_file.exists() else 0

            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()

            if progress_callback:
                progress_callback("Complete!", 100, None)

            if log_callback:
                log_callback(f"Export complete: {job.output_file}")
                log_callback(f"Output size: {output_size / (1024*1024):.2f} MB")
                log_callback(f"Duration: {duration:.1f} seconds")

            self.is_exporting = False

            return ExportResult(
                success=True,
                message=f"Video exported successfully in {duration:.1f}s",
                output_file=job.output_file,
                duration_seconds=duration,
                output_size_bytes=output_size
            )

        except Exception as e:
            self._cleanup_temp(job, log_callback)
            self.is_exporting = False
            return ExportResult(False, f"Export error: {str(e)}", None, 0, 0)

    def _prepare_temp_images(
        self,
        job: ExportJob,
        progress_callback: Optional[Callable],
        log_callback: Optional[Callable]
    ) -> Tuple[bool, str]:
        """
        Copy and rename images to temp folder

        Args:
            job: Export job
            progress_callback: Progress callback
            log_callback: Log callback

        Returns:
            (success, message) tuple
        """
        try:
            # The plan is built whenever the session logged events (it also drives the
            # companion CSV); drawing is what the user's overlay setting controls.
            plan = job.overlay_plan if job.draw_captions else None
            if log_callback:
                what = "Copying" if plan is None else "Copying (with event captions)"
                log_callback(f"{what} {job.image_collection.total_count} images to temp folder...")

            total = job.image_collection.total_count
            drawn = 0

            for i, src_image in enumerate(job.image_collection.images):
                if self.cancel_requested:
                    return False, "Cancelled"

                dst_image = job.temp_folder / f"{i:06d}.jpg"

                # Frames with nothing to draw take the plain copy path. Note that a
                # session with a target loses that fast path: the corner label is on
                # every frame by definition, so every frame gets re-encoded.
                captions = plan.captions_for_index(i) if plan else None
                target = plan.target_at_index(i) if plan else None
                if captions or target:
                    self._copy_with_captions(src_image, dst_image, captions, target)
                    drawn += 1
                else:
                    shutil.copy2(src_image, dst_image)

                # Update progress
                if progress_callback and i % 10 == 0:  # Update every 10 files
                    percent = (i / total) * 10  # 0-10% range
                    progress_callback(f"Copying images: {i}/{total}", percent, None)

            if log_callback:
                log_callback(f"Copied {total} images to {job.temp_folder}")
                if drawn:
                    log_callback(f"Drew event captions on {drawn} frames")

            return True, "Images prepared"

        except Exception as e:
            return False, f"Error preparing images: {str(e)}"

    def _copy_with_captions(self, src_image: Path, dst_image: Path, captions, target=None):
        """Write a copy of `src_image` with event captions and/or the target label burned in.

        Falls back to a plain copy if the image can't be opened or drawn on: a frame
        without its caption is a far better outcome than a failed export.
        """
        try:
            from PIL import Image

            with Image.open(src_image) as img:
                img.load()
                frame = img.convert("RGB") if img.mode != "RGB" else img.copy()
            if captions:
                draw_captions(frame, captions)
            draw_target_label(frame, target)
            # JPEG quality here is intentionally high and independent of the CRF
            # setting - this is an intermediate that FFmpeg re-encodes, so the only
            # goal is not to add visible loss before it gets there.
            frame.save(dst_image, "JPEG", quality=95)
        except Exception:
            shutil.copy2(src_image, dst_image)

    def _write_event_csv(self, job: ExportJob, log_callback: Optional[Callable[[str], None]]):
        """Write <video_stem>.events.csv next to the finished video.

        Best-effort: the video is the deliverable, so a failure here is logged and
        swallowed rather than turned into a failed export.
        """
        if not job.write_events_csv or job.overlay_plan is None:
            return
        # Built by hand rather than with_suffix(): a filename containing dots
        # ("timelapse_2026.07.25.mp4") would have the wrong part replaced.
        csv_path = job.output_file.parent / (job.output_file.stem + ".events.csv")
        try:
            rows = job.overlay_plan.write_csv(csv_path)
            if log_callback:
                log_callback(f"Wrote {rows} events to {csv_path.name}")
        except OSError as e:
            if log_callback:
                log_callback(f"Could not write event CSV: {e}")

    @staticmethod
    def delete_rendered_snapshots(images: Sequence[Path],
                                  log_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Delete exactly the frames that went into a video, then any folder they emptied.

        The single implementation of this, shared by the scheduler, the remote API and
        the Video Export tab, so a destructive action can't drift between the paths.
        Deleting the rendered list rather than a folder means a `since`-filtered render
        (one session among several sharing a folder) never removes frames that were
        not in the video.

        A folder is removed once nothing but its events.jsonl remains - by then the
        events are already preserved in the video overlay/CSV if those are on. A
        folder still holding other frames is kept, events.jsonl included, so a later
        render of those frames can still use it. (A folder holding only an
        events.jsonl and no frames is never visited here - it contributed nothing.)

        Best-effort by design: the video is the deliverable, so a failed cleanup is
        logged rather than turned into a failed export. A file that's already gone
        counts as success - the caller's intent was "it shouldn't be there".

        Args:
            images: the rendered frame paths (ImageCollection.images).
            log_callback: optional callable(str) for progress/error messages.

        Returns:
            True if every listed file, and every folder it emptied, is gone afterwards.
        """
        def log(message: str):
            if log_callback:
                log_callback(message)

        ok = True
        folders: List[Path] = []
        for image in images:
            path = Path(image)
            if path.parent not in folders:
                folders.append(path.parent)
            try:
                path.unlink(missing_ok=True)
            except OSError as e:
                log(f"Failed to delete {path.name}: {e}")
                ok = False

        for folder in folders:
            if not folder.exists():
                continue
            try:
                leftovers = [p for p in folder.iterdir() if p.name != EVENTS_FILENAME]
                if leftovers:
                    log(f"Kept folder {folder}: {len(leftovers)} file(s) were not part of this video")
                    continue
                log(f"Deleting snapshot folder: {folder}")
                shutil.rmtree(folder)
                log("Snapshot folder deleted")
            except OSError as e:
                log(f"Failed to delete snapshot folder: {e}")
                ok = False
        return ok

    def _cleanup_temp(self, job: ExportJob,
                      log_callback: Optional[Callable[[str], None]] = None):
        """Remove the export's temp folder, retrying briefly.

        On Windows the final directory delete can fail while an external process
        (indexer, AV scan, folder sync) briefly holds a handle on it - the copies
        inside are removed but the empty folder stays behind forever. Retry a
        couple of times; if it still won't go, say so instead of failing silently,
        and leave it for the next export's stale-folder sweep.
        """
        if not job.temp_folder or not job.temp_folder.exists():
            return
        for attempt in range(3):
            try:
                shutil.rmtree(job.temp_folder)
                return
            except OSError:
                if attempt < 2:
                    time.sleep(1)
        if log_callback:
            log_callback(f"Could not remove temp folder {job.temp_folder.name} - "
                         "it will be swept on the next render")

    def _sweep_stale_temp_folders(self, output_folder: Path,
                                  log_callback: Optional[Callable[[str], None]] = None):
        """Remove abandoned .temp_export_* folders left by earlier exports.

        A cleanup that lost the race against an external handle leaves an empty
        folder behind (one per render, forever); sweeping here makes the leak
        self-healing. Only folders older than STALE_TEMP_AGE_SECONDS are touched,
        so a concurrent export's live folder is never at risk. Best-effort: a
        folder that still won't delete is left for the next sweep.
        """
        try:
            candidates = list(output_folder.glob(".temp_export_*"))
        except OSError:
            return
        now = time.time()
        for folder in candidates:
            try:
                if not folder.is_dir():
                    continue
                if now - folder.stat().st_mtime < STALE_TEMP_AGE_SECONDS:
                    continue
                shutil.rmtree(folder)
                if log_callback:
                    log_callback(f"Removed stale temp folder {folder.name}")
            except OSError:
                pass

    def cancel_export(self):
        """Request cancellation of current export"""
        self.cancel_requested = True

    def export_video_async(
        self,
        job: ExportJob,
        completion_callback: Callable[[ExportResult], None],
        progress_callback: Optional[Callable[[str, float, Optional[ProgressInfo]], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Execute video export asynchronously

        Args:
            job: Export job configuration
            completion_callback: Called when export completes
            progress_callback: Callback for progress updates
            log_callback: Callback for log messages
        """
        def export_thread():
            result = self.export_video(job, progress_callback, log_callback)
            completion_callback(result)

        self.current_thread = threading.Thread(target=export_thread, daemon=True)
        self.current_thread.start()

    def estimate_duration(self, image_count: int, framerate: int, speed: int) -> float:
        """
        Calculate estimated video duration

        Args:
            image_count: Number of images
            framerate: Output framerate
            speed: Speed multiplier

        Returns:
            Duration in seconds
        """
        effective_frames = image_count / speed
        return effective_frames / framerate

    def estimate_filesize(
        self,
        image_count: int,
        resolution: str,
        quality: int,
        framerate: int,
        sample_image: Optional[Path] = None
    ) -> float:
        """
        Estimate output file size

        Args:
            image_count: Number of images
            resolution: Target resolution string
            quality: CRF quality value
            framerate: Output framerate
            sample_image: Optional sample image to get actual resolution

        Returns:
            Estimated size in MB
        """
        # Determine resolution
        width, height = 1920, 1080  # Default

        if resolution and resolution != 'original':
            try:
                parts = resolution.split('x')
                width = int(parts[0])
                height = int(parts[1])
            except:
                pass

        # Use sample image to get actual resolution if available
        if sample_image and sample_image.exists():
            try:
                from PIL import Image
                with Image.open(sample_image) as img:
                    width, height = img.size
            except:
                pass

        return self.ffmpeg_wrapper.estimate_output_size(
            num_frames=image_count,
            resolution=(width, height),
            quality=quality,
            framerate=framerate
        )

    def get_available_date_folders(self, snapshots_dir: Path) -> List[Path]:
        """
        Get list of date folders in snapshots directory

        Args:
            snapshots_dir: Path to snapshots directory

        Returns:
            List of date folder paths
        """
        if not snapshots_dir.exists():
            return []

        date_folders = []
        for item in snapshots_dir.iterdir():
            if item.is_dir() and re.match(r'\d{8}', item.name):
                date_folders.append(item)

        return sorted(date_folders, reverse=True)  # Most recent first
