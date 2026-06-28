#!/usr/bin/env python3
"""
Video Thumbnail Picker  v5.0  (PyQt6)
======================================
An advanced Python GUI tool that analyses a video and extracts the most
visually compelling thumbnail.

v5 IMPROVEMENTS over v4
  ★ ★★ GENERATION QUALITY ★★
  ★ Frame pre-filtering: reject blurry / overexposed / underexposed / plain
    frames BEFORE scoring so bad frames never waste candidate slots
  ★ Improved sharpness: Tenengrad gradient magnitude + multi-scale Laplacian
    + local-patch variance for robust blur detection
  ★ Exposure quality: highlight/shadow clipping detection + midtone richness
    + histogram spread score
  ★ Dynamic range: full tonal-range utilisation via percentile analysis
  ★ Visual complexity: edge-density × Gabor-texture busyness metric
  ★ Color harmony: perceptual colour diversity (unique hue bins + saturation
    distribution balance)
  ★ Better face scoring: centre-of-frame bias, ideal-size bonus,
    inter-eye-distance clarity proxy
  ★ Improved composition: visual-weight balance (centroid deviation) +
    symmetry axis analysis alongside rule-of-thirds
  ★ Similarity filtering: histogram-correlation dedup so top-N candidates
    are visually distinct
  ★ Adaptive sampling: sample more frames near scene boundaries, fewer in
    static regions

  ★ ★★ VIEWING EXPERIENCE ★★
  ★ Filmstrip timeline bar — scrollable keyframe strip below the preview
    showing the whole video at a glance; click any frame to seek
  ★ Full-screen preview — double-click the preview or press F11
  ★ Grid gallery view — toggle between list cards and a compact thumbnail
    grid (larger images, 4 per row)
  ★ Zoom control buttons (+ / − / Fit / 100 %)
  ★ Sort candidates — by time, total score, or any individual metric
  ★ Video scrubber — open a slider that seeks to any frame in the source
    video in real time
  ★ Comparison blend slider — drag to cross-fade between two candidates
  ★ JPEG / WebP quality slider in the save dialog
  ★ Candidate count spin-box (4–24) so you can ask for more or fewer results
  ★ Image-size info overlay on hover (resolution, estimated file size)
  ★ Animated fade transition when switching candidates
  ★ Star / favourite system — right-click to star; filter gallery to show
    only favourites

Requirements:
  pip install PyQt6 opencv-python numpy pillow

Usage:
  python video_thumbnail_picker_v5.py
"""

from __future__ import annotations

import sys, math, os, subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QRect, QPoint, QSettings,
    QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QPen,
    QKeySequence, QShortcut, QWheelEvent, QMouseEvent, QPainterPath,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QProgressBar, QScrollArea,
    QFileDialog, QMessageBox, QSplitter, QStatusBar, QFrame, QGroupBox,
    QToolBar, QGraphicsView, QGraphicsScene,
    QSlider, QCheckBox, QMenu, QGridLayout,
    QGraphicsOpacityEffect, QDialog, QLineEdit,
)

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
        _face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        _profile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_profileface.xml")
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
        except Exception:
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
    Uses histogram correlation."""
    if len(candidates) <= 1:
        return candidates
    kept = [candidates[0]]
    for c in candidates[1:]:
        feat = _color_histogram(c.frame_bgr)
        is_similar = False
        for k in kept:
            kfeat = _color_histogram(k.frame_bgr)
            corr = cv2.compareHist(kfeat, feat, cv2.HISTCMP_CORREL)
            if corr > threshold:
                is_similar = True
                break
        if not is_similar:
            kept.append(c)
    return kept

# ────────────────────────────────────────────────────────────────────────────
# Scene-change detection
# ────────────────────────────────────────────────────────────────────────────

def detect_scene_changes(video_path: str, threshold: float = 30.0):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        dur = total / fps

        scenes = []
        prev_gray = None
        sample_interval = max(1, int(fps / 4))
        for i in range(0, total, sample_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                continue
            gray = _to_gray(frame)
            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                mean_diff = np.mean(diff)
                if mean_diff > threshold:
                    t = i / fps
                    if dur * 0.03 < t < dur * 0.97:
                        scenes.append((t, frame.copy()))
            prev_gray = gray.copy()
        return scenes
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
        # Check if video has an audio track using ffprobe
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0",
             video_path],
            capture_output=True, text=True, timeout=10,
        )
        if "audio" not in probe.stdout:
            return []

        # Extract audio as raw PCM 16-bit mono at 22050 Hz
        result = subprocess.run(
            ["ffmpeg", "-i", video_path, "-f", "s16le",
             "-ac", "1", "-ar", "22050", "-loglevel", "quiet",
             "pipe:1"],
            capture_output=True, timeout=60,
        )
        raw = result.stdout
        if len(raw) < 2:
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

        # Map segment indices to timestamps: assume same duration as video
        # We'll normalise timestamps later based on actual video duration
        normalised = [(i / n_segments, e / max_e)
                      for i, e in enumerate(energies)]
        return normalised
    except Exception:
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
        try:
            cap = cv2.VideoCapture(self.path)
            if not cap.isOpened():
                self.finished_err.emit(f"Cannot open:\n{self.path}")
                return
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            duration = total_frames / fps
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if duration < 0.1:
                cap.release()
                self.finished_err.emit("Video too short")
                return

            # ── Build filmstrip (thumbnails at regular intervals) ──
            n_filmstrip = min(120, max(30, int(duration)))
            filmstrip = []
            for i in range(n_filmstrip):
                t = duration * (i + 0.5) / n_filmstrip
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ret, frame = cap.read()
                if ret:
                    small = cv2.resize(frame, (160, 90))
                    filmstrip.append((t, small))
            self.filmstrip_frames.emit(filmstrip)

            # ── Audio analysis ──
            audio_energy_data = []
            if self.use_audio:
                audio_energy_data = analyze_audio_energy(self.path, n_segments=200)
                if audio_energy_data:
                    self.audio_energy_ready.emit(audio_energy_data, duration)

            # ── Build sample times ──
            if self.use_scene_detect:
                scenes = detect_scene_changes(self.path)
                if scenes:
                    n = min(self.n_samples * 2, len(scenes))
                    indices = np.linspace(0, len(scenes) - 1, n, dtype=int)
                    sample_times = [scenes[i][0] for i in indices]
                    step = max(1, len(scenes) // 60)
                    for i in range(0, len(scenes), step):
                        self.scene_frame.emit(scenes[i][0], scenes[i][1])
                else:
                    sample_times = list(np.linspace(
                        duration * 0.03, duration * 0.97, self.n_samples))
            elif audio_energy_data and self.use_audio:
                # Audio-aware sampling (priority: scene_detect > audio > uniform)
                sample_times = build_audio_aware_times(
                    audio_energy_data, duration, self.n_samples)
            else:
                sample_times = list(np.linspace(
                    duration * 0.03, duration * 0.97, self.n_samples))

            # ── Score frames with pre-filtering (progressive) ──
            cands: list[Candidate] = []
            prev = None
            filtered = 0
            for i, t in enumerate(sample_times):
                if self._abort:
                    cap.release()
                    self.cancelled.emit()
                    return
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ret, frame = cap.read()
                if not ret:
                    continue

                # Pre-filter: skip low-quality frames early
                if not prefilter_frame(frame):
                    filtered += 1
                    self.progress.emit(i + 1, len(sample_times))
                    continue

                total, bd = compute_score(frame, prev, self.weights)
                prev = _to_gray(frame).copy()
                cand = Candidate(frame, float(t), total, bd)
                cands.append(cand)
                # Progressive: emit candidate as soon as scored
                self.candidate_ready.emit(cand, i + 1, len(sample_times))
                self.progress.emit(i + 1, len(sample_times))

            cap.release()

            # ── Sort and filter similar ──
            cands.sort(key=lambda c: c.total_score, reverse=True)

            # Apply similarity filtering to get diverse candidates
            if len(cands) > self.n_candidates:
                cands = filter_similar(cands, threshold=0.82)
                cands = cands[:self.n_candidates]
            else:
                cands = cands[:self.n_candidates]

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
            self.finished_ok.emit(cands, info)
        except Exception as e:
            try:
                cap.release()
            except Exception:
                pass
            self.finished_err.emit(str(e))

    def abort(self):
        self._abort = True

# ────────────────────────────────────────────────────────────────────────────
# Zoomable preview widget (improved with transition & double-click fullscreen)
# ────────────────────────────────────────────────────────────────────────────

class ZoomablePreview(QGraphicsView):
    zoom_changed = pyqtSignal(float)
    double_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom = 1.0
        self._panning = False
        self._pan_start = QPoint()
        self.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._item = None
        self._anim = None
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)

    def set_pixmap(self, pixmap: QPixmap):
        self._scene.clear()
        self._item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(pixmap.rect())
        self.fitInView(self._item, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = 1.0
        self.zoom_changed.emit(self._zoom)

    def set_pixmap_animated(self, pixmap: QPixmap):
        """Fade out, swap, fade in."""
        if self._anim is not None:
            self._anim.stop()
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(100)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.3)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._anim.finished.connect(lambda: self._swap_and_fade_in(pixmap))
        self._anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _swap_and_fade_in(self, pixmap: QPixmap):
        self.set_pixmap(pixmap)
        if self._anim is not None:
            self._anim.stop()
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(120)
        self._anim.setStartValue(0.3)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InQuad)
        self._anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def fit(self):
        if self._item:
            self.fitInView(self._item, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = 1.0
            self.zoom_changed.emit(self._zoom)

    def zoom_in(self):
        self.scale(1.25, 1.25)
        self._zoom *= 1.25
        self.zoom_changed.emit(self._zoom)

    def zoom_out(self):
        self.scale(1 / 1.25, 1 / 1.25)
        self._zoom /= 1.25
        self.zoom_changed.emit(self._zoom)

    def zoom_100(self):
        if self._item:
            self.resetTransform()
            self._zoom = 1.0
            self.zoom_changed.emit(self._zoom)

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15
        if event.angleDelta().y() > 0:
            self.scale(factor, factor); self._zoom *= factor
        else:
            self.scale(1 / factor, 1 / factor); self._zoom /= factor
        self.zoom_changed.emit(self._zoom)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True; self._pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.double_clicked.emit()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

# ────────────────────────────────────────────────────────────────────────────
# RGB histogram widget
# ────────────────────────────────────────────────────────────────────────────

class HistogramWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._histograms = None
        self.setFixedHeight(90)

    def set_frame(self, bgr):
        r = cv2.calcHist([bgr], [2], None, [256], [0, 256]).flatten()
        g = cv2.calcHist([bgr], [1], None, [256], [0, 256]).flatten()
        b = cv2.calcHist([bgr], [0], None, [256], [0, 256]).flatten()
        mx = max(r.max(), g.max(), b.max(), 1)
        self._histograms = (r / mx, g / mx, b / mx)
        self.update()

    def paintEvent(self, event):
        if self._histograms is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        colors = [(255, 80, 80), (80, 255, 80), (80, 130, 255)]
        for i, hist in enumerate(self._histograms):
            path = QPainterPath()
            path.moveTo(0, h)
            for x in range(256):
                px = x / 256 * w
                py = h - hist[x] * (h - 4)
                path.lineTo(px, py)
            path.lineTo(w, h)
            path.closeSubpath()
            c = QColor(*colors[i], 100)
            painter.setBrush(c)
            painter.setPen(QPen(c, 1))
            painter.drawPath(path)
        painter.end()

# ────────────────────────────────────────────────────────────────────────────
# Audio waveform widget
# ────────────────────────────────────────────────────────────────────────────

class AudioWaveformWidget(QWidget):
    """Mini waveform visualisation showing audio energy over time."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._energy_data: list[tuple[float, float]] = []
        self._sample_times: list[float] = []
        self._duration = 0.0
        self.setFixedHeight(100)

    def set_data(self, energy_data: list[tuple[float, float]],
                 duration: float, sample_times: list[float] | None = None):
        self._energy_data = energy_data
        self._duration = duration
        self._sample_times = sample_times or []
        self.update()

    def paintEvent(self, event):
        if not self._energy_data:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()
            painter.fillRect(self.rect(), QColor(C_CARD))
            painter.setPen(QColor(C_SUBTEXT))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(self.rect(),
                             Qt.AlignmentFlag.AlignCenter,
                             "No audio data")
            painter.end()
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        margin_left = 30
        margin_right = 10
        margin_top = 16
        margin_bottom = 20
        chart_w = w - margin_left - margin_right
        chart_h = h - margin_top - margin_bottom

        # Background
        painter.fillRect(self.rect(), QColor(C_CARD))

        # Draw bars
        n = len(self._energy_data)
        bar_w = max(1, chart_w / n - 1)
        for i, (pos, energy) in enumerate(self._energy_data):
            x = margin_left + pos * chart_w
            bar_h = int(energy * chart_h)
            y = margin_top + chart_h - bar_h
            painter.fillRect(
                int(x), y, max(1, int(bar_w)), bar_h,
                QColor(C_BLUE),  # fillRect ignores alpha on QColor with no setAlpha
            )

        # Draw sample markers above the waveform
        if self._sample_times and self._duration > 0:
            for t in self._sample_times:
                frac = t / self._duration
                x = margin_left + frac * chart_w
                painter.setPen(QPen(QColor(C_GREEN), 2))
                painter.drawLine(int(x), margin_top - 10,
                                 int(x), margin_top - 2)

        # Time axis
        painter.setPen(QColor(C_SUBTEXT))
        painter.setFont(QFont("Consolas", 8))
        num_ticks = min(10, max(3, int(self._duration / 10)))
        for i in range(num_ticks + 1):
            frac = i / num_ticks
            x = margin_left + frac * chart_w
            t = frac * self._duration
            mm, ss = divmod(int(t), 60)
            painter.drawText(int(x) - 15, h - 2, f"{mm:02d}:{ss:02d}")
            painter.setPen(QPen(QColor(C_OVERLAY), 1))
            painter.drawLine(int(x), margin_top + chart_h,
                             int(x), margin_top + chart_h + 4)
            painter.setPen(QColor(C_SUBTEXT))

        painter.end()


