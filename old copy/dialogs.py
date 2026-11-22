"""Video Thumbnail Picker — Dialog Widgets"""

from __future__ import annotations

import math
import cv2
from PIL import Image

from PyQt6.QtCore import Qt, pyqtSignal, QRect, QTimer
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QPen,
    QKeySequence, QShortcut,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSlider, QCheckBox,
    QFileDialog, QDialog, QLineEdit, QApplication,
)

from VideoThumbnailPicker.old.scoring import (
    C_BG, C_SURFACE, C_CARD, C_OVERLAY, C_TEXT, C_SUBTEXT,
    C_BLUE, C_GREEN, C_YELLOW, C_PEACH, C_RED, C_TEAL, C_LAVENDER,
    C_MAUVE, WEIGHTS_DEFAULT, CRIT_LABELS,
    Candidate,
)

from VideoThumbnailPicker.old.widgets import _resize_cover, _resize_fit, _fmt_time


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
# Thumbnail Viewer — fullscreen slideshow with arrow cycling
# ────────────────────────────────────────────────────────────────────────────

class ThumbnailViewer(QWidget):
    """Fullscreen-capable thumbnail viewer.
    Shows one candidate at a time;  ← →  cycle,  Home/End  jump,
    S  save,  F11  fullscreen toggle,  ESC  close.
    """

    closed = pyqtSignal(int)          # emits the index being viewed
    save_requested = pyqtSignal(int)  # index to save

    def __init__(self, candidates: list[Candidate], start_idx=0, parent=None):
        super().__init__(parent)
        self._cands = candidates
        self._idx = start_idx
        self._is_fullscreen = False
        self._labels: list[QLabel] = []  # thin labels drawn via paintEvent

        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumSize(900, 600)
        self.resize(1200, 750)
        self.setWindowTitle("Thumbnail Viewer")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(f"background:{C_BG};")

        # ── layout ──
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Image label (fills available space)
        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(
            Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet(f"background:{C_BG};")
        root.addWidget(self._img_lbl, stretch=1)

        # ── Bottom info bar ──
        bar = QWidget()
        bar.setFixedHeight(72)
        bar.setStyleSheet(
            f"background:{C_SURFACE};border-top:1px solid {C_OVERLAY};")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 6, 16, 6)
        bl.setSpacing(16)

        self._lbl_rank = QLabel()
        self._lbl_rank.setFixedWidth(60)
        bl.addWidget(self._lbl_rank)

        self._lbl_time = QLabel()
        self._lbl_time.setFixedWidth(90)
        bl.addWidget(self._lbl_time)

        self._lbl_score = QLabel()
        self._lbl_score.setFixedWidth(120)
        bl.addWidget(self._lbl_score)

        # Mini score breakdown bar
        self._bar_widget = _ViewerScoreBar()
        self._bar_widget.setFixedSize(220, 18)
        bl.addWidget(self._bar_widget)

        bl.addStretch()

        # Navigation hints
        hint = QLabel("← →  Cycle   ·   Home/End   ·   S  Save   ·   F11  Fullscreen   ·   ESC  Close")
        hint.setStyleSheet(f"font-size:10px;color:{C_SUBTEXT};")
        bl.addWidget(hint)

        root.addWidget(bar)

        # ── Shortcuts (local to this widget) ──
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self._nav(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self._nav(1))
        QShortcut(QKeySequence(Qt.Key.Key_Up), self, lambda: self._nav(-5))
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, lambda: self._nav(5))
        QShortcut(QKeySequence(Qt.Key.Key_Home), self, lambda: self._go(0))
        QShortcut(QKeySequence(Qt.Key.Key_End), self, lambda: self._go(len(self._cands) - 1))
        QShortcut(QKeySequence("S"), self, self._on_save)
        QShortcut(QKeySequence("F11"), self, self._toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._close_self)

        self._refresh()

    # ── navigation ──

    def _nav(self, d):
        n = len(self._cands)
        if n == 0:
            return
        self._idx = (self._idx + d) % n
        self._refresh()

    def _go(self, idx):
        idx = max(0, min(idx, len(self._cands) - 1))
        self._idx = idx
        self._refresh()

    def _on_save(self):
        if self._cands:
            self.save_requested.emit(self._idx)

    def _close_self(self):
        self.closed.emit(self._idx)
        self.close()

    # ── display ──

    def _refresh(self):
        if not self._cands:
            self._img_lbl.setText("No candidates")
            return

        c = self._cands[self._idx]
        rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)

        # Fit to the label size while preserving aspect ratio
        lbl_w = self._img_lbl.width() or 1100
        lbl_h = self._img_lbl.height() or 600
        pil = _resize_fit(pil, lbl_w - 16, lbl_h - 16)
        pw, ph = pil.size
        qi = QImage(pil.tobytes(), pw, ph, 3 * pw,
                    QImage.Format.Format_RGB888)
        self._img_lbl.setPixmap(QPixmap.fromImage(qi))

        # Update info bar
        n = len(self._cands)
        star = " ★" if c.starred else ""
        self._lbl_rank.setText(
            f"<b style='font-size:16px;color:{C_LAVENDER};'>"
            f"#{self._idx + 1}/{n}</b>{star}")
        self._lbl_rank.setStyleSheet(f"background:transparent;")

        self._lbl_time.setText(
            f"<span style='font-size:12px;color:{C_GREEN};"
            f"font-family:Consolas,monospace;'>"
            f"{_fmt_time(c.timestamp)}</span>")
        self._lbl_time.setStyleSheet(f"background:transparent;")

        self._lbl_score.setText(
            f"<span style='font-size:12px;color:{C_TEXT};'>"
            f"Score: <b>{c.total_score:.3f}</b></span>")
        self._lbl_score.setStyleSheet(f"background:transparent;")

        self._bar_widget.set_breakdown(c.breakdown)

        self.setWindowTitle(
            f"Thumbnail Viewer  —  #{self._idx + 1} of {n}")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # Re-render image to fill new size
        if self._cands:
            self._refresh()

    def keyPressEvent(self, e):
        # Handled by shortcuts; ignore other keys
        pass

    # ── fullscreen ──

    def _toggle_fullscreen(self):
        if self._is_fullscreen:
            self.showNormal()
        else:
            self.showFullScreen()
        self._is_fullscreen = not self._is_fullscreen


