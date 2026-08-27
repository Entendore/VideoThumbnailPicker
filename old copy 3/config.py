"""Application configuration: presets, scoring profiles, theme, stylesheet.

All static configuration lives here so the rest of the codebase can stay
focused on behaviour rather than tuning constants.
"""
from __future__ import annotations

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
        "sharpness": 0.14, "colorfulness": 0.10, "contrast": 0.08, "brightness": 0.06,
        "entropy": 0.08, "composition": 0.10, "skin_tone": 0.05, "faces": 0.12,
        "motion": 0.05, "exposure_quality": 0.06, "dynamic_range": 0.04,
        "visual_complexity": 0.04, "color_harmony": 0.04, "center_weight": 0.04,
    },
    "Face Focus (Portrait)": {
        "sharpness": 0.20, "faces": 0.40, "skin_tone": 0.10, "center_weight": 0.15,
        "brightness": 0.05, "exposure_quality": 0.05, "composition": 0.05,
        "contrast": 0.0, "colorfulness": 0.0, "entropy": 0.0,
        "motion": 0.0, "dynamic_range": 0.0, "visual_complexity": 0.0, "color_harmony": 0.0,
    },
    "Scenery (Landscape)": {
        "composition": 0.25, "color_harmony": 0.20, "dynamic_range": 0.15,
        "sharpness": 0.15, "visual_complexity": 0.10, "exposure_quality": 0.05,
        "contrast": 0.10, "faces": 0.0, "skin_tone": 0.0, "motion": 0.0,
        "brightness": 0.0, "center_weight": 0.0, "colorfulness": 0.0, "entropy": 0.0,
    },
    "Action (Motion)": {
        "motion": 0.40, "sharpness": 0.20, "contrast": 0.15, "dynamic_range": 0.10,
        "visual_complexity": 0.10, "faces": 0.05, "brightness": 0.0, "colorfulness": 0.0,
        "entropy": 0.0, "composition": 0.0, "skin_tone": 0.0, "exposure_quality": 0.0,
        "color_harmony": 0.0, "center_weight": 0.0,
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
COMPARE_THUMB_W: int = 280           # compare-tab thumbnail width
COMPARE_THUMB_H: int = 180           # compare-tab thumbnail height
GALLERY_COLUMNS: int = 3             # number of columns in the gallery grid
ANALYSIS_BATCH_INTERVAL_MS: int = 80 # debounce interval for batched candidate_ready emissions
DEFAULT_FILMSTRIP_FRAMES: int = 200  # number of frames in the filmstrip overview

# ────────────────────────────────────────────────────────────────────────────
# Gallery Sort Options
# ────────────────────────────────────────────────────────────────────────────
# Each entry: (display_name, sort_key_or_None_for_score, reverse_bool)
SORT_OPTIONS = [
    ("Score",          None,              True),   # by total_score descending
    ("Time",           "timestamp",       False),  # by timestamp ascending
    ("Sharpness",      "sharpness",       True),
    ("Contrast",       "contrast",        True),
    ("Brightness",     "brightness",      True),
    ("Composition",    "composition",     True),
    ("Faces",          "faces",           True),
    ("Colorfulness",   "colorfulness",    True),
    ("Dynamic Range",  "dynamic_range",   True),
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
    """Return a dict of color overrides for the light theme (Catppuccin Latte)."""
    return {
        "C_BG":       "#eff1f5",
        "C_SURFACE":  "#e6e9ef",
        "C_CARD":     "#dce0e8",
        "C_OVERLAY":  "#bcc0cc",
        "C_TEXT":     "#4c4f69",
        "C_SUBTEXT":  "#6c6f85",
        "C_BLUE":     "#1e66f5",
        "C_GREEN":    "#40a02b",
        "C_YELLOW":   "#df8e1d",
        "C_PEACH":    "#fe640b",
        "C_RED":      "#d20f39",
        "C_MAUVE":    "#8839ef",
        "C_TEAL":     "#179299",
        "C_LAVENDER": "#7287fd",
        "C_PINK":     "#ea76cb",
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
        "C_BLUE": C_BLUE, "C_GREEN": C_GREEN, "C_YELLOW": C_YELLOW,
        "C_PEACH": C_PEACH, "C_RED": C_RED, "C_MAUVE": C_MAUVE,
        "C_TEAL": C_TEAL, "C_LAVENDER": C_LAVENDER, "C_PINK": C_PINK,
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
    padding:12px 10px 10px 10px; font-weight:bold; color:{c['C_LAVENDER']};
    background:{c['C_SURFACE']};
}}
QGroupBox::title {{ subcontrol-origin:margin; left:12px; padding:0 6px; }}

QPushButton {{
    background:{c['C_OVERLAY']}; color:{c['C_TEXT']}; border:none; border-radius:5px;
    padding:7px 14px; font-weight:600;
}}
QPushButton:hover    {{ background:{c['C_BLUE']}; color:{c['C_BG']}; }}
QPushButton:pressed  {{ background:{c['C_MAUVE']}; color:{c['C_BG']}; }}
QPushButton#btnGreen   {{ background:{c['C_GREEN']}; color:{c['C_BG']}; }}
QPushButton#btnGreen:hover   {{ background:{c['C_TEAL']}; color:{c['C_BG']}; }}
QPushButton#btnRed     {{ background:{c['C_RED']};   color:{c['C_BG']}; }}
QPushButton#btnRed:hover     {{ background:{c['C_PEACH']}; color:{c['C_BG']}; }}
QPushButton#btnPrimary {{ background:{c['C_BLUE']}; color:{c['C_BG']}; }}
QPushButton#btnPrimary:hover {{ background:{c['C_LAVENDER']}; color:{c['C_BG']}; }}
QPushButton:disabled   {{ background:{c['C_OVERLAY']}; color:{c['C_SUBTEXT']}; }}

QComboBox {{ background:{c['C_CARD']}; border:1px solid {c['C_OVERLAY']}; border-radius:5px; padding:5px 10px; min-height:18px; }}
QComboBox:hover {{ border-color:{c['C_BLUE']}; }}
QComboBox::drop-down {{ border:none; width:22px; }}
QComboBox QAbstractItemView {{ background:{c['C_CARD']}; selection-background-color:{c['C_BLUE']}; outline:none; }}

QSpinBox {{ background:{c['C_CARD']}; border:1px solid {c['C_OVERLAY']}; border-radius:5px; padding:4px 6px; }}
QSpinBox:hover {{ border-color:{c['C_BLUE']}; }}

QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{ background:{c['C_SURFACE']}; width:10px; border-radius:5px; margin:2px; }}
QScrollBar::handle:vertical {{ background:{c['C_OVERLAY']}; border-radius:5px; min-height:24px; }}
QScrollBar::handle:vertical:hover {{ background:{c['C_BLUE']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; }}
QScrollBar:horizontal {{ background:{c['C_SURFACE']}; height:10px; border-radius:5px; margin:2px; }}
QScrollBar::handle:horizontal {{ background:{c['C_OVERLAY']}; border-radius:5px; min-width:24px; }}
QScrollBar::handle:horizontal:hover {{ background:{c['C_BLUE']}; }}

QStatusBar {{ background:{c['C_SURFACE']}; color:{c['C_SUBTEXT']}; font-weight:bold; border-top:1px solid {c['C_OVERLAY']}; }}
QStatusBar::item {{ border:none; }}

QSlider::groove:horizontal {{ height:4px; background:{c['C_OVERLAY']}; border-radius:2px; }}
QSlider::handle:horizontal {{ background:{c['C_BLUE']}; width:14px; height:14px; margin:-5px 0; border-radius:7px; }}
QSlider::handle:horizontal:hover {{ background:{c['C_LAVENDER']}; }}

QCheckBox::indicator {{ width:14px; height:14px; border-radius:3px; border:1px solid {c['C_OVERLAY']}; background:{c['C_CARD']}; }}
QCheckBox::indicator:checked {{ background:{c['C_BLUE']}; border-color:{c['C_BLUE']}; }}

QProgressBar {{ border:none; border-radius:5px; background:{c['C_OVERLAY']}; text-align:center; color:{c['C_BG']}; font-weight:bold; min-height:18px; }}
QProgressBar::chunk {{ background:{c['C_TEAL']}; border-radius:4px; }}

QLabel#LblTitle   {{ font-size:15px; font-weight:bold; color:{c['C_LAVENDER']}; }}
QLabel#LblSection {{ font-size:11px; font-weight:bold; color:{c['C_SUBTEXT']}; letter-spacing:1px; }}
QLabel#LblValue   {{ font-size:12px; color:{c['C_TEXT']}; font-family:"JetBrains Mono","Consolas",monospace; }}

QFrame#Card       {{ background:{c['C_CARD']};    border-radius:8px; }}
QFrame#CardHover  {{ background:{c['C_CARD']};    border-radius:8px; border:1px solid transparent; }}
QFrame#CardHover:hover {{ border-color:{c['C_BLUE']}; }}
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
QMenu::item:selected {{ background:{c['C_BLUE']}; color:{c['C_BG']}; }}
"""

# ────────────────────────────────────────────────────────────────────────────
# Theme (Catppuccin Mocha)
# ────────────────────────────────────────────────────────────────────────────
C_BG       = "#1e1e2e"
C_SURFACE  = "#2a2a3c"
C_CARD     = "#313244"
C_OVERLAY  = "#45475a"
C_TEXT     = "#cdd6f4"
C_SUBTEXT  = "#a6adc8"
C_BLUE     = "#89b4fa"
C_GREEN    = "#a6e3a1"
C_YELLOW   = "#f9e2af"
C_PEACH    = "#fab387"
C_RED      = "#f38ba8"
C_MAUVE    = "#cba6f7"
C_TEAL     = "#94e2d5"
C_LAVENDER = "#b4befe"
C_PINK     = "#f5c2e7"

STYLESHEET = f"""
QMainWindow {{ background:{C_BG}; }}
QWidget {{ color:{C_TEXT}; font-family:"Segoe UI","SF Pro","Inter",sans-serif; font-size:12px; }}
QToolTip {{ background:{C_OVERLAY}; color:{C_TEXT}; border:1px solid {C_SURFACE}; padding:4px 6px; border-radius:4px; }}

QGroupBox {{
    border:1px solid {C_OVERLAY}; border-radius:6px; margin-top:14px;
    padding:12px 10px 10px 10px; font-weight:bold; color:{C_LAVENDER};
    background:{C_SURFACE};
}}
QGroupBox::title {{ subcontrol-origin:margin; left:12px; padding:0 6px; }}

QPushButton {{
    background:{C_OVERLAY}; color:{C_TEXT}; border:none; border-radius:5px;
    padding:7px 14px; font-weight:600;
}}
QPushButton:hover    {{ background:{C_BLUE}; color:{C_BG}; }}
QPushButton:pressed  {{ background:{C_MAUVE}; color:{C_BG}; }}
QPushButton#btnGreen   {{ background:{C_GREEN}; color:{C_BG}; }}
QPushButton#btnGreen:hover   {{ background:{C_TEAL}; color:{C_BG}; }}
QPushButton#btnRed     {{ background:{C_RED};   color:{C_BG}; }}
QPushButton#btnRed:hover     {{ background:{C_PEACH}; color:{C_BG}; }}
QPushButton#btnPrimary {{ background:{C_BLUE}; color:{C_BG}; }}
QPushButton#btnPrimary:hover {{ background:{C_LAVENDER}; color:{C_BG}; }}
QPushButton:disabled   {{ background:{C_OVERLAY}; color:{C_SUBTEXT}; }}

QComboBox {{ background:{C_CARD}; border:1px solid {C_OVERLAY}; border-radius:5px; padding:5px 10px; min-height:18px; }}
QComboBox:hover {{ border-color:{C_BLUE}; }}
QComboBox::drop-down {{ border:none; width:22px; }}
QComboBox QAbstractItemView {{ background:{C_CARD}; selection-background-color:{C_BLUE}; outline:none; }}

QSpinBox {{ background:{C_CARD}; border:1px solid {C_OVERLAY}; border-radius:5px; padding:4px 6px; }}
QSpinBox:hover {{ border-color:{C_BLUE}; }}

QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{ background:{C_SURFACE}; width:10px; border-radius:5px; margin:2px; }}
QScrollBar::handle:vertical {{ background:{C_OVERLAY}; border-radius:5px; min-height:24px; }}
QScrollBar::handle:vertical:hover {{ background:{C_BLUE}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; }}
QScrollBar:horizontal {{ background:{C_SURFACE}; height:10px; border-radius:5px; margin:2px; }}
QScrollBar::handle:horizontal {{ background:{C_OVERLAY}; border-radius:5px; min-width:24px; }}
QScrollBar::handle:horizontal:hover {{ background:{C_BLUE}; }}

