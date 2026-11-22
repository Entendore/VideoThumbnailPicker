"""Streaming Thumbnail Picker — professional LIVE overlay tool.

Features:
  * Multi-image strip with cycling, reorder (drag), and remove
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
import sys
import math
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from PySide6.QtCore import (
    Qt, QRect, QRectF, QSize, QPoint, Signal, QPointF,
    QMimeData,
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
# Preview Canvas  (zoom, pan, drag badge, right-click menu)
# ══════════════════════════════════════════════════════════════════════════════

class PreviewCanvas(QWidget):
    """Main preview area with zoom, pan, and draggable badge."""

    zoom_changed = Signal(float)
    badge_moved = Signal(float, float)   # normalised x, y
    context_menu_requested = Signal(QPointF)
    images_dropped = Signal(list)         # list[str] paths
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
                       "Drop images here  |  Ctrl+O to open  |  Ctrl+V to paste")
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
            if any(u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() in exts
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
                self.images_dropped.emit(paths)
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

        self._controls = ControlPanel(self._badge, self._undo)
        mid.addWidget(self._controls)
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

    def _connect(self) -> None:
        self._strip.current_changed.connect(self._on_index_changed)
        self._controls.badge_changed.connect(self._refresh)
        self._canvas.badge_moved.connect(self._on_badge_dragged)
        self._canvas.context_menu_requested.connect(self._show_context_menu)
        self._canvas.images_dropped.connect(self._load_files)
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
        default = f"live_{self._badge.text.lower()}.png"
        path, _ = QFileDialog.getSaveFileName(self, "Save Thumbnail", default,
                                               "PNG (*.png);;JPEG (*.jpg *.jpeg);;WebP (*.webp)")
        if path and composite.save(path):
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
            name = f"live_{i + 1:03d}.png"
            path = str(Path(folder) / name)
            if composite.save(path):
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