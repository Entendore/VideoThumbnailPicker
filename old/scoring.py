#!/usr/bin/env python3
"""
scoring.py — Scoring engine for Video Thumbnail Picker v5
==========================================================
Contains constants, scoring functions, audio/scene analysis, the Candidate
dataclass, and the background AnalysisThread.

This module is imported by ``main.py`` and ``widgets.py``.  It intentionally
has **no widget code** — all GUI classes live in the companion modules.
"""

from __future__ import annotations

import sys, math, os, subprocess, logging, traceback
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal

# ────────────────────────────────────────────────────────────────────────────
# Logging setup
# ────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger("thumbnail_picker")

# ────────────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────────────

PRESETS: dict[str, tuple[int, int] | None] = {
    "Original":                 None,
    "YouTube  (1280×720)":      (1280, 720),
    "YouTube  (1920×1080)":     (1920, 1080),
    "Instagram (1080×1080)":    (1080, 1080),
    "Instagram (1080×1350)":    (1080, 1350),
    "Twitter  (1200×675)":      (1200, 675),
    "Facebook (1200×630)":      (1200, 630),
    "LinkedIn (1200×627)":      (1200, 627),
    "TikTok  (1080×1920)":     (1080, 1920),
}

DEFAULT_CANDIDATES = 8
DEFAULT_SAMPLES = 80

WEIGHTS_DEFAULT: dict[str, float] = {
    "sharpness":         0.14,
    "colorfulness":      0.10,
    "contrast":          0.08,
    "brightness":        0.06,
    "entropy":           0.08,
    "composition":       0.10,
    "skin_tone":         0.05,
    "faces":             0.12,
    "motion":            0.05,
    "exposure_quality":  0.06,
    "dynamic_range":     0.04,
    "visual_complexity": 0.04,
    "color_harmony":     0.04,
    "center_weight":     0.04,
}

WEIGHT_PROFILES = {
    "General (balanced)":    WEIGHTS_DEFAULT.copy(),
    "YouTube  (faces)":      {**WEIGHTS_DEFAULT, "faces": 0.22, "sharpness": 0.12, "center_weight": 0.08, "motion": 0.02},
    "Instagram (colour)":    {**WEIGHTS_DEFAULT, "colorfulness": 0.22, "color_harmony": 0.10, "composition": 0.10},
    "TikTok   (dynamic)":    {**WEIGHTS_DEFAULT, "motion": 0.20, "visual_complexity": 0.10, "dynamic_range": 0.08},
    "Film     (moody)":      {**WEIGHTS_DEFAULT, "contrast": 0.18, "dynamic_range": 0.14, "exposure_quality": 0.10},
    "Documentary (clean)":   {**WEIGHTS_DEFAULT, "sharpness": 0.22, "exposure_quality": 0.12, "composition": 0.10},
    "Thumbnail (general)":   {**WEIGHTS_DEFAULT, "sharpness": 0.15, "faces": 0.15, "colorfulness": 0.12,
                               "contrast": 0.10, "composition": 0.10, "visual_complexity": 0.08},
    "Cinematic (dramatic)":  {**WEIGHTS_DEFAULT, "dynamic_range": 0.18, "contrast": 0.16,
                               "color_harmony": 0.10, "composition": 0.10},
}

CRIT_LABELS: dict[str, str] = {
    "sharpness":         "Sharpness",
    "colorfulness":      "Colourfulness",
    "contrast":          "Contrast",
    "brightness":        "Brightness",
    "entropy":           "Entropy",
    "composition":       "Composition",
    "skin_tone":         "Skin Tone",
    "faces":             "Faces",
    "motion":            "Motion",
    "exposure_quality":  "Exposure Q.",
    "dynamic_range":     "Dyn. Range",
    "visual_complexity": "Complexity",
    "color_harmony":     "Colour Harm.",
    "center_weight":     "Centre Wt.",
}

# ──── Catppuccin Mocha palette ────
C_BG       = "#1e1e2e"; C_SURFACE  = "#2a2a3c"; C_CARD     = "#313244"
C_OVERLAY  = "#45475a"; C_TEXT     = "#cdd6f4"; C_SUBTEXT  = "#a6adc8"
C_BLUE     = "#89b4fa"; C_GREEN    = "#a6e3a1"; C_YELLOW   = "#f9e2af"
C_PEACH    = "#fab387"; C_RED      = "#f38ba8"; C_MAUVE    = "#cba6f7"
C_TEAL     = "#94e2d5"; C_LAVENDER = "#b4befe"; C_PINK     = "#f5c2e7"

# ────────────────────────────────────────────────────────────────────────────
# QSS
# ────────────────────────────────────────────────────────────────────────────