QStatusBar {{ background:{C_SURFACE}; color:{C_SUBTEXT}; font-weight:bold; border-top:1px solid {C_OVERLAY}; }}
QStatusBar::item {{ border:none; }}

QSlider::groove:horizontal {{ height:4px; background:{C_OVERLAY}; border-radius:2px; }}
QSlider::handle:horizontal {{ background:{C_BLUE}; width:14px; height:14px; margin:-5px 0; border-radius:7px; }}
QSlider::handle:horizontal:hover {{ background:{C_LAVENDER}; }}

QCheckBox::indicator {{ width:14px; height:14px; border-radius:3px; border:1px solid {C_OVERLAY}; background:{C_CARD}; }}
QCheckBox::indicator:checked {{ background:{C_BLUE}; border-color:{C_BLUE}; }}

QProgressBar {{ border:none; border-radius:5px; background:{C_OVERLAY}; text-align:center; color:{C_BG}; font-weight:bold; min-height:18px; }}
QProgressBar::chunk {{ background:{C_TEAL}; border-radius:4px; }}

QLabel#LblTitle   {{ font-size:15px; font-weight:bold; color:{C_LAVENDER}; }}
QLabel#LblSection {{ font-size:11px; font-weight:bold; color:{C_SUBTEXT}; letter-spacing:1px; }}
QLabel#LblValue   {{ font-size:12px; color:{C_TEXT}; font-family:"JetBrains Mono","Consolas",monospace; }}

QFrame#Card       {{ background:{C_CARD};    border-radius:8px; }}
QFrame#CardHover  {{ background:{C_CARD};    border-radius:8px; border:1px solid transparent; }}
QFrame#CardHover:hover {{ border-color:{C_BLUE}; }}
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
QMenu::item:selected {{ background:{C_BLUE}; color:{C_BG}; }}
"""
