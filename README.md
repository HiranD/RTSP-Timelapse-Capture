# RTSP Timelapse Capture System

> A professional Windows desktop application for capturing and creating timelapse videos from RTSP camera streams.

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)
![Status](https://img.shields.io/badge/status-production-green.svg)

**Complete end-to-end timelapse workflow:** Capture images → Export to video → All in one GUI!

---

## 🎬 Features

### Image Capture
- 📷 **RTSP Stream Capture** - Connect to any RTSP-compatible camera
- ⏰ **Smart Scheduling** - Overnight support (e.g., 22:40 PM to 07:00 AM)
- 🔄 **Auto-Interval Capture** - 1-3600 seconds between frames
- 📁 **Date Organization** - Automatic folder structure by date
- 🎨 **Quality Control** - Adjustable JPEG quality (1-100%)
- 👁️ **Live Preview** - Real-time camera feed with auto-scaling
- 📊 **Session Statistics** - Track captures, success rate, uptime

### Video Export ✨ NEW!
- 🎥 **One-Click Export** - Convert images to video instantly
- 🎛️ **Built-in Presets** - 6 professional presets ready to use
- ⚙️ **Full Customization** - Frame rate, quality, resolution, speed
- 🔒 **Non-Destructive** - Original images never modified
- 📈 **Progress Tracking** - Real-time encoding progress
- 💾 **Smart Estimates** - Duration and file size predictions
- 🎨 **Frame Overlays** - Optional frame counter overlay

### User Experience
- 🖥️ **Tabbed Interface** - Capture | Video Export
- ⌨️ **Keyboard Shortcuts** - Quick access to common actions
- 💾 **Auto-Save Settings** - Remembers your preferences
- 🔄 **Thread-Safe** - Responsive UI, never freezes
- 📝 **Activity Logs** - Color-coded event logging
- 🌐 **Cross-Platform** - Windows tested, Linux/macOS compatible

---

## 📸 Screenshots

### Capture Tab
```
┌─────────────────────────────────────────────────────────────┐
│  RTSP Timelapse Capture System                       [Tabs] │
├─────────────────────────────────────────────────────────────┤
│  ┌──[ Capture ]──┬──[ Video Export ]──┐                     │
│  │                                                           │
│  │  ┌─ Camera Config ─┐  ┌─ Status ──┐  ┌─ Live Preview ─┐ │
│  │  │ IP: 192.168.0.1 │  │ ● Running │  │                 │ │
│  │  │ User: admin     │  │ Frames: 42│  │  [Camera Feed]  │ │
│  │  │ Path: /stream1  │  │ Up: 14:03 │  │                 │ │
│  │  └────────────────┘  └───────────┘  └─────────────────┘ │
│  │                                                           │
│  │  ┌─ Schedule ──────┐  ┌─ Controls ────┐                 │
│  │  │ Start: 22:40    │  │ [Start]       │  Statistics:    │
│  │  │ End:   07:00    │  │ [Stop]        │  • Total: 42    │
│  │  │ Int:   20s      │  │ [Test]        │  • Success: 100%│
│  │  └─────────────────┘  └───────────────┘  • Avg: 20.1s   │
│  │                                                           │
│  │  ┌─ Activity Log ──────────────────────────────────────┐ │
│  │  │ [00:55:04] Capture started                          │ │
│  │  │ [00:55:24] Saved: 20251015-005524.jpg               │ │
│  │  └─────────────────────────────────────────────────────┘ │
│  └───────────────────────────────────────────────────────────┘
```

### Video Export Tab
```
┌─────────────────────────────────────────────────────────────┐
│  ┌──[ Capture ]──┬──[✓ Video Export ]──┐                    │
│  │                                                           │
│  │  ┌─ Input Selection ─────────────────────────────────┐   │
│  │  │ Folder: snapshots/20251015/    [Browse] [Quick]  │   │
│  │  │ Found: 1,234 images | 6h 17m | 2025-10-15        │   │
│  │  └──────────────────────────────────────────────────┘   │
│  │                                                           │
│  │  ┌─ Video Settings ──────────────────────────────────┐   │
│  │  │ Frame Rate: [24] fps    Quality: [20] (lower=best)│   │
│  │  │ Speed: [1x] ▼           Resolution: [Original] ▼  │   │
│  │  │ Format: [MP4] ▼         Est: 51s video, ~12 MB   │   │
│  │  └──────────────────────────────────────────────────┘   │
│  │                                                           │
│  │  ┌─ Presets ─────────────────────────────────────────┐   │
│  │  │ [Standard 24fps ▼]  [Save As] [Manage]           │   │
│  │  └──────────────────────────────────────────────────┘   │
│  │                                                           │
│  │  ┌─ Progress ────────────────────────────────────────┐   │
│  │  │ Status: Encoding... (frame 562/1234)              │   │
│  │  │ [████████████████░░░░░░░░] 45%                   │   │
│  │  │ Elapsed: 00:02:15 | Remaining: ~00:02:50         │   │
│  │  └──────────────────────────────────────────────────┘   │
│  │                                                           │
│  │  [Create Video] [Cancel]                                │
│  └───────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/rtsp-timelapse.git
   cd rtsp-timelapse
   ```

2. **Install dependencies**
   ```bash
   # Create virtual environment
   python -m venv .venv

   # Activate (Windows)
   .venv\Scripts\activate

   # Activate (Linux/Mac)
   source .venv/bin/activate

   # Install packages
   pip install -r requirements.txt
   ```

3. **Install FFmpeg** (required for video export)
   - Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - Add to system PATH **OR** place `ffmpeg.exe` in `bin/` folder
   - Verify: `ffmpeg -version`

4. **Launch the application**
   ```bash
   python run_gui.py
   ```

---

## 📖 Usage Guide

### Capturing Images

#### 1. Configure Camera (Capture Tab)
```
Camera Settings:
  IP Address:  192.168.0.101
  Username:    admin
  Password:    ••••••••
  Stream Path: /stream1
  Force TCP:   ☑ (recommended)
```

#### 2. Set Schedule
```
Schedule:
  Start Time:  22:40  (10:40 PM)
  End Time:    07:00  (7:00 AM)
  Interval:    20     (seconds)
```

#### 3. Start Capture
- Click **"Test Connection"** to verify camera
- Click **"Start Capture"** to begin
- Watch live preview and statistics
- Capture runs automatically until end time

#### Output Structure
```
snapshots/
├── 20251015/
│   ├── 20251015-224000.jpg
│   ├── 20251015-224020.jpg
│   ├── 20251015-224040.jpg
│   └── ... (1,234 images)
└── 20251016/
    └── ...
```

---

### Creating Videos ✨

#### Quick Export (Using Presets)

1. **Switch to Video Export tab**
2. Click **"Quick Select"** → Choose date folder
3. Select a preset:
   - **Standard 24fps** - General purpose
   - **High Quality 30fps** - Best quality
   - **Fast Motion 60fps** - Smooth, 4x speed
   - **Web Optimized** - YouTube/social media
   - **Storage Saver** - Small file size
   - **Ultra Speed 16x** - Very fast timelapse
4. Click **"Create Video"**
5. Video opens automatically when done!

#### Custom Export

**Frame Rate** (1-120 fps)
- 24 fps = Standard cinema look
- 30 fps = Smooth, natural motion
- 60 fps = Ultra-smooth, professional

**Quality - CRF** (0-51, lower = better)
- 18 = Very high quality, large files
- 20 = High quality (recommended)
- 23 = Medium quality, smaller files
- 28 = Lower quality, very small files

**Speed Multiplier**
- 1x = Use all images
- 2x = Use every 2nd image (2x faster)
- 4x = Use every 4th image (4x faster)
- 8x/16x/32x = Even faster timelapses

**Resolution**
- Original = Keep source resolution
- 1920×1080 = Full HD
- 1280×720 = HD
- 640×360 = Low bandwidth

**Example Settings**
```
For 1,234 images captured over 6 hours:

Standard Export:
  24 fps, 1x speed → 51 second video, ~12 MB

Fast Motion:
  60 fps, 4x speed → 5 second video, ~3 MB

Ultra Speed:
  30 fps, 16x speed → 2.5 second video, ~1 MB
```

---

## ⚙️ Configuration

### Camera Settings

| Setting | Description | Example |
|---------|-------------|---------|
| IP Address | Camera's network IP | `192.168.0.101` |
| Username | RTSP authentication | `admin` |
| Password | RTSP password | `YourPassword123` |
| Stream Path | Camera-specific path | `/stream1` |
| Force TCP | Use TCP (more stable) | ☑ Recommended |

**Common Stream Paths:**
- **Hikvision:** `/Streaming/Channels/101`
- **Dahua:** `/cam/realmonitor?channel=1&subtype=0`
- **Generic:** `/stream1`, `/live`, `/h264`

### Schedule Settings

| Setting | Description | Example |
|---------|-------------|---------|
| Start Time | Begin capturing (24h) | `22:40` |
| End Time | Stop capturing (24h) | `07:00` |
| Interval | Seconds between captures | `20` |

**Overnight Support:** Start time can be later than end time (crosses midnight)

### Capture Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Output Folder | Where to save images | `snapshots` |
| JPEG Quality | Image quality (1-100) | `90` |
| Buffer Frames | Read-ahead buffer | `4` |
| Max Retries | Connection retry attempts | `5` |

---

## ⌨️ Keyboard Shortcuts

### Capture Tab
| Shortcut | Action |
|----------|--------|
| `Ctrl+S` | Save configuration |
| `Ctrl+O` | Load configuration |
| `Ctrl+T` | Test camera connection |
| `Space` | Start capture (when stopped) |
| `Esc` | Stop capture (when running) |

### Video Export Tab
| Shortcut | Action |
|----------|--------|
| `Ctrl+E` | Open video export tab |
| `Ctrl+B` | Browse for folder |
| `Enter` | Start video export |
| `Esc` | Cancel export |

---

## 🎯 Video Export Presets

### Built-in Presets

| Preset | Frame Rate | Quality | Speed | Resolution | Best For |
|--------|-----------|---------|-------|------------|----------|
| **Standard 24fps** | 24 fps | CRF 20 | 1x | Original | General purpose |
| **High Quality 30fps** | 30 fps | CRF 18 | 1x | Original | Best quality output |
| **Fast Motion 60fps** | 60 fps | CRF 20 | 4x | Original | Smooth, fast motion |
| **Web Optimized** | 30 fps | CRF 23 | 1x | 720p | YouTube, social media |
| **Storage Saver** | 20 fps | CRF 28 | 1x | 480p | Small file sizes |
| **Ultra Speed 16x** | 30 fps | CRF 20 | 16x | Original | Very fast timelapses |

### Custom Presets

**Save Your Own:**
1. Configure settings to your liking
2. Click "Save As Preset"
3. Name your preset
4. Use anytime with one click!

**Manage Presets:**
- View all custom presets
- Delete unwanted presets
- Export/import preset collections

---

## 🔧 Project Structure

```
RSTP/
├── run_gui.py                    # Application launcher
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── .gitignore                    # Git ignore rules
│
├── src/                          # Source code
│   ├── __init__.py
│   ├── gui_app.py               # Main GUI (tabbed interface)
│   ├── capture_engine.py        # RTSP capture logic
│   ├── config_manager.py        # Configuration management
│   ├── video_export_panel.py    # Video export GUI
│   ├── video_export_controller.py # Video export logic
│   ├── ffmpeg_wrapper.py        # FFmpeg integration
│   ├── preset_manager.py        # Preset management
│   └── main.py                  # Legacy CLI version
│
├── tests/                        # Test files
│   ├── test_backend.py          # Interactive backend tests
│   ├── test_backend_auto.py     # Automated tests
│   └── test_video_export.py     # Video export tests
│
├── docs/                         # Documentation
│   ├── claude.md                # Development context
│   ├── IMPLEMENTATION_PLAN.md   # Project roadmap
│   ├── PHASE3.5_VIDEO_EXPORT_PLAN.md
│   ├── PHASE3.5_COMPLETE.md     # Video export summary
│   └── GUI_TEST_GUIDE.md        # Testing guide
│
├── config/                       # Configuration files
│   ├── camera_config.json       # Current config (auto-saved)
│   └── camera_config_example.json # Template
│
├── bin/                          # Optional FFmpeg location
│   └── ffmpeg.exe               # (not included, user provides)
│
└── snapshots/                    # Captured images (gitignored)
    └── YYYYMMDD/                # Date-organized folders
        └── YYYYMMDD-HHMMSS.jpg  # Timestamped images
```

---

## 🐛 Troubleshooting

### Camera Connection Issues

**Problem:** Can't connect to camera
- ✅ Verify camera IP: `ping 192.168.0.101`
- ✅ Check credentials are correct
- ✅ Test stream URL in VLC: `rtsp://user:pass@ip/stream1`
- ✅ Ensure port 554 (RTSP) not blocked by firewall
- ✅ Try enabling "Force TCP" option

**Problem:** Connection drops frequently
- ✅ Enable "Force TCP" (more stable than UDP)
- ✅ Check network stability
- ✅ Reduce capture interval (less frequent requests)

### Video Export Issues

**Problem:** FFmpeg not found
```
Solution:
1. Download FFmpeg from https://ffmpeg.org/download.html
2. Extract files
3. Add to system PATH OR place in bin/ folder
4. Click "Test FFmpeg" button to verify
```

**Problem:** Export is slow
- ✅ Lower resolution (720p or 480p)
- ✅ Increase CRF quality value (23-28)
- ✅ Use speed multiplier (2x, 4x)
- ✅ Close other applications

**Problem:** Video won't play
- ✅ Ensure using MP4 format (most compatible)
- ✅ Try opening in VLC media player
- ✅ Check FFmpeg export log for errors

### Performance Issues

**Problem:** GUI is slow/laggy
- ✅ Disable live preview (uncheck "Enable Preview")
- ✅ Lower JPEG quality (70-80 instead of 90)
- ✅ Increase capture interval (30s+ instead of 20s)
- ✅ Close background applications

**Problem:** Disk filling up
- ✅ Check available space regularly
- ✅ Lower JPEG quality
- ✅ Delete old snapshots after exporting to video
- ✅ Use "Storage Saver" preset for videos

**Disk Space Calculator:**
```
At quality 90, each 1280×720 frame ≈ 400KB

Formula: (3600 / interval) × hours × 0.4 MB

Example: 20s interval for 8 hours
= (3600/20) × 8 × 0.4
= 576 MB for images
+ ~50 MB for final video
= ~625 MB total
```

---

## 💻 Technical Details

### Architecture

**Frontend:** Tkinter (Python standard library)
**Backend:** Threading-based capture engine
**Video:** OpenCV for RTSP streaming
**Images:** PIL/Pillow for processing
**Export:** FFmpeg for video encoding

### Dependencies

```txt
opencv-python==4.10.0.82   # RTSP capture & processing
numpy==1.26.4              # Numerical operations
Pillow>=10.0.0             # Image processing
```

**External:** FFmpeg (required for video export)

### Thread Safety

- All UI updates use `root.after()` for thread-safe callbacks
- Capture engine runs in separate daemon thread
- Video export runs in background thread
- State synchronized with `threading.Lock`

### Image Processing Pipeline

```
RTSP Stream (OpenCV)
    ↓
BGR Frame Capture
    ↓
RGB Conversion
    ↓
PIL Image Object
    ↓
Resize (LANCZOS)
    ↓
PhotoImage (Tkinter)
    ↓
Canvas Display
```

### Video Export Pipeline

```
Image Files (JPG)
    ↓
Scan & Timestamp Extract
    ↓
Copy to Temp (Sequential Numbering)
    ↓
FFmpeg Command Build
    ↓
H.264 Encoding (MP4)
    ↓
Progress Parsing
    ↓
Final Video + Cleanup
```

---

## ❓ FAQ

### General

**Q: Can I use multiple cameras?**
A: Currently supports one camera per instance. Run multiple instances for multiple cameras. Multi-camera support planned for future version.

**Q: Does it work on Linux/macOS?**
A: Yes! Tested primarily on Windows, but compatible with Linux/macOS. Just install dependencies and FFmpeg for your OS.

**Q: Can I run it headless (no GUI)?**
A: Not currently. The legacy CLI version (`src/main.py`) exists but isn't maintained. GUI is recommended.

### Camera Setup

**Q: What RTSP URL format do I use?**
A: Depends on your camera brand:
- **Hikvision:** `rtsp://user:pass@ip/Streaming/Channels/101`
- **Dahua:** `rtsp://user:pass@ip/cam/realmonitor?channel=1&subtype=0`
- **Amcrest:** `rtsp://user:pass@ip/cam/realmonitor?channel=1&subtype=1`
- **Reolink:** `rtsp://user:pass@ip/h264Preview_01_main`
- **Generic:** `rtsp://user:pass@ip/stream1` or `/live`

**Q: My camera requires a specific port. How do I set it?**
A: Include port in IP address: `192.168.0.101:8554`

**Q: Can I test without a camera?**
A: Yes, use a public RTSP test stream:
```
rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4
```

### Video Export

**Q: What's the best preset for YouTube?**
A: Use **"Web Optimized"** (30fps, 720p) or **"High Quality 30fps"** (original resolution).

**Q: How do I make a very fast timelapse?**
A: Use **"Ultra Speed 16x"** preset or set Speed Multiplier to 8x/16x/32x.

**Q: Can I add music to the video?**
A: Not built-in yet. Use video editing software to add audio after export.

**Q: Why are my original files safe?**
A: The export creates temporary numbered copies in `.temp_export_*/` folder. Your originals are never renamed or modified. Temp folder is automatically deleted after export.

**Q: Can I pause and resume export?**
A: No, but you can cancel anytime. Progress is lost if cancelled. Future enhancement planned.

### Performance

**Q: How long does export take?**
A: Depends on settings and hardware:
- **1000 images → 720p:** ~30-60 seconds
- **1000 images → 1080p:** ~60-120 seconds
- **5000 images → 4K:** ~5-10 minutes

**Q: Can I use GPU acceleration?**
A: Not yet. Currently uses CPU encoding. GPU acceleration (NVENC, QuickSync) is a planned enhancement.

---

## 🧪 Testing

### Run Tests

```bash
# Activate virtual environment
source .venv/Scripts/activate  # Windows: .venv\Scripts\activate

# Test backend capture engine
python tests/test_backend_auto.py

# Test video export
python test_video_export.py

# Interactive backend test
python tests/test_backend.py
```

### Manual Testing

1. **Capture Test**
   - Configure with test RTSP stream
   - Set 10-second interval
   - Capture for 2 minutes
   - Verify 12 images saved

2. **Video Export Test**
   - Select test folder
   - Use "Standard 24fps" preset
   - Export video
   - Verify video plays correctly

---

## 🤝 Contributing

Contributions welcome! Please follow these steps:

1. **Fork the repository**
2. **Create feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Make your changes**
   - Add new features
   - Fix bugs
   - Improve documentation
4. **Add tests**
   - Test your changes thoroughly
   - Add automated tests if applicable
5. **Commit changes**
   ```bash
   git commit -m "Add amazing feature"
   ```
6. **Push to branch**
   ```bash
   git push origin feature/amazing-feature
   ```
7. **Open Pull Request**
   - Describe your changes
   - Reference any related issues

### Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/rtsp-timelapse.git

# Create virtual environment
python -m venv .venv
source .venv/Scripts/activate

# Install dev dependencies
pip install -r requirements.txt

# Run tests
python tests/test_backend_auto.py
```

---

## 📝 License

MIT License - See [LICENSE](LICENSE) file for details.

**TL;DR:** Free to use, modify, and distribute. No warranty provided.

---

## 🙏 Acknowledgments

- **Python** - Amazing language for rapid development
- **Tkinter** - Built-in GUI framework
- **OpenCV** - Powerful video processing library
- **FFmpeg** - Industry-standard video encoding
- **PIL/Pillow** - Image processing excellence
- **Claude AI** - Development assistance
- **Open Source Community** - Inspiration and support

---

## 📞 Support

### Get Help

- 📖 **Documentation:** Check `docs/` folder
- 🐛 **Bug Reports:** [Open an issue](https://github.com/yourusername/rtsp-timelapse/issues)
- 💡 **Feature Requests:** [Open an issue](https://github.com/yourusername/rtsp-timelapse/issues)
- 📧 **Email:** your.email@example.com

### Useful Resources

- [FFmpeg Download](https://ffmpeg.org/download.html)
- [RTSP Protocol Info](https://en.wikipedia.org/wiki/Real_Time_Streaming_Protocol)
- [Tkinter Documentation](https://docs.python.org/3/library/tkinter.html)
- [OpenCV Python Tutorials](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html)

---

## 📊 Changelog

### Version 2.0.0 (2025-10-15) ✨ CURRENT

**Major Release: Video Export Feature**
- ✅ Complete video export functionality
- ✅ 6 built-in presets (Standard, High Quality, Fast Motion, Web, Storage Saver, Ultra Speed)
- ✅ Custom preset save/load/manage
- ✅ Non-destructive workflow (temp copies)
- ✅ Real-time progress tracking
- ✅ FFmpeg integration with auto-detection
- ✅ Frame rate, quality, speed, resolution customization
- ✅ Tabbed interface (Capture | Video Export)
- ✅ Duration and file size estimation
- ✅ Frame counter overlay option
- ✅ Auto-open video when complete

**Improvements:**
- ✅ Enhanced GUI with tabbed layout
- ✅ Better error handling and user feedback
- ✅ Comprehensive test suite
- ✅ Updated documentation

### Version 1.0.0 (2025-10-14)

**Initial Release**
- ✅ Full GUI with live preview
- ✅ RTSP camera capture
- ✅ Overnight schedule support
- ✅ Session statistics
- ✅ Keyboard shortcuts
- ✅ Dynamic preview scaling
- ✅ Configuration management
- ✅ Activity logging
- ✅ Thread-safe architecture

---

## 🗺️ Roadmap

### Version 2.1 (Planned)
- ☐ Multi-camera support (multiple tabs)
- ☐ Batch video export (queue multiple folders)
- ☐ Advanced timestamp overlay (actual timestamps)
- ☐ Video preview before export

### Version 2.2 (Planned)
- ☐ GPU acceleration (NVENC, QuickSync, VideoToolbox)
- ☐ Audio track support (background music)
- ☐ Video stabilization
- ☐ Color correction filters

### Version 3.0 (Future)
- ☐ Cloud upload (YouTube, Vimeo, Dropbox)
- ☐ Mobile app for monitoring
- ☐ Email notifications
- ☐ Motion detection
- ☐ Time-based filtering (day/night only)

### Community Requested
- ☐ Executable build (no Python required)
- ☐ System tray integration
- ☐ Auto-start with Windows
- ☐ Remote API for automation

---

## 🌟 Star History

If you find this project useful, please consider giving it a ⭐ on GitHub!

---

## 📸 Use Cases

### Astronomy Photography
- **Setup:** Point camera at night sky
- **Schedule:** 22:00 to 06:00, 30s intervals
- **Export:** Ultra Speed 16x for fast cloud movement
- **Result:** 8-hour night compressed to 90 seconds

### Construction Progress
- **Setup:** Fixed camera on construction site
- **Schedule:** 08:00 to 17:00, 60s intervals
- **Export:** Standard 24fps for smooth progress
- **Result:** Day of construction in 2 minutes

### Weather Monitoring
- **Setup:** Outdoor weather camera
- **Schedule:** All day, 10s intervals
- **Export:** Fast Motion 60fps, 4x speed
- **Result:** Full day of weather in 3 minutes

### Wildlife Observation
- **Setup:** Camera at bird feeder
- **Schedule:** Dawn to dusk, 15s intervals
- **Export:** High Quality 30fps for detail
- **Result:** Day of wildlife activity in 5 minutes

### Plant Growth
- **Setup:** Indoor camera on plant
- **Schedule:** 24/7, 300s intervals
- **Export:** Ultra Speed 16x, week to 30 seconds
- **Result:** Week of growth in half a minute

---

<div align="center">

## From Wandering Astrophotography

**[⬆ Back to Top](#rtsp-timelapse-capture-system)**

</div>
