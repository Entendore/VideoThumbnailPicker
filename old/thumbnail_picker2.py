"""Video Thumbnail Picker — standalone single-file version.
Run with: python thumbnail_picker.py
"""
from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
import threading
import traceback
import concurrent.futures
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from PySide6.QtCore import Qt, QTimer, QMimeData, QRectF, QPoint, Signal, QSettings
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QPen, QPainterPath, QMouseEvent,
    QKeySequence, QShortcut, QAction, QDragEnterEvent, QDropEvent
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QProgressBar, QScrollArea, QFileDialog,
    QMessageBox, QSplitter, QFrame, QToolBar, QCheckBox, QGridLayout, QSizePolicy,
    QTabWidget, QSlider, QMenu, QGraphicsView, QGraphicsScene, QDialog,
    QDialogButtonBox, QGroupBox, QLineEdit, QDoubleSpinBox
)

# =====================================================================
# CONFIGURATION
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger("thumbnail_picker")

# OpenCV threading configuration
os.environ.setdefault("OMP_NUM_THREADS", "1")
try:
    cv2.setNumThreads(0)
    cv2.ocl.setUseOpenCL(True)
except Exception as e:
    logger.warning(f"Could not configure OpenCV: {e}")

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
    "sharpness": "Sharpness", "colorfulness": "Colour", "contrast": "Contrast",
    "brightness": "Bright", "entropy": "Entropy", "composition": "Compos.",
    "skin_tone": "Skin", "faces": "Faces", "motion": "Motion",
    "exposure_quality": "Exposure", "dynamic_range": "Range",
    "visual_complexity": "Complex", "color_harmony": "Harmony", "center_weight": "Center",
}

SCORING_MAX_DIMENSION: int = 720
GALLERY_THUMB_W: int = 200
GALLERY_THUMB_H: int = 110
FILMSTRIP_THUMB_H: int = 64
GALLERY_COLUMNS: int = 3
ANALYSIS_BATCH_INTERVAL_MS: int = 80
DEFAULT_FILMSTRIP_FRAMES: int = 200

SORT_OPTIONS = [
    ("Score", None, True),
    ("Starred First", "__starred__", True),
    ("Time", "timestamp", False),
    ("Sharpness", "sharpness", True),
    ("Contrast", "contrast", True),
    ("Brightness", "brightness", True),
    ("Composition", "composition", True),
    ("Faces", "faces", True),
    ("Colorfulness", "colorfulness", True),
    ("Dynamic Range", "dynamic_range", True),
    ("Entropy", "entropy", True),
    ("Exposure", "exposure_quality", True),
    ("Complexity", "visual_complexity", True),
    ("Harmony", "color_harmony", True),
    ("Center", "center_weight", True),
    ("Skin", "skin_tone", True),
]

SCORE_THRESHOLD_DEFAULT: float = 0.0
REANALYZE_RADIUS_SEC: float = 2.0
REANALYZE_SAMPLES: int = 12
ETA_UPDATE_INTERVAL_MS: int = 500
CARD_SIZES = ["Small", "Medium", "Large"]
DEFAULT_CARD_SIZE: str = "Medium"

FILENAME_TEMPLATES = [
    "thumb_{timestamp}.jpg",
    "{video}_{timestamp}.jpg",
    "{video}_rank{rank}_{score}.jpg",
    "{video}_{ts_seconds}s_{score}.jpg",
    "thumbnail_{rank:02d}.jpg",
]
DEFAULT_FILENAME_TEMPLATE: str = "thumb_{timestamp}.jpg"

THEME_DARK = "dark"
THEME_LIGHT = "light"
THEMES = [THEME_DARK, THEME_LIGHT]
DEFAULT_THEME: str = THEME_DARK

C_BG = "#171717"
C_SURFACE = "#262626"
C_CARD = "#2E2E2E"
C_OVERLAY = "#404040"
C_TEXT = "#D4D4D4"
C_SUBTEXT = "#737373"
C_ACCENT = "#888888"

def _build_light_theme() -> dict:
    return {
        "C_BG": "#FAFAFA", "C_SURFACE": "#F0F0F0", "C_CARD": "#E8E8E8",
        "C_OVERLAY": "#D4D4D4", "C_TEXT": "#1A1A1A", "C_SUBTEXT": "#737373",
        "C_ACCENT": "#525252",
    }

def get_theme_colors(theme: str) -> dict:
    if theme == THEME_LIGHT:
        return _build_light_theme()
    return {
        "C_BG": C_BG, "C_SURFACE": C_SURFACE, "C_CARD": C_CARD,
        "C_OVERLAY": C_OVERLAY, "C_TEXT": C_TEXT, "C_SUBTEXT": C_SUBTEXT,
        "C_ACCENT": C_ACCENT,
    }

