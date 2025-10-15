"""
Video Export Controller - Business logic for video export
Phase 3.5: Video Export Feature

Handles image scanning, export preparation, and video creation orchestration.
"""

import os
import shutil
import threading
from pathlib import Path
from typing import Optional, Tuple, List, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import re

from ffmpeg_wrapper import FFmpegWrapper, ProgressInfo
from preset_manager import VideoExportSettings


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

    def scan_folder(self, folder_path: Path) -> Tuple[bool, Optional[ImageCollection], str]:
        """
        Scan folder for images and extract metadata

        Args:
            folder_path: Path to folder containing images

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

            # Extract timestamps from filenames (format: YYYYMMDD-HHMMSS.jpg)
            first_timestamp = self._extract_timestamp(images[0])
            last_timestamp = self._extract_timestamp(images[-1])

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
                source_folder=folder
            )

            return True, collection, f"Found {len(images)} images"

        except Exception as e:
            return False, None, f"Error scanning folder: {str(e)}"

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
        output_file: Path
    ) -> Tuple[bool, Optional[ExportJob], str]:
        """
        Prepare for export (validate, create temp folder if needed)

        Args:
            settings: Video export settings
            image_collection: Collection of images to export
            output_file: Output video file path

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

            # Determine if we need temp folder
            temp_folder = None
            use_temp_copies = settings.preserve_originals

            if use_temp_copies:
                # Create temp folder in same directory as output
                temp_folder = output_folder / f".temp_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                temp_folder.mkdir(parents=True, exist_ok=True)

            job = ExportJob(
                settings=settings,
                image_collection=image_collection,
                output_file=output_file,
                temp_folder=temp_folder,
                use_temp_copies=use_temp_copies
            )

            return True, job, "Export prepared"

        except Exception as e:
            return False, None, f"Error preparing export: {str(e)}"

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
                self._cleanup_temp(job)
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
                self._cleanup_temp(job)
                return ExportResult(False, f"FFmpeg failed: {msg}", None, 0, 0)

            if self.cancel_requested:
                self._cleanup_temp(job)
                return ExportResult(False, "Export cancelled by user", None, 0, 0)

            # Step 4: Finalize
            if progress_callback:
                progress_callback("Finalizing...", 95, None)

            # Clean up temp folder if used
            if job.temp_folder and job.temp_folder.exists():
                if log_callback:
                    log_callback("Cleaning up temporary files...")
                self._cleanup_temp(job)

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
            self._cleanup_temp(job)
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
            if log_callback:
                log_callback(f"Copying {job.image_collection.total_count} images to temp folder...")

            total = job.image_collection.total_count

            for i, src_image in enumerate(job.image_collection.images):
                if self.cancel_requested:
                    return False, "Cancelled"

                # Copy with sequential numbering
                dst_image = job.temp_folder / f"{i:06d}.jpg"
                shutil.copy2(src_image, dst_image)

                # Update progress
                if progress_callback and i % 10 == 0:  # Update every 10 files
                    percent = (i / total) * 10  # 0-10% range
                    progress_callback(f"Copying images: {i}/{total}", percent, None)

            if log_callback:
                log_callback(f"Copied {total} images to {job.temp_folder}")

            return True, "Images prepared"

        except Exception as e:
            return False, f"Error preparing images: {str(e)}"

    def _cleanup_temp(self, job: ExportJob):
        """Clean up temporary folder"""
        if job.temp_folder and job.temp_folder.exists():
            try:
                shutil.rmtree(job.temp_folder)
            except Exception:
                pass  # Best effort cleanup

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
