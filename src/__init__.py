"""
RTSP Timelapse Capture System

A professional GUI application for capturing timelapse images from RTSP camera streams.
"""

__version__ = "1.0.0"
__author__ = "RTSP Timelapse Team"

from .capture_engine import CaptureEngine, CaptureState
from .config_manager import ConfigManager

__all__ = ['CaptureEngine', 'CaptureState', 'ConfigManager']
