import sys
import logging
from PySide6.QtWidgets import QApplication

# ────────────────────────────────────────────────────────────────────────────
# Logging Configuration
# ────────────────────────────────────────────────────────────────────────────
# This forces logging to output to the terminal (stdout) with timestamps.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True # Ensures this config overrides any previous settings
)

# Log start immediately to verify it works
log = logging.getLogger("launcher")
log.info("Initializing application...")

from main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    app.setOrganizationName("ThumbnailPicker")
    app.setApplicationName("Video Thumbnail Picker")
    
    win = MainWindow()
    win.show()
    
    log.info("GUI Launched. Ready for input.")
    sys.exit(app.exec())