def build_stylesheet(colors: dict) -> str:
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
    QPushButton:hover {{ background:{c['C_ACCENT']}; color:{c['C_BG']}; }}
    QPushButton:pressed {{ background:{c['C_OVERLAY']}; color:{c['C_TEXT']}; }}
    QPushButton#btnGreen {{ background:{c['C_OVERLAY']}; color:{c['C_TEXT']}; }}
    QPushButton#btnGreen:hover {{ background:{c['C_ACCENT']}; color:{c['C_BG']}; }}
    QPushButton#btnRed {{ background:{c['C_OVERLAY']}; color:{c['C_TEXT']}; }}
    QPushButton#btnRed:hover {{ background:{c['C_ACCENT']}; color:{c['C_BG']}; }}
    QPushButton#btnPrimary {{ background:{c['C_TEXT']}; color:{c['C_BG']}; }}
    QPushButton#btnPrimary:hover {{ background:{c['C_ACCENT']}; color:{c['C_BG']}; }}
    QPushButton:disabled {{ background:{c['C_OVERLAY']}; color:{c['C_SUBTEXT']}; }}
    QComboBox {{ background:{c['C_CARD']}; border:1px solid {c['C_OVERLAY']}; border-radius:5px; padding:5px 10px; min-height:18px; }}
    QComboBox:hover {{ border-color:{c['C_ACCENT']}; }}
    QComboBox::drop-down {{ border:none; width:22px; }}
    QComboBox QAbstractItemView {{ background:{c['C_CARD']}; selection-background-color:{c['C_ACCENT']}; outline:none; }}
    QSpinBox, QDoubleSpinBox {{ background:{c['C_CARD']}; border:1px solid {c['C_OVERLAY']}; border-radius:5px; padding:4px 6px; }}
    QScrollArea {{ border:none; background:transparent; }}
    QScrollBar:vertical {{ background:{c['C_SURFACE']}; width:10px; border-radius:5px; margin:2px; }}
    QScrollBar::handle:vertical {{ background:{c['C_OVERLAY']}; border-radius:5px; min-height:24px; }}
    QScrollBar::handle:vertical:hover {{ background:{c['C_ACCENT']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height:0; }}
    QStatusBar {{ background:{c['C_SURFACE']}; color:{c['C_SUBTEXT']}; font-weight:bold; border-top:1px solid {c['C_OVERLAY']}; }}
    QSlider::groove:horizontal {{ height:4px; background:{c['C_OVERLAY']}; border-radius:2px; }}
    QSlider::handle:horizontal {{ background:{c['C_TEXT']}; width:14px; height:14px; margin:-5px 0; border-radius:7px; }}
    QCheckBox::indicator {{ width:14px; height:14px; border-radius:3px; border:1px solid {c['C_OVERLAY']}; background:{c['C_CARD']}; }}
    QCheckBox::indicator:checked {{ background:{c['C_TEXT']}; border-color:{c['C_TEXT']}; }}
    QProgressBar {{ border:none; border-radius:5px; background:{c['C_OVERLAY']}; text-align:center; color:{c['C_BG']}; font-weight:bold; min-height:18px; }}
    QProgressBar::chunk {{ background:{c['C_TEXT']}; border-radius:4px; }}
    QLabel#LblTitle {{ font-size:15px; font-weight:bold; color:{c['C_TEXT']}; }}
    QLabel#LblSection {{ font-size:11px; font-weight:bold; color:{c['C_SUBTEXT']}; letter-spacing:1px; }}
    QFrame#Card {{ background:{c['C_CARD']}; border-radius:8px; }}
    QTabWidget::pane {{ border:1px solid {c['C_OVERLAY']}; border-radius:6px; background:{c['C_SURFACE']}; }}
    QTabBar::tab {{ background:{c['C_CARD']}; color:{c['C_SUBTEXT']}; padding:8px 18px; border-top-left-radius:5px; border-top-right-radius:5px; margin-right:2px; }}
    QTabBar::tab:selected {{ background:{c['C_SURFACE']}; color:{c['C_TEXT']}; font-weight:bold; }}
    QToolBar {{ background:{c['C_SURFACE']}; border-bottom:1px solid {c['C_OVERLAY']}; spacing:4px; padding:4px; }}
    QMenu {{ background:{c['C_CARD']}; border:1px solid {c['C_OVERLAY']}; border-radius:5px; padding:4px; }}
    QMenu::item:selected {{ background:{c['C_ACCENT']}; color:{c['C_BG']}; }}
    """

STYLESHEET = build_stylesheet(get_theme_colors(DEFAULT_THEME))

# =====================================================================
# STATE MANAGEMENT
# =====================================================================
RECENT_FILES_MAX = 10
SIDECAR_SUFFIX = ".vtp.json"
SIDECAR_VERSION = 1

class AppSettings:
    def __init__(self) -> None:
        self._s = QSettings("ThumbnailPicker", "Video Thumbnail Picker")

    def save_window_state(self, window) -> None:
        self._s.setValue("ui/windowGeometry", window.saveGeometry())
        splitter = getattr(window, "_splitter", None)
        if splitter is not None:
            self._s.setValue("ui/splitterSizes", splitter.sizes())

    def restore_window_state(self, window) -> None:
        geo = self._s.value("ui/windowGeometry")
        if geo is not None:
            window.restoreGeometry(geo)

    def splitter_sizes(self) -> List[int]:
        raw = self._s.value("ui/splitterSizes")
        if raw is None: return []
        if isinstance(raw, (list, tuple)): return [int(x) for x in raw]
        return []

    def save_analysis_settings(self, *, algo: str, preset: str, samples: int, cands: int, scene: bool, sort: str, threshold: float) -> None:
        self._s.setValue("analysis/algo", algo)
        self._s.setValue("analysis/preset", preset)
        self._s.setValue("analysis/samples", int(samples))
        self._s.setValue("analysis/cands", int(cands))
        self._s.setValue("analysis/scene", bool(scene))
        self._s.setValue("analysis/sort", sort)
        self._s.setValue("analysis/threshold", float(threshold))

    def restore_analysis_settings(self) -> Dict[str, Any]:
        return {
            "algo": self._s.value("analysis/algo", "General (Balanced)", type=str),
            "preset": self._s.value("analysis/preset", "Original", type=str),
            "samples": self._s.value("analysis/samples", 80, type=int),
            "cands": self._s.value("analysis/cands", 15, type=int),
            "scene": self._s.value("analysis/scene", False, type=bool),
            "sort": self._s.value("analysis/sort", "Score", type=str),
            "threshold": self._s.value("analysis/threshold", 0.0, type=float),
        }

    @property
    def card_size(self) -> str: return self._s.value("ui/cardSize", "Medium", type=str)
    @card_size.setter
    def card_size(self, value: str) -> None: self._s.setValue("ui/cardSize", str(value))

    @property
    def theme(self) -> str: return self._s.value("ui/theme", "dark", type=str)
    @theme.setter
    def theme(self, value: str) -> None: self._s.setValue("ui/theme", str(value))

    @property
    def filename_template(self) -> str: return self._s.value("ui/filenameTemplate", "thumb_{timestamp}.jpg", type=str)
    @filename_template.setter
    def filename_template(self, value: str) -> None: self._s.setValue("ui/filenameTemplate", str(value))

    @property
    def auto_free_memory(self) -> bool: return self._s.value("ui/autoFreeMemory", False, type=bool)
    @auto_free_memory.setter
    def auto_free_memory(self, value: bool) -> None: self._s.setValue("ui/autoFreeMemory", bool(value))

    @property
    def save_quality(self) -> int: return self._s.value("io/saveQuality", 95, type=int)
    @save_quality.setter
    def save_quality(self, value: int) -> None: self._s.setValue("io/saveQuality", max(1, min(100, int(value))))

    @property
    def save_format(self) -> str: return self._s.value("io/saveFormat", "JPEG", type=str)
    @save_format.setter
    def save_format(self, value: str) -> None: self._s.setValue("io/saveFormat", str(value))

    @property
    def reanalyze_radius(self) -> float: return self._s.value("analysis/reanalyzeRadius", 2.0, type=float)
    @reanalyze_radius.setter
    def reanalyze_radius(self, value: float) -> None: self._s.setValue("analysis/reanalyzeRadius", float(value))

    @property
    def reanalyze_samples(self) -> int: return self._s.value("analysis/reanalyzeSamples", 12, type=int)
    @reanalyze_samples.setter
    def reanalyze_samples(self, value: int) -> None: self._s.setValue("analysis/reanalyzeSamples", max(4, int(value)))

    @property
    def recent_files(self) -> List[str]:
        raw = self._s.value("recent/files", [])
        if isinstance(raw, str): raw = [raw]
        if not isinstance(raw, (list, tuple)): return []
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

    @property
    def custom_profiles(self) -> Dict[str, Dict[str, float]]:
        raw = self._s.value("profiles/custom", {})
        if not isinstance(raw, dict): return {}
        out: Dict[str, Dict[str, float]] = {}
        for name, weights in raw.items():
            if isinstance(weights, dict):
                out[name] = {k: float(v) for k, v in weights.items()}
        return out

    def save_custom_profile(self, name: str, weights: Dict[str, float]) -> None:
        profiles = self.custom_profiles
        profiles[name] = {k: float(v) for k, v in weights.items()}
        self._s.setValue("profiles/custom", profiles)

    @property
    def last_dir(self) -> str: return self._s.value("io/lastDir", "", type=str)
    @last_dir.setter
    def last_dir(self, value: str) -> None: self._s.setValue("io/lastDir", str(value))

    def sync(self) -> None: self._s.sync()

class ProjectState:
    @staticmethod
    def sidecar_path(video_path: str) -> Path:
        return Path(video_path).with_suffix(SIDECAR_SUFFIX)

    @staticmethod
    def save(video_path: str, candidates: List) -> None:
        sidecar = ProjectState.sidecar_path(video_path)
        data = {
            "version": SIDECAR_VERSION,
            "video": str(video_path),
            "starred_timestamps": [round(c.timestamp, 3) for c in candidates if c.starred],
        }
        try:
            sidecar.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Could not save project state: {e}")

    @staticmethod
    def load(video_path: str) -> Dict[str, Any]:
        sidecar = ProjectState.sidecar_path(video_path)
        if not sidecar.exists(): return {}
        try:
            data = json.loads(sidecar.read_text())
            if not isinstance(data, dict): return {}
            return data
        except Exception as e:
            logger.warning(f"Could not load project state: {e}")
            return {}

SETTINGS = AppSettings()

# =====================================================================
# UTILITIES & FRAME STORE
# =====================================================================
def format_time(t: float) -> str:
    if t < 0 or not np.isfinite(t): return "00:00.000"
    m, s = divmod(int(t), 60)
    ms = int((t - int(t)) * 1000)
    return f"{m:02d}:{s:02d}.{ms:03d}"

def format_duration(t: float) -> str:
    if t <= 0: return "0s"
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    parts = []
    if h: parts.append(f"{h}h")
    if m or h: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)

def bgr_to_qimage(bgr: np.ndarray) -> Optional[QImage]:
    if bgr is None or bgr.size == 0: return None
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    qim = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    qim._np_buf = rgb
    return qim

def bgr_to_qpixmap(bgr: np.ndarray) -> QPixmap:
    qim = bgr_to_qimage(bgr)
    return QPixmap.fromImage(qim) if qim is not None else QPixmap()

def scaled_qpixmap(bgr: np.ndarray, w: int, h: int,
                   aspect: Qt.AspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio,
                   smooth: Qt.TransformationMode = Qt.TransformationMode.SmoothTransformation) -> QPixmap:
    if bgr is None or bgr.size == 0: return QPixmap()
    src_h, src_w = bgr.shape[:2]
    scale = min(w / src_w, h / src_h) if aspect == Qt.AspectRatioMode.KeepAspectRatio else max(w / src_w, h / src_h)
    new_w, new_h = max(1, int(src_w * scale)), max(1, int(src_h * scale))
    resized = cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return bgr_to_qpixmap(resized)

class ThumbnailCache:
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

THUMBS = ThumbnailCache()

def fit_crop_pil(pil_img, target: Tuple[int, int]):
    tw, th = target
    if pil_img.size == (tw, th): return pil_img
    ratio = max(tw / pil_img.width, th / pil_img.height)
    pil_img = pil_img.resize((int(pil_img.width * ratio), int(pil_img.height * ratio)), Image.Resampling.LANCZOS)
    left = (pil_img.width - tw) // 2
    top = (pil_img.height - th) // 2
    return pil_img.crop((left, top, left + tw, top + th))

def downscale_for_scoring(bgr: np.ndarray, max_dim: int) -> Tuple[np.ndarray, np.ndarray]:
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

DEFAULT_LRU_SIZE: int = 50
class FrameStore:
    def __init__(self, max_entries: int = DEFAULT_LRU_SIZE) -> None:
        self._max = max(1, int(max_entries))
        self._cache: "OrderedDict[Tuple[str, float], np.ndarray]" = OrderedDict()
        self._lock = threading.RLock()
        self._caps: dict = {}
        self._caps_lock = threading.Lock()

    def get(self, video_path: str, timestamp: float) -> Optional[np.ndarray]:
        key = (video_path, round(timestamp, 3))
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached
        frame = self._fetch(video_path, timestamp)
        if frame is None: return None
        with self._lock:
            self._cache[key] = frame
            self._cache.move_to_end(key)
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)
        return frame

    def _fetch(self, video_path: str, timestamp: float) -> Optional[np.ndarray]:
        cap = self._get_cap(video_path)
        if cap is None: return None
        try:
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ret, frame = cap.read()
            if not ret or frame is None: return None
            return frame
        except Exception as e:
            logger.error(f"Error reading frame: {e}")
            return None

    def _get_cap(self, video_path: str):
        with self._caps_lock:
            cap = self._caps.get(video_path)
            if cap is not None: return cap
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened(): return None
            self._caps[video_path] = cap
            return cap

    def stats(self) -> dict:
        with self._lock:
            return {"entries": len(self._cache), "max": self._max}

FRAME_STORE = FrameStore()

# =====================================================================
# ANALYSIS & SCORING
# =====================================================================
_face_cascade: Optional[cv2.CascadeClassifier] = None
_profile_cascade: Optional[cv2.CascadeClassifier] = None

def _get_cascades() -> Tuple[Optional[cv2.CascadeClassifier], Optional[cv2.CascadeClassifier]]:
    global _face_cascade, _profile_cascade
    if _face_cascade is None:
        try:
            _face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            _profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
            if _face_cascade.empty() or _profile_cascade.empty(): raise IOError("Cascade files are empty")
        except Exception as e:
            logger.error(f"Failed to load cascades: {e}.")
            _face_cascade = None
            _profile_cascade = None
    return _face_cascade, _profile_cascade

@dataclass(eq=False)
class Candidate:
    frame_bgr: Optional[np.ndarray]
    timestamp: float
    total_score: float
    breakdown: Dict[str, float]
    faces: List[Tuple[int, int, int, int]] = field(default_factory=list)
    starred: bool = False
    video_path: Optional[str] = None
    _hist: Optional[np.ndarray] = field(default=None, repr=False)
    _edge_hist_cache: Optional[np.ndarray] = field(default=None, repr=False)
    motion_magnitude: float = 0.0

    @property
    def hist(self) -> np.ndarray:
        if self._hist is None:
            frame = self.ensure_frame()
            if frame is None: return np.zeros(200, dtype=np.float32)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            h = cv2.calcHist([hsv], [0, 1], None, [20, 10], [0, 180, 0, 256]).flatten()
            self._hist = h / (h.sum() + 1e-8)
        return self._hist

    def ensure_frame(self) -> Optional[np.ndarray]:
        if self.frame_bgr is not None: return self.frame_bgr
        if not self.video_path or self.timestamp < 0: return None
        frame = FRAME_STORE.get(self.video_path, self.timestamp)
        if frame is not None: self.frame_bgr = frame
        return frame

    def release_frame(self) -> None:
        self.frame_bgr = None
        self._hist = None
        self._edge_hist_cache = None

def prefilter_frame(bgr: np.ndarray) -> bool:
    if bgr is None or bgr.size == 0: return False
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    m = float(np.mean(gray))
    if m < 18 or m > 242: return False
    p_lo, p_hi = np.percentile(gray, [10, 90])
    if (p_hi - p_lo) < 25: return False
    channel_stds = [float(np.std(bgr[:, :, c])) for c in range(3)]
    if sum(1 for s in channel_stds if s < 8) >= 2: return False
    if cv2.Laplacian(gray, cv2.CV_64F).var() < 12: return False
    return True

def _atan_sat(x: float, scale: float = 1.0, offset: float = 0.0) -> float:
    return float((2.0 / math.pi) * math.atan((max(0.0, x) + offset) / scale))

def score_faces(bgr: np.ndarray) -> Tuple[float, List[Tuple[int, int, int, int]]]:
    fc, pc = _get_cascades()
    if fc is None or fc.empty(): return 0.0, []
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = fc.detectMultiScale(g, 1.2, 5, minSize=(40, 40))
    if len(faces) == 0 and pc and not pc.empty():
        faces = pc.detectMultiScale(g, 1.2, 5, minSize=(40, 40))
    if len(faces) == 0: return 0.0, []
    H, W = bgr.shape[:2]
    largest = max(faces, key=lambda r: r[2] * r[3])
    fx = (largest[0] + largest[2] / 2) / W
    fy = (largest[1] + largest[3] / 2) / H
    dist = math.sqrt((fx - 0.5) ** 2 + (fy - 0.5) ** 2)
    center_bonus = max(0.0, 0.4 * (1 - dist * 2))
    area_ratio = (largest[2] * largest[3]) / (H * W)
    size_bonus = 0.2 if 0.05 < area_ratio < 0.5 else 0.0
    return min(0.4 + center_bonus + size_bonus, 1.0), [tuple(int(v) for v in f) for f in faces]

def score_sharpness(gray: np.ndarray) -> float:
    if gray is None or gray.size == 0: return 0.0
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    tenengrad = float(np.mean(gx * gx + gy * gy))
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    t_norm = _atan_sat(tenengrad / 1000.0, scale=0.55)
    l_norm = _atan_sat(lap_var / 100.0, scale=0.50)
    if t_norm + l_norm < 1e-9: return 0.0
    return float(2.0 * t_norm * l_norm / (t_norm + l_norm))

def score_contrast(gray: np.ndarray) -> float:
    if gray is None or gray.size == 0: return 0.0
    std_val = float(np.std(gray))
    rms_score = _atan_sat(std_val / 40.0, scale=0.45, offset=0.10)
    blur_fine = cv2.GaussianBlur(gray, (7, 7), 1.5)
    blur_coarse = cv2.GaussianBlur(gray, (21, 21), 5.0)
    local_diff = float(np.mean(np.abs(gray.astype(np.float64) - blur_fine.astype(np.float64))))
    coarse_diff = float(np.mean(np.abs(gray.astype(np.float64) - blur_coarse.astype(np.float64))))
    local_score = _atan_sat(local_diff / 15.0, scale=0.50)
    coarse_score = _atan_sat(coarse_diff / 25.0, scale=0.50)
    return float(0.40 * rms_score + 0.35 * local_score + 0.25 * coarse_score)

def score_brightness(gray: np.ndarray) -> float:
    if gray is None or gray.size == 0: return 0.0
    mu = float(np.mean(gray))
    gauss = math.exp(-0.5 * ((mu - 135.0) / 55.0) ** 2)
    bright_boost = 1.0 + 0.15 * math.log1p(math.exp((mu - 128.0) / 20.0))
    return float(min(gauss * min(bright_boost, 1.15), 1.0))

def score_entropy(gray: np.ndarray) -> float:
    if gray is None or gray.size == 0: return 0.0
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    total = hist.sum()
    if total < 1: return 0.0
    p = hist / total
    p_nonzero = p[p > 0]
    H = float(-np.sum(p_nonzero * np.log2(p_nonzero)))
    return float(min(_atan_sat(H / 8.0, scale=0.40, offset=0.05), 1.0))

def score_exposure_quality(bgr: np.ndarray, gray: Optional[np.ndarray] = None) -> float:
    if bgr is None or bgr.size == 0: return 0.0
    if gray is None: gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    total = hist.sum()
    if total < 1: return 0.0
    p = hist / total
    shadow_clip = float(np.sum(p[:5]))
    highlight_clip = float(np.sum(p[251:]))
    clip_score = max(0.0, 1.0 - (shadow_clip + highlight_clip) * 10.0)
    cdf = np.cumsum(p)
    p2 = float(np.searchsorted(cdf, 0.02))
    p98 = float(np.searchsorted(cdf, 0.98))
    spread_score = _atan_sat((p98 - p2) / 255.0, scale=0.45, offset=0.05)
    bins = np.arange(256, dtype=np.float64)
    mu = float(np.sum(bins * p))
    if mu < 1e-9: shape_score = 0.3
    else:
        var = float(np.sum(((bins - mu) ** 2) * p))
        if var < 1e-9: shape_score = 0.3
        else:
            m4 = float(np.sum(((bins - mu) ** 4) * p))
            kurt = m4 / (var ** 2) - 3.0
            shape_score = math.exp(-0.5 * ((kurt - 2.5) / 4.0) ** 2)
    return float(min((clip_score * spread_score * shape_score) ** (1.0 / 3.0), 1.0))

def score_composition(bgr: np.ndarray, gray: Optional[np.ndarray] = None) -> float:
    if bgr is None or bgr.size == 0: return 0.0
    H, W = bgr.shape[:2]
    if gray is None: gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150).astype(np.float64) / 255.0
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    def _gauss_score(cx, cy, sx, sy):
        g = np.exp(-0.5 * (((xx / W - cx) / sx) ** 2 + ((yy / H - cy) / sy) ** 2))
        return float(np.sum(edges * g))
    sx, sy = 0.09, 0.09
    third_score = sum(_gauss_score(fx, fy, sx, sy) for fx in (1/3, 2/3) for fy in (1/3, 2/3))
    golden_score = sum(_gauss_score(fx, fy, sx*0.8, sy*0.8) for fx in (0.382, 0.618) for fy in (0.382, 0.618))
    area = H * W
    g_sum = float(np.exp(-0.5 * 0)) * area
    third_n = _atan_sat(third_score / (g_sum * 0.05), scale=0.45)
    golden_n = _atan_sat(golden_score / (g_sum * 0.05), scale=0.45)
    total_edge = edges.sum() + 1e-9
    com_x = float((edges * xx).sum() / total_edge) / W
    com_y = float((edges * yy).sum() / total_edge) / H
    com_dist = math.sqrt((com_x - 0.5) ** 2 + (com_y - 0.5) ** 2)
    com_score = max(0.0, 1.0 - com_dist / 0.5)
    return float(min(0.55 * third_n + 0.20 * golden_n + 0.25 * com_score, 1.0))

def score_dynamic_range(bgr: np.ndarray, gray: Optional[np.ndarray] = None) -> float:
    if bgr is None or bgr.size == 0: return 0.0
    if gray is None: gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    p_lo, p_hi = float(np.percentile(gray, 1)), float(np.percentile(gray, 99))
    range_score = _atan_sat((p_hi - p_lo) / 255.0, scale=0.40, offset=0.05)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    gap_ratio = float(np.sum(hist == 0)) / 256.0 if hist.sum() > 0 else 0.5
    return float(min(range_score * (1.0 - 0.3 * gap_ratio), 1.0))

def score_colorfulness(bgr: np.ndarray) -> float:
    if bgr is None or bgr.size == 0: return 0.0
    rgb = bgr[:, :, ::-1].astype(np.float64)
    rg = rgb[:, :, 0] - rgb[:, :, 1]
    yb = 0.5 * (rgb[:, :, 0] + rgb[:, :, 1]) - rgb[:, :, 2]
    C = math.sqrt(np.std(rg)**2 + np.std(yb)**2) + 0.3 * math.sqrt(np.mean(rg)**2 + np.mean(yb)**2)
    return float(min(_atan_sat(C / 100.0, scale=0.45, offset=0.02), 1.0))

def score_visual_complexity(bgr: np.ndarray, gray: Optional[np.ndarray] = None) -> float:
    if bgr is None or bgr.size == 0: return 0.0
    if gray is None: gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape[:2]
    edges = cv2.Canny(gray, 50, 150)
    density_score = _atan_sat(float(np.count_nonzero(edges)) / (H * W) * 3.0, scale=0.40, offset=0.02)
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    mask = mag > 10.0
    if mask.sum() < 10: return density_score
    angles = np.mod(np.arctan2(gy[mask], gx[mask]), np.pi)
    hist, _ = np.histogram(angles, bins=12, range=(0, np.pi))
    p = hist / hist.sum()
    orient_norm = float(-np.sum(p[p>0] * np.log2(p[p>0]))) / math.log2(12)
    return float(min(0.55 * density_score + 0.45 * orient_norm, 1.0))

def score_color_harmony(bgr: np.ndarray) -> float:
    if bgr is None or bgr.size == 0: return 0.0
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float64)
    hue = hsv[:, :, 0] / 180.0 * np.pi
    sat = hsv[:, :, 1] / 255.0
    mask = sat > 0.15
    if mask.sum() < 20: return 0.5
    hues, weights = hue[mask], sat[mask]
    w_sum = weights.sum()
    if w_sum < 1e-9: return 0.5
    cos_sum = float(np.sum(weights * np.cos(2 * hues))) / w_sum
    sin_sum = float(np.sum(weights * np.sin(2 * hues))) / w_sum
    coherence_score = math.sqrt(cos_sum**2 + sin_sum**2)
    return float(min(0.50 * coherence_score + 0.50 * 0.5, 1.0))

def score_center_weight(bgr: np.ndarray, gray: Optional[np.ndarray] = None) -> float:
    if bgr is None or bgr.size == 0: return 0.0
    H, W = bgr.shape[:2]
    if gray is None: gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    edge_energy = np.sqrt(gx**2 + gy**2)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float64)
    sat_weight = hsv[:, :, 1] / 255.0
    saliency = edge_energy * (0.5 + 0.5 * sat_weight)
    s_max = saliency.max()
    if s_max > 1e-9: saliency = saliency / s_max
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    cx, cy = W / 2.0, H / 2.0
    sigma = min(W, H) * 0.35
    radial = np.exp(-0.5 * ((xx - cx)**2 + (yy - cy)**2) / (sigma**2))
    s_flat, r_flat = saliency.flatten(), radial.flatten()
    cos_sim = float(np.dot(s_flat, r_flat) / (np.linalg.norm(s_flat) * np.linalg.norm(r_flat) + 1e-9))
    return float(min(0.55 * max(cos_sim, 0.0) + 0.45 * 0.5, 1.0))

def score_skin_tone(bgr: np.ndarray) -> float:
    if bgr is None or bgr.size == 0: return 0.0
    H, W = bgr.shape[:2]
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    cb, cr = ycrcb[:, :, 1], ycrcb[:, :, 2]
    skin_ycrcb = (cb >= 80) & (cb <= 120) & (cr >= 133) & (cr <= 173)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    skin_hsv = (h <= 50) & (s >= 20) & (s <= 204) & (v >= 40)
    skin_mask = skin_ycrcb & skin_hsv
    skin_fraction = float(skin_mask.sum()) / (H * W)
    return float(min(_atan_sat(skin_fraction * 5.0, scale=0.45, offset=0.01), 1.0))

def _edge_hist(gray: np.ndarray, n_bins: int = 16) -> np.ndarray:
    if gray is None or gray.size == 0: return np.zeros(n_bins, dtype=np.float32)
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    mask = mag > 15.0
    if mask.sum() < 5: return np.zeros(n_bins, dtype=np.float32)
    angles = np.mod(np.arctan2(gy, gx)[mask], np.pi)
    hist, _ = np.histogram(angles, bins=n_bins, range=(0, np.pi), weights=mag[mask])
    total = hist.sum()
    return (hist / total).astype(np.float32) if total > 0 else np.zeros(n_bins, dtype=np.float32)

def score_motion(gray: np.ndarray, prev_gray: Optional[np.ndarray] = None) -> float:
    if prev_gray is None or gray is None or gray.size == 0: return 0.0
    try:
        flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 2, 5, 1.2, 0)
        mag = np.sqrt(flow[:, :, 0]**2 + flow[:, :, 1]**2)
        return float(_atan_sat(float(np.mean(mag)) / 4.0, scale=0.45, offset=0.05))
    except Exception:
        return 0.0

SCORERS: Dict[str, Callable] = {
    "sharpness": lambda f, g: score_sharpness(g),
    "contrast": lambda f, g: score_contrast(g),
    "brightness": lambda f, g: score_brightness(g),
    "composition": lambda f, g: score_composition(f, g),
    "motion": lambda f, g: 0.0,
    "dynamic_range": lambda f, g: score_dynamic_range(f, g),
    "colorfulness": lambda f, g: score_colorfulness(f),
    "exposure_quality": lambda f, g: score_exposure_quality(f, g),
    "visual_complexity": lambda f, g: score_visual_complexity(f, g),
    "color_harmony": lambda f, g: score_color_harmony(f),
    "center_weight": lambda f, g: score_center_weight(f, g),
    "skin_tone": lambda f, g: score_skin_tone(f),
    "entropy": lambda f, g: score_entropy(g),
}

def _normalize_scores(cands: List[Candidate]) -> List[Candidate]:
    if len(cands) < 2: return cands
    all_keys = set()
    for c in cands: all_keys.update(c.breakdown.keys())
    ranges = {}
    for key in all_keys:
        vals = [c.breakdown.get(key, 0.0) for c in cands]
        ranges[key] = (min(vals), max(vals))
    for c in cands:
        for key, (lo, hi) in ranges.items():
            if key in c.breakdown and hi > lo:
                c.breakdown[key] = (c.breakdown[key] - lo) / (hi - lo)
    return cands

def filter_similar(cands: List[Candidate], threshold: float = 0.85) -> List[Candidate]:
    if len(cands) <= 1: return cands
    kept: List[Candidate] = [cands[0]]
    struct_threshold = threshold * 0.90
    for c in cands:
        if c._edge_hist_cache is None:
            frame = c.ensure_frame()
            if frame is not None:
                c._edge_hist_cache = _edge_hist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            else:
                c._edge_hist_cache = np.zeros(16, dtype=np.float32)
    for c in cands[1:]:
        is_similar = False
        for k in kept:
            if cv2.compareHist(c.hist, k.hist, cv2.HISTCMP_CORREL) < threshold: continue
            if 1.0 - cv2.compareHist(c._edge_hist_cache, k._edge_hist_cache, cv2.HISTCMP_BHATTACHARYYA) > struct_threshold:
                is_similar = True
                break
        if not is_similar: kept.append(c)
    return kept

def _process_single_frame(path: str, t: float, weights: Dict[str, float], get_cap=None, return_cap=None) -> Optional[Candidate]:
    cap = get_cap() if get_cap else cv2.VideoCapture(path)
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, frame = cap.read()
        if not ret or frame is None: return None
        if not prefilter_frame(frame): return None
        face_score, faces = score_faces(frame)
        small, gray = downscale_for_scoring(frame, SCORING_MAX_DIMENSION)
        scores = {name: fn(small, gray) for name, fn in SCORERS.items()}
        scores["faces"] = face_score
        total = sum(scores.get(k, 0.0) * w for k, w in weights.items())
        return Candidate(frame_bgr=frame, timestamp=float(t), total_score=total, breakdown=scores, faces=faces, video_path=path)
    except Exception as e:
        logger.error(f"Worker error at t={t:.2f}s: {e}")
        return None
    finally:
        if return_cap: return_cap(cap)
        else: cap.release()

def _grab_filmstrip_frame(path: str, t: float, thumb_h: int) -> Optional[Tuple[float, np.ndarray]]:
    cap = cv2.VideoCapture(path)
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, f = cap.read()
        if not ret or f is None: return None
        new_w = max(1, int(f.shape[1] * thumb_h / f.shape[0]))
        return (t, cv2.resize(f, (new_w, thumb_h), interpolation=cv2.INTER_AREA))
    except Exception:
        return None
    finally:
        cap.release()

class AnalysisThread(QThread):
    progress = Signal(int, int)
    stage_changed = Signal(str)
    finished_ok = Signal(list, dict)
    finished_err = Signal(str)
    candidate_ready = Signal(object, int, int)
    filmstrip_ready = Signal(list)

    def __init__(self, path: str, n_samples: int, weights: Dict[str, float], n_cands: int, use_scene: bool,
                 max_workers: Optional[int] = None, sample_times_override: Optional[List[float]] = None, skip_filmstrip: bool = False) -> None:
        super().__init__()
        self.path, self.n_samples, self.weights, self.n_cands, self.use_scene = path, n_samples, weights, n_cands, use_scene
        self._max_workers = max_workers or (os.cpu_count() or 4)
        self._abort, self._sample_times_override, self._skip_filmstrip = False, sample_times_override, skip_filmstrip

    def abort(self) -> None: self._abort = True

    def run(self) -> None:
        cap = cv2.VideoCapture(self.path)
        if not cap.isOpened():
            self.finished_err.emit("Cannot open video file.")
            return
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            dur = total_frames / fps if fps > 0 else 0.0
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            if dur <= 0:
                self.finished_err.emit("Video has zero duration.")
                return

            if not self._skip_filmstrip:
                self.stage_changed.emit("Phase 1: Scanning video")
                filmstrip = self._build_filmstrip(dur)
                if self._abort: return
                self.filmstrip_ready.emit(filmstrip)
            else:
                self.filmstrip_ready.emit([])

            self.stage_changed.emit("Phase 2: Detecting scenes")
            sample_times = self._compute_sample_times(total_frames, fps, dur)
            if self._abort: return

            self.stage_changed.emit("Phase 3: Analysing frames")
            cands = self._score_samples(sample_times, 0)
            if self._abort: return

            cands.sort(key=lambda c: c.total_score, reverse=True)
            cands = filter_similar(cands)[:self.n_cands]
            if len(cands) > 1:
                cands = _normalize_scores(cands)
                for c in cands:
                    c.total_score = sum(c.breakdown.get(k, 0.0) * self.weights.get(k, 0.0) for k in self.weights)
                cands.sort(key=lambda c: c.total_score, reverse=True)

            self.finished_ok.emit(cands, dict(path=self.path, duration=dur, fps=fps, width=w, height=h, total_frames=total_frames))
        except Exception as e:
            traceback.print_exc()
            self.finished_err.emit(str(e))

    def _build_filmstrip(self, dur: float) -> List[Tuple[float, np.ndarray]]:
        n_strip = min(DEFAULT_FILMSTRIP_FRAMES, max(20, int(dur / 2)))
        times = [dur * (i + 0.5) / n_strip for i in range(n_strip)]
        filmstrip = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as ex:
            futures = {ex.submit(_grab_filmstrip_frame, self.path, t, 64): t for t in times}
            done = 0
            for fut in concurrent.futures.as_completed(futures):
                if self._abort: return []
                done += 1
                self.progress.emit(done, n_strip + self.n_samples)
                try:
                    res = fut.result()
                    if res: filmstrip.append(res)
                except Exception: pass
        filmstrip.sort(key=lambda r: r[0])
        return filmstrip

    def _compute_sample_times(self, total_frames: int, fps: float, dur: float) -> List[float]:
        if self._sample_times_override is not None:
            return [max(0.0, min(t, dur)) for t in self._sample_times_override]
        sample_times = []
        if self.use_scene and fps > 0:
            s_cap = cv2.VideoCapture(self.path)
            step = max(1, int(fps))
            prev_gray, prev_hist = None, None
            try:
                for i in range(0, total_frames, step):
                    if self._abort: return []
                    s_cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, f = s_cap.read()
                    if not ret: continue
                    gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
                    if prev_gray is not None:
                        curr_hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
                        cv2.normalize(curr_hist, curr_hist)
                        chi_sq = cv2.compareHist(prev_hist, curr_hist, cv2.HISTCMP_CHISQR) if prev_hist is not None else 0.0
                        pixel_diff = float(np.mean(cv2.absdiff(gray, prev_gray)))
                        if pixel_diff > 20.0 and chi_sq > 0.5:
                            t = i / fps
                            if not sample_times or (t - sample_times[-1]) >= 1.0:
                                sample_times.append(t)
                        prev_hist = curr_hist.copy()
                    prev_gray = gray
            finally:
                s_cap.release()
        if not sample_times:
            sample_times = list(np.linspace(0.05, 0.95, self.n_samples) * dur)
        return sample_times

    def _score_samples(self, sample_times: List[float], n_strip: int) -> List[Candidate]:
        cands = []
        total = len(sample_times)
        if total == 0: return cands
        last_emit, processed = {"t": 0.0}, {"n": 0}
        def maybe_emit(cand):
            processed["n"] += 1
            now = time.monotonic() * 1000.0
            if cand and (now - last_emit["t"]) >= ANALYSIS_BATCH_INTERVAL_MS:
                self.candidate_ready.emit(cand, processed["n"], total)
                last_emit["t"] = now

        caps_lock, caps_pool = threading.Lock(), []
        def _get_pooled_cap():
            with caps_lock:
                if caps_pool: return caps_pool.pop()
            return cv2.VideoCapture(self.path)
        def _return_pooled_cap(cap):
            with caps_lock: caps_pool.append(cap)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as ex:
            fut_to_t = {ex.submit(_process_single_frame, self.path, t, self.weights, _get_pooled_cap, _return_pooled_cap): t for t in sample_times}
            for fut in concurrent.futures.as_completed(fut_to_t):
                if self._abort:
                    with caps_lock:
                        for c in caps_pool: c.release()
                        caps_pool.clear()
                    return []
                self.progress.emit(n_strip + processed["n"], n_strip + total)
                try:
                    cand = fut.result()
                    if cand:
                        cands.append(cand)
                        maybe_emit(cand)
                    else:
                        processed["n"] += 1
                except Exception:
                    processed["n"] += 1
        
        with caps_lock:
            for c in caps_pool: c.release()
            caps_pool.clear()
        return cands

# =====================================================================
# WIDGETS
# =====================================================================
class ZoomablePreview(QGraphicsView):
    def __init__(self) -> None:
        super().__init__()
        self._zoom = 1.0
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setStyleSheet("background: transparent; border: none;")
        self._pixmap_item = None
        self.show_grid, self.show_faces, self.show_crop = False, False, False
        self._crop_size, self._current_cand = None, None

    def set_pixmap(self, pm: QPixmap, cand: Optional[Candidate] = None) -> None:
        self.scene().clear()
        self._pixmap_item = self.scene().addPixmap(pm)
        self.scene().setSceneRect(QRectF(pm.rect()))
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._current_cand, self._zoom = cand, 1.0
        self.viewport().update()

    def set_overlays(self, *, grid=None, faces=None, crop=None, crop_size=None) -> None:
        if grid is not None: self.show_grid = grid
        if faces is not None: self.show_faces = faces
        if crop is not None: self.show_crop = crop
        if crop_size is not None: self._crop_size = crop_size
        self.viewport().update()

    def wheelEvent(self, e) -> None:
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.2 ** (e.angleDelta().y() / 120.0)
            self.scale(factor, factor)
            self._zoom *= factor
        else:
            super().wheelEvent(e)

    def zoom_in(self): self.scale(1.2, 1.2); self._zoom *= 1.2
    def zoom_out(self): self.scale(1/1.2, 1/1.2); self._zoom /= 1.2
    def fit(self):
        if self._pixmap_item:
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = 1.0

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        if not self._pixmap_item: return
        painter.save()
        w, h = self._pixmap_item.pixmap().width(), self._pixmap_item.pixmap().height()
        if self.show_grid:
            pen_grid = QPen(QColor(255, 255, 255, 90), 1)
            pen_grid.setCosmetic(True)
            painter.setPen(pen_grid)
            for i in range(1, 3):
                painter.drawLine(int(w * i / 3), 0, int(w * i / 3), h)
                painter.drawLine(0, int(h * i / 3), w, int(h * i / 3))
        if self.show_faces and self._current_cand:
            pen = QPen(QColor(C_TEXT), 3)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for (x, y, fw, fh) in self._current_cand.faces:
                painter.drawRect(int(x), int(y), int(fw), int(fh))
        painter.restore()

class HistogramWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(120)
        self._hist_data, self._paths = None, []

    def set_data(self, bgr: Optional[np.ndarray]) -> None:
        if bgr is None or bgr.size == 0:
            self._hist_data, self._paths = None, []
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
        if not self._hist_data: return
        w, h = self.width(), self.height()
        margin, gw, gh = 8, w - 2 * margin, h - 2 * margin
        for hist in self._hist_data:
            path = QPainterPath()
            path.moveTo(margin, h - margin)
            for i, val in enumerate(hist):
                path.lineTo(margin + (i / 255.0) * gw, h - margin - float(val) * gh)
            path.lineTo(margin + gw, h - margin)
            self._paths.append(path)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._rebuild_paths()
        self.update()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C_CARD))
        if not self._paths:
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data")
            return
        channel_colors = [(220, 60, 60), (60, 200, 60), (80, 130, 230)]
        for idx, path in enumerate(self._paths):
            r, g, b = channel_colors[idx]
            p.fillPath(path, QColor(r, g, b, 80))
            p.setPen(QColor(r, g, b))
            p.drawPath(path)

class ScoreBreakdownWidget(QWidget):
    _BAR_H, _SPACING, _MARGIN_Y = 14, 6, 10
    def __init__(self) -> None:
        super().__init__()
        self._scores = {}
        self.setMinimumHeight(2 * self._MARGIN_Y + len(CRIT_LABELS) * (self._BAR_H + self._SPACING))

    def set_scores(self, scores: Optional[Dict[str, float]]) -> None:
        self._scores = scores or {}
        self.update()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C_CARD))
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if not self._scores:
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No candidate selected")
            return
        keys = sorted(k for k in self._scores if k in CRIT_LABELS)
        bar_h, spacing, label_w, value_w, margin_x, margin_y = self._BAR_H, self._SPACING, 70, 38, 10, self._MARGIN_Y
        bar_x, bar_w = margin_x + label_w, max(40, self.width() - bar_x - value_w - margin_x)
        p.setFont(QFont("Segoe UI", 9))
        for i, k in enumerate(keys):
            y = margin_y + i * (bar_h + spacing)
            val = float(self._scores.get(k, 0.0))
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(margin_x, y, label_w - 6, bar_h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, CRIT_LABELS.get(k, k))
            p.setBrush(QColor(C_OVERLAY))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(bar_x, y, bar_w, bar_h), 4, 4)
            fill_w = max(0.0, min(bar_w * val, bar_w))
            if fill_w > 0:
                col = C_TEXT if val > 0.7 else (C_SUBTEXT if val < 0.3 else C_ACCENT)
                p.setBrush(QColor(col))
                p.drawRoundedRect(QRectF(bar_x, y, fill_w, bar_h), 4, 4)
            p.setPen(QColor(C_TEXT))
            p.drawText(bar_x + bar_w + 4, y, value_w, bar_h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"{val:.2f}")

class FilmstripTimeline(QScrollArea):
    clicked = Signal(float)
    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(100)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"QScrollArea {{ background:{C_OVERLAY}; border-radius:8px; border:none; }}")
        self.container = QWidget()
        self.lay = QHBoxLayout(self.container)
        self.lay.setContentsMargins(6, 4, 6, 4)
        self.lay.setSpacing(4)
        self.setWidget(self.container)

    def set_frames(self, frames: List[tuple]) -> None:
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for t, bgr in frames:
            if bgr is None or bgr.size == 0: continue
            cell = _FilmstripCell(t, bgr)
            cell.clicked.connect(self.clicked.emit)
            self.lay.addWidget(cell)

class _FilmstripCell(QFrame):
    clicked = Signal(float)
    def __init__(self, t: float, bgr: np.ndarray) -> None:
        super().__init__()
        self._t = t
        self.setFixedSize(96, 84)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(format_time(t))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lbl = QLabel()
        lbl.setPixmap(bgr_to_qpixmap(bgr).scaled(92, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)
        ts_lbl = QLabel(format_time(t))
        ts_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ts_lbl.setStyleSheet(f"color:{C_TEXT}; background:{C_SURFACE}; border-radius:3px; padding:1px 4px; font-size:10px;")
        lay.addWidget(ts_lbl)
        self._refresh_style(False)

    def _refresh_style(self, hovered: bool) -> None:
        self.setStyleSheet(f"QFrame {{ background:{C_SURFACE}; border:2px solid {C_ACCENT if hovered else 'transparent'}; border-radius:6px; }}")

    def enterEvent(self, e) -> None: self._refresh_style(True)
    def leaveEvent(self, e) -> None: self._refresh_style(False)
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit(self._t)

class GalleryCard(QFrame):
    clicked = Signal(int)
    starred_toggled = Signal(int)
    reanalyze_requested = Signal(int)
    multi_select_toggled = Signal(int, bool)
    _save_as_preset = Signal(object)
    CARD_SIZE_PRESETS = {"Small": (160, 95), "Medium": (200, 110), "Large": (260, 145)}

    def __init__(self, idx: int, cand: Candidate, size: str = "Medium") -> None:
        super().__init__()
        self.idx, self.cand, self._selected, self._multi_selected = idx, cand, False, False
        self._size = size if size in self.CARD_SIZE_PRESETS else "Medium"
        w, h = self.CARD_SIZE_PRESETS[self._size]
        self.setFixedSize(w, h)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        self.img = QLabel()
        frame = cand.ensure_frame()
        if frame is not None:
            self.img.setPixmap(THUMBS.gallery(id(cand), frame))
        self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img.setMinimumHeight(max(40, h - 50))
        lay.addWidget(self.img, stretch=1)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        tier_color = C_TEXT if cand.total_score >= 0.7 else (C_ACCENT if cand.total_score >= 0.4 else C_SUBTEXT)
        rank_lbl = QLabel(f"#{idx + 1}")
        rank_lbl.setStyleSheet(f"color:{tier_color}; font-weight:bold; font-size:11px;")
        row.addWidget(rank_lbl)
        ts_lbl = QLabel(format_time(cand.timestamp))
        ts_lbl.setStyleSheet(f"font-size:10px; color:{C_SUBTEXT};")
        row.addWidget(ts_lbl)
        row.addStretch()
        score_lbl = QLabel(f"{cand.total_score:.2f}")
        score_lbl.setStyleSheet(f"font-size:11px; font-weight:bold; color:{tier_color};")
        row.addWidget(score_lbl)
        self.star_btn = QPushButton("☆")
        self.star_btn.setFixedSize(22, 22)
        self.star_btn.setFlat(True)
        self.star_btn.setStyleSheet("font-size:14px; padding:0; margin:0;")
        self.star_btn.clicked.connect(lambda: self.starred_toggled.emit(self.idx))
        row.addWidget(self.star_btn)
        lay.addLayout(row)
        self._refresh_style()

    def resize_card(self, size: str) -> None:
        if size not in self.CARD_SIZE_PRESETS: return
        self._size = size
        w, h = self.CARD_SIZE_PRESETS[size]
        self.setFixedSize(w, h)
        self.img.setMinimumHeight(max(40, h - 50))
        self._refresh_style()

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
        self._refresh_style()

    def refresh_thumbnail(self) -> None:
        frame = self.cand.ensure_frame()
        if frame is not None:
            THUMBS.invalidate(id(self.cand))
            self.img.setPixmap(THUMBS.gallery(id(self.cand), frame))

    def _refresh_style(self) -> None:
        if self._selected: border, bg = C_TEXT, C_SURFACE
        elif self._multi_selected: border, bg = C_ACCENT, C_SURFACE
        elif self.cand.starred: border, bg = C_TEXT, C_SURFACE
        else: border, bg = "transparent", C_CARD
        self.setStyleSheet(f"QFrame {{ background:{bg}; border:2px solid {border}; border-radius:8px; }} QFrame:hover {{ border-color:{C_ACCENT}; }}")

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            if e.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
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
        act = m.exec(self.mapToGlobal(pos))
        if act == a_save: self.clicked.emit(self.idx)
        elif act == a_copy_img:
            frame = self.cand.ensure_frame()
            if frame is not None:
                QApplication.clipboard().setPixmap(bgr_to_qpixmap(frame))
        elif act == a_star: self.starred_toggled.emit(self.idx)
        elif act == a_reanalyze: self.reanalyze_requested.emit(self.idx)

class EmptyStateOverlay(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mode = "no_file"
        self._open_callback = None
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon = QLabel("🎬")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet("font-size: 64px;")
        lay.addWidget(self._icon)
        self._title = QLabel("No Video Loaded")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(f"font-size:18px; font-weight:bold; color:{C_TEXT};")
        lay.addWidget(self._title)
        self._hint = QLabel("Open a video file to begin (Ctrl+O)")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(f"color:{C_SUBTEXT}; font-size:12px;")
        lay.addWidget(self._hint)
        self._btn = QPushButton("  Open Video   ")
        self._btn.setObjectName("btnPrimary")
        self._btn.setFixedWidth(160)
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

    def _update_content(self) -> None:
        if self._mode == "no_file":
            self._icon.setText("🎬"); self._title.setText("No Video Loaded"); self._hint.setText("Open a video file to begin (Ctrl+O)"); self._btn.setVisible(True)
        elif self._mode == "no_analysis":
            self._icon.setText("🔍"); self._title.setText("Ready to Analyze"); self._hint.setText("Click Analyze in the toolbar to find thumbnails"); self._btn.setVisible(False)
        else:
            self._btn.setVisible(False)

    def paintEvent(self, e) -> None:
        bg = QColor(C_BG)
        bg.setAlpha(220)
        p = QPainter(self)
        p.fillRect(self.rect(), bg)
        p.end()
        super().paintEvent(e)

class TimelineHeatmap(QWidget):
    clicked = Signal(int)
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(56)
        self.setMaximumHeight(56)
        self._candidates, self._duration, self._hover_idx, self._selected_idx = [], 0.0, -1, -1
        self.setMouseTracking(True)

    def set_data(self, candidates: List[Candidate], duration: float) -> None:
        self._candidates, self._duration = list(candidates), max(duration, 0.001)
        self.update()

    def clear_data(self) -> None:
        self._candidates, self._duration = [], 0.0
        self.update()

    def _cell_rect(self, idx: int):
        if not self._candidates or idx < 0 or idx >= len(self._candidates): return None
        c = self._candidates[idx]
        w, h, margin = self.width(), self.height(), 4
        bar_w, bar_h = w - 2 * margin, h - 2 * margin
        x_norm = c.timestamp / self._duration
        cell_w = max(3, bar_w / max(len(self._candidates), 1))
        x = margin + x_norm * bar_w - cell_w / 2
        return QRectF(max(margin, x), margin, min(cell_w, bar_w), bar_h)

    def _hit_test(self, x: float, y: float) -> int:
        for i in range(len(self._candidates)):
            rect = self._cell_rect(i)
            if rect is not None and rect.contains(x, y): return i
        return -1

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor(C_CARD))
        if not self._candidates:
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Run analysis to see score heatmap")
            return
        margin, w, h = 4, self.width(), self.height()
        p.setPen(QPen(QColor(C_OVERLAY), 1))
        p.drawLine(margin, h - margin, w - margin, h - margin)
        for i, c in enumerate(self._candidates):
            rect = self._cell_rect(i)
            if rect is None: continue
            v = int(40 + (212 - 40) * max(0.0, min(1.0, c.total_score)))
            color = QColor(v, v, v)
            if i == self._hover_idx: color = color.lighter(130)
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(rect, 2, 2)
        if 0 <= self._selected_idx < len(self._candidates):
            rect = self._cell_rect(self._selected_idx)
            if rect is not None:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(C_TEXT), 2))
                p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 3, 3)

    def mouseMoveEvent(self, e) -> None:
        idx = self._hit_test(e.position().x(), e.position().y())
        if idx != self._hover_idx:
            self._hover_idx = idx
            if idx >= 0:
                c = self._candidates[idx]
                self.setToolTip(f"#{idx + 1} {format_time(c.timestamp)}\nScore: {c.total_score:.3f}")
            else:
                self.setToolTip("")
            self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            idx = self._hit_test(e.position().x(), e.position().y())
            if idx >= 0: self.clicked.emit(idx)

    def leaveEvent(self, e) -> None:
        self._hover_idx = -1
        self.update()

    def set_selected(self, idx: int) -> None:
        self._selected_idx = idx
        self.update()

# =====================================================================
# DIALOGS
# =====================================================================
class WeightsEditorDialog(QDialog):
    def __init__(self, parent, profile_name: str, weights: Dict[str, float], existing_profiles: List[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Algorithm Profile")
        self.setMinimumWidth(520)
        self._initial_weights = dict(weights)
        v = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Profile name:"))
        self.name_edit = QLineEdit(profile_name)
        row.addWidget(self.name_edit, stretch=1)
        v.addLayout(row)
        sliders_box = QGroupBox("Criteria Weights")
        sgrid = QGridLayout(sliders_box)
        self._sliders, self._value_labels = {}, {}
        for i, key in enumerate(sorted(CRIT_LABELS.keys())):
            sgrid.addWidget(QLabel(CRIT_LABELS[key]), i, 0)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(int(round(weights.get(key, 0.0) * 100)))
            slider.valueChanged.connect(self._on_changed)
            sgrid.addWidget(slider, i, 1)
            self._sliders[key] = slider
            val_lbl = QLabel(f"{weights.get(key, 0.0):.2f}")
            sgrid.addWidget(val_lbl, i, 2)
            self._value_labels[key] = val_lbl
        v.addWidget(sliders_box)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)
        self._on_changed()

    def _on_changed(self, *_) -> None:
        weights = self.get_weights()
        for key, slider in self._sliders.items():
            self._value_labels[key].setText(f"{weights.get(key, 0.0):.2f}")

    def get_weights(self) -> Dict[str, float]:
        raw = {k: s.value() / 100.0 for k, s in self._sliders.items() if s.value() > 0}
        total = sum(raw.values())
        if total == 0: return {k: 1.0 / len(self._sliders) for k in self._sliders}
        return {k: v / total for k, v in raw.items()}

    def get_profile_name(self) -> str:
        return self.name_edit.text().strip() or "Custom Profile"

class ShortcutHelpDialog(QDialog):
    SHORTCUTS = [
        ("File", [("Ctrl+O", "Open video"), ("Ctrl+S", "Save selected"), ("Ctrl+Shift+S", "Save starred"), ("Ctrl+E", "Contact sheet")]),
        ("Navigation", [("← / →", "Prev / Next"), ("F2", "Fit image"), ("Ctrl+= / -", "Zoom")]),
        ("Analysis", [("Space", "Run / Stop"), ("Esc", "Stop"), ("F1", "Help")]),
    ]
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        v = QVBoxLayout(self)
        for section_name, items in self.SHORTCUTS:
            group = QGroupBox(section_name)
            gl = QGridLayout(group)
            for i, (key, desc) in enumerate(items):
                gl.addWidget(QLabel(key), i, 0)
                gl.addWidget(QLabel(desc), i, 1)
            v.addWidget(group)
        btn = QPushButton("Close")
        btn.setObjectName("btnPrimary")
        btn.clicked.connect(self.accept)
        v.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)

class AboutDialog(QDialog):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.setWindowTitle("About")
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Video Thumbnail Picker v2.1"))
        v.addWidget(QLabel("Automatically finds the best frames using weighted metrics."))
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        v.addWidget(btn)

class ContactSheetDialog(QDialog):
    def __init__(self, parent, candidates: List[Candidate], video_name: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Contact Sheet")
        self._candidates, self._video_name = candidates, video_name
        v = QVBoxLayout(self)
        box = QGroupBox("Layout")
        gl = QGridLayout(box)
        gl.addWidget(QLabel("Columns:"), 0, 0)
        self.cols_spin = QSpinBox(); self.cols_spin.setRange(1, 10); self.cols_spin.setValue(4)
        gl.addWidget(self.cols_spin, 0, 1)
        self.chk_starred_only = QCheckBox("Starred only")
        gl.addWidget(self.chk_starred_only, 1, 0, 1, 2)
        v.addWidget(box)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._export)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def _get_selected(self) -> List[Candidate]:
        return [c for c in self._candidates if c.starred] if self.chk_starred_only.isChecked() else list(self._candidates)

    def _export(self) -> None:
        cands = self._get_selected()
        if not cands:
            QMessageBox.information(self, "No frames", "No frames to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Contact Sheet", f"contact_sheet_{self._video_name}.png", "PNG (*.png)")
        if not path: return
        try:
            cols, thumb_w, thumb_h = self.cols_spin.value(), 240, 135
            rows = (len(cands) + cols - 1) // cols
            sheet_w, sheet_h = cols * thumb_w + (cols + 1) * 10, rows * thumb_h + (rows + 1) * 10 + 36
            sheet = Image.new("RGB", (sheet_w, sheet_h), (23, 23, 23))
            draw = ImageDraw.Draw(sheet)
            for i, c in enumerate(cands):
                frame = c.ensure_frame()
                if frame is None: continue
                row, col = i // cols, i % cols
                x, y = 10 + col * (thumb_w + 10), 36 + 10 + row * (thumb_h + 10)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                sheet.paste(Image.fromarray(rgb).resize((thumb_w, thumb_h), Image.Resampling.LANCZOS), (x, y))
            sheet.save(path, "PNG")
            QMessageBox.information(self, "Exported", f"Saved to:\n{path}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

class PreferencesDialog(QDialog):
    def __init__(self, parent, *, theme, card_size, filename_template, auto_free_memory, save_quality, save_format, reanalyze_radius, reanalyze_samples) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        v = QVBoxLayout(self)
        app_box = QGroupBox("Appearance")
        app_lay = QVBoxLayout(app_box)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Theme:"))
        self.combo_theme = QComboBox(); self.combo_theme.addItems(["dark", "light"]); self.combo_theme.setCurrentText(theme)
        row1.addWidget(self.combo_theme, stretch=1)
        app_lay.addLayout(row1)
        v.addWidget(app_box)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        v.addWidget(btns)

    @property
    def theme(self) -> str: return self.combo_theme.currentText()

def save_candidates_to_json(path: str, candidates: list, video_path: str, video_info: dict) -> None:
    data = {
        "version": 1, "video_path": video_path, "video_info": video_info,
        "candidates": [
            {"timestamp": round(c.timestamp, 3), "total_score": round(c.total_score, 6),
             "breakdown": {k: round(float(v), 6) for k, v in c.breakdown.items()},
             "faces": [list(f) for f in c.faces], "starred": c.starred}
            for c in candidates
        ],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_candidates_from_json(path: str):
    with open(path, "r") as f:
        data = json.load(f)
    video_path, video_info = data.get("video_path", ""), data.get("video_info", {})
    cands = []
    for d in data.get("candidates", []):
        cands.append(Candidate(
            frame_bgr=None, timestamp=float(d["timestamp"]), total_score=float(d["total_score"]),
            breakdown={k: float(v) for k, v in d.get("breakdown", {}).items()},
            faces=[tuple(f) for f in d.get("faces", [])], starred=bool(d.get("starred", False)), video_path=video_path
        ))
    return cands, video_path, video_info

# =====================================================================
# MAIN WINDOW
# =====================================================================
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".wmv"}

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Video Thumbnail Picker")
        self.resize(1600, 950)
        self.setMinimumSize(1200, 720)
        self.setAcceptDrops(True)
        self.video_path, self.video_info, self.candidates, self.selected_idx = None, {}, [], -1
        self._worker, self._show_starred_only, self._score_threshold = None, False, SCORE_THRESHOLD_DEFAULT
        self._gallery_cards, self._all_profiles, self._append_mode = {}, {}, False
        self._analysis_start_time, self._eta_timer = 0.0, QTimer(self)
        self._eta_timer.timeout.connect(self._update_eta)
        self._card_size, self._theme = DEFAULT_CARD_SIZE, DEFAULT_THEME
        self._filename_template, self._auto_free_memory = DEFAULT_FILENAME_TEMPLATE, False
        self._multi_selected = set()
        self._ui()
        self._menu_bar()
        self._toolbar()
        self._shortcuts()
        self.setStyleSheet(STYLESHEET)
        self._restore_settings()

    def _ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(8)
        header = QFrame(); header.setObjectName("Card")
        header_lay = QHBoxLayout(header)
        title = QLabel("Video Thumbnail Picker"); title.setObjectName("LblTitle")
        header_lay.addWidget(title)
        header_lay.addStretch()
        self.header_file_lbl = QLabel("No file loaded")
        self.header_file_lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
        header_lay.addWidget(self.header_file_lbl)
        root.addWidget(header)
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(6)
        root.addWidget(self._splitter, stretch=1)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        self.preview_container = QFrame()
        self.preview_container.setStyleSheet(f"background:{C_CARD}; border-radius:8px;")
        pc_lay = QVBoxLayout(self.preview_container)
        pc_lay.setContentsMargins(0, 0, 0, 0)
        self.preview = ZoomablePreview()
        self.preview.setMinimumHeight(420)
        pc_lay.addWidget(self.preview)
        self.empty_overlay = EmptyStateOverlay(self.preview_container)
        self.empty_overlay.set_open_callback(self._open_file)
        pc_lay.addWidget(self.empty_overlay)
        left_layout.addWidget(self.preview_container, stretch=1)
        self.filmstrip = FilmstripTimeline()
        self.filmstrip.clicked.connect(self._seek_time)
        left_layout.addWidget(self.filmstrip)
        self.heatmap = TimelineHeatmap()
        self.heatmap.clicked.connect(self._select)
        left_layout.addWidget(self.heatmap)
        self._splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_widget.setMaximumWidth(520)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.addWidget(self._build_control_card())
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

        self.status_stage_lbl = QLabel("Ready")
        self.statusBar().addWidget(self.status_stage_lbl, 1)
        self.status_eta_lbl = QLabel("")
        self.statusBar().addWidget(self.status_eta_lbl)
        self.status_count_lbl = QLabel("0 candidates")
        self.statusBar().addPermanentWidget(self.status_count_lbl)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(240)
        self.progress.setVisible(False)
        self.progress.setFormat("%p%")
        self.statusBar().addPermanentWidget(self.progress)

    def _build_control_card(self) -> QFrame:
        card = QFrame(); card.setObjectName("Card")
        v = QVBoxLayout(card)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Algorithm"))
        self.combo_algo = QComboBox()
        self.combo_algo.currentTextChanged.connect(self._change_algo)
        row1.addWidget(self.combo_algo, stretch=1)
        self.btn_edit_weights = QPushButton("Edit…")
        self.btn_edit_weights.clicked.connect(self._edit_weights)
        row1.addWidget(self.btn_edit_weights)
        v.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Output"))
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(PRESETS.keys())
        row2.addWidget(self.combo_preset, stretch=1)
        v.addLayout(row2)
        row3 = QHBoxLayout()
        self.chk_scene = QCheckBox("Scene Detect")
        row3.addWidget(self.chk_scene)
        row3.addWidget(QLabel("Samples:"))
        self.spin_samples = QSpinBox(); self.spin_samples.setRange(20, 400); self.spin_samples.setValue(80)
        row3.addWidget(self.spin_samples)
        row3.addWidget(QLabel("Max:"))
        self.spin_cands = QSpinBox(); self.spin_cands.setRange(4, 60); self.spin_cands.setValue(15)
        row3.addWidget(self.spin_cands)
        row3.addStretch()
        v.addLayout(row3)
        row4 = QHBoxLayout()
        self.btn_save = QPushButton("  Save Selected   "); self.btn_save.setObjectName("btnGreen"); self.btn_save.clicked.connect(self._save)
        row4.addWidget(self.btn_save, stretch=1)
        self.btn_batch = QPushButton("  Save Starred   "); self.btn_batch.clicked.connect(self._batch_save)
        row4.addWidget(self.btn_batch, stretch=1)
        v.addLayout(row4)
        return card

    def _build_gallery_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        filter_row1 = QHBoxLayout()
        self.chk_starred = QCheckBox("Starred only")
        self.chk_starred.stateChanged.connect(self._on_filter_changed)
        filter_row1.addWidget(self.chk_starred)
        filter_row1.addStretch()
        filter_row1.addWidget(QLabel("Sort:"))
        self.combo_sort = QComboBox()
        for name, _, _ in SORT_OPTIONS: self.combo_sort.addItem(name)
        self.combo_sort.currentTextChanged.connect(self._on_sort_changed)
        filter_row1.addWidget(self.combo_sort)
        lay.addLayout(filter_row1)
        filter_row2 = QHBoxLayout()
        filter_row2.addWidget(QLabel("Min score:"))
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(0, 100)
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        filter_row2.addWidget(self.threshold_slider, stretch=1)
        self.threshold_lbl = QLabel("0.00")
        filter_row2.addWidget(self.threshold_lbl)
        lay.addLayout(filter_row2)
        self.gallery_area = QScrollArea()
        self.gallery_area.setWidgetResizable(True)
        self.gallery_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.gallery_container = QWidget()
        self.gallery_layout = QGridLayout(self.gallery_container)
        self.gallery_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.gallery_area.setWidget(self.gallery_container)
        lay.addWidget(self.gallery_area, stretch=1)
        self.tabs.addTab(tab, "Gallery")

    def _build_analysis_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.addWidget(QLabel("RGB Histogram"))
        self.histogram = HistogramWidget()
        lay.addWidget(self.histogram)
        lay.addWidget(QLabel("Score Breakdown"))
        self.breakdown = ScoreBreakdownWidget()
        lay.addWidget(self.breakdown, stretch=1)
        self.tabs.addTab(tab, "Analysis")

    def _build_info_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.addWidget(QLabel("VIDEO"))
        self.info_video_grid = self._build_info_grid([("File:", ""), ("Duration:", ""), ("Resolution:", ""), ("FPS:", ""), ("Total frames:", "")])
        lay.addWidget(self.info_video_grid)
        lay.addWidget(QLabel("SELECTED CANDIDATE"))
        self.info_cand_grid = self._build_info_grid([("Rank:", "—"), ("Timestamp:", "—"), ("Score:", "—"), ("Faces:", "—"), ("Sharpness:", "—"), ("Contrast:", "—"), ("Brightness:", "—"), ("Composition:", "—")])
        lay.addWidget(self.info_cand_grid)
        lay.addStretch()
        self.tabs.addTab(tab, "Info")

    def _build_info_grid(self, rows: List[tuple]) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background:{C_CARD}; border-radius:6px; }}")
        grid = QGridLayout(frame)
        for i, (label, value) in enumerate(rows):
            lbl = QLabel(label); lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
            val = QLabel(value); val.setStyleSheet(f"color:{C_TEXT}; font-size:11px;")
            grid.addWidget(lbl, i, 0); grid.addWidget(val, i, 1)
            setattr(self, f"_info_{label.rstrip(':').lower().replace(' ', '_')}", val)
        return frame

    def _menu_bar(self) -> None:
        mb = self.menuBar()
        file_menu = mb.addMenu("&File")
        self.act_open = QAction("&Open Video…", self); self.act_open.setShortcut("Ctrl+O"); self.act_open.triggered.connect(self._open_file)
        file_menu.addAction(self.act_open)
        self.act_quit = QAction("&Quit", self); self.act_quit.setShortcut("Ctrl+Q"); self.act_quit.triggered.connect(self.close)
        file_menu.addAction(self.act_quit)
        edit_menu = mb.addMenu("&Edit")
        self.act_edit_weights = QAction("Edit Algorithm &Weights…", self); self.act_edit_weights.triggered.connect(self._edit_weights)
        edit_menu.addAction(self.act_edit_weights)
        view_menu = mb.addMenu("&View")
        self.act_grid = QAction("&Rule-of-thirds Grid", self, checkable=True); self.act_grid.setShortcut("G"); self.act_grid.triggered.connect(lambda: self.preview.set_overlays(grid=self.act_grid.isChecked()))
        view_menu.addAction(self.act_grid)
        self.act_faces = QAction("&Face Overlay", self, checkable=True); self.act_faces.setShortcut("F"); self.act_faces.triggered.connect(lambda: self.preview.set_overlays(faces=self.act_faces.isChecked()))
        view_menu.addAction(self.act_faces)
        help_menu = mb.addMenu("&Help")
        self.act_shortcuts = QAction("&Keyboard Shortcuts", self); self.act_shortcuts.setShortcut("F1"); self.act_shortcuts.triggered.connect(lambda: ShortcutHelpDialog(self).exec())
        help_menu.addAction(self.act_shortcuts)
        self.act_about = QAction("&About", self); self.act_about.triggered.connect(lambda: AboutDialog(self).exec())
        help_menu.addAction(self.act_about)

    def _toolbar(self) -> None:
        tb = QToolBar("Main"); tb.setMovable(False); self.addToolBar(tb)
        self.btn_open = QPushButton("  Open Video"); self.btn_open.setObjectName("btnPrimary"); self.btn_open.clicked.connect(self._open_file)
        tb.addWidget(self.btn_open)
        self.btn_analyze = QPushButton("  Analyze"); self.btn_analyze.setEnabled(False); self.btn_analyze.clicked.connect(self._start_analysis)
        tb.addWidget(self.btn_analyze)
        self.btn_stop = QPushButton("  Stop"); self.btn_stop.setObjectName("btnRed"); self.btn_stop.setVisible(False); self.btn_stop.clicked.connect(self._stop_analysis)
        tb.addWidget(self.btn_stop)
        spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

    def _shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self, self._save)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self._batch_save)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self._nav(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self._nav(1))
        QShortcut(QKeySequence("Ctrl+="), self, self.preview.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self.preview.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self.preview.fit)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._toggle_analysis)
        QShortcut(QKeySequence(Qt.Key.Key_S), self, self._star_current)
        QShortcut(QKeySequence(Qt.Key.Key_G), self, lambda: self.act_grid.toggle())
        QShortcut(QKeySequence(Qt.Key.Key_F), self, lambda: self.act_faces.toggle())
        QShortcut(QKeySequence("Escape"), self, self._stop_analysis)

    def _restore_settings(self) -> None:
        SETTINGS.restore_window_state(self)
        sizes = SETTINGS.splitter_sizes()
        if sizes and len(sizes) == 2: self._splitter.setSizes(sizes)
        s = SETTINGS.restore_analysis_settings()
        self._all_profiles = dict(ALGORITHM_PROFILES)
        self._all_profiles.update(SETTINGS.custom_profiles)
        self.combo_algo.blockSignals(True)
        self.combo_algo.clear()
        for name in self._all_profiles: self.combo_algo.addItem(name)
        if s["algo"] in self._all_profiles: self.combo_algo.setCurrentText(s["algo"])
        self.combo_algo.blockSignals(False)
        if s["preset"] in PRESETS: self.combo_preset.setCurrentText(s["preset"])
        self.spin_samples.setValue(s["samples"])
        self.spin_cands.setValue(s["cands"])
        self.chk_scene.setChecked(s["scene"])
        if any(s["sort"] == name for name, _, _ in SORT_OPTIONS): self.combo_sort.setCurrentText(s["sort"])
        self._score_threshold = s["threshold"]
        self.threshold_slider.setValue(int(s["threshold"] * 100))
        self.threshold_lbl.setText(f"{s['threshold']:.2f}")

    def _save_settings(self) -> None:
        SETTINGS.save_window_state(self)
        SETTINGS.save_analysis_settings(algo=self.combo_algo.currentText(), preset=self.combo_preset.currentText(), samples=self.spin_samples.value(), cands=self.spin_cands.value(), scene=self.chk_scene.isChecked(), sort=self.combo_sort.currentText(), threshold=self._score_threshold)
        SETTINGS.sync()

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            for url in e.mimeData().urls():
                if Path(url.toLocalFile()).suffix.lower() in VIDEO_EXTS:
                    e.acceptProposedAction(); return
        e.ignore()

    def dropEvent(self, e: QDropEvent) -> None:
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).suffix.lower() in VIDEO_EXTS:
                self._open_file_path(path); e.acceptProposedAction(); return
        e.ignore()

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Video", SETTINGS.last_dir, "Video (*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.flv *.wmv);;All Files (*)")
        if path: self._open_file_path(path)

    def _open_file_path(self, path: str) -> None:
        if not Path(path).exists():
            QMessageBox.warning(self, "File not found", f"The file does not exist:\n{path}"); return
        self.video_path = path
        self.header_file_lbl.setText(Path(path).name)
        self.btn_analyze.setEnabled(True)
        SETTINGS.add_recent_file(path)
        SETTINGS.last_dir = str(Path(path).parent)
        self.candidates.clear()
        self._gallery_cards.clear()
        THUMBS.invalidate()
        self.selected_idx = -1
        self._multi_selected.clear()
        self._refresh_gallery()
        self.filmstrip.set_frames([])
        self.heatmap.clear_data()
        self.preview.scene().clear()
        self.empty_overlay.set_mode("no_analysis")

    def _toggle_analysis(self) -> None:
        if self._worker and self._worker.isRunning(): self._stop_analysis()
        else: self._start_analysis()

    def _start_analysis(self, append: bool = False, sample_times: Optional[List[float]] = None) -> None:
        if not self.video_path: return
        self._append_mode = append
        if not append:
            self.candidates.clear()
            self._gallery_cards.clear()
            THUMBS.invalidate()
            self.selected_idx = -1
            self._refresh_gallery()
        else:
            self._gallery_cards.clear()
        self.progress.setVisible(True); self.progress.setValue(0)
        self.status_stage_lbl.setText("Initializing…")
        self.btn_analyze.setVisible(False); self.btn_stop.setVisible(True); self.btn_open.setEnabled(False)
        self.empty_overlay.set_mode("hidden")
        self._analysis_start_time = time.monotonic()
        self._eta_timer.start(ETA_UPDATE_INTERVAL_MS)
        weights = self._all_profiles.get(self.combo_algo.currentText(), ALGORITHM_PROFILES["General (Balanced)"])
        self._worker = AnalysisThread(self.video_path, self.spin_samples.value(), weights, self.spin_cands.value(), self.chk_scene.isChecked(), sample_times_override=sample_times, skip_filmstrip=append)
        self._worker.stage_changed.connect(lambda t: self.status_stage_lbl.setText(t))
        self._worker.progress.connect(lambda c, t: self.progress.setValue(int(100 * c / t)) if t > 0 else None)
        self._worker.candidate_ready.connect(lambda c, _, __: QTimer.singleShot(0, lambda cand=c: self._add_candidate_main(cand)))
        self._worker.filmstrip_ready.connect(lambda frames: self.filmstrip.set_frames(frames) if frames else None)
        self._worker.finished_ok.connect(self._finish_analysis)
        self._worker.finished_err.connect(lambda msg: (self._finish_analysis([], {}), QMessageBox.critical(self, "Error", msg)))
        self._worker.start()

    def _stop_analysis(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait(1500)
        self._finish_analysis([], {})

    def _update_eta(self) -> None:
        if not self._analysis_start_time: return
        elapsed = time.monotonic() - self._analysis_start_time
        pct = self.progress.value()
        if pct > 0:
            total_est = elapsed / (pct / 100.0)
            eta = max(0, total_est - elapsed)
            self.status_eta_lbl.setText(f"⏱ {int(elapsed)}s elapsed / ~{int(eta)}s remaining")
        else:
            self.status_eta_lbl.setText(f"⏱ {int(elapsed)}s elapsed")

    def _add_candidate_main(self, cand: Candidate) -> None:
        self.candidates.append(cand)
        self.status_count_lbl.setText(f"{len(self.candidates)} candidates")
        self._make_card(cand)
        if self.selected_idx < 0: self._select(0)

    def _finish_analysis(self, cands: List[Candidate], info: Dict) -> None:
        self._eta_timer.stop()
        self.status_eta_lbl.setText("")
        if self._append_mode:
            if cands: self.candidates.extend(cands)
            self._apply_sort()
            self._apply_starred_state()
        else:
            if cands:
                self.candidates = cands
                self._gallery_cards.clear()
                THUMBS.invalidate()
            if info:
                self.video_info = info
                self._refresh_info_video(info)
            self._apply_starred_state()
        self.progress.setVisible(False)
        self.btn_stop.setVisible(False); self.btn_analyze.setVisible(True); self.btn_open.setEnabled(True)
        self.status_stage_lbl.setText("Finished")
        self._refresh_gallery()
        self.status_count_lbl.setText(f"{len(self.candidates)} candidates")
        if self.candidates: self._select(0)
        else: self.empty_overlay.set_mode("no_analysis")

    def _apply_starred_state(self) -> None:
        if not self.video_path: return
        data = ProjectState.load(self.video_path)
        starred_ts = data.get("starred_timestamps", [])
        if not starred_ts: return
        for c in self.candidates:
            if any(abs(c.timestamp - ts) < 0.05 for ts in starred_ts): c.starred = True

    def _save_starred_state(self) -> None:
        if self.video_path and self.candidates: ProjectState.save(self.video_path, self.candidates)

    def _make_card(self, cand: Candidate) -> Optional[GalleryCard]:
        if id(cand) in self._gallery_cards: return self._gallery_cards[id(cand)]
        try: real_idx = self.candidates.index(cand)
        except ValueError: return None
        card = GalleryCard(real_idx, cand, size=self._card_size)
        card.clicked.connect(self._select)
        card.starred_toggled.connect(self._toggle_star)
        card.reanalyze_requested.connect(self._reanalyze_idx)
        card.multi_select_toggled.connect(self._on_multi_select_toggled)
        if id(cand) in self._multi_selected: card.set_multi_selected(True)
        self._gallery_cards[id(cand)] = card
        return card

    def _apply_sort(self) -> None:
        if not self.candidates: return
        sort_name = self.combo_sort.currentText()
        for name, key, reverse in SORT_OPTIONS:
            if name == sort_name:
                if key is None: self.candidates.sort(key=lambda c: c.total_score, reverse=reverse)
                elif key == "__starred__": self.candidates.sort(key=lambda c: (not c.starred, -c.total_score))
                else: self.candidates.sort(key=lambda c: c.breakdown.get(key, 0.0) if key != "timestamp" else c.timestamp, reverse=reverse)
                break

    def _refresh_gallery(self) -> None:
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget(): item.widget().setParent(None)
        self._apply_sort()
        display = list(self.candidates)
        if self._show_starred_only: display = [c for c in display if c.starred]
        if self._score_threshold > 0: display = [c for c in display if c.total_score >= self._score_threshold]
        id_to_pos = {id(c): i for i, c in enumerate(self.candidates)}
        for i, c in enumerate(display):
            card = self._gallery_cards.get(id(c)) or self._make_card(c)
            if card is None: continue
            real_idx = id_to_pos.get(id(c), -1)
            if real_idx < 0: continue
            card.idx = real_idx
            card.set_selected(real_idx == self.selected_idx)
            card.refresh_star()
            card.set_multi_selected(id(c) in self._multi_selected)
            card.setParent(self.gallery_container)
            self.gallery_layout.addWidget(card, i // GALLERY_COLUMNS, i % GALLERY_COLUMNS)
        self.heatmap.set_data(self.candidates, self.video_info.get("duration", 0.0))
        self.heatmap.set_selected(self.selected_idx)

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

    def _select(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.candidates): return
        prev = self.selected_idx
        self.selected_idx = idx
        c = self.candidates[idx]
        frame = c.ensure_frame()
        if frame is None: return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        preset = PRESETS.get(self.combo_preset.currentText())
        if preset: pil = fit_crop_pil(pil, preset)
        data = pil.tobytes("raw", "RGB")
        qim = QImage(data, pil.width, pil.height, 3 * pil.width, QImage.Format.Format_RGB888)
        qim._np_buf = data
        self.preview.set_pixmap(QPixmap.fromImage(qim), c)
        self.empty_overlay.set_mode("hidden")
        self.histogram.set_data(frame)
        self.breakdown.set_scores(c.breakdown)
        self._refresh_info_cand(c)
        self.heatmap.set_selected(idx)
        if prev != idx:
            if 0 <= prev < len(self.candidates):
                prev_card = self._gallery_cards.get(id(self.candidates[prev]))
                if prev_card: prev_card.set_selected(False)
            cur_card = self._gallery_cards.get(id(c))
            if cur_card: cur_card.set_selected(True)

    def _toggle_star(self, idx: int) -> None:
        if 0 <= idx < len(self.candidates):
            self.candidates[idx].starred = not self.candidates[idx].starred
            card = self._gallery_cards.get(id(self.candidates[idx]))
            if card: card.refresh_star()
            if self._show_starred_only and not self.candidates[idx].starred: self._refresh_gallery()
            self._save_starred_state()

    def _star_current(self) -> None:
        if 0 <= self.selected_idx < len(self.candidates): self._toggle_star(self.selected_idx)

    def _nav(self, d: int) -> None:
        if not self.candidates: return
        self._select((self.selected_idx + d) % len(self.candidates))

    def _seek_time(self, ts: float) -> None:
        if not self.video_path: return
        cap = cv2.VideoCapture(self.video_path)
        try:
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ret, frame = cap.read()
        finally:
            cap.release()
        if not ret or frame is None: return
        if not prefilter_frame(frame): return
        w = self._all_profiles.get(self.combo_algo.currentText(), ALGORITHM_PROFILES["General (Balanced)"])
        face_score, faces = score_faces(frame)
        small, gray = downscale_for_scoring(frame, 720)
        scores = {n: s(small, gray) for n, s in SCORERS.items()}
        scores["faces"] = face_score
        total = sum(scores.get(k, 0.0) * w.get(k, 0.0) for k in w)
        cand = Candidate(frame_bgr=frame, timestamp=float(ts), total_score=total, breakdown=scores, faces=faces, video_path=self.video_path)
        self.candidates.insert(0, cand)
        self._refresh_gallery()
        self._select(0)

    def _reanalyze_idx(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.candidates): return
        cand = self.candidates[idx]
        center = cand.timestamp
        radius = SETTINGS.reanalyze_radius
        n = SETTINGS.reanalyze_samples
        times = list(np.linspace(max(0, center - radius), center + radius, n))
        self._start_analysis(append=True, sample_times=times)

    def _refresh_info_video(self, info: Dict) -> None:
        if not info: return
        path = info.get("path", "")
        self._info_file.setText(Path(path).name if path else "—")
        self._info_duration.setText(format_duration(info.get("duration", 0)))
        w, h = info.get("width"), info.get("height")
        self._info_resolution.setText(f"{w}×{h}" if w and h else "—")
        fps = info.get("fps")
        self._info_fps.setText(f"{fps:.2f}" if fps else "—")
        tf = info.get("total_frames")
        self._info_total_frames.setText(str(tf) if tf else "—")

    def _refresh_info_cand(self, cand: Optional[Candidate]) -> None:
        all_keys = ["rank", "timestamp", "score", "faces", "sharpness", "contrast", "brightness", "composition"]
        if cand is None:
            for k in all_keys:
                attr = getattr(self, f"_info_{k}", None)
                if attr: attr.setText("—")
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

    def _change_algo(self, name: str) -> None:
        if not self.candidates: return
        w = self._all_profiles.get(name, ALGORITHM_PROFILES["General (Balanced)"])
        for c in self.candidates:
            c.total_score = sum(c.breakdown.get(k, 0.0) * w.get(k, 0.0) for k in w)
        self._apply_sort()
        self._gallery_cards.clear()
        self._refresh_gallery()
        if 0 <= self.selected_idx < len(self.candidates): self._select(self.selected_idx)

    def _edit_weights(self) -> None:
        name = self.combo_algo.currentText()
        weights = self._all_profiles.get(name, {})
        dlg = WeightsEditorDialog(self, name, weights, list(self._all_profiles.keys()))
        if dlg.exec() == WeightsEditorDialog.DialogCode.Accepted:
            new_name = dlg.get_profile_name()
            new_weights = dlg.get_weights()
            self._all_profiles[new_name] = new_weights
            if new_name not in ALGORITHM_PROFILES: SETTINGS.save_custom_profile(new_name, new_weights)
            self.combo_algo.blockSignals(True)
            if self.combo_algo.findText(new_name) < 0: self.combo_algo.addItem(new_name)
            self.combo_algo.setCurrentText(new_name)
            self.combo_algo.blockSignals(False)
            self._change_algo(new_name)

    def _output_dir(self) -> Path:
        out = Path.cwd() / "thumbnails"
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _save(self) -> None:
        if self.selected_idx < 0 or self.selected_idx >= len(self.candidates): return
        cand = self.candidates[self.selected_idx]
        out_dir = self._output_dir()
        rank = self.selected_idx + 1
        fname = self._format_filename(cand, rank)
        self._save_image(cand, path=str(out_dir / fname))

    def _format_filename(self, cand: Candidate, rank: int) -> str:
        video_name = Path(self.video_path).stem if self.video_path else "video"
        preset_name = self.combo_preset.currentText()
        try:
            return self._filename_template.format(
                video=video_name, timestamp=format_time(cand.timestamp).replace(":", "-"),
                ts_seconds=f"{cand.timestamp:.3f}", score=f"{cand.total_score:.3f}",
                rank=rank, preset=preset_name,
            )
        except (KeyError, ValueError):
            return f"thumb_{format_time(cand.timestamp).replace(':', '-')}.jpg"

    def _batch_save(self) -> None:
        starred = [c for c in self.candidates if c.starred]
        if not starred:
            QMessageBox.information(self, "Info", "No starred images to save."); return
        folder = str(self._output_dir())
        for i, c in enumerate(starred, start=1):
            self._save_image(c, path=os.path.join(folder, self._format_filename(c, i)))

    def _save_image(self, cand: Candidate, path: Optional[str] = None) -> None:
        frame = cand.ensure_frame()
        if frame is None:
            QMessageBox.critical(self, "Save failed", "Could not load the frame from disk."); return
        pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        preset = PRESETS.get(self.combo_preset.currentText())
        if preset: pil = fit_crop_pil(pil, preset)
        if not path:
            rank = self.selected_idx + 1 if self.candidates and cand in self.candidates else 1
            path = str(self._output_dir() / self._format_filename(cand, rank))
        try:
            ext = Path(path).suffix.lower()
            if ext in (".png",): pil.save(path, "PNG", optimize=True)
            elif ext in (".webp",): pil.save(path, "WEBP", quality=SETTINGS.save_quality)
            else: pil.save(path, "JPEG", quality=SETTINGS.save_quality)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def _on_multi_select_toggled(self, idx: int, _ctrl: bool) -> None:
        if idx < 0 or idx >= len(self.candidates): return
        cand = self.candidates[idx]
        if id(cand) in self._multi_selected: self._multi_selected.discard(id(cand))
        else: self._multi_selected.add(id(cand))
        card = self._gallery_cards.get(id(cand))
        if card: card.set_multi_selected(id(cand) in self._multi_selected)

    def closeEvent(self, e) -> None:
        self._save_settings()
        self._save_starred_state()
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait(2000)
        super().closeEvent(e)

# =====================================================================
# ENTRY POINT
# =====================================================================
def main() -> int:
    logger.info("Initializing application…")
    app = QApplication(sys.argv)
    app.setOrganizationName("ThumbnailPicker")
    app.setApplicationName("Video Thumbnail Picker")
    app.setApplicationVersion("2.1")
    try:
        _get_cascades()
    except Exception as e:
        logger.warning(f"Could not pre-warm cascades: {e}")
    win = MainWindow()
    win.show()
    logger.info("GUI launched. Ready for input.")
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())