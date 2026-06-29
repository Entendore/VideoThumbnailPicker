"""Video Thumbnail Picker — standalone single-file version.

Merged from: config.py, state.py, utils.py, framestore.py,
             analysis.py, widgets.py, dialogs.py, main_window.py, app.py

Run with: python thumbnail_picker.py
"""

from __future__ import annotations

# ==================================================================
# config.py
# ==================================================================

"""Application configuration: presets, scoring profiles, theme, stylesheet.

All static configuration lives here so the rest of the codebase can stay
focused on behaviour rather than tuning constants.
"""

from typing import Dict, Optional, Tuple

# ────────────────────────────────────────────────────────────────────────────
# Output Presets
# ────────────────────────────────────────────────────────────────────────────
PRESETS: Dict[str, Optional[Tuple[int, int]]] = {
    "Original":          None,
    "YouTube (1280×720)":  (1280, 720),
    "YouTube (1920×1080)": (1920, 1080),
    "Instagram Square":   (1080, 1080),
    "Instagram Portrait": (1080, 1350),
    "Twitter Header":     (1500, 500),
    "TikTok":             (1080, 1920),
}

# ────────────────────────────────────────────────────────────────────────────
# Algorithm Profiles — weights per scoring criterion
# ────────────────────────────────────────────────────────────────────────────
ALGORITHM_PROFILES: Dict[str, Dict[str, float]] = {
    "General (Balanced)": {
        "sharpness": 0.15, "colorfulness": 0.08, "contrast": 0.07, "brightness": 0.05,
        "entropy": 0.08, "composition": 0.10, "skin_tone": 0.04, "faces": 0.12,
        "motion": 0.03, "exposure_quality": 0.08, "dynamic_range": 0.06,
        "visual_complexity": 0.04, "color_harmony": 0.05, "center_weight": 0.05,
    },
    "Face Focus (Portrait)": {
        "sharpness": 0.18, "faces": 0.35, "skin_tone": 0.12, "center_weight": 0.12,
        "exposure_quality": 0.10, "brightness": 0.05, "composition": 0.04,
        "contrast": 0.04, "colorfulness": 0.0, "entropy": 0.0,
        "motion": 0.0, "dynamic_range": 0.0, "visual_complexity": 0.0, "color_harmony": 0.0,
    },
    "Scenery (Landscape)": {
        "composition": 0.20, "color_harmony": 0.15, "dynamic_range": 0.12,
        "sharpness": 0.12, "exposure_quality": 0.10, "visual_complexity": 0.08,
        "contrast": 0.08, "colorfulness": 0.07, "entropy": 0.05, "center_weight": 0.03,
        "faces": 0.0, "skin_tone": 0.0, "motion": 0.0, "brightness": 0.0,
    },
    "Action (Motion)": {
        "sharpness": 0.18, "contrast": 0.14, "dynamic_range": 0.10,
        "visual_complexity": 0.10, "exposure_quality": 0.08, "entropy": 0.08,
        "colorfulness": 0.07, "composition": 0.07, "center_weight": 0.07,
        "faces": 0.05, "motion": 0.03, "brightness": 0.03,
        "skin_tone": 0.0, "color_harmony": 0.0,
    },
}

CRIT_LABELS: Dict[str, str] = {
    "sharpness":          "Sharpness",
    "colorfulness":       "Colour",
    "contrast":           "Contrast",
    "brightness":         "Bright",
    "entropy":            "Entropy",
    "composition":        "Compos.",
    "skin_tone":          "Skin",
    "faces":              "Faces",
    "motion":             "Motion",
    "exposure_quality":   "Exposure",
    "dynamic_range":      "Range",
    "visual_complexity":  "Complex",
    "color_harmony":      "Harmony",
    "center_weight":      "Center",
}

# ────────────────────────────────────────────────────────────────────────────
# Performance Constants
# ────────────────────────────────────────────────────────────────────────────
SCORING_MAX_DIMENSION: int = 720     # downscale frames to this max edge before scoring
GALLERY_THUMB_W: int = 200           # gallery card thumbnail width
GALLERY_THUMB_H: int = 110           # gallery card thumbnail height
FILMSTRIP_THUMB_H: int = 64          # filmstrip thumbnail height
GALLERY_COLUMNS: int = 3             # number of columns in the gallery grid
ANALYSIS_BATCH_INTERVAL_MS: int = 80 # debounce interval for batched candidate_ready emissions
DEFAULT_FILMSTRIP_FRAMES: int = 200  # number of frames in the filmstrip overview

# ────────────────────────────────────────────────────────────────────────────
# Gallery Sort Options
# ────────────────────────────────────────────────────────────────────────────
# Each entry: (display_name, sort_key_or_None_for_score, reverse_bool)
SORT_OPTIONS = [
    ("Score",          None,              True),   # by total_score descending
    ("Starred First",  "__starred__",     True),   # starred on top, then by score
    ("Time",           "timestamp",       False),  # by timestamp ascending
    ("Sharpness",      "sharpness",       True),
    ("Contrast",       "contrast",        True),
    ("Brightness",     "brightness",      True),
    ("Composition",    "composition",     True),
    ("Faces",          "faces",           True),
    ("Colorfulness",   "colorfulness",    True),
    ("Dynamic Range",  "dynamic_range",   True),
    ("Entropy",        "entropy",         True),
    ("Exposure",       "exposure_quality", True),
    ("Complexity",     "visual_complexity", True),
    ("Harmony",        "color_harmony",   True),
    ("Center",         "center_weight",   True),
    ("Skin",           "skin_tone",       True),
]

# Default score threshold for the gallery filter slider (0.0 = show all)
SCORE_THRESHOLD_DEFAULT: float = 0.0

# ────────────────────────────────────────────────────────────────────────────
# Re-analyze neighborhood
# ────────────────────────────────────────────────────────────────────────────
REANALYZE_RADIUS_SEC: float = 2.0     # ±N seconds around the selected frame
REANALYZE_SAMPLES: int = 12           # number of frames to sample in that window

# ────────────────────────────────────────────────────────────────────────────
# ETA / progress
# ────────────────────────────────────────────────────────────────────────────
ETA_UPDATE_INTERVAL_MS: int = 500     # refresh ETA display every 500 ms

# ────────────────────────────────────────────────────────────────────────────
# Gallery card sizes
# ────────────────────────────────────────────────────────────────────────────
CARD_SIZES = ["Small", "Medium", "Large"]
DEFAULT_CARD_SIZE: str = "Medium"

# ────────────────────────────────────────────────────────────────────────────
# Filename templates for save / batch-save
# ────────────────────────────────────────────────────────────────────────────
# Placeholders (case-insensitive):
#   {video}      — video filename without extension
#   {timestamp}  — frame timestamp formatted as MMSS-mmm
#   {ts_seconds} — frame timestamp in seconds (e.g. 12.345)
#   {score}      — total score, 3 decimals
#   {rank}       — 1-based rank in the current sort order
#   {preset}     — output preset name (e.g. "YouTube (1280×720)")
FILENAME_TEMPLATES = [
    "thumb_{timestamp}.jpg",
    "{video}_{timestamp}.jpg",
    "{video}_rank{rank}_{score}.jpg",
    "{video}_{ts_seconds}s_{score}.jpg",
    "thumbnail_{rank:02d}.jpg",
]
DEFAULT_FILENAME_TEMPLATE: str = "thumb_{timestamp}.jpg"

# ────────────────────────────────────────────────────────────────────────────
# Themes
# ────────────────────────────────────────────────────────────────────────────
THEME_DARK = "dark"
THEME_LIGHT = "light"
THEMES = [THEME_DARK, THEME_LIGHT]
DEFAULT_THEME: str = THEME_DARK


def _build_light_theme() -> dict:
    """Return a dict of color overrides for the light theme (monochrome)."""
    return {
        "C_BG":       "#FAFAFA",
        "C_SURFACE":  "#F0F0F0",
        "C_CARD":     "#E8E8E8",
        "C_OVERLAY":  "#D4D4D4",
        "C_TEXT":     "#1A1A1A",
        "C_SUBTEXT":  "#737373",
        "C_ACCENT":   "#525252",
    }


def get_theme_colors(theme: str) -> dict:
    """Return the colour dict for ``theme``. Falls back to dark."""
    if theme == THEME_LIGHT:
        return _build_light_theme()
    # Dark (default) — import-time values
    import sys
    this = sys.modules[__name__]
    return {
        "C_BG": C_BG, "C_SURFACE": C_SURFACE, "C_CARD": C_CARD,
        "C_OVERLAY": C_OVERLAY, "C_TEXT": C_TEXT, "C_SUBTEXT": C_SUBTEXT,
        "C_ACCENT": C_ACCENT,
    }


def build_stylesheet(colors: dict) -> str:
    """Build the application stylesheet from a colour dict."""
    c = colors
    return f"""
QMainWindow {{ background:{c['C_BG']}; }}
QWidget {{ color:{c['C_TEXT']}; font-family:"Segoe UI","SF Pro","Inter",sans-serif; font-size:12px; }}
QToolTip {{ background:{c['C_OVERLAY']}; color:{c['C_TEXT']}; border:1px solid {c['C_SURFACE']}; padding:4px 6px; border-radius:4px; }}

QGroupBox {{
    border:1px solid {c['C_OVERLAY']}; border-radius:6px; margin-top:14px;
    padding:12px 10px 10px 10px; font-weight:bold; color:{c['C_TEXT']};
    background:{c['C_SURFACE']};
}}
QGroupBox::title {{ subcontrol-origin:margin; left:12px; padding:0 6px; }}

QPushButton {{
    background:{c['C_OVERLAY']}; color:{c['C_TEXT']}; border:none; border-radius:5px;
    padding:7px 14px; font-weight:600;
}}
QPushButton:hover    {{ background:{c['C_ACCENT']}; color:{c['C_BG']}; }}
QPushButton:pressed  {{ background:{c['C_OVERLAY']}; color:{c['C_TEXT']}; }}
QPushButton#btnGreen   {{ background:{c['C_OVERLAY']}; color:{c['C_TEXT']}; }}
QPushButton#btnGreen:hover   {{ background:{c['C_ACCENT']}; color:{c['C_BG']}; }}
QPushButton#btnRed     {{ background:{c['C_OVERLAY']}; color:{c['C_TEXT']}; }}
QPushButton#btnRed:hover     {{ background:{c['C_ACCENT']}; color:{c['C_BG']}; }}
QPushButton#btnPrimary {{ background:{c['C_TEXT']}; color:{c['C_BG']}; }}
QPushButton#btnPrimary:hover {{ background:{c['C_ACCENT']}; color:{c['C_BG']}; }}
QPushButton:disabled   {{ background:{c['C_OVERLAY']}; color:{c['C_SUBTEXT']}; }}

QComboBox {{ background:{c['C_CARD']}; border:1px solid {c['C_OVERLAY']}; border-radius:5px; padding:5px 10px; min-height:18px; }}
QComboBox:hover {{ border-color:{c['C_ACCENT']}; }}
QComboBox::drop-down {{ border:none; width:22px; }}
QComboBox QAbstractItemView {{ background:{c['C_CARD']}; selection-background-color:{c['C_ACCENT']}; outline:none; }}

QSpinBox {{ background:{c['C_CARD']}; border:1px solid {c['C_OVERLAY']}; border-radius:5px; padding:4px 6px; }}
QSpinBox:hover {{ border-color:{c['C_ACCENT']}; }}

QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{ background:{c['C_SURFACE']}; width:10px; border-radius:5px; margin:2px; }}
QScrollBar::handle:vertical {{ background:{c['C_OVERLAY']}; border-radius:5px; min-height:24px; }}
QScrollBar::handle:vertical:hover {{ background:{c['C_ACCENT']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; }}
QScrollBar:horizontal {{ background:{c['C_SURFACE']}; height:10px; border-radius:5px; margin:2px; }}
QScrollBar::handle:horizontal {{ background:{c['C_OVERLAY']}; border-radius:5px; min-width:24px; }}
QScrollBar::handle:horizontal:hover {{ background:{c['C_ACCENT']}; }}

QStatusBar {{ background:{c['C_SURFACE']}; color:{c['C_SUBTEXT']}; font-weight:bold; border-top:1px solid {c['C_OVERLAY']}; }}
QStatusBar::item {{ border:none; }}

QSlider::groove:horizontal {{ height:4px; background:{c['C_OVERLAY']}; border-radius:2px; }}
QSlider::handle:horizontal {{ background:{c['C_TEXT']}; width:14px; height:14px; margin:-5px 0; border-radius:7px; }}
QSlider::handle:horizontal:hover {{ background:{c['C_ACCENT']}; }}

QCheckBox::indicator {{ width:14px; height:14px; border-radius:3px; border:1px solid {c['C_OVERLAY']}; background:{c['C_CARD']}; }}
QCheckBox::indicator:checked {{ background:{c['C_TEXT']}; border-color:{c['C_TEXT']}; }}

QProgressBar {{ border:none; border-radius:5px; background:{c['C_OVERLAY']}; text-align:center; color:{c['C_BG']}; font-weight:bold; min-height:18px; }}
QProgressBar::chunk {{ background:{c['C_TEXT']}; border-radius:4px; }}

QLabel#LblTitle   {{ font-size:15px; font-weight:bold; color:{c['C_TEXT']}; }}
QLabel#LblSection {{ font-size:11px; font-weight:bold; color:{c['C_SUBTEXT']}; letter-spacing:1px; }}
QLabel#LblValue   {{ font-size:12px; color:{c['C_TEXT']}; font-family:"JetBrains Mono","Consolas",monospace; }}

QFrame#Card       {{ background:{c['C_CARD']};    border-radius:8px; }}
QFrame#CardHover  {{ background:{c['C_CARD']};    border-radius:8px; border:1px solid transparent; }}
QFrame#CardHover:hover {{ border-color:{c['C_ACCENT']}; }}
QFrame#Separator  {{ background:{c['C_OVERLAY']}; max-height:1px; min-height:1px; border:none; }}

QTabWidget::pane  {{ border:1px solid {c['C_OVERLAY']}; border-radius:6px; background:{c['C_SURFACE']}; }}
QTabBar::tab      {{ background:{c['C_CARD']}; color:{c['C_SUBTEXT']}; padding:8px 18px;
                     border-top-left-radius:5px; border-top-right-radius:5px; margin-right:2px; }}
QTabBar::tab:selected    {{ background:{c['C_SURFACE']}; color:{c['C_TEXT']}; font-weight:bold; }}
QTabBar::tab:hover:!selected {{ background:{c['C_OVERLAY']}; color:{c['C_TEXT']}; }}

QToolBar {{ background:{c['C_SURFACE']}; border-bottom:1px solid {c['C_OVERLAY']}; spacing:4px; padding:4px; }}
QToolBar::separator {{ background:{c['C_OVERLAY']}; width:1px; margin:6px 4px; }}

QMenu {{ background:{c['C_CARD']}; border:1px solid {c['C_OVERLAY']}; border-radius:5px; padding:4px; }}
QMenu::item {{ padding:6px 18px; border-radius:3px; }}
QMenu::item:selected {{ background:{c['C_ACCENT']}; color:{c['C_BG']}; }}
"""

# ────────────────────────────────────────────────────────────────────────────
# Theme (Monochrome Dark)
# ────────────────────────────────────────────────────────────────────────────
C_BG       = "#171717"
C_SURFACE  = "#262626"
C_CARD     = "#2E2E2E"
C_OVERLAY  = "#404040"
C_TEXT     = "#D4D4D4"
C_SUBTEXT  = "#737373"
C_ACCENT   = "#888888"

STYLESHEET = f"""
QMainWindow {{ background:{C_BG}; }}
QWidget {{ color:{C_TEXT}; font-family:"Segoe UI","SF Pro","Inter",sans-serif; font-size:12px; }}
QToolTip {{ background:{C_OVERLAY}; color:{C_TEXT}; border:1px solid {C_SURFACE}; padding:4px 6px; border-radius:4px; }}

QGroupBox {{
    border:1px solid {C_OVERLAY}; border-radius:6px; margin-top:14px;
    padding:12px 10px 10px 10px; font-weight:bold; color:{C_TEXT};
    background:{C_SURFACE};
}}
QGroupBox::title {{ subcontrol-origin:margin; left:12px; padding:0 6px; }}

QPushButton {{
    background:{C_OVERLAY}; color:{C_TEXT}; border:none; border-radius:5px;
    padding:7px 14px; font-weight:600;
}}
QPushButton:hover    {{ background:{C_ACCENT}; color:{C_BG}; }}
QPushButton:pressed  {{ background:{C_OVERLAY}; color:{C_TEXT}; }}
QPushButton#btnGreen   {{ background:{C_OVERLAY}; color:{C_TEXT}; }}
QPushButton#btnGreen:hover   {{ background:{C_ACCENT}; color:{C_BG}; }}
QPushButton#btnRed     {{ background:{C_OVERLAY}; color:{C_TEXT}; }}
QPushButton#btnRed:hover     {{ background:{C_ACCENT}; color:{C_BG}; }}
QPushButton#btnPrimary {{ background:{C_TEXT}; color:{C_BG}; }}
QPushButton#btnPrimary:hover {{ background:{C_ACCENT}; color:{C_BG}; }}
QPushButton:disabled   {{ background:{C_OVERLAY}; color:{C_SUBTEXT}; }}

QComboBox {{ background:{C_CARD}; border:1px solid {C_OVERLAY}; border-radius:5px; padding:5px 10px; min-height:18px; }}
QComboBox:hover {{ border-color:{C_ACCENT}; }}
QComboBox::drop-down {{ border:none; width:22px; }}
QComboBox QAbstractItemView {{ background:{C_CARD}; selection-background-color:{C_ACCENT}; outline:none; }}

QSpinBox {{ background:{C_CARD}; border:1px solid {C_OVERLAY}; border-radius:5px; padding:4px 6px; }}
QSpinBox:hover {{ border-color:{C_ACCENT}; }}

QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{ background:{C_SURFACE}; width:10px; border-radius:5px; margin:2px; }}
QScrollBar::handle:vertical {{ background:{C_OVERLAY}; border-radius:5px; min-height:24px; }}
QScrollBar::handle:vertical:hover {{ background:{C_ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; }}
QScrollBar:horizontal {{ background:{C_SURFACE}; height:10px; border-radius:5px; margin:2px; }}
QScrollBar::handle:horizontal {{ background:{C_OVERLAY}; border-radius:5px; min-width:24px; }}
QScrollBar::handle:horizontal:hover {{ background:{C_ACCENT}; }}

QStatusBar {{ background:{C_SURFACE}; color:{C_SUBTEXT}; font-weight:bold; border-top:1px solid {C_OVERLAY}; }}
QStatusBar::item {{ border:none; }}

QSlider::groove:horizontal {{ height:4px; background:{C_OVERLAY}; border-radius:2px; }}
QSlider::handle:horizontal {{ background:{C_TEXT}; width:14px; height:14px; margin:-5px 0; border-radius:7px; }}
QSlider::handle:horizontal:hover {{ background:{C_ACCENT}; }}

QCheckBox::indicator {{ width:14px; height:14px; border-radius:3px; border:1px solid {C_OVERLAY}; background:{C_CARD}; }}
QCheckBox::indicator:checked {{ background:{C_TEXT}; border-color:{C_TEXT}; }}

QProgressBar {{ border:none; border-radius:5px; background:{C_OVERLAY}; text-align:center; color:{C_BG}; font-weight:bold; min-height:18px; }}
QProgressBar::chunk {{ background:{C_TEXT}; border-radius:4px; }}

QLabel#LblTitle   {{ font-size:15px; font-weight:bold; color:{C_TEXT}; }}
QLabel#LblSection {{ font-size:11px; font-weight:bold; color:{C_SUBTEXT}; letter-spacing:1px; }}
QLabel#LblValue   {{ font-size:12px; color:{C_TEXT}; font-family:"JetBrains Mono","Consolas",monospace; }}

QFrame#Card       {{ background:{C_CARD};    border-radius:8px; }}
QFrame#CardHover  {{ background:{C_CARD};    border-radius:8px; border:1px solid transparent; }}
QFrame#CardHover:hover {{ border-color:{C_ACCENT}; }}
QFrame#Separator  {{ background:{C_OVERLAY}; max-height:1px; min-height:1px; border:none; }}

QTabWidget::pane  {{ border:1px solid {C_OVERLAY}; border-radius:6px; background:{C_SURFACE}; }}
QTabBar::tab      {{ background:{C_CARD}; color:{C_SUBTEXT}; padding:8px 18px;
                     border-top-left-radius:5px; border-top-right-radius:5px; margin-right:2px; }}
QTabBar::tab:selected    {{ background:{C_SURFACE}; color:{C_TEXT}; font-weight:bold; }}
QTabBar::tab:hover:!selected {{ background:{C_OVERLAY}; color:{C_TEXT}; }}

QToolBar {{ background:{C_SURFACE}; border-bottom:1px solid {C_OVERLAY}; spacing:4px; padding:4px; }}
QToolBar::separator {{ background:{C_OVERLAY}; width:1px; margin:6px 4px; }}

QMenu {{ background:{C_CARD}; border:1px solid {C_OVERLAY}; border-radius:5px; padding:4px; }}
QMenu::item {{ padding:6px 18px; border-radius:3px; }}
QMenu::item:selected {{ background:{C_ACCENT}; color:{C_BG}; }}
"""

# ==================================================================
# state.py
# ==================================================================

"""Persistent application state: settings, recent files, custom profiles, project sidecars.

All state that should survive an app restart lives here:
  * Window geometry / splitter sizes (via QSettings)
  * Last-used analysis settings (algorithm, preset, samples, etc.)
  * Recently opened files
  * User-defined custom algorithm profiles
  * Per-video starred-state sidecar (.vtp.json next to the video)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import QSettings

logger = logging.getLogger("thumbnail_picker")

RECENT_FILES_MAX = 10
SIDECAR_SUFFIX = ".vtp.json"
SIDECAR_VERSION = 1


class AppSettings:
    """Thin wrapper around QSettings for persistent app configuration."""

    def __init__(self) -> None:
        self._s = QSettings("ThumbnailPicker", "Video Thumbnail Picker")

    # ── Window state ──────────────────────────────────────────────────
    def save_window_state(self, window) -> None:
        self._s.setValue("ui/windowGeometry", window.saveGeometry())
        # Splitter sizes stored as a list of ints
        splitter = getattr(window, "_splitter", None)
        if splitter is not None:
            self._s.setValue("ui/splitterSizes", splitter.sizes())

    def restore_window_state(self, window) -> None:
        geo = self._s.value("ui/windowGeometry")
        if geo is not None:
            window.restoreGeometry(geo)
        # Splitter sizes are applied after UI is built (caller does this)

    def splitter_sizes(self) -> List[int]:
        raw = self._s.value("ui/splitterSizes")
        if raw is None:
            return []
        if isinstance(raw, (list, tuple)):
            return [int(x) for x in raw]
        return []

    # ── Analysis settings ─────────────────────────────────────────────
    def save_analysis_settings(self, *, algo: str, preset: str, samples: int,
                               cands: int, scene: bool, sort: str,
                               threshold: float) -> None:
        self._s.setValue("analysis/algo", algo)
        self._s.setValue("analysis/preset", preset)
        self._s.setValue("analysis/samples", int(samples))
        self._s.setValue("analysis/cands", int(cands))
        self._s.setValue("analysis/scene", bool(scene))
        self._s.setValue("analysis/sort", sort)
        self._s.setValue("analysis/threshold", float(threshold))

    def restore_analysis_settings(self) -> Dict[str, Any]:
        return {
            "algo":      self._s.value("analysis/algo", "General (Balanced)", type=str),
            "preset":    self._s.value("analysis/preset", "Original", type=str),
            "samples":   self._s.value("analysis/samples", 80, type=int),
            "cands":     self._s.value("analysis/cands", 15, type=int),
            "scene":     self._s.value("analysis/scene", False, type=bool),
            "sort":      self._s.value("analysis/sort", "Score", type=str),
            "threshold": self._s.value("analysis/threshold", 0.0, type=float),
        }

    # ── UI preferences ────────────────────────────────────────────────
    @property
    def card_size(self) -> str:
        return self._s.value("ui/cardSize", "Medium", type=str)

    @card_size.setter
    def card_size(self, value: str) -> None:
        self._s.setValue("ui/cardSize", str(value))

    @property
    def theme(self) -> str:
        return self._s.value("ui/theme", "dark", type=str)

    @theme.setter
    def theme(self, value: str) -> None:
        self._s.setValue("ui/theme", str(value))

    @property
    def filename_template(self) -> str:
        return self._s.value("ui/filenameTemplate", "thumb_{timestamp}.jpg", type=str)

    @filename_template.setter
    def filename_template(self, value: str) -> None:
        self._s.setValue("ui/filenameTemplate", str(value))

    @property
    def auto_free_memory(self) -> bool:
        """If True, release full-res frames after analysis to save RAM."""
        return self._s.value("ui/autoFreeMemory", False, type=bool)

    @auto_free_memory.setter
    def auto_free_memory(self, value: bool) -> None:
        self._s.setValue("ui/autoFreeMemory", bool(value))

    @property
    def save_quality(self) -> int:
        return self._s.value("io/saveQuality", 95, type=int)

    @save_quality.setter
    def save_quality(self, value: int) -> None:
        self._s.setValue("io/saveQuality", max(1, min(100, int(value))))

    @property
    def save_format(self) -> str:
        return self._s.value("io/saveFormat", "JPEG", type=str)

    @save_format.setter
    def save_format(self, value: str) -> None:
        self._s.setValue("io/saveFormat", str(value))

    @property
    def reanalyze_radius(self) -> float:
        return self._s.value("analysis/reanalyzeRadius", 2.0, type=float)

    @reanalyze_radius.setter
    def reanalyze_radius(self, value: float) -> None:
        self._s.setValue("analysis/reanalyzeRadius", float(value))

    @property
    def reanalyze_samples(self) -> int:
        return self._s.value("analysis/reanalyzeSamples", 12, type=int)

    @reanalyze_samples.setter
    def reanalyze_samples(self, value: int) -> None:
        self._s.setValue("analysis/reanalyzeSamples", max(4, int(value)))

    # ── Recent files ──────────────────────────────────────────────────
    @property
    def recent_files(self) -> List[str]:
        raw = self._s.value("recent/files", [])
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, (list, tuple)):
            return []
        # Filter out files that no longer exist
        return [str(f) for f in raw if Path(f).exists()]

    def add_recent_file(self, path: str) -> None:
        files = self.recent_files
        norm = str(Path(path).resolve())
        files = [f for f in files if Path(f).resolve() != Path(norm)]
        files.insert(0, norm)
        files = files[:RECENT_FILES_MAX]
        self._s.setValue("recent/files", files)

    def clear_recent_files(self) -> None:
        self._s.setValue("recent/files", [])

    # ── Custom algorithm profiles ─────────────────────────────────────
    @property
    def custom_profiles(self) -> Dict[str, Dict[str, float]]:
        raw = self._s.value("profiles/custom", {})
        if not isinstance(raw, dict):
            return {}
        # Sanitise: ensure values are floats
        out: Dict[str, Dict[str, float]] = {}
        for name, weights in raw.items():
            if isinstance(weights, dict):
                out[name] = {k: float(v) for k, v in weights.items()}
        return out

    def save_custom_profile(self, name: str, weights: Dict[str, float]) -> None:
        profiles = self.custom_profiles
        profiles[name] = {k: float(v) for k, v in weights.items()}
        self._s.setValue("profiles/custom", profiles)

    def remove_custom_profile(self, name: str) -> None:
        profiles = self.custom_profiles
        profiles.pop(name, None)
        self._s.setValue("profiles/custom", profiles)

    # ── I/O defaults ──────────────────────────────────────────────────
    @property
    def last_dir(self) -> str:
        return self._s.value("io/lastDir", "", type=str)

    @last_dir.setter
    def last_dir(self, value: str) -> None:
        self._s.setValue("io/lastDir", str(value))

    # ── Flush ─────────────────────────────────────────────────────────
    def sync(self) -> None:
        self._s.sync()


class ProjectState:
    """Per-video sidecar file for starred candidates.

    Saves a small JSON file next to the video (``<video>.vtp.json``) so
    starred frames survive across sessions.
    """

    @staticmethod
    def sidecar_path(video_path: str) -> Path:
        return Path(video_path).with_suffix(SIDECAR_SUFFIX)

    @staticmethod
    def save(video_path: str, candidates: List) -> None:
        """Persist starred-candidate timestamps to a sidecar JSON file."""
        sidecar = ProjectState.sidecar_path(video_path)
        data = {
            "version": SIDECAR_VERSION,
            "video": str(video_path),
            "starred_timestamps": [
                round(c.timestamp, 3) for c in candidates if c.starred
            ],
        }
        try:
            sidecar.write_text(json.dumps(data, indent=2))
            logger.info(f"Saved project state to {sidecar.name}")
        except Exception as e:
            logger.warning(f"Could not save project state: {e}")

    @staticmethod
    def load(video_path: str) -> Dict[str, Any]:
        """Load sidecar state. Returns an empty dict if not found / invalid."""
        sidecar = ProjectState.sidecar_path(video_path)
        if not sidecar.exists():
            return {}
        try:
            data = json.loads(sidecar.read_text())
            if not isinstance(data, dict):
                return {}
            logger.info(f"Loaded project state from {sidecar.name}")
            return data
        except Exception as e:
            logger.warning(f"Could not load project state: {e}")
            return {}

    @staticmethod
    def delete(video_path: str) -> None:
        sidecar = ProjectState.sidecar_path(video_path)
        try:
            if sidecar.exists():
                sidecar.unlink()
        except Exception:
            pass


# Module-level singleton
SETTINGS = AppSettings()

# ==================================================================
# utils.py
# ==================================================================

"""Utility helpers: time formatting, cv2 ⇄ Qt conversions, thumbnail caching.

