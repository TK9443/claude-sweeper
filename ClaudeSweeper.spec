# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for both platforms. The purge engine (Node script plus its LevelDB module)
travels inside the bundle, so the installed app never depends on the repo being present."""

import os
import re
import sys

HERE = os.path.abspath(os.getcwd())
ASSETS = os.path.join(HERE, 'assets')
ICO = os.path.join(ASSETS, 'claude-sweeper.ico')
ICNS = os.path.join(ASSETS, 'claude-sweeper.icns')

version = '0.0.0'
with open(os.path.join(HERE, 'claude_sweeper', '__init__.py'), encoding='utf-8') as handle:
    match = re.search(r'__version__\s*=\s*"([^"]+)"', handle.read())
    if match:
        version = match.group(1)

a = Analysis(
    ['claude_sweeper/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('purge/purge.mjs', 'purge'), ('purge/package.json', 'purge'), ('purge/node_modules', 'purge/node_modules')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PIL', 'numpy', 'pytest', 'tkinter', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.Qt3DCore', 'PySide6.QtMultimedia'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ClaudeSweeper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[ICNS if sys.platform == 'darwin' else ICO],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ClaudeSweeper',
)
app = BUNDLE(
    coll,
    name='Claude Sweeper.app',
    icon=ICNS,
    bundle_identifier='co.uk.kalkman.claudesweeper',
    version=version,
    info_plist={
        'CFBundleName': 'Claude Sweeper',
        'CFBundleDisplayName': 'Claude Sweeper',
        'CFBundleShortVersionString': version,
        'CFBundleVersion': version,
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '12.0',
        'NSHumanReadableCopyright': 'Toby Kalkman',
    },
)
