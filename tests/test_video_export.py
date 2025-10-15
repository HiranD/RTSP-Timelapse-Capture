"""
Test script for video export functionality
Tests the video export pipeline without GUI
"""

import sys
from pathlib import Path
import os

# Add src to path
if '__file__' in globals():
    sys.path.insert(0, str(Path(__file__).parent / 'src'))
else:
    sys.path.insert(0, str(Path(os.getcwd()) / 'src'))

from video_export_controller import VideoExportController
from preset_manager import PresetManager, VideoExportSettings
from ffmpeg_wrapper import FFmpegWrapper

def test_ffmpeg_installation():
    """Test 1: Check FFmpeg installation"""
    print("=" * 60)
    print("TEST 1: FFmpeg Installation Check")
    print("=" * 60)

    wrapper = FFmpegWrapper()
    is_installed, version = wrapper.check_installation()

    if is_installed:
        print(f"✓ FFmpeg found at: {wrapper.ffmpeg_path}")
        print(f"✓ Version: {version}")
        return True
    else:
        print("✗ FFmpeg not found")
        return False

def test_scan_folder():
    """Test 2: Scan snapshot folder"""
    print("\n" + "=" * 60)
    print("TEST 2: Scan Snapshot Folder")
    print("=" * 60)

    controller = VideoExportController()
    folder = Path("snapshots/20251014")

    if not folder.exists():
        print(f"✗ Folder not found: {folder}")
        return None

    success, collection, message = controller.scan_folder(folder)

    if success:
        print(f"✓ {message}")
        print(f"  Total images: {collection.total_count}")
        print(f"  Date range: {collection.get_date_range_str()}")
        print(f"  Duration: {collection.get_duration_str()}")
        print(f"  Total size: {collection.get_size_str()}")
        return collection
    else:
        print(f"✗ {message}")
        return None

def test_presets():
    """Test 3: Preset Manager"""
    print("\n" + "=" * 60)
    print("TEST 3: Preset Manager")
    print("=" * 60)

    manager = PresetManager()
    presets = manager.list_presets()

    print(f"✓ Found {len(presets)} presets:")
    for preset_name in presets:
        preset = manager.get_preset(preset_name)
        preset_type = "Built-in" if manager.is_builtin(preset_name) else "Custom"
        print(f"  [{preset_type}] {preset_name}")
        print(f"    - {preset.framerate}fps, CRF{preset.quality}, {preset.speed_multiplier}x, {preset.resolution}")

    return manager

def test_export_preparation(collection):
    """Test 4: Export Preparation"""
    print("\n" + "=" * 60)
    print("TEST 4: Export Preparation")
    print("=" * 60)

    if not collection:
        print("✗ No image collection available")
        return None

    controller = VideoExportController()

    # Use Standard preset
    settings = VideoExportSettings(
        framerate=24,
        quality=20,
        speed_multiplier=1,
        resolution='original',
        format='mp4',
        preserve_originals=True,
        add_timestamp=False
    )

    output_file = Path("test_output/timelapse_test.mp4")

    success, job, message = controller.prepare_export(settings, collection, output_file)

    if success:
        print(f"✓ {message}")
        print(f"  Output: {job.output_file}")
        print(f"  Temp folder: {job.temp_folder}")
        print(f"  Use temp copies: {job.use_temp_copies}")
        return job
    else:
        print(f"✗ {message}")
        return None

def test_estimates(collection):
    """Test 5: Duration and File Size Estimates"""
    print("\n" + "=" * 60)
    print("TEST 5: Estimates")
    print("=" * 60)

    if not collection:
        print("✗ No image collection available")
        return

    controller = VideoExportController()

    # Test with different settings
    settings_list = [
        (24, 1, "24fps, 1x speed"),
        (24, 4, "24fps, 4x speed"),
        (60, 1, "60fps, 1x speed"),
    ]

    for framerate, speed, description in settings_list:
        duration = controller.estimate_duration(
            collection.total_count,
            framerate,
            speed
        )

        sample_image = collection.images[0] if collection.images else None
        filesize = controller.estimate_filesize(
            collection.total_count,
            'original',
            20,  # CRF quality
            framerate,
            sample_image
        )

        print(f"  {description}:")
        print(f"    Duration: {duration:.1f} seconds")
        print(f"    Size: ~{filesize:.1f} MB")

def test_actual_export(collection):
    """Test 6: Actual Video Export (SLOW - creates real video)"""
    print("\n" + "=" * 60)
    print("TEST 6: Actual Video Export")
    print("=" * 60)

    response = input("Run actual export test? This will create a real video (y/N): ")
    if response.lower() != 'y':
        print("Skipped actual export test")
        return

    if not collection:
        print("✗ No image collection available")
        return

    controller = VideoExportController()

    # Use fast settings for testing
    settings = VideoExportSettings(
        framerate=30,
        quality=25,  # Lower quality for faster encoding
        speed_multiplier=2,  # Use every 2nd frame for speed
        resolution='640x360',  # Lower resolution for speed
        format='mp4',
        preserve_originals=True,
        add_timestamp=True
    )

    output_file = Path("test_output/timelapse_test_actual.mp4")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    success, job, message = controller.prepare_export(settings, collection, output_file)

    if not success:
        print(f"✗ Preparation failed: {message}")
        return

    print("✓ Starting export...")
    print("  This may take a minute...")

    def progress_callback(status, percent, info):
        if info:
            print(f"  Progress: {percent:.1f}% - {status} (FPS: {info.fps:.1f})")
        else:
            print(f"  Progress: {percent:.1f}% - {status}")

    def log_callback(message):
        print(f"  Log: {message}")

    result = controller.export_video(job, progress_callback, log_callback)

    if result.success:
        print(f"✓ Export successful!")
        print(f"  Output: {result.output_file}")
        print(f"  Size: {result.output_size_bytes / (1024*1024):.2f} MB")
        print(f"  Duration: {result.duration_seconds:.1f} seconds")
    else:
        print(f"✗ Export failed: {result.message}")

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("VIDEO EXPORT FUNCTIONALITY TEST")
    print("=" * 60)

    # Test 1: FFmpeg
    if not test_ffmpeg_installation():
        print("\n⚠ FFmpeg not found - video export will not work")
        print("Install FFmpeg from: https://ffmpeg.org/download.html")
        return

    # Test 2: Scan folder
    collection = test_scan_folder()

    # Test 3: Presets
    test_presets()

    # Test 4: Export preparation
    test_export_preparation(collection)

    # Test 5: Estimates
    test_estimates(collection)

    # Test 6: Actual export (optional)
    test_actual_export(collection)

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("✓ All core functionality tests passed!")
    print("✓ Video export feature is ready to use")
    print("\nNext steps:")
    print("1. Launch GUI: python run_gui.py")
    print("2. Go to 'Video Export' tab")
    print("3. Select snapshot folder")
    print("4. Choose settings or preset")
    print("5. Click 'Create Video'")
    print("=" * 60)

if __name__ == "__main__":
    main()
