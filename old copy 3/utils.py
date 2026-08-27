"""Utility helpers: time formatting, cv2 ⇄ Qt conversions, thumbnail caching.

Centralising the cv2→QImage/QPixmap conversions here means we can:
  * avoid leaking numpy buffers (QImage keeps a reference to the buffer)
  * cache thumbnails so re-rendering the gallery is essentially free
  * keep main_window.py focused on layout/orchestration
"""
from __future__ import annotations

import threading
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPixmap

from config import (
    GALLERY_THUMB_W, GALLERY_THUMB_H,
    FILMSTRIP_THUMB_H,
    COMPARE_THUMB_W, COMPARE_THUMB_H,
)

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
        self._compare: Dict[int, QPixmap] = {}

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

    def compare(self, cand_id: int, bgr: np.ndarray) -> QPixmap:
        with self._lock:
            pm = self._compare.get(cand_id)
            if pm is None or pm.isNull():
                pm = scaled_qpixmap(bgr, COMPARE_THUMB_W, COMPARE_THUMB_H)
                self._compare[cand_id] = pm
            return pm

    def invalidate(self, cand_id: Optional[int] = None) -> None:
        with self._lock:
            if cand_id is None:
                self._gallery.clear()
                self._filmstrip.clear()
                self._compare.clear()
            else:
                self._gallery.pop(cand_id, None)
                self._filmstrip.pop(cand_id, None)
                self._compare.pop(cand_id, None)


# Module-level singleton
THUMBS = ThumbnailCache()


# ────────────────────────────────────────────────────────────────────────────
# Image helpers used by save path
# ────────────────────────────────────────────────────────────────────────────
def fit_crop_pil(pil_img, target: Tuple[int, int]):
    """Resize-and-center-crop a PIL image to fill ``target`` (cover fit)."""
    from PIL import Image  # local import — only needed on the save path
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
