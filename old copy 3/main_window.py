"""Main application window.

Layout overview:
  ┌───────────────────────────────────────────────────┐
  │ Menu bar: File | Edit | View | Help               │
  ├───────────────────────────────────────────────────┤
  │ Toolbar (Open / Analyze / Stop / Grid / Faces / Zoom) │
  ├───────────────────────────────────┬───────────────┤
  │                                   │ Controls      │
  │         Preview canvas            │ ──────────    │
  │      + EmptyStateOverlay          │ Tabs:         │
  │                                   │ Gallery /     │
  │                                   │ Analysis /    │
  │                                   │ Compare / Info│
  │   Filmstrip timeline              │               │
  ├───────────────────────────────────┴───────────────┤
  │ Status bar: stage | ETA | count | progress        │
  └───────────────────────────────────────────────────┘

Features:
  * Settings persistence (window geometry, last-used settings, recent files,
    custom algorithm profiles) via state.SETTINGS.
  * Drag-and-drop video files onto the window.
  * Per-video starred-state sidecar (.vtp.json).
  * Score-threshold slider and multi-criterion sort in the gallery.
  * Re-analyze neighborhood (right-click any candidate → sample ±2s around it).
  * Contact-sheet PNG export.
  * Custom algorithm-profile editor with live normalisation.
  * F1 keyboard-shortcut help.
  * ETA + elapsed time during analysis.
  * Empty-state overlay on the preview area.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, QTimer, QMimeData
from PySide6.QtGui import (
    QPixmap, QImage, QKeySequence, QShortcut, QAction, QDragEnterEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QProgressBar, QScrollArea,
    QFileDialog, QMessageBox, QSplitter, QFrame, QToolBar, QCheckBox,
    QGridLayout, QSizePolicy, QTabWidget, QSlider, QMenu, QApplication,
)

from config import (
    PRESETS, ALGORITHM_PROFILES, STYLESHEET,
    C_SURFACE, C_CARD, C_OVERLAY, C_SUBTEXT, C_TEXT,
    C_GREEN, C_RED, C_BLUE, C_YELLOW, C_LAVENDER, C_TEAL, C_PEACH,
    GALLERY_COLUMNS, SORT_OPTIONS, SCORE_THRESHOLD_DEFAULT,
    REANALYZE_RADIUS_SEC, REANALYZE_SAMPLES, ETA_UPDATE_INTERVAL_MS,
    CARD_SIZES, DEFAULT_CARD_SIZE, FILENAME_TEMPLATES, DEFAULT_FILENAME_TEMPLATE,
    THEMES, DEFAULT_THEME, THEME_DARK, THEME_LIGHT,
    get_theme_colors, build_stylesheet,
)
from analysis import Candidate, AnalysisThread, SCORERS, score_faces
from widgets import (
    ZoomablePreview, HistogramWidget, ScoreBreakdownWidget,
    FilmstripTimeline, GalleryCard, EmptyStateOverlay, TimelineHeatmap,
)
from utils import (
    THUMBS, format_time, format_duration, fit_crop_pil,
    downscale_for_scoring,
)
from state import SETTINGS, ProjectState
from framestore import FRAME_STORE
from dialogs import (
    WeightsEditorDialog, ShortcutHelpDialog, ContactSheetDialog, AboutDialog,
    PreferencesDialog, save_candidates_to_json, load_candidates_from_json,
)

logger = logging.getLogger("thumbnail_picker")

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".wmv"}


class MainWindow(QMainWindow):
    """Top-level window for the Video Thumbnail Picker."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Video Thumbnail Picker")
        self.resize(1600, 950)
        self.setMinimumSize(1200, 720)
        self.setAcceptDrops(True)

        # ---- state ----
        self.video_path: Optional[str] = None
        self.video_info: Dict = {}
        self.candidates: List[Candidate] = []
        self.selected_idx: int = -1
        self._worker: Optional[AnalysisThread] = None
        self._show_starred_only: bool = False
        self._score_threshold: float = SCORE_THRESHOLD_DEFAULT
        self._gallery_cards: Dict[int, GalleryCard] = {}
        self._all_profiles: Dict[str, Dict[str, float]] = {}
        self._append_mode: bool = False
        self._analysis_start_time: float = 0.0
        self._eta_timer = QTimer(self)
        self._eta_timer.timeout.connect(self._update_eta)
        # New v2.2 state
        self._card_size: str = DEFAULT_CARD_SIZE
        self._theme: str = DEFAULT_THEME
        self._filename_template: str = DEFAULT_FILENAME_TEMPLATE
        self._auto_free_memory: bool = False
        self._multi_selected: set = set()  # set of candidate id()s

        # ---- build UI ----
        self._ui()
        self._menu_bar()
        self._toolbar()
        self._shortcuts()
        self.setStyleSheet(STYLESHEET)

        # ---- restore saved settings ----
        self._restore_settings()

    # ════════════════════════════════════════════════════════════════════
    # UI CONSTRUCTION
    # ════════════════════════════════════════════════════════════════════
    def _ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(8)

        # Top header bar
        header = QFrame()
        header.setObjectName("Card")
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(12, 8, 12, 8)
        header_lay.setSpacing(12)

        title = QLabel("Video Thumbnail Picker")
        title.setObjectName("LblTitle")
        header_lay.addWidget(title)
        header_lay.addStretch()

        self.header_file_lbl = QLabel("No file loaded")
        self.header_file_lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
        header_lay.addWidget(self.header_file_lbl)
        root.addWidget(header)

        # Splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(6)
        root.addWidget(self._splitter, stretch=1)

        # ─── LEFT PANE ───
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Preview container (holds the preview + empty-state overlay)
        self.preview_container = QFrame()
        self.preview_container.setStyleSheet(f"background:{C_CARD}; border-radius:8px;")
        pc_lay = QVBoxLayout(self.preview_container)
        pc_lay.setContentsMargins(0, 0, 0, 0)
        pc_lay.setSpacing(0)

        self.preview = ZoomablePreview()
        self.preview.setMinimumHeight(420)
        self.preview.setStyleSheet("background: transparent; border: none;")
        pc_lay.addWidget(self.preview)

        self.empty_overlay = EmptyStateOverlay(self.preview_container)
        self.empty_overlay.set_open_callback(self._open_file)
        pc_lay.addWidget(self.empty_overlay)

        left_layout.addWidget(self.preview_container, stretch=1)

        self.filmstrip = FilmstripTimeline()
        self.filmstrip.clicked.connect(self._seek_time)
        left_layout.addWidget(self.filmstrip)

        # Score heatmap — shows each candidate's score on a timeline
        self.heatmap = TimelineHeatmap()
        self.heatmap.clicked.connect(self._select)
        left_layout.addWidget(self.heatmap)

        self._splitter.addWidget(left_widget)

        # ─── RIGHT PANE ───
        right_widget = QWidget()
        right_widget.setMaximumWidth(520)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        right_layout.addWidget(self._build_control_card())

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self._build_gallery_tab()
        self._build_analysis_tab()
        self._build_compare_tab()
        self._build_info_tab()
        right_layout.addWidget(self.tabs, stretch=1)

        self._splitter.addWidget(right_widget)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([1000, 520])

        # ─── status bar ───
        self.status_stage_lbl = QLabel("Ready")
        self.status_stage_lbl.setStyleSheet(f"color:{C_SUBTEXT}; padding:0 10px;")
        self.statusBar().addWidget(self.status_stage_lbl, 1)

        self.status_eta_lbl = QLabel("")
        self.status_eta_lbl.setStyleSheet(f"color:{C_PEACH}; padding:0 10px;")
        self.statusBar().addWidget(self.status_eta_lbl)

        self.status_count_lbl = QLabel("0 candidates")
        self.status_count_lbl.setStyleSheet(f"color:{C_SUBTEXT}; padding:0 10px;")
        self.statusBar().addPermanentWidget(self.status_count_lbl)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(240)
        self.progress.setFixedHeight(20)
        self.progress.setVisible(False)
        self.progress.setFormat("%p%")
        self.statusBar().addPermanentWidget(self.progress)

    # -- control card ------------------------------------------------------
    def _build_control_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        # Algorithm row
        row1 = QHBoxLayout()
        lbl = QLabel("Algorithm"); lbl.setObjectName("LblSection"); lbl.setMinimumWidth(64)
        row1.addWidget(lbl)
        self.combo_algo = QComboBox()
        self.combo_algo.currentTextChanged.connect(self._change_algo)
        row1.addWidget(self.combo_algo, stretch=1)

        self.btn_edit_weights = QPushButton("Edit…")
        self.btn_edit_weights.setToolTip("Edit weights for the current algorithm profile")
        self.btn_edit_weights.clicked.connect(self._edit_weights)
        row1.addWidget(self.btn_edit_weights)
        v.addLayout(row1)

        # Output preset row
        row2 = QHBoxLayout()
        lbl = QLabel("Output"); lbl.setObjectName("LblSection"); lbl.setMinimumWidth(64)
        row2.addWidget(lbl)
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(PRESETS.keys())
        self.combo_preset.currentTextChanged.connect(self._on_preset_changed)
        row2.addWidget(self.combo_preset, stretch=1)
        v.addLayout(row2)

        # Advanced row
        row3 = QHBoxLayout()
        self.chk_scene = QCheckBox("Scene Detect")
        self.chk_scene.setToolTip("Run scene-change detection before sampling. Slower but smarter.")
        row3.addWidget(self.chk_scene)

        row3.addWidget(QLabel("Samples:"))
        self.spin_samples = QSpinBox()
        self.spin_samples.setRange(20, 400)
        self.spin_samples.setValue(80)
        self.spin_samples.setToolTip("Number of frames to score (more = slower, more thorough)")
        row3.addWidget(self.spin_samples)

        row3.addWidget(QLabel("Max:"))
        self.spin_cands = QSpinBox()
        self.spin_cands.setRange(4, 60)
        self.spin_cands.setValue(15)
        self.spin_cands.setToolTip("Maximum candidates to keep after dedup")
        row3.addWidget(self.spin_cands)
        row3.addStretch()
        v.addLayout(row3)

        # Action row
        row4 = QHBoxLayout()
        self.btn_save = QPushButton("  Save Selected  ")
        self.btn_save.setObjectName("btnGreen")
        self.btn_save.setToolTip("Save the currently selected frame (Ctrl+S)")
        self.btn_save.clicked.connect(self._save)
        row4.addWidget(self.btn_save, stretch=1)

        self.btn_batch = QPushButton("  Save Starred  ")
        self.btn_batch.setToolTip("Save every starred frame to a folder (Ctrl+Shift+S)")
        self.btn_batch.clicked.connect(self._batch_save)
        row4.addWidget(self.btn_batch, stretch=1)
        v.addLayout(row4)

        return card

    # -- tabs --------------------------------------------------------------
    def _build_gallery_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)

        # Filter row 1: starred + sort + card size
        filter_row1 = QHBoxLayout()
        self.chk_starred = QCheckBox("Starred only")
        self.chk_starred.stateChanged.connect(self._on_filter_changed)
        filter_row1.addWidget(self.chk_starred)
        filter_row1.addStretch()

        filter_row1.addWidget(QLabel("Sort:"))
        self.combo_sort = QComboBox()
        for name, _, _ in SORT_OPTIONS:
            self.combo_sort.addItem(name)
        self.combo_sort.currentTextChanged.connect(self._on_sort_changed)
        filter_row1.addWidget(self.combo_sort)

        filter_row1.addWidget(QLabel("Size:"))
        self.combo_card_size = QComboBox()
        self.combo_card_size.addItems(CARD_SIZES)
        self.combo_card_size.currentTextChanged.connect(self._on_card_size_changed)
        filter_row1.addWidget(self.combo_card_size)
        lay.addLayout(filter_row1)

        # Filter row 2: score threshold slider
        filter_row2 = QHBoxLayout()
        filter_row2.addWidget(QLabel("Min score:"))
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(0, 100)
        self.threshold_slider.setValue(0)
        self.threshold_slider.setToolTip("Hide candidates below this score")
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        filter_row2.addWidget(self.threshold_slider, stretch=1)

        self.threshold_lbl = QLabel("0.00")
        self.threshold_lbl.setMinimumWidth(36)
        self.threshold_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono','Consolas',monospace; color:{C_GREEN}; font-size:11px;"
        )
        filter_row2.addWidget(self.threshold_lbl)
        lay.addLayout(filter_row2)

        # Multi-select actions row (visible only when multi_selected is non-empty)
        self.multi_select_bar = QFrame()
        self.multi_select_bar.setObjectName("Card")
        ms_lay = QHBoxLayout(self.multi_select_bar)
        ms_lay.setContentsMargins(8, 4, 8, 4)
        ms_lay.setSpacing(6)
        self.ms_count_lbl = QLabel("0 selected")
        self.ms_count_lbl.setStyleSheet(f"color:{C_TEAL}; font-weight:bold;")
        ms_lay.addWidget(self.ms_count_lbl)
        ms_lay.addStretch()

        self.btn_ms_star = QPushButton("Star")
        self.btn_ms_star.clicked.connect(lambda: self._multi_apply("star"))
        ms_lay.addWidget(self.btn_ms_star)

        self.btn_ms_unstar = QPushButton("Unstar")
        self.btn_ms_unstar.clicked.connect(lambda: self._multi_apply("unstar"))
        ms_lay.addWidget(self.btn_ms_unstar)

        self.btn_ms_clear = QPushButton("Clear")
        self.btn_ms_clear.clicked.connect(self._clear_multi_select)
        ms_lay.addWidget(self.btn_ms_clear)

        self.multi_select_bar.setVisible(False)
        lay.addWidget(self.multi_select_bar)

        # Gallery area
        self.gallery_area = QScrollArea()
        self.gallery_area.setWidgetResizable(True)
        self.gallery_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.gallery_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.gallery_container = QWidget()
        self.gallery_container.setStyleSheet("background: transparent;")
        self.gallery_layout = QGridLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(4, 4, 4, 4)
        self.gallery_layout.setSpacing(8)
        self.gallery_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.gallery_area.setWidget(self.gallery_container)
        lay.addWidget(self.gallery_area, stretch=1)

        self.tabs.addTab(tab, "Gallery")

    def _build_analysis_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        lbl1 = QLabel("RGB Histogram"); lbl1.setObjectName("LblSection")
        lay.addWidget(lbl1)
        self.histogram = HistogramWidget()
        lay.addWidget(self.histogram)

        lbl2 = QLabel("Score Breakdown"); lbl2.setObjectName("LblSection")
        lay.addWidget(lbl2)
        self.breakdown = ScoreBreakdownWidget()
        lay.addWidget(self.breakdown, stretch=1)
        self.tabs.addTab(tab, "Analysis")

    def _build_compare_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 8, 8, 8)
        self.compare_container = QWidget()
        self.compare_lay = QHBoxLayout(self.compare_container)
        self.compare_lay.setContentsMargins(0, 0, 0, 0)
        self.compare_lay.setSpacing(8)
        lay.addWidget(self.compare_container, stretch=1)

        self.compare_placeholder = QLabel("Run analysis to compare top 3 results.")
        self.compare_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compare_placeholder.setStyleSheet(f"color:{C_SUBTEXT}; font-style:italic;")
        lay.addWidget(self.compare_placeholder)
        self.compare_placeholder.hide()

        self.tabs.addTab(tab, "Compare")

    def _build_info_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        sec1 = QLabel("VIDEO"); sec1.setObjectName("LblSection")
        lay.addWidget(sec1)
        self.info_video_grid = self._build_info_grid([
            ("File:", ""), ("Duration:", ""), ("Resolution:", ""),
            ("FPS:", ""), ("Total frames:", ""),
        ])
        lay.addWidget(self.info_video_grid)

        sec2 = QLabel("SELECTED CANDIDATE"); sec2.setObjectName("LblSection")
        lay.addWidget(sec2)
        self.info_cand_grid = self._build_info_grid([
            ("Rank:", "—"), ("Timestamp:", "—"), ("Score:", "—"),
            ("Faces:", "—"), ("Sharpness:", "—"), ("Contrast:", "—"),
            ("Brightness:", "—"), ("Composition:", "—"),
        ])
        lay.addWidget(self.info_cand_grid)
        lay.addStretch()
        self.tabs.addTab(tab, "Info")

    def _build_info_grid(self, rows: List[tuple]) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background:{C_CARD}; border-radius:6px; }}")
        grid = QGridLayout(frame)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        for i, (label, value) in enumerate(rows):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
            val = QLabel(value)
            val.setStyleSheet(
                f"color:{C_TEXT}; font-family:'JetBrains Mono','Consolas',monospace; font-size:11px;"
            )
            grid.addWidget(lbl, i, 0)
            grid.addWidget(val, i, 1)
            attr_name = f"_info_{label.rstrip(':').lower().replace(' ', '_')}"
            setattr(self, attr_name, val)
        return frame

    # -- menu bar ----------------------------------------------------------
    def _menu_bar(self) -> None:
        mb = self.menuBar()

        # File menu
        file_menu = mb.addMenu("&File")
        self.act_open = QAction("&Open Video…", self)
        self.act_open.setShortcut("Ctrl+O")
        self.act_open.triggered.connect(self._open_file)
        file_menu.addAction(self.act_open)

        self.recent_menu = file_menu.addMenu("Open &Recent")
        self._refresh_recent_menu()

        file_menu.addSeparator()

        self.act_save_list = QAction("&Save Candidate List…", self)
        self.act_save_list.setShortcut("Ctrl+Shift+J")
        self.act_save_list.triggered.connect(self._save_candidate_list)
        file_menu.addAction(self.act_save_list)

        self.act_load_list = QAction("&Load Candidate List…", self)
        self.act_load_list.setShortcut("Ctrl+J")
        self.act_load_list.triggered.connect(self._load_candidate_list)
        file_menu.addAction(self.act_load_list)

        file_menu.addSeparator()

        self.act_contact = QAction("Export &Contact Sheet…", self)
        self.act_contact.setShortcut("Ctrl+E")
        self.act_contact.triggered.connect(self._export_contact_sheet)
        file_menu.addAction(self.act_contact)

        file_menu.addSeparator()

        self.act_quit = QAction("&Quit", self)
        self.act_quit.setShortcut("Ctrl+Q")
        self.act_quit.triggered.connect(self.close)
        file_menu.addAction(self.act_quit)

        # Edit menu
        edit_menu = mb.addMenu("&Edit")
        self.act_edit_weights = QAction("Edit Algorithm &Weights…", self)
        self.act_edit_weights.triggered.connect(self._edit_weights)
        edit_menu.addAction(self.act_edit_weights)

        self.act_auto_select = QAction("&Auto-Select Best", self)
        self.act_auto_select.setShortcut("Ctrl+Space")
        self.act_auto_select.triggered.connect(self._auto_select_best)
        edit_menu.addAction(self.act_auto_select)

        edit_menu.addSeparator()

        self.act_prefs = QAction("&Preferences…", self)
        self.act_prefs.setShortcut("Ctrl+,")
        self.act_prefs.triggered.connect(self._show_preferences)
        edit_menu.addAction(self.act_prefs)

        # View menu
        view_menu = mb.addMenu("&View")
        self.act_grid = QAction("&Rule-of-thirds Grid", self, checkable=True)
        self.act_grid.setShortcut("G")
        self.act_grid.triggered.connect(self._toggle_grid)
        view_menu.addAction(self.act_grid)

        self.act_faces = QAction("&Face Overlay", self, checkable=True)
        self.act_faces.setShortcut("F")
        self.act_faces.triggered.connect(self._toggle_faces)
        view_menu.addAction(self.act_faces)

        view_menu.addSeparator()

        self.act_fit = QAction("&Fit to View", self)
        self.act_fit.setShortcut("F2")
        self.act_fit.triggered.connect(self.preview.fit)
        view_menu.addAction(self.act_fit)

        view_menu.addSeparator()

        self.act_toggle_theme = QAction("Toggle &Theme", self)
        self.act_toggle_theme.setShortcut("Ctrl+T")
        self.act_toggle_theme.triggered.connect(self._toggle_theme)
        view_menu.addAction(self.act_toggle_theme)

        self.act_free_memory = QAction("Free &Memory", self)
        self.act_free_memory.setShortcut("Ctrl+M")
        self.act_free_memory.triggered.connect(self._free_memory)
        view_menu.addAction(self.act_free_memory)

        # Help menu
        help_menu = mb.addMenu("&Help")
        self.act_shortcuts = QAction("&Keyboard Shortcuts", self)
        self.act_shortcuts.setShortcut("F1")
        self.act_shortcuts.triggered.connect(self._show_shortcuts)
        help_menu.addAction(self.act_shortcuts)

        self.act_about = QAction("&About", self)
        self.act_about.triggered.connect(self._show_about)
        help_menu.addAction(self.act_about)

    # -- toolbar -----------------------------------------------------------
    def _toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.btn_open = QPushButton("  Open Video")
        self.btn_open.setObjectName("btnPrimary")
        self.btn_open.setToolTip("Open a video file (Ctrl+O)")
        self.btn_open.clicked.connect(self._open_file)
        tb.addWidget(self.btn_open)

        self.btn_analyze = QPushButton("  Analyze")
        self.btn_analyze.setToolTip("Run thumbnail analysis (Space)")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.clicked.connect(self._start_analysis)
        tb.addWidget(self.btn_analyze)

        self.btn_stop = QPushButton("  Stop")
        self.btn_stop.setObjectName("btnRed")
        self.btn_stop.setVisible(False)
        self.btn_stop.clicked.connect(self._stop_analysis)
        tb.addWidget(self.btn_stop)

        tb.addSeparator()

        zoom_in = QPushButton("+")
        zoom_in.setFixedSize(30, 28)
        zoom_in.setToolTip("Zoom in (Ctrl+=)")
        zoom_in.clicked.connect(self.preview.zoom_in)
        tb.addWidget(zoom_in)

        zoom_out = QPushButton("−")
        zoom_out.setFixedSize(30, 28)
        zoom_out.setToolTip("Zoom out (Ctrl+-)")
        zoom_out.clicked.connect(self.preview.zoom_out)
        tb.addWidget(zoom_out)

        fit_btn = QPushButton("Fit")
        fit_btn.setFixedSize(36, 28)
        fit_btn.setToolTip("Fit to view (F2)")
        fit_btn.clicked.connect(self.preview.fit)
        tb.addWidget(fit_btn)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet(f"color:{C_SUBTEXT}; padding-right:10px;")
        tb.addWidget(self.status_lbl)

    # -- shortcuts ---------------------------------------------------------
    def _shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"),          self, self._save)
        QShortcut(QKeySequence("Ctrl+Shift+S"),    self, self._batch_save)
        QShortcut(QKeySequence("Ctrl+J"),          self, self._load_candidate_list)
        QShortcut(QKeySequence("Ctrl+Shift+J"),    self, self._save_candidate_list)
        QShortcut(QKeySequence(Qt.Key.Key_Left),   self, lambda: self._nav(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Right),  self, lambda: self._nav(1))
        QShortcut(QKeySequence("Ctrl+="),          self, self.preview.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"),          self, self.preview.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"),          self, self.preview.fit)
        QShortcut(QKeySequence("Ctrl+T"),          self, self._toggle_theme)
        QShortcut(QKeySequence("Ctrl+M"),          self, self._free_memory)
        QShortcut(QKeySequence("Ctrl+,"),          self, self._show_preferences)
        QShortcut(QKeySequence(Qt.Key.Key_Space),  self, self._toggle_analysis)
        QShortcut(QKeySequence(Qt.Key.Key_S),      self, self._star_current)
        QShortcut(QKeySequence(Qt.Key.Key_R),      self, self._reanalyze_current)
        QShortcut(QKeySequence("Escape"),          self, self._on_escape)

    def _on_escape(self) -> None:
        """Escape clears multi-selection if any, otherwise stops analysis."""
        if self._multi_selected:
            self._clear_multi_select()
        else:
            self._stop_analysis()

    # ════════════════════════════════════════════════════════════════════
    # SETTINGS SAVE / RESTORE
    # ════════════════════════════════════════════════════════════════════
    def _restore_settings(self) -> None:
        SETTINGS.restore_window_state(self)
        sizes = SETTINGS.splitter_sizes()
        if sizes and len(sizes) == 2:
            self._splitter.setSizes(sizes)

        s = SETTINGS.restore_analysis_settings()
        # Merge built-in + custom profiles
        self._all_profiles = dict(ALGORITHM_PROFILES)
        self._all_profiles.update(SETTINGS.custom_profiles)
        self.combo_algo.blockSignals(True)
        self.combo_algo.clear()
        for name in self._all_profiles:
            self.combo_algo.addItem(name)
        if s["algo"] in self._all_profiles:
            self.combo_algo.setCurrentText(s["algo"])
        self.combo_algo.blockSignals(False)

        if s["preset"] in PRESETS:
            self.combo_preset.setCurrentText(s["preset"])
        self.spin_samples.setValue(s["samples"])
        self.spin_cands.setValue(s["cands"])
        self.chk_scene.setChecked(s["scene"])
        if any(s["sort"] == name for name, _, _ in SORT_OPTIONS):
            self.combo_sort.setCurrentText(s["sort"])
        self._score_threshold = s["threshold"]
        self.threshold_slider.setValue(int(s["threshold"] * 100))
        self.threshold_lbl.setText(f"{s['threshold']:.2f}")

        # Restore UI preferences
        self._card_size = SETTINGS.card_size if SETTINGS.card_size in CARD_SIZES else DEFAULT_CARD_SIZE
        self._theme = SETTINGS.theme if SETTINGS.theme in THEMES else DEFAULT_THEME
        self._filename_template = SETTINGS.filename_template or DEFAULT_FILENAME_TEMPLATE
        self._auto_free_memory = SETTINGS.auto_free_memory
        self.combo_card_size.blockSignals(True)
        self.combo_card_size.setCurrentText(self._card_size)
        self.combo_card_size.blockSignals(False)
        self._apply_theme()

    def _save_settings(self) -> None:
        SETTINGS.save_window_state(self)
        SETTINGS.save_analysis_settings(
            algo=self.combo_algo.currentText(),
            preset=self.combo_preset.currentText(),
            samples=self.spin_samples.value(),
            cands=self.spin_cands.value(),
            scene=self.chk_scene.isChecked(),
            sort=self.combo_sort.currentText(),
            threshold=self._score_threshold,
        )
        SETTINGS.card_size = self._card_size
        SETTINGS.theme = self._theme
        SETTINGS.filename_template = self._filename_template
        SETTINGS.auto_free_memory = self._auto_free_memory
        SETTINGS.sync()

    # ── Theme ─────────────────────────────────────────────────────────
    def _apply_theme(self) -> None:
        """Apply the current theme by rebuilding the stylesheet."""
        colors = get_theme_colors(self._theme)
        self.setStyleSheet(build_stylesheet(colors))

    def _toggle_theme(self) -> None:
        self._theme = THEME_LIGHT if self._theme == THEME_DARK else THEME_DARK
        self._apply_theme()
        self.statusBar().showMessage(f"Theme: {self._theme}", 2000)

    # ── Card size ─────────────────────────────────────────────────────
    def _on_card_size_changed(self, size: str) -> None:
        if size not in CARD_SIZES:
            return
        self._card_size = size
        self._gallery_cards.clear()
        self._refresh_gallery()
        self.statusBar().showMessage(f"Card size: {size}", 2000)

    # ── Memory ────────────────────────────────────────────────────────
    def _free_memory(self) -> None:
        """Release all full-res frames from memory; they'll lazy-load on demand."""
        if not self.candidates:
            self.statusBar().showMessage("No candidates to free.", 2000)
            return
        released = 0
        for c in self.candidates:
            if c.frame_bgr is not None:
                c.release_frame()
                released += 1
        THUMBS.invalidate()
        # Refresh visible gallery cards so they re-fetch from disk
        for card in self._gallery_cards.values():
            card.refresh_thumbnail()
        self.statusBar().showMessage(
            f"Freed {released} frames from memory ({FRAME_STORE.stats()['entries']} in LRU cache).",
            4000
        )

    # ════════════════════════════════════════════════════════════════════
    # DRAG & DROP
    # ════════════════════════════════════════════════════════════════════
    def dragEnterEvent(self, e: QDragEnterEvent) -> None:  # type: ignore[override]
        if e.mimeData().hasUrls():
            for url in e.mimeData().urls():
                path = url.toLocalFile()
                if Path(path).suffix.lower() in VIDEO_EXTS:
                    e.acceptProposedAction()
                    return
        e.ignore()

    def dropEvent(self, e: QDropEvent) -> None:  # type: ignore[override]
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).suffix.lower() in VIDEO_EXTS:
                self._open_file_path(path)
                e.acceptProposedAction()
                return
        e.ignore()

    # ════════════════════════════════════════════════════════════════════
    # FILE LOADING
    # ════════════════════════════════════════════════════════════════════
    def _open_file(self) -> None:
        last_dir = SETTINGS.last_dir or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", last_dir,
            "Video (*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.flv *.wmv);;All Files (*)"
        )
        if path:
            self._open_file_path(path)

    def _open_file_path(self, path: str) -> None:
        if not Path(path).exists():
            QMessageBox.warning(self, "File not found", f"The file does not exist:\n{path}")
            return
        self.video_path = path
        name = Path(path).name
        self.header_file_lbl.setText(name)
        self.statusBar().showMessage(f"Loaded: {name}", 4000)
        self.status_lbl.setText(name)
        self.btn_analyze.setEnabled(True)
        SETTINGS.add_recent_file(path)
        SETTINGS.last_dir = str(Path(path).parent)
        self._refresh_recent_menu()

        # Reset state
        self.candidates.clear()
        self._gallery_cards.clear()
        THUMBS.invalidate()
        self.selected_idx = -1
        self._multi_selected.clear()
        self._refresh_gallery()
        self.filmstrip.set_frames([])
        self.heatmap.clear_data()
        self.preview.scene().clear()
        self._refresh_info_video({"path": path})
        self._refresh_info_cand(None)
        self.empty_overlay.set_mode("no_analysis")

    def _refresh_recent_menu(self) -> None:
        self.recent_menu.clear()
        files = SETTINGS.recent_files
        if not files:
            act = self.recent_menu.addAction("(No recent files)")
            act.setEnabled(False)
            return
        for f in files:
            name = Path(f).name
            act = self.recent_menu.addAction(name)
            act.setToolTip(f)
            act.triggered.connect(lambda checked=False, p=f: self._open_file_path(p))
        self.recent_menu.addSeparator()
        clear_act = self.recent_menu.addAction("Clear recent list")
        clear_act.triggered.connect(self._clear_recent)

    def _clear_recent(self) -> None:
        SETTINGS.clear_recent_files()
        self._refresh_recent_menu()

    # ════════════════════════════════════════════════════════════════════
    # ANALYSIS LIFECYCLE
    # ════════════════════════════════════════════════════════════════════
    def _toggle_analysis(self) -> None:
        if self._worker and self._worker.isRunning():
            self._stop_analysis()
        else:
            self._start_analysis()

    def _start_analysis(self, append: bool = False,
                        sample_times: Optional[List[float]] = None) -> None:
        if not self.video_path:
            return
        self._append_mode = append

        if not append:
            # Full reset
            self.candidates.clear()
            self._gallery_cards.clear()
            THUMBS.invalidate()
            self.selected_idx = -1
            self._refresh_gallery()
            self.compare_placeholder.show()
            self._clear_compare_tab()
        else:
            # Append mode: just clear cards so they get recreated with new ranks
            self._gallery_cards.clear()

        # UI busy state
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status_stage_lbl.setText("Initializing…")
        self.status_lbl.setText("Working…")
        self.status_count_lbl.setText(f"{len(self.candidates)} candidates")
        self.btn_analyze.setVisible(False)
        self.btn_stop.setVisible(True)
        self.btn_open.setEnabled(False)
        self.empty_overlay.set_mode("hidden")

        # ETA
        self._analysis_start_time = time.monotonic()
        self._eta_timer.start(ETA_UPDATE_INTERVAL_MS)

        weights = self._all_profiles.get(self.combo_algo.currentText(),
                                         ALGORITHM_PROFILES["General (Balanced)"])
        skip_filmstrip = append or (sample_times is not None)
        self._worker = AnalysisThread(
            self.video_path, self.spin_samples.value(),
            weights, self.spin_cands.value(), self.chk_scene.isChecked(),
            sample_times_override=sample_times,
            skip_filmstrip=skip_filmstrip,
        )
        self._worker.stage_changed.connect(self._on_stage_changed)
        self._worker.progress.connect(self._on_progress)
        self._worker.candidate_ready.connect(self._on_candidate_ready)
        self._worker.filmstrip_ready.connect(self._on_filmstrip_ready)
        self._worker.finished_ok.connect(self._finish_analysis)
        self._worker.finished_err.connect(self._on_analysis_err)
        self._worker.start()

    def _on_filmstrip_ready(self, frames) -> None:
        # Only replace filmstrip if we actually generated one (skip in append mode)
        if frames:
            self.filmstrip.set_frames(frames)

    def _stop_analysis(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait(1500)
        self._finish_analysis([], {})

    def _on_stage_changed(self, text: str) -> None:
        self.status_stage_lbl.setText(text)
        logger.info(f"Stage: {text}")

    def _on_progress(self, current: int, total: int) -> None:
        if total > 0:
            self.progress.setValue(int(100 * current / total))

    def _update_eta(self) -> None:
        if not self._analysis_start_time:
            return
        elapsed = time.monotonic() - self._analysis_start_time
        pct = self.progress.value()
        if pct > 0:
            total_est = elapsed / (pct / 100.0)
            eta = max(0, total_est - elapsed)
            self.status_eta_lbl.setText(
                f"⏱ {self._fmt_time(elapsed)} elapsed / ~{self._fmt_time(eta)} remaining"
            )
        else:
            self.status_eta_lbl.setText(f"⏱ {self._fmt_time(elapsed)} elapsed")

    @staticmethod
    def _fmt_time(s: float) -> str:
        if s < 60:
            return f"{s:.0f}s"
        m, s = divmod(int(s), 60)
        return f"{m}m {s}s"

    def _on_candidate_ready(self, cand: Candidate, _cur: int, _tot: int) -> None:
        QTimer.singleShot(0, lambda c=cand: self._add_candidate_main(c))

    def _add_candidate_main(self, cand: Candidate) -> None:
        self.candidates.append(cand)
        self.status_count_lbl.setText(f"{len(self.candidates)} candidates")
        self._make_card(cand)
        if self.selected_idx < 0:
            self._select(0)

    def _finish_analysis(self, cands: List[Candidate], info: Dict) -> None:
        self._eta_timer.stop()
        self.status_eta_lbl.setText("")

        if self._append_mode:
            # Merge new candidates into existing list
            if cands:
                self.candidates.extend(cands)
            # Re-sort
            self._apply_sort()
            # Apply starred state from sidecar
            self._apply_starred_state()
        else:
            if cands:
                self.candidates = cands
                self._gallery_cards.clear()
                THUMBS.invalidate()
            if info:
                self.video_info = info
                self._refresh_info_video(info)
            # Apply starred state from sidecar
            self._apply_starred_state()

        # Auto-free memory if enabled
        if self._auto_free_memory and self.candidates:
            freed = 0
            for c in self.candidates:
                if c.frame_bgr is not None:
                    c.release_frame()
                    freed += 1
            logger.info(f"Auto-freed {freed} frames from memory")

        self.progress.setVisible(False)
        self.btn_stop.setVisible(False)
        self.btn_analyze.setVisible(True)
        self.btn_open.setEnabled(True)
        self.status_stage_lbl.setText("Finished")
        self.status_lbl.setText("Ready")

        self._refresh_gallery()
        self._refresh_compare_tab()
        self.status_count_lbl.setText(f"{len(self.candidates)} candidates")
        if self.candidates:
            self._select(0)
        else:
            self.empty_overlay.set_mode("no_analysis")
        self.statusBar().showMessage(
            f"Analysis complete — {len(self.candidates)} candidates.", 5000
        )

    def _on_analysis_err(self, msg: str) -> None:
        self._finish_analysis([], {})
        QMessageBox.critical(self, "Error", msg)

    # ════════════════════════════════════════════════════════════════════
    # STARRED STATE PERSISTENCE
    # ════════════════════════════════════════════════════════════════════
    def _apply_starred_state(self) -> None:
        """Load sidecar and mark matching candidates as starred."""
        if not self.video_path:
            return
        data = ProjectState.load(self.video_path)
        starred_ts = data.get("starred_timestamps", [])
        if not starred_ts:
            return
        for c in self.candidates:
            if any(abs(c.timestamp - ts) < 0.05 for ts in starred_ts):
                c.starred = True

    def _save_starred_state(self) -> None:
        if self.video_path and self.candidates:
            ProjectState.save(self.video_path, self.candidates)

    # ════════════════════════════════════════════════════════════════════
    # GALLERY
    # ════════════════════════════════════════════════════════════════════
    def _make_card(self, cand: Candidate) -> Optional[GalleryCard]:
        if id(cand) in self._gallery_cards:
            return self._gallery_cards[id(cand)]
        try:
            real_idx = self.candidates.index(cand)
        except ValueError:
            return None
        card = GalleryCard(real_idx, cand, size=self._card_size)
        card.clicked.connect(self._select)
        card.starred_toggled.connect(self._toggle_star)
        card.reanalyze_requested.connect(self._reanalyze_idx)
        card.multi_select_toggled.connect(self._on_multi_select_toggled)
        # Apply current multi-select state
        if id(cand) in self._multi_selected:
            card.set_multi_selected(True)
        self._gallery_cards[id(cand)] = card
        return card

    def _apply_sort(self) -> None:
        """Sort candidates by the currently-selected criterion."""
        if not self.candidates:
            return
        sort_name = self.combo_sort.currentText()
        for name, key, reverse in SORT_OPTIONS:
            if name == sort_name:
                if key is None:
                    self.candidates.sort(key=lambda c: c.total_score, reverse=reverse)
                else:
                    self.candidates.sort(
                        key=lambda c: c.breakdown.get(key, 0.0) if key != "timestamp" else c.timestamp,
                        reverse=reverse,
                    )
                break

    def _refresh_gallery(self) -> None:
        """Rebuild the gallery grid (structural changes only)."""
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.setParent(None)

        self._apply_sort()

        display = list(self.candidates)
        # Filter by starred
        if self._show_starred_only:
            display = [c for c in display if c.starred]
        # Filter by score threshold
        if self._score_threshold > 0:
            display = [c for c in display if c.total_score >= self._score_threshold]

        cols = GALLERY_COLUMNS
        for i, c in enumerate(display):
            card = self._gallery_cards.get(id(c)) or self._make_card(c)
            if card is None:
                continue
            try:
                real_idx = self.candidates.index(c)
            except ValueError:
                continue
            card.idx = real_idx
            card.set_selected(real_idx == self.selected_idx)
            card.refresh_star()
            # Apply multi-select state
            card.set_multi_selected(id(c) in self._multi_selected)
            card.setParent(self.gallery_container)
            self.gallery_layout.addWidget(card, i // cols, i % cols)

        # Update heatmap
        self.heatmap.set_data(self.candidates, self.video_info.get("duration", 0.0))
        self.heatmap.set_selected(self.selected_idx)

        # Update multi-select bar visibility
        self._update_multi_select_bar()

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

    def _on_preset_changed(self, _text: str) -> None:
        if 0 <= self.selected_idx < len(self.candidates):
            self._select(self.selected_idx)

    # ════════════════════════════════════════════════════════════════════
    # SELECTION
    # ════════════════════════════════════════════════════════════════════
    def _select(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.candidates):
            return
        prev = self.selected_idx
        self.selected_idx = idx
        c = self.candidates[idx]

        # Lazy-load the frame if it was released
        frame = c.ensure_frame()
        if frame is None:
            self.statusBar().showMessage("Could not load frame.", 3000)
            return

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        preset = PRESETS.get(self.combo_preset.currentText())
        if preset:
            pil = fit_crop_pil(pil, preset)
        data = pil.tobytes("raw", "RGB")
        qim = QImage(data, pil.width, pil.height, 3 * pil.width, QImage.Format.Format_RGB888)
        qim._np_buf = data
        self.preview.set_pixmap(QPixmap.fromImage(qim), c)
        self.empty_overlay.set_mode("hidden")

        self.histogram.set_data(frame)
        self.breakdown.set_scores(c.breakdown)
        self._refresh_info_cand(c)

        # Update heatmap selection
        self.heatmap.set_selected(idx)

        if prev != idx:
            if 0 <= prev < len(self.candidates):
                prev_card = self._gallery_cards.get(id(self.candidates[prev]))
                if prev_card is not None:
                    prev_card.set_selected(False)
            cur_card = self._gallery_cards.get(id(c))
            if cur_card is not None:
                cur_card.set_selected(True)

    def _toggle_star(self, idx: int) -> None:
        if 0 <= idx < len(self.candidates):
            self.candidates[idx].starred = not self.candidates[idx].starred
            card = self._gallery_cards.get(id(self.candidates[idx]))
            if card is not None:
                card.refresh_star()
            if self._show_starred_only and not self.candidates[idx].starred:
                self._refresh_gallery()
            self._save_starred_state()

    def _star_current(self) -> None:
        if 0 <= self.selected_idx < len(self.candidates):
            self._toggle_star(self.selected_idx)

    def _nav(self, d: int) -> None:
        if not self.candidates:
            return
        self._select((self.selected_idx + d) % len(self.candidates))

    def _auto_select_best(self) -> None:
        """Select the highest-scoring candidate."""
        if not self.candidates:
            return
        # Temporarily switch sort to Score
        self.combo_sort.blockSignals(True)
        self.combo_sort.setCurrentText("Score")
        self.combo_sort.blockSignals(False)
        self._apply_sort()
        self._gallery_cards.clear()
        self._refresh_gallery()
        self._select(0)
        self.statusBar().showMessage("Auto-selected best candidate.", 3000)

    def _seek_time(self, ts: float) -> None:
        if not self.video_path:
            return
        cap = cv2.VideoCapture(self.video_path)
        try:
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ret, frame = cap.read()
        finally:
            cap.release()
        if not ret or frame is None:
            self.statusBar().showMessage(f"Could not read frame at {format_time(ts)}", 3000)
            return
        w = self._all_profiles.get(self.combo_algo.currentText(),
                                    ALGORITHM_PROFILES["General (Balanced)"])
        face_score, faces = score_faces(frame)
        small, gray = downscale_for_scoring(frame, 720)
        scores = {n: s(small, gray) for n, s in SCORERS.items()}
        scores["faces"] = face_score
        total = sum(scores.get(k, 0.0) * w.get(k, 0.0) for k in w)
        cand = Candidate(frame_bgr=frame, timestamp=float(ts),
                         total_score=total, breakdown=scores, faces=faces,
                         video_path=self.video_path)
        self.candidates.insert(0, cand)
        self._refresh_gallery()
        self._select(0)
        self.statusBar().showMessage(f"Added manual frame @ {format_time(ts)}", 3000)

    # ════════════════════════════════════════════════════════════════════
    # RE-ANALYZE NEIGHBORHOOD
    # ════════════════════════════════════════════════════════════════════
    def _reanalyze_idx(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.candidates):
            return
        cand = self.candidates[idx]
        center = cand.timestamp
        radius = REANALYZE_RADIUS_SEC
        n = REANALYZE_SAMPLES
        times = list(np.linspace(max(0, center - radius), center + radius, n))
        self.statusBar().showMessage(
            f"Re-analyzing ±{radius}s around {format_time(center)}…", 4000
        )
        self._start_analysis(append=True, sample_times=times)

    def _reanalyze_current(self) -> None:
        if 0 <= self.selected_idx < len(self.candidates):
            self._reanalyze_idx(self.selected_idx)

    # ════════════════════════════════════════════════════════════════════
    # COMPARE TAB
    # ════════════════════════════════════════════════════════════════════
    def _clear_compare_tab(self) -> None:
        while self.compare_lay.count():
            item = self.compare_lay.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.deleteLater()

    def _refresh_compare_tab(self) -> None:
        self._clear_compare_tab()
        if not self.candidates:
            self.compare_placeholder.show()
            return
        self.compare_placeholder.hide()

        top3 = self.candidates[:3]
        for rank, c in enumerate(top3, start=1):
            col = QFrame()
            col.setObjectName("Card")
            col_lay = QVBoxLayout(col)
            col_lay.setContentsMargins(8, 8, 8, 8)
            col_lay.setSpacing(6)

            pm = THUMBS.compare(id(c), c.ensure_frame())
            lbl = QLabel()
            lbl.setPixmap(pm)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setMinimumHeight(180)
            col_lay.addWidget(lbl)

            rank_lbl = QLabel(f"#{rank}")
            rank_lbl.setStyleSheet(f"color:{C_LAVENDER}; font-weight:bold; font-size:13px;")
            rank_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col_lay.addWidget(rank_lbl)

            info = (
                f"Score: {c.total_score:.2f}   Time: {format_time(c.timestamp)}\n"
                f"Faces: {len(c.faces)}   Sharp: {c.breakdown.get('sharpness', 0):.2f}   "
                f"Contrast: {c.breakdown.get('contrast', 0):.2f}"
            )
            info_lbl = QLabel(info)
            info_lbl.setStyleSheet(
                f"color:{C_SUBTEXT}; font-size:10px; "
                "font-family:'JetBrains Mono','Consolas',monospace;"
            )
            info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_lbl.setWordWrap(True)
            col_lay.addWidget(info_lbl)

            btn = QPushButton("Save")
            btn.clicked.connect(lambda _, cc=c: self._save_image(cc))
            col_lay.addWidget(btn)

            self.compare_lay.addWidget(col, stretch=1)

    # ════════════════════════════════════════════════════════════════════
    # INFO TAB
    # ════════════════════════════════════════════════════════════════════
    def _refresh_info_video(self, info: Dict) -> None:
        if not info:
            return
        path = info.get("path", "")
        self._info_file.setText(Path(path).name if path else "—")
        self._info_duration.setText(format_duration(info.get("duration", 0)))
        w = info.get("width"); h = info.get("height")
        self._info_resolution.setText(f"{w}×{h}" if w and h else "—")
        fps = info.get("fps")
        self._info_fps.setText(f"{fps:.2f}" if fps else "—")
        tf = info.get("total_frames")
        self._info_total_frames.setText(str(tf) if tf else "—")

    def _refresh_info_cand(self, cand: Optional[Candidate]) -> None:
        if cand is None:
            for k in ("rank", "timestamp", "score", "faces", "sharpness",
                      "contrast", "brightness", "composition"):
                getattr(self, f"_info_{k}").setText("—")
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

    # ════════════════════════════════════════════════════════════════════
    # ALGORITHM / WEIGHTS
    # ════════════════════════════════════════════════════════════════════
    def _get_active_weights(self) -> Dict[str, float]:
        return self._all_profiles.get(
            self.combo_algo.currentText(), ALGORITHM_PROFILES["General (Balanced)"]
        )

    def _change_algo(self, name: str) -> None:
        if not self.candidates:
            return
        w = self._all_profiles.get(name, ALGORITHM_PROFILES["General (Balanced)"])
        for c in self.candidates:
            c.total_score = sum(c.breakdown.get(k, 0.0) * w.get(k, 0.0) for k in w)
        self._apply_sort()
        self._gallery_cards.clear()
        self._refresh_gallery()
        self._refresh_compare_tab()
        if 0 <= self.selected_idx < len(self.candidates):
            self._select(self.selected_idx)
        self.statusBar().showMessage(f"Re-sorted using {name}", 3000)

    def _edit_weights(self) -> None:
        name = self.combo_algo.currentText()
        weights = self._all_profiles.get(name, {})
        dlg = WeightsEditorDialog(self, name, weights, list(self._all_profiles.keys()))
        if dlg.exec() == WeightsEditorDialog.DialogCode.Accepted:
            new_name = dlg.get_profile_name()
            new_weights = dlg.get_weights()
            self._all_profiles[new_name] = new_weights
            # If it's a new/changed custom profile, persist it
            if new_name not in ALGORITHM_PROFILES:
                SETTINGS.save_custom_profile(new_name, new_weights)
            # Update combo
            self.combo_algo.blockSignals(True)
            if self.combo_algo.findText(new_name) < 0:
                self.combo_algo.addItem(new_name)
            self.combo_algo.setCurrentText(new_name)
            self.combo_algo.blockSignals(False)
            self._change_algo(new_name)
            self.statusBar().showMessage(f"Saved profile '{new_name}'", 3000)

    # ════════════════════════════════════════════════════════════════════
    # CONTACT SHEET EXPORT
    # ════════════════════════════════════════════════════════════════════
    def _export_contact_sheet(self) -> None:
        if not self.candidates:
            QMessageBox.information(self, "No candidates", "Run analysis first.")
            return
        video_name = Path(self.video_path).stem if self.video_path else ""
        dlg = ContactSheetDialog(self, self.candidates, video_name)
        dlg.exec()

    # ════════════════════════════════════════════════════════════════════
    # SAVE
    # ════════════════════════════════════════════════════════════════════
    def _save(self) -> None:
        if self.selected_idx < 0 or self.selected_idx >= len(self.candidates):
            return
        self._save_image(self.candidates[self.selected_idx])

    def _format_filename(self, cand: Candidate, rank: int) -> str:
        """Render the filename template for a candidate."""
        video_name = Path(self.video_path).stem if self.video_path else "video"
        preset_name = self.combo_preset.currentText()
        try:
            return self._filename_template.format(
                video=video_name,
                timestamp=format_time(cand.timestamp).replace(":", "-"),
                ts_seconds=f"{cand.timestamp:.3f}",
                score=f"{cand.total_score:.3f}",
                rank=rank,
                preset=preset_name,
            )
        except (KeyError, ValueError) as e:
            logger.warning(f"Bad filename template: {e}")
            return f"thumb_{format_time(cand.timestamp).replace(':', '-')}.jpg"

    def _batch_save(self) -> None:
        starred = [c for c in self.candidates if c.starred]
        if not starred:
            QMessageBox.information(self, "Info", "No starred images to save.")
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Select Save Folder", SETTINGS.last_dir
        )
        if not folder:
            return
        SETTINGS.last_dir = folder
        for i, c in enumerate(starred, start=1):
            fname = self._format_filename(c, i)
            self._save_image(c, path=os.path.join(folder, fname))
        self.statusBar().showMessage(f"Saved {len(starred)} images to {folder}", 5000)

    def _save_image(self, cand: Candidate, path: Optional[str] = None) -> None:
        frame = cand.ensure_frame()
        if frame is None:
            QMessageBox.critical(self, "Save failed", "Could not load the frame from disk.")
            return
        pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        preset = PRESETS.get(self.combo_preset.currentText())
        if preset:
            pil = fit_crop_pil(pil, preset)

        if not path:
            rank = self.selected_idx + 1 if self.candidates and cand in self.candidates else 1
            default_name = self._format_filename(cand, rank)
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Thumbnail", default_name, "JPEG (*.jpg);;PNG (*.png)"
            )
        if not path:
            return
        try:
            fmt = "PNG" if path.lower().endswith(".png") else "JPEG"
            kwargs = {"quality": 95} if fmt == "JPEG" else {"optimize": True}
            pil.save(path, fmt, **kwargs)
            self.statusBar().showMessage(f"Saved to {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    # ════════════════════════════════════════════════════════════════════
    # TOGGLES & HELP
    # ════════════════════════════════════════════════════════════════════
    def _toggle_grid(self, state: bool) -> None:
        self.preview.set_overlays(grid=state)

    def _toggle_faces(self, state: bool) -> None:
        self.preview.set_overlays(faces=state)

    def _show_shortcuts(self) -> None:
        ShortcutHelpDialog(self).exec()

    def _show_about(self) -> None:
        AboutDialog(self).exec()

    # ════════════════════════════════════════════════════════════════════
    # PREFERENCES
    # ════════════════════════════════════════════════════════════════════
    def _show_preferences(self) -> None:
        dlg = PreferencesDialog(
            self,
            theme=self._theme,
            card_size=self._card_size,
            filename_template=self._filename_template,
            auto_free_memory=self._auto_free_memory,
        )
        dlg.set_callbacks(
            on_theme_change=self._apply_theme_from_pref,
            on_card_size_change=self._apply_card_size_from_pref,
            on_template_change=self._apply_template_from_pref,
            on_auto_free_change=self._apply_auto_free_from_pref,
        )
        if dlg.exec() == PreferencesDialog.DialogCode.Accepted:
            self._theme = dlg.theme
            self._card_size = dlg.card_size
            self._filename_template = dlg.filename_template
            self._auto_free_memory = dlg.auto_free_memory
            self._apply_theme()
            self.combo_card_size.blockSignals(True)
            self.combo_card_size.setCurrentText(self._card_size)
            self.combo_card_size.blockSignals(False)
            self._gallery_cards.clear()
            self._refresh_gallery()

    def _apply_theme_from_pref(self, theme: str) -> None:
        self._theme = theme
        self._apply_theme()

    def _apply_card_size_from_pref(self, size: str) -> None:
        self._card_size = size
        self.combo_card_size.blockSignals(True)
        self.combo_card_size.setCurrentText(size)
        self.combo_card_size.blockSignals(False)
        self._gallery_cards.clear()
        self._refresh_gallery()

    def _apply_template_from_pref(self, template: str) -> None:
        self._filename_template = template

    def _apply_auto_free_from_pref(self, value: bool) -> None:
        self._auto_free_memory = value

    # ════════════════════════════════════════════════════════════════════
    # MULTI-SELECT
    # ════════════════════════════════════════════════════════════════════
    def _on_multi_select_toggled(self, idx: int, _ctrl: bool) -> None:
        if idx < 0 or idx >= len(self.candidates):
            return
        cand = self.candidates[idx]
        if id(cand) in self._multi_selected:
            self._multi_selected.discard(id(cand))
        else:
            self._multi_selected.add(id(cand))
        # Update the card's visual state
        card = self._gallery_cards.get(id(cand))
        if card is not None:
            card.set_multi_selected(id(cand) in self._multi_selected)
        self._update_multi_select_bar()

    def _update_multi_select_bar(self) -> None:
        count = len(self._multi_selected)
        self.ms_count_lbl.setText(f"{count} selected")
        self.multi_select_bar.setVisible(count > 0)

    def _multi_apply(self, action: str) -> None:
        """Apply star/unstar to all multi-selected candidates."""
        for cand in self.candidates:
            if id(cand) in self._multi_selected:
                if action == "star":
                    cand.starred = True
                elif action == "unstar":
                    cand.starred = False
                card = self._gallery_cards.get(id(cand))
                if card is not None:
                    card.refresh_star()
        self._save_starred_state()
        self.statusBar().showMessage(
            f"{'Starred' if action == 'star' else 'Unstarred'} {len(self._multi_selected)} candidates.",
            3000
        )

    def _clear_multi_select(self) -> None:
        self._multi_selected.clear()
        for card in self._gallery_cards.values():
            card.set_multi_selected(False)
        self._update_multi_select_bar()

    # ════════════════════════════════════════════════════════════════════
    # SAVE / LOAD CANDIDATE LIST (JSON)
    # ════════════════════════════════════════════════════════════════════
    def _save_candidate_list(self) -> None:
        if not self.candidates:
            QMessageBox.information(self, "No candidates", "Run analysis first.")
            return
        default_name = (
            Path(self.video_path).stem if self.video_path else "candidates"
        ) + ".vtp.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Candidate List", default_name, "VTP JSON (*.json)"
        )
        if not path:
            return
        try:
            save_candidates_to_json(path, self.candidates, self.video_path or "", self.video_info)
            self.statusBar().showMessage(f"Saved {len(self.candidates)} candidates to {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def _load_candidate_list(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Candidate List", SETTINGS.last_dir,
            "VTP JSON (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            cands, video_path, video_info = load_candidates_from_json(path)
        except Exception as e:
            QMessageBox.critical(self, "Load failed", str(e))
            return

        # If the video path is set and exists, open it; otherwise prompt
        if video_path and Path(video_path).exists():
            self._open_file_path(video_path)
        else:
            QMessageBox.warning(
                self, "Video not found",
                f"The original video could not be found:\n{video_path}\n\n"
                "Candidates loaded but frames cannot be displayed until you "
                "open the matching video file."
            )

        self.candidates = cands
        self.video_info = video_info
        self._gallery_cards.clear()
        THUMBS.invalidate()
        self._refresh_gallery()
        self._refresh_compare_tab()
        self._refresh_info_video(video_info)
        if cands:
            self._select(0)
        self.statusBar().showMessage(
            f"Loaded {len(cands)} candidates from {path}", 4000
        )

    # ════════════════════════════════════════════════════════════════════
    # SHUTDOWN
    # ════════════════════════════════════════════════════════════════════
    def closeEvent(self, e) -> None:  # type: ignore[override]
        self._save_settings()
        self._save_starred_state()
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait(2000)
        super().closeEvent(e)
