@echo off
REM Build script for RTSP Timelapse Capture System
REM Creates Windows executable using PyInstaller

REM === Release version (update this one line per release) ===
set "VERSION=3.6.0"

echo ========================================
echo RTSP Timelapse - Windows Release Build v%VERSION%
echo ========================================
echo.

REM Activate virtual environment
echo [1/5] Activating virtual environment...
call .venv\Scripts\activate.bat

REM Ensure the base Python's Library\bin is on PATH so PyInstaller can find and
REM bundle the Tcl/Tk DLLs (tcl86t.dll / tk86t.dll) that _tkinter.pyd depends
REM on. uv-created venvs don't add it, which intermittently produced exes that
REM failed at launch with "DLL load failed while importing _tkinter".
for /f "delims=" %%i in ('python -c "import sys;print(sys.base_prefix)"') do set "PYBASE=%%i"
set "PATH=%PYBASE%\Library\bin;%PATH%"
echo       Base Python: %PYBASE%

REM Clean previous builds
echo [2/5] Cleaning previous builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM Build executable
echo [3/5] Building executable with PyInstaller...
pyinstaller --clean RTSP_Timelapse.spec

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

REM Create release folder
echo [4/5] Creating release package...
if not exist "release" mkdir "release"
if exist "release\RTSP_Timelapse_v%VERSION%_Windows" rmdir /s /q "release\RTSP_Timelapse_v%VERSION%_Windows"
mkdir "release\RTSP_Timelapse_v%VERSION%_Windows"

REM Copy files to release folder
copy "dist\RTSP_Timelapse.exe" "release\RTSP_Timelapse_v%VERSION%_Windows\"
copy "README.md" "release\RTSP_Timelapse_v%VERSION%_Windows\"

REM Bundle the Remote Control / NINA example scripts
echo Bundling example scripts...
if not exist "release\RTSP_Timelapse_v%VERSION%_Windows\examples" mkdir "release\RTSP_Timelapse_v%VERSION%_Windows\examples"
copy "examples\*" "release\RTSP_Timelapse_v%VERSION%_Windows\examples\" >nul

REM Bundle FFmpeg with all DLLs (no separate install needed!)
echo Bundling FFmpeg...
if not exist "release\RTSP_Timelapse_v%VERSION%_Windows\bin" mkdir "release\RTSP_Timelapse_v%VERSION%_Windows\bin"
copy "C:\Users\wande\Tools\ffmpeg-shared\bin\*" "release\RTSP_Timelapse_v%VERSION%_Windows\bin\" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   - FFmpeg bundled successfully with all DLLs ^(~150 MB^)
    echo   - Users don't need to install anything!
) else (
    echo   - Warning: FFmpeg not found, users will need to install it separately
)

