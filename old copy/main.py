#!/usr/bin/env python3
"""
Video Thumbnail Picker  v5.0  (PyQt6)
======================================
An advanced Python GUI tool that analyses a video and extracts the most
visually compelling thumbnail.

Requirements:
  pip install PyQt6 opencv-python numpy pillow

Usage:
  python main.py
"""

from __future__ import annotations

import sys
import os
import logging
from pathlib import Path

# ────────────────────────────────────────────────────────────────────────────
# Logging setup — configure once at import time
# ────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger("thumbnail_picker")

import cv2
import numpy as np
from PIL import Image

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QPixmap, QImage, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QProgressBar, QScrollArea,
    QFileDialog, QMessageBox, QSplitter, QStatusBar, QGroupBox,
    QToolBar, QCheckBox, QDialog, QGridLayout,
)

from VideoThumbnailPicker.old.scoring import (
    PRESETS, DEFAULT_CANDIDATES, DEFAULT_SAMPLES,
    WEIGHTS_DEFAULT,
    C_TEXT, C_SUBTEXT, C_BLUE, C_BG, C_OVERLAY,
    STYLESHEET,
    Candidate, AnalysisThread,
    compute_score,
)
from VideoThumbnailPicker.old.widgets import (
    ZoomablePreview, HistogramWidget, AudioWaveformWidget,
    WeightPanel, ScoreBreakdownPanel,
    FilmstripTimeline,
    _resize_fit, _resize_cover, _fmt_time,
)
from VideoThumbnailPicker.old.gallery import (
    GalleryCard, GridCard, DropLabel, ThumbnailPickerGrid,
)
from VideoThumbnailPicker.old.dialogs import (
    ComparisonOverlay, SaveDialog, VideoScrubberDialog,
    ThumbnailViewer,
)