Centralising the cv2→QImage/QPixmap conversions here means we can:
  * avoid leaking numpy buffers (QImage keeps a reference to the buffer)
  * cache thumbnails so re-rendering the gallery is essentially free
  * keep main_window.py focused on layout/orchestration
"""

import threading
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPixmap


# ────────────────────────────────────────────────────────────────────────────
# Time helpers
# ────────────────────────────────────────────────────────────────────────────
def format_time(t: float) -> str:
    """Render a timestamp in seconds as ``MM:SS.mmm`` (no leading hours)."""
    if t < 0 or not np.isfinite(t):
        return "00:00.000"
    m, s = divmod(int(t), 60)
    ms = int((t - int(t)) * 1000)
    return f"{m:02d}:{s:02d}.{ms:03d}"


def format_duration(t: float) -> str:
    """Render a duration in seconds as ``Hh Mm Ss`` for the info panel."""
    if t <= 0:
        return "0s"
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    parts = []
    if h: parts.append(f"{h}h")
    if m or h: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


# ────────────────────────────────────────────────────────────────────────────
# cv2 ⇄ Qt conversion (zero-copy, lifetime-safe)
# ────────────────────────────────────────────────────────────────────────────
def bgr_to_qimage(bgr: np.ndarray) -> Optional[QImage]:
    """Convert a BGR uint8 ndarray to a QImage without copying the buffer.

    The returned QImage holds a reference to ``bgr`` so the caller does not
    need to keep the array alive manually.
    """
    if bgr is None or bgr.size == 0:
        return None
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    # sip / shiboken will hold a ref to ``rgb`` via the .data buffer,
    # but to be safe we attach it explicitly.
    qim = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    qim._np_buf = rgb  # keep alive
    return qim


def bgr_to_qpixmap(bgr: np.ndarray) -> QPixmap:
    """Convert a BGR ndarray straight to a QPixmap."""
    qim = bgr_to_qimage(bgr)
    return QPixmap.fromImage(qim) if qim is not None else QPixmap()


def scaled_qpixmap(bgr: np.ndarray, w: int, h: int,
                   aspect: Qt.AspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio,
                   smooth: Qt.TransformationMode = Qt.TransformationMode.SmoothTransformation) -> QPixmap:
    """Single-step: BGR ndarray → scaled QPixmap. Avoids intermediate QImage scaling."""
    if bgr is None or bgr.size == 0:
        return QPixmap()
    # Downscale with cv2 (much faster than Qt's smooth scaling for large sources)
    src_h, src_w = bgr.shape[:2]
    if aspect == Qt.AspectRatioMode.KeepAspectRatio:
        scale = min(w / src_w, h / src_h)
    else:
        scale = max(w / src_w, h / src_h)
    new_w = max(1, int(src_w * scale))
    new_h = max(1, int(src_h * scale))
    resized = cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return bgr_to_qpixmap(resized)


# ────────────────────────────────────────────────────────────────────────────
# Thumbnail cache — keyed by Candidate id()
# ────────────────────────────────────────────────────────────────────────────
class ThumbnailCache:
    """Tiny thread-safe pixmap cache for candidate frames.

    Avoids re-running cv2.cvtColor + cv2.resize on every gallery refresh.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._gallery: Dict[int, QPixmap] = {}
        self._filmstrip: Dict[int, QPixmap] = {}


    def gallery(self, cand_id: int, bgr: np.ndarray) -> QPixmap:
        with self._lock:
            pm = self._gallery.get(cand_id)
            if pm is None or pm.isNull():
                pm = scaled_qpixmap(bgr, GALLERY_THUMB_W, GALLERY_THUMB_H)
                self._gallery[cand_id] = pm
            return pm

    def filmstrip(self, cand_id: int, bgr: np.ndarray) -> QPixmap:
        with self._lock:
            pm = self._filmstrip.get(cand_id)
            if pm is None or pm.isNull():
                # filmstrip thumbs are letterbox-shaped: keep aspect, fix height
                src_h, src_w = bgr.shape[:2]
                new_w = max(1, int(src_w * FILMSTRIP_THUMB_H / src_h))
                resized = cv2.resize(bgr, (new_w, FILMSTRIP_THUMB_H), interpolation=cv2.INTER_AREA)
                pm = bgr_to_qpixmap(resized)
                self._filmstrip[cand_id] = pm
            return pm

    def invalidate(self, cand_id: Optional[int] = None) -> None:
        with self._lock:
            if cand_id is None:
                self._gallery.clear()
                self._filmstrip.clear()

            else:
                self._gallery.pop(cand_id, None)
                self._filmstrip.pop(cand_id, None)


# Module-level singleton
THUMBS = ThumbnailCache()


# ────────────────────────────────────────────────────────────────────────────
# Image helpers used by save path
# ────────────────────────────────────────────────────────────────────────────
def fit_crop_pil(pil_img, target: Tuple[int, int]):
    """Resize-and-center-crop a PIL image to fill ``target`` (cover fit)."""
    # PIL.Image already imported at module level
    tw, th = target
    if pil_img.size == (tw, th):
        return pil_img
    ratio = max(tw / pil_img.width, th / pil_img.height)
    pil_img = pil_img.resize(
        (int(pil_img.width * ratio), int(pil_img.height * ratio)),
        Image.Resampling.LANCZOS,
    )
    left = (pil_img.width - tw) // 2
    top = (pil_img.height - th) // 2
    return pil_img.crop((left, top, left + tw, top + th))


def downscale_for_scoring(bgr: np.ndarray, max_dim: int) -> Tuple[np.ndarray, np.ndarray]:
    """Downscale a BGR frame for scoring speed; return (bgr_small, gray_small).

    Many of our scorers (sharpness, contrast, brightness, composition,
    dynamic_range, colorfulness) produce essentially identical rankings on a
    downscaled frame, so we run them on the small version and only keep the
    full-resolution frame for the user-facing preview & save path.
    """
    if bgr is None or bgr.size == 0:
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        return empty, empty
    h, w = bgr.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        small = bgr
    else:
        scale = max_dim / longest
        small = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    return small, gray

# ==================================================================
# framestore.py
# ==================================================================

"""Lazy frame store: LRU cache for full-res video frames.

Problem: keeping 200 full-res 4K frames in memory uses ~7.6 GB. Most of
those frames are never looked at again after scoring — only the few the
user selects for preview / save / contact-sheet need the full buffer.

Solution: ``Candidate`` keeps an optional reference to its BGR ndarray.
When memory pressure is high (or the user clicks "Free Memory"), we
``release_frame()`` on every candidate, setting ``frame_bgr = None``.
The next time the frame is needed, ``ensure_frame()`` calls into the
``FrameStore``, which re-reads it from the video file at the stored
timestamp. A small LRU cache keeps the N most-recently-fetched frames
hot so repeated accesses don't re-seek the video.
"""

import logging
import threading
import weakref
from collections import OrderedDict
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("thumbnail_picker")

# Default LRU size — ~50 frames at 1080p ≈ 300 MB, a reasonable hot set.
DEFAULT_LRU_SIZE: int = 50


class FrameStore:
    """Thread-safe LRU cache for video frames keyed by (path, timestamp).

    Each entry is the BGR ndarray returned by ``cv2.VideoCapture.read()``.
    Use :meth:`get` to fetch a frame; if it's already in the cache the
    cached copy is returned without re-seeking the video.
    """

    def __init__(self, max_entries: int = DEFAULT_LRU_SIZE) -> None:
        self._max = max(1, int(max_entries))
        self._cache: "OrderedDict[Tuple[str, float], np.ndarray]" = OrderedDict()
        self._lock = threading.RLock()
        # Track open VideoCapture objects per path (lazy, closed on eviction)
        self._caps: dict = {}
        self._caps_lock = threading.Lock()

    # ── public API ──────────────────────────────────────────────────
    def get(self, video_path: str, timestamp: float) -> Optional[np.ndarray]:
        """Return the BGR frame at ``timestamp`` seconds, or None on failure."""
        key = (video_path, round(timestamp, 3))
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                # Move to end (most-recently-used)
                self._cache.move_to_end(key)
                return cached

        # Not cached — fetch from disk
        frame = self._fetch(video_path, timestamp)
        if frame is None:
            return None

        with self._lock:
            self._cache[key] = frame
            self._cache.move_to_end(key)
            # Evict oldest if over capacity
            while len(self._cache) > self._max:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug(f"Evicted frame {evicted_key} from LRU cache")
        return frame

    def prefetch(self, video_path: str, timestamp: float) -> None:
        """Fetch a frame in the background (best-effort, no return value)."""
        threading.Thread(
            target=self.get, args=(video_path, timestamp), daemon=True
        ).start()

    def release_path(self, video_path: str) -> None:
        """Drop all cached frames for a given video path (e.g. on file close)."""
        with self._lock:
            keys_to_drop = [k for k in self._cache if k[0] == video_path]
            for k in keys_to_drop:
                self._cache.pop(k, None)
        with self._caps_lock:
            cap = self._caps.pop(video_path, None)
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    def clear(self) -> None:
        """Drop the entire cache and release all VideoCapture handles."""
        with self._lock:
            self._cache.clear()
        with self._caps_lock:
            for cap in self._caps.values():
                try:
                    cap.release()
                except Exception:
                    pass
            self._caps.clear()

    def stats(self) -> dict:
        """Return cache statistics for diagnostics."""
        with self._lock:
            return {
                "entries": len(self._cache),
                "max": self._max,
                "paths_tracked": len(self._caps),
            }

    def resize(self, max_entries: int) -> None:
        """Change the LRU capacity, evicting excess entries if shrinking."""
        self._max = max(1, int(max_entries))
        with self._lock:
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)

    # ── internal ────────────────────────────────────────────────────
    def _fetch(self, video_path: str, timestamp: float) -> Optional[np.ndarray]:
        """Open (or reuse) a VideoCapture, seek to ``timestamp``, read one frame."""
        cap = self._get_cap(video_path)
        if cap is None:
            return None
        try:
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.warning(f"Failed to read frame at {timestamp:.3f}s from {video_path}")
                return None
            return frame
        except Exception as e:
            logger.error(f"Error reading frame: {e}")
            return None

    def _get_cap(self, video_path: str):
        """Get (or open) a VideoCapture for ``video_path``. Returns None on failure."""
        with self._caps_lock:
            cap = self._caps.get(video_path)
            if cap is not None:
                return cap
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Could not open video: {video_path}")
                return None
            self._caps[video_path] = cap
            return cap


# Module-level singleton
FRAME_STORE = FrameStore()


def ensure_frame(cand) -> Optional[np.ndarray]:
    """Return the candidate's frame, re-fetching from disk if it was released.

    This is the canonical accessor — never read ``cand.frame_bgr`` directly
    from outside ``analysis.py``; always go through this helper (or
    ``cand.ensure_frame()`` which wraps it).
    """
    if cand.frame_bgr is not None:
        return cand.frame_bgr
    if not cand.video_path or cand.timestamp < 0:
        return None
    frame = FRAME_STORE.get(cand.video_path, cand.timestamp)
    if frame is not None:
        cand.frame_bgr = frame  # re-attach so subsequent access is free
    return frame

# ==================================================================
# analysis.py
# ==================================================================

"""Video analysis: scoring functions, candidate dataclass, and the worker thread.

Performance highlights (vs the original):
  * Pre-computes the grayscale frame once per candidate and reuses it for
    every scorer that needs it (was being re-computed 3× per frame).
  * Downscales frames before scoring (configurable via SCORING_MAX_DIMENSION)
    — scoring ranks are nearly identical, but cv2 ops run 4–6× faster.
  * Filmstrip generation runs in a ThreadPoolExecutor (was strictly serial).
  * ``candidate_ready`` is debounced via a timer so a 200-candidate run
    doesn't queue 200 UI refreshes on the main thread.
  * Scene detection reuses one VideoCapture and a single grayscale buffer.
  * ``filter_similar`` caches each candidate's colour histogram.
"""

import logging
import math
import os
import traceback
import concurrent.futures
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, QTimer


# ────────────────────────────────────────────────────────────────────────────
# Logging & globals
# ────────────────────────────────────────────────────────────────────────────
logger = logging.getLogger("thumbnail_picker")
_face_cascade: Optional[cv2.CascadeClassifier] = None
_profile_cascade: Optional[cv2.CascadeClassifier] = None


def _get_cascades() -> Tuple[Optional[cv2.CascadeClassifier], Optional[cv2.CascadeClassifier]]:
    """Lazily load Haar cascades for face detection. Returns (None, None) on failure."""
    global _face_cascade, _profile_cascade
    if _face_cascade is None:
        try:
            _face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            _profile_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_profileface.xml"
            )
            if _face_cascade.empty() or _profile_cascade.empty():
                raise IOError("Cascade files are empty")
            logger.info("Haar cascades loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load cascades: {e}. Face detection disabled.")
            _face_cascade = None
            _profile_cascade = None
    return _face_cascade, _profile_cascade


# ────────────────────────────────────────────────────────────────────────────
# Data classes
# ────────────────────────────────────────────────────────────────────────────
# eq=False so that equality is identity-based — this avoids triggering numpy
# array element-wise comparison (which raises ValueError in list.index() etc.)
@dataclass(eq=False)
class Candidate:
    """A scored video frame candidate.

    ``frame_bgr`` may be ``None`` if the frame has been released to free
    memory — use :meth:`ensure_frame` to access it safely (it will be
    re-fetched from ``video_path`` at ``timestamp`` on demand).
    """
    frame_bgr: Optional[np.ndarray]
    timestamp: float
    total_score: float
    breakdown: Dict[str, float]
    faces: List[Tuple[int, int, int, int]] = field(default_factory=list)
    starred: bool = False
    video_path: Optional[str] = None
    # Cached colour histogram for ``filter_similar`` (lazy-computed)
    _hist: Optional[np.ndarray] = field(default=None, repr=False)
    # Cached edge-orientation histogram for ``filter_similar`` (lazy-computed)
    _edge_hist_cache: Optional[np.ndarray] = field(default=None, repr=False)
    # Motion magnitude (set by AnalysisThread when temporal context available)
    motion_magnitude: float = 0.0

    @property
    def hist(self) -> np.ndarray:
        if self._hist is None:
            frame = self.ensure_frame()
            if frame is None:
                return np.zeros(200, dtype=np.float32)
            self._hist = _color_hist(frame)
        return self._hist

    def ensure_frame(self) -> Optional[np.ndarray]:
        """Return the BGR frame, re-fetching from disk if it was released."""
        if self.frame_bgr is not None:
            return self.frame_bgr
        if not self.video_path or self.timestamp < 0:
            return None
        # Lazy import to avoid circular dependency
        frame = FRAME_STORE.get(self.video_path, self.timestamp)
        if frame is not None:
            self.frame_bgr = frame
        return frame

    def release_frame(self) -> None:
        """Drop the in-memory frame to free RAM. ``ensure_frame`` can re-fetch."""
        self.frame_bgr = None
        self._hist = None  # histogram depends on the frame; force re-compute
        self._edge_hist_cache = None  # edge hist also depends on the frame


# ────────────────────────────────────────────────────────────────────────────
# Pre-filter (cheap reject pass)
# ────────────────────────────────────────────────────────────────────────────
def prefilter_frame(bgr: np.ndarray) -> bool:
    """Reject frames that are too dark, too bright, too flat, or too blurred.

    Uses multi-criteria checks:
      1. Mean brightness in [18, 242] — rejects pure black/white frames.
      2. Percentile spread (p10–p90) > 25 — rejects near-uniform frames
         that have a narrow histogram (e.g. solid colour walls, fog).
      3. Per-channel standard deviation — rejects monochrome/desaturated
         frames where at least 2 colour channels are essentially flat.
      4. Laplacian variance > 12 — rejects completely defocused / motion-
         blurred frames (slightly lower threshold than before to reduce
         false negatives on portrait-style soft backgrounds).
    """
    if bgr is None or bgr.size == 0:
        return False
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    m = float(np.mean(gray))
    if m < 18 or m > 242:
        return False
    # Percentile spread — catches flat frames that have OK mean but no tonal range
    p_lo, p_hi = np.percentile(gray, [10, 90])
    if (p_hi - p_lo) < 25:
        return False
    # Per-channel flatness: reject if 2+ channels have std < 8
    channel_stds = [float(np.std(bgr[:, :, c])) for c in range(3)]
    flat_channels = sum(1 for s in channel_stds if s < 8)
    if flat_channels >= 2:
        return False
    # Blur check
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if lap_var < 12:
        return False
    return True


# ────────────────────────────────────────────────────────────────────────────
# Helper: atan soft-saturation  (maps x ∈ [0, ∞) → [0, 1] smoothly)
# ────────────────────────────────────────────────────────────────────────────
def _atan_sat(x: float, scale: float = 1.0, offset: float = 0.0) -> float:
    r"""Smooth saturation using arctangent.

    .. math::
        f(x) = \frac{2}{\pi} \arctan\!\left(\frac{x + \text{offset}}{\text{scale}}\right)

    Parameters
    ----------
    x : float   — input value (must be >= 0)
    scale : float — controls how quickly the curve approaches 1.0
    offset : float — shifts the curve left/right (useful for dead-zone)
    """
    return float((2.0 / math.pi) * math.atan((max(0.0, x) + offset) / scale))


# ────────────────────────────────────────────────────────────────────────────
# Face detection (called separately from SCORERS because it operates on
# the full-res frame, not the downscaled version)
# ────────────────────────────────────────────────────────────────────────────
def score_faces(bgr: np.ndarray) -> Tuple[float, List[Tuple[int, int, int, int]]]:
    """Detect faces and score centrality + size of the largest one.

    Uses Haar cascades with a two-pass approach: first tries the frontal face
    detector, then falls back to the profile face detector.  The score
    combines three components:
      1. Base score for having at least one face (0.4).
      2. Centrality bonus: Gaussian falloff from the image centre.
      3. Size bonus: faces occupying 5-50 % of the frame area.
    """
    fc, pc = _get_cascades()
    if fc is None or fc.empty():
        return 0.0, []

    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = fc.detectMultiScale(g, 1.2, 5, minSize=(40, 40))
    if len(faces) == 0 and pc and not pc.empty():
        faces = pc.detectMultiScale(g, 1.2, 5, minSize=(40, 40))
    if len(faces) == 0:
        return 0.0, []

    H, W = bgr.shape[:2]
    largest = max(faces, key=lambda r: r[2] * r[3])
    fx = (largest[0] + largest[2] / 2) / W
    fy = (largest[1] + largest[3] / 2) / H
    dist = math.sqrt((fx - 0.5) ** 2 + (fy - 0.5) ** 2)
    center_bonus = max(0.0, 0.4 * (1 - dist * 2))
    area_ratio = (largest[2] * largest[3]) / (H * W)
    size_bonus = 0.2 if 0.05 < area_ratio < 0.5 else 0.0
    return min(0.4 + center_bonus + size_bonus, 1.0), [tuple(int(v) for v in f) for f in faces]


# ────────────────────────────────────────────────────────────────────────────
# Scoring functions — each returns a float in [0, 1]
# ────────────────────────────────────────────────────────────────────────────

def score_sharpness(gray: np.ndarray) -> float:
    """Tenengrad + Laplacian fusion with noise-aware normalisation.

    Uses the **Tenengrad** metric (gradient magnitude via Sobel) combined
    with the variance of the Laplacian.  The harmonic mean of the two
    gives robustness against noise: the Laplacian is sensitive to high-
    frequency noise while Tenengrad emphasises strong directional edges.

    Normalisation uses :func:`_atan_sat` so the mapping saturates
    smoothly rather than clamping abruptly at 1.0.

    References
    ----------
    * Krotkov, E. (1988). *Focusing*.  International Journal of Computer
      Vision, 1(3), 223–237.  — Tenengrad criterion.
    * Pech-Pacheco et al. (2000). *Diatom autofocusing in brightfield
      microscopy*.  Pattern Recognition, 1109–1115.
    """
    if gray is None or gray.size == 0:
        return 0.0
    # Tenengrad: mean of Sobel gradient magnitudes
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    tenengrad = float(np.mean(gx * gx + gy * gy))
    # Laplacian variance
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    # Normalise each independently, then combine via harmonic mean
    t_norm = _atan_sat(tenengrad / 1000.0, scale=0.55)
    l_norm = _atan_sat(lap_var / 100.0, scale=0.50)
    # Harmonic mean penalises cases where one metric is very low
    if t_norm + l_norm < 1e-9:
        return 0.0
    return float(2.0 * t_norm * l_norm / (t_norm + l_norm))


def score_contrast(gray: np.ndarray) -> float:
    r"""RMS contrast with perceptual weighting.

    RMS (root-mean-square) contrast is defined as:

    .. math::
        C_{\text{rms}} = \sqrt{\frac{1}{N}\sum_{i}(I_i - \bar{I})^2}

    This is equivalent to the standard deviation of pixel intensities,
    but we normalise differently than a raw ``std / 60``.  We use
    :func:`_atan_sat` with a small offset so that even moderate contrast
    images (std ≈ 30–40) get partial credit, while high-contrast images
    approach 1.0 smoothly.

    Additionally, we apply a **Weber-like** local contrast measure:
    the average absolute difference between each pixel and its local
    mean (computed via Gaussian blur at two scales).  This captures
    texture contrast that global RMS misses.
    """
    if gray is None or gray.size == 0:
        return 0.0
    std_val = float(np.std(gray))
    # Global RMS component
    rms_score = _atan_sat(std_val / 40.0, scale=0.45, offset=0.10)
    # Local Weber-like contrast at two Gaussian scales
    blur_fine = cv2.GaussianBlur(gray, (7, 7), 1.5)
    blur_coarse = cv2.GaussianBlur(gray, (21, 21), 5.0)
    local_diff = float(np.mean(np.abs(gray.astype(np.float64) - blur_fine.astype(np.float64))))
    coarse_diff = float(np.mean(np.abs(gray.astype(np.float64) - blur_coarse.astype(np.float64))))
    local_score = _atan_sat(local_diff / 15.0, scale=0.50)
    coarse_score = _atan_sat(coarse_diff / 25.0, scale=0.50)
    # Weighted combination (global 40%, fine local 35%, coarse local 25%)
    return float(0.40 * rms_score + 0.35 * local_score + 0.25 * coarse_score)


