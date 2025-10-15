#!/usr/bin/env python3
"""
RTSP Timelapse Capture System - Launcher Script

This script launches the GUI application from the root directory.
"""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import and run the GUI
from gui_app import main

if __name__ == "__main__":
    main()
