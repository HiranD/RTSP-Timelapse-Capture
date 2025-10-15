# RTSP Timelapse Capture System v2.0.0

## 🎉 Major Release: Video Export Feature

**Release Date:** October 15, 2025
**Platform:** Windows 10/11 (64-bit)

---

## 🎬 What's New

### Video Export Feature ✨

Transform your captured images into professional timelapse videos with one click!

**Key Features:**
- 🎥 **One-Click Export** - Convert images to video instantly
- 🎛️ **6 Built-in Presets** - Professional settings ready to use
- ⚙️ **Full Customization** - Frame rate, quality, resolution, speed
- 🔒 **Non-Destructive** - Original images never modified
- 📈 **Real-Time Progress** - Watch encoding progress live
- 💾 **Smart Estimates** - Duration and file size predictions

**Built-in Presets:**
1. **Standard 24fps** - General purpose timelapses
2. **High Quality 30fps** - Best quality output
3. **Fast Motion 60fps** - Smooth 4x speed motion
4. **Web Optimized** - 720p for YouTube/social media
5. **Storage Saver** - 480p small file sizes
6. **Ultra Speed 16x** - Very fast timelapses

### New Tabbed Interface

- **Capture Tab** - Original image capture functionality
- **Video Export Tab** - New video creation workflow
- Clean separation of capture and export workflows

---

## 📋 What's Included

### Windows Executable Package

**Download:** `RTSP_Timelapse_v2.0.0_Windows.zip` (see Assets below)

**Package Contents:**
```
RTSP_Timelapse_v2.0.0_Windows/
├── RTSP_Timelapse.exe    # Main application (no Python required!)
├── bin/
│   ├── ffmpeg.exe        # Video encoding (bundled!)
│   └── ffprobe.exe       # Video info tool
├── README.md              # Full documentation
├── QUICKSTART.txt         # Quick start guide
└── requirements.txt       # For source installation
```

**File Size:** 59 MB (includes all dependencies + FFmpeg!)

---

## 🚀 Installation & Usage

### Quick Start

1. **Download the ZIP file** from Assets below
2. **Extract** to your desired location
3. **Run** `RTSP_Timelapse.exe`

**That's it!** FFmpeg is bundled - no separate installation needed!

### First Use

**Capture Tab:**
1. Enter your camera IP, username, and password
2. Set stream path (e.g., `/stream1`)
3. Configure schedule and interval
4. Click "Start Capture"

**Video Export Tab:**
1. Click "Quick Select" to choose captured images
2. Select a preset or customize settings
3. Click "Create Video"
4. Video opens automatically when done!

---

## ✨ Features

### Image Capture
- 📷 RTSP stream capture from any compatible camera
- ⏰ Smart scheduling with overnight support
- 🔄 Auto-interval capture (1-3600 seconds)
- 📁 Date-based folder organization
- 👁️ Live preview with auto-scaling
- 📊 Session statistics and monitoring

### Video Export (NEW!)
- 🎥 FFmpeg integration for professional encoding
- 🎛️ 6 built-in presets + custom presets
- ⚙️ Frame rate: 1-120 fps
- 🎨 Quality control: CRF 0-51
- ⚡ Speed multiplier: 1x-32x
- 📐 Resolution options: Original to 4K
- 📦 Format support: MP4, AVI, MKV, WebM

### User Experience
- 🖥️ Clean tabbed interface
- ⌨️ Keyboard shortcuts
- 💾 Auto-save settings
- 🔄 Thread-safe, never freezes
- 📝 Color-coded activity logs

---

## 📊 Technical Details

**System Requirements:**
- Windows 10/11 (64-bit)
- 4 GB RAM minimum
- RTSP-compatible camera
- Network connection to camera

**No additional software needed** - FFmpeg is bundled!

**Technologies:**
- Python 3.8+ (bundled in executable)
- OpenCV for RTSP streaming
- FFmpeg for video encoding
- Tkinter GUI framework
- PIL/Pillow for image processing

**Performance:**
- Capture: Minimal CPU usage between captures
- Export: Varies by settings (5-30 fps encoding speed)
- Memory: ~200-300 MB during operation

---

## 🐛 Known Issues