def score_brightness(gray: np.ndarray) -> float:
    r"""Asymmetric Gaussian brightness preference.

    Thumbnail images tend to look more appealing when they are slightly
    **over-exposed** (brighter) rather than under-exposed, because
    small preview sizes lose shadow detail.  We model this with a
    skewed Gaussian centred at 135 (slightly above mid-gray 128).

    .. math::
        f(\mu) = \exp\!\left(-\frac{(\mu - 135)^2}{2 \cdot 55^2}\right)
                 \;\cdot\; (1 + 0.15 \cdot \text{softplus}(\mu - 128))

    The ``softplus`` term gently boosts frames with mean > 128 by up
    to ~15 %, tapering off smoothly for very bright frames.
    """
    if gray is None or gray.size == 0:
        return 0.0
    mu = float(np.mean(gray))
    # Gaussian centred slightly above mid-gray
    gauss = math.exp(-0.5 * ((mu - 135.0) / 55.0) ** 2)
    # Asymmetric boost for brighter frames (softplus-like)
    bright_boost = 1.0 + 0.15 * math.log1p(math.exp((mu - 128.0) / 20.0))
    return float(min(gauss * min(bright_boost, 1.15), 1.0))


def score_entropy(gray: np.ndarray) -> float:
    r"""Shannon entropy of the grayscale intensity histogram.

    Higher entropy indicates that the frame carries more information
    (more distinct intensity levels are represented).  We compute
    the normalised histogram with 256 bins and then:

    .. math::
        H = -\sum_{i=0}^{255} p_i \log_2 p_i, \qquad
        H_{\text{norm}} = \frac{H}{\log_2 256} = \frac{H}{8}

    We apply a gentle sigmoid-like boost to the mid-range so that
    frames with moderate entropy (4–6 bits) are not unduly penalised
    compared to near-maximal entropy (7–8 bits).
    """
    if gray is None or gray.size == 0:
        return 0.0
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    total = hist.sum()
    if total < 1:
        return 0.0
    p = hist / total
    # Ignore zero-probability bins
    p_nonzero = p[p > 0]
    H = float(-np.sum(p_nonzero * np.log2(p_nonzero)))
    H_norm = H / 8.0  # normalise to [0, 1]
    return float(min(_atan_sat(H_norm, scale=0.40, offset=0.05), 1.0))


def score_exposure_quality(bgr: np.ndarray, gray: Optional[np.ndarray] = None) -> float:
    r"""Evaluate how well-exposed a frame is based on histogram shape.

    An ideally exposed frame has:
      * Minimal clipping at either end (shadows or highlights).
      * A well-spread histogram with no large gaps.
      * A roughly bell-shaped distribution (not bimodal or heavily
        skewed).

    We compute three sub-scores and combine them:

    1. **Clipping penalty**: fraction of pixels in the bottom 2 % and
       top 2 % of the intensity range.  Penalises hard clipping.
    2. **Spread score**: inter-percentile range (2nd–98th) normalised
       to [0, 255].
    3. **Shape score**: kurtosis of the histogram — a moderate kurtosis
       (peaked-but-not-too-narrow) indicates good exposure.  We use
       a Gaussian preference around a target kurtosis.

    The final score is the geometric mean of the three, which ensures
    that a failure in any single criterion significantly lowers the
    result.
    """
    if bgr is None or bgr.size == 0:
        return 0.0
    if gray is None:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    total = hist.sum()
    if total < 1:
        return 0.0
    p = hist / total

    # 1. Clipping penalty: fraction in bottom 2% and top 2%
    shadow_clip = float(np.sum(p[:5]))   # pixels 0–4
    highlight_clip = float(np.sum(p[251:]))  # pixels 251–255
    clip_score = max(0.0, 1.0 - (shadow_clip + highlight_clip) * 10.0)

    # 2. Spread: 2nd–98th percentile range
    cdf = np.cumsum(p)
    p2 = float(np.searchsorted(cdf, 0.02))
    p98 = float(np.searchsorted(cdf, 0.98))
    spread = (p98 - p2) / 255.0
    spread_score = _atan_sat(spread, scale=0.45, offset=0.05)

    # 3. Shape: compute kurtosis directly from the histogram (no array expansion)
    bins = np.arange(256, dtype=np.float64)
    mu = float(np.sum(bins * p))
    if mu < 1e-9:
        shape_score = 0.3
    else:
        var = float(np.sum(((bins - mu) ** 2) * p))
        if var < 1e-9:
            shape_score = 0.3
        else:
            m4 = float(np.sum(((bins - mu) ** 4) * p))
            kurt = m4 / (var ** 2) - 3.0  # excess kurtosis
            # Moderate positive kurtosis (1–4) is ideal; penalise very flat (negative)
            # or extremely peaked (>8)
            shape_score = math.exp(-0.5 * ((kurt - 2.5) / 4.0) ** 2)

    # Geometric mean of the three (with floor to avoid zero)
    result = (clip_score * spread_score * shape_score) ** (1.0 / 3.0)
    return float(min(result, 1.0))


def score_composition(bgr: np.ndarray, gray: Optional[np.ndarray] = None) -> float:
    """Gaussian-weighted rule-of-thirds + visual center-of-mass.

    Instead of flat rectangular bands at the third-lines (which give
    equal weight to uninteresting content along the entire band), we
    place 2D **Gaussian blobs** at the four **power points** (the
    intersections of the third-lines).  Each blob has σ proportional
    to the image size, so the influence region is well-scaled.

    We also add secondary Gaussians at the **golden ratio** points
    (≈ 0.382 and ≈ 0.618) which are slightly inside the third-lines,
    and a small **centre bonus** because thumbnails viewed at small
    size benefit from central subject placement.

    The final score blends:
      * Edge density at power points (60 %)
      * Edge density at golden-ratio points (20 %)
      * Centre-of-mass proximity to image centre (20 %)
    """
    if bgr is None or bgr.size == 0:
        return 0.0
    H, W = bgr.shape[:2]
    if gray is None:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150).astype(np.float64) / 255.0

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)

    def _gauss_score(cx: float, cy: float, sigma_x: float, sigma_y: float) -> float:
        """Weighted edge density under a 2D Gaussian at (cx, cy)."""
        g = np.exp(-0.5 * (((xx / W - cx) / sigma_x) ** 2 +
                           ((yy / H - cy) / sigma_y) ** 2))
        return float(np.sum(edges * g))

    sx, sy = 0.09, 0.09  # sigma in normalised coordinates

    # Rule-of-thirds power points (4 intersections)
    third_score = sum(
        _gauss_score(fx, fy, sx, sy)
        for fx in (1 / 3, 2 / 3) for fy in (1 / 3, 2 / 3)
    )
    # Golden ratio points (4 points, slightly inward)
    golden_score = sum(
        _gauss_score(fx, fy, sx * 0.8, sy * 0.8)
        for fx in (0.382, 0.618) for fy in (0.382, 0.618)
    )

    # Normalise each by the maximum possible (all pixels on edge, under Gaussian)
    area = H * W
    g_sum = float(np.exp(-0.5 * 0)) * area  # peak * area (approx)
    third_n = _atan_sat(third_score / (g_sum * 0.05), scale=0.45)
    golden_n = _atan_sat(golden_score / (g_sum * 0.05), scale=0.45)

    # Centre-of-mass of edge energy — how close is it to the image centre?
    total_edge = edges.sum() + 1e-9
    com_x = float((edges * xx).sum() / total_edge) / W
    com_y = float((edges * yy).sum() / total_edge) / H
    com_dist = math.sqrt((com_x - 0.5) ** 2 + (com_y - 0.5) ** 2)
    # Use maximum possible distance (√0.5 ≈ 0.707) for normalisation
    com_score = max(0.0, 1.0 - com_dist / 0.5)

    return float(min(0.55 * third_n + 0.20 * golden_n + 0.25 * com_score, 1.0))


def score_dynamic_range(bgr: np.ndarray, gray: Optional[np.ndarray] = None) -> float:
    r"""Robust dynamic range via percentile spread + histogram gap analysis.

    .. math::
        R = \frac{P_{99} - P_1}{255}

    We use the 1st and 99th percentiles (instead of 5th/95th) for better
    robustness against outliers.  The raw range is passed through
    :func:`_atan_sat` for smooth saturation.

    Additionally, we compute the **histogram gap ratio**: the fraction
    of intensity bins (out of 256) that have zero count.  A high gap
    ratio indicates posterisation or quantisation artefacts, which
    should be penalised.
    """
    if bgr is None or bgr.size == 0:
        return 0.0
    if gray is None:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    p_lo, p_hi = float(np.percentile(gray, 1)), float(np.percentile(gray, 99))
    range_score = _atan_sat((p_hi - p_lo) / 255.0, scale=0.40, offset=0.05)
    # Histogram gap ratio — penalise posterisation
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    total_pixels = hist.sum()
    if total_pixels > 0:
        gap_ratio = float(np.sum(hist == 0)) / 256.0
        gap_penalty = 1.0 - 0.3 * gap_ratio  # max 30% penalty
    else:
        gap_penalty = 0.5
    return float(min(range_score * gap_penalty, 1.0))


def score_colorfulness(bgr: np.ndarray) -> float:
    r"""Hasler & Süsstrunk (2003) colourfulness metric.

    The classic image colourfulness measure uses opponent colour channels:

    .. math::
        \text{rg} = R - G, \qquad
        \text{yb} = \frac{1}{2}(R + G) - B

    .. math::
        C = \sqrt{\sigma_{\text{rg}}^2 + \sigma_{\text{yb}}^2}
          + 0.3 \sqrt{\mu_{\text{rg}}^2 + \mu_{\text{yb}}^2}

    The first term captures the *spread* of colour differences while
    the second captures the *bias* (dominant colour cast).  We
    normalise by a calibrated factor ( empirically ≈ 150 for well-
    saturated natural images downsampled to ~720px) and use atan
    saturation.

    Reference
    ---------
    Hasler, D. & Süsstrunk, S. (2003).  *Measuring colourfulness in
    natural images*.  Proc. SPIE 5007, Human Vision and Electronic
    Imaging VIII.
    """
    if bgr is None or bgr.size == 0:
        return 0.0
    # Convert BGR → RGB float
    rgb = bgr[:, :, ::-1].astype(np.float64)
    rg = rgb[:, :, 0] - rgb[:, :, 1]  # R - G
    yb = 0.5 * (rgb[:, :, 0] + rgb[:, :, 1]) - rgb[:, :, 2]  # 0.5(R+G) - B
    std_rg, std_yb = float(np.std(rg)), float(np.std(yb))
    mean_rg, mean_yb = float(np.mean(rg)), float(np.mean(yb))
    C = math.sqrt(std_rg ** 2 + std_yb ** 2) + 0.3 * math.sqrt(mean_rg ** 2 + mean_yb ** 2)
    return float(min(_atan_sat(C / 100.0, scale=0.45, offset=0.02), 1.0))


def score_visual_complexity(bgr: np.ndarray, gray: Optional[np.ndarray] = None) -> float:
    """Edge density + gradient orientation entropy.

    Visual complexity measures how much "stuff" is happening in the
    frame.  We combine two signals:

    1. **Edge density**: the fraction of pixels that are detected as
       edges by Canny.  Very dense edges indicate complex scenes.
    2. **Gradient orientation entropy**: compute Sobel gradients, bin
       the orientations into 12 angular bins (0°–180°, since gradient
       direction is modulo 180°), and compute Shannon entropy.  High
       orientation entropy means edges point in many different
       directions — a hallmark of complex, natural imagery.
    """
    if bgr is None or bgr.size == 0:
        return 0.0
    if gray is None:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape[:2]
    area = H * W

    # Edge density
    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.count_nonzero(edges)) / area
    density_score = _atan_sat(edge_density * 3.0, scale=0.40, offset=0.02)

    # Gradient orientation entropy
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(gx ** 2 + gy ** 2)
    # Only consider significant gradient pixels (magnitude > threshold)
    mask = mag > 10.0
    if mask.sum() < 10:
        return density_score  # fall back to just edge density
    angles = np.arctan2(gy[mask], gx[mask])  # range [-π, π]
    # Map to [0, π) since gradient direction is undirected
    angles = np.mod(angles, np.pi)
    n_bins = 12
    hist, _ = np.histogram(angles, bins=n_bins, range=(0, np.pi))
    p = hist / hist.sum()
    p_nz = p[p > 0]
    orient_entropy = float(-np.sum(p_nz * np.log2(p_nz)))
    orient_norm = orient_entropy / math.log2(n_bins)  # normalise to [0, 1]

    return float(min(0.55 * density_score + 0.45 * orient_norm, 1.0))


def score_color_harmony(bgr: np.ndarray) -> float:
    r"""HSV hue coherence weighted by saturation.

    Colour harmony is assessed by analysing the distribution of hues
    in the image, weighted by saturation (unsaturated pixels carry no
    colour information and should not influence the score).

    We compute the **circular variance** of the hue distribution:

    .. math::
        V_c = 1 - \frac{|\sum_k w_k e^{i \theta_k}|}{\sum_k w_k}

    where θ_k are hue angles and w_k are pixel saturation weights.
    Low circular variance means colours are clustered → more harmonious.

    Additionally, we check for common harmony patterns:
      * **Analogous**: hues within a 60° arc
      * **Complementary**: two hue clusters ~180° apart
      * **Triadic**: three hue clusters ~120° apart

    The final score blends circular coherence (50 %) with pattern
    detection (50 %).
    """
    if bgr is None or bgr.size == 0:
        return 0.0
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float64)
    hue = hsv[:, :, 0] / 180.0 * np.pi  # [0, π) for OpenCV's half-circle
    sat = hsv[:, :, 1] / 255.0

    # Only consider pixels with meaningful saturation (> 15 %)
    mask = sat > 0.15
    if mask.sum() < 20:
        return 0.5  # neutral image — neither harmonious nor disharmonious

    hues = hue[mask]
    weights = sat[mask]

    # Circular mean and variance
    w_sum = weights.sum()
    if w_sum < 1e-9:
        return 0.5
    # Convert to complex exponentials for circular statistics
    cos_sum = float(np.sum(weights * np.cos(2 * hues))) / w_sum
    sin_sum = float(np.sum(weights * np.sin(2 * hues))) / w_sum
    resultant_length = math.sqrt(cos_sum ** 2 + sin_sum ** 2)
    circular_var = 1.0 - resultant_length  # 0 = all same hue, 1 = uniform
    coherence_score = 1.0 - circular_var  # high = harmonious

    # Pattern detection via hue histogram
    n_bins = 36
    hist, _ = np.histogram(hues, bins=n_bins, range=(0, np.pi), weights=weights)
    hist_norm = hist / (hist.sum() + 1e-9)

    # Find peaks (local maxima above 5% weight)
    peaks = []
    for i in range(n_bins):
        prev_bin = hist_norm[(i - 1) % n_bins]
        curr_bin = hist_norm[i]
        next_bin = hist_norm[(i + 1) % n_bins]
        if curr_bin > prev_bin and curr_bin > next_bin and curr_bin > 0.05:
            peaks.append((i / n_bins * np.pi, curr_bin))

    pattern_score = 0.5  # baseline
    if len(peaks) >= 2:
        # Check for complementary (2 peaks ~π/2 apart on half-circle)
        for i in range(len(peaks)):
            for j in range(i + 1, len(peaks)):
                ang_diff = abs(peaks[i][0] - peaks[j][0])
                ang_diff = min(ang_diff, np.pi - ang_diff)
                # Complementary
                if abs(ang_diff - np.pi / 2) < np.pi / 8:
                    strength = min(peaks[i][1], peaks[j][1])
                    pattern_score = max(pattern_score, 0.6 + 0.3 * strength)
                # Analogous (within 30°)
                if ang_diff < np.pi / 6:
                    strength = peaks[i][1] + peaks[j][1]
                    pattern_score = max(pattern_score, 0.6 + 0.25 * strength)
    if len(peaks) == 1:
        # Single dominant hue — monochromatic harmony
        pattern_score = max(pattern_score, 0.5 + 0.3 * peaks[0][1])

    return float(min(0.50 * coherence_score + 0.50 * pattern_score, 1.0))


def score_center_weight(bgr: np.ndarray, gray: Optional[np.ndarray] = None) -> float:
    """Visual saliency centre-weighting.

    Measures how much visually important content (edges, saturated
    colours, skin tones) is concentrated in the **centre** of the
    frame versus the **periphery**.  A Gaussian radial weight map
    (σ = 0.35 of half-dimension) emphasises the centre region.

    The saliency map is computed as:
      * Edge energy (Sobel magnitude)
      * Saturation weight (from HSV)
    These are combined and compared against the radial weight map
    using a cosine-similarity-like dot-product measure.
    """
    if bgr is None or bgr.size == 0:
        return 0.0
    H, W = bgr.shape[:2]
    if gray is None:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Edge energy
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    edge_energy = np.sqrt(gx ** 2 + gy ** 2)

    # Saturation weight
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float64)
    sat_weight = hsv[:, :, 1] / 255.0

    # Combined saliency: modulate edge energy by saturation
    sat_2d = sat_weight if sat_weight.ndim == 2 else sat_weight.squeeze()
    saliency = edge_energy * (0.5 + 0.5 * sat_2d)
    # Normalise saliency
    s_max = saliency.max()
    if s_max > 1e-9:
        saliency = saliency / s_max

    # Gaussian radial weight map (centred, σ ≈ 35% of half-dimension)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    cx, cy = W / 2.0, H / 2.0
    sigma = min(W, H) * 0.35
    radial = np.exp(-0.5 * ((xx - cx) ** 2 + (yy - cy) ** 2) / (sigma ** 2))

    # Weighted centre score: dot product of saliency and radial weight
    s_flat = saliency.flatten()
    r_flat = radial.flatten()
    s_norm = np.linalg.norm(s_flat) + 1e-9
    r_norm = np.linalg.norm(r_flat) + 1e-9
    cos_sim = float(np.dot(s_flat, r_flat) / (s_norm * r_norm))

    # Also compute a simple centre-ring ratio for robustness
    center_mask = ((xx - cx) ** 2 + (yy - cy) ** 2) < (sigma * 1.2) ** 2
    center_sal = float(saliency[center_mask].mean()) if center_mask.any() else 0.0
    periphery_sal = float(saliency[~center_mask].mean()) if (~center_mask).any() else 0.0
    ratio = (center_sal + 1e-9) / (center_sal + periphery_sal + 1e-9)

    return float(min(0.55 * max(cos_sim, 0.0) + 0.45 * _atan_sat(ratio, scale=0.60), 1.0))


def score_skin_tone(bgr: np.ndarray) -> float:
    """Skin-tone detection in YCbCr + HSV with centre weighting.

    Uses the well-established **YCbCr** skin model (Chai & Ngan, 1999)
    combined with an HSV sanity check.  A pixel is classified as skin
    if it satisfies:

    **YCbCr**:  80 ≤ Cb ≤ 120  and  133 ≤ Cr ≤ 173
    **HSV**:    0 ≤ H ≤ 50    and  20 ≤ S ≤ 80%  and  V ≥ 40

    The score is based on the fraction of skin pixels, with a bonus
    for skin pixels located in the centre half of the frame.
    """
    if bgr is None or bgr.size == 0:
        return 0.0
    H, W = bgr.shape[:2]
    area = H * W
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # YCbCr skin model
    cb = ycrcb[:, :, 1]
    cr = ycrcb[:, :, 2]
    skin_ycrcb = (cb >= 80) & (cb <= 120) & (cr >= 133) & (cr <= 173)

    # HSV refinement (exclude false positives from brownish/greenish objects)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    skin_hsv = (h <= 50) & (s >= 20) & (s <= 204) & (v >= 40) & (v <= 255)

    # Intersection of both models
    skin_mask = skin_ycrcb & skin_hsv
    skin_fraction = float(skin_mask.sum()) / area

    # Centre weighting: bonus for skin in centre half
    cy, cx = H // 2, W // 2
    centre_mask = np.zeros_like(skin_mask)
    centre_mask[cy - H // 4:cy + H // 4, cx - W // 4:cx + W // 4] = True
    centre_skin = float((skin_mask & centre_mask).sum()) / (area * 0.25 + 1e-9)

    # Skin fraction score (atan saturation with offset)
    frac_score = _atan_sat(skin_fraction * 5.0, scale=0.45, offset=0.01)
    # Centre bonus (only if there's meaningful skin)
    centre_score = _atan_sat(centre_skin * 3.0, scale=0.45) if skin_fraction > 0.02 else 0.0

    return float(min(0.60 * frac_score + 0.40 * centre_score, 1.0))


def _color_hist(bgr: np.ndarray) -> np.ndarray:
    """Compute a small HSV colour histogram for similarity comparisons."""
    if bgr is None or bgr.size == 0:
        return np.zeros(200, dtype=np.float32)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [20, 10], [0, 180, 0, 256]).flatten()
    return h / (h.sum() + 1e-8)


def _edge_hist(gray: np.ndarray, n_bins: int = 16) -> np.ndarray:
    """Compute a lightweight edge-orientation histogram for structural similarity."""
    if gray is None or gray.size == 0:
        return np.zeros(n_bins, dtype=np.float32)
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(gx ** 2 + gy ** 2)
    angles = np.arctan2(gy, gx)  # [-π, π]
    # Only use significant edges
    mask = mag > 15.0
    if mask.sum() < 5:
        return np.zeros(n_bins, dtype=np.float32)
    angles = np.mod(angles[mask], np.pi)  # [0, π)
    weights = mag[mask]
    hist, _ = np.histogram(angles, bins=n_bins, range=(0, np.pi), weights=weights)
    total = hist.sum()
    if total > 0:
        hist = hist / total
    return hist.astype(np.float32)


def score_motion(gray: np.ndarray, prev_gray: Optional[np.ndarray] = None) -> float:
    r"""Frame-to-frame motion via optical flow magnitude.

    Uses the Farneback dense optical flow algorithm to estimate per-pixel
    motion between the current and previous frame.  The score is the
    mean flow magnitude, normalised with atan saturation so that
    moderate motion scores well while near-static frames score low.

    When ``prev_gray`` is ``None`` (e.g. first frame or no temporal
    context), returns 0.0.
    """
    if prev_gray is None or gray is None or gray.size == 0:
        return 0.0
    try:
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, gray, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=2, poly_n=5, poly_sigma=1.2, flags=0,
        )
        mag = np.sqrt(flow[:, :, 0] ** 2 + flow[:, :, 1] ** 2)
        mean_mag = float(np.mean(mag))
        # Typical thumbnails: slight motion (mean_mag ~1-3) is good,
        # excessive motion (>10) means blur.  atan_sat maps this to [0,1].
        return float(_atan_sat(mean_mag / 4.0, scale=0.45, offset=0.05))
    except Exception:
        return 0.0


# Scorers registry — each scorer takes (bgr_small, gray_small) for max reuse.
ScorerFn = Callable[[np.ndarray, np.ndarray], float]
SCORERS: Dict[str, ScorerFn] = {
    "sharpness":         lambda f, g: score_sharpness(g),
    "contrast":          lambda f, g: score_contrast(g),
    "brightness":        lambda f, g: score_brightness(g),
    "composition":       lambda f, g: score_composition(f, g),
    "motion":            lambda f, g: 0.0,       # set dynamically in _score_samples
    "dynamic_range":     lambda f, g: score_dynamic_range(f, g),
    "colorfulness":      lambda f, g: score_colorfulness(f),
    "exposure_quality":  lambda f, g: score_exposure_quality(f, g),
    "visual_complexity": lambda f, g: score_visual_complexity(f, g),
    "color_harmony":     lambda f, g: score_color_harmony(f),
    "center_weight":     lambda f, g: score_center_weight(f, g),
    "skin_tone":         lambda f, g: score_skin_tone(f),
    "entropy":           lambda f, g: score_entropy(g),
}


def _normalize_scores(cands: List[Candidate]) -> List[Candidate]:
    """Min-max normalize each criterion's scores across all candidates.

    For each criterion key present in any candidate's breakdown, compute
    the min and max across all candidates, then linearly remap to [0, 1].
    Criteria with zero range (all identical) are left unchanged.
    """
    if len(cands) < 2:
        return cands
    # Collect all keys and their min/max
    all_keys: set = set()
    for c in cands:
        all_keys.update(c.breakdown.keys())
    ranges: Dict[str, Tuple[float, float]] = {}
    for key in all_keys:
        vals = [c.breakdown.get(key, 0.0) for c in cands]
        lo, hi = min(vals), max(vals)
        ranges[key] = (lo, hi)
    # Apply normalization
    for c in cands:
        for key, (lo, hi) in ranges.items():
            if key in c.breakdown and hi > lo:
                c.breakdown[key] = (c.breakdown[key] - lo) / (hi - lo)
    return cands