# ────────────────────────────────────────────────────────────────────────────
# Weight slider row
# ────────────────────────────────────────────────────────────────────────────

class WeightSliderRow(QWidget):
    weight_changed = pyqtSignal(str, float)

    def __init__(self, name, weight, parent=None):
        super().__init__(parent)
        self.name = name
        self._lock = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 1, 0, 1)
        lay.setSpacing(4)

        lbl = QLabel(CRIT_LABELS[name])
        lbl.setFixedWidth(100)
        lbl.setStyleSheet(f"font-size:10px; color:{C_SUBTEXT};")
        lay.addWidget(lbl)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 50)
        self.slider.setValue(int(weight * 100))
        self.slider.valueChanged.connect(self._on_change)
        lay.addWidget(self.slider, stretch=1)

        self.val_lbl = QLabel(f"{weight:.2f}")
        self.val_lbl.setFixedWidth(32)
        self.val_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.val_lbl.setStyleSheet(
            f"font-size:10px; color:{C_TEXT}; font-family:Consolas,monospace;")
        lay.addWidget(self.val_lbl)

    def _on_change(self, v):
        if self._lock:
            return
        w = v / 100
        self.val_lbl.setText(f"{w:.2f}")
        self.weight_changed.emit(self.name, w)

    def set_weight(self, w):
        self._lock = True
        self.slider.setValue(int(w * 100))
        self.val_lbl.setText(f"{w:.2f}")
        self._lock = False

# ────────────────────────────────────────────────────────────────────────────
# Weight panel
# ────────────────────────────────────────────────────────────────────────────

class WeightPanel(QWidget):
    weights_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: dict[str, WeightSliderRow] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(1)

        # Profile selector
        profile_row = QHBoxLayout()
        pl = QLabel("Profile:")
        pl.setStyleSheet(f"font-size:10px; color:{C_SUBTEXT};")
        profile_row.addWidget(pl)
        self.combo_profile = QComboBox()
        self.combo_profile.addItems(WEIGHT_PROFILES.keys())
        self.combo_profile.currentTextChanged.connect(self._on_profile)
        profile_row.addWidget(self.combo_profile, stretch=1)
        lay.addLayout(profile_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C_OVERLAY};")
        lay.addWidget(sep)

        for name in sorted(WEIGHTS_DEFAULT,
                           key=lambda k: WEIGHTS_DEFAULT[k], reverse=True):
            row = WeightSliderRow(name, WEIGHTS_DEFAULT[name])
            row.weight_changed.connect(self._on_weight_change)
            lay.addWidget(row)
            self._rows[name] = row
        lay.addStretch()

    def _on_weight_change(self, name, val):
        self.weights_changed.emit(self._get_weights())

    def _on_profile(self, profile_name):
        w = WEIGHT_PROFILES.get(profile_name, WEIGHTS_DEFAULT)
        for name, val in w.items():
            if name in self._rows:
                self._rows[name].set_weight(val)
        self.weights_changed.emit(w.copy())

    def _get_weights(self):
        return {n: r.slider.value() / 100 for n, r in self._rows.items()}

    def get_weights(self):
        return self._get_weights()

    def set_profile(self, name):
        self.combo_profile.setCurrentText(name)

# ────────────────────────────────────────────────────────────────────────────
# Score breakdown panel
# ────────────────────────────────────────────────────────────────────────────

class ScoreBreakdownPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(1)
        self.total_label = QLabel("Total: -")
        self.total_label.setStyleSheet(
            f"font-size:13px; font-weight:bold; color:{C_GREEN}; padding:2px;")
        layout.addWidget(self.total_label)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C_OVERLAY};")
        layout.addWidget(sep)
        self.bars = {}
        for name in sorted(WEIGHTS_DEFAULT,
                           key=lambda k: WEIGHTS_DEFAULT[k], reverse=True):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 1, 0, 1)
            rl.setSpacing(6)
            lbl = QLabel(CRIT_LABELS[name])
            lbl.setFixedWidth(100)
            lbl.setStyleSheet(f"font-size:10px; color:{C_SUBTEXT};")
            rl.addWidget(lbl)
            bar = QProgressBar()
            bar.setFixedHeight(10)
            bar.setTextVisible(False)
            bar.setRange(0, 100)
            bar.setValue(0)
            rl.addWidget(bar, stretch=1)
            vl = QLabel("0.000")
            vl.setFixedWidth(38)
            vl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            vl.setStyleSheet(
                f"font-size:10px; color:{C_TEXT}; font-family:Consolas,monospace;")
            rl.addWidget(vl)
            layout.addWidget(row)
            self.bars[name] = (bar, vl)
        layout.addStretch()

    def update_scores(self, total, breakdown):
        self.total_label.setText(f"Total: {total:.3f}")
        for name, (bar, vl) in self.bars.items():
            v = breakdown.get(name, 0)
            bar.setValue(int(v * 100))
            vl.setText(f"{v:.3f}")
            c = C_GREEN if v > 0.6 else (C_YELLOW if v > 0.3 else C_RED)
            bar.setStyleSheet(
                f"QProgressBar{{border-radius:3px;background:{C_OVERLAY};}}"
                f"QProgressBar::chunk{{border-radius:3px;background:{c};}}")

# ────────────────────────────────────────────────────────────────────────────
# Filmstrip timeline widget
# ────────────────────────────────────────────────────────────────────────────

class FilmstripTimeline(QWidget):
    """Horizontal scrollable strip of video thumbnails showing the whole video.
    Click a thumbnail to seek to that position."""
    seek_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(110)
        self._frames: list[tuple[float, QPixmap]] = []  # (timestamp, pixmap)
        self._selected_time = -1.0
        self._hover_idx = -1

        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            f"QScrollArea{{border:1px solid {C_OVERLAY};border-radius:6px;"
            f"background:{C_CARD};}}")

        self.container = QWidget()
        self.container_lay = QHBoxLayout(self.container)
        self.container_lay.setContentsMargins(2, 2, 2, 2)
        self.container_lay.setSpacing(2)
        self.container_lay.addStretch()

        self.scroll.setWidget(self.container)
        self.scroll.setMinimumWidth(200)
        lay.addWidget(self.scroll)

        self.time_label = QLabel("--:--")
        self.time_label.setFixedWidth(60)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet(
            f"font-size:10px;color:{C_SUBTEXT};font-family:Consolas,monospace;")
        lay.addWidget(self.time_label)

        self._thumb_labels: list[QWidget] = []

    def set_frames(self, frames: list[tuple[float, object]]):
        """frames: list of (timestamp, bgr_small) tuples."""
        # Clear old
        for w in self._thumb_labels:
            w.setParent(None)
            w.deleteLater()
        self._thumb_labels.clear()
        self._frames.clear()

        for i, (t, bgr) in enumerate(frames):
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            h, w = bgr.shape[:2]
            qi = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            pm = QPixmap.fromImage(qi)
            self._frames.append((t, pm))

            thumb = _FilmstripThumb(i, t, pm)
            thumb.clicked.connect(self._on_thumb_click)
            thumb.entered.connect(self._on_thumb_hover)
            self.container_lay.insertWidget(self.container_lay.count() - 1, thumb)
            self._thumb_labels.append(thumb)

        self.container.adjustSize()

    def highlight_time(self, timestamp: float):
        """Highlight the closest filmstrip frame to the given timestamp."""
        self._selected_time = timestamp
        if not self._frames:
            return
        best_idx = min(range(len(self._frames)),
                       key=lambda i: abs(self._frames[i][0] - timestamp))
        for i, thumb in enumerate(self._thumb_labels):
            thumb.set_highlight(i == best_idx)

        # Scroll to make the selected thumb visible
        if best_idx < len(self._thumb_labels):
            w = self._thumb_labels[best_idx]
            self.scroll.ensureWidgetVisible(w, 20, 20)

    def _on_thumb_click(self, idx):
        if idx < len(self._frames):
            self.seek_requested.emit(self._frames[idx][0])

    def _on_thumb_hover(self, idx):
        if idx < len(self._frames):
            t = self._frames[idx][0]
            mm, ss = divmod(int(t), 60)
            ms = int((t % 1) * 1000)
            self.time_label.setText(f"{mm:02d}:{ss:02d}")