1. **Antivirus False Positives** - Some antivirus may flag the executable
   - Solution: This is normal for PyInstaller executables, add exception

2. **First Launch Slow** - Executable may take 10-20 seconds on first run
   - Solution: Normal behavior, subsequent launches are faster

---

## 🔄 Upgrade Notes

### From v1.0.0

- All existing configurations are compatible
- No breaking changes to capture functionality
- New video export tab added (optional to use)
- Update to continue using capture, explore export at your pace

### Configuration Migration

Your existing `camera_config.json` will work without changes. The new video export feature uses separate settings that don't affect capture.

---

## 📖 Documentation

- **README.md** - Complete documentation
- **GitHub Wiki** - Tutorials and guides
- **FAQ** - Common questions answered
- **docs/** folder - Technical documentation

**Key Documentation:**
- [Installation Guide](README.md#installation)
- [Usage Guide](README.md#usage-guide)
- [Video Export Guide](README.md#creating-videos)
- [Troubleshooting](README.md#troubleshooting)
- [FAQ](README.md#faq)

---

## 🤝 Contributing

This is an open-source project under MIT license. Contributions welcome!

**Ways to Contribute:**
- Report bugs and issues
- Request features
- Submit pull requests
- Improve documentation
- Share your timelapse videos!

**GitHub:** https://github.com/yourusername/rtsp-timelapse

---

## 📸 Use Cases

### Real-World Examples

**Astronomy Photography**
- Capture: 22:00-06:00, 30s intervals
- Export: Ultra Speed 16x preset
- Result: 8-hour night → 90 seconds

**Construction Progress**
- Capture: 08:00-17:00, 60s intervals
- Export: Standard 24fps preset
- Result: 9-hour day → 2 minutes

**Weather Monitoring**
- Capture: All day, 10s intervals
- Export: Fast Motion 60fps preset
- Result: 24 hours → 3 minutes

---

## 🙏 Acknowledgments

- **FFmpeg** - Industry-standard video encoding
- **OpenCV** - Powerful RTSP streaming
- **Python Community** - Amazing ecosystem
- **Claude AI** - Development assistance
- **Open Source Community** - Inspiration and support

---

## 📝 Changelog

### v2.0.0 (October 15, 2025) - CURRENT

**Major Features:**
- ✅ Complete video export functionality
- ✅ 6 built-in presets
- ✅ Custom preset management
- ✅ Tabbed interface (Capture | Video Export)
- ✅ FFmpeg integration
- ✅ Real-time progress tracking
- ✅ Non-destructive workflow
- ✅ Duration and file size estimation

**Improvements:**
- ✅ Enhanced GUI with tabs
- ✅ Better error handling
- ✅ Comprehensive documentation
- ✅ Windows executable release

**Statistics:**
- 4 new modules (2,060 lines)
- 1 test suite (257 lines)
- Updated documentation (800+ lines)
- 8 logical commits

### v1.0.0 (October 14, 2025)

**Initial Release:**
- ✅ RTSP camera capture
- ✅ Live preview
- ✅ Overnight scheduling
- ✅ Session statistics
- ✅ Configuration management

---

## 📞 Support

### Get Help

- 📖 **Documentation:** Check README.md and docs/
- 🐛 **Bug Reports:** [Open an issue](https://github.com/yourusername/rtsp-timelapse/issues)
- 💡 **Feature Requests:** [Open an issue](https://github.com/yourusername/rtsp-timelapse/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/yourusername/rtsp-timelapse/discussions)

### Useful Links

- [FFmpeg Download](https://ffmpeg.org/download.html)
- [Project Homepage](https://github.com/yourusername/rtsp-timelapse)
- [Video Tutorials](https://github.com/yourusername/rtsp-timelapse/wiki)

---

## 📄 License

MIT License - Free to use, modify, and distribute.

See [LICENSE](LICENSE) file for full details.

---

## ⭐ Star Us!

If you find this project useful, please give it a star on GitHub!

---

<div align="center">

**Made with ❤️ for timelapse photography**

**[Download Latest Release](https://github.com/yourusername/rtsp-timelapse/releases/latest)** |
**[View Source Code](https://github.com/yourusername/rtsp-timelapse)** |
**[Report Issue](https://github.com/yourusername/rtsp-timelapse/issues)**

</div>