def filter_similar(cands: List[Candidate], threshold: float = 0.85) -> List[Candidate]:
    """Greedy dedupe combining colour-histogram and edge-structure correlation.

    Uses cached edge histograms (``_edge_hist_cache``) on each Candidate
    so the structural histogram is computed at most once per candidate
    instead of once per comparison pair.  This reduces the complexity
    from O(n^2 * frame_cost) to O(n^2 * hist_compare_cost).
    """
    if len(cands) <= 1:
        return cands
    kept: List[Candidate] = [cands[0]]
    struct_threshold = threshold * 0.90

    # Pre-compute edge histograms for all candidates (one cvtColor + Sobel each)
    for c in cands:
        if c._edge_hist_cache is None:
            frame = c.ensure_frame()
            if frame is not None:
                gray_c = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                c._edge_hist_cache = _edge_hist(gray_c)
            else:
                c._edge_hist_cache = np.zeros(16, dtype=np.float32)

    for c in cands[1:]:
        h = c.hist
        eh_c = c._edge_hist_cache
        is_similar = False
        for k in kept:
            color_sim = cv2.compareHist(h, k.hist, cv2.HISTCMP_CORREL)
            if color_sim < threshold:
                continue
            # Use cached edge histogram (no re-computation)
            struct_sim = 1.0 - cv2.compareHist(eh_c, k._edge_hist_cache, cv2.HISTCMP_BHATTACHARYYA)
            if struct_sim > struct_threshold:
                is_similar = True
                break
        if not is_similar:
            kept.append(c)
    return kept


# ────────────────────────────────────────────────────────────────────────────
# Per-frame worker
# ────────────────────────────────────────────────────────────────────────────
def _process_single_frame(path: str, t: float, weights: Dict[str, float],
                           get_cap=None, return_cap=None) -> Optional[Candidate]:
    """Open ``path``, seek to ``t`` seconds, score the frame, return a Candidate.

    If ``get_cap`` / ``return_cap`` callables are provided, they are used
    to borrow and return a pooled VideoCapture (avoids per-frame open/close).
    """
    if get_cap is not None:
        cap = get_cap()
    else:
        cap = cv2.VideoCapture(path)
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, frame = cap.read()
        if not ret or frame is None:
            return None
        if not prefilter_frame(frame):
            return None

        face_score, faces = score_faces(frame)

        small, gray = downscale_for_scoring(frame, SCORING_MAX_DIMENSION)
        scores: Dict[str, float] = {name: fn(small, gray) for name, fn in SCORERS.items()}
        scores["faces"] = face_score

        total = sum(scores.get(k, 0.0) * w for k, w in weights.items())
        return Candidate(frame_bgr=frame, timestamp=float(t),
                         total_score=total, breakdown=scores, faces=faces,
                         video_path=path)
    except Exception as e:
        logging.error(f"Worker error at t={t:.2f}s: {e}")
        return None
    finally:
        if return_cap is not None:
            return_cap(cap)
        else:
            cap.release()


def _grab_filmstrip_frame(path: str, t: float, thumb_h: int) -> Optional[Tuple[float, np.ndarray]]:
    """Open ``path``, seek to ``t``, return a small BGR thumbnail."""
    cap = cv2.VideoCapture(path)
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, f = cap.read()
        if not ret or f is None:
            return None
        new_w = max(1, int(f.shape[1] * thumb_h / f.shape[0]))
        thumb = cv2.resize(f, (new_w, thumb_h), interpolation=cv2.INTER_AREA)
        return (t, thumb)
    except Exception:
        return None
    finally:
        cap.release()


# ────────────────────────────────────────────────────────────────────────────
# Analysis thread
# ────────────────────────────────────────────────────────────────────────────
class AnalysisThread(QThread):
    """Background worker that scans a video, scores sample frames, and emits
    incremental progress + candidate signals to the UI."""

    progress = Signal(int, int)
    stage_changed = Signal(str)
    finished_ok = Signal(list, dict)
    finished_err = Signal(str)
    candidate_ready = Signal(object, int, int)
    filmstrip_ready = Signal(list)

    def __init__(self, path: str, n_samples: int, weights: Dict[str, float],
                 n_cands: int, use_scene: bool,
                 max_workers: Optional[int] = None,
                 sample_times_override: Optional[List[float]] = None,
                 skip_filmstrip: bool = False) -> None:
        super().__init__()
        self.path = path
        self.n_samples = n_samples
        self.weights = weights
        self.n_cands = n_cands
        self.use_scene = use_scene
        self._max_workers = max_workers or (os.cpu_count() or 4)
        self._abort = False
        self._sample_times_override = sample_times_override
        self._skip_filmstrip = skip_filmstrip

    # -- public control ----------------------------------------------------
    def abort(self) -> None:
        self._abort = True

    # -- main entry --------------------------------------------------------
    def run(self) -> None:
        logger.info(f"Starting PARALLEL analysis for: {self.path}")
        cap = cv2.VideoCapture(self.path)
        if not cap.isOpened():
            self.finished_err.emit("Cannot open video file.")
            return

        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            dur = total_frames / fps if fps > 0 else 0.0
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()

            if dur <= 0:
                self.finished_err.emit("Video has zero duration.")
                return

            logger.info(f"Video Info: {w}x{h} @ {fps:.2f}fps, Duration: {dur:.2f}s")

            # ---- 1. FILMSTRIP (parallel) ----
            n_strip = 0
            if not self._skip_filmstrip:
                self.stage_changed.emit("Phase 1: Scanning video")
                filmstrip = self._build_filmstrip(dur)
                if self._abort:
                    return
                self.filmstrip_ready.emit(filmstrip)
                n_strip = len(filmstrip)
                logger.info(f"Filmstrip generation complete ({n_strip} frames).")
            else:
                filmstrip = []
                self.filmstrip_ready.emit(filmstrip)

            # ---- 2. SAMPLE TIMES (scene detection or uniform) ----
            self.stage_changed.emit("Phase 2: Detecting scenes")
            sample_times = self._compute_sample_times(total_frames, fps, dur)
            if self._abort:
                return
            logger.info(f"Will analyse {len(sample_times)} sample times.")

            # ---- 3. PARALLEL SCORING ----
            self.stage_changed.emit("Phase 3: Analysing frames")
            cands = self._score_samples(sample_times, len(filmstrip))
            if self._abort:
                return

            cands.sort(key=lambda c: c.total_score, reverse=True)
            cands = filter_similar(cands)[: self.n_cands]

            # Normalize per-criterion scores across all candidates using
            # min-max scaling.  This ensures weights are comparable even when
            # raw score distributions differ sharply (e.g. sharpness clusters
            # at 0.8–1.0 while color_harmony sits at 0.4–0.6).
            if len(cands) > 1:
                cands = _normalize_scores(cands)
                # Re-compute total_score with the active weights after normalisation
                for c in cands:
                    c.total_score = sum(
                        c.breakdown.get(k, 0.0) * self.weights.get(k, 0.0) for k in self.weights
                    )
                cands.sort(key=lambda c: c.total_score, reverse=True)

            info = dict(path=self.path, duration=dur, fps=fps, width=w, height=h,
                        total_frames=total_frames)
            logger.info(f"Analysis complete. Returning {len(cands)} candidates.")
            self.finished_ok.emit(cands, info)

        except Exception as e:
            traceback.print_exc()
            logger.error(f"Analysis error: {e}")
            self.finished_err.emit(str(e))

    # -- phase 1: filmstrip ------------------------------------------------
    def _build_filmstrip(self, dur: float) -> List[Tuple[float, np.ndarray]]:
        n_strip = min(DEFAULT_FILMSTRIP_FRAMES, max(20, int(dur / 2)))
        times = [dur * (i + 0.5) / n_strip for i in range(n_strip)]
        thumb_h = 64

        # Sequential cap.set is the bottleneck, so parallelise with a pool.
        filmstrip: List[Tuple[float, np.ndarray]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as ex:
            futures = {ex.submit(_grab_filmstrip_frame, self.path, t, thumb_h): t for t in times}
            done = 0
            for fut in concurrent.futures.as_completed(futures):
                if self._abort:
                    ex.shutdown(wait=False, cancel_futures=True)
                    return []
                done += 1
                self.progress.emit(done, n_strip + self.n_samples)
                try:
                    result = fut.result()
                    if result is not None:
                        filmstrip.append(result)
                except Exception as e:
                    logger.warning(f"Filmstrip grab error: {e}")

        filmstrip.sort(key=lambda r: r[0])  # preserve chronological order
        return filmstrip

    # -- phase 2: sample times ---------------------------------------------
    def _compute_sample_times(self, total_frames: int, fps: float, dur: float) -> List[float]:
        # If an explicit override was provided (e.g. re-analyze neighborhood),
        # use it directly and skip scene detection / uniform sampling.
        if self._sample_times_override is not None:
            return [max(0.0, min(t, dur)) for t in self._sample_times_override]

        sample_times: List[float] = []
        if self.use_scene and fps > 0:
            logger.info("Performing histogram-based scene detection...")
            s_cap = cv2.VideoCapture(self.path)
            step = max(1, int(fps))  # sample ~1 frame per second
            log_interval = max(1, total_frames // 10)
            prev_hist: Optional[np.ndarray] = None
            prev_gray: Optional[np.ndarray] = None

            # Adaptive thresholds: start conservative, track running stats
            diff_history: List[float] = []

            try:
                for i in range(0, total_frames, step):
                    if self._abort:
                        return []
                    s_cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, f = s_cap.read()
                    if not ret:
                        continue
                    gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)

                    if prev_gray is not None:
                        # --- Multi-criteria scene change detection ---
                        # 1. Histogram chi-squared distance (colour distribution change)
                        curr_hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
                        cv2.normalize(curr_hist, curr_hist)
                        if prev_hist is not None:
                            chi_sq = cv2.compareHist(prev_hist, curr_hist, cv2.HISTCMP_CHISQR)
                        else:
                            chi_sq = 0.0
                        prev_hist = curr_hist.copy()

                        # 2. Pixel-level mean absolute difference (structural change)
                        pixel_diff = float(np.mean(cv2.absdiff(gray, prev_gray)))

                        # 3. Edge map change: compute Canny and measure edge overlap
                        edges_curr = cv2.Canny(gray, 50, 150)
                        edges_prev = cv2.Canny(prev_gray, 50, 150)
                        # Symmetric difference of edge pixels
                        edge_change = float(np.count_nonzero(edges_curr != edges_prev)) / (gray.size + 1e-9)

                        # Adaptive thresholding: use running median of diffs
                        diff_history.append(pixel_diff)
                        if len(diff_history) > 30:
                            median_diff = float(np.median(diff_history[-30:]))
                            mad = float(np.median(np.abs(diff_history[-30:] - median_diff)))
                            adaptive_thresh = median_diff + 3.0 * (mad + 5.0)
                        else:
                            adaptive_thresh = 20.0

                        # Scene change decision: require at least 2 of 3 criteria
                        criteria_met = 0
                        if pixel_diff > max(adaptive_thresh, 15.0):
                            criteria_met += 1
                        # Chi-squared threshold: use adaptive or fixed minimum
                        chi_thresh = max(0.5, adaptive_thresh * 0.03)
                        if chi_sq > chi_thresh:
                            criteria_met += 1
                        # Edge change threshold
                        if edge_change > 0.08:
                            criteria_met += 1

                        if criteria_met >= 2:
                            t = i / fps
                            # Avoid detecting multiple scene changes within 1 second
                            if not sample_times or (t - sample_times[-1]) >= 1.0:
                                sample_times.append(t)

                    prev_gray = gray
                    if i % log_interval < step:
                        logger.info(f"Scene scan: {int(100 * i / total_frames)}% complete")
            finally:
                s_cap.release()

            logger.info(f"Detected {len(sample_times)} scene changes "
                        f"(histogram-based multi-criteria).")

        if not sample_times:
            sample_times = list(np.linspace(0.05, 0.95, self.n_samples) * dur)
        return sample_times

    # -- phase 3: parallel scoring -----------------------------------------
    def _score_samples(self, sample_times: List[float], n_strip: int) -> List[Candidate]:
        cands: List[Candidate] = []
        total = len(sample_times)
        if total == 0:
            return cands

        logger.info(f"Dispatching {total} tasks to {self._max_workers} workers...")

        # Debounce UI updates — emit at most every ANALYSIS_BATCH_INTERVAL_MS.
        last_emit = {"t": 0.0}
        processed = {"n": 0}

        def maybe_emit(cand: Optional[Candidate]) -> None:
            processed["n"] += 1
            now = self._elapsed_ms()
            if cand is not None and (now - last_emit["t"]) >= ANALYSIS_BATCH_INTERVAL_MS:
                self.candidate_ready.emit(cand, processed["n"], total)
                last_emit["t"] = now

        # Shared VideoCapture pool — one cap per worker to avoid
        # repeated open/close overhead in _process_single_frame.
        caps_lock = threading.Lock()
        caps_pool: list = []

        def _get_pooled_cap() -> "cv2.VideoCapture":
            with caps_lock:
                if caps_pool:
                    return caps_pool.pop()
            cap = cv2.VideoCapture(self.path)
            return cap

        def _return_pooled_cap(cap) -> None:
            with caps_lock:
                caps_pool.append(cap)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as ex:
            fut_to_t = {
                ex.submit(_process_single_frame, self.path, t, self.weights,
                          _get_pooled_cap, _return_pooled_cap): t
                for t in sample_times
            }
            for fut in concurrent.futures.as_completed(fut_to_t):
                if self._abort:
                    logger.warning("Aborting analysis...")
                    ex.shutdown(wait=False, cancel_futures=True)
                    # Release pooled caps
                    with caps_lock:
                        for c in caps_pool:
                            try: c.release()
                            except Exception: pass
                        caps_pool.clear()
                    return []
                self.progress.emit(n_strip + processed["n"], n_strip + total)
                try:
                    cand = fut.result()
                    if cand is not None:
                        cands.append(cand)
                        maybe_emit(cand)
                    else:
                        processed["n"] += 1
                except Exception as e:
                    logger.error(f"Error processing frame: {e}")
                    processed["n"] += 1

        # Release any remaining pooled caps
        with caps_lock:
            for c in caps_pool:
                try: c.release()
                except Exception: pass
            caps_pool.clear()

        # Post-pass: compute motion scores using temporal ordering.
        # Sort by timestamp, then compute optical flow between consecutive frames.
        if len(cands) > 1 and self.weights.get("motion", 0.0) > 0:
            cands.sort(key=lambda c: c.timestamp)
            for i in range(len(cands)):
                if self._abort:
                    break
                prev_cand = cands[i - 1] if i > 0 else None
                if prev_cand is not None:
                    frame_cur = cands[i].ensure_frame()
                    frame_prev = prev_cand.ensure_frame()
                    if frame_cur is not None and frame_prev is not None:
                        try:
                            _, gray_cur = downscale_for_scoring(frame_cur, SCORING_MAX_DIMENSION)
                            _, gray_prev = downscale_for_scoring(frame_prev, SCORING_MAX_DIMENSION)
                            motion_val = score_motion(gray_cur, gray_prev)
                        except Exception:
                            motion_val = 0.0
                        cands[i].breakdown["motion"] = motion_val
                        cands[i].motion_magnitude = motion_val

        logger.info(f"Parallel scoring complete. {len(cands)} raw candidates.")
        return cands

    # -- small helper ------------------------------------------------------
    @staticmethod
    def _elapsed_ms() -> float:
        # time already imported at module level
        return time.monotonic() * 1000.0

# ==================================================================
# widgets.py
# ==================================================================

"""Custom widgets: preview canvas, histogram, score breakdown, filmstrip,
gallery card, empty-state overlay.

Layout / UX improvements over the original:
  * ZoomablePreview supports wheel-zoom and pan with the middle mouse button,
    plus grid / face-overlay toggles drawn in cosmetic (screen-space) pens.
  * HistogramWidget pre-builds a QPainterPath per channel so paint events
    stay cheap even on resize.
  * ScoreBreakdownWidget uses a clean horizontal-bar layout with dynamic
    colour thresholds and proper label widths.
  * FilmstripTimeline now shows timestamp labels under each thumb and uses
    a hover highlight.
  * GalleryCard is self-contained: it owns its thumbnail (from the shared
    cache), its star button, and its selected / starred styling, so the
    parent window can update it in-place instead of rebuilding the gallery.
    Emits ``reanalyze_requested(idx)`` from the right-click context menu.
  * EmptyStateOverlay sits on top of the preview area when no video is
    loaded and shows a friendly call-to-action.
"""

from typing import List, Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal, QRectF, QPoint
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QPen, QPainterPath, QMouseEvent,
)
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame,
    QScrollArea, QGraphicsView, QGraphicsScene, QMenu, QSizePolicy,
)



# ────────────────────────────────────────────────────────────────────────────
# Preview canvas
# ────────────────────────────────────────────────────────────────────────────
class ZoomablePreview(QGraphicsView):
    """Pannable / zoomable image canvas with optional grid + face + crop overlays."""

    def __init__(self) -> None:
        super().__init__()
        self._zoom = 1.0
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("background: transparent; border: none;")
        self._pixmap_item = None

        self.show_grid: bool = False
        self.show_faces: bool = False
        self.show_crop: bool = False
        self._crop_size: Optional[Tuple[int, int]] = None
        self._current_cand: Optional[Candidate] = None

    # -- public API --------------------------------------------------------
    def set_pixmap(self, pm: QPixmap, cand: Optional[Candidate] = None) -> None:
        self.scene().clear()
        self._pixmap_item = self.scene().addPixmap(pm)
        self.scene().setSceneRect(QRectF(pm.rect()))
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._current_cand = cand
        self._zoom = 1.0
        self.viewport().update()

    def set_overlays(self, *, grid: Optional[bool] = None,
                     faces: Optional[bool] = None,
                     crop: Optional[bool] = None,
                     crop_size: Optional[Tuple[int, int]] = None) -> None:
        if grid is not None:
            self.show_grid = grid
        if faces is not None:
            self.show_faces = faces
        if crop is not None:
            self.show_crop = crop
        if crop_size is not None:
            self._crop_size = crop_size
        self.viewport().update()

    # -- zoom & pan --------------------------------------------------------
    def wheelEvent(self, e) -> None:  # type: ignore[override]
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = e.angleDelta().y() / 120.0
            factor = 1.2 ** delta
            self.scale(factor, factor)
            self._zoom *= factor
        else:
            super().wheelEvent(e)

    def zoom_in(self) -> None:
        self.scale(1.2, 1.2)
        self._zoom *= 1.2

    def zoom_out(self) -> None:
        self.scale(1 / 1.2, 1 / 1.2)
        self._zoom /= 1.2

    def fit(self) -> None:
        if self._pixmap_item is not None:
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = 1.0

    # -- overlays ----------------------------------------------------------
    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        if self._pixmap_item is None:
            return
        painter.save()

        if self.show_grid:
            w = self._pixmap_item.pixmap().width()
            h = self._pixmap_item.pixmap().height()
            pen_grid = QPen(QColor(255, 255, 255, 90), 1)
            pen_grid.setCosmetic(True)
            painter.setPen(pen_grid)
            for i in range(1, 3):
                painter.drawLine(int(w * i / 3), 0, int(w * i / 3), h)
                painter.drawLine(0, int(h * i / 3), w, int(h * i / 3))
            # rule-of-thirds intersections (slightly brighter dots)
            painter.setBrush(QColor(255, 255, 255, 160))
            painter.setPen(Qt.PenStyle.NoPen)
            for fx in (1 / 3, 2 / 3):
                for fy in (1 / 3, 2 / 3):
                    painter.drawEllipse(QPoint(int(w * fx), int(h * fy)), 3, 3)

        if self.show_faces and self._current_cand is not None:
            pen = QPen(QColor(C_TEXT), 3)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for (x, y, fw, fh) in self._current_cand.faces:
                painter.drawRect(int(x), int(y), int(fw), int(fh))

        # Crop overlay: darken areas outside the target crop region
        if self.show_crop and self._crop_size is not None and self._pixmap_item is not None:
            tw, th = self._crop_size
            pw = self._pixmap_item.pixmap().width()
            ph = self._pixmap_item.pixmap().height()
            if pw > 0 and ph > 0:
                ratio = max(tw / pw, th / ph)
                scaled_w = int(pw * ratio)
                scaled_h = int(ph * ratio)
                left = (scaled_w - tw) // 2
                top = (scaled_h - th) // 2
                if ratio > 0:
                    crop_left = left / ratio
                    crop_top = top / ratio
                    crop_w = tw / ratio
                    crop_h = th / ratio
                else:
                    crop_left = crop_top = crop_w = crop_h = 0
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 0, 0, 100))
                painter.drawRect(QRectF(0, 0, pw, crop_top))
                painter.drawRect(QRectF(0, crop_top + crop_h, pw, ph - crop_top - crop_h))
                painter.drawRect(QRectF(0, crop_top, crop_left, crop_h))
                painter.drawRect(QRectF(crop_left + crop_w, crop_top,
                                        pw - crop_left - crop_w, crop_h))
                pen_crop = QPen(QColor(255, 200, 0, 200), 2)
                pen_crop.setCosmetic(True)
                painter.setPen(pen_crop)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(crop_left, crop_top, crop_w, crop_h))

        painter.restore()


