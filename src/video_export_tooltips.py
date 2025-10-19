"""
Video Export Tooltip Messages
Phase 3.6: GUI Tooltip Enhancement

Centralized tooltip text for the Video Export tab.
Organized by GUI section for easy reference and maintenance.
"""

VIDEO_EXPORT_TOOLTIPS = {
    # ========================================
    # Input Selection Section
    # ========================================
    "source_folder": (
        "Path to folder containing captured images. "
        "Images should be in YYYYMMDD-HHMMSS.jpg format."
    ),

    "browse_source": (
        "Browse your file system to select a folder containing timelapse images."
    ),

    "quick_select": (
        "Quickly select from recently captured date folders in the snapshots directory."
    ),

    # ========================================
    # Video Settings Section
    # ========================================
    "framerate": (
        "Video playback speed in frames per second (fps). "
        "24 = cinematic look, 30 = smooth, 60 = ultra-smooth. "
        "Range: 1-120 fps."
    ),

    "quality_crf": (
        "Video compression quality using CRF (Constant Rate Factor). "
        "Range: 0-51. Lower = better quality but larger file size. "
        "Recommended: 18 = visually lossless, 20 = excellent, 23 = good."
    ),

    "speed_multiplier": (
        "Skip frames to speed up playback. "
        "1x = use all frames, 2x = every other frame, 4x = every 4th frame. "
        "Higher values create faster motion timelapses."
    ),

    "resolution": (
        "Output video resolution. "
        "'original' keeps the source image resolution. "
        "Other options downscale to save file size (e.g., 1920x1080 = 1080p)."
    ),

    "format": (
        "Output video container format. "
        "MP4 recommended for best compatibility with media players and browsers."
    ),

    # ========================================
    # Output Options Section
    # ========================================
    "output_file": (
        "Full path where the video will be saved. "
        "The app remembers your last export location."
    ),

    "browse_output": (
        "Choose where to save the output video file."
    ),

    "preserve_originals": (
        "Creates temporary numbered copies for FFmpeg processing. "
        "Your original timestamped files remain untouched. "
        "Recommended: Keep enabled."
    ),

    "frame_counter": (
        "Adds frame number overlay to the video (e.g., 'Frame 1', 'Frame 2'). "
        "Useful for quality assurance and debugging."
    ),

    "open_when_done": (
        "Automatically opens the video in your default media player after export completes."
    ),

    # ========================================
    # Presets Section
    # ========================================
    "preset_select": (
        "Choose from built-in or custom presets to quickly apply common settings. "
        "Built-in presets: Standard 24fps, High Quality 30fps, Fast Motion 60fps, "
        "Web Optimized, Storage Saver, Ultra Speed 16x."
    ),

    "save_preset": (
        "Save current settings as a custom preset for reuse. "
        "Your custom presets are stored alongside built-in presets."
    ),

    "manage_presets": (
        "View, delete, or organize your custom presets. "
        "Built-in presets cannot be modified or deleted."
    ),

    # ========================================
    # Action Buttons
    # ========================================
    "create_video": (
        "Start encoding the video with current settings. "
        "FFmpeg must be installed for this to work."
    ),

    "cancel": (
        "Stop the current video export operation. "
        "Partial files and temp folders will be cleaned up."
    ),

    "test_ffmpeg": (
        "Check if FFmpeg is installed and accessible. "
        "FFmpeg is required for video export functionality."
    ),

    # ========================================
    # Information Labels
    # ========================================
    "image_info": (
        "Summary of scanned images: total count, date range, duration, and total file size."
    ),

    "estimate": (
        "Estimated video duration and file size based on current settings. "
        "Actual results may vary slightly."
    ),

    "status": (
        "Current export status. Shows progress, completion, or errors."
    ),

    "progress_details": (
        "Real-time encoding statistics from FFmpeg: frame number, encoding speed, and output size."
    ),
}