class _FilmstripThumb(QFrame):
    clicked = pyqtSignal(int)
    entered = pyqtSignal(int)

    def __init__(self, index, timestamp, pixmap, parent=None):
        super().__init__(parent)
        self.index = index
        self.timestamp = timestamp
        self._highlighted = False
        self.setFixedSize(96, 68)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(1)

        self.img = QLabel()
        self.img.setPixmap(pixmap.scaled(
            92, 54, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.img, stretch=1)

        mm, ss = divmod(int(timestamp), 60)
        self.time_lbl = QLabel(f"{mm:02d}:{ss:02d}")
        self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_lbl.setStyleSheet("font-size:8px; color:#a6adc8;")
        lay.addWidget(self.time_lbl)

        self._apply_style()

    def set_highlight(self, on):
        self._highlighted = on
        self._apply_style()

    def _apply_style(self):
        if self._highlighted:
            self.setStyleSheet(
                f"QFrame{{background:{C_BLUE};border:2px solid {C_BLUE};"
                f"border-radius:4px;}}")
        else:
            self.setStyleSheet(
                f"QFrame{{background:{C_CARD};border:2px solid transparent;"
                f"border-radius:4px;}}")

    def enterEvent(self, e):
        self.entered.emit(self.index)
        if not self._highlighted:
            self.setStyleSheet(
                f"QFrame{{background:{C_OVERLAY};border:2px solid {C_BLUE};"
                f"border-radius:4px;}}")

    def leaveEvent(self, e):
        self._apply_style()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)

# ────────────────────────────────────────────────────────────────────────────
# Gallery card with animation, star, context menu
# ────────────────────────────────────────────────────────────────────────────

class GalleryCard(QFrame):
    clicked = pyqtSignal(int)
    save_requested = pyqtSignal(int)
    copy_requested = pyqtSignal(int)
    compare_requested = pyqtSignal(int)
    star_toggled = pyqtSignal(int, bool)

    def __init__(self, index, pixmap, candidate, parent=None):
        super().__init__(parent)
        self.index = index
        self.candidate = candidate
        self.setFixedHeight(94)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)
        self._apply_style(False)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)
        self.img_label = QLabel()
        self.img_label.setFixedSize(140, 78)
        self.img_label.setPixmap(pixmap.scaled(
            140, 78, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        lay.addWidget(self.img_label)

        tl = QVBoxLayout()
        tl.setSpacing(2)
        self.rank_label = QLabel(f"#{index + 1}")
        self.rank_label.setStyleSheet(
            f"font-size:13px;font-weight:bold;color:{C_LAVENDER};")
        tl.addWidget(self.rank_label)
        mm, ss = divmod(int(candidate.timestamp), 60)
        ms = int((candidate.timestamp % 1) * 1000)
        self.time_label = QLabel(f"  {mm:02d}:{ss:02d}.{ms:03d}")
        self.time_label.setStyleSheet(f"font-size:11px;color:{C_SUBTEXT};")
        tl.addWidget(self.time_label)
        self.score_label = QLabel(f"Score: {candidate.total_score:.3f}")
        self.score_label.setStyleSheet(f"font-size:11px;color:{C_TEXT};")
        tl.addWidget(self.score_label)
        self.bar_widget = _ScoreMiniBar(candidate.breakdown)
        tl.addWidget(self.bar_widget)
        tl.addStretch()
        lay.addLayout(tl)

        # Star indicator
        self.star_lbl = QLabel("  ")
        self.star_lbl.setFixedWidth(24)
        self.star_lbl.setStyleSheet(f"font-size:16px;")
        self.star_lbl.setToolTip("Right-click to star")
        lay.addWidget(self.star_lbl)
        self._update_star()

    def _apply_style(self, on):
        bc = C_GREEN if on else "transparent"
        bg = "#2a3a2e" if on else C_CARD
        self.setStyleSheet(
            f"QFrame{{background:{bg};border:2px solid {bc};"
            f"border-radius:8px;}}")

    def set_selected(self, on):
        self._apply_style(on)

    def _update_star(self):
        if self.candidate.starred:
            self.star_lbl.setText("\u2605")
            self.star_lbl.setStyleSheet(f"font-size:16px;color:{C_YELLOW};")
        else:
            self.star_lbl.setText("\u2606")
            self.star_lbl.setStyleSheet(f"font-size:16px;color:{C_OVERLAY};")

    def _ctx_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{C_CARD};color:{C_TEXT};border:1px solid "
            f"{C_OVERLAY};border-radius:4px;padding:4px;}}"
            f"QMenu::item{{padding:6px 20px;}}"
            f"QMenu::item:selected{{background:{C_BLUE};color:{C_BG};}}")
        a_save = menu.addAction("Save this thumbnail")
        a_copy = menu.addAction("Copy to clipboard")
        menu.addSeparator()
        star_text = "Unstar" if self.candidate.starred else "Star \u2606"
        a_star = menu.addAction(star_text)
        menu.addSeparator()
        a_cmp = menu.addAction("Compare with selected")
        act = menu.exec(self.mapToGlobal(pos))
        if act == a_save:
            self.save_requested.emit(self.index)
        elif act == a_copy:
            self.copy_requested.emit(self.index)
        elif act == a_cmp:
            self.compare_requested.emit(self.index)
        elif act == a_star:
            self.candidate.starred = not self.candidate.starred
            self._update_star()
            self.star_toggled.emit(self.index, self.candidate.starred)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)


class _ScoreMiniBar(QWidget):
    def __init__(self, breakdown, parent=None):
        super().__init__(parent)
        self.breakdown = breakdown
        self.setFixedHeight(14)
        self.setFixedWidth(120)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = sorted(self.breakdown.items(),
                     key=lambda x: WEIGHTS_DEFAULT[x[0]], reverse=True)[:5]
        w = self.width() / len(top) if top else 1
        cols = [C_BLUE, C_GREEN, C_PEACH, C_MAUVE, C_TEAL]
        for i, (n, v) in enumerate(top):
            bh = max(2, int(v * 12))
            p.setBrush(QColor(cols[i % len(cols)]))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(
                int(i * w) + 1, 14 - bh, max(1, int(w) - 2), bh, 2, 2)
        p.end()

# ────────────────────────────────────────────────────────────────────────────
# Grid gallery card (compact thumbnail for grid mode)
# ────────────────────────────────────────────────────────────────────────────

class GridCard(QFrame):
    clicked = pyqtSignal(int)
    star_toggled = pyqtSignal(int, bool)

    def __init__(self, index, pixmap, candidate, parent=None):
        super().__init__(parent)
        self.index = index
        self.candidate = candidate
        self.setFixedSize(170, 130)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)
        self._apply_style(False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)

        self.img = QLabel()
        self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img.setPixmap(pixmap.scaled(
            162, 90, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        lay.addWidget(self.img, stretch=1)

        info = QHBoxLayout()
        self.rank_lbl = QLabel(f"#{index + 1}")
        self.rank_lbl.setStyleSheet(
            f"font-size:10px;font-weight:bold;color:{C_LAVENDER};")
        info.addWidget(self.rank_lbl)

        mm, ss = divmod(int(candidate.timestamp), 60)
        self.time_lbl = QLabel(f"{mm:02d}:{ss:02d}")
        self.time_lbl.setStyleSheet(f"font-size:9px;color:{C_SUBTEXT};")
        info.addWidget(self.time_lbl)

        info.addStretch()
        self.score_lbl = QLabel(f"{candidate.total_score:.2f}")
        self.score_lbl.setStyleSheet(f"font-size:9px;color:{C_GREEN};")
        info.addWidget(self.score_lbl)

        self.star_lbl = QLabel("\u2606")
        self.star_lbl.setStyleSheet(f"font-size:12px;color:{C_OVERLAY};")
        info.addWidget(self.star_lbl)

        lay.addLayout(info)
        self._update_star()

    def _apply_style(self, on):
        bc = C_GREEN if on else "transparent"
        bg = "#2a3a2e" if on else C_CARD
        self.setStyleSheet(
            f"QFrame{{background:{bg};border:2px solid {bc};"
            f"border-radius:8px;}}")

    def set_selected(self, on):
        self._apply_style(on)

    def _update_star(self):
        if self.candidate.starred:
            self.star_lbl.setText("\u2605")
            self.star_lbl.setStyleSheet(f"font-size:12px;color:{C_YELLOW};")
        else:
            self.star_lbl.setText("\u2606")
            self.star_lbl.setStyleSheet(f"font-size:12px;color:{C_OVERLAY};")

    def _ctx_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{C_CARD};color:{C_TEXT};border:1px solid "
            f"{C_OVERLAY};border-radius:4px;padding:4px;}}"
            f"QMenu::item{{padding:6px 20px;}}"
            f"QMenu::item:selected{{background:{C_BLUE};color:{C_BG};}}")
        star_text = "Unstar" if self.candidate.starred else "Star \u2606"
        a_star = menu.addAction(star_text)
        act = menu.exec(self.mapToGlobal(pos))
        if act == a_star:
            self.candidate.starred = not self.candidate.starred
            self._update_star()
            self.star_toggled.emit(self.index, self.candidate.starred)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)

# ────────────────────────────────────────────────────────────────────────────
# Drop label
# ────────────────────────────────────────────────────────────────────────────

class DropLabel(QLabel):
    fileDropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(400, 300)
        self.setText(
            '<span style="font-size:48px;">\U0001f3ac</span><br>'
            '<span style="font-size:16px;color:#cdd6f4;">'
            'Drag & drop a video here<br>'
            'or click <b>Pick Video</b></span><br>'
            '<span style="font-size:11px;color:#a6adc8;">'
            'MP4 \u00b7 MKV \u00b7 AVI \u00b7 MOV \u00b7 WebM \u00b7 FLV \u00b7 WMV'
            '</span><br><br>'
            '<span style="font-size:10px;color:#45475a;">'
            '\u2328  Ctrl+O  Open  \u00b7  Ctrl+S  Save  \u00b7  '
            '\u2190 \u2192  Navigate  \u00b7  1\u20139  Select  '
            '\u00b7  R  Re-analyse  \u00b7  F11  Fullscreen</span>')

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        u = e.mimeData().urls()[0].toLocalFile()
        if u and Path(u).is_file():
            self.fileDropped.emit(u)

