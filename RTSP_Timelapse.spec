# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['run_gui.py'],
    pathex=['src'],
    binaries=[
        ('C:/Users/wande/miniconda3/Library/bin/tcl86t.dll', '.'),
        ('C:/Users/wande/miniconda3/Library/bin/tk86t.dll', '.'),
    ],
    datas=[
        ('src', 'src'),
        ('config', 'config'),
        ('C:/Users/wande/miniconda3/Library/lib/tcl8.6', 'tcl'),
        ('C:/Users/wande/miniconda3/Library/lib/tk8.6', 'tk'),
    ],
    hiddenimports=[
        'tkinter',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL._tkinter_finder',
        'cv2',
        'numpy',
        'gui_app',
        'capture_engine',
        'config_manager',
        'ffmpeg_wrapper',
        'preset_manager',
        'video_export_controller',
        'video_export_panel',
        'tooltip',
        'video_export_tooltips',
        'capture_tooltips',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RTSP_Timelapse',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
    icon=None,  # Add icon path here if you have one: 'icon.ico'
)