REM Create user guide
echo [5/5] Creating user guide...
(
echo ================================================================================
echo    RTSP Timelapse Capture System v%VERSION%
echo    Session Events + MQTT Delivery
echo ================================================================================
echo.
echo WHAT'S NEW IN v%VERSION%:
echo   * NEW: Session events. External programs - like the RTSP Timelapse
echo     Control NINA plugin 1.5.0 - can tell the app what happened during
echo     the night ^(autofocus, filter changes, meridian flip, target,
echo     guiding^) via POST /events, and the app burns them into the video
echo     as captions at the moment they occurred. The imaging target is
echo     drawn as a standing label in the bottom-right corner. An optional
echo     .events.csv can be written next to the video ^(Video Export tab^).
echo   * NEW: MQTT delivery. The Integrations tab's Discord Upload section
echo     is now Video Delivery - send each finished video to a Discord
echo     webhook ^(as before^) or publish it to an MQTT broker, so a capture
echo     PC with no internet can hand the video to a local broker.
echo   * NEW: Folder Rollover Hour is editable on the Capture tab.
echo   * IMPROVED: renders are session-aware - a night that crosses the
echo     rollover hour renders whole across date folders, and the nightly
echo     auto-video renders exactly the session. "Delete snapshots after
echo     creating video" moved to the Video Export tab, applies to every
echo     video, and deletes only the frames that went into the video.
echo   * IMPROVED: a camera outage no longer ends the session - capture
echo     keeps retrying with escalating backoff ^(orange "Reconnecting"
echo     status^) until capture is stopped or the window ends.
echo   * FIXED: starting the scheduler mid-window ^(or after midnight^) now
echo     captures instead of instantly completing; scheduled end times can
echo     never land in the past.
echo   * FIXED: every render names its video timelapse-YYYY-MM-DD, and a
echo     delivered video keeps that name ^(no more discord_crf32.mp4^).
echo   * FIXED: a UTF-8 BOM in app_config.json ^(e.g. after editing it in
echo     Notepad^) no longer silently resets every setting; Integrations
echo     fields typed just before closing the app are no longer lost.
echo.
echo ================================================================================
echo QUICK START GUIDE
echo ================================================================================
echo.
echo 1. LAUNCH APPLICATION
echo    ^> Double-click RTSP_Timelapse.exe
echo    ^> No installation needed - everything is bundled!
echo.
echo UPGRADING FROM A PREVIOUS VERSION
echo    ^> Easiest - in your existing app folder, replace the old
echo      RTSP_Timelapse.exe with this one and restart. Your settings
echo      in config\app_config.json and history in user_data\ are kept.
echo    ^> Fresh copy - extract this ZIP to a new folder, then copy your
echo      old config\ and user_data\ folders next to the new exe.
echo    ^> Old settings carry over automatically; new options use
echo      sensible defaults - nothing is lost.
echo.
echo 2. CONFIGURE CAMERA ^(Capture Tab^)
echo    ^> Enter camera IP address ^(e.g., 192.168.0.101^)
echo    ^> Enter username and password
echo    ^> Set stream path - must match your camera brand
echo      ^(Hikvision /Streaming/Channels/101, Dahua
echo       /cam/realmonitor?channel=1^&subtype=0, UniFi /s0,
echo       generic /stream1^) - blank falls back to /stream1
echo    ^> Click "Test Connection" to verify
echo.
echo 3. SET SCHEDULE
echo    ^> Start Time: When to begin capturing ^(e.g., 20:00^)
echo    ^> End Time: When to stop ^(e.g., 08:00^)
echo    ^> Interval: Seconds between captures ^(e.g., 30^)
echo    ^> Proactive Reconnect: 300s ^(prevents camera timeouts^)
echo    ^> Settings auto-save when you switch tabs!
echo.
echo 4. START CAPTURING
echo    ^> Click "Start Capture" or press Space
echo    ^> Watch live preview and session statistics
echo    ^> Images saved to snapshots/YYYYMMDD/ folder
echo    ^> Press Esc to stop capture
echo.
echo 5. CREATE VIDEO ^(Video Export Tab^)
echo    ^> Click "Quick Select" to choose date folder
echo    ^> Select preset ^(Standard 24fps, High Quality, etc.^)
echo    ^> Click "Create Video" and wait for encoding
echo    ^> Video opens automatically when complete
echo.
echo 6. AUTOMATED SCHEDULING ^(Scheduling Tab - NEW!^)
echo    ^> Choose time mode: Twilight-based or Manual
echo    ^> For Twilight: Enter lat/long, select twilight type
echo    ^> For Manual: Set fixed start/end times ^(e.g., 20:00 - 08:00^)
echo    ^> Click dates on calendar to schedule captures
echo    ^> Enable "Create video after each night" for auto export
echo    ^> Check "Enable automatic scheduling" to start!
echo.
echo    IMPORTANT - For scheduler to work properly:
echo    -----------------------------------------------
echo    1. CAPTURE TAB ^(Required^):
echo       - Camera must be configured and "Test Connection" must pass
echo       - Output folder must be set
echo       - Capture interval must be set
echo.
echo    2. VIDEO EXPORT TAB ^(Required if auto video enabled^):
echo       - Select a video preset
echo       - Set output folder for videos
echo.
echo    3. SCHEDULING TAB:
echo       - Set location ^(twilight mode^) OR start/end times ^(manual mode^)
echo       - Select at least one date on calendar
echo       - Check "Enable automatic scheduling"
echo.
echo 7. REMOTE CONTROL / NINA ^(NEW in v3.4^)
echo    ^> Control capture from external scripts ^(e.g. NINA^) via a local HTTP API.
echo    ^> Enable it on the Integrations tab, then see examples\README.md for setup.
echo.
echo ================================================================================
echo KEY FEATURES
echo ================================================================================
echo.
echo CAPTURE ENGINE:
echo   * Multi-threaded bufferless RTSP capture
echo   * ±5 second timestamp accuracy ^(stable throughout session^)
echo   * Proactive reconnection ^(100%% success rate^)
echo   * Smart overnight scheduling support
echo   * Adjustable intervals ^(1-3600 seconds^)
echo   * Live preview with quality control
echo   * Comprehensive tooltips ^(hover for help^)
echo.
echo VIDEO EXPORT:
echo   * 6 built-in presets + custom presets
echo   * Frame rates: 1-120 fps
echo   * Quality control: CRF 0-51
echo   * Speed multipliers: 1x-32x
echo   * Resolution scaling: 4K to 360p
echo   * FFmpeg included ^(no separate install^)
echo.
echo ================================================================================
echo RECOMMENDED SETTINGS ^(For Annke I81EM Cameras^)
echo ================================================================================
echo.
echo CAMERA WEB INTERFACE:
echo   * Frame Rate: 10 FPS
echo   * I Frame Interval: 4
echo   * Max Bitrate: 3072 Kbps or lower
echo.
echo APPLICATION SETTINGS:
echo   * Capture Interval: 30 seconds
echo   * Buffer Frames: 1
echo   * Proactive Reconnect: 300 seconds ^(5 minutes^)
echo.
echo RESULTS:
echo   * 100%% capture success rate
echo   * ±5 second timestamp accuracy
echo   * No drift accumulation
echo   * 120 frames per hour
echo.
echo ================================================================================
echo TIPS ^& TRICKS
echo ================================================================================
echo.
echo * HOVER FOR HELP: All controls have tooltips - just hover your mouse!
echo * TEST FIRST: Always click "Test Connection" before starting capture
echo * TCP MODE: All connections use TCP transport - nothing to configure
echo * DISK SPACE: At 30s interval, expect ~400KB per image ^(~1.4MB/min^)
echo * VIDEO PRESETS: Try "Standard 24fps" first, then experiment
echo * KEYBOARD SHORTCUTS: Space=Start, Esc=Stop, Ctrl+T=Test Connection
echo * AUTO-SAVE: Config saves automatically when switching tabs or closing app
echo.
echo ================================================================================
echo TROUBLESHOOTING
echo ================================================================================
echo.
echo CAMERA WON'T CONNECT:
echo   * Verify IP address with ping command
echo   * Test RTSP URL in VLC: rtsp://user:pass@ip/path
echo   * Check firewall isn't blocking port 554
echo   * If VLC works, copy its path into "Stream Path" verbatim -
echo     the Activity Log prints the exact URL the app dials
echo.
echo FFMPEG NOT FOUND:
echo   * FFmpeg is in bin/ folder next to the executable
echo   * Click "Test FFmpeg" button in Video Export tab
echo   * If missing, download from ffmpeg.org
echo.
echo CONNECTION DROPS:
echo   * Enable "Proactive Reconnect" ^(300-420 seconds^)
echo   * Check network stability
echo   * Reduce capture interval if needed
echo.
echo ================================================================================
echo DOCUMENTATION ^& SUPPORT
echo ================================================================================
echo.
echo FULL DOCUMENTATION:
echo   * README.md ^(complete user guide^)
echo   * GitHub: https://github.com/HiranD/RTSP-Timelapse-Capture
echo.
echo GET HELP:
echo   * Bug Reports: github.com/HiranD/RTSP-Timelapse-Capture/issues
echo   * Discussions: github.com/HiranD/RTSP-Timelapse-Capture/discussions
echo.
echo ================================================================================
echo LICENSE: MIT - Free to use, modify, and distribute
echo ================================================================================
echo.
echo Thank you for using RTSP Timelapse Capture System!
echo For the best timestamp accuracy, use the recommended settings above.
echo.
) > "release\RTSP_Timelapse_v%VERSION%_Windows\QUICKSTART.txt"

REM Copy release notes
echo Copying release notes...
copy "release\RELEASE_NOTES_v%VERSION%.md" "release\RTSP_Timelapse_v%VERSION%_Windows\"

REM Create ZIP archive
echo Creating ZIP archive...
cd release
powershell Compress-Archive -Path "RTSP_Timelapse_v%VERSION%_Windows" -DestinationPath "RTSP_Timelapse_v%VERSION%_Windows.zip" -Force
cd ..

echo.
echo ========================================
echo Build Complete!
echo ========================================
echo.
echo Executable: dist\RTSP_Timelapse.exe
echo Release Package: release\RTSP_Timelapse_v%VERSION%_Windows\
echo ZIP Archive: release\RTSP_Timelapse_v%VERSION%_Windows.zip
echo.
echo Ready for GitHub release!
echo.
pause
