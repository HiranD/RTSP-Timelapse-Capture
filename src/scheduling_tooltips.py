"""
Scheduling Panel Tooltips
Provides helpful tooltip messages for the astronomical scheduling interface.
"""

SCHEDULING_TOOLTIPS = {
    # Time mode settings
    "time_mode_twilight": (
        "Use astronomical twilight calculations\n"
        "to automatically determine capture window.\n"
        "Requires location (latitude/longitude) to be set."
    ),
    "time_mode_manual": (
        "Use fixed start/end times for capture window.\n"
        "Does not require location settings.\n"
        "Supports overnight spans (e.g., 22:00 - 06:00)."
    ),
    "manual_start_time": (
        "Capture start time in HH:MM format.\n"
        "Example: 22:00 for 10 PM\n"
        "For overnight captures, use evening time."
    ),
    "manual_end_time": (
        "Capture end time in HH:MM format.\n"
        "Example: 06:00 for 6 AM\n"
        "Can be earlier than start time for overnight captures."
    ),

    # Location settings
    "latitude": (
        "Latitude of your observation location.\n"
        "Range: -90 (South Pole) to +90 (North Pole)\n"
        "Example: 51.5074 for London, -33.8688 for Sydney"
    ),
    "longitude": (
        "Longitude of your observation location.\n"
        "Range: -180 (West) to +180 (East)\n"
        "Example: -0.1278 for London, 151.2093 for Sydney"
    ),

    # Twilight settings
    "twilight_type": (
        "Type of twilight to use for darkness calculation:\n\n"
        "Civil (-6°): Sun 6° below horizon.\n"
        "  Some light remains, outdoor activities possible.\n\n"
        "Nautical (-12°): Sun 12° below horizon.\n"
        "  Horizon still visible at sea, stars appear.\n\n"
        "Astronomical (-18°): Sun 18° below horizon.\n"
        "  True darkness - best for astrophotography."
    ),
    "start_offset": (
        "Minutes to add after darkness begins.\n"
        "Positive values delay start, negative values start earlier.\n"
        "Example: +15 means start 15 minutes after twilight ends.\n"
        "Use to account for local horizon obstructions."
    ),
    "end_offset": (
        "Minutes to add before darkness ends.\n"
        "Negative values end earlier, positive values extend.\n"
        "Example: -15 means stop 15 minutes before dawn.\n"
        "Use to account for local horizon obstructions."
    ),
    "tonight_display": (
        "Calculated darkness window for tonight.\n"
        "Shows start time, end time, and total duration.\n"
        "Times are in your local timezone."
    ),

    # Calendar
    "calendar": (
        "Click on dates to schedule captures.\n\n"
        "Colors:\n"
        "  Green: Past date with captured images\n"
        "  Blue: Scheduled for capture\n"
        "  Gray: Past date without captures\n"
        "  Red border: Today\n\n"
        "Use < > arrows to navigate months."
    ),
    "select_all": (
        "Select all future dates in the visible months.\n"
        "Useful for scheduling a continuous capture period."
    ),
    "clear_all": (
        "Clear all scheduled dates.\n"
        "Does not affect past capture data."
    ),

    # Auto video
    "auto_video": (
        "Automatically create a timelapse video after each\n"
        "night's capture session completes.\n"
        "Uses the selected preset and output folder."
    ),
    "video_preset": (
        "Video export preset to use for auto-created videos.\n"
        "Presets define framerate, quality, and other settings.\n"
        "Configure presets in the Video Export tab."
    ),
    "video_output": (
        "Folder where auto-created videos will be saved.\n"
        "Click Browse to select a different location."
    ),
}