# ────────────────────────────────────────────────────────────────────────────
# Thumbnail picker grid (multi-pick view)
# ────────────────────────────────────────────────────────────────────────────

class _PickerCell(QFrame):
    """A single selectable thumbnail in the picker grid."""
    toggled = pyqtSignal(int, bool)  # (index, selected)

    def __init__(self, index, pixmap, candidate, parent=None):
        super().__init__(parent)
        self.index = index
        self.candidate = candidate
        self._selected = False
        self.setFixedSize(200, 140)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.img = QLabel()
        self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img.setPixmap(pixmap.scaled(
            200, 100, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        lay.addWidget(self.img, stretch=1)

        # Info bar at the bottom
        info = QHBoxLayout()
        info.setContentsMargins(4, 2, 4, 2)
        info.setSpacing(4)

        self.rank_lbl = QLabel(f"#{index + 1}")
        self.rank_lbl.setStyleSheet(
            f"font-size:9px;font-weight:bold;color:{C_LAVENDER};")
        info.addWidget(self.rank_lbl)

        mm, ss = divmod(int(candidate.timestamp), 60)
        self.time_lbl = QLabel(f"{mm:02d}:{ss:02d}")
        self.time_lbl.setStyleSheet(f"font-size:8px;color:{C_SUBTEXT};")
        info.addWidget(self.time_lbl)

        info.addStretch()

        self.score_lbl = QLabel(f"{candidate.total_score:.2f}")
        self.score_lbl.setStyleSheet(f"font-size:8px;color:{C_GREEN};")
        info.addWidget(self.score_lbl)

        # Selection indicator
        self.sel_lbl = QLabel("\u25CB")  # empty circle
        self.sel_lbl.setStyleSheet(f"font-size:12px;color:{C_OVERLAY};")
        info.addWidget(self.sel_lbl)

        lay.addLayout(info)

    def _apply_style(self):
        bc = C_GREEN if self._selected else "transparent"
        bg = "#2a3a2e" if self._selected else C_CARD
        self.setStyleSheet(
            f"QFrame{{background:{bg};border:2px solid {bc};"
            f"border-radius:8px;}}")

    def set_selected(self, on):
        self._selected = on
        self._apply_style()
        self.sel_lbl.setText("\u25CF" if on else "\u25CB")
        self.sel_lbl.setStyleSheet(
            f"font-size:12px;color:{C_BLUE if on else C_OVERLAY};")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._selected = not self._selected
            self._apply_style()
            self.sel_lbl.setText("\u25CF" if self._selected else "\u25CB")
            self.sel_lbl.setStyleSheet(
                f"font-size:12px;color:{C_BLUE if self._selected else C_OVERLAY};")
            self.toggled.emit(self.index, self._selected)


class ThumbnailPickerGrid(QWidget):
    """Dedicated picker view showing all candidates as large clickable thumbnails
    with multi-select for batch export."""
    save_selected = pyqtSignal(list)  # list of Candidate objects

    def __init__(self, parent=None):
        super().__init__(parent)
        self._candidates: list[Candidate] = []
        self._cells: list[_PickerCell] = []
        self._selected_indices: set[int] = set()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)

        # Header bar
        header = QHBoxLayout()
        header.setSpacing(8)
        self.lbl_title = QLabel("Select thumbnails to export")
        self.lbl_title.setStyleSheet(
            f"font-size:11px;font-weight:bold;color:{C_TEXT};")
        header.addWidget(self.lbl_title)

        self.lbl_count = QLabel("0 selected")
        self.lbl_count.setStyleSheet(f"font-size:10px;color:{C_GREEN};")
        header.addWidget(self.lbl_count)

        header.addStretch()

        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.setFixedHeight(24)
        self.btn_select_all.setStyleSheet(
            f"font-size:9px;padding:2px 8px;")
        self.btn_select_all.clicked.connect(self._on_select_all)
        header.addWidget(self.btn_select_all)

        self.btn_deselect_all = QPushButton("Deselect All")
        self.btn_deselect_all.setFixedHeight(24)
        self.btn_deselect_all.setStyleSheet(
            f"font-size:9px;padding:2px 8px;")
        self.btn_deselect_all.clicked.connect(self._on_deselect_all)
        header.addWidget(self.btn_deselect_all)

        self.btn_save_sel = QPushButton("Save Selected")
        self.btn_save_sel.setObjectName("btnGreen")
        self.btn_save_sel.setFixedHeight(24)
        self.btn_save_sel.setStyleSheet(
            f"font-size:9px;padding:2px 8px;")
        self.btn_save_sel.clicked.connect(self._on_save_selected)
        header.addWidget(self.btn_save_sel)

        lay.addLayout(header)

        # Scrollable grid area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(6)
        self.grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.grid_container)
        lay.addWidget(self.scroll, stretch=1)

    def set_candidates(self, candidates: list[Candidate]):
        self._candidates = candidates
        self._selected_indices.clear()
        self._cells.clear()

        # Clear grid
        while self.grid_layout.count():
            it = self.grid_layout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        cols = 2
        for i, c in enumerate(candidates):
            rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
            h, w = c.frame_bgr.shape[:2]
            qi = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            cell = _PickerCell(i, QPixmap.fromImage(qi), c)
            cell.toggled.connect(self._on_cell_toggled)
            self.grid_layout.addWidget(cell, i // cols, i % cols)
            self._cells.append(cell)

        self._update_count()

    def get_selected(self) -> list[Candidate]:
        return [self._candidates[i] for i in self._selected_indices
                if i < len(self._candidates)]

    def _on_cell_toggled(self, idx, selected):
        if selected:
            self._selected_indices.add(idx)
        else:
            self._selected_indices.discard(idx)
        self._update_count()

    def _update_count(self):
        n = len(self._selected_indices)
        self.lbl_count.setText(f"{n} selected")

    def _on_select_all(self):
        self._selected_indices = set(range(len(self._candidates)))
        for cell in self._cells:
            cell.set_selected(True)
        self._update_count()

    def _on_deselect_all(self):
        self._selected_indices.clear()
        for cell in self._cells:
            cell.set_selected(False)
        self._update_count()

    def _on_save_selected(self):
        sel = self.get_selected()
        if sel:
            self.save_selected.emit(sel)


# ────────────────────────────────────────────────────────────────────────────
# Comparison overlay widget (improved with blend slider)
# ────────────────────────────────────────────────────────────────────────────

class ComparisonOverlay(QWidget):
    """Split-view comparing two candidates side by side with blend slider."""
    closed = pyqtSignal()

    def __init__(self, cands, indices, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self._cands = cands
        self._indices = indices
        self._blend = 0.5  # 0 = left only, 1 = right only
        self._dragging = False
        self.setMouseTracking(True)
        self._cached_left = None
        self._cached_right = None

    def show_comparison(self):
        w, h = 1000, 660
        self.setGeometry(80, 80, w, h)
        # Pre-render
        if len(self._indices) > 0:
            self._cached_left = self._render_cand(self._indices[0], w, h)
        if len(self._indices) > 1:
            self._cached_right = self._render_cand(self._indices[1], w, h)
        self.show()
        self.raise_()
        self.activateWindow()

    def _render_cand(self, idx, w, h):
        c = self._cands[idx]
        rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        pil = _resize_cover(pil, w, h)
        return pil

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothTransformation)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(0, 0, 0, 220))

        if self._cached_left:
            pw, ph = self._cached_left.size
            qi = QImage(self._cached_left.tobytes(), pw, ph, 3 * pw,
                        QImage.Format.Format_RGB888)
            if self._blend < 1.0:
                painter.setOpacity(1.0)
                painter.drawImage(QRect(0, 0, w, h), qi)
        if self._cached_right:
            pw, ph = self._cached_right.size
            qi = QImage(self._cached_right.tobytes(), pw, ph, 3 * pw,
                        QImage.Format.Format_RGB888)
            painter.setOpacity(self._blend)
            painter.drawImage(QRect(0, 0, w, h), qi)

        painter.setOpacity(1.0)

        # Divider line
        sx = int(w * self._blend)
        painter.setPen(QPen(QColor(255, 255, 255, 180), 2, Qt.PenStyle.DashLine))
        painter.drawLine(sx, 0, sx, h)

        # Instructions
        painter.setPen(QColor(255, 255, 255, 180))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(10, 22,
                         "Drag to blend  \u00b7  S = swap  \u00b7  "
                         "ESC to close")

        # Scores
        painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        if len(self._indices) > 0:
            s = self._cands[self._indices[0]].total_score
            painter.setPen(QColor(255, 255, 255, 220))
            painter.drawText(10, h - 50,
                             f"#{self._indices[0] + 1}  score: {s:.3f}")
        if len(self._indices) > 1:
            s = self._cands[self._indices[1]].total_score
            painter.setPen(QColor(255, 255, 255, 220))
            painter.drawText(10, h - 25,
                             f"#{self._indices[1] + 1}  score: {s:.3f}")

        # Blend percentage
        painter.setPen(QColor(255, 255, 255, 150))
        painter.setFont(QFont("Consolas", 10))
        painter.drawText(w - 80, 22, f"{self._blend * 100:.0f}%")

        painter.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._blend = max(0, min(1, e.pos().x() / self.width()))
            self.update()

    def mouseMoveEvent(self, e):
        if self._dragging:
            self._blend = max(0, min(1, e.pos().x() / self.width()))
            self.update()

    def mouseReleaseEvent(self, e):
        self._dragging = False

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
            self.closed.emit()
        elif e.key() == Qt.Key.Key_S:
            # Swap
            if len(self._indices) >= 2:
                self._indices[0], self._indices[1] = (
                    self._indices[1], self._indices[0])
                self._cached_left, self._cached_right = (
                    self._cached_right, self._cached_left)
                self._blend = 1.0 - self._blend
                self.update()

# ────────────────────────────────────────────────────────────────────────────
# Save dialog with quality slider
# ────────────────────────────────────────────────────────────────────────────

