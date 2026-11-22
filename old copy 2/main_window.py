import os
import logging
from pathlib import Path
from typing import List

import cv2
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QPixmap, QImage, QKeySequence, QShortcut, QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QProgressBar, QScrollArea,
    QFileDialog, QMessageBox, QSplitter, QStatusBar, QFrame, QGroupBox,
    QToolBar, QCheckBox, QGridLayout, QSizePolicy,
    QStackedWidget, QTabWidget, QApplication,
)

from config import PRESETS, ALGORITHM_PROFILES, STYLESHEET, C_SURFACE, C_SUBTEXT, C_GREEN, C_RED
from analysis import Candidate, AnalysisThread, SCORERS, score_faces
from widgets import ZoomablePreview, HistogramWidget, ScoreBreakdownWidget, FilmstripTimeline, GalleryCard
from utils import format_time

logger = logging.getLogger("thumbnail_picker")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Thumbnail Picker")
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

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, stretch=1)

        # === LEFT PANE ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.preview = ZoomablePreview()
        self.preview.setMinimumHeight(400)
        self.preview.setStyleSheet(f"background:#313244; border-radius:8px;")
        left_layout.addWidget(self.preview, stretch=1)

        self.filmstrip = FilmstripTimeline()
        self.filmstrip.clicked.connect(self._seek_time)
        left_layout.addWidget(self.filmstrip)

        splitter.addWidget(left_widget)

        # === RIGHT PANE ===
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
        self.compare_stack = QStackedWidget()
        self.compare_lbl = QLabel("Run analysis to compare top 3 results.")
        self.compare_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compare_lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-style:italic;")
        t_c_lay.addWidget(self.compare_lbl)
        self.tabs.addTab(tab_compare, "Compare")

        right_layout.addWidget(self.tabs, stretch=1)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        
        # Status Bar Setup
        self.status_stage_lbl = QLabel("Ready")
        self.status_stage_lbl.setStyleSheet(f"color: {C_SUBTEXT}; padding: 0 10px;")
        self.statusBar().addWidget(self.status_stage_lbl, 1)
        
        self.progress = QProgressBar()
        self.progress.setFixedWidth(250)
        self.progress.setFixedHeight(22)
        self.progress.setVisible(False)
        self.progress.setFormat("%p%") # Show percentage
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

        self.btn_stop = QPushButton("  Stop")
        self.btn_stop.setObjectName("btnRed")
        self.btn_stop.setVisible(False)
        self.btn_stop.clicked.connect(self._stop_analysis)
        tb.addWidget(self.btn_stop)

        tb.addSeparator()

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
            self.candidates.clear()
            self._refresh_gallery()
            self.filmstrip.set_frames([])
            self.preview.scene().clear()
            logger.info(f"File selected: {path}")

    def _start_analysis(self):
        if not self.video_path: return
        
        self.candidates.clear()
        self.selected_idx = -1
        self._refresh_gallery()
        
        # UI Setup
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status_stage_lbl.setText("Initializing...")
        self.status_lbl.setText("Working...")
        
        self.btn_analyze.setVisible(False)
        self.btn_stop.setVisible(True)
        
        w = ALGORITHM_PROFILES[self.combo_algo.currentText()]
        self._worker = AnalysisThread(
            self.video_path, self.spin_samples.value(), 
            w, self.spin_cands.value(), self.chk_scene.isChecked()
        )
        
        self._worker.stage_changed.connect(self._on_stage_changed)
        self._worker.progress.connect(self._on_progress)
        self._worker.candidate_ready.connect(self._add_candidate)
        self._worker.filmstrip_ready.connect(self.filmstrip.set_frames)
        self._worker.finished_ok.connect(self._finish_analysis)
        self._worker.finished_err.connect(lambda m: QMessageBox.critical(self, "Error", m))
        
        self._worker.start()

    def _stop_analysis(self):
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait(1000)
        self._finish_analysis([], {})

    def _on_stage_changed(self, text: str):
        self.status_stage_lbl.setText(text)
        logger.info(f"Stage changed: {text}")

    def _on_progress(self, current: int, total: int):
        if total > 0:
            self.progress.setValue(int(100 * current / total))

    def _add_candidate(self, cand, cur, tot):
        self.candidates.append(cand)
        if len(self.candidates) == 1:
            self._select(0)

    def _finish_analysis(self, cands, info):
        if cands: self.candidates = cands
        
        self.progress.setVisible(False)
        self.btn_stop.setVisible(False)
        self.btn_analyze.setVisible(True)
        self.status_stage_lbl.setText("Finished")
        self.status_lbl.setText("Ready")
        
        self._refresh_gallery()
        self._refresh_compare_tab()
        
        if self.candidates: self._select(0)
        self.statusBar().showMessage(f"Analysis complete. Found {len(self.candidates)} candidates.", 5000)

    def _change_algo(self, name):
        if not self.candidates: return
        w = ALGORITHM_PROFILES[name]
        for c in self.candidates:
            c.total_score = sum(c.breakdown.get(k, 0) * w.get(k, 0) for k in w)
        self.candidates.sort(key=lambda x: x.total_score, reverse=True)
        self._refresh_gallery()
        self._refresh_compare_tab()
        self.statusBar().showMessage(f"Resorted using {name}", 3000)

    def _refresh_gallery(self):
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            
        display = [c for c in self.candidates if not self._show_starred_only or c.starred]
        cols = 2 
        
        for i, c in enumerate(display):
            try:
                real_idx = self.candidates.index(c)
            except ValueError:
                continue
                
            rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
            h, w = c.frame_bgr.shape[:2]
            qim = QImage(rgb.data, w, h, 3*w, QImage.Format.Format_RGB888)
            card = GalleryCard(real_idx, QPixmap.fromImage(qim), c)
            card.clicked.connect(self._select)
            card.starred_toggled.connect(self._toggle_star)
            self.gallery_layout.addWidget(card, i // cols, i % cols)

    def _refresh_compare_tab(self):
        while self.compare_stack.count():
            w = self.compare_stack.currentWidget()
            self.compare_stack.removeWidget(w)
            w.deleteLater()
        
        if len(self.candidates) < 1: return

        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0,0,0,0)
        
        top3 = self.candidates[:3]
        
        for c in top3:
            col = QWidget()
            col_lay = QVBoxLayout(col)
            
            rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
            h, w = c.frame_bgr.shape[:2]
            qim = QImage(rgb.data, w, h, 3*w, QImage.Format.Format_RGB888)
            pm = QPixmap.fromImage(qim)
            lbl = QLabel()
            lbl.setPixmap(pm.scaled(300, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col_lay.addWidget(lbl)
            
            txt = f"Score: {c.total_score:.2f}\nFaces: {len(c.faces)}\nSharp: {c.breakdown.get('sharpness', 0):.2f}"
            lbl_t = QLabel(txt)
            lbl_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col_lay.addWidget(lbl_t)
            lay.addWidget(col)

        self.compare_stack.addWidget(container)
        self.compare_stack.setCurrentWidget(container)
        self.compare_lbl.setVisible(False)

    def _select(self, idx):
        if idx < 0 or idx >= len(self.candidates): return
        self.selected_idx = idx
        c = self.candidates[idx]
        
        rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        
        preset = PRESETS[self.combo_preset.currentText()]
        if preset:
            tw, th = preset
            ratio = max(tw/pil.width, th/pil.height)
            pil = pil.resize((int(pil.width*ratio), int(pil.height*ratio)), Image.Resampling.LANCZOS)
            left = (pil.width - tw)//2
            top = (pil.height - th)//2
            pil = pil.crop((left, top, left+tw, top+th))
        
        data = pil.tobytes("raw", "RGB")
        qim = QImage(data, pil.width, pil.height, 3*pil.width, QImage.Format.Format_RGB888)
        self.preview.set_pixmap(QPixmap.fromImage(qim), c)
        
        self.histogram.set_data(c.frame_bgr)
        self.breakdown.set_scores(c.breakdown)
        self._refresh_gallery()

    def _toggle_star(self, idx):
        if 0 <= idx < len(self.candidates):
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
        if ret and frame is not None:
            w = ALGORITHM_PROFILES[self.combo_algo.currentText()]
            face_score, faces = score_faces(frame)
            scores = {n: s(frame, None) for n, s in SCORERS.items()}
            scores['faces'] = face_score
            total = sum(scores[k] * w.get(k, 0) for k in w)
            cand = Candidate(frame, float(ts), total, scores, faces=faces)
            self.candidates.insert(0, cand)
            self._refresh_gallery()
            self._select(0)
            self.statusBar().showMessage(f"Added manual frame @ {format_time(ts)}")

    def _save(self):
        if self.selected_idx < 0 or self.selected_idx >= len(self.candidates): return
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
                fname = f"thumb_{format_time(c.timestamp).replace(':','-')}.jpg"
                self._save_image(c, path=os.path.join(folder, fname))
            self.statusBar().showMessage(f"Saved {len(starred)} images.")

    def _save_image(self, cand, path=None):
        pil = Image.fromarray(cv2.cvtColor(cand.frame_bgr, cv2.COLOR_BGR2RGB))
        preset = PRESETS[self.combo_preset.currentText()]
        if preset:
            tw, th = preset
            ratio = max(tw/pil.width, th/pil.height)
            pil = pil.resize((int(pil.width*ratio), int(pil.height*ratio)), Image.Resampling.LANCZOS)
            left = (pil.width - tw)//2
            top = (pil.height - th)//2
            pil = pil.crop((left, top, left+tw, top+th))
        
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Save", f"thumb_{format_time(cand.timestamp).replace(':','-')}.jpg", "JPEG (*.jpg)")
        
        if path:
            pil.save(path, quality=95)
            self.statusBar().showMessage(f"Saved to {path}")