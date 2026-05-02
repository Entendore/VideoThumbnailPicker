from typing import Dict, Tuple, Optional

# ────────────────────────────────────────────────────────────────────────────
# Constants & Theme
# ────────────────────────────────────────────────────────────────────────────

PRESETS: Dict[str, Optional[Tuple[int, int]]] = {
    "Original": None,
    "YouTube (1280×720)": (1280, 720),
    "YouTube (1920×1080)": (1920, 1080),
    "Instagram Square": (1080, 1080),
    "Instagram Portrait": (1080, 1350),
    "Twitter Header": (1500, 500),
    "TikTok": (1080, 1920),
}

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

CRIT_LABELS = {
    "sharpness": "Sharpness", "colorfulness": "Colour", "contrast": "Contrast",
    "brightness": "Bright", "entropy": "Entropy", "composition": "Compos.",
    "skin_tone": "Skin", "faces": "Faces", "motion": "Motion",
    "exposure_quality": "Exposure", "dynamic_range": "Range",
    "visual_complexity": "Complex", "color_harmony": "Harmony",
    "center_weight": "Center",
}

# Theme (Catppuccin Mocha)
C_BG       = "#1e1e2e"; C_SURFACE  = "#2a2a3c"; C_CARD     = "#313244"
C_OVERLAY  = "#45475a"; C_TEXT     = "#cdd6f4"; C_SUBTEXT  = "#a6adc8"
C_BLUE     = "#89b4fa"; C_GREEN    = "#a6e3a1"; C_YELLOW   = "#f9e2af"
C_PEACH    = "#fab387"; C_RED      = "#f38ba8"; C_MAUVE    = "#cba6f7"
C_TEAL     = "#94e2d5"; C_LAVENDER = "#b4befe"; C_PINK     = "#f5c2e7"

STYLESHEET = f"""
QMainWindow {{ background:{C_BG}; }}
QWidget {{ color:{C_TEXT}; font-family:"Segoe UI","SF Pro",sans-serif; font-size:12px; }}
QGroupBox {{ border:1px solid {C_OVERLAY}; border-radius:6px; margin-top:12px; padding:10px; font-weight:bold; color:{C_LAVENDER}; background:{C_SURFACE}; }}
QGroupBox::title {{ subcontrol-origin:margin; left:10px; padding:0 4px; }}
QPushButton {{ background:{C_OVERLAY}; color:{C_TEXT}; border:none; border-radius:4px; padding:6px 12px; font-weight:bold; }}
QPushButton:hover {{ background:{C_BLUE}; color:{C_BG}; }}
QPushButton#btnGreen {{ background:{C_GREEN}; color:{C_BG}; }}
QPushButton#btnRed {{ background:{C_RED}; color:{C_BG}; }}
QPushButton#btnPrimary {{ background:{C_BLUE}; color:{C_BG}; }}
QPushButton:disabled {{ background:{C_OVERLAY}; color:{C_SUBTEXT}; }}
QComboBox {{ background:{C_CARD}; border:1px solid {C_OVERLAY}; border-radius:4px; padding:4px 10px; }}
QComboBox::drop-down {{ border:none; width:20px; }}
QComboBox QAbstractItemView {{ background:{C_CARD}; selection-background-color:{C_BLUE}; }}
QSpinBox {{ background:{C_CARD}; border:1px solid {C_OVERLAY}; border-radius:4px; padding:4px; }}
QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{ background:{C_SURFACE}; width:10px; border-radius:5px; }}
QScrollBar::handle:vertical {{ background:{C_OVERLAY}; border-radius:5px; min-height:20px; }}
QStatusBar {{ background:{C_SURFACE}; color:{C_SUBTEXT}; font-weight:bold; border-top: 1px solid {C_OVERLAY}; }}
QStatusBar::item {{ border: none; }}
QSlider::groove:horizontal {{ height:4px; background:{C_OVERLAY}; border-radius:2px; }}
QSlider::handle:horizontal {{ background:{C_BLUE}; width:14px; height:14px; margin:-5px 0; border-radius:7px; }}
QCheckBox::indicator {{ width:14px; height:14px; border-radius:3px; border:1px solid {C_OVERLAY}; background:{C_CARD}; }}
QCheckBox::indicator:checked {{ background:{C_BLUE}; border-color:{C_BLUE}; }}
QProgressBar {{ border:none; border-radius:4px; background:{C_OVERLAY}; text-align:center; color:{C_BG}; font-weight:bold; }}
QProgressBar::chunk {{ background:{C_TEAL}; border-radius:3px; }}
QLabel#LblTitle {{ font-size:14px; font-weight:bold; color:{C_LAVENDER}; }}
QFrame#Card {{ background:{C_CARD}; border-radius:6px; }}
QTabWidget::pane {{ border: 1px solid {C_OVERLAY}; border-radius:6px; background: {C_SURFACE}; }}
QTabBar::tab {{ background: {C_CARD}; color: {C_SUBTEXT}; padding: 8px 16px; border-top-left-radius: 4px; border-top-right-radius: 4px; }}
QTabBar::tab:selected {{ background: {C_SURFACE}; color: {C_TEXT}; font-weight: bold; }}
"""