"""Video Thumbnail Picker — Gallery & Picker Widgets"""

from __future__ import annotations

import cv2
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QGridLayout, QMenu,
)

from VideoThumbnailPicker.old.scoring import (
    WEIGHTS_DEFAULT,
    C_BG, C_SURFACE, C_CARD, C_OVERLAY, C_TEXT, C_SUBTEXT,
    C_BLUE, C_GREEN, C_YELLOW, C_PEACH, C_RED, C_MAUVE, C_TEAL, C_LAVENDER, C_PINK,
    Candidate,
)

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