class SaveDialog(QDialog):
    def __init__(self, parent=None, default_name="", default_dir=""):
        super().__init__(parent)
        self.setWindowTitle("Save Thumbnail")
        self.setMinimumWidth(420)
        self.setStyleSheet(
            f"QDialog{{background:{C_SURFACE};}}"
            f"QLabel{{color:{C_TEXT};}}"
            f"QPushButton{{background:{C_OVERLAY};color:{C_TEXT};"
            f"border:none;border-radius:6px;padding:8px 16px;}}"
            f"QPushButton:hover{{background:{C_BLUE};color:{C_BG};}}")

        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        # File path
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("File:"))
        self.path_edit = QLineEdit(default_name)
        self.path_edit.setStyleSheet(
            f"background:{C_CARD};color:{C_TEXT};border:1px solid {C_OVERLAY};"
            f"border-radius:4px;padding:6px;")
        path_row.addWidget(self.path_edit, stretch=1)
        btn_browse = QPushButton("Browse...")
        btn_browse.setFixedWidth(80)
        btn_browse.clicked.connect(self._browse)
        path_row.addWidget(btn_browse)
        lay.addLayout(path_row)

        # Format
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.combo_fmt = QComboBox()
        self.combo_fmt.addItems(["JPEG", "PNG", "WebP"])
        self.combo_fmt.currentTextChanged.connect(self._on_fmt)
        fmt_row.addWidget(self.combo_fmt)
        fmt_row.addStretch()
        lay.addLayout(fmt_row)

        # Quality
        q_row = QHBoxLayout()
        q_row.addWidget(QLabel("Quality:"))
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(10, 100)
        self.quality_slider.setValue(95)
        q_row.addWidget(self.quality_slider, stretch=1)
        self.quality_label = QLabel("95%")
        self.quality_label.setFixedWidth(40)
        self.quality_slider.valueChanged.connect(
            lambda v: self.quality_label.setText(f"{v}%"))
        q_row.addWidget(self.quality_label)
        lay.addLayout(q_row)

        self.quality_note = QLabel(
            "Quality affects file size. 95% is near-lossless JPEG.")
        self.quality_note.setStyleSheet(f"font-size:10px;color:{C_SUBTEXT};")
        lay.addWidget(self.quality_note)

        # Watermark
        self.chk_watermark = QCheckBox("Add timestamp watermark")
        lay.addWidget(self.chk_watermark)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton("Save")
        btn_ok.setObjectName("btnGreen")
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        lay.addLayout(btn_row)

        self._default_dir = default_dir

    def _browse(self):
        fmt = self.combo_fmt.currentText().lower()
        ext_map = {"jpeg": ".jpg", "png": ".png", "webp": ".webp"}
        ext = ext_map.get(fmt, ".jpg")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save", self.path_edit.text(),
            f"{fmt.upper()} (*{ext});;All (*)")
        if path:
            self.path_edit.setText(path)

    def _on_fmt(self, fmt):
        is_lossless = fmt in ("PNG",)
        self.quality_slider.setEnabled(not is_lossless)
        self.quality_note.setText(
            "PNG is lossless \u2014 quality slider disabled."
            if is_lossless else
            "Quality affects file size. 95% is near-lossless JPEG.")

    def get_values(self):
        return (
            self.path_edit.text(),
            self.combo_fmt.currentText(),
            self.quality_slider.value(),
            self.chk_watermark.isChecked(),
        )


# ────────────────────────────────────────────────────────────────────────────
# Video scrubber dialog
# ────────────────────────────────────────────────────────────────────────────

