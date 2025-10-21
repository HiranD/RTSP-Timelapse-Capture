# RTSP Timelapse Capture System

> A professional Windows desktop application for capturing and creating timelapse videos from RTSP camera streams.

![Version](https://img.shields.io/badge/version-2.3.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)
![Status](https://img.shields.io/badge/status-production-green.svg)

**Complete end-to-end timelapse workflow:** capture stills + export to video + manage it all from one GUI.

---

## Key Features

### Image Capture
- RTSP stream capture with optional TCP forcing for stability.
- **Multi-threaded bufferless capture** for accurate timestamps (±5 second precision).
- **Proactive reconnection** to prevent camera firmware timeouts (100% capture success rate).
- Smart scheduling that supports overnight windows (e.g., 22:40 → 07:00).
- Automatic interval capture from 1 to 3600 seconds.
- Automatic date-based folder structure for snapshots.
- Adjustable JPEG output quality (1–100%).
- Live preview with auto-scaling and JPEG compression control.
- Session statistics with uptime, success rate, and error tracking.

### Video Export (New in v2.0)
- One-click export from image folders to MP4.
- Six built-in presets plus unlimited custom presets.
- Full control over frame rate, CRF quality, resolution, and playback speed.
- Non-destructive—source images are never modified.
- Real-time progress, ETA, and output size estimates.
- Optional frame counter overlay.

### User Experience
- Two-tab interface: **Capture** and **Video Export**.
- **Comprehensive tooltip system** with 37 hover tooltips explaining every control.
- Keyboard shortcuts for common actions.
- Auto-save of UI preferences.
- Thread-safe capture engine keeps the UI responsive.
- Color-coded activity log with timestamps.
- Cross-platform Python source (Windows-focused release builds).

---

## Screenshots

### Capture Tab
![Snapshot Capturing Interface](screenshots/Snapshot_capturing.jpg)  
*Live capture interface showing camera configuration, real-time preview, session statistics, and activity logging.*

### Video Export Tab
![Video Export Interface](screenshots/Video_export.jpg)  
*Video export interface with input selection, customizable settings, presets management, and real-time encoding progress.*

---

## Quick Start

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
   - Download from [ffmpeg.org](https://ffmpeg.org/download.html).
   - Add `ffmpeg.exe` to your PATH **or** place it in a `bin/` folder beside the app.
   - Verify with `ffmpeg -version`.

4. **Launch the application**
   ```bash
   python run_gui.py
   ```

---

## Using the Capture Tab

### Learning the Interface

**Hover your mouse** over any button, input field, or checkbox for helpful tooltips that explain:
- What the control does
- Expected values and formats
- Recommended settings
- Keyboard shortcuts
- Common examples

**Example tooltips:**
- *IP Address:* "IP address of your RTSP camera on the local network. Example: 192.168.0.101"
- *Proactive Reconnect:* "Automatically reconnect every N seconds to prevent timeouts. Recommended: 420s for Annke cameras"
- *Frame Rate:* "Video playback speed in fps. 24 = cinematic, 30 = smooth, 60 = ultra-smooth"

1. **Configure Camera**
   ```
   Camera Settings:
     IP Address:  192.168.0.101
     Username:    admin
     Password:    ********
     Stream Path: /stream1
     Force TCP:   Enabled (recommended for most IP cameras)
   ```

2. **Set Schedule**
   ```
   Schedule:
     Start Time:  22:40  (10:40 PM)
     End Time:    07:00  (7:00 AM)
     Interval:    20     (seconds)
   ```

3. **Start Capture**
   - Click **Test Connection** to verify credentials and stream.
   - Click **Start Capture** to begin the timelapse session.
   - Watch the live preview, session statistics, and activity log.

4. **Output Structure**
   ```
   snapshots/
     20251015/
       20251015-224000.jpg
       20251015-224020.jpg
       ...
     20251016/
       20251016-070000.jpg
       ...
   ```

---

## Creating Videos from Snapshots

### Quick Export with Presets

1. Switch to the **Video Export** tab.
2. Click **Quick Select** and choose the desired date folder.
3. Pick a preset:
   - **Standard 24fps** – Balanced quality.
   - **High Quality 30fps** – Lower compression, smoother output.
   - **Fast Motion 60fps** – Every 4th frame for ultra-smooth motion.
   - **Web Optimized** – Ready for YouTube/social uploads.
   - **Storage Saver** – Small files for archival use.
   - **Ultra Speed 16x** – Extreme speed-ups for rapid reviews.
4. Click **Create Video**. The video opens automatically if you enable that option.

### Custom Export

- **Frame Rate**: 1–120 fps (24 for cinematic, 30 for smooth, 60 for ultra-smooth).
- **Quality (CRF)**: 18 = visually lossless, 20 = default, 23+ = smaller files.
- **Speed Multiplier**: Skip frames to speed up (2×, 4×, 8×, 16×, 32×).
- **Resolution**: Keep original size or scale to 4K / 1080p / 720p / 480p / 360p.
- **Overlay**: Optional frame counter overlay for QA workflows.

Example outputs for 1,234 images captured over 6 hours:
```
Standard Export:
  24 fps, 1x speed → 51 s video, ~12 MB

Fast Motion:
  60 fps, 4x speed → 5 s video, ~3 MB

Ultra Speed:
  30 fps, 16x speed → 2.5 s video, ~1 MB
```

---

## Configuration Reference

### Camera Settings

| Setting     | Description                | Example                    |
|-------------|----------------------------|----------------------------|
| IP Address  | Camera IP on your network  | `192.168.0.101`            |
| Username    | RTSP authentication user   | `admin`                    |
| Password    | RTSP authentication pass   | `YourPassword123`          |
| Stream Path | Camera-specific RTSP path  | `/stream1`                 |
| Force TCP   | Use TCP for stability      | `True` (recommended)       |

**Common RTSP Paths**
- **Hikvision**: `/Streaming/Channels/101`
- **Dahua**: `/cam/realmonitor?channel=1&subtype=0`
- **Ubiquiti/UniFi**: `/s0`
- **Generic**: `/stream1`, `/live`, `/h264`

### Schedule Settings

| Setting     | Description                       | Example |
|-------------|-----------------------------------|---------|
| Start Time  | Capture start (24-hour HH:MM)     | `22:40` |
| End Time    | Capture end (24-hour HH:MM)       | `07:00` |
| Interval    | Seconds between captures          | `20`    |
| Rollover    | Hour after midnight to switch day | `12`    |

Overnight windows (start later than end) are handled automatically.

### Capture Settings

| Setting                  | Description                      | Default  |
|--------------------------|----------------------------------|----------|
| Output Folder            | Base folder for snapshots        | `snapshots` |
| JPEG Quality             | Saved image quality (higher = better quality but larger files) | `95` |
| Buffer Frames            | Frames to buffer in OpenCV       | `2`      |
| Max Retries              | Connection retry attempts        | `5`      |
| Proactive Reconnect (s)  | Reconnect interval to prevent camera timeout (0 = disabled) | `0` |

---

## Camera Configuration Tips

- **Verify credentials**: Use VLC or `ffplay` to confirm IP, username, password, and stream path before configuring the app.
- **Prefer TCP**: Many consumer IP cameras are unreliable over UDP; keep **Force TCP** enabled unless the camera vendor recommends otherwise.
- **Mind network latency**: For remote cameras, increase `buffer_frames` (e.g., to 6-8) if you frequently see reconnect messages.
- **Deal with overnight lighting**: Configure the camera's own exposure or IR settings; the app captures whatever the RTSP feed delivers.
- **Multiple cameras**: Copy `config/camera_config_example.json` per device and load them through the GUI to swap configurations quickly.
- **Security**: Store configs in a protected location if the RTSP password is sensitive; the app saves the password in plain text JSON.
- **Prevent camera timeouts**: Enable **Proactive Reconnect** to maintain 100% capture success rate. Most IP cameras have firmware timeouts (typically 5-10 minutes). Set the reconnect interval to ~40 seconds before your camera's timeout for uninterrupted captures.

### Optimal Settings for Annke I81EM Cameras

Based on extensive testing with Annke I81EM IP cameras, two configurations are recommended depending on your needs:

**Camera Settings (Web Interface) - Same for Both Configurations:**
- Frame Rate: `10 FPS` (provides fresh frames without overwhelming buffer)
- I Frame Interval: `4` (keyframe every 0.4 seconds for accurate timestamps)
- Max Bitrate: `3072 Kbps` or lower (stable streaming over network)

#### Configuration A: Maximum Timestamp Accuracy (Recommended)

**Best for:** Most timelapse applications where timestamp precision matters

**Application Settings:**
- Capture Interval: `30 seconds`
- Buffer Frames: `1` (minimal buffer for freshest frames)
- Proactive Reconnect: `300 seconds` (5 minutes - before 460s camera timeout)
- Force TCP: `Enabled` (required for stability)

**Performance Results:**
- 100% capture success rate ✅
- Timestamp accuracy: **±5 seconds** (stable throughout session) - 96% improvement over baseline
- Extremely stable and predictable behavior
- No drift accumulation over time
- Lower system overhead
- 120 frames per hour

#### Comparison Table

| Metric | Config A (30s/300s) | Config B (20s/420s) |
|--------|----------------------------|---------------------|
| **Timestamp Accuracy (avg)** | ±5 seconds ✅✅✅ | 1 min 30 sec |
| **Timestamp Accuracy (worst)** | ±5 seconds ✅✅✅ | 4 minutes |
| **Drift stability** | Stable (no accumulation) ✅✅ | Accumulates over time |
| **Frames per hour** | 120 frames | 180 frames ✅ |
| **System overhead** | Lower ✅ | Higher |
| **Stability** | Extremely stable ✅✅ | Stable |
| **Reconnection frequency** | Every 5 min | Every 7 min ✅ |

**Recommendation:** Use **Configuration A (30s/300s)** for all applications. Version 2.3.0's multi-threaded capture achieves exceptional ±5 second timestamp accuracy with zero drift accumulation, making it the clear choice for any use case requiring timestamp precision.

**Note:** Other Annke models may have different timeout intervals. Test your camera's behavior and adjust the proactive reconnect interval to ~40 seconds before the observed timeout.

---

## Keyboard Shortcuts

### Capture Tab

| Shortcut | Action                |
|----------|-----------------------|
| `Ctrl+S` | Save configuration    |
| `Ctrl+O` | Load configuration    |
| `Ctrl+T` | Test camera connection|
| `Space`  | Start capture         |
| `Esc`    | Stop capture          |

### Video Export Tab

| Shortcut | Action              |
|----------|---------------------|
| `Ctrl+E` | Focus export tab    |
| `Ctrl+B` | Browse for folder   |
| `Enter`  | Begin export        |
| `Esc`    | Cancel export       |

---

## Testing & Automation

- `tests/test_backend.py` exercises configuration management and capture logic with interactive prompts.
- `tests/test_backend_auto.py` runs the same checks without user input (connection tests will fail harmlessly if no camera is reachable).
- `tests/test_video_export.py` validates the export pipeline; provide a populated `snapshots/YYYYMMDD` folder before running it.

---

## Build & Release

- `build_release.bat` builds a PyInstaller executable and packages a release folder (optionally bundling FFmpeg).
- `bundle_ffmpeg.bat` copies FFmpeg/FFprobe into the release bundle.
- `RTSP_Timelapse.spec` defines the PyInstaller build (GUI-only executable with bundled resources).

---

## Troubleshooting

### Camera Connection Issues

**Cannot connect to camera:**
- Verify camera IP with `ping 192.168.0.101`.
- Test stream URL in VLC: `rtsp://user:pass@ip/stream1`.
- Check port 554 (RTSP) is not blocked by firewall.
- Enable **Force TCP** option if using UDP causes dropouts.

**Connection drops frequently:**
- Enable **Force TCP** for more stable connections.
- Enable **Proactive Reconnect** to reconnect before camera timeout (recommended: 420 seconds for Annke cameras).
- Check network stability between PC and camera.
- Increase capture interval to reduce request frequency.
- Check camera settings for session timeout/keepalive options.
- If drops occur at exact intervals (e.g., every 460 seconds), this is a camera firmware timeout - use proactive reconnect set to ~40 seconds before the timeout.

### Video Export Issues

**FFmpeg not found:**
- Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html).
- Add to system PATH **or** place in `bin/` folder next to executable.
- Ensure all FFmpeg DLL files are present (~150 MB total).
- Click **Test FFmpeg** button to verify installation.

**Export is slow:**
- Lower resolution (720p or 480p instead of original).
- Increase CRF quality value (23-28 for smaller files).
- Use speed multiplier (2×, 4×) to skip frames.
- Close other applications to free system resources.

**Video won't play:**
- Ensure using MP4 format (most compatible).
- Try opening in VLC media player.
- Check FFmpeg log for encoding errors.

### Performance Issues

**GUI is slow or laggy:**
- Disable live preview (uncheck "Enable Preview").
- Lower JPEG quality (70-80 instead of 90).
- Increase capture interval (30s+ instead of 20s).
- Close background applications.

**Disk filling up:**
- Monitor available disk space regularly.
- Lower JPEG quality to reduce file sizes.
- Delete old snapshots after exporting to video.
- Use "Storage Saver" preset for smaller video files.

**Disk Space Calculator:**
```
At quality 90, each 1280×720 frame ≈ 400 KB

Formula: (3600 / interval) × hours × 0.4 MB

Example: 20s interval for 8 hours
  = (3600/20) × 8 × 0.4
  = 576 MB for images
  + ~50 MB for final video
  = ~625 MB total
```

## System Requirements

**Minimum:**
- Windows 10/11 (64-bit) or Linux/macOS
- Python 3.8 or higher
- 4 GB RAM
- 2 GB free disk space
- Network connection to RTSP camera

## Project Structure

```
RTSP/
├── run_gui.py                    # Application launcher
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── .gitignore                    # Git ignore rules
│
├── src/                          # Source code
│   ├── gui_app.py               # Main GUI (tabbed interface)
│   ├── capture_engine.py        # RTSP capture logic
│   ├── config_manager.py        # Configuration management
│   ├── video_export_panel.py    # Video export GUI
│   ├── video_export_controller.py # Video export logic
│   ├── ffmpeg_wrapper.py        # FFmpeg integration
│   ├── preset_manager.py        # Preset management
│   ├── tooltip.py               # Tooltip helper class
│   ├── video_export_tooltips.py # Video export tooltip messages
│   └── capture_tooltips.py      # Capture tab tooltip messages
│
├── tests/                        # Test files
│   ├── test_backend.py          # Interactive backend tests
│   ├── test_backend_auto.py     # Automated tests
│   └── test_video_export.py     # Video export tests
│
├── config/                       # Configuration files
│   └── camera_config_example.json # Template
│
└── snapshots/                    # Captured images (gitignored)
    └── YYYYMMDD/                # Date-organized folders
        └── YYYYMMDD-HHMMSS.jpg  # Timestamped images
```

## Frequently Asked Questions

**Q: Can I use multiple cameras?**
A: Currently supports one camera per instance. Run multiple instances for multiple cameras. Save different configs and load them via **File → Load Configuration**.

**Q: Does it work on Linux/macOS?**
A: Yes! The Python source is cross-platform. Install dependencies and FFmpeg for your OS. Windows releases include pre-built executables.

**Q: Can I run it headless (no GUI)?**
A: Not currently. The legacy CLI version (`src/main.py`) exists but isn't maintained. The GUI is recommended.

**Q: What RTSP URL format do I use?**
A: Depends on your camera brand. See [Camera Settings](#camera-settings) for common paths. Test with VLC first: `rtsp://user:pass@ip/path`.

**Q: My camera requires a specific port. How do I set it?**
A: Include port in IP address field: `192.168.0.101:8554`

**Q: What's the best preset for YouTube?**
A: Use **"Web Optimized"** (30fps, 720p) or **"High Quality 30fps"** (original resolution).

**Q: How do I make a very fast timelapse?**
A: Use **"Ultra Speed 16×"** preset or set Speed Multiplier to 8×/16×/32×.

**Q: Can I add music to the video?**
A: Not built-in. Use video editing software (like DaVinci Resolve, Premiere, or OpenShot) to add audio after export.

**Q: Why are my original files safe?**
A: The export creates temporary numbered copies in a `.temp_export_*/` folder. Your originals are never renamed or modified. The temp folder is automatically deleted after export.

**Q: What is Proactive Reconnect and should I use it?**
A: Proactive Reconnect automatically disconnects and reconnects to the camera at a scheduled interval **before** the camera's firmware timeout occurs. This prevents failed captures during timeout periods. Enable it if you notice connection drops at regular intervals (e.g., every 5-10 minutes). Set the value to ~40 seconds before your camera's timeout. For Annke I81EM cameras, use 420 seconds (7 minutes).

**Q: How do I know what reconnect interval to use?**
A: Monitor your logs for "Connection lost" messages. If they occur at regular intervals (e.g., exactly every 460 seconds), that's your camera's timeout. Set Proactive Reconnect to that value minus 40 seconds. Example: 460s timeout → use 420s reconnect interval.

**Q: Why are my snapshot timestamps off by 30 seconds?**
A: This is normal! The timestamp in the filename is when the capture was initiated. The timestamp embedded by the camera in the image is when the frame was encoded. With optimal settings (10 FPS, I-frame 4), this difference should be 5-33 seconds with Configuration A (30s/300s) or 33s-4min with Configuration B (20s/420s). This is acceptable for timelapse purposes.

**Q: Should I use 20-second or 30-second capture intervals?**
A: For most users, **30-second intervals with 300-second proactive reconnect (Configuration A)** is recommended. This provides 4x better timestamp accuracy (25s avg vs 1m30s avg) and lower system overhead. Use 20-second intervals (Configuration B) only if you need maximum frame density for fast-changing scenes. Both achieve 100% capture success rate. See the [Optimal Settings](#optimal-settings-for-annke-i81em-cameras) section for detailed comparison.

**Q: What does timestamp accuracy mean for my timelapse video?**
A: Timestamp accuracy refers to the difference between when you requested the frame (filename) and when the camera actually encoded it. For timelapse videos played back at 24-30 fps, even a 1-2 minute difference is imperceptible. However, if you need accurate timestamps for scientific analysis or precise time correlation, use Configuration A (30s/300s) for 8-33 second accuracy.

**Q: How do I learn what each setting does?**
A: Simply hover your mouse over any control (button, input field, checkbox, etc.) and wait ~500ms. A helpful tooltip will appear explaining what it does, expected values, and recommendations. The app has 37 tooltips covering every important control.

**Q: Can I disable tooltips?**
A: Tooltips are built into the interface and cannot be disabled. However, they only appear when you hover for 500ms, so they won't interfere with normal usage. They disappear instantly when you move your mouse away.

---

## Version History

### v2.3.0 (2025-10-20) - Latest
**Major Release: Multi-Threaded Bufferless Capture**
- **Revolutionary timestamp accuracy**: ±5 seconds throughout entire capture session (96% improvement over baseline)
- **Multi-threaded capture engine**: Background thread continuously reads frames, discards stale ones
- **Zero drift accumulation**: Maintains stable ±5s accuracy across multiple reconnection cycles
- **FFmpeg low-latency flags**: Optimized RTSP streaming with minimal buffering
- **Production-ready**: Tested and validated over 26-minute session with 50 frames and 4 reconnection cycles

**Technical Improvements:**
- Implemented `RTSPBufferlessCapture` class with queue-based architecture (maxsize=1)
- Queue automatically discards old frames, keeps only latest
- Compatible API with cv2.VideoCapture for seamless integration
- Logs show "Multi-threaded bufferless mode" for verification

**Performance Results:**
- Initial capture: +19s (vs baseline +35s, 46% better)
- Steady-state: ±5s (vs baseline -4m 50s, 96% better)
- Drift behavior: Stable (vs accumulating over time)
- Success rate: 100% maintained

### v2.2.0 (2025-01-19)
**New Features:**
- **Comprehensive Tooltip System**: 37 hover tooltips across both tabs providing contextual help for all controls
  - 19 tooltips for Video Export tab
  - 18 tooltips for Capture tab
  - Smart positioning with 500ms delay
  - Helpful explanations with examples and recommendations
- **Output Path Memory**: Video export now remembers your last export location
- Full path display in output file field (no more confusion!)

**Improvements:**
- Enhanced user experience with self-documenting interface
- Reduced learning curve for new users
- Professional tooltip styling with light yellow popups
- Dynamic tooltips (e.g., Start/Stop button changes tooltip text)

### v2.1.0 (2025-10-19)
**New Features:**
- **Proactive Reconnection**: Automatically reconnect before camera firmware timeouts to achieve 100% capture success rate
- Added "Proactive Reconnect (s)" configuration field in GUI
- Optimized buffer settings (default changed from 4 to 2 frames)
- Two recommended configurations for Annke I81EM cameras (timestamp accuracy vs frame density)

**Improvements:**
- Reduced buffer_frames default to 2 for fresher frame captures
- Added flush_buffer_count parameter (internal, for advanced users)
- Enhanced reconnection logging with uptime tracking
- **Dramatically improved timestamp accuracy**: 8-33 seconds (avg 25s) with 30s/300s configuration vs 33s-4min with 20s/420s
- Comprehensive testing and documentation of optimal camera settings
- Added configuration comparison table and selection guidance

### v2.0.1 (2025-10-17)
**Bug Fixes:**
- Fixed PyInstaller executable build issues
- Bundled all FFmpeg DLLs (~150 MB) for video export
- Fixed Tkinter DLL dependencies for Windows
- Increased FFmpeg subprocess timeout to prevent false failures
- Video export now works properly in standalone executable

### v2.0.0 (2025-10-15)
**Major Release: Video Export Feature**
- Complete video export functionality
- 6 built-in presets + custom preset management
- Tabbed interface (Capture | Video Export)
- FFmpeg integration with real-time progress
- Non-destructive workflow with temp copies
- Duration and file size estimation
- Enhanced GUI with better error handling

### v1.0.0 (2025-10-14)
**Initial Release:**
- RTSP camera capture with live preview
- Overnight scheduling support
- Session statistics and monitoring
- Configuration management with JSON
- Thread-safe architecture
- Keyboard shortcuts

---

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Commit: `git commit -m "Add amazing feature"`
5. Push: `git push origin feature/amazing-feature`
6. Open a Pull Request

---

## Support & Contact

- **Documentation:** Check this README and `docs/` folder [TODO]
- **Bug Reports:** [Open an issue](https://github.com/HiranD/RTSP-Timelapse-Capture/issues)
- **Feature Requests:** [Open an issue](https://github.com/HiranD/RTSP-Timelapse-Capture/issues)
- **Discussions:** [GitHub Discussions](https://github.com/HiranD/RTSP-Timelapse-Capture/discussions)

**Useful Resources:**
- [FFmpeg Download](https://ffmpeg.org/download.html)
- [RTSP Protocol Info](https://en.wikipedia.org/wiki/Real_Time_Streaming_Protocol)
- [OpenCV Documentation](https://docs.opencv.org/)

---

## Acknowledgments

- **OpenCV** - RTSP streaming and image processing
- **FFmpeg** - Professional video encoding
- **Tkinter** - Python GUI framework
- **PIL/Pillow** - Image manipulation
- **PyInstaller** - Executable packaging
- **Python Community** - Amazing ecosystem and support

---

## License

Released under the MIT License. See `version_info.txt` for Windows executable metadata.