# ────────────────────────────────────────────────────────────────────────────
# RGB histogram
# ────────────────────────────────────────────────────────────────────────────
class HistogramWidget(QWidget):
    """RGB channel histogram with semi-transparent filled curves."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(120)
        self._hist_data: Optional[List[np.ndarray]] = None
        self._paths: List[QPainterPath] = []

    def set_data(self, bgr: Optional[np.ndarray]) -> None:
        if bgr is None or bgr.size == 0:
            self._hist_data = None
            self._paths = []
            self.update()
            return
        self._hist_data = []
        for i in range(3):
            hist = cv2.calcHist([bgr], [i], None, [256], [0, 256])
            cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
            self._hist_data.append(hist.flatten())
        self._rebuild_paths()
        self.update()

    def _rebuild_paths(self) -> None:
        self._paths = []
        if not self._hist_data:
            return
        w, h = self.width(), self.height()
        margin = 8
        gw, gh = w - 2 * margin, h - 2 * margin
        for hist in self._hist_data:
            path = QPainterPath()
            path.moveTo(margin, h - margin)
            for i, val in enumerate(hist):
                x = margin + (i / 255.0) * gw
                y = h - margin - float(val) * gh
                path.lineTo(x, y)
            path.lineTo(margin + gw, h - margin)
            self._paths.append(path)

    def resizeEvent(self, e) -> None:  # type: ignore[override]
        super().resizeEvent(e)
        self._rebuild_paths()
        self.update()

    def paintEvent(self, e) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C_CARD))
        p.setPen(QPen(QColor(C_OVERLAY), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if not self._paths:
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data")
            return
        channel_colors = [(220, 60, 60), (60, 200, 60), (80, 130, 230)]  # R, G, B
        for idx, path in enumerate(self._paths):
            r, g, b = channel_colors[idx]
            fill = QColor(r, g, b, 80)
            p.fillPath(path, fill)
            p.setPen(QColor(r, g, b))
            p.drawPath(path)


# ────────────────────────────────────────────────────────────────────────────
# Score breakdown bar chart
# ────────────────────────────────────────────────────────────────────────────
class ScoreBreakdownWidget(QWidget):
    """Horizontal bars for each scoring criterion, coloured by threshold."""

    # Height per bar (including spacing)
    _BAR_H = 14
    _SPACING = 6
    _MARGIN_Y = 10

    def __init__(self) -> None:
        super().__init__()
        self._scores: Dict[str, float] = {}
        # Auto-size: 14 criteria * (bar_h + spacing) + margins
        n = len(CRIT_LABELS)
        self.setMinimumHeight(
            2 * self._MARGIN_Y + n * self._BAR_H + (n - 1) * self._SPACING
        )

    def set_scores(self, scores: Optional[Dict[str, float]]) -> None:
        self._scores = scores or {}
        self.update()

    def _bar_color(self, val: float) -> str:
        if val > 0.7:  return C_TEXT
        if val < 0.3:  return C_SUBTEXT
        return C_ACCENT

    def paintEvent(self, e) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C_CARD))
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if not self._scores:
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No candidate selected")
            return

        keys = sorted(k for k in self._scores if k in CRIT_LABELS)
        if not keys:
            return

        bar_h = self._BAR_H
        spacing = self._SPACING
        label_w = 70
        value_w = 38
        margin_x = 10
        margin_y = self._MARGIN_Y
        bar_x = margin_x + label_w
        bar_w = max(40, self.width() - bar_x - value_w - margin_x)

        p.setFont(QFont("Segoe UI", 9))
        for i, k in enumerate(keys):
            y = margin_y + i * (bar_h + spacing)
            val = float(self._scores.get(k, 0.0))

            # Label
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(margin_x, y, label_w - 6, bar_h,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       CRIT_LABELS.get(k, k))

            # Track
            p.setBrush(QColor(C_OVERLAY))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(bar_x, y, bar_w, bar_h), 4, 4)

            # Fill
            fill_w = max(0.0, min(bar_w * val, bar_w))
            if fill_w > 0:
                p.setBrush(QColor(self._bar_color(val)))
                p.drawRoundedRect(QRectF(bar_x, y, fill_w, bar_h), 4, 4)

            # Value
            p.setPen(QColor(C_TEXT))
            p.drawText(bar_x + bar_w + 4, y, value_w, bar_h,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       f"{val:.2f}")


# ────────────────────────────────────────────────────────────────────────────
# Filmstrip timeline
# ────────────────────────────────────────────────────────────────────────────
class FilmstripTimeline(QScrollArea):
    """Horizontal scrolling filmstrip. Click a thumb to seek to that timestamp."""
    clicked = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(100)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"QScrollArea {{ background:{C_OVERLAY}; border-radius:8px; border:none; }}")

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.lay = QHBoxLayout(self.container)
        self.lay.setContentsMargins(6, 4, 6, 4)
        self.lay.setSpacing(4)
        self.lay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setWidget(self.container)

    def set_frames(self, frames: List[tuple]) -> None:
        # Clear existing widgets
        while self.lay.count():
            item = self.lay.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.deleteLater()

        if not frames:
            return

        for t, bgr in frames:
            if bgr is None or bgr.size == 0:
                continue
            cell = _FilmstripCell(t, bgr)
            cell.clicked.connect(self.clicked.emit)
            self.lay.addWidget(cell)


class _FilmstripCell(QFrame):
    """One thumbnail cell in the filmstrip, with timestamp tooltip + hover."""
    clicked = Signal(float)

    def __init__(self, t: float, bgr: np.ndarray) -> None:
        super().__init__()
        self._t = t
        self.setFixedSize(96, 84)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(format_time(t))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)

        lbl = QLabel()
        lbl.setPixmap(bgr_to_qpixmap(bgr).scaled(
            92, 64, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)

        ts_lbl = QLabel(format_time(t))
        ts_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ts_lbl.setStyleSheet(
            f"color:{C_TEXT}; background:{C_SURFACE}; border-radius:3px; "
            "padding:1px 4px; font-size:10px; font-family:'JetBrains Mono','Consolas',monospace;"
        )
        lay.addWidget(ts_lbl)

        self._refresh_style(False)

    def _refresh_style(self, hovered: bool) -> None:
        border = C_ACCENT if hovered else "transparent"
        self.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:2px solid {border}; border-radius:6px; }}"
        )

    def enterEvent(self, e) -> None:  # type: ignore[override]
        self._refresh_style(True)

    def leaveEvent(self, e) -> None:  # type: ignore[override]
        self._refresh_style(False)

    def mousePressEvent(self, e: QMouseEvent) -> None:  # type: ignore[override]
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._t)


# ────────────────────────────────────────────────────────────────────────────
# Gallery card
# ────────────────────────────────────────────────────────────────────────────
class GalleryCard(QFrame):
    """A single candidate tile in the gallery grid.

    Emits ``clicked(idx)`` on left-click, ``starred_toggled(idx)`` when
    the star button is toggled, and ``reanalyze_requested(idx)`` from the
    right-click context menu. Supports Ctrl/Shift-click multi-selection
    via the ``multi_select_toggled`` signal. The parent window updates
    ``selected`` / ``starred`` directly instead of rebuilding the gallery.

    Card size is controlled by the ``size`` argument: "Small", "Medium",
    or "Large" (see ``CARD_SIZE_PRESETS``).
    """
    clicked = Signal(int)
    starred_toggled = Signal(int)
    reanalyze_requested = Signal(int)
    multi_select_toggled = Signal(int, bool)  # (idx, ctrl_or_shift_held)
    _save_as_preset = Signal(object)  # (idx, (w, h) or None)

    CARD_SIZE_PRESETS = {
        "Small":  (160, 95),
        "Medium": (200, 110),
        "Large":  (260, 145),
    }

    def __init__(self, idx: int, cand: Candidate, size: str = "Medium") -> None:
        super().__init__()
        self.idx = idx
        self.cand = cand
        self._selected = False
        self._multi_selected = False
        self._size = size if size in self.CARD_SIZE_PRESETS else "Medium"
        w, h = self.CARD_SIZE_PRESETS[self._size]
        self.setFixedSize(w, h)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)
        # Rich tooltip with top-3 scoring criteria
        self.setToolTip(self._build_top_scores_tooltip())

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        self.img = QLabel()
        # Pull from the shared thumbnail cache — avoids re-converting on every refresh
        frame = cand.ensure_frame() if hasattr(cand, "ensure_frame") else cand.frame_bgr
        if frame is not None:
            pm = THUMBS.gallery(id(cand), frame)
            self.img.setPixmap(pm)
        self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img.setMinimumHeight(max(40, h - 50))
        lay.addWidget(self.img, stretch=1)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        # Rank badge — colour-coded by score tier
        rank_lbl = QLabel(f"#{idx + 1}")
        rank_lbl.setStyleSheet(
            f"color:{self._score_badge_color()}; font-weight:bold; font-size:11px;"
        )
        row.addWidget(rank_lbl)

        ts_lbl = QLabel(format_time(cand.timestamp))
        ts_lbl.setStyleSheet(
            "font-size:10px; font-family:'JetBrains Mono','Consolas',monospace; color:" + C_SUBTEXT + ";"
        )
        row.addWidget(ts_lbl)
        row.addStretch()

        # Score with tier colouring
        score_lbl = QLabel(f"{cand.total_score:.2f}")
        tier_color = self._score_badge_color()
        score_lbl.setStyleSheet(
            f"font-size:11px; font-weight:bold; color:{tier_color}; "
            "font-family:'JetBrains Mono','Consolas',monospace;"
        )
        row.addWidget(score_lbl)

        self.star_btn = QPushButton("☆")
        self.star_btn.setFixedSize(22, 22)
        self.star_btn.setFlat(True)
        self.star_btn.setStyleSheet("font-size:14px; padding:0; margin:0;")
        self.star_btn.clicked.connect(lambda: self.starred_toggled.emit(self.idx))
        row.addWidget(self.star_btn)

        lay.addLayout(row)
        self._refresh_style()

    def _score_badge_color(self) -> str:
        """Return colour for the rank badge based on total_score tier."""
        s = self.cand.total_score
        if s >= 0.7:
            return C_TEXT
        if s >= 0.4:
            return C_ACCENT
        return C_SUBTEXT

    def _build_top_scores_tooltip(self) -> str:
        """Build a tooltip showing the top 3 scoring criteria."""
        if not self.cand.breakdown:
            return ""
        sorted_scores = sorted(self.cand.breakdown.items(), key=lambda kv: kv[1], reverse=True)
        top3 = sorted_scores[:3]
        lines = [f"  {CRIT_LABELS.get(k, k)}: {v:.2f}" for k, v in top3]
        return (f"Rank #{self.idx + 1}  •  Score {self.cand.total_score:.3f}\n"
                + "\n".join(lines))

    def resize_card(self, size: str) -> None:
        """Change the card's size preset. Caller is responsible for re-laying out."""
        if size not in self.CARD_SIZE_PRESETS:
            return
        self._size = size
        w, h = self.CARD_SIZE_PRESETS[size]
        self.setFixedSize(w, h)
        self.img.setMinimumHeight(max(40, h - 50))
        self._refresh_style()

    # -- public state updates ----------------------------------------------
    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self._refresh_style()

    def set_multi_selected(self, selected: bool) -> None:
        if self._multi_selected != selected:
            self._multi_selected = selected
            self._refresh_style()

    def refresh_star(self) -> None:
        self.star_btn.setText("★" if self.cand.starred else "☆")
        self.star_btn.setStyleSheet(
            f"color:{C_TEXT}; font-size:14px; padding:0; margin:0;"
            if self.cand.starred else "font-size:14px; padding:0; margin:0;"
        )
        self._refresh_style()

    def refresh_thumbnail(self) -> None:
        """Re-fetch the thumbnail (e.g. after the frame was re-loaded from disk)."""
        frame = self.cand.ensure_frame() if hasattr(self.cand, "ensure_frame") else self.cand.frame_bgr
        if frame is not None:
            # Invalidate cache for this candidate so we re-generate the thumb
            THUMBS.invalidate(id(self.cand))
            pm = THUMBS.gallery(id(self.cand), frame)
            self.img.setPixmap(pm)

    # -- internal ----------------------------------------------------------
    def _refresh_style(self) -> None:
        if self._selected:
            border, bg = C_TEXT, C_SURFACE
        elif self._multi_selected:
            border, bg = C_ACCENT, C_SURFACE
        elif self.cand.starred:
            border, bg = C_TEXT, C_SURFACE
        else:
            border, bg = "transparent", C_CARD
        self.setStyleSheet(
            f"QFrame {{ background:{bg}; border:2px solid {border}; border-radius:8px; }}"
            "QFrame:hover {{ border-color:" + C_ACCENT + "; }}"
        )

    def mousePressEvent(self, e: QMouseEvent) -> None:  # type: ignore[override]
        if e.button() == Qt.MouseButton.LeftButton:
            if e.modifiers() & (Qt.KeyboardModifier.ControlModifier |
                                Qt.KeyboardModifier.ShiftModifier):
                self.multi_select_toggled.emit(self.idx, True)
            else:
                self.clicked.emit(self.idx)

    def _ctx_menu(self, pos) -> None:
        m = QMenu(self)
        a_save = m.addAction("Save this frame…")
        a_copy_img = m.addAction("Copy frame to clipboard")
        a_star = m.addAction("Unstar" if self.cand.starred else "Star")
        m.addSeparator()
        a_reanalyze = m.addAction("Re-analyze ±2s around this frame")
        a_set_preset = m.addMenu("Save as preset…")
        preset_actions = {}
        for preset_name, preset_size in PRESETS.items():
            if preset_size is not None:
                act_preset = a_set_preset.addAction(
                    f"{preset_name} ({preset_size[0]}\u00d7{preset_size[1]})",
                )
                preset_actions[act_preset] = preset_size
        m.addSeparator()
        a_copy_ts = m.addAction("Copy timestamp")
        act = m.exec(self.mapToGlobal(pos))
        if act == a_save:
            self.clicked.emit(self.idx)
        elif act == a_copy_img:
            frame = self.cand.ensure_frame()
            if frame is not None:
                QApplication.clipboard().setPixmap(bgr_to_qpixmap(frame))
                main_win = self.window()
                if main_win and hasattr(main_win, 'statusBar'):
                    main_win.statusBar().showMessage("Frame copied to clipboard", 2000)
        elif act == a_star:
            self.starred_toggled.emit(self.idx)
        elif act == a_reanalyze:
            self.reanalyze_requested.emit(self.idx)
        elif act in preset_actions:
            self._save_as_preset.emit((self.idx, preset_actions[act]))
        elif act == a_copy_ts:
            QApplication.clipboard().setText(f"{self.cand.timestamp:.3f}")


# ────────────────────────────────────────────────────────────────────────────
# Empty-state overlay
# ────────────────────────────────────────────────────────────────────────────
class EmptyStateOverlay(QWidget):
    """A translucent overlay shown on top of the preview when no video is loaded.

    Shows a large icon, a headline, a hint, and an optional call-to-action
    button. Set ``mode`` to one of:
      * ``"no_file"``  — no video loaded
      * ``"no_analysis"`` — video loaded but no candidates yet
      * ``"hidden"``   — hide the overlay
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._mode = "no_file"
        self._open_callback = None

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(12)

        self._icon = QLabel("🎬")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet("font-size: 64px;")
        lay.addWidget(self._icon)

        self._title = QLabel("No Video Loaded")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"font-size:18px; font-weight:bold; color:{C_TEXT};"
        )
        lay.addWidget(self._title)

        self._hint = QLabel("Open a video file to begin  (Ctrl+O)")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(f"color:{C_SUBTEXT}; font-size:12px;")
        lay.addWidget(self._hint)

        self._btn = QPushButton("  Open Video  ")
        self._btn.setObjectName("btnPrimary")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setFixedWidth(160)
        # Centre the button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._update_content()

    def set_open_callback(self, callback) -> None:
        self._open_callback = callback
        self._btn.clicked.connect(callback)

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._update_content()
        self.setVisible(mode != "hidden")
        self.update()

    def _update_content(self) -> None:
        if self._mode == "no_file":
            self._icon.setText("🎬")
            self._title.setText("No Video Loaded")
            self._hint.setText("Open a video file to begin  (Ctrl+O)")
            self._btn.setVisible(True)
        elif self._mode == "no_analysis":
            self._icon.setText("🔍")
            self._title.setText("Ready to Analyze")
            self._hint.setText("Click Analyze in the toolbar to find thumbnails")
            self._btn.setVisible(False)
        else:
            self._btn.setVisible(False)

    def paintEvent(self, e) -> None:  # type: ignore[override]
        # QPainter, QColor already imported at module level
        from PySide6.QtGui import QColor
        # Use current theme BG color (works for both dark and light themes)
        bg = QColor(C_BG)
        bg.setAlpha(220)
        p = QPainter(self)
        p.fillRect(self.rect(), bg)
        p.end()
        super().paintEvent(e)


# ────────────────────────────────────────────────────────────────────────────
# Timeline score heatmap
# ────────────────────────────────────────────────────────────────────────────
class TimelineHeatmap(QWidget):
    """A horizontal bar showing each candidate's score as a coloured cell.

    Cells are positioned by timestamp (X axis) and coloured by score
    (red → yellow → green). Clicking a cell selects that candidate;
    hovering shows a tooltip with timestamp + score.

    This is the quickest way to spot clusters of high-quality frames
    across the whole video duration.
    """

    clicked = Signal(int)  # candidate index

    # Card-size presets (width, height) for the gallery
    CARD_SIZE_PRESETS = {
        "Small":  (160, 95),
        "Medium": (200, 110),
        "Large":  (260, 145),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(56)
        self.setMaximumHeight(56)
        self._candidates: List[Candidate] = []
        self._duration: float = 0.0
        self._hover_idx: int = -1
        self.setMouseTracking(True)

    def set_data(self, candidates: List[Candidate], duration: float) -> None:
        self._candidates = list(candidates)
        self._duration = max(duration, 0.001)
        self.update()

    def clear_data(self) -> None:
        self._candidates = []
        self._duration = 0.0
        self.update()

    def _score_to_color(self, score: float) -> QColor:
        """Map a 0..1 score to a dark → light monochrome ramp."""
        s = max(0.0, min(1.0, score))
        # dark (40,40,40) → light (212,212,212)  — C_OVERLAY → C_TEXT
        v = int(40 + (212 - 40) * s)
        return QColor(v, v, v)

    def _cell_rect(self, idx: int):
        """Return the QRect for candidate ``idx``'s cell, or None if out of range."""
        if not self._candidates or idx < 0 or idx >= len(self._candidates):
            return None
        c = self._candidates[idx]
        w = self.width()
        h = self.height()
        margin = 4
        bar_h = h - 2 * margin
        bar_w = w - 2 * margin
        x_norm = c.timestamp / self._duration
        cell_w = max(3, bar_w / max(len(self._candidates), 1))
        x = margin + x_norm * bar_w - cell_w / 2
        return QRectF(max(margin, x), margin, min(cell_w, bar_w), bar_h)

    def _hit_test(self, x: float, y: float) -> int:
        """Return the candidate index whose cell contains (x, y), or -1."""
        for i in range(len(self._candidates)):
            rect = self._cell_rect(i)
            if rect is not None and rect.contains(x, y):
                return i
        return -1

    def paintEvent(self, e) -> None:  # type: ignore[override]
        from PySide6.QtGui import QPainter, QColor, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background
        p.fillRect(self.rect(), QColor(C_CARD))

        if not self._candidates:
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Run analysis to see score heatmap")
            return

        # Draw axis line
        margin = 4
        w = self.width()
        h = self.height()
        p.setPen(QPen(QColor(C_OVERLAY), 1))
        p.drawLine(margin, h - margin, w - margin, h - margin)

        # Draw cells
        for i, c in enumerate(self._candidates):
            rect = self._cell_rect(i)
            if rect is None:
                continue
            color = self._score_to_color(c.total_score)
            if i == self._hover_idx:
                color = color.lighter(130)
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(rect, 2, 2)

        # Highlight selected if parent set it (we look up via _selected_idx attr)
        sel = getattr(self, "_selected_idx", -1)
        if 0 <= sel < len(self._candidates):
            rect = self._cell_rect(sel)
            if rect is not None:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(C_TEXT), 2))
                p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 3, 3)

    def mouseMoveEvent(self, e) -> None:  # type: ignore[override]
        idx = self._hit_test(e.position().x(), e.position().y())
        if idx != self._hover_idx:
            self._hover_idx = idx
            if idx >= 0:
                c = self._candidates[idx]
                self.setToolTip(
                    f"#{idx + 1}  {format_time(c.timestamp)}\nScore: {c.total_score:.3f}"
                )
            else:
                self.setToolTip("")
            self.update()

    def mousePressEvent(self, e) -> None:  # type: ignore[override]
        if e.button() == Qt.MouseButton.LeftButton:
            idx = self._hit_test(e.position().x(), e.position().y())
            if idx >= 0:
                self.clicked.emit(idx)

    def leaveEvent(self, e) -> None:  # type: ignore[override]
        self._hover_idx = -1
        self.update()

    def set_selected(self, idx: int) -> None:
        self._selected_idx = idx
        self.update()

# ==================================================================
# dialogs.py
# ==================================================================

"""Modal dialogs: weights editor, shortcut help, contact sheet export, about.

All secondary UI that doesn't belong in the main window lives here.
"""

from typing import Dict, List, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QSpinBox,
    QScrollArea, QWidget, QGridLayout, QDialogButtonBox, QFileDialog,
    QMessageBox, QGroupBox, QCheckBox, QComboBox, QLineEdit,
)



# ────────────────────────────────────────────────────────────────────────────
# Algorithm weights editor
# ────────────────────────────────────────────────────────────────────────────
class WeightsEditorDialog(QDialog):
    """Edit algorithm weights with live normalization preview.

    Sliders are 0–100 (display); actual weights are normalised to sum to 1.0.
    The user can save the result as a new (or overwrite an existing) custom
    profile.
    """

    def __init__(self, parent, profile_name: str, weights: Dict[str, float],
                 existing_profiles: List[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Algorithm Profile")
        self.setMinimumWidth(520)
        self._initial_weights = dict(weights)

        v = QVBoxLayout(self)
        v.setSpacing(10)

        # ── Profile name row ──
        row = QHBoxLayout()
        row.addWidget(QLabel("Profile name:"))
        self.name_edit = QLineEdit(profile_name)
        self.name_edit.setStyleSheet("padding: 4px 6px;")
        row.addWidget(self.name_edit, stretch=1)
        v.addLayout(row)

        # ── Hint ──
        hint = QLabel(
            "Drag the sliders to adjust each criterion's weight. "
            "Weights are normalised to sum to 1.0. A zero-weight criterion "
            "is excluded entirely."
        )
        hint.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
        hint.setWordWrap(True)
        v.addWidget(hint)

        # ── Sliders ──
        sliders_box = QGroupBox("Criteria Weights")
        sgrid = QGridLayout(sliders_box)
        sgrid.setContentsMargins(12, 16, 12, 12)
        sgrid.setHorizontalSpacing(10)
        sgrid.setVerticalSpacing(6)
        self._sliders: Dict[str, QSlider] = {}
        self._value_labels: Dict[str, QLabel] = {}

        for i, key in enumerate(sorted(CRIT_LABELS.keys())):
            label = QLabel(CRIT_LABELS[key])
            label.setMinimumWidth(70)
            sgrid.addWidget(label, i, 0)

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(int(round(weights.get(key, 0.0) * 100)))
            slider.valueChanged.connect(self._on_changed)
            sgrid.addWidget(slider, i, 1)
            self._sliders[key] = slider

            val_lbl = QLabel(f"{weights.get(key, 0.0):.2f}")
            val_lbl.setMinimumWidth(40)
            val_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono','Consolas',monospace; color:{C_TEXT};"
            )
            sgrid.addWidget(val_lbl, i, 2)
            self._value_labels[key] = val_lbl

        v.addWidget(sliders_box)

        # ── Summary ──
        self.summary_lbl = QLabel()
        self.summary_lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
        v.addWidget(self.summary_lbl)

        # ── Buttons ──
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        reset_btn = QPushButton("Reset to Original")
        reset_btn.clicked.connect(self._reset)
        btns.addButton(reset_btn, QDialogButtonBox.ButtonRole.ResetRole)

        v.addWidget(btns)
        self._on_changed()

    def _on_changed(self, *_) -> None:
        weights = self.get_weights()
        for key, slider in self._sliders.items():
            w = weights.get(key, 0.0)
            self._value_labels[key].setText(f"{w:.2f}")
        total = sum(weights.values())
        active = sum(1 for val in weights.values() if val > 0)
        self.summary_lbl.setText(
            f"Normalised sum: {total:.3f}  |  Active criteria: {active}/{len(self._sliders)}"
        )

    def _reset(self) -> None:
        for key, slider in self._sliders.items():
            slider.setValue(int(round(self._initial_weights.get(key, 0.0) * 100)))

    def get_weights(self) -> Dict[str, float]:
        """Return normalised weights (sum to 1.0)."""
        raw = {k: s.value() / 100.0 for k, s in self._sliders.items() if s.value() > 0}
        total = sum(raw.values())
        if total == 0:
            # All zero — fall back to uniform
            return {k: 1.0 / len(self._sliders) for k in self._sliders}
        return {k: v / total for k, v in raw.items()}

    def get_profile_name(self) -> str:
        return self.name_edit.text().strip() or "Custom Profile"


# ────────────────────────────────────────────────────────────────────────────
# Keyboard shortcut help
# ────────────────────────────────────────────────────────────────────────────
class ShortcutHelpDialog(QDialog):
    """Show keyboard shortcuts grouped by category."""

    SHORTCUTS: List[tuple] = [
        ("File", [
            ("Ctrl+O",          "Open video file"),
            ("Ctrl+S",          "Save selected frame"),
            ("Ctrl+Shift+S",    "Save all starred frames"),
            ("Ctrl+E",          "Export contact sheet"),
            ("Ctrl+Q",          "Quit"),
        ]),
        ("Navigation", [
            ("← / →",           "Previous / next candidate"),
            ("F2",              "Fit image to view"),
            ("Ctrl+= / Ctrl+-", "Zoom in / out"),
            ("Ctrl+0",          "Reset zoom to 100%"),
        ]),
        ("Overlays", [
            ("G",               "Toggle rule-of-thirds grid"),
            ("F",               "Toggle face-detection overlay"),
        ]),
        ("Analysis", [
            ("Space",           "Run / stop analysis"),
            ("Esc",             "Stop analysis"),
            ("F1",              "Show this help"),
        ]),
        ("Gallery", [
            ("S",               "Star / unstar current candidate"),
            ("R",               "Re-analyze around current frame"),
        ]),
    ]

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumWidth(460)

        v = QVBoxLayout(self)
        v.setSpacing(10)

        title = QLabel("Keyboard Shortcuts")
        title.setStyleSheet(f"font-size:15px; font-weight:bold; color:{C_TEXT};")
        v.addWidget(title)

        for section_name, items in self.SHORTCUTS:
            group = QGroupBox(section_name)
            gl = QGridLayout(group)
            gl.setContentsMargins(12, 14, 12, 12)
            gl.setHorizontalSpacing(16)
            gl.setVerticalSpacing(4)
            for i, (key, desc) in enumerate(items):
                k_lbl = QLabel(key)
                k_lbl.setStyleSheet(
                    f"color:{C_TEXT}; font-family:'JetBrains Mono','Consolas',monospace; "
                    f"font-weight:bold; font-size:11px;"
                )
                gl.addWidget(k_lbl, i, 0)
                d_lbl = QLabel(desc)
                d_lbl.setStyleSheet(f"color:{C_TEXT};")
                gl.addWidget(d_lbl, i, 1)
            v.addWidget(group)

        btn = QPushButton("Close")
        btn.setObjectName("btnPrimary")
        btn.clicked.connect(self.accept)
        v.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)


