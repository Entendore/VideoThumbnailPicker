#!/usr/bin/env python3
"""
Video Thumbnail Picker  v8.0  (PySide6 Professional)
=====================================================
A professional GUI tool to automatically select the best thumbnail from a video.
New in v8.0:
  - Analysis Dashboard: RGB Histogram & Score Breakdown.
  - Top 3 Comparison Mode.
  - Visual Overlays (Rule of Thirds, Face Detection).
  - Batch Export for starred images.
  - Performance optimizations.
"""

from __future__ import annotations

import sys, math, os, subprocess, logging, traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import cv2
import numpy as np
from PIL import Image

from PySide6.QtCore import (
    Qt, Signal, QThread, QSize, QRect, QRectF, QPoint, QSettings,
    QPropertyAnimation, QEasingCurve, Slot, QUrl, QTimer
)
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QPen, QKeySequence,
    QShortcut, QWheelEvent, QMouseEvent, QPainterPath, QBrush, QIcon, QAction
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QProgressBar, QScrollArea,
    QFileDialog, QMessageBox, QSplitter, QStatusBar, QFrame, QGroupBox,
    QToolBar, QGraphicsView, QGraphicsScene, QGraphicsItem,
    QSlider, QCheckBox, QMenu, QGridLayout, QSizePolicy,
    QGraphicsOpacityEffect, QDialog, QLineEdit, QStackedWidget, QTabWidget
)

# ────────────────────────────────────────────────────────────────────────────
# Constants & Theme
# ────────────────────────────────────────────────────────────────────────────

PRESETS = {
    "Original": None,
    "YouTube (1280×720)": (1280, 720),
    "YouTube (1920×1080)": (1920, 1080),
    "Instagram Square": (1080, 1080),
    "Instagram Portrait": (1080, 1350),
    "Twitter Header": (1500, 500),
    "TikTok": (1080, 1920),
}