STYLESHEET = f"""
QMainWindow {{ background:{C_BG}; }}
QWidget {{ color:{C_TEXT}; font-family:"Segoe UI","SF Pro","Helvetica Neue",sans-serif; }}
QGroupBox {{
    border:1px solid {C_OVERLAY}; border-radius:8px; margin-top:12px;
    padding:14px 10px 10px; font-weight:bold; font-size:11px;
    color:{C_LAVENDER}; background:{C_SURFACE};
}}
QGroupBox::title {{ subcontrol-origin:margin; left:12px; padding:0 6px; }}
QPushButton {{
    background:{C_OVERLAY}; color:{C_TEXT}; border:none; border-radius:6px;
    padding:8px 16px; font-size:12px; font-weight:bold; min-height:18px;
}}
QPushButton:hover {{ background:{C_BLUE}; color:{C_BG}; }}
QPushButton:pressed {{ background:{C_LAVENDER}; color:{C_BG}; }}
QPushButton:disabled {{ background:{C_OVERLAY}; color:{C_OVERLAY}; }}
QPushButton#btnPrimary {{ background:{C_BLUE}; color:{C_BG}; }}
QPushButton#btnPrimary:hover {{ background:{C_LAVENDER}; }}
QPushButton#btnGreen {{ background:{C_GREEN}; color:{C_BG}; }}
QPushButton#btnGreen:hover {{ background:{C_TEAL}; }}
QPushButton#btnMauve {{ background:{C_MAUVE}; color:{C_BG}; }}
QPushButton#btnMauve:hover {{ background:{C_PINK}; }}
QPushButton#btnPeach {{ background:{C_PEACH}; color:{C_BG}; }}
QPushButton#btnPeach:hover {{ background:{C_YELLOW}; }}
QPushButton#btnRed {{ background:{C_RED}; color:{C_BG}; }}
QPushButton#btnRed:hover {{ background:{C_PEACH}; }}
QPushButton#btnYellow {{ background:{C_YELLOW}; color:{C_BG}; }}
QPushButton#btnYellow:hover {{ background:{C_PEACH}; }}
QPushButton#btnTeal {{ background:{C_TEAL}; color:{C_BG}; }}
QPushButton#btnTeal:hover {{ background:{C_GREEN}; }}
QProgressBar {{
    border:none; border-radius:4px; background:{C_OVERLAY};
    text-align:center; color:{C_BG}; font-weight:bold; font-size:11px; min-height:18px;
}}
QProgressBar::chunk {{
    border-radius:4px;
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {C_BLUE},stop:1 {C_TEAL});
}}
QComboBox {{
    background:{C_CARD}; color:{C_TEXT}; border:1px solid {C_OVERLAY};
    border-radius:6px; padding:6px 12px; font-size:11px; min-height:18px;
}}
QComboBox::drop-down {{ border:none; width:24px; }}
QComboBox::down-arrow {{
    image:none; border-left:5px solid transparent; border-right:5px solid transparent;
    border-top:6px solid {C_SUBTEXT}; margin-right:8px;
}}
QComboBox QAbstractItemView {{
    background:{C_CARD}; color:{C_TEXT}; selection-background-color:{C_BLUE};
    selection-color:{C_BG}; border:1px solid {C_OVERLAY};
}}
QSpinBox, QDoubleSpinBox {{
    background:{C_CARD}; color:{C_TEXT}; border:1px solid {C_OVERLAY};
    border-radius:6px; padding:6px 10px; font-size:11px; min-height:18px;
}}
QSpinBox::up-button,QSpinBox::down-button {{ background:{C_OVERLAY}; border:none; width:18px; }}
QSpinBox::up-button:hover,QSpinBox::down-button:hover {{ background:{C_BLUE}; }}
QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{
    background:{C_SURFACE}; width:10px; border-radius:5px; margin:0;
}}
QScrollBar::handle:vertical {{
    background:{C_OVERLAY}; border-radius:5px; min-height:30px;
}}
QScrollBar::handle:vertical:hover {{ background:{C_BLUE}; }}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{
    background:{C_SURFACE}; height:10px; border-radius:5px; margin:0;
}}
QScrollBar::handle:horizontal {{
    background:{C_OVERLAY}; border-radius:5px; min-width:30px;
}}
QScrollBar::handle:horizontal:hover {{ background:{C_BLUE}; }}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{ width:0; }}
QStatusBar {{
    background:{C_SURFACE}; color:{C_SUBTEXT}; font-size:11px;
    border-top:1px solid {C_OVERLAY};
}}
QLabel {{ background:transparent; }}
QGraphicsView {{ border:none; background:{C_CARD}; border-radius:8px; }}
QSplitter::handle {{ background:{C_OVERLAY}; width:2px; }}
QSplitter::handle:vertical {{ background:{C_OVERLAY}; height:2px; }}
QToolBar {{ background:{C_SURFACE}; border:none; spacing:6px; padding:4px; }}
QSlider::groove:horizontal {{
    height:6px; background:{C_OVERLAY}; border-radius:3px;
}}
QSlider::handle:horizontal {{
    background:{C_BLUE}; width:16px; height:16px; margin:-5px 0;
    border-radius:8px;
}}
QSlider::handle:horizontal:hover {{ background:{C_LAVENDER}; }}
QSlider::sub-page:horizontal {{
    background:{C_BLUE}; border-radius:3px;
}}
QCheckBox {{ spacing:6px; font-size:11px; }}
QCheckBox::indicator {{
    width:16px; height:16px; border:2px solid {C_OVERLAY};
    border-radius:4px; background:{C_CARD};
}}
QCheckBox::indicator:checked {{ background:{C_BLUE}; border-color:{C_BLUE}; }}
QRadioButton {{ spacing:6px; font-size:11px; }}
QRadioButton::indicator {{
    width:14px; height:14px; border:2px solid {C_OVERLAY};
    border-radius:7px; background:{C_CARD};
}}
QRadioButton::indicator:checked {{ background:{C_BLUE}; border-color:{C_BLUE}; }}
QToolTip {{
    background:{C_SURFACE}; color:{C_TEXT}; border:1px solid {C_OVERLAY};
    border-radius:4px; padding:6px; font-size:11px;
}}
"""

