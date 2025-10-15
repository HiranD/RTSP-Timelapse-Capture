# RTSP Timelapse Capture System

A professional Windows desktop application for capturing timelapse images from RTSP camera streams with live preview, scheduling, and comprehensive statistics.

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

## Features

### Core Functionality
- **RTSP Stream Capture** - Connect to any RTSP-compatible camera
- **Overnight Scheduling** - Supports schedules that cross midnight (e.g., 22:40 to 07:00)
- **Automatic Interval Capture** - Configurable capture intervals (1-3600 seconds)
- **Date-Based Organization** - Automatic folder organization by date
- **JPEG Quality Control** - Adjustable image quality (1-100%)

### User Interface
- **Live Preview** - Real-time camera feed display with dynamic auto-scaling
- **Session Statistics** - Track total captures, success rate, average interval, and session duration
- **Activity Log** - Color-coded event logging with timestamps
- **Configuration Management** - Save/load settings as JSON files
- **Keyboard Shortcuts** - Quick access to common actions

### Advanced Features
- **Thread-Safe Architecture** - Responsive UI during capture
- **TCP Forcing** - Force TCP for stable connections
- **Auto-Reconnect** - Automatic retry on connection failure
- **Window Responsive** - Preview scales dynamically with window resize
- **Preferences Auto-Save** - Remembers your settings

## Screenshots

```
┌─────────────────────────────────────────────────────────────┐
│  RTSP Timelapse Capture System                              │
├───────────┬──────────────────┬─────────────────────────────┤
│  CONFIG   │  STATUS/CONTROLS │  LIVE PREVIEW               │
│           │                  │                             │
│  Camera   │  Connection: ✓   │  [Camera Feed Display]      │
│  Settings │  State: Running  │                             │
│           │  Frames: 42      │                             │
│  Schedule │  Uptime: 0:14:03 │  Statistics:                │
│           │                  │  • Total: 42                │
│  Capture  │  [Test Connect]  │  • Success: 100%            │
│  Settings │  [Stop Capture]  │  • Avg: 20.1s               │
│           │                  │  • Duration: 0:14:03        │
├───────────┴──────────────────┴─────────────────────────────┤
│  ACTIVITY LOG                                               │
│  [2025-10-15 00:54:34] Capture started                     │
│  [2025-10-15 00:55:04] Saved frame 1: 20251015-005504.jpg  │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites
- Python 3.8 or higher
- Windows 10/11 (tested)
- RTSP-compatible camera

### Setup

1. **Clone or download the repository**
   ```bash
   git clone https://github.com/yourusername/rtsp-timelapse.git
   cd rtsp-timelapse
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   ```

3. **Activate virtual environment**
   ```bash
   # Windows
   .venv\Scripts\activate

   # Linux/Mac
   source .venv/bin/activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Quick Start

1. **Launch the application**
   ```bash
   python run_gui.py
   ```

2. **Configure your camera**
   - Enter your camera's IP address
   - Provide username and password
   - Set stream path (e.g., `/stream1`)

3. **Set schedule**
   - Start time (HH:MM format)
   - End time (HH:MM format)
   - Capture interval in seconds

4. **Test connection**
   - Click "Test Connection" to verify camera settings

5. **Start capturing**
   - Click "Start Capture"
   - Watch the live preview and statistics update

### Configuration

#### Camera Settings
- **IP Address** - Camera IP (e.g., `192.168.0.101`)
- **Username** - RTSP authentication username
- **Password** - RTSP authentication password
- **Stream Path** - Camera-specific stream path (e.g., `/stream1`)
- **Force TCP** - Use TCP instead of UDP for reliability

#### Schedule Settings
- **Start Time** - When to begin capturing (HH:MM, 24-hour format)
- **End Time** - When to stop capturing (HH:MM, 24-hour format)
- **Overnight Support** - Schedule can cross midnight (e.g., 22:40 to 07:00)

#### Capture Settings
- **Interval** - Seconds between captures (1-3600)
- **Output Folder** - Where to save images
- **JPEG Quality** - Image quality 1-100 (default: 90)

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+S` | Save configuration |
| `Ctrl+O` | Load configuration |
| `Ctrl+T` | Test camera connection |
| `Space` | Start capture (when stopped) |
| `Esc` | Stop capture (when running) |

## Project Structure

```
RSTP/
├── run_gui.py              # Application launcher
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── .gitignore             # Git ignore rules
│
├── src/                   # Source code
│   ├── __init__.py
│   ├── gui_app.py         # Main GUI application
│   ├── capture_engine.py  # RTSP capture logic
│   ├── config_manager.py  # Configuration management
│   └── main.py            # Legacy CLI version
│
├── tests/                 # Test files
│   ├── test_backend.py           # Interactive tests
│   └── test_backend_auto.py      # Automated tests
│
├── docs/                  # Documentation
│   ├── claude.md                 # Development context
│   ├── IMPLEMENTATION_PLAN.md    # Original roadmap
│   ├── GUI_TEST_GUIDE.md         # Testing guide
│   └── PHASE3_SUMMARY.md         # Phase 3 features
│
├── config/                # Configuration files
│   ├── config.py                 # Legacy config
│   ├── camera_config.json        # Current config
│   └── camera_config_example.json # Example template
│
├── examples/              # Example scripts
│
└── snapshots/             # Captured images (gitignored)
    └── YYYYMMDD/          # Organized by date