# Algorithm Profiles
ALGORITHM_PROFILES = {
    "General (Balanced)": {
        "sharpness": 0.14, "colorfulness": 0.10, "contrast": 0.08, "brightness": 0.06,
        "entropy": 0.08, "composition": 0.10, "skin_tone": 0.05, "faces": 0.12,
        "motion": 0.05, "exposure_quality": 0.06, "dynamic_range": 0.04, 
        "visual_complexity": 0.04, "color_harmony": 0.04, "center_weight": 0.04,
    },
    "Face Focus (Portrait)": {
        "sharpness": 0.20, "faces": 0.40, "skin_tone": 0.10, "center_weight": 0.15,
        "brightness": 0.05, "exposure_quality": 0.05, "composition": 0.05,
        "contrast": 0.00, "colorfulness": 0.00, "entropy": 0.00,
        "motion": 0.00, "dynamic_range": 0.00, "visual_complexity": 0.00, "color_harmony": 0.00,
    },
    "Scenery (Landscape)": {
        "composition": 0.25, "color_harmony": 0.20, "dynamic_range": 0.15,
        "sharpness": 0.15, "visual_complexity": 0.10, "exposure_quality": 0.05,
        "contrast": 0.10, "faces": 0.00, "skin_tone": 0.00, "motion": 0.00,
        "brightness": 0.00, "center_weight": 0.00, "colorfulness": 0.00, "entropy": 0.00,
    },
    "Action (Motion)": {
        "motion": 0.40, "sharpness": 0.20, "contrast": 0.15, "dynamic_range": 0.10,
        "visual_complexity": 0.10, "faces": 0.05, "brightness": 0.00, "colorfulness": 0.00,
        "entropy": 0.00, "composition": 0.00, "skin_tone": 0.00, "exposure_quality": 0.00,
        "color_harmony": 0.00, "center_weight": 0.00,
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
QStatusBar {{ background:{C_SURFACE}; color:{C_SUBTEXT}; }}
QSlider::groove:horizontal {{ height:4px; background:{C_OVERLAY}; border-radius:2px; }}
QSlider::handle:horizontal {{ background:{C_BLUE}; width:14px; height:14px; margin:-5px 0; border-radius:7px; }}
QCheckBox::indicator {{ width:14px; height:14px; border-radius:3px; border:1px solid {C_OVERLAY}; background:{C_CARD}; }}
QCheckBox::indicator:checked {{ background:{C_BLUE}; border-color:{C_BLUE}; }}
QProgressBar {{ border:none; border-radius:3px; background:{C_OVERLAY}; text-align:center; color:{C_BG}; font-weight:bold; }}
QProgressBar::chunk {{ background:{C_TEAL}; border-radius:3px; }}
QLabel#LblTitle {{ font-size:14px; font-weight:bold; color:{C_LAVENDER}; }}
QFrame#Card {{ background:{C_CARD}; border-radius:6px; }}
QTabWidget::pane {{ border: 1px solid {C_OVERLAY}; border-radius:6px; background: {C_SURFACE}; }}
QTabBar::tab {{ background: {C_CARD}; color: {C_SUBTEXT}; padding: 8px 16px; border-top-left-radius: 4px; border-top-right-radius: 4px; }}
QTabBar::tab:selected {{ background: {C_SURFACE}; color: {C_TEXT}; font-weight: bold; }}
"""

# ────────────────────────────────────────────────────────────────────────────
# Scoring Logic
# ────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger("thumbnail_picker")

_face_cascade = _profile_cascade = None

def _get_cascades():
    global _face_cascade, _profile_cascade
    if _face_cascade is None:
        try:
            _face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            _profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
        except Exception: pass
    return _face_cascade, _profile_cascade

def prefilter_frame(bgr) -> bool:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    m = np.mean(gray)
    if m < 20 or m > 240: return False
    if np.var(cv2.Laplacian(gray, cv2.CV_64F)) < 20: return False # Blur check
    return True

def score_faces(bgr):
    fc, pc = _get_cascades()
    if fc is None: return 0.0, []
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = fc.detectMultiScale(g, 1.2, 5, minSize=(40,40))
    if len(faces) == 0:
        faces = pc.detectMultiScale(g, 1.2, 5, minSize=(40,40))
    if len(faces) == 0: return 0.0, []
    
    H, W = bgr.shape[:2]
    largest = max(faces, key=lambda r: r[2]*r[3])
    fx = (largest[0] + largest[2]/2) / W
    fy = (largest[1] + largest[3]/2) / H
    dist = math.sqrt((fx-0.5)**2 + (fy-0.5)**2)
    center_bonus = max(0, 0.4 * (1 - dist*2))
    
    area_ratio = (largest[2]*largest[3]) / (H*W)
    size_bonus = 0.2 if 0.05 < area_ratio < 0.5 else 0.0
    
    return min(0.4 + center_bonus + size_bonus, 1.0), faces

def score_sharpness(gray): return min(np.var(cv2.Laplacian(gray, cv2.CV_64F)) / 400, 1)
def score_contrast(gray): return min(np.std(gray) / 60, 1)
def score_brightness(gray): return float(np.exp(-0.5 * ((np.mean(gray) - 128) / 60.0) ** 2))

def score_composition(bgr):
    H, W = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150) / 255.0
    wt = np.zeros_like(edges)
    for f in (1/3, 2/3):
        y, x = int(H*f), int(W*f)
        wt[max(0,y-10):min(H,y+10), :] += 0.5
        wt[:, max(0,x-10):min(W,x+10)] += 0.5
    return min(np.mean(edges * wt) * 20, 1.0)

def score_motion_flow(prev, curr):
    if prev is None: return 0.0
    try:
        flow = cv2.calcOpticalFlowFarneback(cv2.resize(prev, (160,90)), cv2.resize(curr, (160,90)), None, 0.5, 3, 15, 3, 5, 1.2, 0)
        mag, _ = cv2.cartToPolar(flow[...,0], flow[...,1])
        return min(np.mean(mag) / 4.0, 1.0)
    except: return 0.0

def score_dynamic_range(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    p_lo, p_hi = np.percentile(g, [5, 95])
    return min((p_hi - p_lo) / 255.0, 1.0)

def score_colorfulness(bgr):
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    return min(np.std(lab[:,:,1:]) / 50.0, 1.0)

SCORERS = {
    "sharpness": lambda f, p: score_sharpness(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)),
    "faces": lambda f, p: score_faces(f)[0], # Wrapper to return only score
    "contrast": lambda f, p: score_contrast(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)),
    "brightness": lambda f, p: score_brightness(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)),
    "composition": lambda f, p: score_composition(f),
    "motion": lambda f, p: score_motion_flow(p, cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)),
    "dynamic_range": lambda f, p: score_dynamic_range(f),
    "colorfulness": lambda f, p: score_colorfulness(f),
    # Defaults
    "exposure_quality": lambda f, p: 0.5,
    "visual_complexity": lambda f, p: 0.5,
    "color_harmony": lambda f, p: 0.5,
    "center_weight": lambda f, p: 0.5,
    "skin_tone": lambda f, p: 0.5,
    "entropy": lambda f, p: 0.5
}

def compute_score(frame, prev_gray, weights):
    scores = {n: s(frame, prev_gray) for n, s in SCORERS.items()}
    total = sum(scores[k] * w for k, w in weights.items())
    return total, scores

def _color_hist(bgr):
    h = cv2.calcHist([cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)], [0,1], None, [20,10], [0,180,0,256]).flatten()
    return h / (h.sum() + 1e-8)

def filter_similar(cands):
    if len(cands) <= 1: return cands
    kept = [cands[0]]
    kept_h = [_color_hist(cands[0].frame_bgr)]
    for c in cands[1:]:
        h = _color_hist(c.frame_bgr)
        if all(cv2.compareHist(h, kh, cv2.HISTCMP_CORREL) < 0.85 for kh in kept_h):
            kept.append(c); kept_h.append(h)
    return kept

# ────────────────────────────────────────────────────────────────────────────
# Data Classes
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class Candidate:
    frame_bgr: np.ndarray
    timestamp: float
    total_score: float
    breakdown: dict
    faces: List[Tuple[int, int, int, int]] = field(default_factory=list)
    starred: bool = False

# ────────────────────────────────────────────────────────────────────────────
# Backend Thread
# ────────────────────────────────────────────────────────────────────────────

class AnalysisThread(QThread):
    progress = Signal(int, int)
    finished_ok = Signal(list, dict)
    finished_err = Signal(str)
    candidate_ready = Signal(object, int, int)
    filmstrip_ready = Signal(list) 

    def __init__(self, path, n_samples, weights, n_cands, use_scene):
        super().__init__()
        self.path = path
        self.n_samples = n_samples
        self.weights = weights
        self.n_cands = n_cands
        self.use_scene = use_scene
        self._abort = False

    def run(self):
        cap = cv2.VideoCapture(self.path)
        if not cap.isOpened(): self.finished_err.emit("Cannot open video"); return
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            dur = total_frames / fps
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # 1. Generate Filmstrip
            filmstrip = []
            n_strip = max(20, int(dur / 2))
            for i in range(n_strip):
                t = dur * (i + 0.5) / n_strip
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ret, f = cap.read()
                if ret: filmstrip.append((t, f.copy()))
            self.filmstrip_ready.emit(filmstrip)
            
            # 2. Scene Detection or Uniform Sampling
            sample_times = []
            if self.use_scene:
                prev_gray = None
                scenes = []
                for i in range(0, total_frames, int(fps)): # Sample 1fps
                    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, f = cap.read()
                    if not ret: continue
                    gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
                    if prev_gray is not None:
                        diff = np.mean(cv2.absdiff(gray, prev_gray))
                        if diff > 25: scenes.append(i/fps)
                    prev_gray = gray
                sample_times = scenes[:self.n_samples]
            
            if not sample_times:
                sample_times = np.linspace(0.05, 0.95, self.n_samples) * dur

            # 3. Scoring
            cands = []
            prev = None
            for i, t in enumerate(sample_times):
                if self._abort: return
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ret, frame = cap.read()
                if not ret: continue
                
                if not prefilter_frame(frame): continue
                
                # Score
                scores = {n: s(frame, prev) for n, s in SCORERS.items()}
                total = sum(scores[k] * w for k, w in self.weights.items())
                
                # Get Face rects for overlay
                _, faces = score_faces(frame)
                
                prev = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                c = Candidate(frame, float(t), total, scores, faces=faces)
                cands.append(c)
                self.candidate_ready.emit(c, i+1, len(sample_times))
                self.progress.emit(i+1, len(sample_times))
            
            cands.sort(key=lambda c: c.total_score, reverse=True)
            cands = filter_similar(cands)[:self.n_cands]
            
            info = dict(path=self.path, duration=dur, fps=fps, width=w, height=h)
            self.finished_ok.emit(cands, info)
        except Exception as e: 
            traceback.print_exc()
            self.finished_err.emit(str(e))
        finally: cap.release()

    def abort(self): self._abort = True

# ────────────────────────────────────────────────────────────────────────────
# UI Components
# ────────────────────────────────────────────────────────────────────────────

def _fmt_time(t):
    m, s = divmod(int(t), 60)
    ms = int((t%1)*1000)
    return f"{m:02d}:{s:02d}.{ms:03d}"

class ZoomablePreview(QGraphicsView):
    def __init__(self):
        super().__init__()
        self._zoom = 1.0
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._pixmap_item = None
        self.setStyleSheet("background: transparent;")
        
        self.show_grid = False
        self.show_faces = False
        self._current_cand = None

    def set_pixmap(self, pm: QPixmap, cand: Candidate = None):
        self.scene().clear()
        self._pixmap_item = self.scene().addPixmap(pm)
        self.scene().setSceneRect(QRectF(pm.rect()))
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._current_cand = cand
        self.viewport().update()

    def drawForeground(self, painter, rect):
        if not self._pixmap_item: return
        
        # Transform painter to match image coordinates
        painter.save()
        painter.setTransform(self.viewportTransform().inverted()[0]) # Map screen to scene
        
        pen = QPen(QColor(255, 255, 255, 200), 2)
        pen.setCosmetic(True) # constant width regardless of zoom
        painter.setPen(pen)

        if self.show_grid:
            # Rule of Thirds
            w = self._pixmap_item.pixmap().width()
            h = self._pixmap_item.pixmap().height()
            for i in range(1, 3):
                painter.drawLine(int(w * i / 3), 0, int(w * i / 3), h)
                painter.drawLine(0, int(h * i / 3), w, int(h * i / 3))

        if self.show_faces and self._current_cand:
            for (x, y, w, h) in self._current_cand.faces:
                painter.setPen(QPen(QColor(C_GREEN), 2))
                painter.drawRect(x, y, w, h)

        painter.restore()

    def zoom_in(self): self.scale(1.2, 1.2)
    def zoom_out(self): self.scale(1/1.2, 1/1.2)
    def fit(self): 
        if self._pixmap_item: self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

class HistogramWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(100)
        self.hist_data = None # tuple of (R, G, B) arrays

    def set_data(self, bgr):
        # Calculate histograms
        h = []
        for i in range(3): # B, G, R
            hist = cv2.calcHist([bgr], [i], None, [256], [0, 256])
            cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
            h.append(hist.flatten())
        self.hist_data = h
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C_CARD))
        
        if not self.hist_data:
            return

        w, h = self.width(), self.height()
        margin = 10
        gw, gh = w - 2*margin, h - 2*margin
        
        colors = [C_BLUE, C_GREEN, C_RED] # BGR -> RGB drawing
        for idx, hist in enumerate(self.hist_data):
            path = QPainterPath()
            path.moveTo(margin, h - margin)
            for i, val in enumerate(hist):
                x = margin + (i / 255.0) * gw
                y = h - margin - val * gh
                path.lineTo(x, y)
            path.lineTo(margin + gw, h - margin)
            
            color = QColor(colors[idx])
            color.setAlpha(100)
            p.fillPath(path, color)
            p.setPen(QColor(colors[idx]))
            p.drawPath(path)

class ScoreBreakdownWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.scores = {}
        self.setMinimumHeight(200)

    def set_scores(self, scores: dict):
        self.scores = scores
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C_CARD))
        
        if not self.scores:
            return

        # Filter and sort keys for consistent display
        keys = sorted([k for k in self.scores.keys() if k in CRIT_LABELS])
        
        bar_h = 16
        spacing = 4
        margin_x = 80
        w = self.width() - margin_x - 20
        
        p.setPen(QColor(C_TEXT))
        p.setFont(QFont("Segoe UI", 9))

        for i, k in enumerate(keys):
            y = 10 + i * (bar_h + spacing)
            val = self.scores.get(k, 0)
            
            # Label
            p.drawText(10, y + bar_h - 3, CRIT_LABELS.get(k, k))
            
            # Bar Background
            p.fillRect(margin_x, y, w, bar_h, QColor(C_OVERLAY))
            
            # Bar Fill
            color = C_BLUE
            if val > 0.7: color = C_GREEN
            elif val < 0.3: color = C_RED
            p.fillRect(margin_x, y, int(w * val), bar_h, QColor(color))
            
            # Value Text
            p.drawText(margin_x + w + 5, y + bar_h - 3, f"{val:.2f}")

class FilmstripTimeline(QScrollArea):
    clicked = Signal(float)
    def __init__(self):
        super().__init__()
        self.setFixedHeight(110)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"QScrollArea {{ background:{C_SURFACE}; border-radius:8px; }}")
        
        self.container = QWidget()
        self.lay = QHBoxLayout(self.container)
        self.lay.setContentsMargins(4,4,4,4)
        self.lay.setSpacing(4)
        self.setWidget(self.container)
        
    def set_frames(self, frames): # List of (timestamp, bgr)
        while self.lay.count(): self.lay.takeAt(0).widget().deleteLater()
        
        for t, bgr in frames:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            h, w = bgr.shape[:2]
            qim = QImage(rgb.data, w, h, 3*w, QImage.Format.Format_RGB888)
            pm = QPixmap.fromImage(qim)
            
            lbl = QLabel()
            lbl.setPixmap(pm.scaled(100, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            lbl.setToolTip(_fmt_time(t))
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.mousePressEvent = lambda e, ts=t: self.clicked.emit(ts)
            
            self.lay.addWidget(lbl)

class GalleryCard(QFrame):
    clicked = Signal(int)
    starred_toggled = Signal(int)
    
    def __init__(self, idx, pm, cand):
        super().__init__()
        self.idx = idx
        self.cand = cand
        self.setFixedSize(200, 130)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6,6,6,6)
        lay.setSpacing(4)
        
        self.img = QLabel()
        self.img.setPixmap(pm.scaled(190, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        lay.addWidget(self.img)
        
        row = QHBoxLayout()
        row.addWidget(QLabel(f"#{idx+1}"))
        row.addWidget(QLabel(f"{_fmt_time(cand.timestamp)}"))
        row.addStretch()
        
        self.star_btn = QPushButton("☆")
        self.star_btn.setFixedSize(24,24)
        self.star_btn.setFlat(True)
        self.star_btn.setStyleSheet("font-size:16px;")
        self.star_btn.clicked.connect(lambda: self.starred_toggled.emit(self.idx))
        row.addWidget(self.star_btn)
        lay.addLayout(row)
        
        self._refresh_style()

    def _refresh_style(self):
        border = C_GREEN if self.cand.starred else "transparent"
        bg = C_SURFACE if self.cand.starred else C_CARD
        self.setStyleSheet(f"QFrame#Card {{ background:{bg}; border:2px solid {border}; border-radius:6px; }}")
        self.star_btn.setText("★" if self.cand.starred else "☆")
        self.star_btn.setStyleSheet(f"color:{C_YELLOW};" if self.cand.starred else "")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit(self.idx)

    def _ctx_menu(self, pos):
        m = QMenu(self)
        a_save = m.addAction("Save")
        a_star = m.addAction("Unstar" if self.cand.starred else "Star")
        act = m.exec(self.mapToGlobal(pos))
        if act == a_save: self.clicked.emit(self.idx)
        elif act == a_star: self.starred_toggled.emit(self.idx)

# ────────────────────────────────────────────────────────────────────────────
# Main Window
# ────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Thumbnail Picker v8.0")
        self.resize(1500, 900)
        
        self.video_path = None
        self.candidates: List[Candidate] = []
        self.selected_idx = -1
        self._worker = None
        self._show_starred_only = False
        
        self._ui()
        self._toolbar()
        self._shortcuts()
        self.setStyleSheet(STYLESHEET)
        
    def _ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(8)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, stretch=1)

        # === LEFT PANE: Preview & Timeline ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.preview = ZoomablePreview()
        self.preview.setMinimumHeight(400)
        self.preview.setStyleSheet(f"background:{C_CARD}; border-radius:8px;")
        left_layout.addWidget(self.preview, stretch=1)

        self.filmstrip = FilmstripTimeline()
        self.filmstrip.clicked.connect(self._seek_time)
        left_layout.addWidget(self.filmstrip)

        splitter.addWidget(left_widget)

        # === RIGHT PANE: Controls & Tabs ===
        right_widget = QWidget()
        right_widget.setMaximumWidth(480)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # -- Control Bar --
        ctrl_frame = QFrame()
        ctrl_frame.setObjectName("Card")
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(12, 12, 12, 12)
        ctrl_layout.setSpacing(10)

        # Row 1: Algorithm
        row_algo = QHBoxLayout()
        row_algo.addWidget(QLabel("Algorithm:"))
        self.combo_algo = QComboBox()
        self.combo_algo.addItems(ALGORITHM_PROFILES.keys())
        self.combo_algo.currentTextChanged.connect(self._change_algo)
        row_algo.addWidget(self.combo_algo)
        ctrl_layout.addLayout(row_algo)

        # Row 2: Output
        row_out = QHBoxLayout()
        row_out.addWidget(QLabel("Output:"))
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(PRESETS.keys())
        row_out.addWidget(self.combo_preset)
        ctrl_layout.addLayout(row_out)

        # Row 3: Settings
        row_adv = QHBoxLayout()
        self.chk_scene = QCheckBox("Scene Detect")
        row_adv.addWidget(self.chk_scene)
        row_adv.addWidget(QLabel("Samples:"))
        self.spin_samples = QSpinBox(); self.spin_samples.setRange(20, 200); self.spin_samples.setValue(60)
        row_adv.addWidget(self.spin_samples)
        row_adv.addWidget(QLabel("Max:"))
        self.spin_cands = QSpinBox(); self.spin_cands.setRange(4, 50); self.spin_cands.setValue(12)
        row_adv.addWidget(self.spin_cands)
        ctrl_layout.addLayout(row_adv)
        
        # Row 4: Actions
        row_act = QHBoxLayout()
        self.btn_save = QPushButton("  Save Selected  ")
        self.btn_save.setObjectName("btnGreen")
        self.btn_save.clicked.connect(self._save)
        row_act.addWidget(self.btn_save, stretch=1)

        self.btn_batch = QPushButton("  Save Starred  ")
        self.btn_batch.clicked.connect(self._batch_save)
        row_act.addWidget(self.btn_batch, stretch=1)
        ctrl_layout.addLayout(row_act)
        
        right_layout.addWidget(ctrl_frame)

        # -- Tabs --
        self.tabs = QTabWidget()
        
        # Tab 1: Gallery
        tab_gallery = QWidget()
        t_g_lay = QVBoxLayout(tab_gallery)
        self.gallery_area = QScrollArea()
        self.gallery_area.setWidgetResizable(True)
        self.gallery_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.gallery_container = QWidget()
        self.gallery_layout = QGridLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(4, 4, 4, 4)
        self.gallery_layout.setSpacing(8)
        self.gallery_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.gallery_area.setWidget(self.gallery_container)
        t_g_lay.addWidget(self.gallery_area)
        
        self.chk_starred = QCheckBox("Show Starred Only")
        self.chk_starred.stateChanged.connect(lambda s: setattr(self, '_show_starred_only', s==Qt.CheckState.Checked.value))
        self.chk_starred.stateChanged.connect(self._refresh_gallery)
        t_g_lay.addWidget(self.chk_starred)

        self.tabs.addTab(tab_gallery, "Gallery")

        # Tab 2: Analysis
        tab_analysis = QWidget()
        t_a_lay = QVBoxLayout(tab_analysis)
        self.histogram = HistogramWidget()
        self.breakdown = ScoreBreakdownWidget()
        t_a_lay.addWidget(QLabel("RGB Histogram"))
        t_a_lay.addWidget(self.histogram)
        t_a_lay.addWidget(QLabel("Score Breakdown"))
        t_a_lay.addWidget(self.breakdown)
        self.tabs.addTab(tab_analysis, "Analysis")

        # Tab 3: Compare
        tab_compare = QWidget()
        t_c_lay = QVBoxLayout(tab_compare)
        self.compare_stack = QStackedWidget() # Placeholder logic for simple view
        self.compare_lbl = QLabel("Run analysis to compare top 3 results.")
        self.compare_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compare_lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-style:italic;")
        t_c_lay.addWidget(self.compare_lbl)
        self.tabs.addTab(tab_compare, "Compare")

        right_layout.addWidget(self.tabs, stretch=1)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        
        # Status Bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.statusBar().addPermanentWidget(self.progress)

    def _toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.btn_open = QPushButton("  Open Video")
        self.btn_open.setObjectName("btnPrimary")
        self.btn_open.clicked.connect(self._open_file)
        tb.addWidget(self.btn_open)

        self.btn_analyze = QPushButton("  Analyze")
        self.btn_analyze.clicked.connect(self._start_analysis)
        tb.addWidget(self.btn_analyze)

        tb.addSeparator()

        # Overlay toggles
        self.act_grid = QAction("Grid", self, checkable=True)
        self.act_grid.triggered.connect(self._toggle_grid)
        tb.addAction(self.act_grid)

        self.act_faces = QAction("Faces", self, checkable=True)
        self.act_faces.triggered.connect(self._toggle_faces)
        tb.addAction(self.act_faces)

        tb.addSeparator()

        zoom_in = QPushButton("+")
        zoom_in.setFixedSize(28, 28)
        zoom_in.clicked.connect(self.preview.zoom_in)
        tb.addWidget(zoom_in)
        
        zoom_out = QPushButton("-")
        zoom_out.setFixedSize(28, 28)
        zoom_out.clicked.connect(self.preview.zoom_out)
        tb.addWidget(zoom_out)
        
        fit_btn = QPushButton("Fit")
        fit_btn.setFixedSize(32, 28)
        fit_btn.clicked.connect(self.preview.fit)
        tb.addWidget(fit_btn)
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet(f"color:{C_SUBTEXT}; padding-right: 10px;")
        tb.addWidget(self.status_lbl)

    def _toggle_grid(self, state): 
        self.preview.show_grid = state
        self.preview.viewport().update()
    
    def _toggle_faces(self, state):
        self.preview.show_faces = state
        self.preview.viewport().update()

    def _shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_file)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self._nav(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self._nav(1))
        QShortcut(QKeySequence(Qt.Key.Key_F), self, self.preview.fit)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Video", "", "Video (*.mp4 *.mkv *.mov *.avi *.webm)")
        if path:
            self.video_path = path
            self.statusBar().showMessage(f"Loaded: {Path(path).name}")
            self.status_lbl.setText(Path(path).name)
            self.btn_analyze.setEnabled(True)

    def _start_analysis(self):
        if not self.video_path: return
        self.candidates.clear()
        self.selected_idx = -1
        self._refresh_gallery()
        self.progress.setVisible(True); self.progress.setValue(0)
        
        w = ALGORITHM_PROFILES[self.combo_algo.currentText()]
        self._worker = AnalysisThread(
            self.video_path, self.spin_samples.value(), 
            w, self.spin_cands.value(), self.chk_scene.isChecked()
        )
        self._worker.progress.connect(lambda c,t: self.progress.setValue(int(100*c/t)))
        self._worker.candidate_ready.connect(self._add_candidate)
        self._worker.filmstrip_ready.connect(self.filmstrip.set_frames)
        self._worker.finished_ok.connect(self._finish_analysis)
        self._worker.finished_err.connect(lambda m: QMessageBox.critical(self, "Error", m))
        self._worker.start()

    def _add_candidate(self, cand, cur, tot):
        self.candidates.append(cand)
        # Only refresh gallery once every 10 frames to save performance, or just at the end
        # But we want the first one to show up immediately
        if len(self.candidates) == 1:
            self._select(0)

    def _finish_analysis(self, cands, info):
        self.candidates = cands 
        self.progress.setVisible(False)
        self._refresh_gallery()
        self._refresh_compare_tab()
        if cands: self._select(0)
        self.statusBar().showMessage(f"Found {len(cands)} candidates.", 5000)

    def _change_algo(self, name):
        if not self.candidates: return
        w = ALGORITHM_PROFILES[name]
        for c in self.candidates:
            c.total_score = sum(c.breakdown[k]*w[k] for k in w)
        self.candidates.sort(key=lambda x: x.total_score, reverse=True)
        self._refresh_gallery()
        self._refresh_compare_tab()
        self.statusBar().showMessage(f"Resorted using {name}", 3000)

    def _refresh_gallery(self):
        while self.gallery_layout.count():
            self.gallery_layout.takeAt(0).widget().deleteLater()
            
        display = [c for c in self.candidates if not self._show_starred_only or c.starred]
        
        cols = 2 if self.gallery_container.width() > 300 else 1
        
        for i, c in enumerate(display):
            real_idx = self.candidates.index(c)
            rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
            h, w = c.frame_bgr.shape[:2]
            qim = QImage(rgb.data, w, h, 3*w, QImage.Format.Format_RGB888)
            card = GalleryCard(real_idx, QPixmap.fromImage(qim), c)
            card.clicked.connect(self._select)
            card.starred_toggled.connect(self._toggle_star)
            self.gallery_layout.addWidget(card, i // cols, i % cols)

    def _refresh_compare_tab(self):
        # Clear previous
        while self.compare_stack.count():
            self.compare_stack.removeWidget(self.compare_stack.currentWidget())
        
        if len(self.candidates) < 1: return

        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0,0,0,0)
        
        top3 = self.candidates[:3]
        
        for c in top3:
            col = QWidget()
            col_lay = QVBoxLayout(col)
            
            # Image
            rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
            h, w = c.frame_bgr.shape[:2]
            qim = QImage(rgb.data, w, h, 3*w, QImage.Format.Format_RGB888)
            pm = QPixmap.fromImage(qim)
            lbl = QLabel()
            lbl.setPixmap(pm.scaled(300, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col_lay.addWidget(lbl)
            
            # Scores summary
            txt = f"Score: {c.total_score:.2f}\n"
            txt += f"Faces: {len(c.faces)}\n"
            txt += f"Sharp: {c.breakdown.get('sharpness', 0):.2f}"
            
            lbl_t = QLabel(txt)
            lbl_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col_lay.addWidget(lbl_t)
            
            lay.addWidget(col)

        self.compare_stack.addWidget(container)
        self.compare_stack.setCurrentWidget(container)
        self.compare_lbl.setVisible(False)

    def _select(self, idx):
        self.selected_idx = idx
        c = self.candidates[idx]
        
        # Update Preview
        rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        
        preset = PRESETS[self.combo_preset.currentText()]
        if preset:
            tw, th = preset
            ratio = max(tw/pil.width, th/pil.height)
            new_size = (int(pil.width*ratio), int(pil.height*ratio))
            pil = pil.resize(new_size, Image.LANCZOS)
            
            # Center Crop
            left = (pil.width - tw)//2
            top = (pil.height - th)//2
            pil = pil.crop((left, top, left+tw, top+th))
        
        qim = QImage(pil.tobytes(), pil.width, pil.height, 3*pil.width, QImage.Format.Format_RGB888)
        self.preview.set_pixmap(QPixmap.fromImage(qim), c)
        
        # Update Analysis Tab
        self.histogram.set_data(c.frame_bgr)
        self.breakdown.set_scores(c.breakdown)
        
        self._refresh_gallery() # Highlight

    def _toggle_star(self, idx):
        self.candidates[idx].starred = not self.candidates[idx].starred
        self._refresh_gallery()

    def _nav(self, d):
        if not self.candidates: return
        self._select((self.selected_idx + d) % len(self.candidates))

    def _seek_time(self, ts):
        if not self.video_path: return
        cap = cv2.VideoCapture(self.video_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
        ret, frame = cap.read()
        cap.release()
        if ret:
            w = ALGORITHM_PROFILES[self.combo_algo.currentText()]
            # Need to re-score manually added frame
            scores = {n: s(frame, None) for n, s in SCORERS.items()}
            total = sum(scores[k] * w[k] for k in w)
            
            _, faces = score_faces(frame)
            
            cand = Candidate(frame, float(ts), total, scores, faces=faces)
            self.candidates.insert(0, cand)
            self._refresh_gallery()
            self._select(0)
            self.statusBar().showMessage(f"Added manual frame @ {_fmt_time(ts)}")

    def _save(self):
        if self.selected_idx < 0: return
        c = self.candidates[self.selected_idx]
        self._save_image(c)

    def _batch_save(self):
        starred = [c for c in self.candidates if c.starred]
        if not starred:
            QMessageBox.information(self, "Info", "No starred images to save.")
            return
        
        folder = QFileDialog.getExistingDirectory(self, "Select Save Folder")
        if folder:
            for c in starred:
                fname = f"thumb_{_fmt_time(c.timestamp).replace(':','-')}.jpg"
                self._save_image(c, path=os.path.join(folder, fname))
            self.statusBar().showMessage(f"Saved {len(starred)} images.")

    def _save_image(self, cand, path=None):
        pil = Image.fromarray(cv2.cvtColor(cand.frame_bgr, cv2.COLOR_BGR2RGB))
        preset = PRESETS[self.combo_preset.currentText()]
        if preset:
            tw, th = preset
            ratio = max(tw/pil.width, th/pil.height)
            pil = pil.resize((int(pil.width*ratio), int(pil.height*ratio)), Image.LANCZOS)
            left = (pil.width - tw)//2
            top = (pil.height - th)//2
            pil = pil.crop((left, top, left+tw, top+th))
        
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Save", f"thumb_{_fmt_time(cand.timestamp).replace(':','-')}.jpg", "JPEG (*.jpg)")
        
        if path:
            pil.save(path, quality=95)
            self.statusBar().showMessage(f"Saved to {path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())