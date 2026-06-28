"""Video Thumbnail Picker — Custom Widgets"""

from __future__ import annotations

import math
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from PyQt6.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QRectF, QPoint,
)
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QPen,
    QWheelEvent, QMouseEvent, QPainterPath,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QProgressBar, QScrollArea,
    QFileDialog, QFrame,
    QGraphicsView, QGraphicsScene,
    QSlider, QCheckBox, QMenu, QGridLayout,
    QGraphicsOpacityEffect, QDialog, QLineEdit,
)

from VideoThumbnailPicker.old.scoring import (
    PRESETS, DEFAULT_CANDIDATES, DEFAULT_SAMPLES,
    WEIGHTS_DEFAULT, WEIGHT_PROFILES, CRIT_LABELS,
    C_BG, C_SURFACE, C_CARD, C_OVERLAY, C_TEXT, C_SUBTEXT,
    C_BLUE, C_GREEN, C_YELLOW, C_PEACH, C_RED, C_MAUVE, C_TEAL, C_LAVENDER, C_PINK,
    Candidate,
)

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
    # Guard against rounding to zero or smaller than target
    nw = max(nw, tw)
    nh = max(nh, th)
    img = img.resize((nw, nh), Image.LANCZOS)
    return img.crop(((nw - tw) // 2, (nh - th) // 2,
                     (nw - tw) // 2 + tw, (nh - th) // 2 + th))

def _fmt_time(t):
    mm, ss = divmod(int(t), 60)
    ms = int((t % 1) * 1000)
    return f"{mm:02d}:{ss:02d}.{ms:03d}"

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
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self.fitInView(self._item, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = 1.0
        self.zoom_changed.emit(self._zoom)

    def _stop_anim(self):
        """Safely stop the current animation, handling the case where
        Qt has already deleted the underlying C++ object (DeleteWhenStopped)."""
        if self._anim is not None:
            try:
                self._anim.stop()
            except RuntimeError:
                pass
            self._anim = None

    def set_pixmap_animated(self, pixmap: QPixmap):
        """Fade out, swap, fade in."""
        self._stop_anim()
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(100)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.3)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._anim.finished.connect(lambda: self._swap_and_fade_in(pixmap))
        self._anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _swap_and_fade_in(self, pixmap: QPixmap):
        self.set_pixmap(pixmap)
        self._stop_anim()
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

