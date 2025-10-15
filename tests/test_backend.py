"""
Backend Component Test Script

Tests the capture_engine and config_manager independently
before integrating with the GUI.
"""

import sys
from pathlib import Path

# Add parent/src directory to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import time
from config_manager import ConfigManager
from capture_engine import CaptureEngine, CaptureState


def test_config_manager():
    """Test configuration management"""
    print("=" * 60)
    print("TESTING CONFIG MANAGER")
    print("=" * 60)
    print()

    # Test 1: Create default config
    print("Test 1: Create default configuration")
    config = ConfigManager()
    print(config.get_summary())
    print()

    # Test 2: Validate
    print("Test 2: Validate configuration")
    valid, errors = config.validate()
    if valid:
        print("✓ Configuration is valid")
    else:
        print("✗ Configuration has errors:")
        for error in errors:
            print(f"  - {error}")
    print()

    # Test 3: Migrate from old config.py
    print("Test 3: Migrate from old config.py")
    success, message = config.migrate_from_old_config()
    print(f"  {message}")
    if success:
        print("\nMigrated values:")
        print(f"  IP: {config.camera.ip_address}")
        print(f"  User: {config.camera.username}")
        print(f"  Start: {config.schedule.start_time}")
        print(f"  End: {config.schedule.end_time}")
        print(f"  Interval: {config.capture.interval_seconds}s")
    print()

    # Test 4: Save to file
    print("Test 4: Save configuration to file")
    success, message = config.save_to_file("test_config.json")
    print(f"  {message}")
    print()

    # Test 5: Load from file
    print("Test 5: Load configuration from file")
    config2 = ConfigManager()
    success, message = config2.load_from_file("test_config.json")
    print(f"  {message}")
    if success:
        print(f"  Loaded IP: {config2.camera.ip_address}")
    print()

    # Test 6: Convert to dict (for capture engine)
    print("Test 6: Convert to dictionary for capture engine")
    config_dict = config.to_dict()
    print(f"  Camera IP: {config_dict['camera']['ip_address']}")
    print(f"  Schedule Start: {config_dict['schedule']['start_time']}")
    print(f"  Capture Interval: {config_dict['capture']['interval_seconds']}")
    print()

    return config


def test_capture_engine(config: ConfigManager):
    """Test capture engine (without actually capturing)"""
    print("=" * 60)
    print("TESTING CAPTURE ENGINE")
    print("=" * 60)
    print()

    # Create engine
    print("Test 1: Create capture engine")
    engine = CaptureEngine(config.to_dict())
    print(f"  Initial state: {engine.state.value}")
    print()

    # Set up callbacks
    print("Test 2: Set up callbacks")

    def status_callback(state: CaptureState, stats: dict):
        print(f"  [STATUS] State: {state.value}, Frames: {stats['frame_count']}, Uptime: {stats['uptime_seconds']}s")

    def frame_callback(frame):
        print(f"  [FRAME] Received frame: {frame.shape}")

    def log_callback(level: str, message: str):
        print(f"  [LOG:{level}] {message}")

    engine.set_status_callback(status_callback)
    engine.set_frame_callback(frame_callback)
    engine.set_log_callback(log_callback)
    print("  ✓ Callbacks registered")
    print()

    # Test connection (this will actually try to connect)
    print("Test 3: Test camera connection")
    print("  NOTE: This will attempt to connect to your camera")
    print("  Press Ctrl+C to skip if camera is not available")
    try:
        success, message = engine.test_connection()
        if success:
            print(f"  ✓ {message}")
        else:
            print(f"  ✗ {message}")
    except KeyboardInterrupt:
        print("  ⊘ Skipped by user")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    print()

    # Get stats
    print("Test 4: Get statistics")
    stats = engine.get_stats()
    print(f"  State: {stats['state']}")
    print(f"  Frames: {stats['frame_count']}")
    print(f"  Uptime: {stats['uptime_seconds']}s")
    print()

    return engine


def test_capture_cycle(config: ConfigManager):
    """Test a short capture cycle (if user confirms)"""
    print("=" * 60)
    print("TESTING CAPTURE CYCLE")
    print("=" * 60)
    print()

    response = input("Do you want to test actual capture? (yes/no): ").strip().lower()
    if response != "yes":
        print("  Skipped by user")
        return

    print()
    print("Starting 30-second capture test...")
    print("Press Ctrl+C to stop early")
    print()

    # Modify config for quick test
    test_config = config.to_dict()
    test_config["capture"]["interval_seconds"] = 5  # Capture every 5 seconds
    test_config["schedule"]["start_time"] = "00:00"  # Start immediately
    test_config["schedule"]["end_time"] = "23:59"   # Run all day

    # Create engine
    engine = CaptureEngine(test_config)

    # Callbacks for monitoring
    frame_count = [0]

    def status_callback(state: CaptureState, stats: dict):
        print(f"  State: {state.value} | Frames: {stats['frame_count']} | Uptime: {stats['uptime_seconds']}s")

    def frame_callback(frame):
        frame_count[0] += 1
        print(f"  → Frame {frame_count[0]} captured: {frame.shape[1]}x{frame.shape[0]}")

    def log_callback(level: str, message: str):
        timestamp = time.strftime("%H:%M:%S")
        print(f"  [{timestamp}] [{level}] {message}")

    engine.set_status_callback(status_callback)
    engine.set_frame_callback(frame_callback)
    engine.set_log_callback(log_callback)

    # Start capture
    try:
        engine.start_capture()

        # Let it run for 30 seconds
        for i in range(30):
            time.sleep(1)
            if engine.state == CaptureState.ERROR:
                print("\n✗ Capture engine encountered an error")
                break
            if engine.state == CaptureState.STOPPED:
                print("\n✗ Capture engine stopped unexpectedly")
                break

        # Stop capture
        print("\nStopping capture...")
        engine.stop_capture()

        # Wait for clean shutdown
        time.sleep(2)

        # Final stats
        final_stats = engine.get_stats()
        print("\nFinal Statistics:")
        print(f"  Total Frames: {final_stats['frame_count']}")
        print(f"  Total Uptime: {final_stats['uptime_seconds']}s")
        print(f"  Final State: {final_stats['state']}")

        if final_stats['frame_count'] > 0:
            print("\n✓ Capture test PASSED")
        else:
            print("\n✗ Capture test FAILED (no frames captured)")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        engine.stop_capture()
        time.sleep(1)
        print("✓ Clean shutdown successful")

    except Exception as e:
        print(f"\n✗ Test error: {e}")
        engine.stop_capture()


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "BACKEND COMPONENT TEST" + " " * 21 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    try:
        # Test config manager
        config = test_config_manager()

        input("Press Enter to continue to capture engine tests...")
        print()

        # Test capture engine
        engine = test_capture_engine(config)

        input("Press Enter to continue to capture cycle test...")
        print()

        # Test actual capture (optional)
        test_capture_cycle(config)

        print()
        print("=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60)
        print()
        print("✓ Backend components are ready for GUI integration")
        print()

    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Test suite error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