```

## Configuration File

The application uses JSON configuration files. Example:

```json
{
  "camera": {
    "ip_address": "192.168.0.101",
    "username": "admin",
    "password": "your_password",
    "stream_path": "/stream1",
    "force_tcp": true
  },
  "schedule": {
    "start_time": "22:40",
    "end_time": "07:00",
    "folder_rollover_hour": 12
  },
  "capture": {
    "interval_seconds": 20,
    "jpeg_quality": 90,
    "output_folder": "snapshots",
    "buffer_frames": 4,
    "max_retries": 5
  },
  "ui": {
    "window_width": 1200,
    "window_height": 800,
    "preview_size": "medium",
    "preview_enabled": true
  }
}
```

## Troubleshooting

### Connection Issues
- **Verify camera IP** - Ping the camera: `ping 192.168.0.101`
- **Check credentials** - Ensure username/password are correct
- **Test stream URL** - Try opening in VLC: `rtsp://user:pass@ip/stream1`
- **Firewall** - Ensure port 554 (RTSP) is not blocked
- **Force TCP** - Enable "Force TCP" if UDP connections fail

### Performance Issues
- **Reduce interval** - Longer intervals reduce CPU/network load
- **Lower JPEG quality** - Reduce quality to 70-80 for smaller files
- **Disable preview** - Uncheck "Enable Preview" to save resources
- **Check disk space** - Ensure adequate space in output folder

### Preview Not Updating
- **Check "Enable Preview"** - Ensure checkbox is enabled
- **Verify capture is running** - State should show "Running"
- **Wait for interval** - Preview updates only when frames are captured

## Development

### Running Tests

```bash
# Activate virtual environment
source .venv/Scripts/activate  # or .venv\Scripts\activate on Windows

# Run automated tests
python tests/test_backend_auto.py

# Run interactive tests
python tests/test_backend.py
```

### Code Structure

- **gui_app.py** - Tkinter GUI, handles user interaction
- **capture_engine.py** - Background capture thread, RTSP handling
- **config_manager.py** - Configuration validation and persistence

### Adding Features

1. Create feature branch
2. Update appropriate module
3. Add tests
4. Update documentation
5. Submit pull request

## Technical Details

### Architecture
- **Frontend**: Tkinter (Python standard library)
- **Backend**: Threading-based capture engine
- **Video**: OpenCV for RTSP streaming
- **Images**: PIL/Pillow for processing

### Thread Safety
- All UI updates use `root.after()` for thread-safe callbacks
- Capture engine runs in separate daemon thread
- State synchronized with threading.Lock

### Image Processing Pipeline
```
RTSP Stream (OpenCV) → BGR Frame →
RGB Conversion → PIL Image →
Resize (LANCZOS) → PhotoImage →
Canvas Display
```

## FAQ

**Q: Can I use multiple cameras?**
A: Currently supports one camera per instance. Run multiple instances for multiple cameras.

**Q: What RTSP URL format do I use?**
A: Depends on your camera. Common formats:
- Hikvision: `/Streaming/Channels/101`
- Dahua: `/cam/realmonitor?channel=1&subtype=0`
- Generic: `/stream1` or `/live`

**Q: How much disk space do I need?**
A: At quality 90, each 1280x720 frame is ~400KB. Calculate:
`(3600 / interval) × hours × 0.4 MB`
Example: 20s interval for 8 hours = `(3600/20) × 8 × 0.4 = 576 MB`

**Q: Can I export as a video?**
A: Not currently built-in. Use FFmpeg to create timelapse:
```bash
ffmpeg -framerate 30 -pattern_type glob -i 'snapshots/20251015/*.jpg' output.mp4
```

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - feel free to use and modify for your projects.

## Acknowledgments

- Built with Python, Tkinter, OpenCV, and PIL/Pillow
- Inspired by astronomy timelapse photography needs
- Developed with assistance from Claude AI

## Support

For issues, questions, or feature requests:
- Open an issue on GitHub
- Check the documentation in `docs/`
- Review the test guide: `docs/GUI_TEST_GUIDE.md`

## Changelog

### Version 1.0.0 (2025-10-15)
- ✅ Initial release
- ✅ Full GUI with live preview
- ✅ Overnight schedule support
- ✅ Session statistics
- ✅ Keyboard shortcuts
- ✅ Dynamic preview scaling
- ✅ Configuration management

---

**Made with ❤️ for timelapse photography**