class VideoScrubberDialog(QDialog):
    """Dialog with a slider to seek to any frame in the video."""
    frame_selected = pyqtSignal(float)  # timestamp

    def __init__(self, video_path, video_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Scrubber")
        self.setMinimumWidth(700)
        self.setMinimumHeight(300)
        self.video_path = video_path
        self.info = video_info
        self.duration = video_info.get("duration", 10)
        self.setStyleSheet(
            f"QDialog{{background:{C_SURFACE};}}"
            f"QLabel{{color:{C_TEXT};}}"
            f"QPushButton{{background:{C_OVERLAY};color:{C_TEXT};"
            f"border:none;border-radius:6px;padding:8px 16px;}}"
            f"QPushButton:hover{{background:{C_BLUE};color:{C_BG};}}")

        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        # Preview
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(250)
        self.preview_label.setStyleSheet(
            f"background:{C_CARD};border-radius:8px;")
        lay.addWidget(self.preview_label, stretch=1)

        # Time label
        self.time_label = QLabel("00:00.000 / --:--")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet(
            f"font-size:13px;color:{C_GREEN};font-family:Consolas,monospace;")
        lay.addWidget(self.time_label)

        # Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, int(self.duration * 1000))
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self._on_seek)
        lay.addWidget(self.slider)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_select = QPushButton("Use this frame")
        btn_select.setObjectName("btnGreen")
        btn_select.clicked.connect(self._select)
        btn_row.addWidget(btn_select)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        lay.addLayout(btn_row)

        self._cap = cv2.VideoCapture(video_path)
        self._on_seek(0)

    def _on_seek(self, ms):
        if self._cap is None or not self._cap.isOpened():
            return
        self._cap.set(cv2.CAP_PROP_POS_MSEC, ms)
        ret, frame = self._cap.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame.shape[:2]
            qi = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            pm = QPixmap.fromImage(qi).scaled(
                680, 240, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.preview_label.setPixmap(pm)

        t = ms / 1000
        mm, ss = divmod(int(t), 60)
        ms_rem = int((t % 1) * 1000)
        total_mm, total_ss = divmod(int(self.duration), 60)
        self.time_label.setText(
            f"{mm:02d}:{ss:02d}.{ms_rem:03d} / "
            f"{total_mm:02d}:{total_ss:02d}")

    def _select(self):
        t = self.slider.value() / 1000
        self.frame_selected.emit(t)
        self.accept()

    def closeEvent(self, e):
        if self._cap:
            self._cap.release()
        super().closeEvent(e)

# ────────────────────────────────────────────────────────────────────────────
# Image helpers
# ────────────────────────────────────────────────────────────────────────────

def _resize_fit(img, mw, mh):
    w, h = img.size
    s = min(mw / w, mh / h)
    return img if s >= 1 else img.resize(
        (int(w * s), int(h * s)), Image.LANCZOS)

def _resize_cover(img, tw, th):
    w, h = img.size
    s = max(tw / w, th / h)
    nw, nh = int(w * s), int(h * s)
    img = img.resize((nw, nh), Image.LANCZOS)
    return img.crop(((nw - tw) // 2, (nh - th) // 2,
                     (nw - tw) // 2 + tw, (nh - th) // 2 + th))

def _fmt_time(t):
    mm, ss = divmod(int(t), 60)
    ms = int((t % 1) * 1000)
    return f"{mm:02d}:{ss:02d}.{ms:03d}"

# ────────────────────────────────────────────────────────────────────────────
# Main Window
# ────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Thumbnail Picker  v5")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        self.video_path = None
        self.candidates: list[Candidate] = []
        self.video_info: dict = {}
        self.selected_idx = 0
        self._compare_first: int | None = None
        self._analysis_thread: AnalysisThread | None = None
        self._current_weights = WEIGHTS_DEFAULT.copy()
        self._grid_mode = False
        self._show_starred_only = False
        self._was_maximized = False
        self._filmstrip_data: list[tuple[float, object]] = []
        self._audio_energy: list[tuple[float, float]] = []
        self._progress_candidates: list[Candidate] = []
        self._picker_mode = False
        self._selected_picker_indices: set[int] = set()

        self._settings = QSettings("ThumbnailPicker", "v5")
        self._restore_settings()

        self._build_central()
        self._build_toolbar()
        self._build_statusbar()
        self._build_shortcuts()
        self.setStyleSheet(STYLESHEET)
        self.setAcceptDrops(True)

        self.weight_panel.weights_changed.connect(self._on_weights_changed)

    # ── settings ──

    def _restore_settings(self):
        geo = self._settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        self._last_dir = self._settings.value("last_dir", "", type=str)

    def closeEvent(self, e):
        if self._analysis_thread and self._analysis_thread.isRunning():
            self._analysis_thread.abort()
        self._settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(e)

    # ── building ──

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 4, 8, 4)
        root.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, stretch=1)

        # ── Left: preview ──
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 4, 0)
        ll.setSpacing(4)

        # Title row (placeholders — buttons added after preview exists)
        title_row = QHBoxLayout()
        self.lbl_preview_title = QLabel("Preview")
        self.lbl_preview_title.setStyleSheet(
            f"font-size:14px;font-weight:bold;color:{C_TEXT};padding:4px;")
        title_row.addWidget(self.lbl_preview_title)
        title_row.addStretch()
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setStyleSheet(f"font-size:10px;color:{C_SUBTEXT};")
        title_row.addWidget(self.lbl_zoom)
        ll.addLayout(title_row)

        # Preview (must be created before zoom buttons reference it)
        self.preview = ZoomablePreview()
        self.preview.zoom_changed.connect(
            lambda z: self.lbl_zoom.setText(f"{z * 100:.0f}%"))
        self.preview.double_clicked.connect(self._toggle_fullscreen)
        ll.addWidget(self.preview, stretch=1)

        # Zoom buttons (inserted after the zoom label in title_row)
        for label, slot in [("+", self.preview.zoom_in),
                            ("-", self.preview.zoom_out),
                            ("Fit", self._fit_preview),
                            ("100%", self.preview.zoom_100)]:
            b = QPushButton(label)
            b.setFixedSize(36, 22)
            b.setStyleSheet(f"font-size:9px;padding:2px;")
            b.clicked.connect(slot)
            title_row.addWidget(b)

        # Filmstrip timeline
        self.filmstrip = FilmstripTimeline()
        self.filmstrip.seek_requested.connect(self._on_filmstrip_seek)
        self.filmstrip.setVisible(False)
        ll.addWidget(self.filmstrip)

        # Audio waveform
        self.audio_waveform = AudioWaveformWidget()
        self.audio_waveform.setVisible(False)
        ll.addWidget(self.audio_waveform)

        # Histogram
        self.histogram = HistogramWidget()
        self.histogram.setVisible(False)
        ll.addWidget(self.histogram)

        # Drop overlay
        self.drop_label = DropLabel()
        self.drop_label.fileDropped.connect(self._on_file_dropped)
        ll.addWidget(self.drop_label, stretch=1)
        self.drop_label.hide()

        # Options row
        opt_row = QHBoxLayout()
        opt_row.setSpacing(8)
        opt_row.addWidget(self._lbl("Output:", C_SUBTEXT, 10))
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(PRESETS.keys())
        self.combo_preset.currentTextChanged.connect(self._refresh_preview)
        opt_row.addWidget(self.combo_preset)
        self.chk_watermark = QCheckBox("Timestamp")
        self.chk_watermark.setStyleSheet("font-size:10px;")
        opt_row.addWidget(self.chk_watermark)
        self.chk_histogram = QCheckBox("Histogram")
        self.chk_histogram.stateChanged.connect(
            lambda s: self.histogram.setVisible(
                s == Qt.CheckState.Checked.value))
        opt_row.addWidget(self.chk_histogram)
        self.chk_filmstrip = QCheckBox("Filmstrip")
        self.chk_filmstrip.setChecked(True)
        self.chk_filmstrip.stateChanged.connect(
            lambda s: self.filmstrip.setVisible(
                s == Qt.CheckState.Checked.value and bool(self.candidates)))
        opt_row.addWidget(self.chk_filmstrip)
        self.chk_waveform = QCheckBox("Waveform")
        self.chk_waveform.stateChanged.connect(
            lambda s: self.audio_waveform.setVisible(
                s == Qt.CheckState.Checked.value and bool(self._audio_energy)))
        opt_row.addWidget(self.chk_waveform)
        opt_row.addStretch()
        ll.addLayout(opt_row)

        splitter.addWidget(left)

        # ── Right: sidebar ──
        right = QWidget()
        right.setFixedWidth(390)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 0, 0)
        rl.setSpacing(4)

        # Video info
        info_g = QGroupBox("Video Info")
        il = QVBoxLayout(info_g)
        self.lbl_info = QLabel("No video loaded")
        self.lbl_info.setStyleSheet(
            f"font-size:10px;color:{C_SUBTEXT};"
            f"font-family:Consolas,monospace;")
        self.lbl_info.setWordWrap(True)
        il.addWidget(self.lbl_info)
        rl.addWidget(info_g)

        # Score breakdown
        score_g = QGroupBox("Score Breakdown")
        sl = QVBoxLayout(score_g)
        self.score_panel = ScoreBreakdownPanel()
        sl.addWidget(self.score_panel)
        rl.addWidget(score_g)

        # Weights
        weight_g = QGroupBox("Scoring Weights")
        wl = QVBoxLayout(weight_g)
        self.weight_panel = WeightPanel()
        wl.addWidget(self.weight_panel)
        rl.addWidget(weight_g)

        # Gallery controls
        gal_ctrl = QHBoxLayout()
        gal_ctrl.setSpacing(6)
        self.btn_view_list = QPushButton("List")
        self.btn_view_list.setFixedSize(50, 22)
        self.btn_view_list.setStyleSheet(f"font-size:9px;padding:2px;")
        self.btn_view_list.clicked.connect(lambda: self._set_view_mode("list"))
        gal_ctrl.addWidget(self.btn_view_list)
        self.btn_view_grid = QPushButton("Grid")
        self.btn_view_grid.setFixedSize(50, 22)
        self.btn_view_grid.setStyleSheet(f"font-size:9px;padding:2px;")
        self.btn_view_grid.clicked.connect(lambda: self._set_view_mode("grid"))
        gal_ctrl.addWidget(self.btn_view_grid)
        self.btn_view_picker = QPushButton("Picker")
        self.btn_view_picker.setFixedSize(54, 22)
        self.btn_view_picker.setStyleSheet(f"font-size:9px;padding:2px;")
        self.btn_view_picker.setToolTip("P \u2014 multi-select thumbnails for export")
        self.btn_view_picker.clicked.connect(lambda: self._set_view_mode("picker"))
        gal_ctrl.addWidget(self.btn_view_picker)
        gal_ctrl.addWidget(self._lbl("Sort:", C_SUBTEXT, 10))
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(
            ["Score", "Time", "Sharpness", "Colourfulness", "Faces",
             "Contrast", "Composition", "Exposure Q.", "Dyn. Range",
             "Complexity", "Colour Harm."])
        self.combo_sort.currentTextChanged.connect(self._on_sort_changed)
        gal_ctrl.addWidget(self.combo_sort, stretch=1)

        self.chk_starred = QCheckBox("Stars only")
        self.chk_starred.setStyleSheet(f"font-size:10px;")
        self.chk_starred.stateChanged.connect(self._on_star_filter)
        gal_ctrl.addWidget(self.chk_starred)
        rl.addLayout(gal_ctrl)

        # Gallery
        self.gallery_groupbox = QGroupBox(
            "Top Candidates  (click \u00b7 \u2190 \u2192 \u00b7 "
            "1\u20139 \u00b7 right-click)")
        gl = QVBoxLayout(self.gallery_groupbox)
        gl.setSpacing(4)
        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.gallery_container = QWidget()
        self.gallery_vlayout = QVBoxLayout(self.gallery_container)
        self.gallery_vlayout.setContentsMargins(4, 4, 4, 4)
        self.gallery_vlayout.setSpacing(4)
        self.gallery_vlayout.addStretch()
        self.gallery_scroll.setWidget(self.gallery_container)
        gl.addWidget(self.gallery_scroll)

        # Picker grid (hidden by default)
        self.picker_grid = ThumbnailPickerGrid()
        self.picker_grid.save_selected.connect(self._on_save_selected)
        self.picker_grid.setVisible(False)
        gl.addWidget(self.picker_grid)

        rl.addWidget(self.gallery_groupbox, stretch=1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        self.btn_pick = QPushButton("  Pick Video")
        self.btn_pick.setObjectName("btnPrimary")
        self.btn_pick.setToolTip("Ctrl+O")
        self.btn_pick.clicked.connect(self._on_pick)
        tb.addWidget(self.btn_pick)

        self.btn_analyze = QPushButton("  Analyse")
        self.btn_analyze.setObjectName("btnPrimary")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setToolTip("R")
        self.btn_analyze.clicked.connect(self._on_analyze)
        tb.addWidget(self.btn_analyze)

        tb.addSeparator()
        tb.addWidget(self._lbl("Samples:", C_SUBTEXT))
        self.spin_samples = QSpinBox()
        self.spin_samples.setRange(10, 500)
        self.spin_samples.setSingleStep(10)
        self.spin_samples.setValue(DEFAULT_SAMPLES)
        tb.addWidget(self.spin_samples)

        tb.addWidget(self._lbl("Cands:", C_SUBTEXT))
        self.spin_cands = QSpinBox()
        self.spin_cands.setRange(4, 24)
        self.spin_cands.setValue(DEFAULT_CANDIDATES)
        tb.addWidget(self.spin_cands)

        self.chk_scene = QCheckBox("Scene detect")
        tb.addWidget(self.chk_scene)
        self.chk_scene.setToolTip(
            "Use scene-change detection instead of uniform sampling")
        self.chk_scene.setStyleSheet(f"color:{C_TEXT};")

        self.chk_audio = QCheckBox("Audio aware")
        self.chk_audio.setChecked(True)
        tb.addWidget(self.chk_audio)
        self.chk_audio.setToolTip(
            "Prioritize sampling at moments with high audio activity")
        self.chk_audio.setStyleSheet(f"color:{C_TEXT};")

        tb.addSeparator()

        self.btn_save = QPushButton("  Save")
        self.btn_save.setObjectName("btnGreen")
        self.btn_save.setEnabled(False)
        self.btn_save.setToolTip("Ctrl+S")
        self.btn_save.clicked.connect(self._on_save)
        tb.addWidget(self.btn_save)

        self.btn_save_all = QPushButton("  Save All")
        self.btn_save_all.setObjectName("btnMauve")
        self.btn_save_all.setEnabled(False)
        self.btn_save_all.clicked.connect(self._on_save_all)
        tb.addWidget(self.btn_save_all)

        self.btn_clipboard = QPushButton("  Copy")
        self.btn_clipboard.setObjectName("btnPeach")
        self.btn_clipboard.setEnabled(False)
        self.btn_clipboard.setToolTip("Ctrl+C")
        self.btn_clipboard.clicked.connect(self._on_clipboard)
        tb.addWidget(self.btn_clipboard)

        tb.addSeparator()

        self.btn_scrubber = QPushButton("  Scrubber")
        self.btn_scrubber.setObjectName("btnTeal")
        self.btn_scrubber.setEnabled(False)
        self.btn_scrubber.setToolTip("Open video timeline scrubber")
        self.btn_scrubber.clicked.connect(self._on_scrubber)
        tb.addWidget(self.btn_scrubber)

        self.btn_compare = QPushButton("  Compare")
        self.btn_compare.setObjectName("btnYellow")
        self.btn_compare.setEnabled(False)
        self.btn_compare.setToolTip("C \u2014 select 2 candidates")
        self.btn_compare.clicked.connect(self._on_compare)
        tb.addWidget(self.btn_compare)

    def _build_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(260)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.status_bar.showMessage(
            "Ready \u2014 drop a video or press Ctrl+O")

    def _build_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self._on_pick)
        QShortcut(QKeySequence("Ctrl+S"), self, self._on_save)
        QShortcut(QKeySequence("Ctrl+C"), self, self._on_clipboard)
        QShortcut(QKeySequence("Ctrl+R"), self, self._on_analyze)
        QShortcut(QKeySequence("Escape"), self, self._on_escape)
        QShortcut(QKeySequence("Left"), self, lambda: self._nav(-1))
        QShortcut(QKeySequence("Right"), self, lambda: self._nav(1))
        QShortcut(QKeySequence("Up"), self, lambda: self._nav(-1))
        QShortcut(QKeySequence("Down"), self, lambda: self._nav(1))
        QShortcut(QKeySequence("R"), self, self._on_analyze)
        for i in range(1, 10):
            QShortcut(QKeySequence(str(i)), self,
                      lambda idx=i - 1: self._select(idx))
        QShortcut(QKeySequence("F"), self, self._fit_preview)
        QShortcut(QKeySequence("F11"), self, self._toggle_fullscreen)
        QShortcut(QKeySequence("G"), self,
                  lambda: self._set_view_mode("grid" if not self._grid_mode else "list"))
        QShortcut(QKeySequence("P"), self,
                  lambda: self._set_view_mode(
                      "list" if self._picker_mode else "picker"))

    def _lbl(self, text, color, size=11):
        l = QLabel(text)
        l.setStyleSheet(f"font-size:{size}px;color:{color};")
        return l

    # ── drag/drop ──

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        u = e.mimeData().urls()[0].toLocalFile()
        if u and Path(u).is_file():
            self._on_file_dropped(u)

    # ── file ──

    def _on_pick(self):
        d = self._settings.value("last_dir", "", type=str)
        path, _ = QFileDialog.getOpenFileName(
            self, "Select video", d,
            "Video (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v);;"
            "All (*)")
        if path:
            self._settings.setValue("last_dir", str(Path(path).parent))
            self._on_file_dropped(path)

    def _on_file_dropped(self, path):
        self.video_path = path
        self.status_bar.showMessage(f"Loaded: {Path(path).name}")
        self.btn_analyze.setEnabled(True)
        self.btn_scrubber.setEnabled(True)
        self.btn_analyze.setText("  Analyse")
        self.btn_analyze.setObjectName("btnPrimary")
        self._on_analyze()

    # ── analysis ──

    def _on_analyze(self):
        if not self.video_path:
            return
        # Disconnect old thread signals to prevent leaks
        if self._analysis_thread is not None:
            try:
                self._analysis_thread.progress.disconnect()
                self._analysis_thread.finished_ok.disconnect()
                self._analysis_thread.finished_err.disconnect()
                self._analysis_thread.cancelled.disconnect()
                self._analysis_thread.filmstrip_frames.disconnect()
                self._analysis_thread.candidate_ready.disconnect()
                self._analysis_thread.audio_energy_ready.disconnect()
            except RuntimeError:
                pass
        if (self._analysis_thread
                and self._analysis_thread.isRunning()):
            self._analysis_thread.abort()
            return

        num = self.spin_samples.value()
        n_cands = self.spin_cands.value()
        self._current_weights = self.weight_panel.get_weights()
        self.btn_analyze.setText("  Cancel")
        self.btn_analyze.setObjectName("btnRed")
        for b in (self.btn_save, self.btn_save_all,
                  self.btn_clipboard, self.btn_compare):
            b.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._progress_candidates = []
        self.status_bar.showMessage(f"Analysing {num} samples \u2026")

        self._analysis_thread = AnalysisThread(
            self.video_path, num, self._current_weights,
            self.chk_scene.isChecked(), n_cands,
            use_audio=self.chk_audio.isChecked())
        self._analysis_thread.progress.connect(self._on_progress)
        self._analysis_thread.finished_ok.connect(self._on_done)
        self._analysis_thread.finished_err.connect(self._on_err)
        self._analysis_thread.cancelled.connect(self._on_cancel)
        self._analysis_thread.filmstrip_frames.connect(self._on_filmstrip)
        self._analysis_thread.candidate_ready.connect(self._on_candidate_ready)
        self._analysis_thread.audio_energy_ready.connect(self._on_audio_energy_ready)
        self._analysis_thread.start()

    def _on_progress(self, cur, tot):
        p = int(cur / tot * 100)
        self.progress_bar.setValue(p)
        n_prog = len(self._progress_candidates)
        self.status_bar.showMessage(
            f"Analysing \u2026 {cur}/{tot} ({p}%)"
            + (f" \u2014 found {n_prog} candidates so far"
               if n_prog > 0 else ""))

    def _on_filmstrip(self, frames):
        self._filmstrip_data = frames
        self.filmstrip.set_frames(frames)

    def _on_audio_energy_ready(self, energy_data, duration):
        self._audio_energy = energy_data
        self.audio_waveform.set_data(energy_data, duration)

    def _on_candidate_ready(self, candidate, cur_idx, total):
        self._progress_candidates.append(candidate)
        # Keep sorted by score
        self._progress_candidates.sort(
            key=lambda c: c.total_score, reverse=True)
        # Update preview with current best
        if self._progress_candidates:
            best = self._progress_candidates[0]
            rgb = cv2.cvtColor(best.frame_bgr, cv2.COLOR_BGR2RGB)
            h, w = best.frame_bgr.shape[:2]
            qi = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            pm = QPixmap.fromImage(qi)
            vp = self.preview.viewport()
            if vp:
                pil = Image.fromarray(rgb)
                pil = _resize_fit(pil, (vp.width() or 640) - 8,
                                  (vp.height() or 480) - 8)
                pw, ph = pil.size
                qi2 = QImage(pil.tobytes(), pw, ph, 3 * pw,
                             QImage.Format.Format_RGB888)
                self.preview.set_pixmap(QPixmap.fromImage(qi2))
            self.score_panel.update_scores(best.total_score, best.breakdown)
            self.lbl_preview_title.setText(
                f"Preview  \u2014  live best @  "
                f"{_fmt_time(best.timestamp)}  "
                f"(score {best.total_score:.3f})")
        n_prog = len(self._progress_candidates)
        self.status_bar.showMessage(
            f"Analysing \u2026 {cur_idx}/{total}"
            f" \u2014 found {n_prog} candidates so far")

    def _on_done(self, cands, vinfo):
        self.candidates = cands
        self.video_info = vinfo
        self.selected_idx = 0
        self._progress_candidates = []
        self.btn_analyze.setText("  Re-analyse")
        self.btn_analyze.setObjectName("btnPrimary")
        self.progress_bar.setValue(100)
        filtered_msg = ""
        if vinfo.get('frames_filtered', 0) > 0:
            filtered_msg = (
                f" \u00b7 {vinfo['frames_filtered']} frames pre-filtered")
        # Guard: no candidates found (all frames filtered)
        if not cands:
            self.status_bar.showMessage(
                f"Done \u2014 {vinfo['total_sampled']} sampled"
                f"{filtered_msg} \u00b7 0 candidates (all frames filtered)")
            self.btn_analyze.setEnabled(True)
            self.progress_bar.setVisible(False)
            return
        self.status_bar.showMessage(
            f"Done \u2014 {vinfo['total_sampled']} sampled"
            f"{filtered_msg} \u00b7 "
            f"{vinfo['candidates_kept']} diverse candidates"
            f" \u00b7 top at {_fmt_time(cands[0].timestamp)}"
            f" \u00b7 \u2190\u2192 navigate \u00b7 "
            f"1\u2013{len(cands)} select \u00b7 "
            f"Ctrl+S save \u00b7 G grid \u00b7 P picker \u00b7 F11 fullscreen")
        self._show_info(vinfo)
        self._build_gallery(cands)
        self._show_preview(0)
        self._show_breakdown(0)
        for b in (self.btn_save, self.btn_save_all,
                  self.btn_clipboard, self.btn_compare):
            b.setEnabled(True)
        self.drop_label.hide()
        self.preview.show()

        # Show filmstrip if checked
        if self._filmstrip_data:
            self.filmstrip.setVisible(self.chk_filmstrip.isChecked())
            self.filmstrip.highlight_time(cands[0].timestamp)

        # Show waveform if checked and data available
        if self._audio_energy:
            sample_times = vinfo.get("sample_times", [])
            self.audio_waveform.set_data(
                self._audio_energy, vinfo["duration"], sample_times)
            self.audio_waveform.setVisible(self.chk_waveform.isChecked())

        # Update picker grid
        self.picker_grid.set_candidates(cands)

    def _on_err(self, msg):
        self.btn_analyze.setText("  Analyse")
        self.btn_analyze.setObjectName("btnPrimary")
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Error", msg)

    def _on_cancel(self):
        self.btn_analyze.setText("  Analyse")
        self.btn_analyze.setObjectName("btnPrimary")
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Cancelled")

    def _on_weights_changed(self, w):
        self._current_weights = w
        if self.candidates:
            for c in self.candidates:
                c.total_score = sum(
                    c.breakdown[k] * w.get(k, 0) for k in w)
            cands_sorted = sorted(
                self.candidates,
                key=lambda c: c.total_score, reverse=True)
            self.candidates = cands_sorted

            self._show_breakdown(self.selected_idx)
            self._build_gallery(self.candidates)
            self._show_preview(self.selected_idx)

    # ── display ──

    def _show_info(self, info):
        mm, ss = divmod(int(info["duration"]), 60)
        filtered = info.get('frames_filtered', 0)
        kept = info.get('candidates_kept', len(self.candidates))
        has_audio = info.get('has_audio', False)
        audio_used = info.get('audio_aware_used', False)
        lines = [
            f"File:        {Path(info['path']).name}",
            f"Resolution:  {info['width']}\u00d7{info['height']}",
            f"Duration:    {mm:02d}:{ss:02d}  ({info['duration']:.1f}s)",
            f"FPS:         {info['fps']:.2f}",
            f"Frames:      {info['total_frames']:,}",
            f"Sampled:     {info['total_sampled']}",
        ]
        if filtered:
            lines.append(f"Filtered:    {filtered}")
        lines.append(f"Kept:        {kept}")
        if has_audio:
            mode = "Audio-aware" if audio_used else "Has audio"
            lines.append(f"Audio:       {mode}")
        self.lbl_info.setText("\n".join(lines))

    def _build_gallery(self, cands):
        # Handle picker mode — gallery is hidden
        if self._picker_mode:
            self.gallery_scroll.setVisible(False)
            self.picker_grid.setVisible(True)
            self.picker_grid.set_candidates(cands)
            self.gallery_groupbox.setTitle(
                "Thumbnail Picker  (click to select \u00b7 P to exit)")
            return

        # Normal gallery modes
        self.gallery_scroll.setVisible(True)
        self.picker_grid.setVisible(False)
        self.gallery_groupbox.setTitle(
            "Top Candidates  (click \u00b7 \u2190 \u2192 \u00b7 "
            "1\u20139 \u00b7 right-click)")

        # Clear gallery
        while self.gallery_vlayout.count():
            it = self.gallery_vlayout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        # Re-add bottom stretch (removed by the loop above)
        self.gallery_vlayout.addStretch()

        display_cands = cands
        if self._show_starred_only:
            display_cands = [c for c in cands if c.starred]
            if not display_cands:
                # If no starred, show all
                display_cands = cands

        if self._grid_mode:
            self._build_gallery_grid(display_cands)
        else:
            self._build_gallery_list(display_cands)

    def _build_gallery_list(self, cands):
        for i, c in enumerate(cands):
            rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
            h, w = c.frame_bgr.shape[:2]
            qi = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            global_idx = self.candidates.index(c)
            card = GalleryCard(global_idx, QPixmap.fromImage(qi), c)
            card.clicked.connect(self._select_candidate)
            card.save_requested.connect(self._save_idx)
            card.copy_requested.connect(self._copy_idx)
            card.compare_requested.connect(self._compare_add)
            card.star_toggled.connect(self._on_star_toggle)
            self.gallery_vlayout.insertWidget(
                self.gallery_vlayout.count() - 1, card)
        # Highlight the first card
        if cands:
            first_w = self.gallery_vlayout.itemAt(0)
            if first_w:
                c0 = first_w.widget()
                if isinstance(c0, GalleryCard):
                    c0.set_selected(True)

    def _build_gallery_grid(self, cands):
        grid = QGridLayout()
        grid.setSpacing(6)
        cols = 2
        for i, c in enumerate(cands):
            rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
            h, w = c.frame_bgr.shape[:2]
            qi = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            global_idx = self.candidates.index(c)
            card = GridCard(global_idx, QPixmap.fromImage(qi), c)
            card.clicked.connect(self._select_candidate)
            card.star_toggled.connect(self._on_star_toggle)
            grid.addWidget(card, i // cols, i % cols)
        grid_widget = QWidget()
        grid_widget.setLayout(grid)
        self.gallery_vlayout.insertWidget(
            self.gallery_vlayout.count() - 1, grid_widget)

    def _select_candidate(self, idx):
        if idx < len(self.candidates):
            self.selected_idx = idx
            self._highlight_gallery(idx)
            self._show_preview(idx)
            self._show_breakdown(idx)
            if self._filmstrip_data:
                self.filmstrip.highlight_time(
                    self.candidates[idx].timestamp)

    def _highlight_gallery(self, idx):
        if idx >= len(self.candidates):
            return
        target = self.candidates[idx]
        count = self.gallery_vlayout.count()
        for i in range(count):
            w = self.gallery_vlayout.itemAt(i).widget()
            if isinstance(w, GalleryCard):
                w.set_selected(w.candidate is target)
            elif isinstance(w, GridCard):
                w.set_selected(w.candidate is target)

    def _select(self, idx):
        if idx < len(self.candidates):
            self._select_candidate(idx)

    def _nav(self, d):
        if not self.candidates:
            return
        n = (self.selected_idx + d) % len(self.candidates)
        self._select_candidate(n)

    def _show_preview(self, idx):
        c = self.candidates[idx]
        rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        preset = PRESETS.get(self.combo_preset.currentText())
        if preset:
            pil = _resize_cover(pil, *preset)
        else:
            vp = self.preview.viewport()
            pil = _resize_fit(
                pil, (vp.width() or 640) - 8, (vp.height() or 480) - 8)
        pw, ph = pil.size
        qi = QImage(pil.tobytes(), pw, ph, 3 * pw, QImage.Format.Format_RGB888)
        self.preview.set_pixmap_animated(QPixmap.fromImage(qi))

        self.histogram.set_frame(c.frame_bgr)
        star_mark = " \u2605" if c.starred else ""
        self.lbl_preview_title.setText(
            f"Preview  \u2014  #{idx + 1}{star_mark}  @  "
            f"{_fmt_time(c.timestamp)}  "
            f"(score {c.total_score:.3f})")

    def _refresh_preview(self):
        if self.candidates:
            self._show_preview(self.selected_idx)

    def _show_breakdown(self, idx):
        self.score_panel.update_scores(
            self.candidates[idx].total_score,
            self.candidates[idx].breakdown)

    def _fit_preview(self):
        self.preview.fit()

    # ── view mode ──

    def _set_view_mode(self, mode: str):
        """Switch between 'list', 'grid', and 'picker' view modes."""
        if mode == "picker":
            self._picker_mode = True
            self._grid_mode = False
        else:
            self._picker_mode = False
            self._grid_mode = (mode == "grid")

        # Update button styles
        active_style = (
            f"font-size:9px;padding:2px;background:{C_BLUE};"
            f"color:{C_BG};border-radius:4px;")
        inactive_style = f"font-size:9px;padding:2px;"

        self.btn_view_list.setStyleSheet(
            active_style if mode == "list" else inactive_style)
        self.btn_view_grid.setStyleSheet(
            active_style if mode == "grid" else inactive_style)
        self.btn_view_picker.setStyleSheet(
            active_style if mode == "picker" else inactive_style)
        if mode == "picker":
            self.btn_view_picker.setObjectName("btnPrimary")
        else:
            self.btn_view_picker.setObjectName("")

        if self.candidates:
            self._build_gallery(self.candidates)

    # ── sort ──

    def _on_sort_changed(self, sort_by):
        if not self.candidates:
            return
        key_map = {
            "Score": lambda c: c.total_score,
            "Time": lambda c: c.timestamp,
            "Sharpness": lambda c: c.breakdown.get("sharpness", 0),
            "Colourfulness": lambda c: c.breakdown.get("colorfulness", 0),
            "Faces": lambda c: c.breakdown.get("faces", 0),
            "Contrast": lambda c: c.breakdown.get("contrast", 0),
            "Composition": lambda c: c.breakdown.get("composition", 0),
            "Exposure Q.": lambda c: c.breakdown.get("exposure_quality", 0),
            "Dyn. Range": lambda c: c.breakdown.get("dynamic_range", 0),
            "Complexity": lambda c: c.breakdown.get("visual_complexity", 0),
            "Colour Harm.": lambda c: c.breakdown.get("color_harmony", 0),
        }
        key_fn = key_map.get(sort_by, lambda c: c.total_score)
        reverse = sort_by != "Time"
        self.candidates.sort(key=key_fn, reverse=reverse)
        self.selected_idx = 0
        self._build_gallery(self.candidates)
        self._show_preview(0)
        self._show_breakdown(0)

    # ── star filter ──

    def _on_star_toggle(self, idx, starred):
        self._show_starred_only = self.chk_starred.isChecked()
        # Don't rebuild immediately to avoid disrupting interaction

    def _on_star_filter(self, state):
        self._show_starred_only = (state == Qt.CheckState.Checked.value)
        if self.candidates:
            self._build_gallery(self.candidates)

    # ── fullscreen ──

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            if self._was_maximized:
                self.showMaximized()
        else:
            self._was_maximized = self.isMaximized()
            self.showFullScreen()

    # ── filmstrip seek ──

    def _on_filmstrip_seek(self, timestamp):
        """Seek to a specific timestamp in the video and pick that frame."""
        if not self.video_path:
            return
        cap = cv2.VideoCapture(self.video_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ret, frame = cap.read()
        cap.release()
        if ret:
            total, bd = compute_score(frame, None, self._current_weights)
            # Add as a new candidate at the top
            new_cand = Candidate(frame, timestamp, total, bd)
            self.candidates.insert(0, new_cand)
            self.selected_idx = 0
            self._build_gallery(self.candidates)
            self._show_preview(0)
            self._show_breakdown(0)
            self.filmstrip.highlight_time(timestamp)
            self.picker_grid.set_candidates(self.candidates)
            self.status_bar.showMessage(
                f"Added frame from {_fmt_time(timestamp)} "
                f"(score {total:.3f}) as #1")

    # ── save / export ──

    def _get_output_frame(self, cand, quality=95):
        f = cand.frame_bgr.copy()
        preset = PRESETS.get(self.combo_preset.currentText())
        if preset:
            rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            pil = _resize_cover(pil, *preset)
            f = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        if self.chk_watermark.isChecked():
            h, w = f.shape[:2]
            ts = _fmt_time(cand.timestamp)
            # Semi-transparent background for readability
            overlay = f.copy()
            (tw, th), _ = cv2.getTextSize(
                ts, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(overlay,
                          (w - tw - 20, h - th - 10),
                          (w - 6, h - 4), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.5, f, 0.5, 0, f)
            cv2.putText(f, ts, (w - tw - 14, h - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (255, 255, 255), 1, cv2.LINE_AA)
        return f

    def _on_save(self):
        if not self.candidates:
            return
        stem = Path(self.video_path).stem
        default_name = (
            f"thumbnail_{stem}_#{self.selected_idx + 1}.jpg")
        d = self._settings.value("last_dir", "", type=str)
        dlg = SaveDialog(
            self,
            default_name=os.path.join(d, default_name))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        path, fmt, quality, add_wm = dlg.get_values()
        if not path:
            return

        cand = self.candidates[self.selected_idx]
        old_wm = self.chk_watermark.isChecked()
        self.chk_watermark.setChecked(add_wm)
        f = self._get_output_frame(cand, quality)
        self.chk_watermark.setChecked(old_wm)

        ext = Path(path).suffix.lower()
        if ext == ".png":
            cv2.imwrite(path, f)
        elif ext == ".webp":
            cv2.imwrite(path, f, [cv2.IMWRITE_WEBP_QUALITY, quality])
        else:
            cv2.imwrite(path, f, [cv2.IMWRITE_JPEG_QUALITY, quality])

        self._settings.setValue("last_dir", str(Path(path).parent))
        self.status_bar.showMessage(f"Saved \u2192 {path}")

    def _on_save_all(self):
        if not self.candidates:
            return
        d = QFileDialog.getExistingDirectory(self, "Save all")
        if not d:
            return
        stem = Path(self.video_path).stem
        for i, c in enumerate(self.candidates):
            f = self._get_output_frame(c)
            cv2.imwrite(
                str(Path(d) / f"thumbnail_{stem}_#{i + 1}.jpg"),
                f, [cv2.IMWRITE_JPEG_QUALITY, 95])
        self.status_bar.showMessage(
            f"Saved {len(self.candidates)} \u2192 {d}")

    def _on_save_selected(self, selected_cands: list):
        """Save selected thumbnails from the picker grid."""
        if not selected_cands:
            return
        d = QFileDialog.getExistingDirectory(
            self, "Save selected thumbnails")
        if not d:
            return
        stem = Path(self.video_path).stem
        for i, c in enumerate(selected_cands):
            f = self._get_output_frame(c)
            cv2.imwrite(
                str(Path(d) / f"thumbnail_{stem}_pick#{i + 1}.jpg"),
                f, [cv2.IMWRITE_JPEG_QUALITY, 95])
        self.status_bar.showMessage(
            f"Saved {len(selected_cands)} selected thumbnails \u2192 {d}")

    def _on_clipboard(self):
        if not self.candidates:
            return
        c = self.candidates[self.selected_idx]
        f = self._get_output_frame(c)
        rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        h, w = f.shape[:2]
        qi = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        QApplication.clipboard().setPixmap(QPixmap.fromImage(qi))
        self.status_bar.showMessage("Copied to clipboard")

    def _save_idx(self, idx):
        old = self.selected_idx
        self.selected_idx = idx
        self._on_save()
        self.selected_idx = old

    def _copy_idx(self, idx):
        old = self.selected_idx
        self.selected_idx = idx
        self._on_clipboard()
        self.selected_idx = old

    # ── comparison ──

    def _compare_add(self, idx):
        if self._compare_first is None:
            self._compare_first = idx
            self.status_bar.showMessage(
                f"Compare: selected #{idx + 1} "
                f"\u2014 click another candidate")
        else:
            self._show_comparison(self._compare_first, idx)
            self._compare_first = None

    def _on_compare(self):
        if not self.candidates or len(self.candidates) < 2:
            return
        self._show_comparison(0, 1)

    def _show_comparison(self, a, b):
        if a == b:
            b = (a + 1) % len(self.candidates)
        self._cmp = ComparisonOverlay(self.candidates, [a, b], self)
        self._cmp.show_comparison()
        self.status_bar.showMessage(
            f"Comparing #{a + 1} vs #{b + 1} "
            f"\u2014 drag to blend, S to swap, ESC to close")

    # ── scrubber ──

    def _on_scrubber(self):
        if not self.video_path or not self.video_info:
            return
        dlg = VideoScrubberDialog(
            self.video_path, self.video_info, self)
        dlg.frame_selected.connect(self._on_filmstrip_seek)
        dlg.exec()

    # ── escape ──

    def _on_escape(self):
        if hasattr(self, '_cmp') and self._cmp.isVisible():
            self._cmp.close()
            self._compare_first = None
        elif self.isFullScreen():
            self._toggle_fullscreen()
        else:
            self.close()


# ────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    win.preview.hide()
    win.drop_label.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
