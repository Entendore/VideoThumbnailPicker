"""Custom widgets: preview canvas, histogram, score breakdown, filmstrip,
gallery card, empty-state overlay.

Layout / UX improvements over the original:
  * ZoomablePreview supports wheel-zoom and pan with the middle mouse button,
    plus grid / face-overlay toggles drawn in cosmetic (screen-space) pens.
  * HistogramWidget pre-builds a QPainterPath per channel so paint events
    stay cheap even on resize.
  * ScoreBreakdownWidget uses a clean horizontal-bar layout with dynamic
    colour thresholds and proper label widths.
  * FilmstripTimeline now shows timestamp labels under each thumb and uses
    a hover highlight.
  * GalleryCard is self-contained: it owns its thumbnail (from the shared
    cache), its star button, and its selected / starred styling, so the
    parent window can update it in-place instead of rebuilding the gallery.
    Emits ``reanalyze_requested(idx)`` from the right-click context menu.
  * EmptyStateOverlay sits on top of the preview area when no video is
    loaded and shows a friendly call-to-action.
"""
from __future__ import annotations

from typing import List, Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal, QRectF, QPoint
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QPen, QPainterPath, QMouseEvent,
)
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame,
    QScrollArea, QGraphicsView, QGraphicsScene, QMenu, QSizePolicy,
)

from config import (
    C_CARD, C_OVERLAY, C_SURFACE, C_TEXT, C_SUBTEXT,
    C_GREEN, C_RED, C_BLUE, C_YELLOW, C_LAVENDER, C_TEAL, C_PEACH,
    CRIT_LABELS, GALLERY_THUMB_W, GALLERY_THUMB_H,
)
from analysis import Candidate
from utils import THUMBS, format_time, bgr_to_qpixmap, scaled_qpixmap


# ────────────────────────────────────────────────────────────────────────────
# Preview canvas
# ────────────────────────────────────────────────────────────────────────────
class ZoomablePreview(QGraphicsView):
    """Pannable / zoomable image canvas with optional grid + face overlays."""

    def __init__(self) -> None:
        super().__init__()
        self._zoom = 1.0
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("background: transparent; border: none;")
        self._pixmap_item = None

        self.show_grid: bool = False
        self.show_faces: bool = False
        self._current_cand: Optional[Candidate] = None

    # -- public API --------------------------------------------------------
    def set_pixmap(self, pm: QPixmap, cand: Optional[Candidate] = None) -> None:
        self.scene().clear()
        self._pixmap_item = self.scene().addPixmap(pm)
        self.scene().setSceneRect(QRectF(pm.rect()))
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._current_cand = cand
        self._zoom = 1.0
        self.viewport().update()

    def set_overlays(self, *, grid: Optional[bool] = None,
                     faces: Optional[bool] = None) -> None:
        if grid is not None:
            self.show_grid = grid
        if faces is not None:
            self.show_faces = faces
        self.viewport().update()

    # -- zoom & pan --------------------------------------------------------
    def wheelEvent(self, e) -> None:  # type: ignore[override]
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = e.angleDelta().y() / 120.0
            factor = 1.2 ** delta
            self.scale(factor, factor)
            self._zoom *= factor
        else:
            super().wheelEvent(e)

    def zoom_in(self) -> None:
        self.scale(1.2, 1.2)
        self._zoom *= 1.2

    def zoom_out(self) -> None:
        self.scale(1 / 1.2, 1 / 1.2)
        self._zoom /= 1.2

    def fit(self) -> None:
        if self._pixmap_item is not None:
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = 1.0

    # -- overlays ----------------------------------------------------------
    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        if self._pixmap_item is None:
            return
        painter.save()

        if self.show_grid:
            w = self._pixmap_item.pixmap().width()
            h = self._pixmap_item.pixmap().height()
            pen_grid = QPen(QColor(255, 255, 255, 90), 1)
            pen_grid.setCosmetic(True)
            painter.setPen(pen_grid)
            for i in range(1, 3):
                painter.drawLine(int(w * i / 3), 0, int(w * i / 3), h)
                painter.drawLine(0, int(h * i / 3), w, int(h * i / 3))
            # rule-of-thirds intersections (slightly brighter dots)
            painter.setBrush(QColor(255, 255, 255, 160))
            painter.setPen(Qt.PenStyle.NoPen)
            for fx in (1 / 3, 2 / 3):
                for fy in (1 / 3, 2 / 3):
                    painter.drawEllipse(QPoint(int(w * fx), int(h * fy)), 3, 3)

        if self.show_faces and self._current_cand is not None:
            pen = QPen(QColor(C_GREEN), 3)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for (x, y, fw, fh) in self._current_cand.faces:
                painter.drawRect(int(x), int(y), int(fw), int(fh))

        painter.restore()


