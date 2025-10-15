"""
Preset Manager - Video export preset management
Phase 3.5: Video Export Feature

Manages built-in and custom video export presets.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class VideoExportSettings:
    """Video export settings container"""
    framerate: int = 24
    quality: int = 20  # CRF value
    speed_multiplier: int = 1
    resolution: str = 'original'  # 'original', '1920x1080', '1280x720', etc.
    format: str = 'mp4'  # 'mp4', 'avi', 'mkv', 'webm'
    codec: str = 'libx264'
    add_timestamp: bool = False
    preserve_originals: bool = True
    open_when_done: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'VideoExportSettings':
        """Create from dictionary"""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


class PresetManager:
    """Manage video export presets"""

    # Built-in presets that cannot be modified
    BUILTIN_PRESETS = {
        'Standard 24fps': VideoExportSettings(
            framerate=24,
            quality=20,
            speed_multiplier=1,
            resolution='original',
            format='mp4',
            codec='libx264',
            add_timestamp=False,
            preserve_originals=True,
            open_when_done=True
        ),
        'High Quality 30fps': VideoExportSettings(
            framerate=30,
            quality=18,
            speed_multiplier=1,
            resolution='original',
            format='mp4',
            codec='libx264',
            add_timestamp=False,
            preserve_originals=True,
            open_when_done=True
        ),
        'Fast Motion 60fps': VideoExportSettings(
            framerate=60,
            quality=20,
            speed_multiplier=4,
            resolution='original',
            format='mp4',
            codec='libx264',
            add_timestamp=False,
            preserve_originals=True,
            open_when_done=True
        ),
        'Web Optimized': VideoExportSettings(
            framerate=30,
            quality=23,
            speed_multiplier=1,
            resolution='1280x720',
            format='mp4',
            codec='libx264',
            add_timestamp=False,
            preserve_originals=True,
            open_when_done=True
        ),
        'Storage Saver': VideoExportSettings(
            framerate=20,
            quality=28,
            speed_multiplier=1,
            resolution='854x480',
            format='mp4',
            codec='libx264',
            add_timestamp=False,
            preserve_originals=True,
            open_when_done=True
        ),
        'Ultra Speed 16x': VideoExportSettings(
            framerate=30,
            quality=20,
            speed_multiplier=16,
            resolution='original',
            format='mp4',
            codec='libx264',
            add_timestamp=False,
            preserve_originals=True,
            open_when_done=True
        ),
    }

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize preset manager

        Args:
            config_dir: Directory to store custom presets (defaults to user config dir)
        """
        if config_dir is None:
            config_dir = Path.home() / '.rtsp_timelapse'

        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.presets_file = self.config_dir / 'video_export_presets.json'
        self.custom_presets: Dict[str, VideoExportSettings] = {}

        # Load custom presets
        self.load_custom_presets()

    def get_preset(self, name: str) -> Optional[VideoExportSettings]:
        """
        Get preset by name

        Args:
            name: Preset name

        Returns:
            VideoExportSettings or None if not found
        """
        # Check built-in presets first
        if name in self.BUILTIN_PRESETS:
            return self.BUILTIN_PRESETS[name]

        # Check custom presets
        if name in self.custom_presets:
            return self.custom_presets[name]

        return None

    def save_preset(self, name: str, settings: VideoExportSettings) -> Tuple[bool, str]:
        """
        Save a custom preset

        Args:
            name: Preset name
            settings: Video export settings

        Returns:
            (success, message) tuple
        """
        # Prevent overwriting built-in presets
        if name in self.BUILTIN_PRESETS:
            return False, "Cannot overwrite built-in preset"

        # Validate name
        if not name or len(name.strip()) == 0:
            return False, "Preset name cannot be empty"

        # Add to custom presets
        self.custom_presets[name] = settings

        # Save to file
        return self._save_custom_presets()

    def delete_preset(self, name: str) -> Tuple[bool, str]:
        """
        Delete a custom preset

        Args:
            name: Preset name to delete

        Returns:
            (success, message) tuple
        """
        # Cannot delete built-in presets
        if name in self.BUILTIN_PRESETS:
            return False, "Cannot delete built-in preset"

        # Check if exists
        if name not in self.custom_presets:
            return False, f"Preset '{name}' not found"

        # Remove from custom presets
        del self.custom_presets[name]

        # Save to file
        return self._save_custom_presets()

    def rename_preset(self, old_name: str, new_name: str) -> Tuple[bool, str]:
        """
        Rename a custom preset

        Args:
            old_name: Current preset name
            new_name: New preset name

        Returns:
            (success, message) tuple
        """
        # Cannot rename built-in presets
        if old_name in self.BUILTIN_PRESETS:
            return False, "Cannot rename built-in preset"

        # Check if old name exists
        if old_name not in self.custom_presets:
            return False, f"Preset '{old_name}' not found"

        # Check if new name conflicts
        if new_name in self.BUILTIN_PRESETS or new_name in self.custom_presets:
            return False, f"Preset '{new_name}' already exists"

        # Validate new name
        if not new_name or len(new_name.strip()) == 0:
            return False, "Preset name cannot be empty"

        # Rename
        self.custom_presets[new_name] = self.custom_presets[old_name]
        del self.custom_presets[old_name]

        # Save to file
        return self._save_custom_presets()

    def list_presets(self, include_builtin: bool = True) -> List[str]:
        """
        Get list of all preset names

        Args:
            include_builtin: Whether to include built-in presets

        Returns:
            List of preset names
        """
        presets = []

        if include_builtin:
            presets.extend(sorted(self.BUILTIN_PRESETS.keys()))

        presets.extend(sorted(self.custom_presets.keys()))

        return presets

    def is_builtin(self, name: str) -> bool:
        """Check if a preset is built-in"""
        return name in self.BUILTIN_PRESETS

    def is_custom(self, name: str) -> bool:
        """Check if a preset is custom"""
        return name in self.custom_presets

    def load_custom_presets(self) -> Tuple[bool, str]:
        """
        Load custom presets from file

        Returns:
            (success, message) tuple
        """
        if not self.presets_file.exists():
            return True, "No custom presets file found"

        try:
            with open(self.presets_file, 'r') as f:
                data = json.load(f)

            # Convert dict to VideoExportSettings objects
            self.custom_presets = {}
            for name, settings_dict in data.items():
                self.custom_presets[name] = VideoExportSettings.from_dict(settings_dict)

            return True, f"Loaded {len(self.custom_presets)} custom preset(s)"

        except Exception as e:
            return False, f"Failed to load custom presets: {str(e)}"

    def _save_custom_presets(self) -> Tuple[bool, str]:
        """
        Save custom presets to file

        Returns:
            (success, message) tuple
        """
        try:
            # Convert VideoExportSettings objects to dicts
            data = {}
            for name, settings in self.custom_presets.items():
                data[name] = settings.to_dict()

            # Save to file
            with open(self.presets_file, 'w') as f:
                json.dump(data, f, indent=2)

            return True, f"Saved {len(self.custom_presets)} custom preset(s)"

        except Exception as e:
            return False, f"Failed to save custom presets: {str(e)}"

    def export_presets(self, export_file: Path) -> Tuple[bool, str]:
        """
        Export custom presets to a file

        Args:
            export_file: File path to export to

        Returns:
            (success, message) tuple
        """
        try:
            # Convert to dict
            data = {}
            for name, settings in self.custom_presets.items():
                data[name] = settings.to_dict()

            # Save to export file
            with open(export_file, 'w') as f:
                json.dump(data, f, indent=2)

            return True, f"Exported {len(self.custom_presets)} preset(s) to {export_file}"

        except Exception as e:
            return False, f"Failed to export presets: {str(e)}"

    def import_presets(self, import_file: Path, overwrite: bool = False) -> Tuple[bool, str]:
        """
        Import custom presets from a file

        Args:
            import_file: File path to import from
            overwrite: Whether to overwrite existing presets with same name

        Returns:
            (success, message) tuple
        """
        try:
            with open(import_file, 'r') as f:
                data = json.load(f)

            imported_count = 0
            skipped_count = 0

            for name, settings_dict in data.items():
                # Skip built-in preset names
                if name in self.BUILTIN_PRESETS:
                    skipped_count += 1
                    continue

                # Skip if exists and not overwriting
                if name in self.custom_presets and not overwrite:
                    skipped_count += 1
                    continue

                # Import preset
                self.custom_presets[name] = VideoExportSettings.from_dict(settings_dict)
                imported_count += 1

            # Save to file
            self._save_custom_presets()

            msg = f"Imported {imported_count} preset(s)"
            if skipped_count > 0:
                msg += f", skipped {skipped_count}"

            return True, msg

        except Exception as e:
            return False, f"Failed to import presets: {str(e)}"

    def get_resolution_options(self) -> List[str]:
        """Get list of common resolution options"""
        return [
            'original',
            '3840x2160',  # 4K
            '1920x1080',  # 1080p
            '1280x720',   # 720p
            '854x480',    # 480p
            '640x360',    # 360p
        ]

    def get_format_options(self) -> List[str]:
        """Get list of supported video formats"""
        return ['mp4', 'avi', 'mkv', 'webm']

    def get_codec_options(self) -> Dict[str, List[str]]:
        """Get list of codecs for each format"""
        return {
            'mp4': ['libx264', 'libx265'],
            'avi': ['libx264', 'mpeg4'],
            'mkv': ['libx264', 'libx265', 'libvpx'],
            'webm': ['libvpx', 'libvpx-vp9']
        }

    def get_framerate_options(self) -> List[int]:
        """Get list of common framerate options"""
        return [10, 15, 20, 24, 25, 30, 60]

    def get_speed_multiplier_options(self) -> List[int]:
        """Get list of speed multiplier options"""
        return [1, 2, 4, 8, 16, 32]


def test_preset_manager():
    """Test function for preset manager"""
    print("Preset Manager Test")
    print("=" * 50)

    # Create preset manager
    manager = PresetManager()

    # List built-in presets
    print("\nBuilt-in Presets:")
    for name in manager.list_presets(include_builtin=True):
        if manager.is_builtin(name):
            preset = manager.get_preset(name)
            print(f"  - {name}: {preset.framerate}fps, CRF{preset.quality}, {preset.speed_multiplier}x")

    # Create a custom preset
    print("\nCreating custom preset...")
    custom_settings = VideoExportSettings(
        framerate=25,
        quality=22,
        speed_multiplier=2,
        resolution='1920x1080',
        format='mp4'
    )
    success, msg = manager.save_preset("My Custom Preset", custom_settings)
    print(f"  {msg}")

    # List all presets including custom
    print("\nAll Presets:")
    for name in manager.list_presets():
        preset = manager.get_preset(name)
        preset_type = "Built-in" if manager.is_builtin(name) else "Custom"
        print(f"  [{preset_type}] {name}: {preset.framerate}fps, CRF{preset.quality}")


if __name__ == "__main__":
    test_preset_manager()
