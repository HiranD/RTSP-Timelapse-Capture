# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\gui_app.py'],
    pathex=['src'],
    binaries=[],
    datas=[('assets/icon.ico', 'assets')],
    hiddenimports=[
        'config_manager',
        'capture_engine',
        'video_export_panel',
        'video_export_controller',
        'scheduling_panel',
        'integrations_panel',
        'calendar_widget',
        'twilight_calculator',
        'astro_scheduler',
        'preset_manager',
        'ffmpeg_wrapper',
        'tooltip',
        'capture_tooltips',
        'scheduling_tooltips',
        'remote_api',
        # pystray is loaded via importlib.import_module() (dynamic), which
        # PyInstaller's static analysis can't see. hook-pystray then bundles
        # the platform backend (pystray._win32 on Windows).
        'pystray',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RTSP_Timelapse',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
    version='version_info.txt',
)