# ────────────────────────────────────────────────────────────────────────────
# About dialog
# ────────────────────────────────────────────────────────────────────────────
class AboutDialog(QDialog):
    """Simple about / credits dialog."""

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setMinimumWidth(380)

        v = QVBoxLayout(self)
        v.setSpacing(10)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Video Thumbnail Picker")
        title.setStyleSheet(f"font-size:18px; font-weight:bold; color:{C_TEXT};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title)

        ver = QLabel("Version 2.1")
        ver.setStyleSheet(f"color:{C_SUBTEXT}; font-size:12px;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(ver)

        desc = QLabel(
            "Automatically finds the best frames in a video using a\n"
            "weighted set of image-quality metrics (sharpness, contrast,\n"
            "faces, composition, colour, dynamic range and more).\n\n"
            "Built with PySide6, OpenCV and Pillow."
        )
        desc.setStyleSheet(f"color:{C_TEXT}; font-size:11px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(desc)

        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        v.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)


# ────────────────────────────────────────────────────────────────────────────
# Contact sheet export
# ────────────────────────────────────────────────────────────────────────────
class ContactSheetDialog(QDialog):
    """Configure and export a contact-sheet PNG of candidates."""

    def __init__(self, parent, candidates: List[Candidate], video_name: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Contact Sheet")
        self.setMinimumWidth(380)
        self._candidates = candidates
        self._video_name = video_name

        v = QVBoxLayout(self)
        v.setSpacing(10)

        # ── Layout settings ──
        box = QGroupBox("Layout")
        gl = QGridLayout(box)
        gl.setContentsMargins(12, 14, 12, 12)
        gl.setHorizontalSpacing(10)
        gl.setVerticalSpacing(6)

        gl.addWidget(QLabel("Columns:"), 0, 0)
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 10)
        self.cols_spin.setValue(4)
        gl.addWidget(self.cols_spin, 0, 1)

        gl.addWidget(QLabel("Thumb width (px):"), 1, 0)
        self.thumb_w_spin = QSpinBox()
        self.thumb_w_spin.setRange(80, 480)
        self.thumb_w_spin.setValue(240)
        self.thumb_w_spin.setSingleStep(20)
        gl.addWidget(self.thumb_w_spin, 1, 1)

        gl.addWidget(QLabel("Thumb height (px):"), 2, 0)
        self.thumb_h_spin = QSpinBox()
        self.thumb_h_spin.setRange(60, 360)
        self.thumb_h_spin.setValue(135)
        self.thumb_h_spin.setSingleStep(15)
        gl.addWidget(self.thumb_h_spin, 2, 1)

        self.chk_labels = QCheckBox("Show labels (rank, time, score)")
        self.chk_labels.setChecked(True)
        gl.addWidget(self.chk_labels, 3, 0, 1, 2)

        self.chk_starred_only = QCheckBox("Starred only")
        gl.addWidget(self.chk_starred_only, 4, 0, 1, 2)

        v.addWidget(box)

        # ── Preview count ──
        self.count_lbl = QLabel()
        self.count_lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
        v.addWidget(self.count_lbl)
        self._update_count()

        for sp in (self.cols_spin, self.thumb_w_spin, self.thumb_h_spin):
            sp.valueChanged.connect(self._update_count)
        self.chk_starred_only.stateChanged.connect(self._update_count)

        # ── Buttons ──
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._export)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def _update_count(self) -> None:
        cands = self._get_selected()
        cols = self.cols_spin.value()
        rows = (len(cands) + cols - 1) // cols if cols else 0
        self.count_lbl.setText(
            f"{len(cands)} frames → {rows} rows × {cols} cols"
        )

    def _get_selected(self) -> List[Candidate]:
        if self.chk_starred_only.isChecked():
            return [c for c in self._candidates if c.starred]
        return list(self._candidates)

    def _export(self) -> None:
        cands = self._get_selected()
        if not cands:
            QMessageBox.information(self, "No frames", "No frames to export.")
            return

        default_name = f"contact_sheet_{self._video_name or 'thumbnails'}.png"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Contact Sheet", default_name, "PNG (*.png)"
        )
        if not path:
            return

        try:
            self._generate(path, cands)
            QMessageBox.information(self, "Exported", f"Saved contact sheet to:\n{path}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

    def _generate(self, path: str, cands: List[Candidate]) -> None:
        cols = self.cols_spin.value()
        thumb_w = self.thumb_w_spin.value()
        thumb_h = self.thumb_h_spin.value()
        show_labels = self.chk_labels.isChecked()

        label_h = 22 if show_labels else 0
        cell_w = thumb_w
        cell_h = thumb_h + label_h
        padding = 10
        title_h = 36

        rows = (len(cands) + cols - 1) // cols
        sheet_w = cols * cell_w + (cols + 1) * padding
        sheet_h = rows * cell_h + (rows + 1) * padding + title_h

        # Background = C_BG (#171717)
        sheet = Image.new("RGB", (sheet_w, sheet_h), (23, 23, 23))
        draw = ImageDraw.Draw(sheet)

        try:
            font_title = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16
            )
            font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11
            )
        except Exception:
            font_title = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Title bar
        title_text = f"Contact Sheet — {self._video_name} ({len(cands)} frames)"
        draw.text((padding, 8), title_text, fill=(212, 212, 212), font=font_title)  # C_TEXT

        for i, c in enumerate(cands):
            row = i // cols
            col = i % cols
            x = padding + col * (cell_w + padding)
            y = title_h + padding + row * (cell_h + padding)

            # Thumbnail
            rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
            pil_thumb = Image.fromarray(rgb).resize(
                (thumb_w, thumb_h), Image.Resampling.LANCZOS
            )
            sheet.paste(pil_thumb, (x, y))

            # Border
            border_color = (212, 212, 212) if c.starred else (64, 64, 64)  # C_TEXT / C_OVERLAY
            draw.rectangle(
                [(x, y), (x + thumb_w - 1, y + thumb_h - 1)],
                outline=border_color, width=2,
            )

            # Label
            if show_labels:
                ly = y + thumb_h + 2
                label = f"#{i + 1}  {format_time(c.timestamp)}  {c.total_score:.2f}"
                draw.text((x + 2, ly), label, fill=(115, 115, 115), font=font_small)  # C_SUBTEXT

        sheet.save(path, "PNG")


# ────────────────────────────────────────────────────────────────────────────
# Preferences dialog
# ────────────────────────────────────────────────────────────────────────────
class PreferencesDialog(QDialog):
    """Edit user preferences: theme, gallery card size, filename template.

    Changes are applied immediately to the parent window via callbacks
    set with :meth:`set_callbacks`.
    """

    def __init__(self, parent, *, theme: str, card_size: str,
                 filename_template: str, auto_free_memory: bool,
                 save_quality: int, save_format: str,
                 reanalyze_radius: float, reanalyze_samples: int) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(480)

        self._on_theme_change = None
        self._on_card_size_change = None
        self._on_template_change = None
        self._on_auto_free_change = None
        self._on_save_quality_change = None
        self._on_save_format_change = None
        self._on_reanalyze_radius_change = None
        self._on_reanalyze_samples_change = None

        v = QVBoxLayout(self)
        v.setSpacing(12)

        # ── Appearance ──
        app_box = QGroupBox("Appearance")
        app_lay = QVBoxLayout(app_box)
        app_lay.setContentsMargins(12, 16, 12, 12)
        app_lay.setSpacing(8)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Theme:"))
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["dark", "light"])
        self.combo_theme.setCurrentText(theme)
        self.combo_theme.currentTextChanged.connect(self._on_theme_changed)
        row1.addWidget(self.combo_theme, stretch=1)
        app_lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Gallery card size:"))
        self.combo_card_size = QComboBox()
        self.combo_card_size.addItems(["Small", "Medium", "Large"])
        self.combo_card_size.setCurrentText(card_size)
        self.combo_card_size.currentTextChanged.connect(self._on_card_size_changed)
        row2.addWidget(self.combo_card_size, stretch=1)
        app_lay.addLayout(row2)
        v.addWidget(app_box)

        # ── Save ──
        save_box = QGroupBox("Save")
        save_lay = QVBoxLayout(save_box)
        save_lay.setContentsMargins(12, 16, 12, 12)
        save_lay.setSpacing(8)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Filename template:"))
        self.combo_template = QComboBox()
        self.combo_template.setEditable(True)
        self.combo_template.addItems([
            "thumb_{timestamp}.jpg",
            "{video}_{timestamp}.jpg",
            "{video}_rank{rank}_{score}.jpg",
            "{video}_{ts_seconds}s_{score}.jpg",
            "thumbnail_{rank:02d}.jpg",
        ])
        self.combo_template.setCurrentText(filename_template)
        self.combo_template.currentTextChanged.connect(self._on_template_changed)
        row3.addWidget(self.combo_template, stretch=1)
        save_lay.addLayout(row3)

        hint = QLabel(
            "Placeholders: {video} {timestamp} {ts_seconds} {score} {rank} {preset}\n"
            "Example: myvideo_00:12-345_0.87.jpg"
        )
        hint.setStyleSheet(f"color:{C_SUBTEXT}; font-size:10px;")
        save_lay.addWidget(hint)

        row_fmt = QHBoxLayout()
        row_fmt.addWidget(QLabel("Save format:"))
        self.combo_format = QComboBox()
        self.combo_format.addItems(["JPEG", "PNG", "WebP"])
        self.combo_format.setCurrentText(save_format)
        self.combo_format.currentTextChanged.connect(self._on_format_changed)
        row_fmt.addWidget(self.combo_format, stretch=1)
        save_lay.addLayout(row_fmt)

        row_qual = QHBoxLayout()
        row_qual.addWidget(QLabel("JPEG / WebP quality:"))
        self.slider_quality = QSlider(Qt.Orientation.Horizontal)
        self.slider_quality.setRange(10, 100)
        self.slider_quality.setValue(save_quality)
        self.quality_label = QLabel(f"{save_quality}%")
        self.quality_label.setFixedWidth(40)
        self.slider_quality.valueChanged.connect(self._on_quality_changed)
        row_qual.addWidget(self.slider_quality, stretch=1)
        row_qual.addWidget(self.quality_label)
        save_lay.addLayout(row_qual)

        v.addWidget(save_box)

        # ── Re-analyze ──
        re_box = QGroupBox("Re-analyze (right-click a candidate)")
        re_lay = QGridLayout(re_box)
        re_lay.setContentsMargins(12, 16, 12, 12)
        re_lay.setSpacing(8)

        re_lay.addWidget(QLabel("Time radius (\u00b1seconds):"), 0, 0)
        self.spin_radius = QDoubleSpinBox()
        self.spin_radius.setRange(0.5, 30.0)
        self.spin_radius.setSingleStep(0.5)
        self.spin_radius.setValue(reanalyze_radius)
        self.spin_radius.setSuffix(" s")
        self.spin_radius.valueChanged.connect(self._on_radius_changed)
        re_lay.addWidget(self.spin_radius, 0, 1)

        re_lay.addWidget(QLabel("Sample count:"), 1, 0)
        self.spin_samples = QSpinBox()
        self.spin_samples.setRange(4, 100)
        self.spin_samples.setValue(reanalyze_samples)
        self.spin_samples.valueChanged.connect(self._on_samples_changed)
        re_lay.addWidget(self.spin_samples, 1, 1)

        v.addWidget(re_box)

        # ── Memory ──
        mem_box = QGroupBox("Memory")
        mem_lay = QVBoxLayout(mem_box)
        mem_lay.setContentsMargins(12, 16, 12, 12)
        self.chk_auto_free = QCheckBox(
            "Auto-free full-res frames after analysis (re-fetches on demand)"
        )
        self.chk_auto_free.setChecked(auto_free_memory)
        self.chk_auto_free.setToolTip(
            "Releases all full-resolution frames from memory once analysis "
            "completes. Frames are re-read from the video file when needed. "
            "Saves ~30MB per 1080p candidate."
        )
        self.chk_auto_free.stateChanged.connect(self._on_auto_free_changed)
        mem_lay.addWidget(self.chk_auto_free)
        v.addWidget(mem_box)

        # ── Buttons ──
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        v.addWidget(btns)

    # -- callbacks ---------------------------------------------------------
    def set_callbacks(self, *, on_theme_change=None, on_card_size_change=None,
                      on_template_change=None, on_auto_free_change=None,
                      on_save_quality_change=None, on_save_format_change=None,
                      on_reanalyze_radius_change=None, on_reanalyze_samples_change=None,
                      ) -> None:
        self._on_theme_change = on_theme_change
        self._on_card_size_change = on_card_size_change
        self._on_template_change = on_template_change
        self._on_auto_free_change = on_auto_free_change
        self._on_save_quality_change = on_save_quality_change
        self._on_save_format_change = on_save_format_change
        self._on_reanalyze_radius_change = on_reanalyze_radius_change
        self._on_reanalyze_samples_change = on_reanalyze_samples_change

    def _on_theme_changed(self, theme: str) -> None:
        if self._on_theme_change:
            self._on_theme_change(theme)

    def _on_card_size_changed(self, size: str) -> None:
        if self._on_card_size_change:
            self._on_card_size_change(size)

    def _on_template_changed(self, template: str) -> None:
        if self._on_template_change:
            self._on_template_change(template)

    def _on_auto_free_changed(self, state: int) -> None:
        if self._on_auto_free_change:
            self._on_auto_free_change(state != 0)

    def _on_quality_changed(self, val: int) -> None:
        self.quality_label.setText(f"{val}%")
        if self._on_save_quality_change:
            self._on_save_quality_change(val)

    def _on_format_changed(self, fmt: str) -> None:
        if self._on_save_format_change:
            self._on_save_format_change(fmt)

    def _on_radius_changed(self, val: float) -> None:
        if self._on_reanalyze_radius_change:
            self._on_reanalyze_radius_change(val)

    def _on_samples_changed(self, val: int) -> None:
        if self._on_reanalyze_samples_change:
            self._on_reanalyze_samples_change(val)

    # -- getters -----------------------------------------------------------
    @property
    def theme(self) -> str: return self.combo_theme.currentText()
    @property
    def card_size(self) -> str: return self.combo_card_size.currentText()
    @property
    def filename_template(self) -> str: return self.combo_template.currentText()
    @property
    def auto_free_memory(self) -> bool: return self.chk_auto_free.isChecked()
    @property
    def save_quality(self) -> int: return self.slider_quality.value()
    @property
    def save_format(self) -> str: return self.combo_format.currentText()
    @property
    def reanalyze_radius(self) -> float: return self.spin_radius.value()
    @property
    def reanalyze_samples(self) -> int: return self.spin_samples.value()


