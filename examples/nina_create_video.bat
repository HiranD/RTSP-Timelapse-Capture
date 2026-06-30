@echo off
REM Create the timelapse video for the most recent capture session via the
REM Remote Control API (honours your Video Export preset + Discord settings).
REM Run this after nina_stop.bat, e.g. at the very end of a NINA sequence.
REM
REM To target a specific night instead of the newest, pass a date (YYYYMMDD):
REM   curl -s -S -f -X POST -H "Content-Type: application/json" ^
REM        -d "{\"date\":\"20250620\"}" http://127.0.0.1:8787/video/create
curl -s -S -f -X POST http://127.0.0.1:8787/video/create
