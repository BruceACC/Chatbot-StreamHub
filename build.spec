# KickBot — PyInstaller build spec
# Run with: pyinstaller build.spec

import sys
from pathlib import Path
import subprocess

# Find playwright browser path
def find_playwright_browsers():
    """Find the chromium binary bundled with playwright."""
    import playwright
    playwright_path = Path(playwright.__file__).parent
    return str(playwright_path)

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Include customtkinter assets
        (
            str(Path(sys.exec_prefix) / 'Lib' / 'site-packages' / 'customtkinter'),
            'customtkinter'
        ),
        # Include bundled Chromium if PLAYWRIGHT_BROWSERS_PATH=0 was used
        (
            str(Path(sys.exec_prefix) / 'Lib' / 'site-packages' / 'playwright' / 'driver'),
            'playwright/driver'
        ),
    ],
    hiddenimports=[
        'customtkinter',
        'PIL',
        'PIL._tkinter_finder',
        'playwright',
        'playwright.sync_api',
        'playwright._impl._sync_api',
        'playwright._impl._browser_context',
        'playwright._impl._browser',
        'playwright._impl._page',
        'playwright._impl._element_handle',
        'cryptography',
        'core.session_manager',
        'core.bot_worker',
        'core.spam_engine',
        'core.message_pool',
        'gui.main_window',
        'gui.account_panel',
        'gui.config_panel',
        'gui.message_editor',
        'gui.bot_control',
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
    [],
    exclude_binaries=True,
    name='kickbot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # No console window (windowed app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='kickbot',
)