# ────────────────────────────────────────────────────────────────────────────
# Save / Load candidate list (JSON)
# ────────────────────────────────────────────────────────────────────────────
def save_candidates_to_json(path: str, candidates: list, video_path: str,
                             video_info: dict) -> None:
    """Serialise candidate metadata (no frames) to a JSON file.

    The file can be re-loaded to skip re-analysis on a known video.
    """
    # json already imported at module level
    data = {
        "version": 1,
        "video_path": video_path,
        "video_info": video_info,
        "candidates": [
            {
                "timestamp": round(c.timestamp, 3),
                "total_score": round(c.total_score, 6),
                "breakdown": {k: round(float(v), 6) for k, v in c.breakdown.items()},
                "faces": [list(f) for f in c.faces],
                "starred": c.starred,
            }
            for c in candidates
        ],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_candidates_from_json(path: str):
    """Return (candidates, video_path, video_info) from a saved JSON file.

    Candidates are returned as ``Candidate`` objects with ``frame_bgr=None``
    — they will lazy-load from the video file on first access.
    """
    # json already imported at module level
    with open(path, "r") as f:
        data = json.load(f)
    video_path = data.get("video_path", "")
    video_info = data.get("video_info", {})
    cands = []
    for d in data.get("candidates", []):
        cands.append(Candidate(
            frame_bgr=None,
            timestamp=float(d["timestamp"]),
            total_score=float(d["total_score"]),
            breakdown={k: float(v) for k, v in d.get("breakdown", {}).items()},
            faces=[tuple(f) for f in d.get("faces", [])],
            starred=bool(d.get("starred", False)),
            video_path=video_path,
        ))
    return cands, video_path, video_info

# ==================================================================
# main_window.py
# ==================================================================

"""Main application window.

Layout overview:
  ┌───────────────────────────────────────────────────┐
  │ Menu bar: File | Edit | View | Help               │
  ├───────────────────────────────────────────────────┤
  │ Toolbar (Open / Analyze / Stop / Grid / Faces / Zoom) │
  ├───────────────────────────────────┬───────────────┤
  │                                   │ Controls      │
  │         Preview canvas            │ ──────────    │
  │      + EmptyStateOverlay          │ Tabs:         │
  │                                   │ Gallery /     │
  │                                   │ Analysis /    │
  │                                   │ Info          │
  │   Filmstrip timeline              │               │
  ├───────────────────────────────────┴───────────────┤
  │ Status bar: stage | ETA | count | progress        │
  └───────────────────────────────────────────────────┘

Features:
  * Settings persistence (window geometry, last-used settings, recent files,
    custom algorithm profiles) via state.SETTINGS.
  * Drag-and-drop video files onto the window.
  * Per-video starred-state sidecar (.vtp.json).
  * Score-threshold slider and multi-criterion sort in the gallery.
  * Re-analyze neighborhood (right-click any candidate → sample ±2s around it).
  * Contact-sheet PNG export.
  * Custom algorithm-profile editor with live normalisation.
  * F1 keyboard-shortcut help.
  * ETA + elapsed time during analysis.
  * Empty-state overlay on the preview area.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, QTimer, QMimeData
from PySide6.QtGui import (
    QPixmap, QImage, QKeySequence, QShortcut, QAction, QDragEnterEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QProgressBar, QScrollArea,
    QFileDialog, QMessageBox, QSplitter, QFrame, QToolBar, QCheckBox,
    QGridLayout, QSizePolicy, QTabWidget, QSlider, QMenu, QApplication,
)


logger = logging.getLogger("thumbnail_picker")

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".wmv"}


class MainWindow(QMainWindow):
    """Top-level window for the Video Thumbnail Picker."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Video Thumbnail Picker")
        self.resize(1600, 950)
        self.setMinimumSize(1200, 720)
        self.setAcceptDrops(True)

        # ---- state ----
        self.video_path: Optional[str] = None
        self.video_info: Dict = {}
        self.candidates: List[Candidate] = []
        self.selected_idx: int = -1
        self._worker: Optional[AnalysisThread] = None
        self._show_starred_only: bool = False
        self._score_threshold: float = SCORE_THRESHOLD_DEFAULT
        self._gallery_cards: Dict[int, GalleryCard] = {}
        self._all_profiles: Dict[str, Dict[str, float]] = {}
        self._append_mode: bool = False
        self._analysis_start_time: float = 0.0
        self._eta_timer = QTimer(self)
        self._eta_timer.timeout.connect(self._update_eta)
        # New v2.2 state
        self._card_size: str = DEFAULT_CARD_SIZE
        self._theme: str = DEFAULT_THEME
        self._filename_template: str = DEFAULT_FILENAME_TEMPLATE
        self._auto_free_memory: bool = False
        self._multi_selected: set = set()  # set of candidate id()s

        # ---- build UI ----
        self._ui()
        self._menu_bar()
        self._toolbar()
        self._shortcuts()
        self.setStyleSheet(STYLESHEET)

        # ---- restore saved settings ----
        self._restore_settings()

    # ════════════════════════════════════════════════════════════════════
    # UI CONSTRUCTION
    # ════════════════════════════════════════════════════════════════════
    def _ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(8)

        # Top header bar
        header = QFrame()
        header.setObjectName("Card")
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(12, 8, 12, 8)
        header_lay.setSpacing(12)

        title = QLabel("Video Thumbnail Picker")
        title.setObjectName("LblTitle")
        header_lay.addWidget(title)
        header_lay.addStretch()

        self.header_file_lbl = QLabel("No file loaded")
        self.header_file_lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
        header_lay.addWidget(self.header_file_lbl)
        root.addWidget(header)

        # Splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(6)
        root.addWidget(self._splitter, stretch=1)

        # ─── LEFT PANE ───
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Preview container (holds the preview + empty-state overlay)
        self.preview_container = QFrame()
        self.preview_container.setStyleSheet(f"background:{C_CARD}; border-radius:8px;")
        pc_lay = QVBoxLayout(self.preview_container)
        pc_lay.setContentsMargins(0, 0, 0, 0)
        pc_lay.setSpacing(0)

        self.preview = ZoomablePreview()
        self.preview.setMinimumHeight(420)
        self.preview.setStyleSheet("background: transparent; border: none;")
        pc_lay.addWidget(self.preview)

        self.empty_overlay = EmptyStateOverlay(self.preview_container)
        self.empty_overlay.set_open_callback(self._open_file)
        pc_lay.addWidget(self.empty_overlay)

        left_layout.addWidget(self.preview_container, stretch=1)

        self.filmstrip = FilmstripTimeline()
        self.filmstrip.clicked.connect(self._seek_time)
        left_layout.addWidget(self.filmstrip)

        # Score heatmap — shows each candidate's score on a timeline
        self.heatmap = TimelineHeatmap()
        self.heatmap.clicked.connect(self._select)
        left_layout.addWidget(self.heatmap)

        self._splitter.addWidget(left_widget)

        # ─── RIGHT PANE ───
        right_widget = QWidget()
        right_widget.setMaximumWidth(520)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        right_layout.addWidget(self._build_control_card())

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self._build_gallery_tab()
        self._build_analysis_tab()
        self._build_info_tab()
        right_layout.addWidget(self.tabs, stretch=1)

        self._splitter.addWidget(right_widget)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([1000, 520])

        # ─── status bar ───
        self.status_stage_lbl = QLabel("Ready")
        self.status_stage_lbl.setStyleSheet(f"color:{C_SUBTEXT}; padding:0 10px;")
        self.statusBar().addWidget(self.status_stage_lbl, 1)

        self.status_eta_lbl = QLabel("")
        self.status_eta_lbl.setStyleSheet(f"color:{C_SUBTEXT}; padding:0 10px;")
        self.statusBar().addWidget(self.status_eta_lbl)

        self.status_count_lbl = QLabel("0 candidates")
        self.status_count_lbl.setStyleSheet(f"color:{C_SUBTEXT}; padding:0 10px;")
        self.statusBar().addPermanentWidget(self.status_count_lbl)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(240)
        self.progress.setFixedHeight(20)
        self.progress.setVisible(False)
        self.progress.setFormat("%p%")
        self.statusBar().addPermanentWidget(self.progress)

        # Memory usage label
        self.status_mem_lbl = QLabel("")
        self.status_mem_lbl.setStyleSheet(f"color:{C_SUBTEXT}; padding:0 10px; font-size:11px;")
        self.statusBar().addPermanentWidget(self.status_mem_lbl)
        # Update memory display periodically
        self._mem_timer = QTimer(self)
        self._mem_timer.timeout.connect(self._update_memory_display)
        self._mem_timer.start(3000)
        self._update_memory_display()

    # -- control card ------------------------------------------------------
    def _build_control_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        # Algorithm row
        row1 = QHBoxLayout()
        lbl = QLabel("Algorithm"); lbl.setObjectName("LblSection"); lbl.setMinimumWidth(64)
        row1.addWidget(lbl)
        self.combo_algo = QComboBox()
        self.combo_algo.currentTextChanged.connect(self._change_algo)
        row1.addWidget(self.combo_algo, stretch=1)

        self.btn_edit_weights = QPushButton("Edit…")
        self.btn_edit_weights.setToolTip("Edit weights for the current algorithm profile")
        self.btn_edit_weights.clicked.connect(self._edit_weights)
        row1.addWidget(self.btn_edit_weights)
        v.addLayout(row1)

        # Output preset row
        row2 = QHBoxLayout()
        lbl = QLabel("Output"); lbl.setObjectName("LblSection"); lbl.setMinimumWidth(64)
        row2.addWidget(lbl)
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(PRESETS.keys())
        self.combo_preset.currentTextChanged.connect(self._on_preset_changed)
        row2.addWidget(self.combo_preset, stretch=1)
        v.addLayout(row2)

        # Advanced row
        row3 = QHBoxLayout()
        self.chk_scene = QCheckBox("Scene Detect")
        self.chk_scene.setToolTip("Run scene-change detection before sampling. Slower but smarter.")
        row3.addWidget(self.chk_scene)

        row3.addWidget(QLabel("Samples:"))
        self.spin_samples = QSpinBox()
        self.spin_samples.setRange(20, 400)
        self.spin_samples.setValue(80)
        self.spin_samples.setToolTip("Number of frames to score (more = slower, more thorough)")
        row3.addWidget(self.spin_samples)

        row3.addWidget(QLabel("Max:"))
        self.spin_cands = QSpinBox()
        self.spin_cands.setRange(4, 60)
        self.spin_cands.setValue(15)
        self.spin_cands.setToolTip("Maximum candidates to keep after dedup")
        row3.addWidget(self.spin_cands)
        row3.addStretch()
        v.addLayout(row3)

        # Action row
        row4 = QHBoxLayout()
        self.btn_save = QPushButton("  Save Selected  ")
        self.btn_save.setObjectName("btnGreen")
        self.btn_save.setToolTip("Save the currently selected frame (Ctrl+S)")
        self.btn_save.clicked.connect(self._save)
        row4.addWidget(self.btn_save, stretch=1)

        self.btn_batch = QPushButton("  Save Starred  ")
        self.btn_batch.setToolTip("Save every starred frame to a folder (Ctrl+Shift+S)")
        self.btn_batch.clicked.connect(self._batch_save)
        row4.addWidget(self.btn_batch, stretch=1)

        # Second row of actions
        row5 = QHBoxLayout()
        self.btn_save_all = QPushButton("  Save All  ")
        self.btn_save_all.setToolTip("Save all candidates to a folder")
        self.btn_save_all.clicked.connect(self._save_all)
        row5.addWidget(self.btn_save_all, stretch=1)

        self.btn_auto_best = QPushButton("  Auto-Select Best  ")
        self.btn_auto_best.setToolTip("Select highest-scoring candidate (Ctrl+Space)")
        self.btn_auto_best.clicked.connect(self._auto_select_best)
        row5.addWidget(self.btn_auto_best, stretch=1)
        v.addLayout(row5)

        return card

    # -- tabs --------------------------------------------------------------
    def _build_gallery_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)

        # Filter row 1: starred + sort + card size
        filter_row1 = QHBoxLayout()
        self.chk_starred = QCheckBox("Starred only")
        self.chk_starred.stateChanged.connect(self._on_filter_changed)
        filter_row1.addWidget(self.chk_starred)
        filter_row1.addStretch()

        filter_row1.addWidget(QLabel("Sort:"))
        self.combo_sort = QComboBox()
        for name, _, _ in SORT_OPTIONS:
            self.combo_sort.addItem(name)
        self.combo_sort.currentTextChanged.connect(self._on_sort_changed)
        filter_row1.addWidget(self.combo_sort)

        filter_row1.addWidget(QLabel("Size:"))
        self.combo_card_size = QComboBox()
        self.combo_card_size.addItems(CARD_SIZES)
        self.combo_card_size.currentTextChanged.connect(self._on_card_size_changed)
        filter_row1.addWidget(self.combo_card_size)
        lay.addLayout(filter_row1)

        # Filter row 2: score threshold slider
        filter_row2 = QHBoxLayout()
        filter_row2.addWidget(QLabel("Min score:"))
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(0, 100)
        self.threshold_slider.setValue(0)
        self.threshold_slider.setToolTip("Hide candidates below this score")
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        filter_row2.addWidget(self.threshold_slider, stretch=1)

        self.threshold_lbl = QLabel("0.00")
        self.threshold_lbl.setMinimumWidth(36)
        self.threshold_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono','Consolas',monospace; color:{C_TEXT}; font-size:11px;"
        )
        filter_row2.addWidget(self.threshold_lbl)
        lay.addLayout(filter_row2)

        # Multi-select actions row (visible only when multi_selected is non-empty)
        self.multi_select_bar = QFrame()
        self.multi_select_bar.setObjectName("Card")
        ms_lay = QHBoxLayout(self.multi_select_bar)
        ms_lay.setContentsMargins(8, 4, 8, 4)
        ms_lay.setSpacing(6)
        self.ms_count_lbl = QLabel("0 selected")
        self.ms_count_lbl.setStyleSheet(f"color:{C_TEXT}; font-weight:bold;")
        ms_lay.addWidget(self.ms_count_lbl)
        ms_lay.addStretch()

        self.btn_ms_star = QPushButton("Star")
        self.btn_ms_star.clicked.connect(lambda: self._multi_apply("star"))
        ms_lay.addWidget(self.btn_ms_star)

        self.btn_ms_unstar = QPushButton("Unstar")
        self.btn_ms_unstar.clicked.connect(lambda: self._multi_apply("unstar"))
        ms_lay.addWidget(self.btn_ms_unstar)

        self.btn_ms_clear = QPushButton("Clear")
        self.btn_ms_clear.clicked.connect(self._clear_multi_select)
        ms_lay.addWidget(self.btn_ms_clear)

        self.multi_select_bar.setVisible(False)
        lay.addWidget(self.multi_select_bar)

        # Gallery area
        self.gallery_area = QScrollArea()
        self.gallery_area.setWidgetResizable(True)
        self.gallery_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.gallery_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.gallery_container = QWidget()
        self.gallery_container.setStyleSheet("background: transparent;")
        self.gallery_layout = QGridLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(4, 4, 4, 4)
        self.gallery_layout.setSpacing(8)
        self.gallery_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.gallery_area.setWidget(self.gallery_container)
        lay.addWidget(self.gallery_area, stretch=1)

        self.tabs.addTab(tab, "Gallery")

    def _build_analysis_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        lbl1 = QLabel("RGB Histogram"); lbl1.setObjectName("LblSection")
        lay.addWidget(lbl1)
        self.histogram = HistogramWidget()
        lay.addWidget(self.histogram)

        lbl2 = QLabel("Score Breakdown"); lbl2.setObjectName("LblSection")
        lay.addWidget(lbl2)
        self.breakdown = ScoreBreakdownWidget()
        lay.addWidget(self.breakdown, stretch=1)
        self.tabs.addTab(tab, "Analysis")

    def _build_info_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        sec1 = QLabel("VIDEO"); sec1.setObjectName("LblSection")
        lay.addWidget(sec1)
        self.info_video_grid = self._build_info_grid([
            ("File:", ""), ("Duration:", ""), ("Resolution:", ""),
            ("FPS:", ""), ("Total frames:", ""),
        ])
        lay.addWidget(self.info_video_grid)

        sec2 = QLabel("SELECTED CANDIDATE"); sec2.setObjectName("LblSection")
        lay.addWidget(sec2)
        self.info_cand_grid = self._build_info_grid([
            ("Rank:", "—"), ("Timestamp:", "—"), ("Score:", "—"),
            ("Faces:", "—"), ("Sharpness:", "—"), ("Contrast:", "—"),
            ("Brightness:", "—"), ("Composition:", "—"), ("Entropy:", "—"),
            ("Exposure:", "—"), ("Complexity:", "—"), ("Harmony:", "—"),
            ("Center:", "—"), ("Skin:", "—"), ("Range:", "—"),
        ])
        lay.addWidget(self.info_cand_grid)
        lay.addStretch()
        self.tabs.addTab(tab, "Info")

    def _build_info_grid(self, rows: List[tuple]) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background:{C_CARD}; border-radius:6px; }}")
        grid = QGridLayout(frame)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        for i, (label, value) in enumerate(rows):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
            val = QLabel(value)
            val.setStyleSheet(
                f"color:{C_TEXT}; font-family:'JetBrains Mono','Consolas',monospace; font-size:11px;"
            )
            grid.addWidget(lbl, i, 0)
            grid.addWidget(val, i, 1)
            attr_name = f"_info_{label.rstrip(':').lower().replace(' ', '_')}"
            setattr(self, attr_name, val)
        return frame

    # -- menu bar ----------------------------------------------------------
    def _menu_bar(self) -> None:
        mb = self.menuBar()

        # File menu
        file_menu = mb.addMenu("&File")
        self.act_open = QAction("&Open Video…", self)
        self.act_open.setShortcut("Ctrl+O")
        self.act_open.triggered.connect(self._open_file)
        file_menu.addAction(self.act_open)

        self.recent_menu = file_menu.addMenu("Open &Recent")
        self._refresh_recent_menu()

        file_menu.addSeparator()

        self.act_save_list = QAction("&Save Candidate List…", self)
        self.act_save_list.setShortcut("Ctrl+Shift+J")
        self.act_save_list.triggered.connect(self._save_candidate_list)
        file_menu.addAction(self.act_save_list)

        self.act_load_list = QAction("&Load Candidate List…", self)
        self.act_load_list.setShortcut("Ctrl+J")
        self.act_load_list.triggered.connect(self._load_candidate_list)
        file_menu.addAction(self.act_load_list)

        file_menu.addSeparator()

        self.act_contact = QAction("Export &Contact Sheet…", self)
        self.act_contact.setShortcut("Ctrl+E")
        self.act_contact.triggered.connect(self._export_contact_sheet)
        file_menu.addAction(self.act_contact)

        file_menu.addSeparator()

        self.act_quit = QAction("&Quit", self)
        self.act_quit.setShortcut("Ctrl+Q")
        self.act_quit.triggered.connect(self.close)
        file_menu.addAction(self.act_quit)

        # Edit menu
        edit_menu = mb.addMenu("&Edit")
        self.act_edit_weights = QAction("Edit Algorithm &Weights…", self)
        self.act_edit_weights.triggered.connect(self._edit_weights)
        edit_menu.addAction(self.act_edit_weights)

        self.act_auto_select = QAction("&Auto-Select Best", self)
        self.act_auto_select.setShortcut("Ctrl+Space")
        self.act_auto_select.triggered.connect(self._auto_select_best)
        edit_menu.addAction(self.act_auto_select)

        edit_menu.addSeparator()

        self.act_prefs = QAction("&Preferences…", self)
        self.act_prefs.setShortcut("Ctrl+,")
        self.act_prefs.triggered.connect(self._show_preferences)
        edit_menu.addAction(self.act_prefs)

        # View menu
        view_menu = mb.addMenu("&View")
        self.act_grid = QAction("&Rule-of-thirds Grid", self, checkable=True)
        self.act_grid.setShortcut("G")
        self.act_grid.triggered.connect(self._toggle_grid)
        view_menu.addAction(self.act_grid)

        self.act_faces = QAction("&Face Overlay", self, checkable=True)
        self.act_faces.setShortcut("F")
        self.act_faces.triggered.connect(self._toggle_faces)
        view_menu.addAction(self.act_faces)

        self.act_crop = QAction("&Crop Overlay", self, checkable=True)
        self.act_crop.triggered.connect(self._on_crop_overlay_changed)
        view_menu.addAction(self.act_crop)

        view_menu.addSeparator()

        self.act_fit = QAction("&Fit to View", self)
        self.act_fit.setShortcut("F2")
        self.act_fit.triggered.connect(self.preview.fit)
        view_menu.addAction(self.act_fit)

        view_menu.addSeparator()

        self.act_toggle_theme = QAction("Toggle &Theme", self)
        self.act_toggle_theme.setShortcut("Ctrl+T")
        self.act_toggle_theme.triggered.connect(self._toggle_theme)
        view_menu.addAction(self.act_toggle_theme)

        self.act_free_memory = QAction("Free &Memory", self)
        self.act_free_memory.setShortcut("Ctrl+M")
        self.act_free_memory.triggered.connect(self._free_memory)
        view_menu.addAction(self.act_free_memory)

        # Help menu
        help_menu = mb.addMenu("&Help")
        self.act_shortcuts = QAction("&Keyboard Shortcuts", self)
        self.act_shortcuts.setShortcut("F1")
        self.act_shortcuts.triggered.connect(self._show_shortcuts)
        help_menu.addAction(self.act_shortcuts)

        self.act_about = QAction("&About", self)
        self.act_about.triggered.connect(self._show_about)
        help_menu.addAction(self.act_about)

    # -- toolbar -----------------------------------------------------------
    def _toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.btn_open = QPushButton("  Open Video")
        self.btn_open.setObjectName("btnPrimary")
        self.btn_open.setToolTip("Open a video file (Ctrl+O)")
        self.btn_open.clicked.connect(self._open_file)
        tb.addWidget(self.btn_open)

        self.btn_analyze = QPushButton("  Analyze")
        self.btn_analyze.setToolTip("Run thumbnail analysis (Space)")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.clicked.connect(self._start_analysis)
        tb.addWidget(self.btn_analyze)

        self.btn_stop = QPushButton("  Stop")
        self.btn_stop.setObjectName("btnRed")
        self.btn_stop.setVisible(False)
        self.btn_stop.clicked.connect(self._stop_analysis)
        tb.addWidget(self.btn_stop)

        tb.addSeparator()

        zoom_in = QPushButton("+")
        zoom_in.setFixedSize(30, 28)
        zoom_in.setToolTip("Zoom in (Ctrl+=)")
        zoom_in.clicked.connect(self.preview.zoom_in)
        tb.addWidget(zoom_in)

        zoom_out = QPushButton("−")
        zoom_out.setFixedSize(30, 28)
        zoom_out.setToolTip("Zoom out (Ctrl+-)")
        zoom_out.clicked.connect(self.preview.zoom_out)
        tb.addWidget(zoom_out)

        fit_btn = QPushButton("Fit")
        fit_btn.setFixedSize(36, 28)
        fit_btn.setToolTip("Fit to view (F2)")
        fit_btn.clicked.connect(self.preview.fit)
        tb.addWidget(fit_btn)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet(f"color:{C_SUBTEXT}; padding-right:10px;")
        tb.addWidget(self.status_lbl)

    # -- shortcuts ---------------------------------------------------------
    def _shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"),          self, self._save)
        QShortcut(QKeySequence("Ctrl+Shift+S"),    self, self._batch_save)
        QShortcut(QKeySequence("Ctrl+J"),          self, self._load_candidate_list)
        QShortcut(QKeySequence("Ctrl+Shift+J"),    self, self._save_candidate_list)
        QShortcut(QKeySequence(Qt.Key.Key_Left),     self, lambda: self._nav(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Right),    self, lambda: self._nav(1))
        QShortcut(QKeySequence(Qt.Key.Key_PageDown), self, lambda: self._nav_page(1))
        QShortcut(QKeySequence(Qt.Key.Key_PageUp),   self, lambda: self._nav_page(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Home),     self, lambda: self._nav_home_end(False))
        QShortcut(QKeySequence(Qt.Key.Key_End),      self, lambda: self._nav_home_end(True))
        QShortcut(QKeySequence("Ctrl+="),          self, self.preview.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"),          self, self.preview.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"),          self, self.preview.fit)
        QShortcut(QKeySequence("Ctrl+T"),          self, self._toggle_theme)
        QShortcut(QKeySequence("Ctrl+M"),          self, self._free_memory)
        QShortcut(QKeySequence("Ctrl+,"),          self, self._show_preferences)
        QShortcut(QKeySequence(Qt.Key.Key_Space),  self, self._toggle_analysis)
        QShortcut(QKeySequence(Qt.Key.Key_S),      self, self._star_current)
        QShortcut(QKeySequence(Qt.Key.Key_R),      self, self._reanalyze_current)
        QShortcut(QKeySequence(Qt.Key.Key_G),      self, lambda: self.act_grid.toggle())
        QShortcut(QKeySequence(Qt.Key.Key_F),      self, lambda: self.act_faces.toggle())
        QShortcut(QKeySequence(Qt.Key.Key_C),      self, lambda: self.act_crop.toggle())
        QShortcut(QKeySequence("Escape"),          self, self._on_escape)

    def _on_escape(self) -> None:
        """Escape clears multi-selection if any, otherwise stops analysis."""
        if self._multi_selected:
            self._clear_multi_select()
        else:
            self._stop_analysis()

    # ════════════════════════════════════════════════════════════════════
    # SETTINGS SAVE / RESTORE
    # ════════════════════════════════════════════════════════════════════
    def _restore_settings(self) -> None:
        SETTINGS.restore_window_state(self)
        sizes = SETTINGS.splitter_sizes()
        if sizes and len(sizes) == 2:
            self._splitter.setSizes(sizes)

        s = SETTINGS.restore_analysis_settings()
        # Merge built-in + custom profiles
        self._all_profiles = dict(ALGORITHM_PROFILES)
        self._all_profiles.update(SETTINGS.custom_profiles)
        self.combo_algo.blockSignals(True)
        self.combo_algo.clear()
        for name in self._all_profiles:
            self.combo_algo.addItem(name)
        if s["algo"] in self._all_profiles:
            self.combo_algo.setCurrentText(s["algo"])
        self.combo_algo.blockSignals(False)

        if s["preset"] in PRESETS:
            self.combo_preset.setCurrentText(s["preset"])
        self.spin_samples.setValue(s["samples"])
        self.spin_cands.setValue(s["cands"])
        self.chk_scene.setChecked(s["scene"])
        if any(s["sort"] == name for name, _, _ in SORT_OPTIONS):
            self.combo_sort.setCurrentText(s["sort"])
        self._score_threshold = s["threshold"]
        self.threshold_slider.setValue(int(s["threshold"] * 100))
        self.threshold_lbl.setText(f"{s['threshold']:.2f}")

        # Restore UI preferences
        self._card_size = SETTINGS.card_size if SETTINGS.card_size in CARD_SIZES else DEFAULT_CARD_SIZE
        self._theme = SETTINGS.theme if SETTINGS.theme in THEMES else DEFAULT_THEME
        self._filename_template = SETTINGS.filename_template or DEFAULT_FILENAME_TEMPLATE
        self._auto_free_memory = SETTINGS.auto_free_memory
        self.combo_card_size.blockSignals(True)
        self.combo_card_size.setCurrentText(self._card_size)
        self.combo_card_size.blockSignals(False)
        self._apply_theme()

    def _save_settings(self) -> None:
        SETTINGS.save_window_state(self)
        SETTINGS.save_analysis_settings(
            algo=self.combo_algo.currentText(),
            preset=self.combo_preset.currentText(),
            samples=self.spin_samples.value(),
            cands=self.spin_cands.value(),
            scene=self.chk_scene.isChecked(),
            sort=self.combo_sort.currentText(),
            threshold=self._score_threshold,
        )
        SETTINGS.card_size = self._card_size
        SETTINGS.theme = self._theme
        SETTINGS.filename_template = self._filename_template
        SETTINGS.auto_free_memory = self._auto_free_memory
        SETTINGS.sync()

    # ── Theme ─────────────────────────────────────────────────────────
    def _apply_theme(self) -> None:
        """Apply the current theme by rebuilding the stylesheet."""
        colors = get_theme_colors(self._theme)
        self.setStyleSheet(build_stylesheet(colors))

    def _toggle_theme(self) -> None:
        self._theme = THEME_LIGHT if self._theme == THEME_DARK else THEME_DARK
        self._apply_theme()
        self.statusBar().showMessage(f"Theme: {self._theme}", 2000)

    # ── Card size ─────────────────────────────────────────────────────
    def _on_card_size_changed(self, size: str) -> None:
        if size not in CARD_SIZES:
            return
        self._card_size = size
        self._gallery_cards.clear()
        self._refresh_gallery()
        self.statusBar().showMessage(f"Card size: {size}", 2000)

    # ── Memory ────────────────────────────────────────────────────────
    def _update_memory_display(self) -> None:
        """Update the memory usage label in the status bar."""
        loaded = sum(1 for c in self.candidates if c.frame_bgr is not None)
        if loaded > 0:
            # Rough estimate: H*W*3 bytes per frame
            bytes_total = sum(
                c.frame_bgr.shape[0] * c.frame_bgr.shape[1] * 3
                for c in self.candidates if c.frame_bgr is not None
            )
            if bytes_total >= 1024 ** 3:
                txt = f"~{bytes_total / (1024**3):.1f} GB ({loaded} frames)"
            else:
                txt = f"~{bytes_total / (1024**2):.0f} MB ({loaded} frames)"
        else:
            txt = ""
        self.status_mem_lbl.setText(txt)

    def _free_memory(self) -> None:
        """Release all full-res frames from memory; they'll lazy-load on demand."""
        if not self.candidates:
            self.statusBar().showMessage("No candidates to free.", 2000)
            return
        released = 0
        for c in self.candidates:
            if c.frame_bgr is not None:
                c.release_frame()
                released += 1
        THUMBS.invalidate()
        # Refresh visible gallery cards so they re-fetch from disk
        for card in self._gallery_cards.values():
            card.refresh_thumbnail()
        self.statusBar().showMessage(
            f"Freed {released} frames from memory ({FRAME_STORE.stats()['entries']} in LRU cache).",
            4000
        )

    # ════════════════════════════════════════════════════════════════════
    # DRAG & DROP
    # ════════════════════════════════════════════════════════════════════
    def dragEnterEvent(self, e: QDragEnterEvent) -> None:  # type: ignore[override]
        if e.mimeData().hasUrls():
            for url in e.mimeData().urls():
                path = url.toLocalFile()
                if Path(path).suffix.lower() in VIDEO_EXTS:
                    e.acceptProposedAction()
                    return
        e.ignore()

    def dropEvent(self, e: QDropEvent) -> None:  # type: ignore[override]
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).suffix.lower() in VIDEO_EXTS:
                self._open_file_path(path)
                e.acceptProposedAction()
                return
        e.ignore()

    # ════════════════════════════════════════════════════════════════════
    # FILE LOADING
    # ════════════════════════════════════════════════════════════════════
    def _open_file(self) -> None:
        last_dir = SETTINGS.last_dir or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", last_dir,
            "Video (*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.flv *.wmv);;All Files (*)"
        )
        if path:
            self._open_file_path(path)

    def _open_file_path(self, path: str) -> None:
        if not Path(path).exists():
            QMessageBox.warning(self, "File not found", f"The file does not exist:\n{path}")
            return
        self.video_path = path
        name = Path(path).name
        self.header_file_lbl.setText(name)
        self.statusBar().showMessage(f"Loaded: {name}", 4000)
        self.status_lbl.setText(name)
        self.btn_analyze.setEnabled(True)
        SETTINGS.add_recent_file(path)
        SETTINGS.last_dir = str(Path(path).parent)
        self._refresh_recent_menu()

        # Reset state
        self.candidates.clear()
        self._gallery_cards.clear()
        THUMBS.invalidate()
        self.selected_idx = -1
        self._multi_selected.clear()
        self._refresh_gallery()
        self.filmstrip.set_frames([])
        self.heatmap.clear_data()
        self.preview.scene().clear()
        self._refresh_info_video({"path": path})
        self._refresh_info_cand(None)
        self.empty_overlay.set_mode("no_analysis")

    def _refresh_recent_menu(self) -> None:
        self.recent_menu.clear()
        files = SETTINGS.recent_files
        if not files:
            act = self.recent_menu.addAction("(No recent files)")
            act.setEnabled(False)
            return
        for f in files:
            name = Path(f).name
            act = self.recent_menu.addAction(name)
            act.setToolTip(f)
            act.triggered.connect(lambda checked=False, p=f: self._open_file_path(p))
        self.recent_menu.addSeparator()
        clear_act = self.recent_menu.addAction("Clear recent list")
        clear_act.triggered.connect(self._clear_recent)

    def _clear_recent(self) -> None:
        SETTINGS.clear_recent_files()
        self._refresh_recent_menu()

    # ════════════════════════════════════════════════════════════════════
    # ANALYSIS LIFECYCLE
    # ════════════════════════════════════════════════════════════════════
    def _toggle_analysis(self) -> None:
        if self._worker and self._worker.isRunning():
            self._stop_analysis()
        else:
            self._start_analysis()

    def _start_analysis(self, append: bool = False,
                        sample_times: Optional[List[float]] = None) -> None:
        if not self.video_path:
            return
        self._append_mode = append

        if not append:
            # Full reset
            self.candidates.clear()
            self._gallery_cards.clear()
            THUMBS.invalidate()
            self.selected_idx = -1
            self._refresh_gallery()

        else:
            # Append mode: just clear cards so they get recreated with new ranks
            self._gallery_cards.clear()

        # UI busy state
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status_stage_lbl.setText("Initializing…")
        self.status_lbl.setText("Working…")
        self.status_count_lbl.setText(f"{len(self.candidates)} candidates")
        self.btn_analyze.setVisible(False)
        self.btn_stop.setVisible(True)
        self.btn_open.setEnabled(False)
        self.empty_overlay.set_mode("hidden")

        # ETA
        self._analysis_start_time = time.monotonic()
        self._eta_timer.start(ETA_UPDATE_INTERVAL_MS)

        weights = self._all_profiles.get(self.combo_algo.currentText(),
                                         ALGORITHM_PROFILES["General (Balanced)"])
        skip_filmstrip = append or (sample_times is not None)
        self._worker = AnalysisThread(
            self.video_path, self.spin_samples.value(),
            weights, self.spin_cands.value(), self.chk_scene.isChecked(),
            sample_times_override=sample_times,
            skip_filmstrip=skip_filmstrip,
        )
        self._worker.stage_changed.connect(self._on_stage_changed)
        self._worker.progress.connect(self._on_progress)
        self._worker.candidate_ready.connect(self._on_candidate_ready)
        self._worker.filmstrip_ready.connect(self._on_filmstrip_ready)
        self._worker.finished_ok.connect(self._finish_analysis)
        self._worker.finished_err.connect(self._on_analysis_err)
        self._worker.start()

    def _on_filmstrip_ready(self, frames) -> None:
        # Only replace filmstrip if we actually generated one (skip in append mode)
        if frames:
            self.filmstrip.set_frames(frames)

    def _stop_analysis(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait(1500)
        self._finish_analysis([], {})

    def _on_stage_changed(self, text: str) -> None:
        self.status_stage_lbl.setText(text)
        logger.info(f"Stage: {text}")

    def _on_progress(self, current: int, total: int) -> None:
        if total > 0:
            self.progress.setValue(int(100 * current / total))

    def _update_eta(self) -> None:
        if not self._analysis_start_time:
            return
        elapsed = time.monotonic() - self._analysis_start_time
        pct = self.progress.value()
        if pct > 0:
            total_est = elapsed / (pct / 100.0)
            eta = max(0, total_est - elapsed)
            self.status_eta_lbl.setText(
                f"⏱ {self._fmt_time(elapsed)} elapsed / ~{self._fmt_time(eta)} remaining"
            )
        else:
            self.status_eta_lbl.setText(f"⏱ {self._fmt_time(elapsed)} elapsed")

    @staticmethod
    def _fmt_time(s: float) -> str:
        if s < 60:
            return f"{s:.0f}s"
        m, s = divmod(int(s), 60)
        return f"{m}m {s}s"

    def _on_candidate_ready(self, cand: Candidate, _cur: int, _tot: int) -> None:
        QTimer.singleShot(0, lambda c=cand: self._add_candidate_main(c))

    def _add_candidate_main(self, cand: Candidate) -> None:
        self.candidates.append(cand)
        self.status_count_lbl.setText(f"{len(self.candidates)} candidates")
        self._make_card(cand)
        if self.selected_idx < 0:
            self._select(0)

    def _finish_analysis(self, cands: List[Candidate], info: Dict) -> None:
        self._eta_timer.stop()
        self.status_eta_lbl.setText("")

        if self._append_mode:
            # Merge new candidates into existing list
            if cands:
                self.candidates.extend(cands)
            # Re-sort
            self._apply_sort()
            # Apply starred state from sidecar
            self._apply_starred_state()
        else:
            if cands:
                self.candidates = cands
                self._gallery_cards.clear()
                THUMBS.invalidate()
            if info:
                self.video_info = info
                self._refresh_info_video(info)
            # Apply starred state from sidecar
            self._apply_starred_state()

        # Auto-free memory if enabled
        if self._auto_free_memory and self.candidates:
            freed = 0
            for c in self.candidates:
                if c.frame_bgr is not None:
                    c.release_frame()
                    freed += 1
            logger.info(f"Auto-freed {freed} frames from memory")

        self.progress.setVisible(False)
        self.btn_stop.setVisible(False)
        self.btn_analyze.setVisible(True)
        self.btn_open.setEnabled(True)
        self.status_stage_lbl.setText("Finished")
        self.status_lbl.setText("Ready")

        self._refresh_gallery()
        self.status_count_lbl.setText(f"{len(self.candidates)} candidates")
        if self.candidates:
            self._select(0)
        else:
            self.empty_overlay.set_mode("no_analysis")
        self.statusBar().showMessage(
            f"Analysis complete — {len(self.candidates)} candidates.", 5000
        )

    def _on_analysis_err(self, msg: str) -> None:
        self._finish_analysis([], {})
        QMessageBox.critical(self, "Error", msg)

    # ════════════════════════════════════════════════════════════════════
    # STARRED STATE PERSISTENCE
    # ════════════════════════════════════════════════════════════════════
    def _apply_starred_state(self) -> None:
        """Load sidecar and mark matching candidates as starred."""
        if not self.video_path:
            return
        data = ProjectState.load(self.video_path)
        starred_ts = data.get("starred_timestamps", [])
        if not starred_ts:
            return
        for c in self.candidates:
            if any(abs(c.timestamp - ts) < 0.05 for ts in starred_ts):
                c.starred = True

    def _save_starred_state(self) -> None:
        if self.video_path and self.candidates:
            ProjectState.save(self.video_path, self.candidates)

    # ════════════════════════════════════════════════════════════════════
    # GALLERY
    # ════════════════════════════════════════════════════════════════════
    def _make_card(self, cand: Candidate) -> Optional[GalleryCard]:
        if id(cand) in self._gallery_cards:
            return self._gallery_cards[id(cand)]
        try:
            real_idx = self.candidates.index(cand)
        except ValueError:
            return None
        card = GalleryCard(real_idx, cand, size=self._card_size)
        card.clicked.connect(self._select)
        card.starred_toggled.connect(self._toggle_star)
        card.reanalyze_requested.connect(self._reanalyze_idx)
        card._save_as_preset.connect(self._save_as_preset)
        card.multi_select_toggled.connect(self._on_multi_select_toggled)
        # Apply current multi-select state
        if id(cand) in self._multi_selected:
            card.set_multi_selected(True)
        self._gallery_cards[id(cand)] = card
        return card

    def _apply_sort(self) -> None:
        """Sort candidates by the currently-selected criterion."""
        if not self.candidates:
            return
        sort_name = self.combo_sort.currentText()
        for name, key, reverse in SORT_OPTIONS:
            if name == sort_name:
                if key is None:
                    self.candidates.sort(key=lambda c: c.total_score, reverse=reverse)
                elif key == "__starred__":
                    # Starred first, then by total_score descending within each group
                    self.candidates.sort(key=lambda c: (not c.starred, -c.total_score))
                else:
                    self.candidates.sort(
                        key=lambda c: c.breakdown.get(key, 0.0) if key != "timestamp" else c.timestamp,
                        reverse=reverse,
                    )
                break

    def _refresh_gallery(self) -> None:
        """Rebuild the gallery grid (structural changes only)."""
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.setParent(None)

        self._apply_sort()

        display = list(self.candidates)
        # Filter by starred
        if self._show_starred_only:
            display = [c for c in display if c.starred]
        # Filter by score threshold
        if self._score_threshold > 0:
            display = [c for c in display if c.total_score >= self._score_threshold]

        cols = GALLERY_COLUMNS
        # Build an O(1) index map: id(cand) → position in self.candidates
        id_to_pos = {id(c): i for i, c in enumerate(self.candidates)}
        for i, c in enumerate(display):
            card = self._gallery_cards.get(id(c)) or self._make_card(c)
            if card is None:
                continue
            real_idx = id_to_pos.get(id(c), -1)
            if real_idx < 0:
                continue
            card.idx = real_idx
            card.set_selected(real_idx == self.selected_idx)
            card.refresh_star()
            # Apply multi-select state
            card.set_multi_selected(id(c) in self._multi_selected)
            card.setParent(self.gallery_container)
            self.gallery_layout.addWidget(card, i // cols, i % cols)

        # Update heatmap
        self.heatmap.set_data(self.candidates, self.video_info.get("duration", 0.0))
        self.heatmap.set_selected(self.selected_idx)

        # Update multi-select bar visibility
        self._update_multi_select_bar()

    def _on_filter_changed(self, _state) -> None:
        self._show_starred_only = self.chk_starred.isChecked()
        self._refresh_gallery()

    def _on_sort_changed(self, _text: str) -> None:
        self._gallery_cards.clear()
        self._refresh_gallery()

    def _on_threshold_changed(self, value: int) -> None:
        self._score_threshold = value / 100.0
        self.threshold_lbl.setText(f"{self._score_threshold:.2f}")
        self._refresh_gallery()

    def _on_preset_changed(self, _text: str) -> None:
        if 0 <= self.selected_idx < len(self.candidates):
            self._select(self.selected_idx)

    # ════════════════════════════════════════════════════════════════════
    # SELECTION
    # ════════════════════════════════════════════════════════════════════
    def _select(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.candidates):
            return
        prev = self.selected_idx
        self.selected_idx = idx
        c = self.candidates[idx]

        # Lazy-load the frame if it was released
        frame = c.ensure_frame()
        if frame is None:
            self.statusBar().showMessage("Could not load frame.", 3000)
            return

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        preset = PRESETS.get(self.combo_preset.currentText())
        if preset:
            pil = fit_crop_pil(pil, preset)
        data = pil.tobytes("raw", "RGB")
        qim = QImage(data, pil.width, pil.height, 3 * pil.width, QImage.Format.Format_RGB888)
        qim._np_buf = data
        self.preview.set_pixmap(QPixmap.fromImage(qim), c)
        self.empty_overlay.set_mode("hidden")

        self.histogram.set_data(frame)
        self.breakdown.set_scores(c.breakdown)
        self._refresh_info_cand(c)

        # Update heatmap selection
        self.heatmap.set_selected(idx)

        if prev != idx:
            if 0 <= prev < len(self.candidates):
                prev_card = self._gallery_cards.get(id(self.candidates[prev]))
                if prev_card is not None:
                    prev_card.set_selected(False)
            cur_card = self._gallery_cards.get(id(c))
            if cur_card is not None:
                cur_card.set_selected(True)

    def _toggle_star(self, idx: int) -> None:
        if 0 <= idx < len(self.candidates):
            self.candidates[idx].starred = not self.candidates[idx].starred
            card = self._gallery_cards.get(id(self.candidates[idx]))
            if card is not None:
                card.refresh_star()
            if self._show_starred_only and not self.candidates[idx].starred:
                self._refresh_gallery()
            self._save_starred_state()

    def _star_current(self) -> None:
        if 0 <= self.selected_idx < len(self.candidates):
            self._toggle_star(self.selected_idx)

    def _nav(self, d: int) -> None:
        if not self.candidates:
            return
        self._select((self.selected_idx + d) % len(self.candidates))

    def _nav_page(self, direction: int) -> None:
        """Navigate by a page (~12 cards) in the gallery."""
        if not self.candidates:
            return
        step = 12 * direction
        new_idx = max(0, min(self.selected_idx + step, len(self.candidates) - 1))
        self._select(new_idx)

    def _nav_home_end(self, to_end: bool) -> None:
        """Jump to first (False) or last (True) candidate."""
        if not self.candidates:
            return
        idx = len(self.candidates) - 1 if to_end else 0
        self._select(idx)

    def _on_crop_overlay_changed(self, state: int) -> None:
        """Toggle the crop overlay and update the crop size from preset."""
        show = state != 0
        preset = PRESETS.get(self.combo_preset.currentText())
        self.preview.set_overlays(crop=show, crop_size=preset)

    def _auto_select_best(self) -> None:
        """Select the highest-scoring candidate."""
        if not self.candidates:
            return
        # Temporarily switch sort to Score
        self.combo_sort.blockSignals(True)
        self.combo_sort.setCurrentText("Score")
        self.combo_sort.blockSignals(False)
        self._apply_sort()
        self._gallery_cards.clear()
        self._refresh_gallery()
        self._select(0)
        self.statusBar().showMessage("Auto-selected best candidate.", 3000)

    def _seek_time(self, ts: float) -> None:
        if not self.video_path:
            return
        cap = cv2.VideoCapture(self.video_path)
        try:
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ret, frame = cap.read()
        finally:
            cap.release()
        if not ret or frame is None:
            self.statusBar().showMessage(f"Could not read frame at {format_time(ts)}", 3000)
            return
        if not prefilter_frame(frame):
            self.statusBar().showMessage(
                f"Frame at {format_time(ts)} failed quality prefilter (too dark/bright/flat/blurry)", 4000
            )
            return
        w = self._all_profiles.get(self.combo_algo.currentText(),
                                    ALGORITHM_PROFILES["General (Balanced)"])
        face_score, faces = score_faces(frame)
        small, gray = downscale_for_scoring(frame, 720)
        scores = {n: s(small, gray) for n, s in SCORERS.items()}
        scores["faces"] = face_score
        total = sum(scores.get(k, 0.0) * w.get(k, 0.0) for k in w)
        cand = Candidate(frame_bgr=frame, timestamp=float(ts),
                         total_score=total, breakdown=scores, faces=faces,
                         video_path=self.video_path)
        self.candidates.insert(0, cand)
        self._refresh_gallery()
        self._select(0)
        self.statusBar().showMessage(f"Added manual frame @ {format_time(ts)}", 3000)

    # ════════════════════════════════════════════════════════════════════
    # RE-ANALYZE NEIGHBORHOOD
    # ════════════════════════════════════════════════════════════════════
    def _reanalyze_idx(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.candidates):
            return
        cand = self.candidates[idx]
        center = cand.timestamp
        radius = SETTINGS.reanalyze_radius
        n = SETTINGS.reanalyze_samples
        times = list(np.linspace(max(0, center - radius), center + radius, n))
        self.statusBar().showMessage(
            f"Re-analyzing ±{radius}s around {format_time(center)}…", 4000
        )
        self._start_analysis(append=True, sample_times=times)

    def _reanalyze_current(self) -> None:
        if 0 <= self.selected_idx < len(self.candidates):
            self._reanalyze_idx(self.selected_idx)

    # ════════════════════════════════════════════════════════════════════
    # INFO TAB
    # ════════════════════════════════════════════════════════════════════
    def _refresh_info_video(self, info: Dict) -> None:
        if not info:
            return
        path = info.get("path", "")
        self._info_file.setText(Path(path).name if path else "—")
        self._info_duration.setText(format_duration(info.get("duration", 0)))
        w = info.get("width"); h = info.get("height")
        self._info_resolution.setText(f"{w}×{h}" if w and h else "—")
        fps = info.get("fps")
        self._info_fps.setText(f"{fps:.2f}" if fps else "—")
        tf = info.get("total_frames")
        self._info_total_frames.setText(str(tf) if tf else "—")

    def _refresh_info_cand(self, cand: Optional[Candidate]) -> None:
        all_keys = ["rank", "timestamp", "score", "faces", "sharpness",
                      "contrast", "brightness", "composition", "entropy",
                      "exposure", "complexity", "harmony", "center",
                      "skin", "range"]
        if cand is None:
            for k in all_keys:
                attr = getattr(self, f"_info_{k}", None)
                if attr:
                    attr.setText("—")
            return
        b = cand.breakdown
        self._info_rank.setText(f"#{self.selected_idx + 1}")
        self._info_timestamp.setText(format_time(cand.timestamp))
        self._info_score.setText(f"{cand.total_score:.3f}")
        self._info_faces.setText(str(len(cand.faces)))
        self._info_sharpness.setText(f"{b.get('sharpness', 0):.3f}")
        self._info_contrast.setText(f"{b.get('contrast', 0):.3f}")
        self._info_brightness.setText(f"{b.get('brightness', 0):.3f}")
        self._info_composition.setText(f"{b.get('composition', 0):.3f}")
        if hasattr(self, '_info_entropy'):
            self._info_entropy.setText(f"{b.get('entropy', 0):.3f}")
        if hasattr(self, '_info_exposure'):
            self._info_exposure.setText(f"{b.get('exposure_quality', 0):.3f}")
        if hasattr(self, '_info_complexity'):
            self._info_complexity.setText(f"{b.get('visual_complexity', 0):.3f}")
        if hasattr(self, '_info_harmony'):
            self._info_harmony.setText(f"{b.get('color_harmony', 0):.3f}")
        if hasattr(self, '_info_center'):
            self._info_center.setText(f"{b.get('center_weight', 0):.3f}")
        if hasattr(self, '_info_skin'):
            self._info_skin.setText(f"{b.get('skin_tone', 0):.3f}")
        if hasattr(self, '_info_range'):
            self._info_range.setText(f"{b.get('dynamic_range', 0):.3f}")

    # ════════════════════════════════════════════════════════════════════
    # ALGORITHM / WEIGHTS
    # ════════════════════════════════════════════════════════════════════
    def _get_active_weights(self) -> Dict[str, float]:
        return self._all_profiles.get(
            self.combo_algo.currentText(), ALGORITHM_PROFILES["General (Balanced)"]
        )

    def _change_algo(self, name: str) -> None:
        if not self.candidates:
            return
        w = self._all_profiles.get(name, ALGORITHM_PROFILES["General (Balanced)"])
        for c in self.candidates:
            c.total_score = sum(c.breakdown.get(k, 0.0) * w.get(k, 0.0) for k in w)
        self._apply_sort()
        self._gallery_cards.clear()
        self._refresh_gallery()
        if 0 <= self.selected_idx < len(self.candidates):
            self._select(self.selected_idx)
        self.statusBar().showMessage(f"Re-sorted using {name}", 3000)

    def _edit_weights(self) -> None:
        name = self.combo_algo.currentText()
        weights = self._all_profiles.get(name, {})
        dlg = WeightsEditorDialog(self, name, weights, list(self._all_profiles.keys()))
        if dlg.exec() == WeightsEditorDialog.DialogCode.Accepted:
            new_name = dlg.get_profile_name()
            new_weights = dlg.get_weights()
            self._all_profiles[new_name] = new_weights
            # If it's a new/changed custom profile, persist it
            if new_name not in ALGORITHM_PROFILES:
                SETTINGS.save_custom_profile(new_name, new_weights)
            # Update combo
            self.combo_algo.blockSignals(True)
            if self.combo_algo.findText(new_name) < 0:
                self.combo_algo.addItem(new_name)
            self.combo_algo.setCurrentText(new_name)
            self.combo_algo.blockSignals(False)
            self._change_algo(new_name)
            self.statusBar().showMessage(f"Saved profile '{new_name}'", 3000)

    # ════════════════════════════════════════════════════════════════════
    # CONTACT SHEET EXPORT
    # ════════════════════════════════════════════════════════════════════
    def _export_contact_sheet(self) -> None:
        if not self.candidates:
            QMessageBox.information(self, "No candidates", "Run analysis first.")
            return
        video_name = Path(self.video_path).stem if self.video_path else ""
        dlg = ContactSheetDialog(self, self.candidates, video_name)
        dlg.exec()

    # ════════════════════════════════════════════════════════════════════
    # SAVE
    # ════════════════════════════════════════════════════════════════════
    def _output_dir(self) -> Path:
        """Resolve the best output directory for saving thumbnails.

        Always saves to a ``thumbnails/`` subfolder in CWD.
        """
        out = Path.cwd() / "thumbnails"
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _save(self) -> None:
        if self.selected_idx < 0 or self.selected_idx >= len(self.candidates):
            return
        cand = self.candidates[self.selected_idx]
        out_dir = self._output_dir()
        rank = self.selected_idx + 1
        fname = self._format_filename(cand, rank)
        self._save_image(cand, path=str(out_dir / fname))

    def _format_filename(self, cand: Candidate, rank: int) -> str:
        """Render the filename template for a candidate."""
        video_name = Path(self.video_path).stem if self.video_path else "video"
        preset_name = self.combo_preset.currentText()
        try:
            return self._filename_template.format(
                video=video_name,
                timestamp=format_time(cand.timestamp).replace(":", "-"),
                ts_seconds=f"{cand.timestamp:.3f}",
                score=f"{cand.total_score:.3f}",
                rank=rank,
                preset=preset_name,
            )
        except (KeyError, ValueError) as e:
            logger.warning(f"Bad filename template: {e}")
            return f"thumb_{format_time(cand.timestamp).replace(':', '-')}.jpg"

    def _batch_save(self) -> None:
        starred = [c for c in self.candidates if c.starred]
        if not starred:
            QMessageBox.information(self, "Info", "No starred images to save.")
            return
        folder = str(self._output_dir())
        for i, c in enumerate(starred, start=1):
            fname = self._format_filename(c, i)
            self._save_image(c, path=os.path.join(folder, fname))
        self.statusBar().showMessage(f"Saved {len(starred)} images to {folder}", 5000)

    def _save_all(self) -> None:
        """Save all current candidates (after sort/filter) to a folder."""
        if not self.candidates:
            QMessageBox.information(self, "Info", "No candidates to save.")
            return
        folder = str(self._output_dir())
        for i, c in enumerate(self.candidates, start=1):
            fname = self._format_filename(c, i)
            self._save_image(c, path=os.path.join(folder, fname))
        self.statusBar().showMessage(f"Saved {len(self.candidates)} images to {folder}", 5000)

    @staticmethod
    def _unique_path(path: str) -> str:
        """If *path* already exists, append ``_2``, ``_3``, etc. before the extension."""
        p = Path(path)
        if not p.exists():
            return path
        stem = p.stem
        suffix = p.suffix
        parent = p.parent
        n = 2
        while True:
            candidate = parent / f"{stem}_{n}{suffix}"
            if not candidate.exists():
                return str(candidate)
            n += 1

    def _save_image(self, cand: Candidate, path: Optional[str] = None) -> None:
        frame = cand.ensure_frame()
        if frame is None:
            QMessageBox.critical(self, "Save failed", "Could not load the frame from disk.")
            return
        pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        preset = PRESETS.get(self.combo_preset.currentText())
        if preset:
            pil = fit_crop_pil(pil, preset)

        if not path:
            rank = self.selected_idx + 1 if self.candidates and cand in self.candidates else 1
            default_name = self._format_filename(cand, rank)
            out_dir = self._output_dir()
            path = str(out_dir / default_name)

        path = self._unique_path(path)
        try:
            ext = Path(path).suffix.lower()
            if ext in (".png",):
                fmt = "PNG"
                kwargs = {"optimize": True}
            elif ext in (".webp",):
                fmt = "WEBP"
                kwargs = {"quality": SETTINGS.save_quality}
            else:
                preferred = SETTINGS.save_format
                if preferred == "PNG":
                    fmt = "PNG"
                    kwargs = {"optimize": True}
                    if not path.lower().endswith(".png"):
                        path = path.rsplit(".", 1)[0] + ".png"
                        path = self._unique_path(path)
                elif preferred == "WebP":
                    fmt = "WEBP"
                    kwargs = {"quality": SETTINGS.save_quality}
                    if not path.lower().endswith(".webp"):
                        path = path.rsplit(".", 1)[0] + ".webp"
                        path = self._unique_path(path)
                else:
                    fmt = "JPEG"
                    kwargs = {"quality": SETTINGS.save_quality}
                    if not path.lower().endswith((".jpg", ".jpeg")):
                        path = path.rsplit(".", 1)[0] + ".jpg"
                        path = self._unique_path(path)
            pil.save(path, fmt, **kwargs)
            self.statusBar().showMessage(
                f"Saved to {path} ({fmt}, quality={kwargs.get('quality', 'lossless')})", 4000
            )
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def _save_as_preset(self, payload: object) -> None:
        """Save a frame cropped to the selected output preset."""
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        idx, (pw, ph) = payload
        if idx < 0 or idx >= len(self.candidates):
            return
        cand = self.candidates[idx]
        frame = cand.ensure_frame()
        if frame is None:
            return
        pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        cropped = fit_crop_pil(pil, (pw, ph))
        try:
            rank = idx + 1
            fname = f"{Path(self.video_path or 'video').stem}_rank{rank:02d}_{pw}x{ph}.png"
            out_dir = self._output_dir()
            path = self._unique_path(str(out_dir / fname))
            cropped.save(path, "PNG", optimize=True)
            self.statusBar().showMessage(f"Saved preset to {path}", 4000)
        except Exception as e:
            self.statusBar().showMessage(f"Save failed: {e}", 4000)

    # ════════════════════════════════════════════════════════════════════
    # TOGGLES & HELP
    # ════════════════════════════════════════════════════════════════════
    def _toggle_grid(self, state: bool) -> None:
        self.preview.set_overlays(grid=state)

    def _toggle_faces(self, state: bool) -> None:
        self.preview.set_overlays(faces=state)

    def _show_shortcuts(self) -> None:
        ShortcutHelpDialog(self).exec()

    def _show_about(self) -> None:
        AboutDialog(self).exec()

    # ════════════════════════════════════════════════════════════════════
    # PREFERENCES
    # ════════════════════════════════════════════════════════════════════
    def _show_preferences(self) -> None:
        dlg = PreferencesDialog(
            self,
            theme=self._theme,
            card_size=self._card_size,
            filename_template=self._filename_template,
            auto_free_memory=self._auto_free_memory,
            save_quality=SETTINGS.save_quality,
            save_format=SETTINGS.save_format,
            reanalyze_radius=SETTINGS.reanalyze_radius,
            reanalyze_samples=SETTINGS.reanalyze_samples,
        )
        dlg.set_callbacks(
            on_theme_change=self._apply_theme_from_pref,
            on_card_size_change=self._apply_card_size_from_pref,
            on_template_change=self._apply_template_from_pref,
            on_auto_free_change=self._apply_auto_free_from_pref,
            on_save_quality_change=lambda v: setattr(SETTINGS, "save_quality", v),
            on_save_format_change=lambda v: setattr(SETTINGS, "save_format", v),
            on_reanalyze_radius_change=lambda v: setattr(SETTINGS, "reanalyze_radius", v),
            on_reanalyze_samples_change=lambda v: setattr(SETTINGS, "reanalyze_samples", v),
        )
        if dlg.exec() == PreferencesDialog.DialogCode.Accepted:
            self._theme = dlg.theme
            self._card_size = dlg.card_size
            self._filename_template = dlg.filename_template
            self._auto_free_memory = dlg.auto_free_memory
            SETTINGS.save_quality = dlg.save_quality
            SETTINGS.save_format = dlg.save_format
            SETTINGS.reanalyze_radius = dlg.reanalyze_radius
            SETTINGS.reanalyze_samples = dlg.reanalyze_samples
            self._apply_theme()
            self.combo_card_size.blockSignals(True)
            self.combo_card_size.setCurrentText(self._card_size)
            self.combo_card_size.blockSignals(False)
            self._gallery_cards.clear()
            self._refresh_gallery()

    def _apply_theme_from_pref(self, theme: str) -> None:
        self._theme = theme
        self._apply_theme()

    def _apply_card_size_from_pref(self, size: str) -> None:
        self._card_size = size
        self.combo_card_size.blockSignals(True)
        self.combo_card_size.setCurrentText(size)
        self.combo_card_size.blockSignals(False)
        self._gallery_cards.clear()
        self._refresh_gallery()

    def _apply_template_from_pref(self, template: str) -> None:
        self._filename_template = template

    def _apply_auto_free_from_pref(self, value: bool) -> None:
        self._auto_free_memory = value

    # ════════════════════════════════════════════════════════════════════
    # MULTI-SELECT
    # ════════════════════════════════════════════════════════════════════
    def _on_multi_select_toggled(self, idx: int, _ctrl: bool) -> None:
        if idx < 0 or idx >= len(self.candidates):
            return
        cand = self.candidates[idx]
        if id(cand) in self._multi_selected:
            self._multi_selected.discard(id(cand))
        else:
            self._multi_selected.add(id(cand))
        # Update the card's visual state
        card = self._gallery_cards.get(id(cand))
        if card is not None:
            card.set_multi_selected(id(cand) in self._multi_selected)
        self._update_multi_select_bar()

    def _update_multi_select_bar(self) -> None:
        count = len(self._multi_selected)
        self.ms_count_lbl.setText(f"{count} selected")
        self.multi_select_bar.setVisible(count > 0)

    def _multi_apply(self, action: str) -> None:
        """Apply star/unstar to all multi-selected candidates."""
        for cand in self.candidates:
            if id(cand) in self._multi_selected:
                if action == "star":
                    cand.starred = True
                elif action == "unstar":
                    cand.starred = False
                card = self._gallery_cards.get(id(cand))
                if card is not None:
                    card.refresh_star()
        self._save_starred_state()
        self.statusBar().showMessage(
            f"{'Starred' if action == 'star' else 'Unstarred'} {len(self._multi_selected)} candidates.",
            3000
        )

    def _clear_multi_select(self) -> None:
        self._multi_selected.clear()
        for card in self._gallery_cards.values():
            card.set_multi_selected(False)
        self._update_multi_select_bar()

    # ════════════════════════════════════════════════════════════════════
    # SAVE / LOAD CANDIDATE LIST (JSON)
    # ════════════════════════════════════════════════════════════════════
    def _save_candidate_list(self) -> None:
        if not self.candidates:
            QMessageBox.information(self, "No candidates", "Run analysis first.")
            return
        default_name = (
            Path(self.video_path).stem if self.video_path else "candidates"
        ) + ".vtp.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Candidate List", default_name, "VTP JSON (*.json)"
        )
        if not path:
            return
        try:
            save_candidates_to_json(path, self.candidates, self.video_path or "", self.video_info)
            self.statusBar().showMessage(f"Saved {len(self.candidates)} candidates to {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def _load_candidate_list(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Candidate List", SETTINGS.last_dir,
            "VTP JSON (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            cands, video_path, video_info = load_candidates_from_json(path)
        except Exception as e:
            QMessageBox.critical(self, "Load failed", str(e))
            return

        # If the video path is set and exists, open it; otherwise prompt
        if video_path and Path(video_path).exists():
            self._open_file_path(video_path)
        else:
            QMessageBox.warning(
                self, "Video not found",
                f"The original video could not be found:\n{video_path}\n\n"
                "Candidates loaded but frames cannot be displayed until you "
                "open the matching video file."
            )

        self.candidates = cands
        self.video_info = video_info
        self._gallery_cards.clear()
        THUMBS.invalidate()
        self._refresh_gallery()
        self._refresh_info_video(video_info)
        if cands:
            self._select(0)
        self.statusBar().showMessage(
            f"Loaded {len(cands)} candidates from {path}", 4000
        )

    # ════════════════════════════════════════════════════════════════════
    # SHUTDOWN
    # ════════════════════════════════════════════════════════════════════
    def closeEvent(self, e) -> None:  # type: ignore[override]
        self._save_settings()
        self._save_starred_state()
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait(2000)
        super().closeEvent(e)

# ==================================================================
# app.py
# ==================================================================

"""Video Thumbnail Picker — entry point.

Run with:
    python app.py
"""

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


def main() -> int:
    log.info("Initializing application…")
    app = QApplication(sys.argv)
    app.setOrganizationName("ThumbnailPicker")
    app.setApplicationName("Video Thumbnail Picker")
    app.setApplicationVersion("2.1")

    # Pre-warm the Haar cascades so the first analysis isn't slow.
    # This runs in the main thread but only takes ~100 ms.
    try:
        _get_cascades()
    except Exception as e:
        log.warning(f"Could not pre-warm cascades: {e}")

    win = MainWindow()
    win.show()

    log.info("GUI launched. Ready for input.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())