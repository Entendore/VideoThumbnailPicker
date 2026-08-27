"""Streaming Thumbnail Picker — professional LIVE overlay tool.

Features:
  * Multi-image strip with cycling, reorder (drag), and remove
  * Video analysis: open video, extract frames, CV smart-pick (sharpness, faces, color, contrast, composition)
  * Draggable LIVE badge on the preview canvas
  * Zoom / pan on the preview (scroll wheel + middle-click drag)
  * Undo / redo for every badge change
  * Copy composite to clipboard, save individual or batch-export all
  * Right-click context menu on the preview
  * Keyboard shortcuts (arrows, Ctrl+Z/Y, Ctrl+C/S/V/O, Delete, Home/End)
  * Fit / 1:1 / Fill preview modes

Run with:  python thumbnail_picker.py
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import math
import tempfile
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from PySide6.QtCore import (
    Qt, QRect, QRectF, QSize, QPoint, Signal, QPointF,
    QMimeData, QThread,
)
from PySide6.QtGui import (
    QAction, QColor, QFont, QFontMetrics, QClipboard,
    QImage, QPainter, QPainterPath, QPixmap, QPen, QBrush,
    QDragEnterEvent, QDropEvent, QMouseEvent, QWheelEvent,
    QShortcut, QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox,
    QDoubleSpinBox, QFileDialog, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSlider, QSpinBox,
    QVBoxLayout, QWidget, QInputDialog, QFrame, QMenu,
    QProgressBar, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
    QTabWidget, QFontComboBox, QTextEdit,
)

# ══════════════════════════════════════════════════════════════════════════════
# Platform presets & badge style data
# ══════════════════════════════════════════════════════════════════════════════

PRESETS: dict[str, Optional[Tuple[int, int]]] = {
    "Original":            None,
    "YouTube 720p":        (1280, 720),
    "YouTube 1080p":       (1920, 1080),
    "Twitch":              (1920, 1080),
    "Kick":                (1920, 1080),
    "TikTok 9:16":         (1080, 1920),
    "Instagram 1:1":       (1080, 1080),
    "Facebook 16:9":       (1200, 675),
    "Twitter Header":      (1500, 500),
}

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".mts", ".mpg", ".mpeg"}

VIDEO_FILTER = "Videos (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.ts *.mts *.mpg *.mpeg);;All Files (*)"


BADGE_STYLES: Dict[str, Dict[str, Any]] = {
    "Classic Red": {
        "bg_color": "#E50914", "text_color": "#FFFFFF", "border_color": None,
        "border_width": 0, "corner_radius": 6, "font_size_ratio": 0.045,
        "padding_h_ratio": 0.020, "padding_v_ratio": 0.013, "margin_ratio": 0.025,
        "shadow": True, "shadow_opacity": 0.55, "shadow_blur": 8,
        "text": "LIVE",
    },
    "Twitch Purple": {
        "bg_color": "#9146FF", "text_color": "#FFFFFF", "border_color": None,
        "border_width": 0, "corner_radius": 6, "font_size_ratio": 0.045,
        "padding_h_ratio": 0.020, "padding_v_ratio": 0.013, "margin_ratio": 0.025,
        "shadow": True, "shadow_opacity": 0.55, "shadow_blur": 8,
        "text": "LIVE",
    },
    "YouTube Pill": {
        "bg_color": "#FF0000", "text_color": "#FFFFFF", "border_color": None,
        "border_width": 0, "corner_radius": 22, "font_size_ratio": 0.040,
        "padding_h_ratio": 0.028, "padding_v_ratio": 0.011, "margin_ratio": 0.030,
        "shadow": True, "shadow_opacity": 0.50, "shadow_blur": 6,
        "text": "LIVE",
    },
    "Kick Green": {
        "bg_color": "#53FC18", "text_color": "#000000", "border_color": None,
        "border_width": 0, "corner_radius": 6, "font_size_ratio": 0.045,
        "padding_h_ratio": 0.020, "padding_v_ratio": 0.013, "margin_ratio": 0.025,
        "shadow": True, "shadow_opacity": 0.50, "shadow_blur": 8,
        "text": "LIVE",
    },
    "Outline Only": {
        "bg_color": None, "text_color": "#FF0000", "border_color": "#FF0000",
        "border_width": 3, "corner_radius": 6, "font_size_ratio": 0.050,
        "padding_h_ratio": 0.022, "padding_v_ratio": 0.013, "margin_ratio": 0.025,
        "shadow": True, "shadow_opacity": 0.60, "shadow_blur": 6,
        "text": "LIVE",
    },
    "Dark Glass": {
        "bg_color": "#1A1A1A", "text_color": "#FFFFFF", "border_color": "#444444",
        "border_width": 1, "corner_radius": 6, "font_size_ratio": 0.042,
        "padding_h_ratio": 0.020, "padding_v_ratio": 0.013, "margin_ratio": 0.025,
        "shadow": True, "shadow_opacity": 0.50, "shadow_blur": 10,
        "text": "LIVE",
    },
    "Minimal White": {
        "bg_color": "#FFFFFF", "text_color": "#111111", "border_color": None,
        "border_width": 0, "corner_radius": 5, "font_size_ratio": 0.042,
        "padding_h_ratio": 0.020, "padding_v_ratio": 0.013, "margin_ratio": 0.025,
        "shadow": True, "shadow_opacity": 0.35, "shadow_blur": 10,
        "text": "LIVE",
    },
    "Neon Glow": {
        "bg_color": None, "text_color": "#00FF88", "border_color": "#00FF88",
        "border_width": 2, "corner_radius": 6, "font_size_ratio": 0.048,
        "padding_h_ratio": 0.022, "padding_v_ratio": 0.013, "margin_ratio": 0.025,
        "shadow": True, "shadow_opacity": 0.80, "shadow_blur": 16,
        "text": "LIVE",
    },
}

CORNER_POSITIONS = ["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right", "Custom"]

# ══════════════════════════════════════════════════════════════════════════════
# Stylesheet — dark professional theme
# ══════════════════════════════════════════════════════════════════════════════

STYLESHEET = """
QMainWindow { background:#141414; }
QWidget { color:#D4D4D4; font-family:"Segoe UI","SF Pro","Inter","Helvetica Neue",sans-serif; font-size:12px; }

/* ── Group boxes ─────────────────────────────────────────────────── */
QGroupBox {
    border:1px solid #333; border-radius:8px; margin-top:16px;
    padding:14px 12px 10px 12px; font-weight:600; color:#BBBBBB;
    background:#1e1e1e;
}
QGroupBox::title { subcontrol-origin:margin; left:14px; padding:0 6px; }

/* ── Buttons ─────────────────────────────────────────────────────── */
QPushButton {
    background:#2a2a2a; color:#D4D4D4; border:1px solid #3a3a3a;
    border-radius:6px; padding:7px 16px; font-weight:600; font-size:11px;
}
QPushButton:hover { background:#3a3a3a; border-color:#555; color:#EEEEEE; }
QPushButton:pressed { background:#222; }
QPushButton#btnPrimary {
    background:#D4D4D4; color:#111; border:1px solid #D4D4D4;
    font-weight:700;
}
QPushButton#btnPrimary:hover { background:#EEEEEE; }
QPushButton#btnAccent {
    background:#2563EB; color:#FFF; border:1px solid #2563EB;
}
QPushButton#btnAccent:hover { background:#3B82F6; }
QPushButton:disabled { background:#1e1e1e; color:#555; border-color:#2a2a2a; }

/* ── Combos / Spinners ───────────────────────────────────────────── */
QComboBox {
    background:#222; border:1px solid #3a3a3a; border-radius:6px;
    padding:6px 10px; min-height:20px; font-size:11px;
}
QComboBox:hover { border-color:#555; }
QComboBox::drop-down { border:none; width:24px; }
QComboBox QAbstractItemView { background:#222; selection-background-color:#2563EB; outline:none; }

QSpinBox, QDoubleSpinBox {
    background:#222; border:1px solid #3a3a3a; border-radius:6px;
    padding:5px 8px; font-size:11px;
}
QSpinBox:hover, QDoubleSpinBox:hover { border-color:#555; }

/* ── Scrollbars ──────────────────────────────────────────────────── */
QScrollArea { border:none; background:transparent; }
QScrollBar:vertical { background:transparent; width:8px; border-radius:4px; margin:2px; }
QScrollBar::handle:vertical { background:#3a3a3a; border-radius:4px; min-height:20px; }
QScrollBar::handle:vertical:hover { background:#555; }
QScrollBar::add-line, QScrollBar::sub-line { height:0; }
QScrollBar:horizontal { background:transparent; height:8px; border-radius:4px; margin:2px; }
QScrollBar::handle:horizontal { background:#3a3a3a; border-radius:4px; min-width:20px; }
QScrollBar::handle:horizontal:hover { background:#555; }

/* ── Status bar ──────────────────────────────────────────────────── */
QStatusBar { background:#1a1a1a; color:#666; font-size:11px; border-top:1px solid #2a2a2a; }
QStatusBar::item { border:none; }

/* ── Sliders ─────────────────────────────────────────────────────── */
QSlider::groove:horizontal { height:4px; background:#333; border-radius:2px; }
QSlider::handle:horizontal { background:#D4D4D4; width:14px; height:14px; margin:-5px 0; border-radius:7px; }
QSlider::handle:horizontal:hover { background:#FFF; }

/* ── Checkbox ────────────────────────────────────────────────────── */
QCheckBox::indicator { width:16px; height:16px; border-radius:4px; border:1px solid #444; background:#222; }
QCheckBox::indicator:checked { background:#2563EB; border-color:#2563EB; }

/* ── Labels ──────────────────────────────────────────────────────── */
QLabel#LblSection { font-size:10px; font-weight:700; color:#777; letter-spacing:1.2px; text-transform:uppercase; }
QLabel#Counter { font-size:13px; color:#999; font-weight:600; font-family:"Inter","SF Mono","Consolas",monospace; }
QLabel#Shortcut { font-size:10px; color:#555; font-family:"Inter","SF Mono",monospace; }
QLabel#LblValue { font-size:11px; color:#AAA; font-family:"Inter","SF Mono","Consolas",monospace; }

/* ── Separator ───────────────────────────────────────────────────── */
QFrame#Separator { background:#2a2a2a; max-height:1px; }

/* ── Tooltip ─────────────────────────────────────────────────────── */
QToolTip { background:#333; color:#DDD; border:1px solid #444; padding:5px 8px; border-radius:5px; font-size:11px; }

/* ── Menu ────────────────────────────────────────────────────────── */
QMenu { background:#222; border:1px solid #3a3a3a; border-radius:8px; padding:4px; }
QMenu::item { padding:7px 20px; border-radius:4px; font-size:11px; }
QMenu::item:selected { background:#2563EB; color:#FFF; }
QMenu::separator { height:1px; background:#333; margin:4px 8px; }
"""

# ══════════════════════════════════════════════════════════════════════════════
# Image helpers
# ══════════════════════════════════════════════════════════════════════════════

def load_image(path: str) -> Optional[QImage]:
    r = QImage(path)
    return None if r.isNull() else r


def fit_crop(img: QImage, target: Tuple[int, int]) -> QImage:
    tw, th = target
    if img.width() == tw and img.height() == th:
        return img
    ratio = max(tw / img.width(), th / img.height())
    nw, nh = int(img.width() * ratio), int(img.height() * ratio)
    s = img.scaled(nw, nh, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return s.copy((nw - tw) // 2, (nh - th) // 2, tw, th)


def _scaled_in(pm: QPixmap, w: int, h: int, mode: str = "fit") -> QPixmap:
    if pm.isNull():
        return pm
    ar = pm.width() / max(1, pm.height())
    if mode == "1:1":
        return pm
    if mode == "fill":
        scale = max(w / pm.width(), h / pm.height())
        return pm.scaled(int(pm.width() * scale), int(pm.height() * scale),
                         Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    # fit
    if w / max(1, h) > ar:
        dh, dw = h, int(h * ar)
    else:
        dw, dh = w, int(w / max(ar, 1e-9))
    return pm.scaled(dw, dh, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


# ══════════════════════════════════════════════════════════════════════════════
# Computer-Vision Frame Analyzer
# ══════════════════════════════════════════════════════════════════════════════

try:
    import cv2
    _CV2_OK = True
except ImportError:
    _CV2_OK = False


def _qimage_to_cv(img: QImage):
    """Convert a PySide6 QImage to an OpenCV BGR numpy array."""
    if img.isNull():
        return None
    img = img.convertToFormat(QImage.Format.Format_RGB888)
    w, h = img.width(), img.height()
    bits = img.bits()
    bits.setsize(h * w * 3)
    arr = np.frombuffer(bits, dtype=np.uint8).reshape((h, w, 3))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


class FrameAnalyzer:
    """Multi-metric computer-vision analysis for thumbnail quality scoring.

    Each public static method returns a float in [0, 1] (higher = better),
    except ``analyze()`` which returns the full score dict.

    Metrics & research basis
    ------------------------
    sharpness     – Laplacian variance (Pech-Pacheco et al. 2000)
    brightness    – Gaussian fitness around ideal luminance (140/255)
    contrast      – Std-dev of luminance channel
    colorfulness  – Hasler & Susstrunk opponent-channel metric (ICIP 2003)
    edge_density  – Canny edge pixel fraction (visual complexity)
    face_score    – Haar cascade face count + area ratio
    composition   – Rule-of-thirds gradient-energy overlap + edge penalty
    """

    # Scoring weights for the composite score
    WEIGHTS = {
        "sharpness":       0.15,
        "face_score":      0.12,
        "eye_quality":     0.10,
        "brightness":      0.07,
        "contrast":        0.05,
        "colorfulness":    0.07,
        "color_harmony":   0.07,
        "edge_density":    0.05,
        "composition":     0.05,
        "spectral_saliency": 0.08,
        "motion_blur_score": 0.06,
        "skin_tone_ratio": 0.05,
        "histogram_entropy": 0.04,
        "text_region_score": 0.04,
    }

    @staticmethod
    def sharpness(bgr):
        """Laplacian variance -- high means sharp, low means blurry."""
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        var = float(lap.var())
        return float(np.tanh(var / 800.0))

    @staticmethod
    def brightness(bgr):
        """Perceived luminance scored by proximity to the ideal range (100-180)."""
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        mu = float(gray.mean())
        return float(np.exp(-((mu - 140) ** 2) / (2 * 60 ** 2)))

    @staticmethod
    def contrast(bgr):
        """Standard deviation of luminance -- higher means more contrast."""
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        std = float(gray.std())
        return float(min(1.0, std / 80.0))

    @staticmethod
    def colorfulness(bgr):
        """Hasler & Susstrunk colourfulness metric (ICIP 2003)."""
        b_ch = bgr[:, :, 0].astype(np.float64)
        g_ch = bgr[:, :, 1].astype(np.float64)
        r_ch = bgr[:, :, 2].astype(np.float64)
        rg = np.abs(r_ch - g_ch)
        yb = np.abs(0.5 * (r_ch + g_ch) - b_ch)
        rb_std, rb_mu = np.std(rg), np.mean(rg)
        yb_std, yb_mu = np.std(yb), np.mean(yb)
        std_root = np.sqrt((rb_std ** 2) + (yb_std ** 2))
        mu_root = np.sqrt((rb_mu ** 2) + (yb_mu ** 2))
        cf = std_root + (0.3 * mu_root)
        return float(min(1.0, cf / 120.0))

    @staticmethod
    def edge_density(bgr):
        """Fraction of pixels that are strong Canny edges -- visual complexity."""
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        density = float(np.count_nonzero(edges)) / max(1, edges.size)
        return float(min(1.0, density / 0.20))

    @staticmethod
    def face_score(bgr):
        """Detect faces with Haar cascade.

        Returns (score_0to1, face_count, face_area_ratio).
        """
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if cascade.empty():
            return 0.0, 0, 0.0
        faces = cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4,
                                         minSize=(40, 40))
        n = len(faces)
        if n == 0:
            return 0.15, 0, 0.0
        area = sum(fw * fh for (_, _, fw, fh) in faces if fw > 0 and fh > 0)
        ratio = area / max(1, w * h)
        count_score = min(1.0, n / 2.0) * 0.6
        size_score = min(1.0, ratio / 0.25) * 0.4
        return (count_score + size_score), n, ratio

    @staticmethod
    def composition(bgr):
        """Rule-of-thirds gradient-energy overlap + edge penalty."""
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        mag = np.sqrt(gx ** 2 + gy ** 2)
        total = max(1.0, float(mag.sum()))
        zone_r = min(int(min(w, h) * 0.12), 80)
        rois = [
            (int(w / 3), int(h / 3)), (int(2 * w / 3), int(h / 3)),
            (int(w / 3), int(2 * h / 3)), (int(2 * w / 3), int(2 * h / 3)),
            (w // 2, h // 2),
        ]
        zone_energy = 0.0
        for cx, cy in rois:
            y0 = max(0, cy - zone_r)
            y1 = min(h, cy + zone_r)
            x0 = max(0, cx - zone_r)
            x1 = min(w, cx + zone_r)
            zone_energy += float(mag[y0:y1, x0:x1].sum())
        border = int(min(w, h) * 0.06)
        edge_energy = (float(mag[:border, :].sum()) +
                       float(mag[-border:, :].sum()) +
                       float(mag[:, :border].sum()) +
                       float(mag[:, -border:].sum()))
        roi_score = min(1.0, zone_energy / (total * 0.15))
        edge_penalty = min(0.3, edge_energy / (total * 0.3))
        return max(0.0, min(1.0, roi_score - edge_penalty))


    @staticmethod
    def spectral_saliency(bgr):
        """Spectral Residual Saliency (Hou & Zhang, CVPR 2007).
        Measures visual attention -- high saliency means the frame has
        a clear focal point, which is excellent for thumbnails."""
        try:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float64)
            h, w = gray.shape
            # FFT
            fft = np.fft.fft2(gray)
            log_mag = np.log(np.abs(fft) + 1e-12)
            phase = np.angle(fft)
            # Spectral residual
            mean_log = np.mean(log_mag)
            sr = np.exp(log_mag - mean_log) * np.exp(1j * phase)
            saliency = np.abs(np.fft.ifft2(sr)) ** 2
            # Normalize
            saliency = (saliency - saliency.min()) / max(1e-12, saliency.max() - saliency.min())
            # Score = fraction of image with high saliency (top 10%)
            threshold = np.percentile(saliency, 90)
            hot = np.sum(saliency > threshold) / max(1, saliency.size)
            # Penalize if saliency is too uniform (no focal point)
            focused = 1.0 - min(1.0, np.std(saliency) / 0.15)
            return float(np.clip(hot * (0.5 + 0.5 * focused), 0, 1))
        except Exception:
            return 0.5

    @staticmethod
    def motion_blur_score(bgr):
        """FFT-based motion blur detection.
        Blur causes energy loss in high frequencies.
        Ratio of high-freq energy to total energy indicates sharpness."""
        try:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float64)
            h, w = gray.shape
            # Apply Gaussian window to reduce edge artifacts
            cy, cx = h // 2, w // 2
            y, x = np.ogrid[:h, :w]
            sigma = min(h, w) / 4.0
            gauss = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma ** 2))
            windowed = gray * gauss
            fft = np.fft.fft2(windowed)
            fshift = np.fft.fftshift(fft)
            mag = np.abs(fshift)
            total_energy = np.sum(mag ** 2) + 1e-12
            # High-frequency band (outer 30-50% of spectrum)
            radius = int(min(h, w) * 0.15)
            ym, xm = np.ogrid[:h, :w]
            mask_inner = ((ym - cy) ** 2 + (xm - cx) ** 2) <= radius ** 2
            low_energy = np.sum(mag[mask_inner] ** 2)
            high_energy = total_energy - low_energy
            ratio = high_energy / total_energy
            # Typical range: 0.4-0.95 for natural images
            return float(np.clip((ratio - 0.35) / 0.60, 0, 1))
        except Exception:
            return 0.5

    @staticmethod
    def skin_tone_ratio(bgr):
        """Skin tone detection in HSV color space.
        Thumbnails with visible people (skin tones) typically perform better.
        Uses broad HSV ranges covering diverse skin tones."""
        try:
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
            # Broad skin tone ranges in HSV
            h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
            # Range 1: lighter skin tones (H: 0-25, S: 15-170, V: 60-255)
            mask1 = (h <= 25) & (s >= 15) & (s <= 170) & (v >= 60)
            # Range 2: darker skin tones (H: 0-30, S: 20-180, V: 30-170)
            mask2 = (h <= 30) & (s >= 20) & (s <= 180) & (v >= 30) & (v <= 170)
            # Range 3: very light / Asian tones (H: 0-50 with low S)
            mask3 = (h <= 50) & (s >= 5) & (s <= 60) & (v >= 150)
            combined = mask1 | mask2 | mask3
            ratio = np.count_nonzero(combined) / max(1, combined.size)
            # Score: sweet spot around 10-35% skin (faces in frame)
            # Too little = no people, too much = probably not a good thumbnail
            if ratio < 0.02:
                return 0.15  # Small bonus for non-people shots
            elif ratio < 0.08:
                return 0.3 + (ratio / 0.08) * 0.5
            elif ratio <= 0.40:
                return 0.8 + (1.0 - abs(ratio - 0.20) / 0.20) * 0.2
            else:
                return max(0.1, 1.0 - (ratio - 0.40) / 0.40)
        except Exception:
            return 0.3

    @staticmethod
    def histogram_entropy(bgr):
        """Shannon entropy of the intensity histogram.
        Higher entropy = more information content = more visually interesting."""
        try:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
            total = hist.sum() + 1e-12
            probs = hist / total
            # Remove zero-probability bins
            probs = probs[probs > 0]
            entropy = -np.sum(probs * np.log2(probs))
            # Typical range: 3.0-8.0 bits; max = log2(256) = 8.0
            return float(np.clip(entropy / 7.5, 0, 1))
        except Exception:
            return 0.5

    @staticmethod
    def eye_quality(bgr):
        """Eye detection quality using OpenCV eye cascade.
        Frames with visible eyes are more engaging for thumbnails.
        Returns (score, eyes_detected, face_centered)."""
        try:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape[:2]
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            eye_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_eye.xml")
            if face_cascade.empty() or eye_cascade.empty():
                return 0.5, 0, False
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.15,
                                                  minNeighbors=3, minSize=(60, 60))
            if len(faces) == 0:
                return 0.1, 0, False
            total_eyes = 0
            best_face_score = 0.0
            for (fx, fy, fw, fh) in faces:
                roi_gray = gray[fy:fy + fh, fx:fx + fw]
                eyes = eye_cascade.detectMultiScale(roi_gray, scaleFactor=1.1,
                                                    minNeighbors=3, minSize=(15, 15))
                eye_count = len(eyes)
                total_eyes += eye_count
                # Score: 2 eyes visible + centered face = best
                eye_score = min(1.0, eye_count / 2.0) * 0.5
                # Face centrality: center of face should be near image center
                face_cx = fx + fw / 2
                face_cy = fy + fh / 2
                dist_to_center = math.sqrt((face_cx - w / 2) ** 2 +
                                           (face_cy - h / 2) ** 2)
                max_dist = math.sqrt((w / 2) ** 2 + (h / 2) ** 2)
                centrality = 1.0 - (dist_to_center / max_dist)
                centrality = max(0, centrality ** 0.5)  # Non-linear, more forgiving
                centrality_score = centrality * 0.3
                # Face size: not too small, not too large
                face_area = (fw * fh) / (w * h)
                size_score = min(1.0, face_area / 0.15) * 0.2
                face_total = eye_score + centrality_score + size_score
                best_face_score = max(best_face_score, face_total)
            return (min(1.0, best_face_score), total_eyes,
                    best_face_score > 0.5)
        except Exception:
            return 0.3, 0, False

    @staticmethod
    def color_harmony(bgr):
        """HSL color harmony analysis.
        Checks for analogous, complementary, and triadic color relationships
        which are aesthetically pleasing in thumbnails."""
        try:
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float64)
            h = hsv[:, :, 0] * 2  # Scale to 0-360
            s = hsv[:, :, 1] / 255.0
            v = hsv[:, :, 2] / 255.0
            # Only consider pixels with sufficient saturation and brightness
            mask = (s > 0.15) & (v > 0.15) & (v < 0.90)
            if np.count_nonzero(mask) < 100:
                return 0.4
            hues = h[mask]
            # Compute hue histogram (36 bins of 10 degrees each)
            hist, _ = np.histogram(hues, bins=36, range=(0, 360))
            hist = hist.astype(np.float64)
            total = hist.sum() + 1e-12
            probs = hist / total
            # Dominant hue
            dominant_bin = np.argmax(probs)
            dominant_angle = dominant_bin * 10 + 5
            # Harmony score: how much of the color is in harmonious relationships
            # Complementary (180 +/- 20)
            comp_center = (dominant_angle + 180) % 360
            # Analogous (+/- 30)
            ana_low = (dominant_angle - 30) % 360
            ana_high = (dominant_angle + 30) % 360
            # Triadic (+/- 120)
            tri1 = (dominant_angle + 120) % 360
            tri2 = (dominant_angle + 240) % 360
            harmony_weight = 0.0
            for i in range(36):
                angle = i * 10 + 5
                # Dominant hue contribution
                dist_dominant = min(abs(angle - dominant_angle),
                                    360 - abs(angle - dominant_angle))
                if dist_dominant <= 30:
                    harmony_weight += probs[i] * (1.0 - dist_dominant / 30)
                # Complementary
                dist_comp = min(abs(angle - comp_center),
                                360 - abs(angle - comp_center))
                if dist_comp <= 25:
                    harmony_weight += probs[i] * 0.5 * (1.0 - dist_comp / 25)
                # Triadic
                for tri_c in [tri1, tri2]:
                    dist_tri = min(abs(angle - tri_c), 360 - abs(angle - tri_c))
                    if dist_tri <= 25:
                        harmony_weight += probs[i] * 0.3 * (1.0 - dist_tri / 25)
            # Diversity bonus (not too monochrome)
            n_active = np.sum(probs > 0.02)
            diversity = min(1.0, n_active / 8.0)
            # Saturation richness
            avg_sat = np.mean(s[mask])
            sat_score = min(1.0, avg_sat / 0.6)
            raw = harmony_weight * 0.5 + diversity * 0.25 + sat_score * 0.25
            return float(np.clip(raw, 0, 1))
        except Exception:
            return 0.4

    @staticmethod
    def text_region_score(bgr):
        """MSER-based text region detection.
        Thumbnails with readable text regions (signs, titles, graphics)
        can be useful. Scores presence and clarity of text-like regions."""
        try:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape[:2]
            mser = cv2.MSER_create()
            mser.setMinArea(int(w * h * 0.0001))
            mser.setMaxArea(int(w * h * 0.15))
            regions, _ = mser.detectRegions(gray)
            if not regions or len(regions) == 0:
                return 0.1
            # Filter regions by aspect ratio and size (text-like)
            text_like = 0
            for region in regions[:200]:  # Limit for performance
                if len(region) < 4:
                    continue
                x_coords = region[:, 0]
                y_coords = region[:, 1]
                rw = float(x_coords.max() - x_coords.min())
                rh = float(y_coords.max() - y_coords.min())
                if rw < 5 or rh < 5:
                    continue
                aspect = rw / max(1, rh)
                # Text-like: aspect ratio between 0.2 and 8.0
                if 0.15 <= aspect <= 10.0:
                    area = rw * rh
                    fill = len(region) / max(1, area)
                    if 0.1 <= fill <= 0.9:
                        text_like += 1
            score = min(1.0, text_like / 15.0)
            return float(score)
        except Exception:
            return 0.2

    @staticmethod
    def temporal_uniqueness(frame_bgr, prev_hist=None, similarity_threshold=0.92):
        """Measure how unique this frame is compared to the previous frame.
        Used during batch processing to avoid near-duplicate thumbnails.
        Returns (score 0-1, histogram for chaining)."""
        try:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [64], [0, 256]).flatten()
            cv2.normalize(hist, hist)
            if prev_hist is None:
                return 0.8, hist
            # Bhattacharyya distance (0 = identical, 1 = completely different)
            dist = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
            # Convert distance to uniqueness score
            if dist < (1.0 - similarity_threshold):
                return 0.05, hist  # Near-duplicate
            elif dist > 0.5:
                return 1.0, hist  # Very unique
            else:
                return float(np.clip(dist / 0.5, 0.05, 1.0)), hist
        except Exception:
            return 0.5, None

    @staticmethod
    def analyze(img: QImage, prev_hist=None) -> dict:
        """Run all 13 metrics on a QImage and return a score dict.
        
        Parameters
        ----------
        img : QImage
        prev_hist : numpy array or None
            Histogram from the previous frame for temporal uniqueness scoring.
            Pass None for the first frame or standalone analysis.
        """
        if not _CV2_OK:
            return {"sharpness": 0.5, "brightness": 0.5, "contrast": 0.5,
                    "colorfulness": 0.5, "edge_density": 0.5,
                    "face_score": 0.5, "face_count": 0, "face_area_ratio": 0.0,
                    "composition": 0.5, "overall": 0.5,
                    "spectral_saliency": 0.5, "motion_blur_score": 0.5,
                    "skin_tone_ratio": 0.5, "histogram_entropy": 0.5,
                    "eye_quality": 0.5, "eyes_detected": 0,
                    "color_harmony": 0.5, "text_region_score": 0.5,
                    "temporal_uniqueness": 0.8,
                    "label": "cv2 not installed"}
        bgr = _qimage_to_cv(img)
        if bgr is None:
            return {"sharpness": 0, "brightness": 0, "contrast": 0,
                    "colorfulness": 0, "edge_density": 0,
                    "face_score": 0, "face_count": 0, "face_area_ratio": 0.0,
                    "composition": 0, "overall": 0,
                    "spectral_saliency": 0, "motion_blur_score": 0,
                    "skin_tone_ratio": 0, "histogram_entropy": 0,
                    "eye_quality": 0, "eyes_detected": 0,
                    "color_harmony": 0, "text_region_score": 0,
                    "temporal_uniqueness": 0, "label": "null image"}

        # Core metrics
        sh = FrameAnalyzer.sharpness(bgr)
        br = FrameAnalyzer.brightness(bgr)
        co = FrameAnalyzer.contrast(bgr)
        cf = FrameAnalyzer.colorfulness(bgr)
        ed = FrameAnalyzer.edge_density(bgr)
        fs, fc, fa = FrameAnalyzer.face_score(bgr)
        cp = FrameAnalyzer.composition(bgr)

        # Expert metrics
        sal = FrameAnalyzer.spectral_saliency(bgr)
        mb = FrameAnalyzer.motion_blur_score(bgr)
        sk = FrameAnalyzer.skin_tone_ratio(bgr)
        ent = FrameAnalyzer.histogram_entropy(bgr)
        eq, eyes_detected, face_centered = FrameAnalyzer.eye_quality(bgr)
        ch = FrameAnalyzer.color_harmony(bgr)
        tr = FrameAnalyzer.text_region_score(bgr)
        tu, _ = FrameAnalyzer.temporal_uniqueness(bgr, prev_hist)

        W = FrameAnalyzer.WEIGHTS
        overall = (W["sharpness"] * sh + W["face_score"] * fs +
                   W["eye_quality"] * eq + W["brightness"] * br +
                   W["colorfulness"] * cf + W["contrast"] * co +
                   W["color_harmony"] * ch + W["edge_density"] * ed +
                   W["composition"] * cp + W["spectral_saliency"] * sal +
                   W["motion_blur_score"] * mb + W["skin_tone_ratio"] * sk +
                   W["histogram_entropy"] * ent + W["text_region_score"] * tr)
        # Note: temporal_uniqueness is NOT included in the overall score
        # (it is used for filtering, not scoring)

        tags = []
        if sh > 0.7:
            tags.append("sharp")
        elif sh < 0.3:
            tags.append("blurry")
        if fc > 0:
            tags.append(str(fc) + (" faces" if fc > 1 else " face"))
        if eyes_detected > 0:
            tags.append(f"{eyes_detected} eye{'s' if eyes_detected > 1 else ''}")
        if cf > 0.6:
            tags.append("vivid")
        if br > 0.8:
            tags.append("bright")
        elif br < 0.3:
            tags.append("dark")
        if sal > 0.7:
            tags.append("focused")
        if mb < 0.3:
            tags.append("motion-blur")
        if sk > 0.6:
            tags.append("people")
        if ch > 0.7:
            tags.append("harmonious")
        if tr > 0.5:
            tags.append("text-regions")
        if tu < 0.1:
            tags.append("duplicate")
        label = ", ".join(tags) if tags else "neutral"
        return {
            "sharpness": round(sh, 3), "brightness": round(br, 3),
            "contrast": round(co, 3), "colorfulness": round(cf, 3),
            "edge_density": round(ed, 3), "face_score": round(fs, 3),
            "face_count": fc, "face_area_ratio": round(fa, 3),
            "composition": round(cp, 3),
            "spectral_saliency": round(sal, 3),
            "motion_blur_score": round(mb, 3),
            "skin_tone_ratio": round(sk, 3),
            "histogram_entropy": round(ent, 3),
            "eye_quality": round(eq, 3), "eyes_detected": eyes_detected,
            "color_harmony": round(ch, 3),
            "text_region_score": round(tr, 3),
            "temporal_uniqueness": round(tu, 3),
            "overall": round(overall, 3), "label": label,
        }


class FrameAnalysisWorker(QThread):
    """Analyze a batch of QImages in a background thread."""

    frame_scored = Signal(int, object)
    all_scored = Signal(list)

    def __init__(self, frames: list, parent=None):
        super().__init__(parent)
        self._frames = frames
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        scores = []
        prev_hist = None
        for i, img in enumerate(self._frames):
            if self._abort:
                break
            result = FrameAnalyzer.analyze(img, prev_hist=prev_hist)
            scores.append(result)
            # Chain histograms for temporal uniqueness
            if _CV2_OK and not img.isNull():
                cv_img = _qimage_to_cv(img)
                if cv_img is not None:
                    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                    h = cv2.calcHist([gray], [0], None, [64], [0, 256]).flatten()
                    cv2.normalize(h, h)
                    prev_hist = h
            self.frame_scored.emit(i, result)
        self.all_scored.emit(scores)


# ══════════════════════════════════════════════════════════════════════════════
# Video Frame Extractor  (QThread — ffmpeg powered)
# ══════════════════════════════════════════════════════════════════════════════

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class VideoFrameExtractor(QThread):
    """Background thread that extracts frames from a video file using ffmpeg.

    Signals
    -------
    progress(int, int)            – current_frame, total_frames
    frame_extracted(object, str)  – QImage, timestamp label
    all_done(list, list)          – [QImage, ...], [label, ...]
    error_occurred(str)           – human-readable error message
    """

    progress = Signal(int, int)
    frame_extracted = Signal(object, str)
    all_done = Signal(list, list)
    error_occurred = Signal(str)

    def __init__(self, video_path: str, mode: str = "even", count: int = 10,
                 max_width: int = 1920, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.mode = mode          # "even" | "scenes" | "smart"
        self.count = max(1, min(count, 2000))
        self.max_width = max_width
        self._abort = False

    def abort(self):
        self._abort = True

    # ── ffmpeg helpers ──────────────────────────────────────────────

    @staticmethod
    def find_ffmpeg() -> str:
        """Return the path/name of an available ffmpeg binary, or empty string."""
        candidates = ["ffmpeg"]
        if sys.platform == "win32":
            candidates += [
                os.path.join(os.environ.get("PROGRAMFILES", ""),
                             "FFmpeg", "bin", "ffmpeg.exe"),
                os.path.join(os.environ.get("PROGRAMFILES", ""),
                             "ffmpeg", "bin", "ffmpeg.exe"),
            ]
        for name in candidates:
            try:
                subprocess.run([name, "-version"], capture_output=True,
                               timeout=5, creationflags=_NO_WINDOW)
                return name
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue
        return ""

    @staticmethod
    def get_video_info(video_path: str) -> dict:
        """Probe a video file and return metadata."""
        ffmpeg = VideoFrameExtractor.find_ffmpeg()
        if not ffmpeg:
            return {"error": "ffmpeg not found. Install from https://ffmpeg.org"}
        ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
        try:
            r = subprocess.run(
                [ffprobe, "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", video_path],
                capture_output=True, text=True, timeout=30,
                creationflags=_NO_WINDOW,
            )
            data = json.loads(r.stdout)
            vstream = next(
                (s for s in data.get("streams", [])
                 if s.get("codec_type") == "video"), None)
            if not vstream:
                return {"error": "No video stream found"}
            fmt = data.get("format", {})
            dur = float(fmt.get("duration", vstream.get("duration", 0)))
            w, h = int(vstream.get("width", 0)), int(vstream.get("height", 0))
            fr = vstream.get("r_frame_rate", "0/1")
            try:
                fn, fd = map(int, fr.split("/"))
                fps = round(fn / max(fd, 1), 2)
            except (ValueError, ZeroDivisionError):
                fps = 0.0
            sz = int(fmt.get("size", 0))
            return {
                "duration": dur, "width": w, "height": h, "fps": fps,
                "codec": vstream.get("codec_name", "?"),
                "size_mb": round(sz / 1048576, 1),
                "bitrate_kbps": int(fmt.get("bit_rate", 0)) // 1000,
            }
        except Exception as exc:
            return {"error": str(exc)}

    # ── main extraction logic ───────────────────────────────────────

    def run(self):
        ffmpeg = self.find_ffmpeg()
        if not ffmpeg:
            self.error_occurred.emit(
                "ffmpeg not found.\n\n"
                "Please install ffmpeg from https://ffmpeg.org/download.html\n"
                "and ensure it is in your system PATH.")
            return

        info = self.get_video_info(self.video_path)
        if "error" in info:
            self.error_occurred.emit(info["error"])
            return
        dur = info["duration"]
        if dur <= 0:
            self.error_occurred.emit("Could not determine video duration.")
            return

        # Build timestamp list
        if self.mode == "scenes":
            timestamps = self._scene_timestamps(ffmpeg, dur)
        else:
            timestamps = [dur * (i + 0.5) / self.count
                          for i in range(self.count)]

        if not timestamps:
            self.error_occurred.emit("No frames could be extracted.")
            return

        frames: list = []
        labels: list = []

        with tempfile.TemporaryDirectory() as tmp:
            for idx, ts in enumerate(timestamps):
                if self._abort:
                    break
                self.progress.emit(idx + 1, len(timestamps))
                out = os.path.join(tmp, f"f{idx:04d}.png")
                try:
                    cmd = [ffmpeg, "-y", "-ss", f"{ts:.3f}",
                           "-i", self.video_path, "-vframes", "1", "-q:v", "2"]
                    if self.max_width > 0 and info["width"] > self.max_width:
                        cmd += ["-vf", f"scale={self.max_width}:-2"]
                    cmd.append(out)
                    subprocess.run(cmd, capture_output=True, timeout=30,
                                   creationflags=_NO_WINDOW)
                    img = QImage(out)
                    if not img.isNull():
                        frames.append(img)
                        m, s = divmod(ts, 60)
                        lbl = f"{int(m):02d}:{s:05.2f}"
                        labels.append(lbl)
                        self.frame_extracted.emit(img, lbl)
                except Exception:
                    continue

        self.all_done.emit(frames, labels)

    def _scene_timestamps(self, ffmpeg, duration):
        """Detect scene changes and return up to *self.count* timestamps."""
        try:
            import re as _re
            r = subprocess.run(
                [ffmpeg, "-i", self.video_path,
                 "-vf", "select='gt(scene,0.3)',showinfo",
                 "-vsync", "vfr", "-f", "null", "-"],
                capture_output=True, text=True, timeout=120,
                creationflags=_NO_WINDOW,
            )
            pts_times = _re.findall(r"pts_time:(\d+\.?\d*)", r.stderr)
            timestamps = sorted(float(t) for t in pts_times
                                if 0 < float(t) < duration)
            if not timestamps:
                return [duration * (i + 0.5) / self.count
                        for i in range(self.count)]
            if len(timestamps) > self.count:
                step = len(timestamps) / self.count
                timestamps = [timestamps[int(i * step)]
                              for i in range(self.count)]
            return timestamps
        except Exception:
            return [duration * (i + 0.5) / self.count
                    for i in range(self.count)]

# ══════════════════════════════════════════════════════════════════════════════
# Undo / Redo stack
# ══════════════════════════════════════════════════════════════════════════════

class UndoStack:
    """Simple undo/redo for badge state snapshots."""

    def __init__(self, limit: int = 40) -> None:
        self._undo: List[dict] = []
        self._redo: List[dict] = []
        self._limit = limit

    def push(self, state_dict: dict) -> None:
        self._undo.append(state_dict)
        if len(self._undo) > self._limit:
            self._undo.pop(0)
        self._redo.clear()

    def can_undo(self) -> bool:
        return len(self._undo) > 1

    def can_redo(self) -> bool:
        return len(self._redo) > 0

    def undo(self) -> Optional[dict]:
        if not self.can_undo():
            return None
        current = self._undo.pop()
        self._redo.append(current)
        return self._undo[-1] if self._undo else None

    def redo(self) -> Optional[dict]:
        if not self._redo:
            return None
        state = self._redo.pop()
        self._undo.append(state)
        return state

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

# ══════════════════════════════════════════════════════════════════════════════
# Badge state + renderer
# ══════════════════════════════════════════════════════════════════════════════

class BadgeState:
    """All badge configuration — serialisable to dict for undo/redo."""

    def __init__(self) -> None:
        self.style_name: str = "Classic Red"
        self.text: str = "LIVE"
        self.position: str = "Top-Right"
        self.custom_x: float = 0.0   # 0‥1 normalised
        self.custom_y: float = 0.0
        self.font_size_ratio: float = 0.045
        self.padding_h_ratio: float = 0.020
        self.padding_v_ratio: float = 0.013
        self.margin_ratio: float = 0.025
        self.corner_radius: int = 6
        self.bg_color: Optional[QColor] = QColor("#E50914")
        self.text_color: QColor = QColor("#FFFFFF")
        self.border_color: Optional[QColor] = None
        self.border_width: int = 0
        self.shadow_enabled: bool = True
        self.shadow_opacity: float = 0.55
        self.shadow_blur: int = 8
        self.opacity: float = 1.0

    def to_dict(self) -> dict:
        def _c(c):
            return c.name() if c else None
        return {
            "style_name": self.style_name, "text": self.text,
            "position": self.position,
            "custom_x": self.custom_x, "custom_y": self.custom_y,
            "font_size_ratio": self.font_size_ratio,
            "padding_h_ratio": self.padding_h_ratio,
            "padding_v_ratio": self.padding_v_ratio,
            "margin_ratio": self.margin_ratio,
            "corner_radius": self.corner_radius,
            "bg_color": _c(self.bg_color),
            "text_color": _c(self.text_color),
            "border_color": _c(self.border_color),
            "border_width": self.border_width,
            "shadow_enabled": self.shadow_enabled,
            "shadow_opacity": self.shadow_opacity,
            "shadow_blur": self.shadow_blur,
            "opacity": self.opacity,
        }

    def load_dict(self, d: dict) -> None:
        for k, v in d.items():
            if k in ("bg_color", "text_color", "border_color"):
                v = QColor(v) if v else None
            setattr(self, k, v)

    def apply_style(self, name: str) -> None:
        if name not in BADGE_STYLES:
            return
        s = BADGE_STYLES[name]
        self.style_name = name
        self.text = s["text"]
        self.font_size_ratio = s["font_size_ratio"]
        self.padding_h_ratio = s["padding_h_ratio"]
        self.padding_v_ratio = s["padding_v_ratio"]
        self.margin_ratio = s["margin_ratio"]
        self.corner_radius = s["corner_radius"]
        self.bg_color = QColor(s["bg_color"]) if s["bg_color"] else None
        self.text_color = QColor(s["text_color"])
        self.border_color = QColor(s["border_color"]) if s["border_color"] else None
        self.border_width = s["border_width"]
        self.shadow_enabled = s["shadow"]
        self.shadow_opacity = s["shadow_opacity"]
        self.shadow_blur = s["shadow_blur"]


def render_badge(img: QImage, state: BadgeState) -> QImage:
    """Render the LIVE badge onto a copy of *img*. Returns the composite."""
    canvas = QImage(img)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    w, h = canvas.width(), canvas.height()
    if w < 10 or h < 10:
        p.end()
        return canvas

    base = max(w, h)
    margin = int(base * state.margin_ratio)

    font_size = max(8, int(base * state.font_size_ratio))
    font = QFont("Arial Black", font_size)
    font.setBold(True)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
    p.setFont(font)
    fm = QFontMetrics(font)

    text = state.text.upper()
    tw = fm.horizontalAdvance(text)
    th = fm.ascent() + fm.descent()
    pad_h = int(base * state.padding_h_ratio)
    pad_v = int(base * state.padding_v_ratio)
    bw = tw + 2 * pad_h
    bh = th + 2 * pad_v
    radius = max(1, state.corner_radius)

    # Compute top-left of badge
    if state.position == "Top-Left":
        bx, by = margin, margin
    elif state.position == "Top-Right":
        bx, by = w - bw - margin, margin
    elif state.position == "Bottom-Left":
        bx, by = margin, h - bh - margin
    elif state.position == "Bottom-Right":
        bx, by = w - bw - margin, h - bh - margin
    else:  # Custom
        bx = int(state.custom_x * (w - bw))
        by = int(state.custom_y * (h - bh))
    bx = max(0, min(bx, w - bw))
    by = max(0, min(by, h - bh))
    rect = QRect(bx, by, bw, bh)

    # Global opacity
    p.setOpacity(state.opacity)

    # Shadow (layered soft shadow)
    if state.shadow_enabled and state.shadow_blur > 0:
        blur = state.shadow_blur
        for i in range(blur, 0, -1):
            alpha = int(255 * state.shadow_opacity * (1 - i / blur) * 0.5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, max(0, min(255, alpha))))
            p.drawRoundedRect(rect.adjusted(-i + 2, -i + 2, i + 2, i + 2), radius + i, radius + i)

    # Background
    if state.bg_color is not None:
        p.setBrush(QColor(state.bg_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, radius, radius)

    # Border
    if state.border_color is not None and state.border_width > 0:
        pen = QPen(state.border_color, state.border_width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, radius, radius)

    # Text
    p.setPen(state.text_color)
    p.drawText(QPointF(bx + (bw - tw) / 2.0, by + pad_v + fm.ascent()), text)
    p.end()
    return canvas


# ══════════════════════════════════════════════════════════════════════════════
# Text Overlay Presets
# ══════════════════════════════════════════════════════════════════════════════

TEXT_PRESETS: Dict[str, Dict[str, Any]] = {
    "YouTube Title": {
        "text": "YOUR TITLE HERE",
        "font_family": "Arial Black",
        "font_size_ratio": 0.065,
        "bold": True, "italic": False,
        "color": "#FFFFFF",
        "outline_color": "#000000", "outline_width": 4,
        "shadow_enabled": True, "shadow_color": "#000000",
        "shadow_opacity": 0.7, "shadow_blur": 10, "shadow_offset_x": 2, "shadow_offset_y": 2,
        "position": "Top-Center", "custom_x": 0.5, "custom_y": 0.05,
        "opacity": 1.0,
    },
    "Reaction Text": {
        "text": "NO WAY!",
        "font_family": "Impact",
        "font_size_ratio": 0.080,
        "bold": True, "italic": False,
        "color": "#FFD700",
        "outline_color": "#000000", "outline_width": 5,
        "shadow_enabled": True, "shadow_color": "#000000",
        "shadow_opacity": 0.8, "shadow_blur": 8, "shadow_offset_x": 3, "shadow_offset_y": 3,
        "position": "Bottom-Center", "custom_x": 0.5, "custom_y": 0.82,
        "opacity": 1.0,
    },
    "Subtitle": {
        "text": "Subtitle text goes here",
        "font_family": "Arial",
        "font_size_ratio": 0.035,
        "bold": False, "italic": False,
        "color": "#FFFFFF",
        "outline_color": "#000000", "outline_width": 3,
        "shadow_enabled": True, "shadow_color": "#000000",
        "shadow_opacity": 0.6, "shadow_blur": 6, "shadow_offset_x": 1, "shadow_offset_y": 1,
        "position": "Bottom-Center", "custom_x": 0.5, "custom_y": 0.88,
        "opacity": 0.95,
    },
    "Watermark": {
        "text": "My Channel",
        "font_family": "Arial",
        "font_size_ratio": 0.025,
        "bold": False, "italic": False,
        "color": "#FFFFFF",
        "outline_color": None, "outline_width": 0,
        "shadow_enabled": False, "shadow_color": "#000000",
        "shadow_opacity": 0.3, "shadow_blur": 4, "shadow_offset_x": 0, "shadow_offset_y": 0,
        "position": "Bottom-Right", "custom_x": 0.95, "custom_y": 0.95,
        "opacity": 0.5,
    },
    "Lower Third": {
        "text": "Guest Name  |  Topic",
        "font_family": "Segoe UI",
        "font_size_ratio": 0.032,
        "bold": True, "italic": False,
        "color": "#FFFFFF",
        "outline_color": None, "outline_width": 0,
        "shadow_enabled": True, "shadow_color": "#000000",
        "shadow_opacity": 0.5, "shadow_blur": 12, "shadow_offset_x": 0, "shadow_offset_y": 4,
        "position": "Bottom-Left", "custom_x": 0.03, "custom_y": 0.85,
        "opacity": 0.9,
    },
    "Top Banner": {
        "text": "EPISODE 1",
        "font_family": "Arial Black",
        "font_size_ratio": 0.028,
        "bold": True, "italic": False,
        "color": "#FFFFFF",
        "outline_color": None, "outline_width": 0,
        "shadow_enabled": True, "shadow_color": "#000000",
        "shadow_opacity": 0.6, "shadow_blur": 8, "shadow_offset_x": 0, "shadow_offset_y": 2,
        "position": "Top-Left", "custom_x": 0.03, "custom_y": 0.03,
        "opacity": 0.9,
    },
}

TEXT_POSITIONS = [
    "Top-Left", "Top-Center", "Top-Right",
    "Center-Left", "Center", "Center-Right",
    "Bottom-Left", "Bottom-Center", "Bottom-Right",
    "Custom",
]


# ══════════════════════════════════════════════════════════════════════════════
# Text Overlay State
# ══════════════════════════════════════════════════════════════════════════════

class TextOverlayState:
    """State for a single text overlay layer. Serializable for undo/redo."""

    def __init__(self) -> None:
        self.text: str = "YOUR TEXT"
        self.font_family: str = "Arial Black"
        self.font_size_ratio: float = 0.065
        self.bold: bool = True
        self.italic: bool = False
        self.color: str = "#FFFFFF"
        self.outline_color: Optional[str] = "#000000"
        self.outline_width: int = 4
        self.shadow_enabled: bool = True
        self.shadow_color: str = "#000000"
        self.shadow_opacity: float = 0.7
        self.shadow_blur: int = 10
        self.shadow_offset_x: int = 2
        self.shadow_offset_y: int = 2
        self.position: str = "Top-Center"
        self.custom_x: float = 0.5
        self.custom_y: float = 0.05
        self.opacity: float = 1.0
        self.visible: bool = True

    def to_dict(self) -> dict:
        return {
            "text": self.text, "font_family": self.font_family,
            "font_size_ratio": self.font_size_ratio,
            "bold": self.bold, "italic": self.italic,
            "color": self.color, "outline_color": self.outline_color,
            "outline_width": self.outline_width,
            "shadow_enabled": self.shadow_enabled,
            "shadow_color": self.shadow_color,
            "shadow_opacity": self.shadow_opacity,
            "shadow_blur": self.shadow_blur,
            "shadow_offset_x": self.shadow_offset_x,
            "shadow_offset_y": self.shadow_offset_y,
            "position": self.position,
            "custom_x": self.custom_x, "custom_y": self.custom_y,
            "opacity": self.opacity, "visible": self.visible,
        }

    def load_dict(self, d: dict) -> None:
        for k, v in d.items():
            if k in self.__dict__:
                setattr(self, k, v)

    def apply_preset(self, name: str) -> None:
        if name not in TEXT_PRESETS:
            return
        for k, v in TEXT_PRESETS[name].items():
            if k in self.__dict__:
                setattr(self, k, v)


def render_text_overlays(img: QImage, overlays: list) -> QImage:
    """Render all text overlays onto a copy of the image."""
    canvas = QImage(img)
    if not overlays:
        return canvas
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    w, h = canvas.width(), canvas.height()
    base = max(w, h)

    for state in overlays:
        if not state.visible or not state.text.strip():
            continue

        p.setOpacity(state.opacity)

        font_size = max(8, int(base * state.font_size_ratio))
        font = QFont(state.font_family, font_size)
        font.setBold(state.bold)
        font.setItalic(state.italic)
        if state.bold:
            font.setWeight(QFont.Weight.Black)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)
        p.setFont(font)
        fm = QFontMetrics(font)

        text = state.text
        lines = text.split("\\n")
        line_heights = [fm.ascent() + fm.descent() for _ in lines]
        total_text_h = sum(line_heights) + 4 * (len(lines) - 1)
        max_tw = max(fm.horizontalAdvance(line) for line in lines)

        margin = int(base * 0.02)
        text_w = max_tw
        text_h = total_text_h

        pos = state.position
        if pos == "Top-Left":
            tx, ty = margin, margin
            align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        elif pos == "Top-Center":
            tx, ty = (w - text_w) / 2, margin
            align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        elif pos == "Top-Right":
            tx, ty = w - text_w - margin, margin
            align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        elif pos == "Center-Left":
            tx, ty = margin, (h - text_h) / 2
            align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        elif pos == "Center":
            tx, ty = (w - text_w) / 2, (h - text_h) / 2
            align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        elif pos == "Center-Right":
            tx, ty = w - text_w - margin, (h - text_h) / 2
            align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        elif pos == "Bottom-Left":
            tx, ty = margin, h - text_h - margin
            align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
        elif pos == "Bottom-Center":
            tx, ty = (w - text_w) / 2, h - text_h - margin
            align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
        elif pos == "Bottom-Right":
            tx, ty = w - text_w - margin, h - text_h - margin
            align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom
        else:
            tx = int(state.custom_x * w)
            ty = int(state.custom_y * h)
            align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop

        tx = max(margin, min(tx, w - text_w - margin))
        ty = max(margin, min(ty, h - text_h - margin))

        y_offset = 0
        for i, line in enumerate(lines):
            ly = ty + y_offset + fm.ascent()

            # Shadow
            if state.shadow_enabled and state.shadow_blur > 0:
                p.setOpacity(state.opacity * state.shadow_opacity)
                sc = QColor(state.shadow_color)
                blur = state.shadow_blur
                for j in range(blur, 0, -2):
                    alpha = int(255 * (1 - j / blur) * 0.4)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(sc.red(), sc.green(), sc.blue(),
                                      max(0, min(255, alpha))))
                    ox = state.shadow_offset_x + j // 2
                    oy = state.shadow_offset_y + j // 2
                    p.drawText(QRectF(tx + ox, ty + y_offset + oy,
                                      text_w, line_heights[i]), align, line)
                p.setOpacity(state.opacity)

            # Outline (stroke via QPainterPath)
            if state.outline_color and state.outline_width > 0:
                oc = QColor(state.outline_color)
                p.setPen(QPen(oc, state.outline_width * 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                path = QPainterPath()
                path.addText(QPointF(tx, ly), font, line)
                p.drawPath(path)
                p.setPen(Qt.PenStyle.NoPen)

            # Main text
            p.setPen(QColor(state.color))
            p.drawText(QRectF(tx, ty + y_offset, text_w, line_heights[i]),
                       align, line)

            y_offset += line_heights[i] + 4

    p.end()
    return canvas


# ══════════════════════════════════════════════════════════════════════════════
# Preview Canvas  (zoom, pan, drag badge, right-click menu)
# ══════════════════════════════════════════════════════════════════════════════

class PreviewCanvas(QWidget):
    """Main preview area with zoom, pan, and draggable badge."""

    zoom_changed = Signal(float)
    badge_moved = Signal(float, float)   # normalised x, y
    context_menu_requested = Signal(QPointF)
    images_dropped = Signal(list)         # list[str] paths
    video_dropped = Signal(list)          # list[str] video paths
    image_pasted = Signal()              # single paste

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._composite: Optional[QPixmap] = None
        self._zoom: float = 1.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._fit_mode: str = "fit"  # fit / 1:1 / fill
        self._dragging_badge: bool = False
        self._panning: bool = False
        self._last_pos: Optional[QPointF] = None
        self.setMinimumSize(400, 225)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

    def set_composite(self, pm: QPixmap) -> None:
        self._composite = pm
        self._reset_view()
        self.update()

    def set_fit_mode(self, mode: str) -> None:
        self._fit_mode = mode
        self._reset_view()
        self.update()

    def _reset_view(self) -> None:
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.zoom_changed.emit(1.0)

    def zoom_in(self) -> None:
        self._zoom = min(5.0, self._zoom * 1.25)
        self.zoom_changed.emit(self._zoom)
        self.update()

    def zoom_out(self) -> None:
        self._zoom = max(0.1, self._zoom / 1.25)
        self.zoom_changed.emit(self._zoom)
        self.update()

    def zoom_reset(self) -> None:
        self._reset_view()
        self.update()

    @property
    def zoom(self) -> float:
        return self._zoom

    # ── Coordinate mapping ───────────────────────────────────────────

    def _image_rect(self) -> QRectF:
        """The rect where the (scaled, panned) composite is drawn."""
        if not self._composite or self._composite.isNull():
            return QRectF()
        base = _scaled_in(self._composite, self.width(), self.height(), self._fit_mode)
        sw = base.width() * self._zoom
        sh = base.height() * self._zoom
        sx = (self.width() - sw) / 2 + self._pan_x
        sy = (self.height() - sh) / 2 + self._pan_y
        return QRectF(sx, sy, sw, sh)

    def _widget_to_image(self, wp: QPointF) -> QPointF:
        """Map a widget-space point to the full-res composite image space."""
        ir = self._image_rect()
        if ir.isEmpty() or not self._composite:
            return QPointF()
        ix = (wp.x() - ir.x()) / ir.width() * self._composite.width()
        iy = (wp.y() - ir.y()) / ir.height() * self._composite.height()
        return QPointF(ix, iy)

    # ── Painting ─────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#111111"))

        if not self._composite or self._composite.isNull():
            p.setPen(QColor("#555"))
            f = QFont("Segoe UI", 15)
            f.setBold(True)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Drop images or videos here  |  Ctrl+O  |  Ctrl+V  |  Ctrl+Shift+O video")
            # Draw keyboard shortcut hints
            p.setPen(QColor("#444"))
            f2 = QFont("Segoe UI", 10)
            p.setFont(f2)
            p.drawText(QRectF(0, self.height() * 0.62, self.width(), 30),
                       Qt.AlignmentFlag.AlignCenter,
                       "Arrow keys cycle  |  Ctrl+Z undo  |  Ctrl+Y redo  |  Scroll to zoom  |  Right-click for options")
            p.end()
            return

        ir = self._image_rect()
        # Clip so zoomed image doesn't bleed
        p.setClipRect(self.rect())
        p.drawPixmap(QRectF(ir.x(), ir.y(), ir.width(), ir.height()), self._composite, self._composite.rect())

        # Zoom indicator
        if self._zoom != 1.0:
            p.setClipping(False)
            p.setPen(QColor("#666"))
            f = QFont("Inter", 9)
            p.setFont(f)
            p.drawText(10, self.height() - 10, f"{int(self._zoom * 100)}%")
        p.end()

    # ── Mouse events ────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.context_menu_requested.emit(event.position())
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._last_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_badge = True
            self._last_pos = event.position()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._panning and self._last_pos:
            dx = event.position().x() - self._last_pos.x()
            dy = event.position().y() - self._last_pos.y()
            self._pan_x += dx
            self._pan_y += dy
            self._last_pos = event.position()
            self.update()
            return
        if self._dragging_badge and self._last_pos and self._composite:
            img_pos = self._widget_to_image(event.position())
            # Convert to normalised custom position
            bw_ratio = max(0.01, 80 / self._composite.width())   # approximate badge w/h ratio
            bh_ratio = max(0.01, 30 / self._composite.height())
            nx = max(0, min(1, (img_pos.x() / self._composite.width()) - bw_ratio / 2))
            ny = max(0, min(1, (img_pos.y() / self._composite.height()) - bh_ratio / 2))
            self.badge_moved.emit(nx, ny)
            self._last_pos = event.position()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self._dragging_badge = False
        self._last_pos = None

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    # ── Drag & drop ─────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
            vid_exts = VIDEO_EXTS
            if any(u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() in exts
                   for u in event.mimeData().urls()):
                event.acceptProposedAction()
                return
            if any(u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() in vid_exts
                   for u in event.mimeData().urls()):
                event.acceptProposedAction()
                return
        if event.mimeData().hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasImage():
            img = event.mimeData().imageData()
            if isinstance(img, QImage) and not img.isNull():
                self._pasted_img = img
                self.image_pasted.emit()
                event.acceptProposedAction()
                return
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            if paths:
                img_paths = [p for p in paths if Path(p).suffix.lower() not in VIDEO_EXTS]
                vid_paths = [p for p in paths if Path(p).suffix.lower() in VIDEO_EXTS]
                if img_paths:
                    self.images_dropped.emit(img_paths)
                if vid_paths:
                    self.video_dropped.emit(vid_paths)
                event.acceptProposedAction()

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Paste):
            self._try_paste()
            return
        super().keyPressEvent(event)

    def _try_paste(self) -> None:
        cb = QApplication.clipboard()
        if not cb:
            return
        img = cb.image()
        if img.isNull():
            pm = cb.pixmap()
            if not pm.isNull():
                img = pm.toImage()
        if not img.isNull():
            self._pasted_img = img
            self.image_pasted.emit()

# ══════════════════════════════════════════════════════════════════════════════
# Thumbnail Strip  (bottom bar with drag-reorder)
# ══════════════════════════════════════════════════════════════════════════════

STRIP_H = 72

class ThumbnailStrip(QWidget):
    current_changed = Signal(int)
    order_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full: List[QImage] = []
        self._thumbs: List[QPixmap] = []
        self._paths: List[str] = []   # original file paths (for display)
        self._index: int = -1
        self._scroll_offset: int = 0
        self._drag_idx: int = -1
        self.setFixedHeight(STRIP_H + 14)
        self.setMinimumWidth(300)
        self.setMouseTracking(True)

    def load_images(self, images: List[QImage], paths: Optional[List[str]] = None) -> None:
        self._full = list(images)
        self._paths = list(paths) if paths else [""] * len(images)
        self._rebuild_thumbs()
        self._index = 0 if self._full else -1
        self._scroll_offset = 0
        self.current_changed.emit(self._index)
        self.update()

    def append_images(self, images: List[QImage], paths: Optional[List[str]] = None) -> None:
        p = list(paths) if paths else [""] * len(images)
        for img, pth in zip(images, p):
            self._full.append(img)
            self._paths.append(pth)
            pm = QPixmap.fromImage(img)
            ar = pm.width() / max(1, pm.height())
            tw = max(60, int(STRIP_H * ar))
            self._thumbs.append(pm.scaled(tw, STRIP_H,
                                          Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
        if self._index < 0:
            self._index = 0
        self.current_changed.emit(self._index)
        self.update()

    def _rebuild_thumbs(self) -> None:
        self._thumbs = []
        for img in self._full:
            pm = QPixmap.fromImage(img)
            ar = pm.width() / max(1, pm.height())
            tw = max(60, int(STRIP_H * ar))
            self._thumbs.append(pm.scaled(tw, STRIP_H,
                                          Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))

    def set_index(self, idx: int) -> None:
        if 0 <= idx < len(self._full):
            self._index = idx
            self._ensure_visible(idx)
            self.current_changed.emit(self._index)
            self.update()

    def go_next(self) -> None:
        if self._full:
            self.set_index((self._index + 1) % len(self._full))

    def go_prev(self) -> None:
        if self._full:
            self.set_index((self._index - 1) % len(self._full))

    def go_first(self) -> None:
        if self._full:
            self.set_index(0)

    def go_last(self) -> None:
        if self._full:
            self.set_index(len(self._full) - 1)

    def remove_current(self) -> None:
        if 0 <= self._index < len(self._full):
            del self._full[self._index]
            del self._thumbs[self._index]
            del self._paths[self._index]
            if self._index >= len(self._full):
                self._index = max(0, len(self._full) - 1)
            self.current_changed.emit(self._index)
            self.order_changed.emit()
            self.update()

    def move_current(self, direction: int) -> None:
        """Move current item by *direction* (-1 left, +1 right)."""
        i = self._index + direction
        if 0 <= i < len(self._full):
            self._full[self._index], self._full[i] = self._full[i], self._full[self._index]
            self._thumbs[self._index], self._thumbs[i] = self._thumbs[i], self._thumbs[self._index]
            self._paths[self._index], self._paths[i] = self._paths[i], self._paths[self._index]
            self._index = i
            self.order_changed.emit()
            self.update()

    def clear(self) -> None:
        self._full.clear()
        self._thumbs.clear()
        self._paths.clear()
        self._index = -1
        self.current_changed.emit(-1)
        self.update()

    def _ensure_visible(self, idx: int) -> None:
        """Scroll so thumb at *idx* is visible."""
        if idx < 0 or idx >= len(self._thumbs):
            return
        total_w = sum(t.width() for t in self._thumbs) + 6 * max(0, len(self._thumbs) - 1) + 16
        thumb_x = sum(self._thumbs[j].width() + 6 for j in range(idx))
        if thumb_x < self._scroll_offset:
            self._scroll_offset = thumb_x
        elif thumb_x + self._thumbs[idx].width() > self._scroll_offset + self.width() - 16:
            self._scroll_offset = thumb_x + self._thumbs[idx].width() - (self.width() - 16)
        self._scroll_offset = max(0, self._scroll_offset)

    @property
    def index(self) -> int:
        return self._index

    @property
    def count(self) -> int:
        return len(self._full)

    def current_image(self) -> Optional[QImage]:
        if 0 <= self._index < len(self._full):
            return self._full[self._index]
        return None

    def current_path(self) -> str:
        if 0 <= self._index < len(self._paths):
            return self._paths[self._index]
        return ""

    # ── Layout helpers ───────────────────────────────────────────────

    def _thumb_layout(self) -> List[Tuple[int, int, QPixmap]]:
        """Return [(x, y, pixmap), ...] for visible thumbs."""
        x = 8 - self._scroll_offset
        y = 7
        result = []
        for pm in self._thumbs:
            if x + pm.width() >= 0 and x <= self.width():
                result.append((x, y, pm))
            x += pm.width() + 6
        return result

    def _index_at(self, wx: int) -> int:
        cx = 8 - self._scroll_offset
        for i, pm in enumerate(self._thumbs):
            if cx <= wx <= cx + pm.width():
                return i
            cx += pm.width() + 6
        return -1

    # ── Paint ────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # Background
        p.fillRect(self.rect(), QColor("#181818"))
        # Top edge line
        p.setPen(QPen(QColor("#2a2a2a"), 1))
        p.drawLine(0, 0, self.width(), 0)

        if not self._thumbs:
            p.setPen(QColor("#555"))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No images loaded")
            p.end()
            return

        clip_rect = QRectF(8, 0, self.width() - 16, self.height())
        p.setClipRect(clip_rect)

        x = 8 - self._scroll_offset
        y = 7
        for i, pm in enumerate(self._thumbs):
            # Selection highlight
            if i == self._index:
                p.setPen(QPen(QColor("#2563EB"), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(x - 3, y - 3, pm.width() + 6, pm.height() + 6, 6, 6)
            else:
                p.setPen(QPen(QColor("#333"), 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(x - 1, y - 1, pm.width() + 2, pm.height() + 2, 4, 4)

            # Draw thumb
            if i != self._index:
                p.setOpacity(0.45)
            p.drawPixmap(x, y, pm)
            p.setOpacity(1.0)

            # Index number
            p.setPen(QColor("#FFF" if i == self._index else "#888"))
            f = QFont("Inter", 8)
            f.setBold(True)
            p.setFont(f)
            p.drawText(x + 3, y + pm.height() - 3, str(i + 1))

            x += pm.width() + 6

        # Fade edges
        p.setClipping(False)
        fade_w = 20
        for px in range(fade_w):
            alpha = int(255 * (1 - px / fade_w))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(24, 24, 24, alpha))
            p.drawRect(px, 0, 1, self.height())
            p.drawRect(self.width() - px - 1, 0, 1, self.height())

        p.end()

    # ── Mouse ───────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._index_at(int(event.position().x()))
            if idx >= 0:
                self.set_index(idx)
                self._drag_idx = idx

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_idx >= 0 and event.buttons() & Qt.MouseButton.LeftButton:
            target = self._index_at(int(event.position().x()))
            if target >= 0 and target != self._drag_idx:
                direction = 1 if target > self._drag_idx else -1
                self._full[self._drag_idx], self._full[target] = self._full[target], self._full[self._drag_idx]
                self._thumbs[self._drag_idx], self._thumbs[target] = self._thumbs[target], self._thumbs[self._drag_idx]
                self._paths[self._drag_idx], self._paths[target] = self._paths[target], self._paths[self._drag_idx]
                self._index = target
                self._drag_idx = target
                self.current_changed.emit(self._index)
                self.order_changed.emit()
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_idx = -1

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.angleDelta().y() > 0:
            self.go_prev()
        else:
            self.go_next()

# ══════════════════════════════════════════════════════════════════════════════
# Control Panel
# ══════════════════════════════════════════════════════════════════════════════

class ControlPanel(QScrollArea):
    badge_changed = Signal()

    def __init__(self, state: BadgeState, undo: UndoStack, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._undo = undo
        self._block = False

        container = QWidget()
        lo = QVBoxLayout(container)
        lo.setSpacing(6)
        lo.setContentsMargins(12, 12, 12, 12)

        # ── Badge Style ──
        g1 = QGroupBox("Badge Style")
        gl = QGridLayout(g1)
        gl.setSpacing(6)
        gl.setContentsMargins(10, 18, 10, 10)

        gl.addWidget(QLabel("Preset:"), 0, 0)
        self.combo_style = QComboBox()
        self.combo_style.addItems(BADGE_STYLES.keys())
        self.combo_style.setCurrentText(state.style_name)
        self.combo_style.currentTextChanged.connect(self._on_style)
        gl.addWidget(self.combo_style, 0, 1)

        gl.addWidget(QLabel("Text:"), 1, 0)
        self.btn_text = QPushButton(state.text)
        self.btn_text.setFixedHeight(28)
        self.btn_text.setToolTip("Click to change badge text")
        self.btn_text.clicked.connect(self._on_edit_text)
        gl.addWidget(self.btn_text, 1, 1)

        gl.addWidget(QLabel("Position:"), 2, 0)
        self.combo_pos = QComboBox()
        self.combo_pos.addItems(CORNER_POSITIONS)
        self.combo_pos.setCurrentText(state.position)
        self.combo_pos.currentTextChanged.connect(self._on_pos)
        gl.addWidget(self.combo_pos, 2, 1)

        self.lbl_drag_hint = QLabel("Drag on preview to reposition")
        self.lbl_drag_hint.setObjectName("Shortcut")
        self.lbl_drag_hint.setWordWrap(True)
        gl.addWidget(self.lbl_drag_hint, 3, 0, 1, 2)

        lo.addWidget(g1)

        # ── Size ──
        g2 = QGroupBox("Size & Shape")
        sl = QGridLayout(g2)
        sl.setSpacing(6)
        sl.setContentsMargins(10, 18, 10, 10)

        sl.addWidget(QLabel("Font Size:"), 0, 0)
        self.spin_font = QDoubleSpinBox()
        self.spin_font.setRange(0.01, 0.20)
        self.spin_font.setSingleStep(0.003)
        self.spin_font.setDecimals(3)
        self.spin_font.setValue(state.font_size_ratio)
        self.spin_font.valueChanged.connect(lambda v: self._set("font_size_ratio", v))
        sl.addWidget(self.spin_font, 0, 1)

        sl.addWidget(QLabel("Corner Radius:"), 1, 0)
        self.spin_radius = QSpinBox()
        self.spin_radius.setRange(0, 100)
        self.spin_radius.setValue(state.corner_radius)
        self.spin_radius.valueChanged.connect(lambda v: self._set("corner_radius", v))
        sl.addWidget(self.spin_radius, 1, 1)

        sl.addWidget(QLabel("Margin:"), 2, 0)
        self.spin_margin = QDoubleSpinBox()
        self.spin_margin.setRange(0.0, 0.20)
        self.spin_margin.setSingleStep(0.005)
        self.spin_margin.setDecimals(3)
        self.spin_margin.setValue(state.margin_ratio)
        self.spin_margin.valueChanged.connect(lambda v: self._set("margin_ratio", v))
        sl.addWidget(self.spin_margin, 2, 1)

        lo.addWidget(g2)

        # ── Colors ──
        g3 = QGroupBox("Colors")
        cl = QGridLayout(g3)
        cl.setSpacing(6)
        cl.setContentsMargins(10, 18, 10, 10)

        cl.addWidget(QLabel("Text:"), 0, 0)
        self.btn_tc = QPushButton()
        self.btn_tc.setFixedSize(48, 22)
        self._cbtn(self.btn_tc, state.text_color)
        self.btn_tc.clicked.connect(lambda: self._pick("text_color", self.btn_tc))
        cl.addWidget(self.btn_tc, 0, 1)

        cl.addWidget(QLabel("Background:"), 1, 0)
        self.btn_bg = QPushButton()
        self.btn_bg.setFixedSize(48, 22)
        self._cbtn(self.btn_bg, state.bg_color or QColor("#E50914"))
        self.btn_bg.clicked.connect(self._on_bg)
        cl.addWidget(self.btn_bg, 1, 1)

        self.chk_no_bg = QCheckBox("No fill")
        self.chk_no_bg.setChecked(state.bg_color is None)
        self.chk_no_bg.toggled.connect(self._on_no_bg)
        cl.addWidget(self.chk_no_bg, 1, 2)

        cl.addWidget(QLabel("Border:"), 2, 0)
        self.btn_bc = QPushButton()
        self.btn_bc.setFixedSize(48, 22)
        self._cbtn(self.btn_bc, state.border_color or QColor("#FF0000"))
        self.btn_bc.clicked.connect(lambda: self._pick("border_color", self.btn_bc))
        cl.addWidget(self.btn_bc, 2, 1)

        cl.addWidget(QLabel("Border W:"), 3, 0)
        self.spin_bw = QSpinBox()
        self.spin_bw.setRange(0, 20)
        self.spin_bw.setValue(state.border_width)
        self.spin_bw.valueChanged.connect(lambda v: self._set("border_width", v))
        cl.addWidget(self.spin_bw, 3, 1)

        lo.addWidget(g3)

        # ── Shadow ──
        g4 = QGroupBox("Shadow")
        shl = QGridLayout(g4)
        shl.setSpacing(6)
        shl.setContentsMargins(10, 18, 10, 10)

        self.chk_shadow = QCheckBox("Enabled")
        self.chk_shadow.setChecked(state.shadow_enabled)
        self.chk_shadow.toggled.connect(lambda v: self._set("shadow_enabled", v))
        shl.addWidget(self.chk_shadow, 0, 0, 1, 2)

        shl.addWidget(QLabel("Opacity:"), 1, 0)
        self.slider_op = QSlider(Qt.Orientation.Horizontal)
        self.slider_op.setRange(0, 100)
        self.slider_op.setValue(int(state.shadow_opacity * 100))
        self.lbl_op = QLabel(f"{int(state.shadow_opacity * 100)}%")
        self.lbl_op.setObjectName("LblValue")
        self.lbl_op.setFixedWidth(36)
        self.slider_op.valueChanged.connect(self._on_opacity)
        shl.addWidget(self.slider_op, 1, 1)
        shl.addWidget(self.lbl_op, 1, 2)

        shl.addWidget(QLabel("Blur:"), 2, 0)
        self.spin_blur = QSpinBox()
        self.spin_blur.setRange(0, 40)
        self.spin_blur.setValue(state.shadow_blur)
        self.spin_blur.valueChanged.connect(lambda v: self._set("shadow_blur", v))
        shl.addWidget(self.spin_blur, 2, 1)

        lo.addWidget(g4)

        # ── Output ──
        g5 = QGroupBox("Output")
        ol = QGridLayout(g5)
        ol.setSpacing(6)
        ol.setContentsMargins(10, 18, 10, 10)

        ol.addWidget(QLabel("Size:"), 0, 0)
        self.combo_out = QComboBox()
        self.combo_out.addItems(PRESETS.keys())
        self.combo_out.currentTextChanged.connect(lambda _: self.badge_changed.emit())
        ol.addWidget(self.combo_out, 0, 1)

        ol.addWidget(QLabel("Opacity:"), 1, 0)
        self.slider_bopacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_bopacity.setRange(10, 100)
        self.slider_bopacity.setValue(int(state.opacity * 100))
        self.lbl_bop = QLabel(f"{int(state.opacity * 100)}%")
        self.lbl_bop.setObjectName("LblValue")
        self.lbl_bop.setFixedWidth(36)
        self.slider_bopacity.valueChanged.connect(self._on_bopacity)
        ol.addWidget(self.slider_bopacity, 1, 1)
        ol.addWidget(self.lbl_bop, 1, 2)

        lo.addWidget(g5)

        lo.addStretch()
        self.setWidget(container)
        self.setWidgetResizable(True)
        self.setMinimumWidth(270)
        self.setMaximumWidth(330)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    # helpers

    @staticmethod
    def _cbtn(btn: QPushButton, c: QColor) -> None:
        border = "#666" if c.lightness() > 128 else "#444"
        btn.setStyleSheet(f"background:{c.name()}; border:1px solid {border}; border-radius:4px;")

    def _push_undo(self) -> None:
        self._undo.push(self._state.to_dict())

    def _emit(self) -> None:
        if not self._block:
            self._push_undo()
            self.badge_changed.emit()

    def _set(self, attr: str, val) -> None:
        setattr(self._state, attr, val)
        self._emit()

    def _on_opacity(self, v: int) -> None:
        self._state.shadow_opacity = v / 100.0
        self.lbl_op.setText(f"{v}%")
        self._emit()

    def _on_bopacity(self, v: int) -> None:
        self._state.opacity = v / 100.0
        self.lbl_bop.setText(f"{v}%")
        self._emit()

    def _on_pos(self, p: str) -> None:
        self._state.position = p
        self.lbl_drag_hint.setVisible(p == "Custom")
        self._emit()

    def _pick(self, attr: str, btn: QPushButton) -> None:
        cur = getattr(self._state, attr) or QColor("#000000")
        c = QColorDialog.getColor(cur, self)
        if c.isValid():
            setattr(self._state, attr, c)
            self._cbtn(btn, c)
            self._emit()

    def _on_bg(self) -> None:
        cur = self._state.bg_color or QColor("#E50914")
        c = QColorDialog.getColor(cur, self)
        if c.isValid():
            self._state.bg_color = c
            self.chk_no_bg.setChecked(False)
            self._cbtn(self.btn_bg, c)
            self._emit()

    def _on_no_bg(self, checked: bool) -> None:
        self._state.bg_color = None if checked else QColor(self.btn_bg.styleSheet().split("background:")[1].split(";")[0])
        self._emit()

    def _on_style(self, name: str) -> None:
        self._push_undo()
        self._state.apply_style(name)
        self._sync()
        self.badge_changed.emit()

    def _on_edit_text(self) -> None:
        text, ok = QInputDialog.getText(self, "Badge Text", "Enter badge text:", text=self._state.text)
        if ok and text.strip():
            self._state.text = text.strip()
            self.btn_text.setText(text.strip())
            self._emit()

    def _sync(self) -> None:
        self._block = True
        s = self._state
        self.combo_style.setCurrentText(s.style_name)
        self.btn_text.setText(s.text)
        self.combo_pos.setCurrentText(s.position)
        self.lbl_drag_hint.setVisible(s.position == "Custom")
        self.spin_font.setValue(s.font_size_ratio)
        self.spin_radius.setValue(s.corner_radius)
        self.spin_margin.setValue(s.margin_ratio)
        self._cbtn(self.btn_tc, s.text_color)
        if s.bg_color:
            self._cbtn(self.btn_bg, s.bg_color)
        self.chk_no_bg.setChecked(s.bg_color is None)
        self._cbtn(self.btn_bc, s.border_color or QColor("#FF0000"))
        self.spin_bw.setValue(s.border_width)
        self.chk_shadow.setChecked(s.shadow_enabled)
        self.slider_op.setValue(int(s.shadow_opacity * 100))
        self.lbl_op.setText(f"{int(s.shadow_opacity * 100)}%")
        self.spin_blur.setValue(s.shadow_blur)
        self.slider_bopacity.setValue(int(s.opacity * 100))
        self.lbl_bop.setText(f"{int(s.opacity * 100)}%")
        self._block = False

    def load_state(self, d: dict) -> None:
        self._state.load_dict(d)
        self._sync()


# ══════════

# ══════════════════════════════════════════════════════════════════════════════
# Text Overlay Panel
# ══════════════════════════════════════════════════════════════════════════════

class TextOverlayPanel(QWidget):
    """Panel for managing text overlays (add, edit, remove, reorder)."""

    overlay_changed = Signal()

    def __init__(self, overlays: list, undo: UndoStack, parent=None):
        super().__init__(parent)
        self._overlays = overlays
        self._undo = undo
        self._current_idx: int = -1
        self._block = False
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Text Overlays"))
        hdr.addStretch()
        btn_add = QPushButton("+ Add Layer")
        btn_add.setFixedHeight(26)
        btn_add.clicked.connect(self._add_layer)
        hdr.addWidget(btn_add)
        root.addLayout(hdr)

        # Layer list
        self._list = QListWidget()
        self._list.setMaximumHeight(100)
        self._list.currentRowChanged.connect(self._on_layer_selected)
        root.addWidget(self._list)

        # Preset selector
        g_preset = QGroupBox("Preset")
        pl = QHBoxLayout(g_preset)
        self._combo_preset = QComboBox()
        self._combo_preset.addItems(TEXT_PRESETS.keys())
        self._combo_preset.currentTextChanged.connect(self._on_preset)
        pl.addWidget(self._combo_preset)
        root.addWidget(g_preset)

        # Text editing
        g_text = QGroupBox("Text Content")
        tl = QVBoxLayout(g_text)
        self._text_edit = QTextEdit()
        self._text_edit.setMaximumHeight(60)
        self._text_edit.setPlaceholderText("Enter overlay text...")
        self._text_edit.textChanged.connect(self._on_text_changed)
        tl.addWidget(self._text_edit)
        root.addWidget(g_text)

        # Font settings
        g_font = QGroupBox("Font")
        fl = QGridLayout(g_font)
        fl.setSpacing(6)
        fl.setContentsMargins(10, 18, 10, 10)

        fl.addWidget(QLabel("Font:"), 0, 0)
        self._combo_font = QFontComboBox()
        self._combo_font.currentTextChanged.connect(self._on_font_changed)
        fl.addWidget(self._combo_font, 0, 1)

        fl.addWidget(QLabel("Size:"), 1, 0)
        self._spin_size = QDoubleSpinBox()
        self._spin_size.setRange(0.01, 0.20)
        self._spin_size.setSingleStep(0.005)
        self._spin_size.setDecimals(3)
        self._spin_size.valueChanged.connect(lambda v: self._set("font_size_ratio", v))
        fl.addWidget(self._spin_size, 1, 1)

        self._chk_bold = QCheckBox("Bold")
        self._chk_bold.toggled.connect(lambda v: self._set("bold", v))
        fl.addWidget(self._chk_bold, 2, 0)

        self._chk_italic = QCheckBox("Italic")
        self._chk_italic.toggled.connect(lambda v: self._set("italic", v))
        fl.addWidget(self._chk_italic, 2, 1)

        root.addWidget(g_font)

        # Colors
        g_colors = QGroupBox("Colors & Stroke")
        cl = QGridLayout(g_colors)
        cl.setSpacing(6)
        cl.setContentsMargins(10, 18, 10, 10)

        cl.addWidget(QLabel("Text:"), 0, 0)
        self._btn_text_color = QPushButton()
        self._btn_text_color.setFixedSize(48, 22)
        self._btn_text_color.clicked.connect(self._pick_text_color)
        cl.addWidget(self._btn_text_color, 0, 1)

        cl.addWidget(QLabel("Outline:"), 1, 0)
        self._btn_outline_color = QPushButton()
        self._btn_outline_color.setFixedSize(48, 22)
        self._btn_outline_color.clicked.connect(self._pick_outline_color)
        cl.addWidget(self._btn_outline_color, 1, 1)

        self._chk_no_outline = QCheckBox("No Outline")
        self._chk_no_outline.toggled.connect(self._on_no_outline)
        cl.addWidget(self._chk_no_outline, 1, 2)

        cl.addWidget(QLabel("Stroke W:"), 2, 0)
        self._spin_outline_w = QSpinBox()
        self._spin_outline_w.setRange(0, 20)
        self._spin_outline_w.valueChanged.connect(lambda v: self._set("outline_width", v))
        cl.addWidget(self._spin_outline_w, 2, 1)

        root.addWidget(g_colors)

        # Shadow
        g_shadow = QGroupBox("Shadow")
        shl = QGridLayout(g_shadow)
        shl.setSpacing(6)
        shl.setContentsMargins(10, 18, 10, 10)

        self._chk_shadow = QCheckBox("Enabled")
        self._chk_shadow.toggled.connect(lambda v: self._set("shadow_enabled", v))
        shl.addWidget(self._chk_shadow, 0, 0, 1, 2)

        shl.addWidget(QLabel("Opacity:"), 1, 0)
        self._slider_shadow_op = QSlider(Qt.Orientation.Horizontal)
        self._slider_shadow_op.setRange(0, 100)
        self._slider_shadow_op.valueChanged.connect(self._on_shadow_opacity)
        shl.addWidget(self._slider_shadow_op, 1, 1)
        self._lbl_shadow_op = QLabel("70%")
        self._lbl_shadow_op.setObjectName("LblValue")
        self._lbl_shadow_op.setFixedWidth(36)
        shl.addWidget(self._lbl_shadow_op, 1, 2)

        shl.addWidget(QLabel("Blur:"), 2, 0)
        self._spin_shadow_blur = QSpinBox()
        self._spin_shadow_blur.setRange(0, 40)
        self._spin_shadow_blur.valueChanged.connect(lambda v: self._set("shadow_blur", v))
        shl.addWidget(self._spin_shadow_blur, 2, 1)

        shl.addWidget(QLabel("Offset X:"), 3, 0)
        self._spin_ox = QSpinBox()
        self._spin_ox.setRange(-20, 20)
        self._spin_ox.valueChanged.connect(lambda v: self._set("shadow_offset_x", v))
        shl.addWidget(self._spin_ox, 3, 1)

        shl.addWidget(QLabel("Y:"), 3, 2)
        self._spin_oy = QSpinBox()
        self._spin_oy.setRange(-20, 20)
        self._spin_oy.valueChanged.connect(lambda v: self._set("shadow_offset_y", v))
        shl.addWidget(self._spin_oy, 3, 3)

        root.addWidget(g_shadow)

        # Position
        g_pos = QGroupBox("Position")
        pol = QGridLayout(g_pos)
        pol.setSpacing(6)
        pol.setContentsMargins(10, 18, 10, 10)

        pol.addWidget(QLabel("Zone:"), 0, 0)
        self._combo_pos = QComboBox()
        self._combo_pos.addItems(TEXT_POSITIONS)
        self._combo_pos.currentTextChanged.connect(lambda v: self._set("position", v))
        pol.addWidget(self._combo_pos, 0, 1, 1, 2)

        pol.addWidget(QLabel("Opacity:"), 1, 0)
        self._slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self._slider_opacity.setRange(5, 100)
        self._slider_opacity.valueChanged.connect(self._on_opacity)
        pol.addWidget(self._slider_opacity, 1, 1)
        self._lbl_opacity = QLabel("100%")
        self._lbl_opacity.setObjectName("LblValue")
        self._lbl_opacity.setFixedWidth(36)
        pol.addWidget(self._lbl_opacity, 1, 2)

        self._chk_visible = QCheckBox("Visible")
        self._chk_visible.setChecked(True)
        self._chk_visible.toggled.connect(lambda v: self._set("visible", v))
        pol.addWidget(self._chk_visible, 2, 0, 1, 2)

        root.addWidget(g_pos)

        # Delete button
        btn_del = QPushButton("Delete Selected Layer")
        btn_del.clicked.connect(self._delete_layer)
        root.addWidget(btn_del)

        root.addStretch()

        self.setMinimumWidth(270)
        self.setMaximumWidth(330)

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _cbtn(btn: QPushButton, c: QColor) -> None:
        border = "#666" if c.lightness() > 128 else "#444"
        btn.setStyleSheet(f"background:{c.name()}; border:1px solid {border}; border-radius:4px;")

    def _current_state(self):
        if 0 <= self._current_idx < len(self._overlays):
            return self._overlays[self._current_idx]
        return None

    def _push_undo(self):
        snapshot = [o.to_dict() for o in self._overlays]
        self._undo.push({"_text_overlays": snapshot})

    def _emit(self):
        if not self._block:
            self._push_undo()
            self.overlay_changed.emit()

    def _set(self, attr: str, val):
        s = self._current_state()
        if s:
            setattr(s, attr, val)
            self._emit()

    def _refresh_list(self):
        self._block = True
        self._list.blockSignals(True)
        self._list.clear()
        for i, o in enumerate(self._overlays):
            label = f"#{i+1}: {o.text[:25]}{'...' if len(o.text)>25 else ''}"
            if not o.visible:
                label += "  [hidden]"
            item = QListWidgetItem(label)
            self._list.addItem(item)
        if 0 <= self._current_idx < self._list.count():
            self._list.setCurrentRow(self._current_idx)
        self._list.blockSignals(False)
        self._block = False

    def _sync_to_ui(self):
        s = self._current_state()
        if not s:
            return
        self._block = True
        self._text_edit.blockSignals(True)
        self._text_edit.setPlainText(s.text)
        self._text_edit.blockSignals(False)
        self._combo_font.setCurrentText(s.font_family)
        self._spin_size.setValue(s.font_size_ratio)
        self._chk_bold.setChecked(s.bold)
        self._chk_italic.setChecked(s.italic)
        self._cbtn(self._btn_text_color, QColor(s.color))
        if s.outline_color:
            self._cbtn(self._btn_outline_color, QColor(s.outline_color))
            self._chk_no_outline.setChecked(False)
        else:
            self._chk_no_outline.setChecked(True)
        self._spin_outline_w.setValue(s.outline_width)
        self._chk_shadow.setChecked(s.shadow_enabled)
        self._slider_shadow_op.setValue(int(s.shadow_opacity * 100))
        self._lbl_shadow_op.setText(f"{int(s.shadow_opacity * 100)}%")
        self._spin_shadow_blur.setValue(s.shadow_blur)
        self._spin_ox.setValue(s.shadow_offset_x)
        self._spin_oy.setValue(s.shadow_offset_y)
        self._combo_pos.setCurrentText(s.position)
        self._slider_opacity.setValue(int(s.opacity * 100))
        self._lbl_opacity.setText(f"{int(s.opacity * 100)}%")
        self._chk_visible.setChecked(s.visible)
        self._block = False

    # ── Actions ──────────────────────────────────────────────────────

    def _add_layer(self):
        self._push_undo()
        state = TextOverlayState()
        self._overlays.append(state)
        self._current_idx = len(self._overlays) - 1
        self._refresh_list()
        self._sync_to_ui()
        self.overlay_changed.emit()

    def _delete_layer(self):
        if not (0 <= self._current_idx < len(self._overlays)):
            return
        self._push_undo()
        del self._overlays[self._current_idx]
        if self._current_idx >= len(self._overlays):
            self._current_idx = max(0, len(self._overlays) - 1)
        self._refresh_list()
        self._sync_to_ui()
        self.overlay_changed.emit()

    def _on_layer_selected(self, row: int):
        self._current_idx = row
        self._sync_to_ui()

    def _on_preset(self, name: str):
        s = self._current_state()
        if not s:
            return
        self._push_undo()
        s.apply_preset(name)
        self._sync_to_ui()
        self._refresh_list()
        self.overlay_changed.emit()

    def _on_text_changed(self):
        s = self._current_state()
        if not s or self._block:
            return
        self._push_undo()
        s.text = self._text_edit.toPlainText()
        self._refresh_list()
        self.overlay_changed.emit()

    def _on_font_changed(self, family: str):
        s = self._current_state()
        if s:
            self._push_undo()
            s.font_family = family
            self._emit()

    def _pick_text_color(self):
        s = self._current_state()
        if not s:
            return
        c = QColorDialog.getColor(QColor(s.color), self)
        if c.isValid():
            s.color = c.name()
            self._cbtn(self._btn_text_color, c)
            self._emit()

    def _pick_outline_color(self):
        s = self._current_state()
        if not s:
            return
        cur = s.outline_color or "#000000"
        c = QColorDialog.getColor(QColor(cur), self)
        if c.isValid():
            s.outline_color = c.name()
            self._chk_no_outline.setChecked(False)
            self._cbtn(self._btn_outline_color, c)
            self._emit()

    def _on_no_outline(self, checked: bool):
        s = self._current_state()
        if not s:
            return
        if checked:
            s.outline_color = None
        else:
            s.outline_color = "#000000"
            self._cbtn(self._btn_outline_color, QColor("#000000"))
        self._emit()

    def _on_shadow_opacity(self, v: int):
        s = self._current_state()
        if s:
            s.shadow_opacity = v / 100.0
            self._lbl_shadow_op.setText(f"{v}%")
            self._emit()

    def _on_opacity(self, v: int):
        s = self._current_state()
        if s:
            s.opacity = v / 100.0
            self._lbl_opacity.setText(f"{v}%")
            self._emit()


# ══════════════════════════════════════════════════════════════════════════════
# Video Import Dialog
# ══════════════════════════════════════════════════════════════════════════════


class _FrameThumb(QFrame):
    """Single frame thumbnail widget with checkbox, timestamp, and CV score."""

    toggled = Signal(int, bool)   # index, checked

    def __init__(self, index: int, pixmap: QPixmap, label: str,
                 parent=None):
        super().__init__(parent)
        self.index = index
        self._score: dict | None = None
        self.setFixedSize(170, 130)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lo = QVBoxLayout(self)
        lo.setContentsMargins(4, 4, 4, 4)
        lo.setSpacing(1)

        # Top row: checkbox + score badge
        top = QHBoxLayout()
        self._chk = QCheckBox(f"#{index + 1}")
        self._chk.setChecked(True)
        self._chk.stateChanged.connect(
            lambda st: self.toggled.emit(index, st == Qt.CheckState.Checked.value))
        top.addWidget(self._chk)
        top.addStretch()

        self._lbl_score = QLabel("")
        self._lbl_score.setFixedWidth(36)
        self._lbl_score.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._lbl_score.setStyleSheet("font-size:10px; font-weight:700; font-family:'Inter','Consolas',monospace;")
        top.addWidget(self._lbl_score)
        lo.addLayout(top)

        # Pixmap
        self._lbl_img = QLabel()
        self._lbl_img.setPixmap(pixmap.scaled(
            156, 70, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        self._lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(self._lbl_img, stretch=1)

        # Timestamp + label row
        bottom = QHBoxLayout()
        lbl_ts = QLabel(label)
        lbl_ts.setObjectName("LblValue")
        bottom.addWidget(lbl_ts)
        self._lbl_tags = QLabel("")
        self._lbl_tags.setObjectName("LblValue")
        self._lbl_tags.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._lbl_tags.setStyleSheet("font-size:9px; color:#888;")
        bottom.addWidget(self._lbl_tags)
        lo.addLayout(bottom)

    # ── Score display ────────────────────────────────────────────────

    def set_score(self, score: dict):
        """Update the CV score display."""
        self._score = score
        ov = score.get("overall", 0)
        pct = int(ov * 100)
        # Color code: green >= 70, yellow >= 45, red < 45
        if ov >= 0.70:
            color = "#22C55E"
            border = "#22C55E"
        elif ov >= 0.45:
            color = "#EAB308"
            border = "#EAB308"
        else:
            color = "#EF4444"
            border = "#EF4444"
        self._lbl_score.setText(f"{pct}%")
        self._lbl_score.setStyleSheet(
            f"font-size:10px; font-weight:700; color:{color}; "
            f"font-family:'Inter','Consolas',monospace;")
        self.setStyleSheet(
            f"_FrameThumb {{ border:2px solid {border}; border-radius:6px; }}")
        # Tags
        tags = score.get("label", "")
        fc = score.get("face_count", 0)
        if fc > 0 and "face" not in tags:
            tags = f"{fc} face{'s' if fc > 1 else ''}, {tags}" if tags else f"{fc} face{'s' if fc > 1 else ''}"
        self._lbl_tags.setText(tags)

    def build_tooltip(self) -> str:
        """Build a detailed tooltip from the score dict."""
        if not self._score:
            return ""
        s = self._score
        return (
            f"Overall: {int(s.get('overall', 0) * 100)}%\n"
            f"Sharpness: {int(s.get('sharpness', 0) * 100)}%  |  "
            f"Faces: {s.get('face_count', 0)}  ({int(s.get('face_score', 0) * 100)}%)\n"
            f"Eyes: {s.get('eyes_detected', 0)}  ({int(s.get('eye_quality', 0) * 100)}%)  |  "
            f"Skin: {int(s.get('skin_tone_ratio', 0) * 100)}%\n"
            f"Brightness: {int(s.get('brightness', 0) * 100)}%  |  "
            f"Contrast: {int(s.get('contrast', 0) * 100)}%\n"
            f"Colorfulness: {int(s.get('colorfulness', 0) * 100)}%  |  "
            f"Harmony: {int(s.get('color_harmony', 0) * 100)}%\n"
            f"Saliency: {int(s.get('spectral_saliency', 0) * 100)}%  |  "
            f"Motion Blur: {int(s.get('motion_blur_score', 0) * 100)}%\n"
            f"Entropy: {int(s.get('histogram_entropy', 0) * 100)}%  |  "
            f"Text Regions: {int(s.get('text_region_score', 0) * 100)}%\n"
            f"Edges: {int(s.get('edge_density', 0) * 100)}%  |  "
            f"Composition: {int(s.get('composition', 0) * 100)}%\n"
            f"Temporal: {int(s.get('temporal_uniqueness', 0) * 100)}%"
        )

    def set_checked(self, on: bool):
        self._chk.setChecked(on)

    @property
    def checked(self) -> bool:
        return self._chk.isChecked()

    @property
    def score(self) -> dict | None:
        return self._score

class VideoImportDialog(QDialog):
    """Dialog to open a video, extract frames, select and import them."""

    frames_imported = Signal(list, list)   # [QImage], [str] labels

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Frame Analyzer")
        self.resize(920, 640)
        self._extractor = None
        self._analysis_worker = None
        self._frames: list = []
        self._labels: list = []
        self._thumbs: list = []
        self._scores: list = []
        self._video_path = ""
        self._auto_pick_pending = False
        self._init_ui()

    # ── UI ──────────────────────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── Video file selector ──
        row_file = QHBoxLayout()
        self._lbl_file = QLabel("No video selected")
        self._lbl_file.setObjectName("LblValue")
        row_file.addWidget(QLabel("Video:"))
        row_file.addWidget(self._lbl_file, stretch=1)
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse)
        row_file.addWidget(btn_browse)
        root.addLayout(row_file)

        # ── Video info ──
        self._lbl_info = QLabel("")
        self._lbl_info.setObjectName("LblValue")
        self._lbl_info.setWordWrap(True)
        self._lbl_info.setStyleSheet(
            "background:#1a1a1a; border:1px solid #333; border-radius:6px; "
            "padding:8px 10px; font-size:11px;")
        root.addWidget(self._lbl_info)

        # ── Settings ──
        g_set = QGroupBox("Extraction Settings")
        gl = QGridLayout(g_set)
        gl.setSpacing(8)
        gl.setContentsMargins(12, 20, 12, 10)

        gl.addWidget(QLabel("Mode:"), 0, 0)
        self._combo_mode = QComboBox()
        self._combo_mode.addItems(["Evenly Spaced", "Scene Detection", "Smart Pick (CV)"])
        self._combo_mode.setToolTip(
            "Evenly Spaced: N frames distributed across the video.\n"
            "Scene Detection: frames at detected scene changes.\n"
            "Smart Pick (Expert CV): sample the ENTIRE video at 1 fps,\n"
            "run 13 expert CV metrics (saliency, FFT blur, skin tone,\n"
            "entropy, eye quality, color harmony, text regions, etc.),\n"
            "auto-rank and select the top N best thumbnail frames.\n"
            "Optimized for long videos (5+ hours).")
        gl.addWidget(self._combo_mode, 0, 1)

        gl.addWidget(QLabel("Frames:"), 0, 2)
        self._spin_count = QSpinBox()
        self._spin_count.setRange(2, 500)
        self._spin_count.setValue(50)
        self._spin_count.setToolTip("Number of frames for Even/Scene modes.\n"
                                     "Smart Pick mode samples the entire video.")
        gl.addWidget(self._spin_count, 0, 3)

        self._btn_extract = QPushButton("  Extract Frames  ")
        self._btn_extract.setObjectName("btnPrimary")
        self._btn_extract.clicked.connect(self._extract)
        self._btn_extract.setEnabled(False)
        gl.addWidget(self._btn_extract, 0, 4)

        # Row 2: Analyze & Rank + Auto-select top
        self._btn_analyze = QPushButton("  Analyze & Rank (CV)  ")
        self._btn_analyze.setToolTip(
            "Run computer-vision analysis on extracted frames.\n"
            "Scores: sharpness, faces, brightness, color, contrast, edges, composition.")
        self._btn_analyze.setEnabled(False)
        self._btn_analyze.clicked.connect(self._run_analysis)
        gl.addWidget(self._btn_analyze, 1, 0, 1, 2)

        self._btn_auto = QPushButton("  Auto-Select Top N  ")
        self._btn_auto.setToolTip("Select the highest-scoring frames based on CV analysis.")
        self._btn_auto.setEnabled(False)
        self._btn_auto.clicked.connect(self._auto_select_top)
        gl.addWidget(self._btn_auto, 1, 2)

        self._spin_top = QSpinBox()
        self._spin_top.setRange(1, 200)
        self._spin_top.setValue(50)
        self._spin_top.setToolTip("Number of top-scored frames to auto-select")
        gl.addWidget(self._spin_top, 1, 3)

        self._btn_sort = QPushButton("  Sort by Score  ")
        self._btn_sort.setToolTip("Reorder thumbnails from highest to lowest CV score.")
        self._btn_sort.setEnabled(False)
        self._btn_sort.clicked.connect(self._sort_by_score)
        gl.addWidget(self._btn_sort, 1, 4)

        # Row 3: Temporal dedup + filter
        self._btn_dedup = QPushButton("  Filter Duplicates  ")
        self._btn_dedup.setToolTip("Remove near-duplicate frames (temporal similarity > threshold).\n"
                                   "Uses histogram comparison to find and remove redundant frames.")
        self._btn_dedup.setEnabled(False)
        self._btn_dedup.clicked.connect(self._filter_duplicates)
        gl.addWidget(self._btn_dedup, 2, 0, 1, 2)

        gl.addWidget(QLabel("Similarity:"), 2, 2)
        self._spin_dedup = QDoubleSpinBox()
        self._spin_dedup.setRange(0.80, 0.99)
        self._spin_dedup.setSingleStep(0.01)
        self._spin_dedup.setDecimals(2)
        self._spin_dedup.setValue(0.92)
        self._spin_dedup.setToolTip("Frames with Bhattacharyya distance below this threshold\n"
                                     "are considered duplicates and deselected.")
        gl.addWidget(self._spin_dedup, 2, 3)

        self._lbl_dedup_info = QLabel("")
        self._lbl_dedup_info.setObjectName("LblValue")
        self._lbl_dedup_info.setStyleSheet("font-size:10px; color:#888;")
        gl.addWidget(self._lbl_dedup_info, 2, 4)

        root.addWidget(g_set)

        # ── Progress ──
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(True)
        root.addWidget(self._progress)

        # ── Frame grid (scrollable) ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setMinimumHeight(200)
        self._grid_container = QWidget()
        self._grid_lo = QGridLayout(self._grid_container)
        self._grid_lo.setSpacing(8)
        self._grid_lo.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._grid_container)

        # Placeholder label
        self._lbl_placeholder = QLabel(
            "Select a video file and click \'Extract Frames\'")
        self._lbl_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid_lo.addWidget(self._lbl_placeholder, 0, 0)

        root.addWidget(self._scroll, stretch=1)

        # ── Bottom buttons ──
        bot = QHBoxLayout()

        self._lbl_selected = QLabel("Selected: 0 frames")
        self._lbl_selected.setObjectName("LblValue")
        bot.addWidget(self._lbl_selected)

        bot.addStretch()

        btn_sel_all = QPushButton("Select All")
        btn_sel_all.clicked.connect(self._select_all)
        bot.addWidget(btn_sel_all)

        btn_desel = QPushButton("Deselect All")
        btn_desel.clicked.connect(self._deselect_all)
        bot.addWidget(btn_desel)

        bot.addSpacing(20)

        self._btn_import = QPushButton("  Import Selected  ")
        self._btn_import.setObjectName("btnAccent")
        self._btn_import.setEnabled(False)
        self._btn_import.clicked.connect(self._import_selected)
        bot.addWidget(self._btn_import)

        btn_cancel = QPushButton("  Cancel  ")
        btn_cancel.clicked.connect(self.reject)
        bot.addWidget(btn_cancel)

        root.addLayout(bot)

    # ── Actions ─────────────────────────────────────────────────────

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", "", VIDEO_FILTER)
        if not path:
            return

        self._video_path = path
        self._lbl_file.setText(Path(path).name)
        self._lbl_file.setToolTip(path)

        # Probe video info
        info = VideoFrameExtractor.get_video_info(path)
        if "error" in info:
            self._lbl_info.setText(f"Error: {info['error']}")
            self._btn_extract.setEnabled(False)
            return
        self._btn_extract.setEnabled(True)
        self._set_info_text(info)

        # Clear previous results
        self._clear_grid()

    def _set_info_text(self, info: dict):
        dur = info["duration"]
        m, s = divmod(dur, 60)
        self._lbl_info.setText(
            f"  Resolution: {info['width']}x{info['height']}   |   "
            f"Duration: {int(m):02d}:{s:05.2f}   |   "
            f"FPS: {info['fps']}   |   "
            f"Codec: {info['codec']}   |   "
            f"Size: {info['size_mb']} MB   |   "
            f"Bitrate: {info['bitrate_kbps']} kbps")

    def _extract(self):
        if not self._video_path:
            return
        self._clear_grid()
        self._btn_extract.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)

        mode_idx = self._combo_mode.currentIndex()
        is_smart = mode_idx == 2
        is_scene = mode_idx == 1
        mode = "scenes" if is_scene else "even"

        info = VideoFrameExtractor.get_video_info(self._video_path)
        dur = info.get("duration", 0)

        if is_smart:
            # Dense full-video sampling: 1 frame per second, capped at 2000
            if dur > 0:
                count = int(dur) + 1
                count = max(count, self._spin_count.value())
                count = min(count, 2000)
            else:
                count = min(self._spin_count.value() * 4, 100)
            self._progress.setFormat(
                f"Smart Scan: extracting {count} frames from {int(dur//60)}m{int(dur%60)}s video  |  %v/%m")
        elif is_scene:
            count = self._spin_count.value()
            self._progress.setFormat("Scene Detection  |  %v/%m")
        else:
            count = self._spin_count.value()
            self._progress.setFormat("Extracting %v/%m")

        self._extractor = VideoFrameExtractor(
            self._video_path, mode=mode, count=count, max_width=1920,
            parent=self)
        self._extractor.progress.connect(self._on_progress)
        self._extractor.frame_extracted.connect(self._on_frame)
        self._extractor.all_done.connect(self._on_done)
        self._extractor.error_occurred.connect(self._on_error)
        self._extractor.start()

    def _on_progress(self, current: int, total: int):
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        self._lbl_placeholder.hide()

    def _on_frame(self, img, label: str):
        idx = len(self._frames)
        self._frames.append(img)
        self._labels.append(label)

        pm = QPixmap.fromImage(img)
        thumb = _FrameThumb(idx, pm, label)
        thumb.toggled.connect(self._update_selection_count)
        self._thumbs.append(thumb)

        row = idx // 6
        col = idx % 6
        self._grid_lo.addWidget(thumb, row, col)
        self._update_selection_count()
        # Scroll to latest
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_done(self, frames: list, labels: list):
        self._btn_extract.setEnabled(True)
        self._progress.setVisible(False)
        self._progress.setFormat("%v/%m")
        self._btn_import.setEnabled(len(frames) > 0)
        has_frames = len(frames) > 0
        self._btn_analyze.setEnabled(has_frames)
        if not has_frames:
            self._lbl_placeholder.setText("No frames extracted.")
            self._lbl_placeholder.show()
        # If Smart Pick mode, auto-run analysis then auto-pick top 50
        if has_frames and self._combo_mode.currentIndex() == 2:
            self._run_analysis(auto_pick=True)

    def _on_error(self, msg: str):
        self._btn_extract.setEnabled(True)
        self._progress.setVisible(False)
        QMessageBox.warning(self, "Video Error", msg)

    def _clear_grid(self):
        for t in self._thumbs:
            self._grid_lo.removeWidget(t)
            t.deleteLater()
        self._thumbs.clear()
        self._frames.clear()
        self._labels.clear()
        self._scores.clear()
        self._lbl_placeholder.show()
        self._btn_import.setEnabled(False)
        self._update_selection_count()

    def _update_selection_count(self):
        n = sum(1 for t in self._thumbs if t.checked)
        self._lbl_selected.setText(f"Selected: {n} frame(s)")
        self._btn_import.setEnabled(n > 0)

    def _select_all(self):
        for t in self._thumbs:
            t.set_checked(True)
        self._update_selection_count()

    def _deselect_all(self):
        for t in self._thumbs:
            t.set_checked(False)
        self._update_selection_count()


    # ── CV Analysis ──────────────────────────────────────────────────

    def _run_analysis(self, auto_pick: bool = False):
        """Run FrameAnalyzer on all extracted frames in a background thread.

        Parameters
        ----------
        auto_pick : bool
            If True (Smart Pick mode), auto-sort and auto-select top N
            frames after analysis completes.
        """
        if not self._frames:
            return
        self._auto_pick_pending = auto_pick
        self._btn_analyze.setEnabled(False)
        self._btn_extract.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._progress.setMaximum(len(self._frames))
        self._progress.setFormat("Analyzing %v/%m  |  CV scoring...")

        self._analysis_worker = FrameAnalysisWorker(self._frames, parent=self)
        self._analysis_worker.frame_scored.connect(self._on_frame_scored)
        self._analysis_worker.all_scored.connect(self._on_all_scored)
        self._analysis_worker.start()

    def _on_frame_scored(self, idx: int, score: dict):
        self._progress.setValue(idx + 1)
        self._scores.append(score)
        if idx < len(self._thumbs):
            self._thumbs[idx].set_score(score)
            self._thumbs[idx].setToolTip(self._thumbs[idx].build_tooltip())

    def _on_all_scored(self, scores: list):
        self._btn_analyze.setEnabled(True)
        self._btn_extract.setEnabled(True)
        self._progress.setVisible(False)
        self._progress.setFormat("%v/%m")
        self._btn_auto.setEnabled(len(scores) > 0)
        self._btn_sort.setEnabled(len(scores) > 0)
        self._btn_dedup.setEnabled(len(scores) > 0)
        # Show summary
        if scores:
            avg = sum(s.get("overall", 0) for s in scores) / len(scores)
            best_i = max(range(len(scores)), key=lambda i: scores[i].get("overall", 0))
            best_label = self._labels[best_i] if best_i < len(self._labels) else "?"
            top_n = self._spin_top.value()
            self._lbl_info.setText(
                self._lbl_info.text() +
                f"\n  CV Analysis: {len(scores)} frames scored  |  "
                f"Avg: {int(avg * 100)}%  |  "
                f"Best: #{best_i + 1} at {best_label} "
                f"({int(scores[best_i].get('overall', 0) * 100)}%)")
            # Auto-pick if Smart Pick mode
            if getattr(self, '_auto_pick_pending', False):
                self._auto_pick_pending = False
                self._sort_by_score()
                self._auto_select_top()
                self._update_selection_count()

    def _sort_by_score(self):
        """Reorder the frame grid from highest to lowest CV score."""
        if not self._scores or not self._thumbs:
            return
        # Pair thumbs with their scores and sort descending
        indexed = [(t, self._scores[t.index]) for t in self._thumbs
                    if t.index < len(self._scores)]
        indexed.sort(key=lambda x: x[1].get("overall", 0), reverse=True)
        # Remove all from layout and re-add in sorted order
        for t in self._thumbs:
            self._grid_lo.removeWidget(t)
        for new_idx, (thumb, sc) in enumerate(indexed):
            row, col = new_idx // 6, new_idx % 6
            self._grid_lo.addWidget(thumb, row, col)
        self.status_message = "Sorted by CV score (highest first)"

    def _auto_select_top(self):
        """Select only the top N highest-scoring frames."""
        if not self._scores or not self._thumbs:
            return
        n = self._spin_top.value()
        # Score each thumb
        scored = [(t, self._scores[t.index].get("overall", 0))
                  for t in self._thumbs if t.index < len(self._scores)]
        scored.sort(key=lambda x: x[1], reverse=True)
        # Deselect all, then select top N
        for t in self._thumbs:
            t.set_checked(False)
        for thumb, _ in scored[:n]:
            thumb.set_checked(True)
        self._update_selection_count()

    def _filter_duplicates(self):
        """Remove near-duplicate frames using histogram comparison."""
        if not _CV2_OK or not self._frames or not self._scores:
            QMessageBox.information(self, "Requires OpenCV",
                                    "Temporal deduplication requires OpenCV (cv2).")
            return
        threshold = self._spin_dedup.value()
        # Build histogram for each frame
        hists = []
        for img in self._frames:
            bgr = _qimage_to_cv(img)
            if bgr is not None:
                gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                h = cv2.calcHist([gray], [0], None, [64], [0, 256]).flatten()
                cv2.normalize(h, h)
                hists.append(h)
            else:
                hists.append(None)

        # Compare each frame to the last kept frame
        keep_indices = []
        last_kept_hist = None
        for i, hist in enumerate(hists):
            if hist is None:
                keep_indices.append(i)
                continue
            if last_kept_hist is None:
                keep_indices.append(i)
                last_kept_hist = hist
                continue
            dist = cv2.compareHist(last_kept_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
            if dist >= (1.0 - threshold):
                keep_indices.append(i)
                last_kept_hist = hist
            # else: skip (duplicate)

        # Deselect duplicates, select kept
        keep_set = set(keep_indices)
        removed = len(self._thumbs) - len(keep_set)
        for t in self._thumbs:
            t.set_checked(t.index in keep_set)
        self._update_selection_count()
        self._lbl_dedup_info.setText(f"Kept {len(keep_set)}, removed {removed} duplicates")
        self.status_message = f"Dedup: kept {len(keep_set)}, removed {removed}"

    def _import_selected(self):
        images, labels = [], []
        for t in self._thumbs:
            if t.checked and t.index < len(self._frames):
                images.append(self._frames[t.index])
                labels.append(self._labels[t.index])
        if images:
            self.frames_imported.emit(images, labels)
            self.accept()

    def closeEvent(self, event):
        if self._extractor and self._extractor.isRunning():
            self._extractor.abort()
            self._extractor.wait(3000)
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._analysis_worker.abort()
            self._analysis_worker.wait(5000)
        super().closeEvent(event)

# ══════════════════════════════════════════════════════════════════════════════
# Main Window
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Streaming Thumbnail Picker")
        self.resize(1300, 800)

        self._badge = BadgeState()
        self._undo = UndoStack()
        self._text_overlays: List[TextOverlayState] = []
        self._fit_mode: str = "fit"

        self._build_ui()
        self._build_menus()
        self._build_shortcuts()
        self._connect()
        self._undo.push(self._badge.to_dict())  # initial state
        self._refresh()
        self.statusBar().showMessage("Ready  |  Open images to get started")

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Create the strip early so toolbar buttons can reference it
        self._strip = ThumbnailStrip()

        # ── Top toolbar ──
        tb = QHBoxLayout()
        tb.setContentsMargins(10, 8, 10, 6)
        tb.setSpacing(4)

        # File group
        btn_open = QPushButton("  Open Images  ")
        btn_open.setToolTip("Open image files (Ctrl+O)")
        btn_open.clicked.connect(self._on_open)
        tb.addWidget(btn_open)

        btn_paste = QPushButton("  Paste  ")
        btn_paste.setToolTip("Paste from clipboard (Ctrl+V)")
        btn_paste.clicked.connect(self._on_paste)
        tb.addWidget(btn_paste)

        btn_video = QPushButton("  Open Video  ")
        btn_video.setObjectName("btnAccent")
        btn_video.setToolTip("Analyze video and extract frames (Ctrl+Shift+O)")
        btn_video.clicked.connect(self._on_open_video)
        tb.addWidget(btn_video)

        sep1 = QFrame()
        sep1.setObjectName("Separator")
        sep1.setFixedWidth(1)
        sep1.setFixedHeight(28)
        tb.addWidget(sep1)

        # Navigation group
        btn_first = QPushButton(" |< ")
        btn_first.setFixedWidth(38)
        btn_first.setToolTip("First image (Home)")
        btn_first.clicked.connect(self._strip.go_first)
        tb.addWidget(btn_first)

        btn_prev = QPushButton("  < Prev  ")
        btn_prev.setToolTip("Previous image (Left arrow)")
        btn_prev.clicked.connect(self._strip.go_prev)
        tb.addWidget(btn_prev)

        self._lbl_counter = QLabel("")
        self._lbl_counter.setObjectName("Counter")
        self._lbl_counter.setMinimumWidth(60)
        self._lbl_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb.addWidget(self._lbl_counter)

        btn_next = QPushButton("  Next >  ")
        btn_next.setToolTip("Next image (Right arrow)")
        btn_next.clicked.connect(self._strip.go_next)
        tb.addWidget(btn_next)

        btn_last = QPushButton(" >| ")
        btn_last.setFixedWidth(38)
        btn_last.setToolTip("Last image (End)")
        btn_last.clicked.connect(self._strip.go_last)
        tb.addWidget(btn_last)

        sep2 = QFrame()
        sep2.setObjectName("Separator")
        sep2.setFixedWidth(1)
        sep2.setFixedHeight(28)
        tb.addWidget(sep2)

        # Actions group
        btn_undo = QPushButton("  Undo  ")
        btn_undo.setToolTip("Undo (Ctrl+Z)")
        btn_undo.clicked.connect(self._on_undo)
        tb.addWidget(btn_undo)

        btn_redo = QPushButton("  Redo  ")
        btn_redo.setToolTip("Redo (Ctrl+Y)")
        btn_redo.clicked.connect(self._on_redo)
        tb.addWidget(btn_redo)

        sep3 = QFrame()
        sep3.setObjectName("Separator")
        sep3.setFixedWidth(1)
        sep3.setFixedHeight(28)
        tb.addWidget(sep3)

        # Preview mode
        self._btn_fit = QPushButton(" Fit ")
        self._btn_fit.setCheckable(True)
        self._btn_fit.setChecked(True)
        self._btn_fit.setToolTip("Fit to window")
        self._btn_fit.clicked.connect(lambda: self._set_fit("fit"))
        tb.addWidget(self._btn_fit)

        btn_11 = QPushButton(" 1:1 ")
        btn_11.setCheckable(True)
        btn_11.setToolTip("Actual pixel size")
        btn_11.clicked.connect(lambda: self._set_fit("1:1"))
        tb.addWidget(btn_11)
        self._fit_btns = [self._btn_fit, btn_11]
        btn_11.setObjectName("")

        tb.addStretch()

        # Export group
        btn_copy = QPushButton("  Copy  ")
        btn_copy.setToolTip("Copy composite to clipboard (Ctrl+C)")
        btn_copy.clicked.connect(self._on_copy)
        tb.addWidget(btn_copy)

        btn_save = QPushButton("  Save Thumbnail  ")
        btn_save.setObjectName("btnPrimary")
        btn_save.setToolTip("Save current thumbnail with overlay (Ctrl+S)")
        btn_save.clicked.connect(self._on_save)
        tb.addWidget(btn_save)

        btn_saveall = QPushButton("  Save All  ")
        btn_saveall.setObjectName("btnAccent")
        btn_saveall.setToolTip("Batch-export all thumbnails with overlay")
        btn_saveall.clicked.connect(self._on_save_all)
        tb.addWidget(btn_saveall)

        root.addLayout(tb)

        # ── Separator ──
        sep_main = QFrame()
        sep_main.setObjectName("Separator")
        sep_main.setFixedHeight(1)
        root.addWidget(sep_main)

        # ── Middle: preview + controls ──
        mid = QHBoxLayout()
        mid.setSpacing(0)

        self._canvas = PreviewCanvas()
        mid.addWidget(self._canvas, stretch=1)

        # Right panel: tabbed Badge + Text Overlays
        self._tab_widget = QTabWidget()
        self._tab_widget.setMaximumWidth(340)
        self._tab_widget.setMinimumWidth(270)

        self._controls = ControlPanel(self._badge, self._undo)
        self._tab_widget.addTab(self._controls, "Badge")

        self._text_panel = TextOverlayPanel(self._text_overlays, self._undo)
        self._text_panel.overlay_changed.connect(self._refresh)
        self._tab_widget.addTab(self._text_panel, "Text")

        mid.addWidget(self._tab_widget)
        root.addLayout(mid, stretch=1)

        # ── Bottom strip ──
        strip_row = QHBoxLayout()
        strip_row.setContentsMargins(10, 2, 10, 8)
        strip_row.setSpacing(6)

        btn_add = QPushButton("+")
        btn_add.setFixedWidth(32)
        btn_add.setFixedHeight(32)
        btn_add.setToolTip("Add more images")
        btn_add.clicked.connect(self._on_open)
        strip_row.addWidget(btn_add)

        strip_row.addWidget(self._strip, stretch=1)

        btn_remove = QPushButton("Remove")
        btn_remove.setFixedHeight(32)
        btn_remove.setToolTip("Remove current (Delete)")
        btn_remove.clicked.connect(self._strip.remove_current)
        strip_row.addWidget(btn_remove)

        btn_clear = QPushButton("Clear All")
        btn_clear.setFixedHeight(32)
        btn_clear.setToolTip("Remove all images")
        btn_clear.clicked.connect(self._on_clear)
        strip_row.addWidget(btn_clear)

        root.addLayout(strip_row)

    def _build_menus(self) -> None:
        mb = self.menuBar()

        file_m = mb.addMenu("&File")
        self._add_action(file_m, "&Open Images...", "Ctrl+O", self._on_open)
        self._add_action(file_m, "&Paste from Clipboard", "Ctrl+V", self._on_paste)
        self._add_action(file_m, "Open &Video...", "Ctrl+Shift+O", self._on_open_video)
        file_m.addSeparator()
        self._add_action(file_m, "&Save Thumbnail...", "Ctrl+S", self._on_save)
        self._add_action(file_m, "Save &All...", "Ctrl+Shift+S", self._on_save_all)
        self._add_action(file_m, "&Copy to Clipboard", "Ctrl+C", self._on_copy)
        file_m.addSeparator()
        self._add_action(file_m, "E&xit", "Ctrl+Q", self.close)

        edit_m = mb.addMenu("&Edit")
        self._add_action(edit_m, "&Undo", "Ctrl+Z", self._on_undo)
        self._add_action(edit_m, "&Redo", "Ctrl+Y", self._on_redo)
        edit_m.addSeparator()
        self._add_action(edit_m, "Reset Badge", "", self._on_reset_badge)

        view_m = mb.addMenu("&View")
        self._add_action(view_m, "Fit to Window", "", lambda: self._set_fit("fit"))
        self._add_action(view_m, "Actual Size (1:1)", "", lambda: self._set_fit("1:1"))
        self._add_action(view_m, "Zoom In", "Ctrl+=", self._canvas.zoom_in)
        self._add_action(view_m, "Zoom Out", "Ctrl+-", self._canvas.zoom_out)
        self._add_action(view_m, "Reset Zoom", "Ctrl+0", self._canvas.zoom_reset)

    @staticmethod
    def _add_action(menu, text, shortcut, callback):
        a = QAction(text, menu)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(callback)
        menu.addAction(a)

    def _build_shortcuts(self) -> None:
        # Arrow keys
        s_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        s_left.activated.connect(self._strip.go_prev)
        s_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        s_right.activated.connect(self._strip.go_next)
        s_home = QShortcut(QKeySequence(Qt.Key.Key_Home), self)
        s_home.activated.connect(self._strip.go_first)
        s_end = QShortcut(QKeySequence(Qt.Key.Key_End), self)
        s_end.activated.connect(self._strip.go_last)
        s_del = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        s_del.activated.connect(self._strip.remove_current)
        s_vid = QShortcut(QKeySequence("Ctrl+Shift+O"), self)
        s_vid.activated.connect(self._on_open_video)

    def _connect(self) -> None:
        self._strip.current_changed.connect(self._on_index_changed)
        self._controls.badge_changed.connect(self._refresh)
        self._canvas.badge_moved.connect(self._on_badge_dragged)
        self._canvas.context_menu_requested.connect(self._show_context_menu)
        self._canvas.images_dropped.connect(self._load_files)
        self._canvas.video_dropped.connect(self._on_video_dropped)
        self._canvas.image_pasted.connect(self._on_paste)

    # ── Core refresh ─────────────────────────────────────────────────

    def _on_index_changed(self, idx: int) -> None:
        self._update_counter()
        self._refresh()

    def _update_counter(self) -> None:
        i, n = self._strip.index, self._strip.count
        path = self._strip.current_path()
        name = Path(path).name if path else "—"
        if n > 0:
            info = f"{i + 1} / {n}"
            if name != "—":
                info += f"   {name}"
            self._lbl_counter.setText(info)
        else:
            self._lbl_counter.setText("")

    def _refresh(self) -> None:
        img = self._strip.current_image()
        if img is None or img.isNull():
            self._canvas.set_composite(QPixmap())
            return
        preset = self._controls.combo_out.currentText()
        target = PRESETS.get(preset)
        base = fit_crop(img, target) if target else QImage(img)
        composite = render_badge(base, self._badge)
        # Apply text overlays
        visible_overlays = [o for o in self._text_overlays if o.visible]
        if visible_overlays:
            composite = render_text_overlays(composite, visible_overlays)
        self._canvas.set_composite(QPixmap.fromImage(composite))
        # Update status
        path = self._strip.current_path()
        name = Path(path).name if path else "—"
        self.statusBar().showMessage(
            f"{name}   |   {base.width()} x {base.height()} px   |   "
            f"Zoom {int(self._canvas.zoom * 100)}%   |   "
            f"Undo: {len(self._undo._undo) - 1}  Redo: {len(self._undo._redo)}"
        )
        self._update_counter()

    # ── Badge dragging on canvas ─────────────────────────────────────

    def _on_badge_dragged(self, nx: float, ny: float) -> None:
        self._badge.position = "Custom"
        self._badge.custom_x = nx
        self._badge.custom_y = ny
        self._controls.combo_pos.blockSignals(True)
        self._controls.combo_pos.setCurrentText("Custom")
        self._controls.combo_pos.blockSignals(False)
        self._controls.lbl_drag_hint.setVisible(True)
        self._refresh()

    # ── Fit mode ─────────────────────────────────────────────────────

    def _set_fit(self, mode: str) -> None:
        self._fit_mode = mode
        self._canvas.set_fit_mode(mode)
        for b in self._fit_btns:
            b.setChecked((mode == "fit" and b is self._btn_fit) or
                         (b.text().strip() == "1:1" and mode == "1:1"))
        self.statusBar().showMessage(f"Preview mode: {mode}")

    # ── Context menu ────────────────────────────────────────────────

    def _show_context_menu(self, pos: QPointF) -> None:
        menu = QMenu(self)
        menu.addAction("Fit to Window", lambda: self._set_fit("fit"))
        menu.addAction("Actual Size (1:1)", lambda: self._set_fit("1:1"))
        menu.addSeparator()
        menu.addAction("Zoom In", self._canvas.zoom_in)
        menu.addAction("Zoom Out", self._canvas.zoom_out)
        menu.addAction("Reset Zoom", self._canvas.zoom_reset)
        menu.addSeparator()
        menu.addAction("Copy to Clipboard", self._on_copy)
        menu.addAction("Save Thumbnail...", self._on_save)
        menu.addSeparator()
        menu.addAction("Reset Badge", self._on_reset_badge)
        menu.exec(self._canvas.mapToGlobal(pos.toPoint()))

    # ── File I/O ─────────────────────────────────────────────────────

    def _on_open(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open Images", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;All Files (*)",
        )
        if paths:
            self._load_files(paths)

    def _load_files(self, paths: List[str]) -> None:
        images, valid_paths = [], []
        for p in paths:
            img = load_image(p)
            if img:
                images.append(img)
                valid_paths.append(p)
        if not images:
            return
        if self._strip.count == 0:
            self._strip.load_images(images, valid_paths)
        else:
            self._strip.append_images(images, valid_paths)
        self.statusBar().showMessage(f"Loaded {len(images)} image(s)  |  Arrow keys to cycle")

    def _on_open_video(self) -> None:
        """Open the Video Import Dialog, extract frames, and load selected ones."""
        dlg = VideoImportDialog(self)
        dlg.frames_imported.connect(self._on_video_frames_imported)
        dlg.exec()

    def _on_video_frames_imported(self, images: list, labels: list) -> None:
        """Handle frames imported from the Video Import Dialog."""
        if not images:
            return
        if self._strip.count == 0:
            self._strip.load_images(images, labels)
        else:
            self._strip.append_images(images, labels)
        self.statusBar().showMessage(
            f"Imported {len(images)} video frame(s)  |  Arrow keys to cycle")

    def _on_video_dropped(self, video_paths: list) -> None:
        """Handle video files dropped onto the canvas."""
        if not video_paths:
            return
        path = video_paths[0]
        dlg = VideoImportDialog(self)
        dlg.frames_imported.connect(self._on_video_frames_imported)
        # Pre-load the dropped video info
        dlg._video_path = path
        dlg._lbl_file.setText(Path(path).name)
        dlg._lbl_file.setToolTip(path)
        info = VideoFrameExtractor.get_video_info(path)
        if "error" not in info:
            dlg._btn_extract.setEnabled(True)
            dlg._set_info_text(info)
        else:
            dlg._lbl_info.setText(f"Error: {info['error']}")
        dlg.exec()

    def _on_paste(self) -> None:
        cb = QApplication.clipboard()
        if not cb:
            return
        img = cb.image()
        if img.isNull():
            pm = cb.pixmap()
            if not pm.isNull():
                img = pm.toImage()
        if not img.isNull():
            self._strip.append_images([img])
            self.statusBar().showMessage("Pasted image added to strip")
        else:
            self.statusBar().showMessage("No image on clipboard")

    def _on_save(self) -> None:
        img = self._strip.current_image()
        if not img or img.isNull():
            QMessageBox.information(self, "No Image", "Load an image first.")
            return
        preset = self._controls.combo_out.currentText()
        target = PRESETS.get(preset)
        base = fit_crop(img, target) if target else QImage(img)
        composite = render_badge(base, self._badge)
        visible_overlays = [o for o in self._text_overlays if o.visible]
        if visible_overlays:
            composite = render_text_overlays(composite, visible_overlays)
        default = f"live_{self._badge.text.lower()}.jpg"
        path, _ = QFileDialog.getSaveFileName(self, "Save Thumbnail", default,
                                               "JPEG (*.jpg *.jpeg);;PNG (*.png);;WebP (*.webp)")
        if path and composite.save(path, quality=95):
            self.statusBar().showMessage(f"Saved: {Path(path).name}")

    def _on_save_all(self) -> None:
        if self._strip.count == 0:
            QMessageBox.information(self, "No Images", "Load images first.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if not folder:
            return
        preset = self._controls.combo_out.currentText()
        target = PRESETS.get(preset)
        saved = 0
        for i, img in enumerate(self._strip._full):
            if img.isNull():
                continue
            base = fit_crop(img, target) if target else QImage(img)
            composite = render_badge(base, self._badge)
            visible_overlays = [o for o in self._text_overlays if o.visible]
            if visible_overlays:
                composite = render_text_overlays(composite, visible_overlays)
            name = f"live_{i + 1:03d}.jpg"
            path = str(Path(folder) / name)
            if composite.save(path, quality=95):
                saved += 1
        self.statusBar().showMessage(f"Saved {saved}/{self._strip.count} thumbnails to {folder}")

    def _on_copy(self) -> None:
        img = self._strip.current_image()
        if not img or img.isNull():
            return
        preset = self._controls.combo_out.currentText()
        target = PRESETS.get(preset)
        base = fit_crop(img, target) if target else QImage(img)
        composite = render_badge(base, self._badge)
        visible_overlays = [o for o in self._text_overlays if o.visible]
        if visible_overlays:
            composite = render_text_overlays(composite, visible_overlays)
        cb = QApplication.clipboard()
        if cb:
            cb.setPixmap(QPixmap.fromImage(composite))
            self.statusBar().showMessage("Copied to clipboard")

    def _on_clear(self) -> None:
        if self._strip.count == 0:
            return
        if QMessageBox.question(self, "Clear All",
                                f"Remove all {self._strip.count} images?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                ) == QMessageBox.StandardButton.Yes:
            self._strip.clear()
            self.statusBar().showMessage("All images cleared")

    # ── Undo / Redo ──────────────────────────────────────────────────

    def _on_undo(self) -> None:
        state = self._undo.undo()
        if state:
            self._controls.load_state(state)
            self._refresh()
            self.statusBar().showMessage("Undo")

    def _on_redo(self) -> None:
        state = self._undo.redo()
        if state:
            self._controls.load_state(state)
            self._refresh()
            self.statusBar().showMessage("Redo")

    def _on_reset_badge(self) -> None:
        self._badge.apply_style("Classic Red")
        self._badge.position = "Top-Right"
        self._badge.opacity = 1.0
        self._controls.load_state(self._badge.to_dict())
        self._refresh()
        self.statusBar().showMessage("Badge reset")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Streaming Thumbnail Picker")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()