# ────────────────────────────────────────────────────────────────────────────
# Scoring engine
# ────────────────────────────────────────────────────────────────────────────

_face_cascade = _profile_cascade = None

def _get_cascades():
    global _face_cascade, _profile_cascade
    if _face_cascade is None:
        frontal_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        profile_path = cv2.data.haarcascades + "haarcascade_profileface.xml"
        _face_cascade = cv2.CascadeClassifier(frontal_path)
        _profile_cascade = cv2.CascadeClassifier(profile_path)
        if _face_cascade.empty():
            logger.warning("Failed to load frontal face cascade: %s", frontal_path)
        if _profile_cascade.empty():
            logger.warning("Failed to load profile face cascade: %s", profile_path)
        logger.debug("Loaded face cascade classifiers")
    return _face_cascade, _profile_cascade

def _to_gray(frame_bgr):
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

# ──── Frame pre-filter ────

def prefilter_frame(bgr: np.ndarray) -> bool:
    """Return True if the frame passes basic quality checks.
    Rejects frames that are too dark, too bright, too blurry, or too plain.
    Uses downscaled image (1/4) for faster checks on large frames."""
    h, w = bgr.shape[:2]
    # Downscale for faster pre-filtering on large frames (e.g. 4K)
    if h > 540 or w > 960:
        scale = 0.25
        small = cv2.resize(bgr, (max(1, int(w * scale)), max(1, int(h * scale))))
        gray = _to_gray(small)
    else:
        gray = _to_gray(bgr)
    # Brightness check — reject very dark or very bright
    mean_val = np.mean(gray)
    if mean_val < 25 or mean_val > 235:
        return False

    # Clipping check — reject frames with severe highlight or shadow clipping
    clipped_high = np.count_nonzero(gray > 250) / gray.size
    clipped_low = np.count_nonzero(gray < 5) / gray.size
    if clipped_high > 0.30 or clipped_low > 0.30:
        return False

    # Blur check — Laplacian variance must exceed a minimum
    lap_var = np.var(cv2.Laplacian(gray, cv2.CV_64F))
    if lap_var < 15:
        return False

    # Plainness check — standard deviation must be above a floor
    if np.std(gray) < 12:
        return False

    return True

# ──── Improved scorers ────

def score_brightness(gray):
    """Prefer frames centred around 125 ± 50 with Gaussian falloff."""
    return float(np.exp(-0.5 * ((np.mean(gray) - 125) / 50.0) ** 2))

def score_contrast(gray):
    """Combines standard deviation and 5th-95th percentile spread."""
    std = np.std(gray)
    p = np.percentile(gray, [5, 95])
    return 0.5 * min(std / 75, 1) + 0.5 * min((p[1] - p[0]) / 255, 1)

