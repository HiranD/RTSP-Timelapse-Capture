@echo off
REM Bundle FFmpeg with the release package

echo ========================================
echo Bundling FFmpeg with Release
echo ========================================
echo.

REM Create bin directory in release folder
if not exist "release\RTSP_Timelapse_v2.0.0_Windows\bin" mkdir "release\RTSP_Timelapse_v2.0.0_Windows\bin"

REM Copy FFmpeg executables
echo Copying FFmpeg binaries...
copy "C:\Users\wande\Tools\ffmpeg-shared\bin\ffmpeg.exe" "release\RTSP_Timelapse_v2.0.0_Windows\bin\"
copy "C:\Users\wande\Tools\ffmpeg-shared\bin\ffprobe.exe" "release\RTSP_Timelapse_v2.0.0_Windows\bin\"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to copy FFmpeg files!
    echo Please ensure FFmpeg is installed at: C:\Users\wande\Tools\ffmpeg-shared\bin\
    pause
    exit /b 1
)

echo.
echo [SUCCESS] FFmpeg bundled successfully!
echo Location: release\RTSP_Timelapse_v2.0.0_Windows\bin\
echo   - ffmpeg.exe
echo   - ffprobe.exe
echo.
echo Users will no longer need to install FFmpeg separately!
echo.
pause