# ────────────────────────────────────────────────────────────────────────────
# Main Window
# ────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Thumbnail Picker  v5")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        self.video_path = None
        self.candidates: list[Candidate] = []
        self.video_info: dict = {}
        self.selected_idx = 0
        self._compare_first: int | None = None
        self._analysis_thread: AnalysisThread | None = None
        self._current_weights = WEIGHTS_DEFAULT.copy()
        self._grid_mode = False
        self._show_starred_only = False
        self._was_maximized = False
        self._filmstrip_data: list[tuple[float, object]] = []
        self._audio_energy: list[tuple[float, float]] = []
        self._progress_candidates: list[Candidate] = []
        self._picker_mode = False
        self._selected_picker_indices: set[int] = set()

        self._settings = QSettings("ThumbnailPicker", "v5")
        self._restore_settings()

        self._build_central()
        self._build_toolbar()
        self._build_statusbar()
        self._build_shortcuts()
        self.setStyleSheet(STYLESHEET)
        self.setAcceptDrops(True)

        self.weight_panel.weights_changed.connect(self._on_weights_changed)

    # ── settings ──

    def _restore_settings(self):
        geo = self._settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        self._last_dir = self._settings.value("last_dir", "", type=str)

    def closeEvent(self, e):
        if self._analysis_thread and self._analysis_thread.isRunning():
            self._analysis_thread.abort()
        self._settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(e)

    # ── building ──

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 4, 8, 4)
        root.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, stretch=1)

        # ── Left: preview ──
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 4, 0)
        ll.setSpacing(4)

        # Title row
        title_row = QHBoxLayout()
        self.lbl_preview_title = QLabel("Preview")
        self.lbl_preview_title.setStyleSheet(
            f"font-size:14px;font-weight:bold;color:{C_TEXT};padding:4px;")
        title_row.addWidget(self.lbl_preview_title)
        title_row.addStretch()
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setStyleSheet(f"font-size:10px;color:{C_SUBTEXT};")
        title_row.addWidget(self.lbl_zoom)
        ll.addLayout(title_row)

        # Preview (must be created before zoom buttons reference it)
        self.preview = ZoomablePreview()
        self.preview.zoom_changed.connect(
            lambda z: self.lbl_zoom.setText(f"{z * 100:.0f}%"))
        self.preview.double_clicked.connect(self._toggle_fullscreen)
        ll.addWidget(self.preview, stretch=1)

        # Zoom buttons
        for label, slot in [("+", self.preview.zoom_in),
                            ("-", self.preview.zoom_out),
                            ("Fit", self._fit_preview),
                            ("100%", self.preview.zoom_100)]:
            b = QPushButton(label)
            b.setFixedSize(36, 22)
            b.setStyleSheet(f"font-size:9px;padding:2px;")
            b.clicked.connect(slot)
            title_row.addWidget(b)

        # Filmstrip timeline
        self.filmstrip = FilmstripTimeline()
        self.filmstrip.seek_requested.connect(self._on_filmstrip_seek)
        self.filmstrip.setVisible(False)
        ll.addWidget(self.filmstrip)

        # Audio waveform
        self.audio_waveform = AudioWaveformWidget()
        self.audio_waveform.setVisible(False)
        ll.addWidget(self.audio_waveform)

        # Histogram
        self.histogram = HistogramWidget()
        self.histogram.setVisible(False)
        ll.addWidget(self.histogram)

        # Drop overlay
        self.drop_label = DropLabel()
        self.drop_label.fileDropped.connect(self._on_file_dropped)
        ll.addWidget(self.drop_label, stretch=1)
        self.drop_label.hide()

        # Options row
        opt_row = QHBoxLayout()
        opt_row.setSpacing(8)
        opt_row.addWidget(self._lbl("Output:", C_SUBTEXT, 10))
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(PRESETS.keys())
        self.combo_preset.currentTextChanged.connect(self._refresh_preview)
        opt_row.addWidget(self.combo_preset)
        self.chk_watermark = QCheckBox("Timestamp")
        self.chk_watermark.setStyleSheet("font-size:10px;")
        opt_row.addWidget(self.chk_watermark)
        self.chk_histogram = QCheckBox("Histogram")
        self.chk_histogram.stateChanged.connect(
            lambda s: self.histogram.setVisible(
                s == Qt.CheckState.Checked.value))
        opt_row.addWidget(self.chk_histogram)
        self.chk_filmstrip = QCheckBox("Filmstrip")
        self.chk_filmstrip.setChecked(True)
        self.chk_filmstrip.stateChanged.connect(
            lambda s: self.filmstrip.setVisible(
                s == Qt.CheckState.Checked.value and bool(self.candidates)))
        opt_row.addWidget(self.chk_filmstrip)
        self.chk_waveform = QCheckBox("Waveform")
        self.chk_waveform.stateChanged.connect(
            lambda s: self.audio_waveform.setVisible(
                s == Qt.CheckState.Checked.value and bool(self._audio_energy)))
        opt_row.addWidget(self.chk_waveform)
        opt_row.addStretch()
        ll.addLayout(opt_row)

        splitter.addWidget(left)

        # ── Right: sidebar ──
        right = QWidget()
        right.setFixedWidth(390)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 0, 0)
        rl.setSpacing(4)

        # Video info
        info_g = QGroupBox("Video Info")
        il = QVBoxLayout(info_g)
        self.lbl_info = QLabel("No video loaded")
        self.lbl_info.setStyleSheet(
            f"font-size:10px;color:{C_SUBTEXT};"
            f"font-family:Consolas,monospace;")
        self.lbl_info.setWordWrap(True)
        il.addWidget(self.lbl_info)
        rl.addWidget(info_g)

        # Score breakdown
        score_g = QGroupBox("Score Breakdown")
        sl = QVBoxLayout(score_g)
        self.score_panel = ScoreBreakdownPanel()
        sl.addWidget(self.score_panel)
        rl.addWidget(score_g)

        # Weights
        weight_g = QGroupBox("Scoring Weights")
        wl = QVBoxLayout(weight_g)
        self.weight_panel = WeightPanel()
        wl.addWidget(self.weight_panel)
        rl.addWidget(weight_g)

        # Gallery controls
        gal_ctrl = QHBoxLayout()
        gal_ctrl.setSpacing(6)
        self.btn_view_list = QPushButton("List")
        self.btn_view_list.setFixedSize(50, 22)
        self.btn_view_list.setStyleSheet(f"font-size:9px;padding:2px;")
        self.btn_view_list.clicked.connect(lambda: self._set_view_mode("list"))
        gal_ctrl.addWidget(self.btn_view_list)
        self.btn_view_grid = QPushButton("Grid")
        self.btn_view_grid.setFixedSize(50, 22)
        self.btn_view_grid.setStyleSheet(f"font-size:9px;padding:2px;")
        self.btn_view_grid.clicked.connect(lambda: self._set_view_mode("grid"))
        gal_ctrl.addWidget(self.btn_view_grid)
        self.btn_view_picker = QPushButton("Picker")
        self.btn_view_picker.setFixedSize(54, 22)
        self.btn_view_picker.setStyleSheet(f"font-size:9px;padding:2px;")
        self.btn_view_picker.setToolTip("P \u2014 multi-select thumbnails for export")
        self.btn_view_picker.clicked.connect(lambda: self._set_view_mode("picker"))
        gal_ctrl.addWidget(self.btn_view_picker)
        gal_ctrl.addWidget(self._lbl("Sort:", C_SUBTEXT, 10))
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(
            ["Score", "Time", "Sharpness", "Colourfulness", "Faces",
             "Contrast", "Composition", "Exposure Q.", "Dyn. Range",
             "Complexity", "Colour Harm."])
        self.combo_sort.currentTextChanged.connect(self._on_sort_changed)
        gal_ctrl.addWidget(self.combo_sort, stretch=1)

        self.chk_starred = QCheckBox("Stars only")
        self.chk_starred.setStyleSheet(f"font-size:10px;")
        self.chk_starred.stateChanged.connect(self._on_star_filter)
        gal_ctrl.addWidget(self.chk_starred)
        rl.addLayout(gal_ctrl)

        # Gallery
        self.gallery_groupbox = QGroupBox(
            "Top Candidates  (click \u00b7 \u2190 \u2192 \u00b7 "
            "1\u20139 \u00b7 right-click)")
        gl = QVBoxLayout(self.gallery_groupbox)
        gl.setSpacing(4)
        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.gallery_container = QWidget()
        self.gallery_vlayout = QVBoxLayout(self.gallery_container)
        self.gallery_vlayout.setContentsMargins(4, 4, 4, 4)
        self.gallery_vlayout.setSpacing(4)
        self.gallery_vlayout.addStretch()
        self.gallery_scroll.setWidget(self.gallery_container)
        gl.addWidget(self.gallery_scroll)

        # Picker grid (hidden by default)
        self.picker_grid = ThumbnailPickerGrid()
        self.picker_grid.save_selected.connect(self._on_save_selected)
        self.picker_grid.setVisible(False)
        gl.addWidget(self.picker_grid)

        rl.addWidget(self.gallery_groupbox, stretch=1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        self.btn_pick = QPushButton("  Pick Video")
        self.btn_pick.setObjectName("btnPrimary")
        self.btn_pick.setToolTip("Ctrl+O")
        self.btn_pick.clicked.connect(self._on_pick)
        tb.addWidget(self.btn_pick)

        self.btn_analyze = QPushButton("  Analyse")
        self.btn_analyze.setObjectName("btnPrimary")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setToolTip("R")
        self.btn_analyze.clicked.connect(self._on_analyze)
        tb.addWidget(self.btn_analyze)

        tb.addSeparator()
        tb.addWidget(self._lbl("Samples:", C_SUBTEXT))
        self.spin_samples = QSpinBox()
        self.spin_samples.setRange(10, 500)
        self.spin_samples.setSingleStep(10)
        self.spin_samples.setValue(DEFAULT_SAMPLES)
        tb.addWidget(self.spin_samples)

        tb.addWidget(self._lbl("Cands:", C_SUBTEXT))
        self.spin_cands = QSpinBox()
        self.spin_cands.setRange(4, 24)
        self.spin_cands.setValue(DEFAULT_CANDIDATES)
        tb.addWidget(self.spin_cands)

        self.chk_scene = QCheckBox("Scene detect")
        tb.addWidget(self.chk_scene)
        self.chk_scene.setToolTip(
            "Use scene-change detection instead of uniform sampling")
        self.chk_scene.setStyleSheet(f"color:{C_TEXT};")

        self.chk_audio = QCheckBox("Audio aware")
        self.chk_audio.setChecked(True)
        tb.addWidget(self.chk_audio)
        self.chk_audio.setToolTip(
            "Prioritize sampling at moments with high audio activity")
        self.chk_audio.setStyleSheet(f"color:{C_TEXT};")

        tb.addSeparator()

        self.btn_save = QPushButton("  Save")
        self.btn_save.setObjectName("btnGreen")
        self.btn_save.setEnabled(False)
        self.btn_save.setToolTip("Ctrl+S")
        self.btn_save.clicked.connect(self._on_save)
        tb.addWidget(self.btn_save)

        self.btn_save_all = QPushButton("  Save All")
        self.btn_save_all.setObjectName("btnMauve")
        self.btn_save_all.setEnabled(False)
        self.btn_save_all.clicked.connect(self._on_save_all)
        tb.addWidget(self.btn_save_all)

        self.btn_clipboard = QPushButton("  Copy")
        self.btn_clipboard.setObjectName("btnPeach")
        self.btn_clipboard.setEnabled(False)
        self.btn_clipboard.setToolTip("Ctrl+C")
        self.btn_clipboard.clicked.connect(self._on_clipboard)
        tb.addWidget(self.btn_clipboard)

        tb.addSeparator()

        self.btn_scrubber = QPushButton("  Scrubber")
        self.btn_scrubber.setObjectName("btnTeal")
        self.btn_scrubber.setEnabled(False)
        self.btn_scrubber.setToolTip("Open video timeline scrubber")
        self.btn_scrubber.clicked.connect(self._on_scrubber)
        tb.addWidget(self.btn_scrubber)

        self.btn_compare = QPushButton("  Compare")
        self.btn_compare.setObjectName("btnYellow")
        self.btn_compare.setEnabled(False)
        self.btn_compare.setToolTip("C \u2014 select 2 candidates")
        self.btn_compare.clicked.connect(self._on_compare)
        tb.addWidget(self.btn_compare)

        self.btn_viewer = QPushButton("  Viewer")
        self.btn_viewer.setObjectName("btnTeal")
        self.btn_viewer.setEnabled(False)
        self.btn_viewer.setToolTip("V \u2014 open thumbnail viewer slideshow")
        self.btn_viewer.clicked.connect(self._on_viewer)
        tb.addWidget(self.btn_viewer)

    def _build_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(260)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.status_bar.showMessage(
            "Ready \u2014 drop a video or press Ctrl+O")

    def _build_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self._on_pick)
        QShortcut(QKeySequence("Ctrl+S"), self, self._on_save)
        QShortcut(QKeySequence("Ctrl+C"), self, self._on_clipboard)
        QShortcut(QKeySequence("Ctrl+R"), self, self._on_analyze)
        QShortcut(QKeySequence("Escape"), self, self._on_escape)
        QShortcut(QKeySequence("Left"), self, lambda: self._nav(-1))
        QShortcut(QKeySequence("Right"), self, lambda: self._nav(1))
        QShortcut(QKeySequence("Up"), self, lambda: self._nav(-1))
        QShortcut(QKeySequence("Down"), self, lambda: self._nav(1))
        QShortcut(QKeySequence("R"), self, self._on_analyze)
        for i in range(1, 10):
            QShortcut(QKeySequence(str(i)), self,
                      lambda idx=i - 1: self._select(idx))
        QShortcut(QKeySequence("F"), self, self._fit_preview)
        QShortcut(QKeySequence("F11"), self, self._toggle_fullscreen)
        QShortcut(QKeySequence("G"), self,
                  lambda: self._set_view_mode("grid" if not self._grid_mode else "list"))
        QShortcut(QKeySequence("P"), self,
                  lambda: self._set_view_mode(
                      "list" if self._picker_mode else "picker"))
        QShortcut(QKeySequence("V"), self, self._on_viewer)

    def _lbl(self, text, color, size=11):
        l = QLabel(text)
        l.setStyleSheet(f"font-size:{size}px;color:{color};")
        return l

    def _restyle(self, widget):
        """Force stylesheet refresh after setObjectName()."""
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    # ── drag/drop ──

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        u = e.mimeData().urls()[0].toLocalFile()
        if u and Path(u).is_file():
            self._on_file_dropped(u)

    # ── file ──

    def _on_pick(self):
        d = self._settings.value("last_dir", "", type=str)
        path, _ = QFileDialog.getOpenFileName(
            self, "Select video", d,
            "Video (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v);;"
            "All (*)")
        if path:
            self._settings.setValue("last_dir", str(Path(path).parent))
            self._on_file_dropped(path)

    def _on_file_dropped(self, path):
        p = Path(path)
        if not p.is_file():
            logger.warning("Dropped path is not a file: %s", path)
            return
        if not p.stat().st_size > 0:
            self.status_bar.showMessage("File is empty: " + p.name)
            logger.warning("Dropped file is empty: %s (%d bytes)", path, p.stat().st_size)
            return
        logger.info("File loaded: %s (%.1f MB)", p.name, p.stat().st_size / 1048576)
        self.video_path = path
        self.status_bar.showMessage(f"Loaded: {p.name}")
        self.btn_analyze.setEnabled(True)
        self.btn_scrubber.setEnabled(True)
        self.btn_analyze.setText("  Analyse")
        self.btn_analyze.setObjectName("btnPrimary"); self._restyle(self.btn_analyze)
        self._on_analyze()

    # ── analysis ──

    def _on_analyze(self):
        if not self.video_path:
            logger.warning("Analyze called but no video loaded")
            return
        # Disconnect old thread signals to prevent leaks
        if self._analysis_thread is not None:
            try:
                self._analysis_thread.progress.disconnect()
                self._analysis_thread.finished_ok.disconnect()
                self._analysis_thread.finished_err.disconnect()
                self._analysis_thread.cancelled.disconnect()
                self._analysis_thread.filmstrip_frames.disconnect()
                self._analysis_thread.candidate_ready.disconnect()
                self._analysis_thread.audio_energy_ready.disconnect()
            except RuntimeError:
                pass
        if (self._analysis_thread
                and self._analysis_thread.isRunning()):
            self._analysis_thread.abort()
            return

        num = self.spin_samples.value()
        n_cands = self.spin_cands.value()
        self._current_weights = self.weight_panel.get_weights()
        self.btn_analyze.setText("  Cancel")
        self.btn_analyze.setObjectName("btnRed"); self._restyle(self.btn_analyze)
        for b in (self.btn_save, self.btn_save_all,
                  self.btn_clipboard, self.btn_compare):
            b.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._progress_candidates = []
        self.status_bar.showMessage(f"Analysing {num} samples \u2026")

        self._analysis_thread = AnalysisThread(
            self.video_path, num, self._current_weights,
            self.chk_scene.isChecked(), n_cands,
            use_audio=self.chk_audio.isChecked())
        self._analysis_thread.progress.connect(self._on_progress)
        self._analysis_thread.finished_ok.connect(self._on_done)
        self._analysis_thread.finished_err.connect(self._on_err)
        self._analysis_thread.cancelled.connect(self._on_cancel)
        self._analysis_thread.filmstrip_frames.connect(self._on_filmstrip)
        self._analysis_thread.candidate_ready.connect(self._on_candidate_ready)
        self._analysis_thread.audio_energy_ready.connect(self._on_audio_energy_ready)
        self._analysis_thread.start()

    def _on_progress(self, cur, tot):
        p = int(cur / tot * 100) if tot > 0 else 0
        self.progress_bar.setValue(p)
        n_prog = len(self._progress_candidates)
        self.status_bar.showMessage(
            f"Analysing \u2026 {cur}/{tot} ({p}%)"
            + (f" \u2014 found {n_prog} candidates so far"
               if n_prog > 0 else ""))

    def _on_filmstrip(self, frames):
        self._filmstrip_data = frames
        self.filmstrip.set_frames(frames)

    def _on_audio_energy_ready(self, energy_data, duration):
        self._audio_energy = energy_data
        self.audio_waveform.set_data(energy_data, duration)

    def _on_candidate_ready(self, candidate, cur_idx, total):
        self._progress_candidates.append(candidate)
        # Keep sorted by score
        self._progress_candidates.sort(
            key=lambda c: c.total_score, reverse=True)
        # Update preview with current best
        if self._progress_candidates:
            best = self._progress_candidates[0]
            rgb = cv2.cvtColor(best.frame_bgr, cv2.COLOR_BGR2RGB)
            vp = self.preview.viewport()
            if vp:
                pil = Image.fromarray(rgb)
                pil = _resize_fit(pil, (vp.width() or 640) - 8,
                                  (vp.height() or 480) - 8)
                pw, ph = pil.size
                qi = QImage(pil.tobytes(), pw, ph, 3 * pw,
                             QImage.Format.Format_RGB888)
                self.preview.set_pixmap(QPixmap.fromImage(qi))
            self.score_panel.update_scores(best.total_score, best.breakdown)
            self.lbl_preview_title.setText(
                f"Preview  \u2014  live best @  "
                f"{_fmt_time(best.timestamp)}  "
                f"(score {best.total_score:.3f})")
        n_prog = len(self._progress_candidates)
        self.status_bar.showMessage(
            f"Analysing \u2026 {cur_idx}/{total}"
            f" \u2014 found {n_prog} candidates so far")

    def _on_done(self, cands, vinfo):
        self.candidates = cands
        self.video_info = vinfo
        self.selected_idx = 0
        self._progress_candidates = []
        self.btn_analyze.setText("  Re-analyse")
        self.btn_analyze.setObjectName("btnPrimary"); self._restyle(self.btn_analyze)
        self.progress_bar.setValue(100)
        logger.info("Analysis complete: %d candidates, %.1fs video, %d frames sampled",
                     len(cands), vinfo["duration"], vinfo["total_sampled"])
        filtered_msg = ""
        if vinfo.get('frames_filtered', 0) > 0:
            filtered_msg = (
                f" \u00b7 {vinfo['frames_filtered']} frames pre-filtered")
        # Guard: no candidates found (all frames filtered)
        if not cands:
            self.status_bar.showMessage(
                f"Done \u2014 {vinfo['total_sampled']} sampled"
                f"{filtered_msg} \u00b7 0 candidates (all frames filtered)")
            self.btn_analyze.setEnabled(True)
            self.progress_bar.setVisible(False)
            return
        self.status_bar.showMessage(
            f"Done \u2014 {vinfo['total_sampled']} sampled"
            f"{filtered_msg} \u00b7 "
            f"{vinfo['candidates_kept']} diverse candidates"
            f" \u00b7 top at {_fmt_time(cands[0].timestamp)}"
            f" \u00b7 \u2190\u2192 navigate \u00b7 "
            f"1\u2013{len(cands)} select \u00b7 "
            f"Ctrl+S save \u00b7 G grid \u00b7 P picker \u00b7 F11 fullscreen")
        self._show_info(vinfo)
        self._build_gallery(cands)
        self._show_preview(0)
        self._show_breakdown(0)
        for b in (self.btn_save, self.btn_save_all,
                  self.btn_clipboard, self.btn_compare,
                  self.btn_viewer):
            b.setEnabled(True)
        self.drop_label.hide()
        self.preview.show()

        # Show filmstrip if checked
        if self._filmstrip_data:
            self.filmstrip.setVisible(self.chk_filmstrip.isChecked())
            self.filmstrip.highlight_time(cands[0].timestamp)

        # Show waveform if checked and data available
        if self._audio_energy:
            sample_times = vinfo.get("sample_times", [])
            self.audio_waveform.set_data(
                self._audio_energy, vinfo["duration"], sample_times)
            self.audio_waveform.setVisible(self.chk_waveform.isChecked())

        # Update picker grid
        self.picker_grid.set_candidates(cands)

    def _on_err(self, msg):
        self.btn_analyze.setText("  Analyse")
        self.btn_analyze.setObjectName("btnPrimary"); self._restyle(self.btn_analyze)
        self.progress_bar.setVisible(False)
        logger.error("Analysis error: %s", msg)
        QMessageBox.critical(self, "Analysis Error", msg)

    def _on_cancel(self):
        self.btn_analyze.setText("  Analyse")
        self.btn_analyze.setObjectName("btnPrimary"); self._restyle(self.btn_analyze)
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Cancelled")

    def _on_weights_changed(self, w):
        self._current_weights = w
        if self.candidates:
            for c in self.candidates:
                c.total_score = sum(
                    c.breakdown[k] * w.get(k, 0) for k in w)
            cands_sorted = sorted(
                self.candidates,
                key=lambda c: c.total_score, reverse=True)
            self.candidates = cands_sorted
            self.selected_idx = 0

            self._show_breakdown(self.selected_idx)
            self._build_gallery(self.candidates)
            self._show_preview(self.selected_idx)
            # Also update the picker grid with new scores
            if self._picker_mode and self.picker_grid.isVisible():
                self.picker_grid.set_candidates(self.candidates)

    # ── display ──

    def _show_info(self, info):
        mm, ss = divmod(int(info["duration"]), 60)
        filtered = info.get('frames_filtered', 0)
        kept = info.get('candidates_kept', len(self.candidates))
        has_audio = info.get('has_audio', False)
        audio_used = info.get('audio_aware_used', False)
        lines = [
            f"File:        {Path(info['path']).name}",
            f"Resolution:  {info['width']}\u00d7{info['height']}",
            f"Duration:    {mm:02d}:{ss:02d}  ({info['duration']:.1f}s)",
            f"FPS:         {info['fps']:.2f}",
            f"Frames:      {info['total_frames']:,}",
            f"Sampled:     {info['total_sampled']}",
        ]
        if filtered:
            lines.append(f"Filtered:    {filtered}")
        lines.append(f"Kept:        {kept}")
        if has_audio:
            mode = "Audio-aware" if audio_used else "Has audio"
            lines.append(f"Audio:       {mode}")
        self.lbl_info.setText("\n".join(lines))

    def _build_gallery(self, cands):
        # Handle picker mode
        if self._picker_mode:
            self.gallery_scroll.setVisible(False)
            self.picker_grid.setVisible(True)
            self.picker_grid.set_candidates(cands)
            self.gallery_groupbox.setTitle(
                "Thumbnail Picker  (click to select \u00b7 P to exit)")
            return

        # Normal gallery modes
        self.gallery_scroll.setVisible(True)
        self.picker_grid.setVisible(False)
        self.gallery_groupbox.setTitle(
            "Top Candidates  (click \u00b7 \u2190 \u2192 \u00b7 "
            "1\u20139 \u00b7 right-click)")

        # Clear gallery
        while self.gallery_vlayout.count():
            it = self.gallery_vlayout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        # Re-add bottom stretch (removed by the loop above)
        self.gallery_vlayout.addStretch()

        display_cands = cands
        if self._show_starred_only:
            display_cands = [c for c in cands if c.starred]
            if not display_cands:
                display_cands = cands

        if self._grid_mode:
            self._build_gallery_grid(display_cands)
        else:
            self._build_gallery_list(display_cands)

    def _build_gallery_list(self, cands):
        for i, c in enumerate(cands):
            rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
            h, w = c.frame_bgr.shape[:2]
            qi = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            global_idx = next(i for i, x in enumerate(self.candidates) if x is c)
            card = GalleryCard(global_idx, QPixmap.fromImage(qi), c)
            card.clicked.connect(self._select_candidate)
            card.save_requested.connect(self._save_idx)
            card.copy_requested.connect(self._copy_idx)
            card.compare_requested.connect(self._compare_add)
            card.star_toggled.connect(self._on_star_toggle)
            self.gallery_vlayout.insertWidget(
                self.gallery_vlayout.count() - 1, card)
        # Highlight the first card
        if cands and self.candidates:
            first_w = self.gallery_vlayout.itemAt(0)
            if first_w:
                c0 = first_w.widget()
                if isinstance(c0, GalleryCard):
                    c0.set_selected(c0.candidate is self.candidates[0])
                elif isinstance(c0, QWidget):
                    for child in c0.findChildren((GalleryCard, GridCard)):
                        if child.candidate is self.candidates[0]:
                            child.set_selected(True)
                            break

    def _build_gallery_grid(self, cands):
        grid = QGridLayout()
        grid.setSpacing(6)
        cols = 2
        for i, c in enumerate(cands):
            rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
            h, w = c.frame_bgr.shape[:2]
            qi = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            global_idx = next(i for i, x in enumerate(self.candidates) if x is c)
            card = GridCard(global_idx, QPixmap.fromImage(qi), c)
            card.clicked.connect(self._select_candidate)
            card.star_toggled.connect(self._on_star_toggle)
            grid.addWidget(card, i // cols, i % cols)
        grid_widget = QWidget()
        grid_widget.setLayout(grid)
        self.gallery_vlayout.insertWidget(
            self.gallery_vlayout.count() - 1, grid_widget)

    def _select_candidate(self, idx):
        if idx < len(self.candidates):
            self.selected_idx = idx
            self._highlight_gallery(idx)
            self._show_preview(idx)
            self._show_breakdown(idx)
            if self._filmstrip_data:
                self.filmstrip.highlight_time(
                    self.candidates[idx].timestamp)

    def _highlight_gallery(self, idx):
        if idx >= len(self.candidates):
            return
        target = self.candidates[idx]
        count = self.gallery_vlayout.count()
        for i in range(count):
            w = self.gallery_vlayout.itemAt(i).widget()
            if isinstance(w, (GalleryCard, GridCard)):
                w.set_selected(w.candidate is target)
            elif isinstance(w, QWidget):
                # Grid mode: GridCards are children of a wrapper widget
                for child in w.findChildren((GalleryCard, GridCard)):
                    child.set_selected(child.candidate is target)

    def _select(self, idx):
        if idx < len(self.candidates):
            self._select_candidate(idx)

    def _nav(self, d):
        if not self.candidates:
            return
        n = (self.selected_idx + d) % len(self.candidates)
        self._select_candidate(n)

    def _show_preview(self, idx):
        c = self.candidates[idx]
        rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        preset = PRESETS.get(self.combo_preset.currentText())
        if preset:
            pil = _resize_cover(pil, *preset)
        else:
            vp = self.preview.viewport()
            pil = _resize_fit(
                pil, (vp.width() or 640) - 8, (vp.height() or 480) - 8)
        pw, ph = pil.size
        qi = QImage(pil.tobytes(), pw, ph, 3 * pw, QImage.Format.Format_RGB888)
        self.preview.set_pixmap_animated(QPixmap.fromImage(qi))

        self.histogram.set_frame(c.frame_bgr)
        star_mark = " \u2605" if c.starred else ""
        self.lbl_preview_title.setText(
            f"Preview  \u2014  #{idx + 1}{star_mark}  @  "
            f"{_fmt_time(c.timestamp)}  "
            f"(score {c.total_score:.3f})")

    def _refresh_preview(self):
        if self.candidates:
            self._show_preview(self.selected_idx)

    def _show_breakdown(self, idx):
        self.score_panel.update_scores(
            self.candidates[idx].total_score,
            self.candidates[idx].breakdown)

    def _fit_preview(self):
        self.preview.fit()

    # ── view mode ──

    def _set_view_mode(self, mode: str):
        """Switch between 'list', 'grid', and 'picker' view modes."""
        if mode == "picker":
            self._picker_mode = True
            self._grid_mode = False
        else:
            self._picker_mode = False
            self._grid_mode = (mode == "grid")

        active_style = (
            f"font-size:9px;padding:2px;background:{C_BLUE};"
            f"color:{C_BG};border-radius:4px;")
        inactive_style = f"font-size:9px;padding:2px;"

        self.btn_view_list.setStyleSheet(
            active_style if mode == "list" else inactive_style)
        self.btn_view_grid.setStyleSheet(
            active_style if mode == "grid" else inactive_style)
        self.btn_view_picker.setStyleSheet(
            active_style if mode == "picker" else inactive_style)
        if mode == "picker":
            self.btn_view_picker.setObjectName("btnPrimary"); self._restyle(self.btn_view_picker)
        else:
            self.btn_view_picker.setObjectName(""); self._restyle(self.btn_view_picker)

        if self.candidates:
            self._build_gallery(self.candidates)

    # ── sort ──

    def _on_sort_changed(self, sort_by):
        if not self.candidates:
            return
        key_map = {
            "Score": lambda c: c.total_score,
            "Time": lambda c: c.timestamp,
            "Sharpness": lambda c: c.breakdown.get("sharpness", 0),
            "Colourfulness": lambda c: c.breakdown.get("colorfulness", 0),
            "Faces": lambda c: c.breakdown.get("faces", 0),
            "Contrast": lambda c: c.breakdown.get("contrast", 0),
            "Composition": lambda c: c.breakdown.get("composition", 0),
            "Exposure Q.": lambda c: c.breakdown.get("exposure_quality", 0),
            "Dyn. Range": lambda c: c.breakdown.get("dynamic_range", 0),
            "Complexity": lambda c: c.breakdown.get("visual_complexity", 0),
            "Colour Harm.": lambda c: c.breakdown.get("color_harmony", 0),
        }
        key_fn = key_map.get(sort_by, lambda c: c.total_score)
        reverse = sort_by != "Time"
        self.candidates.sort(key=key_fn, reverse=reverse)
        self.selected_idx = 0
        self._build_gallery(self.candidates)
        self._show_preview(0)
        self._show_breakdown(0)

    # ── star filter ──

    def _on_star_toggle(self, idx, starred):
        # Rebuild gallery if "Stars only" filter is active so the
        # newly toggled star is immediately reflected in the view.
        if self._show_starred_only and self.candidates:
            self._build_gallery(self.candidates)

    def _on_star_filter(self, state):
        self._show_starred_only = (state == Qt.CheckState.Checked.value)
        if self.candidates:
            self._build_gallery(self.candidates)

    # ── fullscreen ──

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            if self._was_maximized:
                self.showMaximized()
        else:
            self._was_maximized = self.isMaximized()
            self.showFullScreen()

    # ── filmstrip seek ──

    def _on_filmstrip_seek(self, timestamp):
        """Seek to a specific timestamp in the video and pick that frame."""
        if not self.video_path:
            return
        logger.info("Filmstrip seek to %.2fs", timestamp)
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            logger.error("Cannot open video for filmstrip seek")
            return
        try:
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ret, frame = cap.read()
        finally:
            cap.release()
        if ret:
            total, bd = compute_score(frame, None, self._current_weights)
            new_cand = Candidate(frame, timestamp, total, bd)
            self.candidates.insert(0, new_cand)
            self.selected_idx = 0
            self._build_gallery(self.candidates)
            self._show_preview(0)
            self._show_breakdown(0)
            self.filmstrip.highlight_time(timestamp)
            self.picker_grid.set_candidates(self.candidates)
            self.status_bar.showMessage(
                f"Added frame from {_fmt_time(timestamp)} "
                f"(score {total:.3f}) as #1")
            logger.info("Added filmstrip frame: %.2fs, score=%.3f", timestamp, total)
        else:
            logger.warning("Could not read frame at %.2fs for filmstrip seek", timestamp)

    # ── save / export ──

    def _get_output_frame(self, cand, quality=95):
        f = cand.frame_bgr.copy()
        preset = PRESETS.get(self.combo_preset.currentText())
        if preset:
            rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            pil = _resize_cover(pil, *preset)
            f = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        if self.chk_watermark.isChecked():
            h, w = f.shape[:2]
            ts = _fmt_time(cand.timestamp)
            overlay = f.copy()
            (tw, th), _ = cv2.getTextSize(
                ts, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(overlay,
                          (w - tw - 20, h - th - 10),
                          (w - 6, h - 4), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.5, f, 0.5, 0, f)
            cv2.putText(f, ts, (w - tw - 14, h - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (255, 255, 255), 1, cv2.LINE_AA)
        return f

    def _on_save(self):
        if not self.candidates:
            logger.warning("Save called but no candidates available")
            return
        stem = Path(self.video_path).stem
        default_name = (
            f"thumbnail_{stem}_#{self.selected_idx + 1}.jpg")
        d = self._settings.value("last_dir", "", type=str)
        dlg = SaveDialog(
            self,
            default_name=os.path.join(d, default_name))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        path, fmt, quality, add_wm = dlg.get_values()
        if not path:
            return

        cand = self.candidates[self.selected_idx]
        old_wm = self.chk_watermark.isChecked()
        self.chk_watermark.setChecked(add_wm)
        try:
            f = self._get_output_frame(cand, quality)
            self.chk_watermark.setChecked(old_wm)

            ext = Path(path).suffix.lower()
            if ext == ".png":
                success = cv2.imwrite(path, f)
            elif ext == ".webp":
                success = cv2.imwrite(path, f, [cv2.IMWRITE_WEBP_QUALITY, quality])
            else:
                success = cv2.imwrite(path, f, [cv2.IMWRITE_JPEG_QUALITY, quality])

            if not success:
                logger.error("cv2.imwrite failed for %s", path)
                QMessageBox.warning(self, "Save Error",
                                    f"Failed to write file:\n{path}\n\n"
                                    f"Check the path is writable and the directory exists.")
                return

            saved_size = Path(path).stat().st_size
            logger.info("Saved thumbnail #%d: %s (%s, %d KB)",
                         self.selected_idx + 1, Path(path).name, fmt.upper(), saved_size // 1024)
            self._settings.setValue("last_dir", str(Path(path).parent))
            self.status_bar.showMessage(f"Saved \u2192 {path}")
        except Exception as exc:
            logger.error("Save failed: %s", exc)
            QMessageBox.critical(self, "Save Error",
                                f"Failed to save thumbnail:\n{exc}")
        finally:
            self.chk_watermark.setChecked(old_wm)

    def _on_save_all(self):
        if not self.candidates:
            return
        d = QFileDialog.getExistingDirectory(self, "Save all")
        if not d:
            return
        stem = Path(self.video_path).stem
        fmt = self.combo_preset.currentText()
        ext = ".png" if fmt == "Original" else ".jpg"
        saved = 0
        failed = 0
        for i, c in enumerate(self.candidates):
            try:
                f = self._get_output_frame(c)
                out_path = str(Path(d) / f"thumbnail_{stem}_#{i + 1}{ext}")
                if ext == ".png":
                    ok = cv2.imwrite(out_path, f)
                else:
                    ok = cv2.imwrite(out_path, f, [cv2.IMWRITE_JPEG_QUALITY, 95])
                if ok:
                    saved += 1
                else:
                    failed += 1
                    logger.warning("Failed to write: %s", out_path)
            except Exception as exc:
                failed += 1
                logger.error("Save all failed for #%d: %s", i + 1, exc)
        logger.info("Saved %d/%d thumbnails to %s (failures: %d)",
                     saved, len(self.candidates), d, failed)
        if failed:
            QMessageBox.warning(self, "Save All",
                                f"Saved {saved} thumbnails. {failed} failed.")
        self.status_bar.showMessage(
            f"Saved {saved} \u2192 {d}" + (f" ({failed} failed)" if failed else ""))

    def _on_save_selected(self, selected_cands: list):
        """Save selected thumbnails from the picker grid."""
        if not selected_cands:
            return
        d = QFileDialog.getExistingDirectory(
            self, "Save selected thumbnails")
        if not d:
            return
        stem = Path(self.video_path).stem
        saved = 0
        failed = 0
        for i, c in enumerate(selected_cands):
            try:
                f = self._get_output_frame(c)
                out_path = str(Path(d) / f"thumbnail_{stem}_pick#{i + 1}.jpg")
                ok = cv2.imwrite(out_path, f, [cv2.IMWRITE_JPEG_QUALITY, 95])
                if ok:
                    saved += 1
                else:
                    failed += 1
                    logger.warning("Failed to write: %s", out_path)
            except Exception as exc:
                failed += 1
                logger.error("Save selected failed for #%d: %s", i + 1, exc)
        if failed:
            QMessageBox.warning(self, "Save Selected",
                                f"Saved {saved} thumbnails. {failed} failed.")
        self.status_bar.showMessage(
            f"Saved {saved}/{len(selected_cands)} selected thumbnails \u2192 {d}"
            + (f" ({failed} failed)" if failed else ""))

    def _on_clipboard(self):
        if not self.candidates:
            return
        try:
            c = self.candidates[self.selected_idx]
            f = self._get_output_frame(c)
            rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
            h, w = f.shape[:2]
            qi = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            QApplication.clipboard().setPixmap(QPixmap.fromImage(qi))
            self.status_bar.showMessage("Copied to clipboard")
            logger.info("Copied candidate #%d to clipboard", self.selected_idx + 1)
        except Exception as exc:
            logger.error("Clipboard copy failed: %s", exc)
            QMessageBox.warning(self, "Clipboard Error",
                                f"Failed to copy to clipboard:\n{exc}")

    def _save_idx(self, idx):
        old = self.selected_idx
        self.selected_idx = idx
        self._on_save()
        self.selected_idx = old

    def _copy_idx(self, idx):
        old = self.selected_idx
        self.selected_idx = idx
        self._on_clipboard()
        self.selected_idx = old

    # ── comparison ──

    def _compare_add(self, idx):
        if len(self.candidates) < 2:
            self.status_bar.showMessage("Need at least 2 candidates to compare")
            return
        if self._compare_first is None:
            self._compare_first = idx
            self.status_bar.showMessage(
                f"Compare: selected #{idx + 1} "
                f"\u2014 click another candidate")
        else:
            self._show_comparison(self._compare_first, idx)
            self._compare_first = None

    def _on_compare(self):
        if not self.candidates or len(self.candidates) < 2:
            return
        self._show_comparison(0, 1)

    def _compare_first_reset(self):
        self._compare_first = None

    def _show_comparison(self, a, b):
        if a == b:
            b = (a + 1) % len(self.candidates)
        self._cmp = ComparisonOverlay(self.candidates, [a, b], self)
        self._cmp.closed.connect(lambda: self._compare_first_reset())
        self._cmp.show_comparison()
        self.status_bar.showMessage(
            f"Comparing #{a + 1} vs #{b + 1} "
            f"\u2014 drag to blend, S to swap, ESC to close")

    # ── scrubber ──

    def _on_scrubber(self):
        if not self.video_path or not self.video_info:
            return
        dlg = VideoScrubberDialog(
            self.video_path, self.video_info, self)
        dlg.frame_selected.connect(self._on_filmstrip_seek)
        dlg.exec()

    # ── viewer ──

    def _on_viewer(self):
        if not self.candidates:
            return
        self._viewer_win = ThumbnailViewer(
            self.candidates, start_idx=self.selected_idx, parent=self)
        self._viewer_win.closed.connect(self._on_viewer_closed)
        self._viewer_win.save_requested.connect(self._save_idx)
        self._viewer_win.show()
        self._viewer_win.raise_()
        self._viewer_win.activateWindow()

    def _on_viewer_closed(self, idx):
        if idx < len(self.candidates):
            self.selected_idx = idx
            self._highlight_gallery(idx)
            self._show_preview(idx)
            self._show_breakdown(idx)

    # ── escape ──

    def _on_escape(self):
        if hasattr(self, '_viewer_win') and self._viewer_win.isVisible():
            self._viewer_win.close()
        elif hasattr(self, '_cmp') and self._cmp.isVisible():
            self._cmp.close()
            self._compare_first = None
        elif self.isFullScreen():
            self._toggle_fullscreen()
        else:
            self.close()


# ────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info("Video Thumbnail Picker v5 starting...")
    logger.debug("Python %s", sys.version)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    win.preview.hide()
    win.drop_label.show()
    logger.info("Window created, entering event loop")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