def score_sharpness(gray):
    """Multi-metric sharpness: Laplacian variance + Tenengrad + local-patch variance."""
    # 1) Laplacian variance
    lap = np.var(cv2.Laplacian(gray, cv2.CV_64F))
    lap_score = min(lap / 500, 1)

    # 2) Tenengrad (Sobel gradient magnitude)
    sx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    tenengrad = np.mean(sx ** 2 + sy ** 2)
    ten_score = min(tenengrad / 3000, 1)

    # 3) Multi-scale Laplacian: downsample 2× and compute variance
    small = cv2.resize(gray, (max(1, gray.shape[1] // 2), max(1, gray.shape[0] // 2)))
    lap2 = np.var(cv2.Laplacian(small, cv2.CV_64F))
    ms_score = min(lap2 / 300, 1)

    return 0.40 * lap_score + 0.35 * ten_score + 0.25 * ms_score

def score_colorfulness(bgr):
    """Hasler & Süsstrunk colourfulness metric (improved normalisation)."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    a, b = lab[:, :, 1], lab[:, :, 2]
    val = (math.sqrt(np.std(a)**2 + np.std(b)**2) +
           0.3 * math.sqrt(np.mean(a)**2 + np.mean(b)**2))
    return min(val / 120, 1)

def score_entropy(gray):
    """Shannon entropy of the intensity histogram."""
    h = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    h = h / h.sum(); h = h[h > 0]
    return min(-np.sum(h * np.log2(h)) / 7.5, 1)

def score_composition(bgr):
    """Rule-of-thirds + visual-weight balance + symmetry axis."""
    H, W = bgr.shape[:2]
    edges = cv2.Canny(_to_gray(bgr), 50, 150).astype(np.float32) / 255

    # --- Rule of thirds ---
    wt = np.zeros((H, W), np.float32)
    for f in (1 / 3, 2 / 3):
        x, y = int(W * f), int(H * f)
        lw, hw = max(2, W // 40), max(2, H // 40)
        wt[:, max(0, x - lw):min(W, x + lw)] += 0.5
        wt[max(0, y - hw):min(H, y + hw), :] += 0.5
    r = max(3, min(W, H) // 20)
    for fx in (1 / 3, 2 / 3):
        for fy in (1 / 3, 2 / 3):
            cx, cy = int(W * fx), int(H * fy)
            wt[max(0, cy - r):min(H, cy + r), max(0, cx - r):min(W, cx + r)] += 1.0
    thirds_score = min(float(np.mean(edges * np.clip(wt, 0, 1))) / 0.08, 1)

    # --- Visual-weight balance (centroid deviation from centre) ---
    gray = _to_gray(bgr)
    yy, xx = np.mgrid[:H, :W]
    weights = (255 - gray).astype(np.float32)  # brighter pixels get more weight
    total_w = weights.sum() + 1e-8
    cx = float(np.sum(xx * weights)) / total_w / W  # normalised 0..1
    cy = float(np.sum(yy * weights)) / total_w / H
    deviation = math.sqrt((cx - 0.5) ** 2 + (cy - 0.5) ** 2)
    balance_score = max(0, 1 - deviation * 2.5)  # 0 at corners, 1 at centre

    # --- Vertical symmetry ---
    left = gray[:, :W // 2]
    right = cv2.flip(gray[:, W // 2:], 1)
    if left.shape == right.shape:
        diff = np.abs(left.astype(float) - right.astype(float))
        sym_score = 1 - min(float(np.mean(diff)) / 40, 1)
    else:
        sym_score = 0.5

    return 0.45 * thirds_score + 0.35 * balance_score + 0.20 * sym_score

def score_skin_tone(bgr):
    """YCrCb skin-tone pixel ratio."""
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    cr, cb = ycrcb[:, :, 1], ycrcb[:, :, 2]
    m = (cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)
    return min(float(np.count_nonzero(m)) / m.size / 0.15, 1)

def score_faces(bgr):
    """Face detection with centre-of-frame bias and ideal-size bonus."""
    fc, pc = _get_cascades()
    g = _to_gray(bgr)
    faces = fc.detectMultiScale(g, 1.1, 4, minSize=(48, 48))
    if len(faces) == 0:
        faces = pc.detectMultiScale(g, 1.1, 4, minSize=(48, 48))
    n = len(faces)
    if n == 0:
        return 0.0

    H, W = bgr.shape[:2]
    fa = H * W
    base = min(n * 0.30, 1.0)

    # Centre bias: bonus if the largest face is near the centre
    largest = max(faces, key=lambda r: r[2] * r[3])
    fx = (largest[0] + largest[2] / 2) / W
    fy = (largest[1] + largest[3] / 2) / H
    centre_dist = math.sqrt((fx - 0.5) ** 2 + (fy - 0.5) ** 2)
    centre_bonus = max(0, 0.30 * (1 - centre_dist * 2.5))

    # Ideal size bonus: face occupies 10-40% of the frame area
    face_ratio = (largest[2] * largest[3]) / fa
    if 0.10 <= face_ratio <= 0.40:
        size_bonus = 0.20
    elif 0.05 <= face_ratio < 0.10 or 0.40 < face_ratio <= 0.55:
        size_bonus = 0.10
    else:
        size_bonus = 0.0

    return min(base + centre_bonus + size_bonus, 1.0)

def score_motion_flow(prev, curr):
    """Optical-flow magnitude (smoothed)."""
    if prev is None:
        return 0.0
    H, W = curr.shape
    s = (max(1, W // 4), max(1, H // 4))
    fl = cv2.calcOpticalFlowFarneback(
        cv2.resize(prev, s), cv2.resize(curr, s), None, 0.5, 3, 15, 3, 5, 1.2, 0)
    return min(float(np.mean(cv2.cartToPolar(fl[..., 0], fl[..., 1])[0])) / 4, 1)

def score_exposure_quality(bgr):
    """Histogram spread + highlight/shadow clipping penalty + midtone richness."""
    gray = _to_gray(bgr)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    total = gray.size

    # Histogram spread: what fraction of the 0-255 range is "used"?
    nonzero = np.count_nonzero(hist)
    spread = nonzero / 256.0

    # Clipping penalty
    clip_high = np.count_nonzero(gray > 248) / total
    clip_low = np.count_nonzero(gray < 7) / total
    clip_penalty = min(clip_high + clip_low, 0.5)

    # Midtone richness: fraction of pixels in the 60-195 range
    mid = np.count_nonzero((gray >= 60) & (gray <= 195)) / total
    midtone_score = min(mid / 0.70, 1.0)

    return min(spread * 0.35 + midtone_score * 0.45 + (1 - clip_penalty * 2) * 0.20, 1.0)

def score_dynamic_range(bgr):
    """Tonal range utilisation via percentile analysis."""
    gray = _to_gray(bgr)
    p_low = np.percentile(gray, 2)
    p_high = np.percentile(gray, 98)
    utilised = (p_high - p_low) / 255.0

    # Std-based range score
    std_score = min(np.std(gray) / 70, 1)

    return 0.6 * min(utilised, 1) + 0.4 * std_score

def score_visual_complexity(bgr):
    """Edge-density × normalised Gabor-texture busyness."""
    gray = _to_gray(bgr)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.count_nonzero(edges) / edges.size

    # Local binary pattern variance as a cheap texture metric
    h, w = gray.shape
    small = cv2.resize(gray, (min(128, w), min(128, h)))
    local_var = np.std(small) / 80  # normalised

    density_score = min(edge_density / 0.15, 1)
    texture_score = min(local_var, 1)

    # Avoid extremes: too plain (0) or too noisy (1)
    combined = 0.5 * density_score + 0.5 * texture_score
    # Bell curve: penalise both very low and very high complexity
    return max(0, 1 - (combined - 0.55) ** 2 / 0.2)

def score_color_harmony(bgr):
    """Perceptual colour diversity: unique hue bins + saturation balance."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hue = hsv[:, :, 0]
    sat = hsv[:, :, 1]

    # Number of populated hue bins (out of 12, each 30°)
    n_bins = 12
    bin_size = 180.0 / n_bins
    hue_bins = np.zeros(n_bins)
    for i in range(n_bins):
        mask = (hue >= i * bin_size) & (hue < (i + 1) * bin_size)
        hue_bins[i] = np.count_nonzero(mask & (sat > 40)) / hue.size

    # Diversity: how many bins have significant (>2%) colour?
    significant = np.sum(hue_bins > 0.02) / n_bins

    # Saturation balance: mean saturation of saturated pixels
    sat_mask = sat > 40
    if np.any(sat_mask):
        mean_sat = np.mean(sat[sat_mask]) / 255
    else:
        mean_sat = 0

    # Best harmony: 3-6 significant hue bins with decent saturation
    diversity_score = min(significant / 0.45, 1)
    sat_score = min(mean_sat / 0.65, 1)

    return 0.55 * diversity_score + 0.45 * sat_score

def score_center_weight(bgr):
    """How much visual interest is concentrated in the centre third."""
    gray = _to_gray(bgr)
    H, W = gray.shape
    # Centre region: middle third
    y1, y2 = H // 3, 2 * H // 3
    x1, x2 = W // 3, 2 * W // 3
    centre = gray[y1:y2, x1:x2]
    border = np.concatenate([gray[:y1, :].flatten(), gray[y2:, :].flatten(),
                             gray[y1:y2, :x1].flatten(), gray[y1:y2, x2:].flatten()])
    centre_energy = np.std(centre)
    border_energy = np.std(border) + 1e-8
    ratio = centre_energy / border_energy
    return min(ratio / 2.5, 1)

# ──── Scorer dispatch ────

SCORERS = {
    "sharpness":         lambda f, p: score_sharpness(_to_gray(f)),
    "colorfulness":      lambda f, p: score_colorfulness(f),
    "contrast":          lambda f, p: score_contrast(_to_gray(f)),
    "brightness":        lambda f, p: score_brightness(_to_gray(f)),
    "entropy":           lambda f, p: score_entropy(_to_gray(f)),
    "composition":       lambda f, p: score_composition(f),
    "skin_tone":         lambda f, p: score_skin_tone(f),
    "faces":             lambda f, p: score_faces(f),
    "motion":            lambda f, p: score_motion_flow(p, _to_gray(f)),
    "exposure_quality":  lambda f, p: score_exposure_quality(f),
    "dynamic_range":     lambda f, p: score_dynamic_range(f),
    "visual_complexity": lambda f, p: score_visual_complexity(f),
    "color_harmony":     lambda f, p: score_color_harmony(f),
    "center_weight":     lambda f, p: score_center_weight(f),
}

def compute_score(frame_bgr, prev_gray=None, weights=None):
    w = weights or WEIGHTS_DEFAULT
    scores = {}
    for name, scorer in SCORERS.items():
        try:
            scores[name] = scorer(frame_bgr, prev_gray)
        except Exception as exc:
            logger.warning("Scorer '%s' failed: %s", name, exc)
            scores[name] = 0.0
    total = sum(scores[k] * w.get(k, 0) for k in w)
    return total, scores

# ──── Similarity filtering ────

def _color_histogram(bgr: np.ndarray) -> np.ndarray:
    """Compute a compact colour histogram descriptor for frame comparison."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hist_h = cv2.calcHist([hsv], [0], None, [24], [0, 180]).flatten()
    hist_s = cv2.calcHist([hsv], [1], None, [12], [0, 256]).flatten()
    hist_v = cv2.calcHist([hsv], [2], None, [12], [0, 256]).flatten()
    feat = np.concatenate([hist_h, hist_s, hist_v]).astype(np.float32)
    return feat / (feat.sum() + 1e-8)

def filter_similar(candidates: list, threshold: float = 0.85) -> list:
    """Remove candidates that are too similar to higher-ranked ones.
    Uses histogram correlation.  Histograms are computed once and cached."""
    if len(candidates) <= 1:
        return candidates
    kept = [candidates[0]]
    kept_feats = [_color_histogram(candidates[0].frame_bgr)]
    for c in candidates[1:]:
        feat = _color_histogram(c.frame_bgr)
        is_similar = False
        for kfeat in kept_feats:
            corr = cv2.compareHist(kfeat, feat, cv2.HISTCMP_CORREL)
            if corr > threshold:
                is_similar = True
                break
        if not is_similar:
            kept.append(c)
            kept_feats.append(feat)
    return kept

# ────────────────────────────────────────────────────────────────────────────
# Scene-change detection
# ────────────────────────────────────────────────────────────────────────────

def detect_scene_changes(video_path: str, threshold: float = 30.0):
    logger.info("Scene detection starting for %s (threshold=%.1f)", video_path, threshold)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("Cannot open video for scene detection: %s", video_path)
        return []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        dur = total / fps
        logger.debug("Scene detect: %.1fs, %d frames, %.2f fps", dur, total, fps)

        scenes = []
        prev_gray = None
        sample_interval = max(1, int(fps / 4))
        frames_checked = 0
        for i in range(0, total, sample_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                continue
            frames_checked += 1
            gray = _to_gray(frame)
            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                mean_diff = np.mean(diff)
                if mean_diff > threshold:
                    t = i / fps
                    if dur * 0.03 < t < dur * 0.97:
                        scenes.append((t, frame.copy()))
            prev_gray = gray.copy()
        logger.info("Scene detection done: %d scenes found in %d frames checked",
                     len(scenes), frames_checked)
        return scenes
    except Exception as exc:
        logger.error("Scene detection failed: %s\n%s", exc, traceback.format_exc())
        return []
    finally:
        cap.release()

# ────────────────────────────────────────────────────────────────────────────
# Audio analysis
# ────────────────────────────────────────────────────────────────────────────

def analyze_audio_energy(video_path: str, n_segments: int = 200) -> list[tuple[float, float]]:
    """Extract audio energy per segment from the video's audio track.
    Returns list of (timestamp, energy) tuples normalized to 0-1 range.
    Returns empty list if no audio track or on error."""
    try:
        logger.info("Audio analysis starting: %d segments from %s", n_segments, video_path)
        # Check if video has an audio track using ffprobe
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-select_streams", "a",
                 "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                 video_path],
                capture_output=True, text=True, timeout=10,
            )
        except FileNotFoundError:
            logger.warning("ffprobe not found — audio analysis disabled (install FFmpeg)")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("ffprobe timed out for %s", video_path)
            return []

        if "audio" not in probe.stdout:
            logger.info("No audio track found in video")
            return []

        logger.debug("Audio track detected, extracting PCM...")
        # Extract audio as raw PCM 16-bit mono at 22050 Hz
        try:
            result = subprocess.run(
                ["ffmpeg", "-i", video_path, "-f", "s16le",
                 "-ac", "1", "-ar", "22050", "-loglevel", "quiet",
                 "pipe:1"],
                capture_output=True, timeout=120,
            )
        except FileNotFoundError:
            logger.warning("ffmpeg not found — audio analysis disabled (install FFmpeg)")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg timed out extracting audio from %s", video_path)
            return []
        raw = result.stdout
        if len(raw) < 2:
            logger.warning("Audio extraction returned no data (%d bytes)", len(raw))
            return []

        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
        seg_len = max(1, len(audio) // n_segments)
        energies = []
        for i in range(n_segments):
            chunk = audio[i * seg_len : (i + 1) * seg_len]
            rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) > 0 else 0.0
            energies.append(rms)

        max_e = max(energies) if energies else 1.0
        if max_e < 1e-6:
            max_e = 1.0
            logger.debug("Audio energy is very low, normalising from flat signal")

        # Map segment indices to timestamps: assume same duration as video
        # We'll normalise timestamps later based on actual video duration
        normalised = [(i / n_segments, e / max_e)
                      for i, e in enumerate(energies)]
        logger.info("Audio analysis done: %d energy segments computed", len(normalised))
        return normalised
    except Exception as exc:
        logger.error("Audio analysis failed: %s\n%s", exc, traceback.format_exc())
        return []


def build_audio_aware_times(
    energy_data: list[tuple[float, float]],
    duration: float,
    n_samples: int,
) -> list[float]:
    """Distribute sample times toward high-energy moments.
    Falls back to uniform sampling if energy is flat."""
    if not energy_data:
        return list(np.linspace(
            duration * 0.03, duration * 0.97, n_samples))

    energies = np.array([e for _, e in energy_data])
    # Check if energy is flat (constant background noise)
    if np.std(energies) < 0.05:
        return list(np.linspace(
            duration * 0.03, duration * 0.97, n_samples))

    # Use energy as probability distribution (higher energy = more samples)
    prob = energies + 1e-8
    prob = prob / prob.sum()

    # Sample n_samples indices from the distribution
    indices = np.random.choice(len(energy_data), size=n_samples, replace=False, p=prob)
    indices.sort()

    # Convert normalised positions to timestamps
    margin = 0.03
    usable = duration * (1 - 2 * margin)
    times = [margin + (idx / len(energy_data)) * usable for idx in indices]
    return times


# ────────────────────────────────────────────────────────────────────────────
# Data classes
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class Candidate:
    frame_bgr: np.ndarray
    timestamp: float
    total_score: float
    breakdown: dict
    starred: bool = False

# ────────────────────────────────────────────────────────────────────────────
# Analysis thread
# ────────────────────────────────────────────────────────────────────────────

class AnalysisThread(QThread):
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(list, dict)
    finished_err = pyqtSignal(str)
    cancelled = pyqtSignal()
    scene_frame = pyqtSignal(float, object)
    filmstrip_frames = pyqtSignal(list)  # [(timestamp, bgr_small), ...]
    candidate_ready = pyqtSignal(object, int, int)  # (Candidate, current_index, total_frames)
    audio_energy_ready = pyqtSignal(list, float)  # (energy_data, duration)

    def __init__(self, path, n_samples, weights, use_scene_detect, n_candidates,
                 use_audio=True):
        super().__init__()
        self.path = path
        self.n_samples = n_samples
        self.weights = weights
        self.use_scene_detect = use_scene_detect
        self.n_candidates = n_candidates
        self.use_audio = use_audio
        self._abort = False

    def run(self):
        logger.info("=== Analysis started ===")
        logger.info("Video: %s", self.path)
        logger.info("Config: %d samples, %d candidates, scene_detect=%s, audio=%s",
                     self.n_samples, self.n_candidates,
                     self.use_scene_detect, self.use_audio)
        cap = None
        try:
            cap = cv2.VideoCapture(self.path)
            if not cap.isOpened():
                msg = f"Cannot open video:\n{self.path}\n\n"
                msg += "Possible causes:\n"
                msg += "  - File does not exist or path is incorrect\n"
                msg += "  - Video codec not supported (try MP4/H.264)\n"
                msg += "  - File is corrupted or locked by another program"
                logger.error("Cannot open video: %s", self.path)
                self.finished_err.emit(msg)
                return
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            duration = total_frames / fps
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            logger.info("Video info: %dx%d, %.2f fps, %.1fs, %d total frames",
                         w, h, fps, duration, total_frames)
            if duration < 0.1:
                cap.release()
                self.finished_err.emit(f"Video too short ({duration:.2f}s). Need at least 0.1s.")
                return
            if w == 0 or h == 0:
                cap.release()
                self.finished_err.emit(
                    f"Could not read video dimensions ({w}x{h}). "
                    f"The file may be corrupted.")
                return

            # ── Build filmstrip (thumbnails at regular intervals) ──
            n_filmstrip = min(120, max(30, int(duration)))
            filmstrip = []
            logger.info("Building filmstrip: %d thumbnails...", n_filmstrip)
            filmstrip_failures = 0
            for i in range(n_filmstrip):
                t = duration * (i + 0.5) / n_filmstrip
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ret, frame = cap.read()
                if ret:
                    try:
                        small = cv2.resize(frame, (160, 90))
                        filmstrip.append((t, small))
                    except cv2.error as exc:
                        filmstrip_failures += 1
                        logger.debug("Filmstrip frame resize failed at %.2fs: %s", t, exc)
                else:
                    filmstrip_failures += 1
            logger.info("Filmstrip done: %d/%d frames (failures: %d)",
                         len(filmstrip), n_filmstrip, filmstrip_failures)
            self.filmstrip_frames.emit(filmstrip)

            # ── Audio analysis ──
            audio_energy_data = []
            if self.use_audio:
                audio_energy_data = analyze_audio_energy(self.path, n_segments=200)
                if audio_energy_data:
                    self.audio_energy_ready.emit(audio_energy_data, duration)

            # ── Build sample times ──
            if self.use_scene_detect:
                logger.info("Using scene-change detection mode")
                scenes = detect_scene_changes(self.path)
                if scenes:
                    n = min(self.n_samples * 2, len(scenes))
                    indices = np.linspace(0, len(scenes) - 1, n, dtype=int)
                    sample_times = [scenes[i][0] for i in indices]
                    step = max(1, len(scenes) // 60)
                    for i in range(0, len(scenes), step):
                        self.scene_frame.emit(scenes[i][0], scenes[i][1])
                    logger.info("Scene mode: %d sample times from %d scenes",
                                 len(sample_times), len(scenes))
                else:
                    logger.info("No scenes detected, falling back to uniform sampling")
                    sample_times = list(np.linspace(
                        duration * 0.03, duration * 0.97, self.n_samples))
            elif audio_energy_data and self.use_audio:
                logger.info("Using audio-aware sampling mode")
                sample_times = build_audio_aware_times(
                    audio_energy_data, duration, self.n_samples)
                logger.info("Audio-aware: %d sample times generated", len(sample_times))
            else:
                logger.info("Using uniform sampling mode")
                sample_times = list(np.linspace(
                    duration * 0.03, duration * 0.97, self.n_samples))
            logger.info("Total sample times: %d", len(sample_times))

            # ── Score frames with pre-filtering (progressive) ──
            cands: list[Candidate] = []
            prev = None
            filtered = 0
            read_failures = 0
            score_failures = 0
            try:
                for i, t in enumerate(sample_times):
                    if self._abort:
                        self.cancelled.emit()
                        logger.info("Analysis cancelled by user at frame %d/%d", i + 1, len(sample_times))
                        return
                    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                    ret, frame = cap.read()
                    if not ret:
                        read_failures += 1
                        logger.debug("Failed to read frame at %.2fs", t)
                        continue

                    # Pre-filter: skip low-quality frames early
                    if not prefilter_frame(frame):
                        filtered += 1
                        self.progress.emit(i + 1, len(sample_times))
                        continue

                    try:
                        total, bd = compute_score(frame, prev, self.weights)
                        prev = _to_gray(frame).copy()
                        cand = Candidate(frame, float(t), total, bd)
                        cands.append(cand)
                        # Progressive: emit candidate as soon as scored
                        self.candidate_ready.emit(cand, i + 1, len(sample_times))
                    except Exception as exc:
                        score_failures += 1
                        logger.warning("Scoring failed at %.2fs: %s", t, exc)
                    self.progress.emit(i + 1, len(sample_times))
            finally:
                cap.release()
            logger.info("Scoring complete: %d scored, %d filtered, %d read failures, %d score failures",
                         len(cands), filtered, read_failures, score_failures)

            # ── Sort and filter similar ──
            cands.sort(key=lambda c: c.total_score, reverse=True)
            if cands:
                logger.info("Top 3 scores: %.3f, %.3f, %.3f",
                             cands[0].total_score,
                             cands[1].total_score if len(cands) > 1 else 0,
                             cands[2].total_score if len(cands) > 2 else 0)

            # Apply similarity filtering to get diverse candidates
            pre_filter_count = len(cands)
            if len(cands) > self.n_candidates:
                cands = filter_similar(cands, threshold=0.82)
                cands = cands[:self.n_candidates]
                logger.info("Similarity filter: %d → %d candidates", pre_filter_count, len(cands))
            else:
                cands = cands[:self.n_candidates]
                logger.info("Kept top %d candidates (no similarity filter needed)", len(cands))

            info = dict(
                path=self.path, duration=duration, fps=fps,
                width=w, height=h, total_frames=total_frames,
                total_sampled=len(sample_times),
                candidates_kept=len(cands),
                frames_filtered=filtered,
                has_audio=bool(audio_energy_data),
                audio_aware_used=bool(audio_energy_data and self.use_audio
                                      and not self.use_scene_detect),
                sample_times=sample_times,
            )
            logger.info("=== Analysis finished: %d candidates ===", len(cands))
            self.finished_ok.emit(cands, info)
        except Exception as e:
            logger.error("Analysis thread error: %s\n%s", e, traceback.format_exc())
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
            self.finished_err.emit(
                f"An unexpected error occurred during analysis:\n\n{e}\n\n"
                f"Try:\n"
                f"  - Check the video file is valid and playable\n"
                f"  - Try a different video format (MP4 recommended)\n"
                f"  - Reduce the number of samples")

    def abort(self):
        self._abort = True
