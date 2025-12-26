@echo off
REM Build script for RTSP Timelapse Capture System
REM Creates Windows executable using PyInstaller

echo ========================================
echo RTSP Timelapse - Windows Release Build
echo ========================================
echo.

REM Activate virtual environment
echo [1/5] Activating virtual environment...
call .venv\Scripts\activate.bat

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
if exist "release\RTSP_Timelapse_v3.0.0_Windows" rmdir /s /q "release\RTSP_Timelapse_v3.0.0_Windows"
mkdir "release\RTSP_Timelapse_v3.0.0_Windows"

REM Copy files to release folder
copy "dist\RTSP_Timelapse.exe" "release\RTSP_Timelapse_v3.0.0_Windows\"
copy "README.md" "release\RTSP_Timelapse_v3.0.0_Windows\"

REM Bundle FFmpeg with all DLLs (no separate install needed!)
echo Bundling FFmpeg...
if not exist "release\RTSP_Timelapse_v3.0.0_Windows\bin" mkdir "release\RTSP_Timelapse_v3.0.0_Windows\bin"
copy "C:\Users\wande\Tools\ffmpeg-shared\bin\*" "release\RTSP_Timelapse_v3.0.0_Windows\bin\" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   - FFmpeg bundled successfully with all DLLs (~150 MB)
    echo   - Users don't need to install anything!
) else (
    echo   - Warning: FFmpeg not found, users will need to install it separately
)

REM Create user guide
echo [5/5] Creating user guide...
(
echo ================================================================================
echo    RTSP Timelapse Capture System v3.0.0
echo    Astronomical Scheduling - Automated Long-Term Capture Planning
echo ================================================================================
echo.
echo WHAT'S NEW IN v3.0.0:
echo   * NEW Scheduling Tab for automated multi-night captures
echo   * Twilight-based scheduling ^(civil/nautical/astronomical^)
echo   * Manual time mode as alternative to twilight calculations
echo   * Two-month calendar with capture history indicators
echo   * Auto video creation after each night's session
echo   * Capture history tracking ^(shows past captures on calendar^)
echo   * Last selected preset remembered across sessions
echo   * Auto-save config on tab switch and app close ^(no manual save needed^)
echo.
echo ================================================================================
echo QUICK START GUIDE
echo ================================================================================
echo.
echo 1. LAUNCH APPLICATION
echo    ^> Double-click RTSP_Timelapse.exe
echo    ^> No installation needed - everything is bundled!
echo.
echo 2. CONFIGURE CAMERA ^(Capture Tab^)
echo    ^> Enter camera IP address ^(e.g., 192.168.0.101^)
echo    ^> Enter username and password
echo    ^> Set stream path ^(e.g., /stream1, /h264^)
echo    ^> Enable "Force TCP" for stability
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
echo   * Force TCP: Enabled
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
echo * TCP MODE: Keep "Force TCP" enabled for most IP cameras
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
echo   * Enable "Force TCP" option
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
) > "release\RTSP_Timelapse_v3.0.0_Windows\QUICKSTART.txt"

REM Copy release notes
echo Copying release notes...
copy "release\RELEASE_NOTES_v3.0.0.md" "release\RTSP_Timelapse_v3.0.0_Windows\"

REM Create ZIP archive
echo Creating ZIP archive...
cd release
powershell Compress-Archive -Path "RTSP_Timelapse_v3.0.0_Windows" -DestinationPath "RTSP_Timelapse_v3.0.0_Windows.zip" -Force
cd ..

echo.
echo ========================================
echo Build Complete!
echo ========================================
echo.
echo Executable: dist\RTSP_Timelapse.exe
echo Release Package: release\RTSP_Timelapse_v3.0.0_Windows\
echo ZIP Archive: release\RTSP_Timelapse_v3.0.0_Windows.zip
echo.
echo Ready for GitHub release!
echo.
pause
