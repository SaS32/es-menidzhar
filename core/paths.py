# ── Where things live ────────────────────────────────────────────────────────
#
# Two different roots, and mixing them up is the classic packaging bug:
#
#   RESOURCE_DIR — read-only files shipped WITH the program (templates, static,
#                  the DejaVu fonts). In a PyInstaller one-file build these are
#                  unpacked into a temp folder that is DELETED on exit.
#   DATA_DIR     — the user's own data (etazna.db, backups/, generated PDFs).
#                  Must survive restarts, so it sits next to the .exe (frozen)
#                  or next to the sources (running from Python).
#
# Never write to RESOURCE_DIR — under a frozen build the write is silently
# thrown away when the program closes.
# ─────────────────────────────────────────────────────────────────────────────
import os
import sys

FROZEN = getattr(sys, "frozen", False)

_SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# PyInstaller sets sys._MEIPASS to the unpack folder; plain Python has no such
# attribute and the sources are the resources.
RESOURCE_DIR = getattr(sys, "_MEIPASS", None) or _SRC_ROOT

# ES_DATA_DIR overrides the location of etazna.db and friends — useful when the
# .exe lives in Program Files or on a read-only share.
DATA_DIR = os.environ.get("ES_DATA_DIR") or (
    os.path.dirname(os.path.abspath(sys.executable)) if FROZEN else _SRC_ROOT
)


def resource(*parts):
    """Absolute path to a bundled, read-only file."""
    return os.path.join(RESOURCE_DIR, *parts)


def data(*parts):
    """Absolute path inside the writable data directory (created on demand)."""
    path = os.path.join(DATA_DIR, *parts)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return path
