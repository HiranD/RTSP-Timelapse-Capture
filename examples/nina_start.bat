@echo off
REM Start RTSP Timelapse capture via the local Remote Control API.
REM Use this in NINA's "External Script" instruction at the start of a sequence.
REM Edit the port below if you changed it on the Integrations tab.
curl -s -S -f -X POST http://127.0.0.1:8787/capture/start
