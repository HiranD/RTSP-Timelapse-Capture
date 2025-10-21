"""
Configuration Manager - Save/Load/Validate application configuration

Handles all configuration operations including JSON serialization,
validation, and migration from the old config.py format.
"""

import json
import os
from typing import Optional, Any
from dataclasses import dataclass, asdict


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
    start_time: str = "22:40"  # HH:MM format
    end_time: str = "07:00"     # HH:MM format
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
    auto_start: bool = False
    last_video_export_dir: str = ""  # Last directory used for video export


class ConfigManager:
    """
    Manages application configuration.

    Handles loading, saving, validation, and provides default values.
    """

    DEFAULT_CONFIG_FILE = "capture_config.json"

    def __init__(self):
        """Initialize with default configuration."""
        self.camera = CameraConfig()
        self.schedule = ScheduleConfig()
        self.capture = CaptureConfig()
        self.ui = UIConfig()

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
            "ui": asdict(self.ui)
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
            self.ui = UIConfig(**config_dict["ui"])

    def save_to_file(self, filepath: Optional[str] = None) -> tuple[bool, str]:
        """
        Save configuration to JSON file.

        Args:
            filepath: Path to save to (uses default if None)

        Returns:
            Tuple of (success: bool, message: str)
        """
        if filepath is None:
            filepath = self.DEFAULT_CONFIG_FILE

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
            filepath = self.DEFAULT_CONFIG_FILE

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
            f"  Auto-start: {self.ui.auto_start}",
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