class _ViewerScoreBar(QWidget):
    """Tiny horizontal score-breakdown bar for the viewer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._breakdown: dict = {}
        self.setFixedHeight(18)

    def set_breakdown(self, bd: dict):
        self._breakdown = bd
        self.update()

    def paintEvent(self, e):
        if not self._breakdown:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        top = sorted(self._breakdown.items(),
                     key=lambda x: WEIGHTS_DEFAULT.get(x[0], 0),
                     reverse=True)[:7]
        if not top:
            p.end()
            return
        seg = w / len(top)
        cols = [C_BLUE, C_GREEN, C_PEACH, C_MAUVE, C_TEAL, C_LAVENDER, C_YELLOW]
        for i, (name, val) in enumerate(top):
            bw = int(seg * val)
            x = int(i * seg)
            if bw > 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(cols[i % len(cols)]))
                p.drawRoundedRect(x + 1, 2, max(1, bw - 2), h - 4, 2, 2)
        # Label each segment
        p.setPen(QColor(C_TEXT))
        p.setFont(QFont("Segoe UI", 7))
        for i, (name, val) in enumerate(top):
            label = CRIT_LABELS.get(name, name)
            # Abbreviate long labels
            if len(label) > 8:
                label = label[:7] + "."
            p.setPen(QColor(C_TEXT))
            x = int(i * seg) + 4
            y = h - 3
            p.drawText(x, y, label)
        p.end()
