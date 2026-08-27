"""Video Thumbnail Picker — entry point.

Run with:
    python app.py
"""
from __future__ import annotations

import logging
import os
import sys

# ────────────────────────────────────────────────────────────────────────────
# Logging configuration — early, before anything else logs.
# ────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)
log = logging.getLogger("launcher")

# OpenCV: prefer using our own thread pool, disable its internal threading
# to avoid contention with the ThreadPoolExecutor in analysis.py.
os.environ.setdefault("OMP_NUM_THREADS", "1")
try:
    import cv2
    cv2.setNumThreads(0)        # we parallelise via ThreadPoolExecutor
    cv2.ocl.setUseOpenCL(True)  # OpenCL helps if available; harmless if not
    log.info(f"OpenCV {cv2.__version__} — threads=0, OpenCL={cv2.ocl.useOpenCL()}")
except Exception as e:
    log.warning(f"Could not configure OpenCV: {e}")

# Now safe to import Qt + main window
from PySide6.QtWidgets import QApplication  # noqa: E402
from main_window import MainWindow          # noqa: E402


def main() -> int:
    log.info("Initializing application…")
    app = QApplication(sys.argv)
    app.setOrganizationName("ThumbnailPicker")
    app.setApplicationName("Video Thumbnail Picker")
    app.setApplicationVersion("2.1")

    # Pre-warm the Haar cascades so the first analysis isn't slow.
    # This runs in the main thread but only takes ~100 ms.
    try:
        from analysis import _get_cascades
        _get_cascades()
    except Exception as e:
        log.warning(f"Could not pre-warm cascades: {e}")

    win = MainWindow()
    win.show()

    log.info("GUI launched. Ready for input.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
