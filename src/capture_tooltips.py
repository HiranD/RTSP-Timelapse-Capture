"""
Capture Tab Tooltip Messages
Phase 3.6: GUI Tooltip Enhancement

Centralized tooltip text for the Capture tab.
Organized by GUI section for easy reference and maintenance.
"""

CAPTURE_TOOLTIPS = {
    # ========================================
    # Camera Configuration Section
    # ========================================
    "ip_address": (
        "IP address of your RTSP camera on the local network. "
        "Example: 192.168.0.101 or 192.168.0.101:8554 (with custom port)."
    ),

    "username": (
        "RTSP authentication username. "
        "Usually 'admin' for most IP cameras. Check your camera documentation."
    ),

    "password": (
        "RTSP authentication password for your camera. "
        "Saved in plain text in config file - keep config secure."
    ),

    "stream_path": (
        "Camera-specific RTSP stream path. Common examples:\n"
        "Hikvision: /Streaming/Channels/101\n"
        "Dahua: /cam/realmonitor?channel=1&subtype=0\n"
        "UniFi: /s0\n"
        "Generic: /stream1 or /live"
    ),

    "force_tcp": (
        "Force TCP transport instead of UDP for more reliable streaming. "
        "Recommended: Enable for IP cameras to prevent frame drops and disconnections."
    ),

    # ========================================
    # Schedule Section
    # ========================================
    "start_time": (
        "Time to begin capturing in 24-hour format (HH:MM). "
        "Example: 22:40 for 10:40 PM. "
        "Supports overnight schedules (e.g., 22:40 to 07:00)."
    ),

    "end_time": (
        "Time to stop capturing in 24-hour format (HH:MM). "
        "Example: 07:00 for 7:00 AM. "
        "Can be earlier than start time for overnight capture."
    ),

    # ========================================
    # Capture Settings Section
    # ========================================
    "interval": (
        "Seconds between each snapshot. "
        "Examples: 20s = 3 frames/min, 60s = 1 frame/min, 300s = 12 frames/hour. "
        "Range: 1-3600 seconds."
    ),

    "output_folder": (
        "Base folder where snapshots will be saved. "
        "Images are organized in date subfolders (YYYYMMDD/YYYYMMDD-HHMMSS.jpg)."
    ),

    "browse_output": (
        "Select the folder where timelapse snapshots will be saved."
    ),

    "jpeg_quality": (
        "JPEG compression quality for saved images. "
        "Range: 1-100. Higher = better quality but larger files. "
        "Recommended: 85-95 for good balance. "
        "Example: Quality 90 ≈ 400 KB per 720p frame."
    ),

    "proactive_reconnect": (
        "Automatically reconnect to camera every N seconds to prevent firmware timeouts. "
        "0 = disabled (reconnect only on errors). "
        "Recommended: 420s (7 min) for Annke I81EM cameras. "
        "Set to ~40 seconds before your camera's timeout interval."
    ),

    # ========================================
    # Configuration Buttons
    # ========================================
    "save_config": (
        "Save current camera, schedule, and capture settings to a JSON file. "
        "Keyboard shortcut: Ctrl+S"
    ),

    "load_config": (
        "Load previously saved settings from a JSON configuration file. "
        "Keyboard shortcut: Ctrl+O"
    ),

    # ========================================
    # Control Buttons
    # ========================================
    "test_connection": (
        "Test RTSP connection to camera without starting capture. "
        "Verifies credentials and stream availability. "
        "Keyboard shortcut: Ctrl+T"
    ),

    "start_capture": (
        "Begin timelapse capture session with current settings. "
        "Waits for start time if configured. "
        "Keyboard shortcut: Space"
    ),

    "stop_capture": (
        "Stop the current capture session gracefully. "
        "Closes camera connection and logs statistics. "
        "Keyboard shortcut: Esc"
    ),

    # ========================================
    # Preview Section
    # ========================================
    "enable_preview": (
        "Show live preview of captured frames in the GUI. "
        "Disable to improve performance on slower systems or reduce CPU usage."
    ),

    # ========================================
    # Additional Elements
    # ========================================
    "clear_log": (
        "Clear the activity log display. Does not affect saved snapshots or logs."
    ),

    # ========================================
    # Status Information Labels
    # ========================================
    "status_state": (
        "Current capture state: Stopped, Starting, Running, Stopping, or Error."
    ),

    "status_frames": (
        "Total number of frames successfully captured in this session."
    ),

    "status_uptime": (
        "Time elapsed since capture started (HH:MM:SS format)."
    ),

    "status_last_capture": (
        "Timestamp of the most recently captured frame."
    ),

    # ========================================
    # Session Statistics Labels
    # ========================================
    "stats_total_captures": (
        "Total number of successful snapshots captured since this session started. "
        "Excludes failed capture attempts."
    ),

    "stats_success_rate": (
        "Percentage of successful captures out of all capture attempts. "
        "Calculated as: (successful captures) / (total attempts) × 100%"
    ),

    "stats_avg_interval": (
        "Average time between successful captures in this session. "
        "May differ from configured interval due to schedule, reconnects, or delays."
    ),

    "stats_session_duration": (
        "Total elapsed time since the capture session started (HH:MM:SS format). "
        "Continues running until you stop the capture."
    ),
}
