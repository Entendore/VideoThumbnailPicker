import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal, QRectF, QPoint
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont, QPen, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, 
    QScrollArea, QGraphicsView, QGraphicsScene, QMenu
)

from config import C_CARD, C_OVERLAY, C_TEXT, C_GREEN, C_RED, C_BLUE, C_YELLOW, CRIT_LABELS
from analysis import Candidate
from utils import format_time

# ────────────────────────────────────────────────────────────────────────────
# Preview & Visualization
# ────────────────────────────────────────────────────────────────────────────

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
        
        painter.save()
        # Draw in Scene Coordinates (image pixels)
        
        pen = QPen(QColor(255, 255, 255, 200), 2)
        pen.setCosmetic(True) # Constant width regardless of zoom
        painter.setPen(pen)

        if self.show_grid:
            w = self._pixmap_item.pixmap().width()
            h = self._pixmap_item.pixmap().height()
            pen_grid = QPen(QColor(255, 255, 255, 80), 1)
            pen_grid.setCosmetic(True)
            painter.setPen(pen_grid)
            for i in range(1, 3):
                painter.drawLine(int(w * i / 3), 0, int(w * i / 3), h)
                painter.drawLine(0, int(h * i / 3), w, int(h * i / 3))

        if self.show_faces and self._current_cand:
            for (x, y, w, h) in self._current_cand.faces:
                painter.setPen(QPen(QColor(C_GREEN), 3))
                painter.drawRect(x, y, w, h)

        painter.restore()

    def zoom_in(self): self.scale(1.2, 1.2)
    def zoom_out(self): self.scale(1/1.2, 1/1.2)
    def fit(self): 
        if self._pixmap_item: 
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

class HistogramWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(100)
        self.hist_data = None

    def set_data(self, bgr):
        if bgr is None: return
        h = []
        for i in range(3):
            hist = cv2.calcHist([bgr], [i], None, [256], [0, 256])
            cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
            h.append(hist.flatten())
        self.hist_data = h
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C_CARD))
        
        if not self.hist_data: return

        w, h = self.width(), self.height()
        margin = 10
        gw, gh = w - 2*margin, h - 2*margin
        
        colors = [C_BLUE, C_GREEN, C_RED]
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
        
        if not self.scores: return

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
            
            p.drawText(10, y + bar_h - 3, CRIT_LABELS.get(k, k))
            p.fillRect(margin_x, y, w, bar_h, QColor(C_OVERLAY))
            
            color = C_BLUE
            if val > 0.7: color = C_GREEN
            elif val < 0.3: color = C_RED
            p.fillRect(margin_x, y, int(w * val), bar_h, QColor(color))
            
            p.drawText(margin_x + w + 5, y + bar_h - 3, f"{val:.2f}")

# ────────────────────────────────────────────────────────────────────────────
# Gallery & Timeline
# ────────────────────────────────────────────────────────────────────────────

class FilmstripTimeline(QScrollArea):
    clicked = Signal(float)
    def __init__(self):
        super().__init__()
        self.setFixedHeight(110)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"QScrollArea {{ background:{C_OVERLAY}; border-radius:8px; }}")
        
        self.container = QWidget()
        self.lay = QHBoxLayout(self.container)
        self.lay.setContentsMargins(4,4,4,4)
        self.lay.setSpacing(4)
        self.setWidget(self.container)
        
    def set_frames(self, frames):
        # Clear old
        while self.lay.count(): 
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not frames: return
        
        for t, bgr in frames:
            if bgr is None: continue
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            h, w = bgr.shape[:2]
            qim = QImage(rgb.data, w, h, 3*w, QImage.Format.Format_RGB888)
            pm = QPixmap.fromImage(qim)
            
            lbl = QLabel()
            lbl.setPixmap(pm.scaled(100, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            lbl.setToolTip(format_time(t))
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.mousePressEvent = lambda e, ts=t: self.clicked.emit(ts)
            
            self.lay.addWidget(lbl)

class GalleryCard(QFrame):
    clicked = Signal(int)
    starred_toggled = Signal(int)
    
    def __init__(self, idx, pm, cand: Candidate):
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
        row.addWidget(QLabel(f"{format_time(cand.timestamp)}"))
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
        self.setStyleSheet(f"QFrame {{ background:{bg}; border:2px solid {border}; border-radius:6px; }}")
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