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
if exist "release\RTSP_Timelapse_v2.0.0_Windows" rmdir /s /q "release\RTSP_Timelapse_v2.0.0_Windows"
mkdir "release\RTSP_Timelapse_v2.0.0_Windows"

REM Copy files to release folder
copy "dist\RTSP_Timelapse.exe" "release\RTSP_Timelapse_v2.0.0_Windows\"
copy "README.md" "release\RTSP_Timelapse_v2.0.0_Windows\"
copy "requirements.txt" "release\RTSP_Timelapse_v2.0.0_Windows\"

REM Bundle FFmpeg (no separate install needed!)
echo Bundling FFmpeg...
if not exist "release\RTSP_Timelapse_v2.0.0_Windows\bin" mkdir "release\RTSP_Timelapse_v2.0.0_Windows\bin"
copy "C:\Users\wande\Tools\ffmpeg-shared\bin\ffmpeg.exe" "release\RTSP_Timelapse_v2.0.0_Windows\bin\" >nul 2>&1
copy "C:\Users\wande\Tools\ffmpeg-shared\bin\ffprobe.exe" "release\RTSP_Timelapse_v2.0.0_Windows\bin\" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   - FFmpeg bundled successfully! Users don't need to install it.
) else (
    echo   - Warning: FFmpeg not found, users will need to install it separately
)

REM Create user guide
echo [5/5] Creating user guide...
(
echo RTSP Timelapse Capture System v2.0.0
echo =====================================
echo.
echo QUICK START:
echo 1. Run RTSP_Timelapse.exe
echo 2. Configure your camera settings in the Capture tab
echo 3. Click "Start Capture" to begin capturing images
echo 4. Switch to "Video Export" tab to create videos
echo.
echo FEATURES:
echo - RTSP camera capture with live preview
echo - Overnight scheduling support
echo - Video export with 6 built-in presets
echo - FFmpeg is included - no separate installation needed!
echo.
echo DOCUMENTATION:
echo - See README.md for full documentation
echo - GitHub: https://github.com/yourusername/rtsp-timelapse
echo.
echo SUPPORT:
echo - Report issues on GitHub
echo - Check docs/ folder for guides
echo.
echo LICENSE: MIT
) > "release\RTSP_Timelapse_v2.0.0_Windows\QUICKSTART.txt"

REM Create ZIP archive
echo Creating ZIP archive...
cd release
powershell Compress-Archive -Path "RTSP_Timelapse_v2.0.0_Windows" -DestinationPath "RTSP_Timelapse_v2.0.0_Windows.zip" -Force
cd ..

echo.
echo ========================================
echo Build Complete!
echo ========================================
echo.
echo Executable: dist\RTSP_Timelapse.exe
echo Release Package: release\RTSP_Timelapse_v2.0.0_Windows\
echo ZIP Archive: release\RTSP_Timelapse_v2.0.0_Windows.zip
echo.
echo Ready for GitHub release!
echo.
pause