# ────────────────────────────────────────────────────────────────────────────
# RGB histogram
# ────────────────────────────────────────────────────────────────────────────
class HistogramWidget(QWidget):
    """RGB channel histogram with semi-transparent filled curves."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(120)
        self._hist_data: Optional[List[np.ndarray]] = None
        self._paths: List[QPainterPath] = []

    def set_data(self, bgr: Optional[np.ndarray]) -> None:
        if bgr is None or bgr.size == 0:
            self._hist_data = None
            self._paths = []
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
        if not self._hist_data:
            return
        w, h = self.width(), self.height()
        margin = 8
        gw, gh = w - 2 * margin, h - 2 * margin
        for hist in self._hist_data:
            path = QPainterPath()
            path.moveTo(margin, h - margin)
            for i, val in enumerate(hist):
                x = margin + (i / 255.0) * gw
                y = h - margin - float(val) * gh
                path.lineTo(x, y)
            path.lineTo(margin + gw, h - margin)
            self._paths.append(path)

    def resizeEvent(self, e) -> None:  # type: ignore[override]
        super().resizeEvent(e)
        self._rebuild_paths()
        self.update()

    def paintEvent(self, e) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C_CARD))
        p.setPen(QPen(QColor(C_OVERLAY), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if not self._paths:
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data")
            return
        colors = [C_BLUE, C_GREEN, C_RED]
        for idx, path in enumerate(self._paths):
            fill = QColor(colors[idx]); fill.setAlpha(90)
            p.fillPath(path, fill)
            p.setPen(QColor(colors[idx]))
            p.drawPath(path)


# ────────────────────────────────────────────────────────────────────────────
# Score breakdown bar chart
# ────────────────────────────────────────────────────────────────────────────
class ScoreBreakdownWidget(QWidget):
    """Horizontal bars for each scoring criterion, coloured by threshold."""

    def __init__(self) -> None:
        super().__init__()
        self._scores: Dict[str, float] = {}
        self.setMinimumHeight(260)

    def set_scores(self, scores: Optional[Dict[str, float]]) -> None:
        self._scores = scores or {}
        self.update()

    def _bar_color(self, val: float) -> str:
        if val > 0.7:  return C_GREEN
        if val < 0.3:  return C_RED
        return C_BLUE

    def paintEvent(self, e) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C_CARD))
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if not self._scores:
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No candidate selected")
            return

        keys = sorted(k for k in self._scores if k in CRIT_LABELS)
        if not keys:
            return

        bar_h = 14
        spacing = 6
        label_w = 70
        value_w = 38
        margin_x = 10
        margin_y = 10
        bar_x = margin_x + label_w
        bar_w = max(40, self.width() - bar_x - value_w - margin_x)

        p.setFont(QFont("Segoe UI", 9))
        for i, k in enumerate(keys):
            y = margin_y + i * (bar_h + spacing)
            val = float(self._scores.get(k, 0.0))

            # Label
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(margin_x, y, label_w - 6, bar_h,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       CRIT_LABELS.get(k, k))

            # Track
            p.setBrush(QColor(C_OVERLAY))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(bar_x, y, bar_w, bar_h), 4, 4)

            # Fill
            fill_w = max(0.0, min(bar_w * val, bar_w))
            if fill_w > 0:
                p.setBrush(QColor(self._bar_color(val)))
                p.drawRoundedRect(QRectF(bar_x, y, fill_w, bar_h), 4, 4)

            # Value
            p.setPen(QColor(C_TEXT))
            p.drawText(bar_x + bar_w + 4, y, value_w, bar_h,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       f"{val:.2f}")


# ────────────────────────────────────────────────────────────────────────────
# Filmstrip timeline
# ────────────────────────────────────────────────────────────────────────────
class FilmstripTimeline(QScrollArea):
    """Horizontal scrolling filmstrip. Click a thumb to seek to that timestamp."""
    clicked = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(100)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"QScrollArea {{ background:{C_OVERLAY}; border-radius:8px; border:none; }}")

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.lay = QHBoxLayout(self.container)
        self.lay.setContentsMargins(6, 4, 6, 4)
        self.lay.setSpacing(4)
        self.lay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setWidget(self.container)

    def set_frames(self, frames: List[tuple]) -> None:
        # Clear existing widgets
        while self.lay.count():
            item = self.lay.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.deleteLater()

        if not frames:
            return

        for t, bgr in frames:
            if bgr is None or bgr.size == 0:
                continue
            cell = _FilmstripCell(t, bgr)
            cell.clicked.connect(self.clicked.emit)
            self.lay.addWidget(cell)


class _FilmstripCell(QFrame):
    """One thumbnail cell in the filmstrip, with timestamp tooltip + hover."""
    clicked = Signal(float)

    def __init__(self, t: float, bgr: np.ndarray) -> None:
        super().__init__()
        self._t = t
        self.setFixedSize(96, 84)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(format_time(t))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)

        lbl = QLabel()
        lbl.setPixmap(bgr_to_qpixmap(bgr).scaled(
            92, 64, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)

        ts_lbl = QLabel(format_time(t))
        ts_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ts_lbl.setStyleSheet(
            f"color:{C_TEXT}; background:{C_SURFACE}; border-radius:3px; "
            "padding:1px 4px; font-size:10px; font-family:'JetBrains Mono','Consolas',monospace;"
        )
        lay.addWidget(ts_lbl)

        self._refresh_style(False)

    def _refresh_style(self, hovered: bool) -> None:
        border = C_BLUE if hovered else "transparent"
        self.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:2px solid {border}; border-radius:6px; }}"
        )

    def enterEvent(self, e) -> None:  # type: ignore[override]
        self._refresh_style(True)

    def leaveEvent(self, e) -> None:  # type: ignore[override]
        self._refresh_style(False)

    def mousePressEvent(self, e: QMouseEvent) -> None:  # type: ignore[override]
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._t)


# ────────────────────────────────────────────────────────────────────────────
# Gallery card
# ────────────────────────────────────────────────────────────────────────────
class GalleryCard(QFrame):
    """A single candidate tile in the gallery grid.

    Emits ``clicked(idx)`` on left-click, ``starred_toggled(idx)`` when
    the star button is toggled, and ``reanalyze_requested(idx)`` from the
    right-click context menu. Supports Ctrl/Shift-click multi-selection
    via the ``multi_select_toggled`` signal. The parent window updates
    ``selected`` / ``starred`` directly instead of rebuilding the gallery.

    Card size is controlled by the ``size`` argument: "Small", "Medium",
    or "Large" (see ``CARD_SIZE_PRESETS``).
    """
    clicked = Signal(int)
    starred_toggled = Signal(int)
    reanalyze_requested = Signal(int)
    multi_select_toggled = Signal(int, bool)  # (idx, ctrl_or_shift_held)

    CARD_SIZE_PRESETS = {
        "Small":  (160, 95),
        "Medium": (200, 110),
        "Large":  (260, 145),
    }

    def __init__(self, idx: int, cand: Candidate, size: str = "Medium") -> None:
        super().__init__()
        self.idx = idx
        self.cand = cand
        self._selected = False
        self._multi_selected = False
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
        # Pull from the shared thumbnail cache — avoids re-converting on every refresh
        frame = cand.ensure_frame() if hasattr(cand, "ensure_frame") else cand.frame_bgr
        if frame is not None:
            pm = THUMBS.gallery(id(cand), frame)
            self.img.setPixmap(pm)
        self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img.setMinimumHeight(max(40, h - 50))
        lay.addWidget(self.img, stretch=1)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        rank_lbl = QLabel(f"#{idx + 1}")
        rank_lbl.setStyleSheet(f"color:{C_LAVENDER}; font-weight:bold; font-size:11px;")
        row.addWidget(rank_lbl)

        ts_lbl = QLabel(format_time(cand.timestamp))
        ts_lbl.setStyleSheet(
            "font-size:10px; font-family:'JetBrains Mono','Consolas',monospace; color:" + C_SUBTEXT + ";"
        )
        row.addWidget(ts_lbl)
        row.addStretch()

        score_lbl = QLabel(f"{cand.total_score:.2f}")
        score_lbl.setStyleSheet(
            f"font-size:11px; font-weight:bold; color:{C_GREEN}; "
            "font-family:'JetBrains Mono','Consolas',monospace;"
        )
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
        """Change the card's size preset. Caller is responsible for re-laying out."""
        if size not in self.CARD_SIZE_PRESETS:
            return
        self._size = size
        w, h = self.CARD_SIZE_PRESETS[size]
        self.setFixedSize(w, h)
        self.img.setMinimumHeight(max(40, h - 50))
        self._refresh_style()

    # -- public state updates ----------------------------------------------
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
        self.star_btn.setStyleSheet(
            f"color:{C_YELLOW}; font-size:14px; padding:0; margin:0;"
            if self.cand.starred else "font-size:14px; padding:0; margin:0;"
        )
        self._refresh_style()

    def refresh_thumbnail(self) -> None:
        """Re-fetch the thumbnail (e.g. after the frame was re-loaded from disk)."""
        frame = self.cand.ensure_frame() if hasattr(self.cand, "ensure_frame") else self.cand.frame_bgr
        if frame is not None:
            # Invalidate cache for this candidate so we re-generate the thumb
            THUMBS.invalidate(id(self.cand))
            pm = THUMBS.gallery(id(self.cand), frame)
            self.img.setPixmap(pm)

    # -- internal ----------------------------------------------------------
    def _refresh_style(self) -> None:
        if self._selected:
            border, bg = C_BLUE, C_SURFACE
        elif self._multi_selected:
            border, bg = C_TEAL, C_SURFACE
        elif self.cand.starred:
            border, bg = C_YELLOW, C_SURFACE
        else:
            border, bg = "transparent", C_CARD
        self.setStyleSheet(
            f"QFrame {{ background:{bg}; border:2px solid {border}; border-radius:8px; }}"
            "QFrame:hover {{ border-color:" + C_LAVENDER + "; }}"
        )

    def mousePressEvent(self, e: QMouseEvent) -> None:  # type: ignore[override]
        if e.button() == Qt.MouseButton.LeftButton:
            if e.modifiers() & (Qt.KeyboardModifier.ControlModifier |
                                Qt.KeyboardModifier.ShiftModifier):
                self.multi_select_toggled.emit(self.idx, True)
            else:
                self.clicked.emit(self.idx)

    def _ctx_menu(self, pos) -> None:
        m = QMenu(self)
        a_save = m.addAction("Save this frame…")
        a_star = m.addAction("Unstar" if self.cand.starred else "Star")
        m.addSeparator()
        a_reanalyze = m.addAction("Re-analyze ±2s around this frame")
        m.addSeparator()
        a_copy_ts = m.addAction("Copy timestamp")
        act = m.exec(self.mapToGlobal(pos))
        if act == a_save:
            self.clicked.emit(self.idx)
        elif act == a_star:
            self.starred_toggled.emit(self.idx)
        elif act == a_reanalyze:
            self.reanalyze_requested.emit(self.idx)
        elif act == a_copy_ts:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(f"{self.cand.timestamp:.3f}")


