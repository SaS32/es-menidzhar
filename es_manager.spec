# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for ЕС Мениджър — one self-contained .exe, no Python needed
# on the target machine.
#
# Build with:  build_exe.bat      (creates the build venv and runs this)
#
# What goes where at run time
# ───────────────────────────
#   templates/, static/  → bundled INTO the exe, unpacked to a temp folder on
#                          every start and deleted on exit (core.paths.RESOURCE_DIR)
#   etazna.db, backups/, → written NEXT TO the exe (core.paths.DATA_DIR), so the
#   reports/generated/     data survives restarts and stays easy to copy to a USB
#
# Never add a writable file to `datas` — the write would be thrown away when
# the program closes.

import os
import re

# The version comes from core/__init__.py, the single source of truth.
_init = open(os.path.join("core", "__init__.py"), encoding="utf-8").read()
VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', _init).group(1)

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("templates", "templates"),
        # Includes static/fonts/DejaVuSans*.ttf — without them the PDF reports
        # come out with blank Cyrillic text.
        ("static", "static"),
    ],
    # Imported lazily inside route functions, so PyInstaller cannot see them.
    hiddenimports=[
        "reports.pdf_generator",
        "core.paths",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc_data"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=f"ES_Menidzhar_v{VERSION}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # Console stays visible: it prints the address to open and Ctrl+C stops
    # the server. Hiding it would leave the user with no way to stop the app.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
