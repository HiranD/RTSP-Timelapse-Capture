"""
Configuration Manager - Save/Load/Validate application configuration

Handles all configuration operations including JSON serialization,
validation, and migration from the old config.py format.
"""

import sys
import json
import os
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, asdict, field
from typing import List


def get_app_base_dir() -> Path:
    """Get the application's base directory (where exe or main script is located)."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - use exe's directory
        return Path(sys.executable).parent
    else:
        # Running from source - use src's parent directory
        return Path(__file__).parent.parent


def get_config_path() -> Path:
    """Get the path to the config file."""
    return get_app_base_dir() / "config" / "app_config.json"


@dataclass
class CameraConfig:
    """Camera connection settings"""
    ip_address: str = "192.168.0.101"
    username: str = "admin"
    password: str = ""
    stream_path: str = "/stream1"
    force_tcp: bool = True


@dataclass
class ScheduleConfig:
    """Capture scheduling settings"""
    start_time: str = "20:00"  # HH:MM format
    end_time: str = "08:00"     # HH:MM format
    folder_rollover_hour: int = 12  # 0-23


@dataclass
class CaptureConfig:
    """Capture behavior settings"""
    interval_seconds: int = 30  # Optimal for timestamp accuracy (Configuration A)
    jpeg_quality: int = 95  # 1-100, higher quality for archival purposes
    output_folder: str = "snapshots"
    buffer_frames: int = 1  # Minimal buffer for multi-threaded bufferless capture
    max_retries: int = 3  # Quick failure detection - if it fails 3 times, there's a real issue
    proactive_reconnect_seconds: int = 300  # 5 minutes - optimal for Annke cameras (Configuration A)
    flush_buffer_count: int = 0  # Not needed with multi-threaded bufferless capture (v2.3.0+)


@dataclass
class UIConfig:
    """UI preferences"""
    window_width: int = 1000
    window_height: int = 700
    preview_size: str = "medium"  # small/medium/large
    preview_enabled: bool = True
    minimize_to_tray: bool = False
    auto_start: bool = False
    last_video_export_dir: str = ""  # Last directory used for video export
    last_video_preset: str = "Standard 24fps"  # Last selected video export preset


@dataclass
class AstroScheduleConfig:
    """Astronomical scheduling settings for long-term capture planning"""
    latitude: float = 0.0  # -90 to 90, negative = southern hemisphere
    longitude: float = 0.0  # -180 to 180, negative = west
    twilight_type: str = "astronomical"  # civil, nautical, astronomical
    start_offset_minutes: int = 0  # Minutes after darkness begins (can be negative)
    end_offset_minutes: int = 0  # Minutes before darkness ends (can be negative)
    scheduled_dates: List[str] = field(default_factory=list)  # ["2025-12-15", "2025-12-16"]
    auto_create_video: bool = False  # Automatically create video after each night
    delete_snapshots_after_video: bool = False  # Delete snapshot folder after video creation
    discord_webhook_url: str = ""  # Discord webhook URL for automatic uploads
    discord_max_video_size_mb: int = 8  # Maximum file size to upload to Discord in MB
    discord_export_resolution: str = "original"  # Resolution for Discord export: original/720p/480p/360p
    discord_auto_quality_reduction: bool = False  # Auto re-encode with lower quality if file exceeds limit
    delete_video_after_discord_upload: bool = False  # Delete generated video after successful Discord upload
    discord_keep_reencoded: bool = False  # Keep the re-encoded copy uploaded to Discord (in .discord_encode/)
    # Manual time mode settings
    use_manual_times: bool = False  # True = use manual times, False = use twilight calculation
    manual_start_time: str = "20:00"  # HH:MM format - capture start time
    manual_end_time: str = "08:00"  # HH:MM format - capture end time
    scheduler_enabled: bool = False  # Persist "Enable automatic scheduling" toggle state


@dataclass
class RemoteApiConfig:
    """Localhost HTTP API for external control (e.g. NINA). See issue #12.

    Opt-in and off by default. The server binds to 127.0.0.1 only (no token);
    'enabled' also governs whether it auto-starts on launch. Mutually exclusive
    with automatic scheduling (enforced in the UI).
    """
    enabled: bool = False  # Start the local HTTP server on launch
    port: int = 8787  # TCP port (bound to 127.0.0.1 only)


class ConfigManager:
    """
    Manages application configuration.

    Handles loading, saving, validation, and provides default values.
    """

    DEFAULT_CONFIG_FILE = "config/app_config.json"

    def __init__(self):
        """Initialize with default configuration."""
        self.camera = CameraConfig()
        self.schedule = ScheduleConfig()
        self.capture = CaptureConfig()
        self.ui = UIConfig()
        self.astro_schedule = AstroScheduleConfig()
        self.remote_api = RemoteApiConfig()

    def to_dict(self) -> dict:
        """
        Convert configuration to dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "camera": asdict(self.camera),
            "schedule": asdict(self.schedule),
            "capture": asdict(self.capture),
            "ui": asdict(self.ui),
            "astro_schedule": asdict(self.astro_schedule),
            "remote_api": asdict(self.remote_api)
        }

    def from_dict(self, config_dict: dict):
        """
        Load configuration from dictionary.

        Args:
            config_dict: Dictionary with configuration sections
        """
        if "camera" in config_dict:
            self.camera = CameraConfig(**config_dict["camera"])

        if "schedule" in config_dict:
            self.schedule = ScheduleConfig(**config_dict["schedule"])

        if "capture" in config_dict:
            self.capture = CaptureConfig(**config_dict["capture"])

        if "ui" in config_dict:
            ui_data = dict(config_dict["ui"])
            # Backward compat: "minimize_to_tray_on_startup" was renamed to
            # "minimize_to_tray" (it now also governs the minimize button).
            if "minimize_to_tray_on_startup" in ui_data:
                ui_data.setdefault("minimize_to_tray", ui_data.pop("minimize_to_tray_on_startup"))
            self.ui = UIConfig(**ui_data)

        if "astro_schedule" in config_dict:
            self.astro_schedule = AstroScheduleConfig(**config_dict["astro_schedule"])

        if "remote_api" in config_dict:
            self.remote_api = RemoteApiConfig(**config_dict["remote_api"])

    def save_to_file(self, filepath: Optional[str] = None) -> tuple[bool, str]:
        """
        Save configuration to JSON file.

        Args:
            filepath: Path to save to (uses default if None)

        Returns:
            Tuple of (success: bool, message: str)
        """
        if filepath is None:
            config_path = get_config_path()
            # Ensure config directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)
            filepath = str(config_path)

        try:
            with open(filepath, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)

            return True, f"Configuration saved to {filepath}"

        except Exception as e:
            return False, f"Failed to save configuration: {str(e)}"

    def load_from_file(self, filepath: Optional[str] = None) -> tuple[bool, str]:
        """
        Load configuration from JSON file.

        Args:
            filepath: Path to load from (uses default if None)

        Returns:
            Tuple of (success: bool, message: str)
        """
        if filepath is None:
            filepath = str(get_config_path())

        if not os.path.exists(filepath):
            return False, f"Configuration file not found: {filepath}"

        try:
            with open(filepath, 'r') as f:
                config_dict = json.load(f)

            self.from_dict(config_dict)
            return True, f"Configuration loaded from {filepath}"

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON in configuration file: {str(e)}"
        except Exception as e:
            return False, f"Failed to load configuration: {str(e)}"

    def migrate_from_old_config(self) -> tuple[bool, str]:
        """
        Import settings from old config.py file if it exists.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            import config

            # Migrate camera settings
            if hasattr(config, 'rtsp_ip_address'):
                self.camera.ip_address = config.rtsp_ip_address
            if hasattr(config, 'rtsp_username'):
                self.camera.username = config.rtsp_username
            if hasattr(config, 'rtsp_password'):
                self.camera.password = config.rtsp_password

            # Migrate schedule settings
            if hasattr(config, 'capture_start_time'):
                self.schedule.start_time = config.capture_start_time
            if hasattr(config, 'capture_end_time'):
                self.schedule.end_time = config.capture_end_time
            if hasattr(config, 'folder_rollover_hour'):
                self.schedule.folder_rollover_hour = config.folder_rollover_hour

            # Migrate capture settings
            if hasattr(config, 'snapshot_interval_seconds'):
                self.capture.interval_seconds = config.snapshot_interval_seconds
            if hasattr(config, 'jpeg_quality'):
                self.capture.jpeg_quality = config.jpeg_quality
            if hasattr(config, 'rtsp_buffer_frames'):
                self.capture.buffer_frames = config.rtsp_buffer_frames
            if hasattr(config, 'rtsp_max_retries'):
                self.capture.max_retries = config.rtsp_max_retries
            if hasattr(config, 'rtsp_force_tcp'):
                self.camera.force_tcp = config.rtsp_force_tcp

            return True, "Successfully imported settings from config.py"

        except ImportError:
            return False, "config.py not found"
        except Exception as e:
            return False, f"Error importing from config.py: {str(e)}"

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate current configuration.

        Returns:
            Tuple of (is_valid: bool, errors: list[str])
        """
        errors = []

        # Validate camera
        if not self.camera.ip_address:
            errors.append("Camera IP address is required")
        if not self.camera.username:
            errors.append("Camera username is required")

        # Validate schedule
        if not self._is_valid_time(self.schedule.start_time):
            errors.append(f"Invalid start time format: {self.schedule.start_time} (use HH:MM)")
        if not self._is_valid_time(self.schedule.end_time):
            errors.append(f"Invalid end time format: {self.schedule.end_time} (use HH:MM)")
        if not 0 <= self.schedule.folder_rollover_hour <= 23:
            errors.append(f"Folder rollover hour must be 0-23, got {self.schedule.folder_rollover_hour}")

        # Validate capture
        if not 1 <= self.capture.interval_seconds <= 3600:
            errors.append(f"Interval must be 1-3600 seconds, got {self.capture.interval_seconds}")
        if not 1 <= self.capture.jpeg_quality <= 100:
            errors.append(f"JPEG quality must be 1-100, got {self.capture.jpeg_quality}")
        if not self.capture.output_folder:
            errors.append("Output folder is required")
        if not 1 <= self.capture.buffer_frames <= 100:
            errors.append(f"Buffer frames must be 1-100, got {self.capture.buffer_frames}")
        if not 1 <= self.capture.max_retries <= 20:
            errors.append(f"Max retries must be 1-20, got {self.capture.max_retries}")
        if not 0 <= self.capture.proactive_reconnect_seconds <= 3600:
            errors.append(f"Proactive reconnect must be 0-3600 seconds, got {self.capture.proactive_reconnect_seconds}")
        if not 0 <= self.capture.flush_buffer_count <= 50:
            errors.append(f"Flush buffer count must be 0-50, got {self.capture.flush_buffer_count}")

        # Validate UI
        if self.ui.preview_size not in ["small", "medium", "large"]:
            errors.append(f"Preview size must be small/medium/large, got {self.ui.preview_size}")

        # Validate astro_schedule
        if not -90 <= self.astro_schedule.latitude <= 90:
            errors.append(f"Latitude must be -90 to 90, got {self.astro_schedule.latitude}")
        if not -180 <= self.astro_schedule.longitude <= 180:
            errors.append(f"Longitude must be -180 to 180, got {self.astro_schedule.longitude}")
        if self.astro_schedule.twilight_type not in ["civil", "nautical", "astronomical"]:
            errors.append(f"Twilight type must be civil/nautical/astronomical, got {self.astro_schedule.twilight_type}")
        if not -120 <= self.astro_schedule.start_offset_minutes <= 120:
            errors.append(f"Start offset must be -120 to 120 minutes, got {self.astro_schedule.start_offset_minutes}")
        if not -120 <= self.astro_schedule.end_offset_minutes <= 120:
            errors.append(f"End offset must be -120 to 120 minutes, got {self.astro_schedule.end_offset_minutes}")
        if not 1 <= self.astro_schedule.discord_max_video_size_mb <= 1024:
            errors.append(
                f"Discord max upload size must be between 1 and 1024 MB, got {self.astro_schedule.discord_max_video_size_mb}"
            )
        if self.astro_schedule.discord_export_resolution not in ["original", "720p", "480p", "360p"]:
            errors.append(
                f"Discord export resolution must be original/720p/480p/360p, got {self.astro_schedule.discord_export_resolution}"
            )

        # Validate remote API
        if self.remote_api.enabled and not 1024 <= self.remote_api.port <= 65535:
            errors.append(f"Remote API port must be 1024-65535, got {self.remote_api.port}")

        return len(errors) == 0, errors

    def _is_valid_time(self, time_str: str) -> bool:
        """
        Check if time string is valid HH:MM format.

        Args:
            time_str: Time string to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            parts = time_str.split(":")
            if len(parts) != 2:
                return False

            hour, minute = int(parts[0]), int(parts[1])
            return 0 <= hour <= 23 and 0 <= minute <= 59

        except (ValueError, AttributeError):
            return False

    def get_summary(self) -> str:
        """
        Get a human-readable summary of the configuration.

        Returns:
            Multi-line string with configuration summary
        """
        lines = [
            "=== Configuration Summary ===",
            "",
            "Camera:",
            f"  IP Address: {self.camera.ip_address}",
            f"  Username: {self.camera.username}",
            f"  Password: {'*' * len(self.camera.password)}",
            f"  Force TCP: {self.camera.force_tcp}",
            "",
            "Schedule:",
            f"  Start Time: {self.schedule.start_time}",
            f"  End Time: {self.schedule.end_time}",
            f"  Folder Rollover: {self.schedule.folder_rollover_hour}:00",
            "",
            "Capture:",
            f"  Interval: {self.capture.interval_seconds} seconds",
            f"  JPEG Quality: {self.capture.jpeg_quality}",
            f"  Output Folder: {self.capture.output_folder}",
            f"  Buffer Frames: {self.capture.buffer_frames}",
            f"  Max Retries: {self.capture.max_retries}",
            f"  Proactive Reconnect: {self.capture.proactive_reconnect_seconds}s ({'enabled' if self.capture.proactive_reconnect_seconds > 0 else 'disabled'})",
            "",
            "UI:",
            f"  Window Size: {self.ui.window_width}x{self.ui.window_height}",
            f"  Preview: {self.ui.preview_size} ({'enabled' if self.ui.preview_enabled else 'disabled'})",
            f"  Minimize to Tray: {self.ui.minimize_to_tray}",
            f"  Auto-start: {self.ui.auto_start}",
            "",
            "Astro Schedule:",
            f"  Time Mode: {'Manual' if self.astro_schedule.use_manual_times else 'Twilight-based'}",
            f"  Location: {self.astro_schedule.latitude}, {self.astro_schedule.longitude}",
            f"  Twilight Type: {self.astro_schedule.twilight_type}",
            f"  Start Offset: {self.astro_schedule.start_offset_minutes} min",
            f"  End Offset: {self.astro_schedule.end_offset_minutes} min",
            f"  Manual Times: {self.astro_schedule.manual_start_time} - {self.astro_schedule.manual_end_time}",
            f"  Scheduled Dates: {len(self.astro_schedule.scheduled_dates)} dates",
            f"  Auto Video: {'enabled' if self.astro_schedule.auto_create_video else 'disabled'}",
            "",
            "Remote API:",
            f"  Enabled: {self.remote_api.enabled}",
            f"  Port: {self.remote_api.port}",
        ]

        return "\n".join(lines)

    @classmethod
    def load_or_create_default(cls, filepath: Optional[str] = None) -> 'ConfigManager':
        """
        Load configuration from file, or create default if not found.

        This is the recommended way to initialize configuration.

        Args:
            filepath: Path to config file (uses default if None)

        Returns:
            ConfigManager instance
        """
        manager = cls()

        # Try to load from file
        if filepath is None:
            filepath = cls.DEFAULT_CONFIG_FILE

        if os.path.exists(filepath):
            success, message = manager.load_from_file(filepath)
            if success:
                print(f"✓ {message}")
            else:
                print(f"⚠ {message}")
                print("  Using default configuration")
        else:
            # Try to migrate from old config.py
            success, message = manager.migrate_from_old_config()
            if success:
                print(f"✓ {message}")
                # Save the migrated config
                manager.save_to_file(filepath)
                print(f"✓ Saved migrated configuration to {filepath}")
            else:
                print(f"⚠ No existing configuration found")
                print(f"  Using default configuration")

        return manager


# Convenience function for quick access
def load_config(filepath: Optional[str] = None) -> dict:
    """
    Load configuration and return as dictionary.

    This is a convenience function for backward compatibility
    with the old config.py style.

    Args:
        filepath: Path to config file (uses default if None)

    Returns:
        Configuration dictionary
    """
    manager = ConfigManager.load_or_create_default(filepath)
    return manager.to_dict()


if __name__ == "__main__":
    """Test/demo the configuration manager"""
    print("Configuration Manager Test\n")

    # Create and display default config
    config = ConfigManager()
    print(config.get_summary())
    print()

    # Validate
    valid, errors = config.validate()
    if valid:
        print("✓ Configuration is valid")
    else:
        print("✗ Configuration errors:")
        for error in errors:
            print(f"  - {error}")
    print()

    # Save to file
    success, message = config.save_to_file("test_config.json")
    print(message)
    print()

    # Load from file
    config2 = ConfigManager()
    success, message = config2.load_from_file("test_config.json")
    print(message)
    print()

    # Try migration
    config3 = ConfigManager()
    success, message = config3.migrate_from_old_config()
    print(message)
    if success:
        print("\nMigrated configuration:")
        print(config3.get_summary())