# ────────────────────────────────────────────────────────────────────────────
# Empty-state overlay
# ────────────────────────────────────────────────────────────────────────────
class EmptyStateOverlay(QWidget):
    """A translucent overlay shown on top of the preview when no video is loaded.

    Shows a large icon, a headline, a hint, and an optional call-to-action
    button. Set ``mode`` to one of:
      * ``"no_file"``  — no video loaded
      * ``"no_analysis"`` — video loaded but no candidates yet
      * ``"hidden"``   — hide the overlay
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._mode = "no_file"
        self._open_callback = None

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(12)

        self._icon = QLabel("🎬")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet("font-size: 64px;")
        lay.addWidget(self._icon)

        self._title = QLabel("No Video Loaded")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"font-size:18px; font-weight:bold; color:{C_LAVENDER};"
        )
        lay.addWidget(self._title)

        self._hint = QLabel("Open a video file to begin  (Ctrl+O)")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(f"color:{C_SUBTEXT}; font-size:12px;")
        lay.addWidget(self._hint)

        self._btn = QPushButton("  Open Video  ")
        self._btn.setObjectName("btnPrimary")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setFixedWidth(160)
        # Centre the button
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
        self.update()

    def _update_content(self) -> None:
        if self._mode == "no_file":
            self._icon.setText("🎬")
            self._title.setText("No Video Loaded")
            self._hint.setText("Open a video file to begin  (Ctrl+O)")
            self._btn.setVisible(True)
        elif self._mode == "no_analysis":
            self._icon.setText("🔍")
            self._title.setText("Ready to Analyze")
            self._hint.setText("Click Analyze in the toolbar to find thumbnails")
            self._btn.setVisible(False)
        else:
            self._btn.setVisible(False)

    def paintEvent(self, e) -> None:  # type: ignore[override]
        from PySide6.QtGui import QPainter, QColor
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(30, 30, 46, 220))  # C_BG with alpha
        p.end()
        super().paintEvent(e)


# ────────────────────────────────────────────────────────────────────────────
# Timeline score heatmap
# ────────────────────────────────────────────────────────────────────────────
class TimelineHeatmap(QWidget):
    """A horizontal bar showing each candidate's score as a coloured cell.

    Cells are positioned by timestamp (X axis) and coloured by score
    (red → yellow → green). Clicking a cell selects that candidate;
    hovering shows a tooltip with timestamp + score.

    This is the quickest way to spot clusters of high-quality frames
    across the whole video duration.
    """

    clicked = Signal(int)  # candidate index

    # Card-size presets (width, height) for the gallery
    CARD_SIZE_PRESETS = {
        "Small":  (160, 95),
        "Medium": (200, 110),
        "Large":  (260, 145),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(56)
        self.setMaximumHeight(56)
        self._candidates: List[Candidate] = []
        self._duration: float = 0.0
        self._hover_idx: int = -1
        self.setMouseTracking(True)

    def set_data(self, candidates: List[Candidate], duration: float) -> None:
        self._candidates = list(candidates)
        self._duration = max(duration, 0.001)
        self.update()

    def clear_data(self) -> None:
        self._candidates = []
        self._duration = 0.0
        self.update()

    def _score_to_color(self, score: float) -> QColor:
        """Map a 0..1 score to a red → yellow → green colour ramp."""
        s = max(0.0, min(1.0, score))
        if s < 0.5:
            # red (243,139,168) → yellow (249,226,175)
            t = s * 2.0
            r = int(243 + (249 - 243) * t)
            g = int(139 + (226 - 139) * t)
            b = int(168 + (175 - 168) * t)
        else:
            # yellow (249,226,175) → green (166,227,161)
            t = (s - 0.5) * 2.0
            r = int(249 + (166 - 249) * t)
            g = int(226 + (227 - 226) * t)
            b = int(175 + (161 - 175) * t)
        return QColor(r, g, b)

    def _cell_rect(self, idx: int):
        """Return the QRect for candidate ``idx``'s cell, or None if out of range."""
        if not self._candidates or idx < 0 or idx >= len(self._candidates):
            return None
        c = self._candidates[idx]
        w = self.width()
        h = self.height()
        margin = 4
        bar_h = h - 2 * margin
        bar_w = w - 2 * margin
        x_norm = c.timestamp / self._duration
        cell_w = max(3, bar_w / max(len(self._candidates), 1))
        x = margin + x_norm * bar_w - cell_w / 2
        return QRectF(max(margin, x), margin, min(cell_w, bar_w), bar_h)

    def _hit_test(self, x: float, y: float) -> int:
        """Return the candidate index whose cell contains (x, y), or -1."""
        for i in range(len(self._candidates)):
            rect = self._cell_rect(i)
            if rect is not None and rect.contains(x, y):
                return i
        return -1

    def paintEvent(self, e) -> None:  # type: ignore[override]
        from PySide6.QtGui import QPainter, QColor, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background
        p.fillRect(self.rect(), QColor(C_CARD))

        if not self._candidates:
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Run analysis to see score heatmap")
            return

        # Draw axis line
        margin = 4
        w = self.width()
        h = self.height()
        p.setPen(QPen(QColor(C_OVERLAY), 1))
        p.drawLine(margin, h - margin, w - margin, h - margin)

        # Draw cells
        for i, c in enumerate(self._candidates):
            rect = self._cell_rect(i)
            if rect is None:
                continue
            color = self._score_to_color(c.total_score)
            if i == self._hover_idx:
                color = color.lighter(130)
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(rect, 2, 2)

        # Highlight selected if parent set it (we look up via _selected_idx attr)
        sel = getattr(self, "_selected_idx", -1)
        if 0 <= sel < len(self._candidates):
            rect = self._cell_rect(sel)
            if rect is not None:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(C_LAVENDER), 2))
                p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 3, 3)

    def mouseMoveEvent(self, e) -> None:  # type: ignore[override]
        idx = self._hit_test(e.position().x(), e.position().y())
        if idx != self._hover_idx:
            self._hover_idx = idx
            if idx >= 0:
                c = self._candidates[idx]
                self.setToolTip(
                    f"#{idx + 1}  {format_time(c.timestamp)}\nScore: {c.total_score:.3f}"
                )
            else:
                self.setToolTip("")
            self.update()

    def mousePressEvent(self, e) -> None:  # type: ignore[override]
        if e.button() == Qt.MouseButton.LeftButton:
            idx = self._hit_test(e.position().x(), e.position().y())
            if idx >= 0:
                self.clicked.emit(idx)

    def leaveEvent(self, e) -> None:  # type: ignore[override]
        self._hover_idx = -1
        self.update()

    def set_selected(self, idx: int) -> None:
        self._selected_idx = idx
        self.update()
