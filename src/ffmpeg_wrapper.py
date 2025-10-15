"""
FFmpeg Wrapper - Interface for FFmpeg video encoding operations
Phase 3.5: Video Export Feature

Handles FFmpeg detection, command building, and video export execution.
"""

import subprocess
import re
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple, Callable, Dict, Any


class ProgressInfo:
    """Container for FFmpeg progress information"""

    def __init__(self):
        self.frame: int = 0
        self.fps: float = 0.0
        self.size_kb: int = 0
        self.time_seconds: float = 0.0
        self.bitrate_kbps: float = 0.0
        self.speed: float = 0.0
        self.progress_percent: float = 0.0


class FFmpegWrapper:
    """Wrapper for FFmpeg operations"""

    def __init__(self):
        self.ffmpeg_path = self.find_ffmpeg()
        self.version = None
        if self.ffmpeg_path:
            self.version = self.get_version()

    def find_ffmpeg(self) -> Optional[str]:
        """
        Locate FFmpeg executable
        Checks: 1) System PATH, 2) Local bin/ folder, 3) Common install locations
        """
        # Check if ffmpeg is in PATH
        ffmpeg_cmd = shutil.which('ffmpeg')
        if ffmpeg_cmd:
            return ffmpeg_cmd

        # Check local bin folder (for bundled versions)
        local_bin = Path(__file__).parent.parent / 'bin' / 'ffmpeg.exe'
        if local_bin.exists():
            return str(local_bin)

        # Check common Windows installation locations
        common_paths = [
            r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
            r'C:\ffmpeg\bin\ffmpeg.exe',
        ]

        for path in common_paths:
            if Path(path).exists():
                return path

        return None

    def check_installation(self) -> Tuple[bool, Optional[str]]:
        """
        Verify FFmpeg is installed and accessible
        Returns: (is_installed, version_string)
        """
        if not self.ffmpeg_path:
            return False, None

        try:
            result = subprocess.run(
                [self.ffmpeg_path, '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Extract version from first line
                version_line = result.stdout.split('\n')[0]
                return True, version_line
            return False, None
        except Exception as e:
            return False, None

    def get_version(self) -> Optional[str]:
        """Get FFmpeg version string"""
        is_installed, version = self.check_installation()
        if is_installed:
            return version
        return None

    def build_command(
        self,
        input_pattern: str,
        output_file: str,
        framerate: int = 24,
        quality: int = 20,
        resolution: Optional[str] = None,
        speed_multiplier: int = 1,
        add_timestamp: bool = False,
        codec: str = 'libx264',
        pixel_format: str = 'yuv420p'
    ) -> list:
        """
        Build FFmpeg command line arguments

        Args:
            input_pattern: Input file pattern (e.g., "%06d.jpg")
            output_file: Output video file path
            framerate: Output video framerate
            quality: CRF quality value (0-51, lower=better)
            resolution: Target resolution (e.g., "1920x1080") or None for original
            speed_multiplier: Frame skip multiplier (1=all frames, 2=every 2nd, etc.)
            add_timestamp: Whether to add timestamp overlay
            codec: Video codec to use (default: libx264)
            pixel_format: Pixel format (default: yuv420p for compatibility)

        Returns:
            List of command arguments
        """
        cmd = [
            self.ffmpeg_path,
            '-framerate', str(framerate),
            '-i', input_pattern,
            '-c:v', codec,
            '-crf', str(quality),
            '-pix_fmt', pixel_format,
            '-y',  # Overwrite output file without asking
        ]

        # Add frame selection filter for speed multiplier
        filters = []

        if speed_multiplier > 1:
            # Select every Nth frame
            filters.append(f'select=not(mod(n\\,{speed_multiplier}))')
            filters.append(f'setpts=N/FRAME_RATE/TB')

        # Add resolution scaling if specified
        if resolution and resolution.lower() != 'original':
            filters.append(f'scale={resolution}')

        # Add timestamp overlay if enabled
        if add_timestamp:
            # Extract timestamp from filename and display it
            # Format: drawtext=fontfile=/path/to/font.ttf:text='%{pts\:gmtime\:0\:%Y-%m-%d %H\:%M\:%S}':x=10:y=10:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5
            timestamp_filter = (
                "drawtext="
                "text='%{frame_num}':x=10:y=10:fontsize=24:fontcolor=white:"
                "box=1:boxcolor=black@0.5:boxborderw=5"
            )
            filters.append(timestamp_filter)

        # Combine filters if any
        if filters:
            cmd.extend(['-vf', ','.join(filters)])

        # Add output file
        cmd.append(output_file)

        return cmd

    def build_timestamp_filter(self) -> str:
        """Build FFmpeg filter for timestamp overlay"""
        return (
            "drawtext="
            "fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=5:"
            "x=10:y=10:text='Frame %{frame_num}'"
        )

    def run(
        self,
        command: list,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
        total_frames: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Execute FFmpeg command with progress monitoring

        Args:
            command: FFmpeg command as list of arguments
            progress_callback: Optional callback function for progress updates
            total_frames: Total number of frames (for progress percentage)

        Returns:
            (success, message) tuple
        """
        try:
            # Run FFmpeg process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # Monitor stderr for progress (FFmpeg outputs to stderr)
            stderr_output = []
            for line in process.stderr:
                stderr_output.append(line)

                # Parse progress information
                if progress_callback:
                    progress = self.parse_progress(line, total_frames)
                    if progress:
                        progress_callback(progress)

            # Wait for completion
            process.wait()

            if process.returncode == 0:
                return True, "Video export completed successfully"
            else:
                error_msg = ''.join(stderr_output[-20:])  # Last 20 lines
                return False, f"FFmpeg failed with code {process.returncode}: {error_msg}"

        except Exception as e:
            return False, f"Error running FFmpeg: {str(e)}"

    def parse_progress(self, line: str, total_frames: Optional[int] = None) -> Optional[ProgressInfo]:
        """
        Parse FFmpeg output line for progress information

        FFmpeg progress format:
        frame=  123 fps= 45 q=28.0 size=    1024kB time=00:00:05.12 bitrate=1638.4kbits/s speed=1.23x

        Args:
            line: Output line from FFmpeg stderr
            total_frames: Total frames for percentage calculation

        Returns:
            ProgressInfo object or None if line doesn't contain progress
        """
        # Look for frame= in the line (indicates progress output)
        if 'frame=' not in line:
            return None

        try:
            progress = ProgressInfo()

            # Extract frame number
            frame_match = re.search(r'frame=\s*(\d+)', line)
            if frame_match:
                progress.frame = int(frame_match.group(1))

            # Extract fps
            fps_match = re.search(r'fps=\s*([\d.]+)', line)
            if fps_match:
                progress.fps = float(fps_match.group(1))

            # Extract size
            size_match = re.search(r'size=\s*(\d+)kB', line)
            if size_match:
                progress.size_kb = int(size_match.group(1))

            # Extract time (convert to seconds)
            time_match = re.search(r'time=(\d{2}):(\d{2}):([\d.]+)', line)
            if time_match:
                hours = int(time_match.group(1))
                minutes = int(time_match.group(2))
                seconds = float(time_match.group(3))
                progress.time_seconds = hours * 3600 + minutes * 60 + seconds

            # Extract bitrate
            bitrate_match = re.search(r'bitrate=\s*([\d.]+)kbits/s', line)
            if bitrate_match:
                progress.bitrate_kbps = float(bitrate_match.group(1))

            # Extract speed
            speed_match = re.search(r'speed=\s*([\d.]+)x', line)
            if speed_match:
                progress.speed = float(speed_match.group(1))

            # Calculate progress percentage
            if total_frames and progress.frame > 0:
                progress.progress_percent = (progress.frame / total_frames) * 100

            return progress

        except Exception:
            return None

    def estimate_output_size(
        self,
        num_frames: int,
        resolution: Tuple[int, int],
        quality: int,
        framerate: int
    ) -> float:
        """
        Estimate output video file size in MB

        This is a rough estimation based on typical compression ratios.
        Actual size will vary based on content complexity.

        Args:
            num_frames: Number of input frames
            resolution: (width, height) tuple
            quality: CRF quality value (0-51)
            framerate: Output framerate

        Returns:
            Estimated file size in MB
        """
        # Calculate video duration in seconds
        duration_seconds = num_frames / framerate

        # Estimate bitrate based on resolution and quality
        # These are rough estimates for H.264
        width, height = resolution
        pixels = width * height

        # Base bitrate (kbps) for different quality levels
        # CRF 18-23: High quality
        # CRF 23-28: Medium quality
        # CRF 28+: Lower quality
        if quality <= 18:
            base_bitrate = 0.15  # bits per pixel per frame
        elif quality <= 23:
            base_bitrate = 0.10
        elif quality <= 28:
            base_bitrate = 0.07
        else:
            base_bitrate = 0.05

        # Calculate estimated bitrate
        bitrate_kbps = (pixels * framerate * base_bitrate) / 1000

        # Calculate file size: (bitrate * duration) / 8 / 1024
        size_mb = (bitrate_kbps * duration_seconds) / 8 / 1024

        return size_mb

    def get_video_info(self, video_file: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a video file using FFprobe

        Args:
            video_file: Path to video file

        Returns:
            Dictionary with video info or None on error
        """
        ffprobe_path = self.ffmpeg_path.replace('ffmpeg', 'ffprobe')

        if not Path(ffprobe_path).exists():
            return None

        try:
            cmd = [
                ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_file
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                import json
                return json.loads(result.stdout)

        except Exception:
            pass

        return None


def test_ffmpeg_installation():
    """Test function to check FFmpeg installation"""
    wrapper = FFmpegWrapper()

    print("FFmpeg Installation Check")
    print("=" * 50)

    if wrapper.ffmpeg_path:
        print(f"✓ FFmpeg found at: {wrapper.ffmpeg_path}")
        is_installed, version = wrapper.check_installation()
        if is_installed:
            print(f"✓ Version: {version}")
            print("✓ FFmpeg is ready to use")
        else:
            print("✗ FFmpeg found but not working properly")
    else:
        print("✗ FFmpeg not found")
        print("\nInstallation instructions:")
        print("1. Download FFmpeg from: https://ffmpeg.org/download.html")
        print("2. Add FFmpeg to your system PATH, or")
        print("3. Place ffmpeg.exe in the 'bin' folder of this application")


if __name__ == "__main__":
    test_ffmpeg_installation()
