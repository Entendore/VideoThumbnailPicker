"""Modal dialogs: weights editor, shortcut help, contact sheet export, about.

All secondary UI that doesn't belong in the main window lives here.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QSpinBox,
    QScrollArea, QWidget, QGridLayout, QDialogButtonBox, QFileDialog,
    QMessageBox, QGroupBox, QCheckBox, QComboBox, QLineEdit,
)

from config import (
    CRIT_LABELS, ALGORITHM_PROFILES,
    C_TEXT, C_SUBTEXT, C_CARD, C_OVERLAY, C_SURFACE, C_GREEN, C_BLUE,
    C_LAVENDER, C_BG, C_YELLOW, C_PEACH,
)
from analysis import Candidate
from utils import format_time


# ────────────────────────────────────────────────────────────────────────────
# Algorithm weights editor
# ────────────────────────────────────────────────────────────────────────────
class WeightsEditorDialog(QDialog):
    """Edit algorithm weights with live normalization preview.

    Sliders are 0–100 (display); actual weights are normalised to sum to 1.0.
    The user can save the result as a new (or overwrite an existing) custom
    profile.
    """

    def __init__(self, parent, profile_name: str, weights: Dict[str, float],
                 existing_profiles: List[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Algorithm Profile")
        self.setMinimumWidth(520)
        self._initial_weights = dict(weights)

        v = QVBoxLayout(self)
        v.setSpacing(10)

        # ── Profile name row ──
        row = QHBoxLayout()
        row.addWidget(QLabel("Profile name:"))
        self.name_edit = QLineEdit(profile_name)
        self.name_edit.setStyleSheet("padding: 4px 6px;")
        row.addWidget(self.name_edit, stretch=1)
        v.addLayout(row)

        # ── Hint ──
        hint = QLabel(
            "Drag the sliders to adjust each criterion's weight. "
            "Weights are normalised to sum to 1.0. A zero-weight criterion "
            "is excluded entirely."
        )
        hint.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
        hint.setWordWrap(True)
        v.addWidget(hint)

        # ── Sliders ──
        sliders_box = QGroupBox("Criteria Weights")
        sgrid = QGridLayout(sliders_box)
        sgrid.setContentsMargins(12, 16, 12, 12)
        sgrid.setHorizontalSpacing(10)
        sgrid.setVerticalSpacing(6)
        self._sliders: Dict[str, QSlider] = {}
        self._value_labels: Dict[str, QLabel] = {}

        for i, key in enumerate(sorted(CRIT_LABELS.keys())):
            label = QLabel(CRIT_LABELS[key])
            label.setMinimumWidth(70)
            sgrid.addWidget(label, i, 0)

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(int(round(weights.get(key, 0.0) * 100)))
            slider.valueChanged.connect(self._on_changed)
            sgrid.addWidget(slider, i, 1)
            self._sliders[key] = slider

            val_lbl = QLabel(f"{weights.get(key, 0.0):.2f}")
            val_lbl.setMinimumWidth(40)
            val_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono','Consolas',monospace; color:{C_GREEN};"
            )
            sgrid.addWidget(val_lbl, i, 2)
            self._value_labels[key] = val_lbl

        v.addWidget(sliders_box)

        # ── Summary ──
        self.summary_lbl = QLabel()
        self.summary_lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
        v.addWidget(self.summary_lbl)

        # ── Buttons ──
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        reset_btn = QPushButton("Reset to Original")
        reset_btn.clicked.connect(self._reset)
        btns.addButton(reset_btn, QDialogButtonBox.ButtonRole.ResetRole)

        v.addWidget(btns)
        self._on_changed()

    def _on_changed(self, *_) -> None:
        weights = self.get_weights()
        for key, slider in self._sliders.items():
            w = weights.get(key, 0.0)
            self._value_labels[key].setText(f"{w:.2f}")
        total = sum(weights.values())
        active = sum(1 for val in weights.values() if val > 0)
        self.summary_lbl.setText(
            f"Normalised sum: {total:.3f}  |  Active criteria: {active}/{len(self._sliders)}"
        )

    def _reset(self) -> None:
        for key, slider in self._sliders.items():
            slider.setValue(int(round(self._initial_weights.get(key, 0.0) * 100)))

    def get_weights(self) -> Dict[str, float]:
        """Return normalised weights (sum to 1.0)."""
        raw = {k: s.value() / 100.0 for k, s in self._sliders.items() if s.value() > 0}
        total = sum(raw.values())
        if total == 0:
            # All zero — fall back to uniform
            return {k: 1.0 / len(self._sliders) for k in self._sliders}
        return {k: v / total for k, v in raw.items()}

    def get_profile_name(self) -> str:
        return self.name_edit.text().strip() or "Custom Profile"


# ────────────────────────────────────────────────────────────────────────────
# Keyboard shortcut help
# ────────────────────────────────────────────────────────────────────────────
class ShortcutHelpDialog(QDialog):
    """Show keyboard shortcuts grouped by category."""

    SHORTCUTS: List[tuple] = [
        ("File", [
            ("Ctrl+O",          "Open video file"),
            ("Ctrl+S",          "Save selected frame"),
            ("Ctrl+Shift+S",    "Save all starred frames"),
            ("Ctrl+E",          "Export contact sheet"),
            ("Ctrl+Q",          "Quit"),
        ]),
        ("Navigation", [
            ("← / →",           "Previous / next candidate"),
            ("F2",              "Fit image to view"),
            ("Ctrl+= / Ctrl+-", "Zoom in / out"),
            ("Ctrl+0",          "Reset zoom to 100%"),
        ]),
        ("Overlays", [
            ("G",               "Toggle rule-of-thirds grid"),
            ("F",               "Toggle face-detection overlay"),
        ]),
        ("Analysis", [
            ("Space",           "Run / stop analysis"),
            ("Esc",             "Stop analysis"),
            ("F1",              "Show this help"),
        ]),
        ("Gallery", [
            ("S",               "Star / unstar current candidate"),
            ("R",               "Re-analyze around current frame"),
        ]),
    ]

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumWidth(460)

        v = QVBoxLayout(self)
        v.setSpacing(10)

        title = QLabel("Keyboard Shortcuts")
        title.setStyleSheet(f"font-size:15px; font-weight:bold; color:{C_LAVENDER};")
        v.addWidget(title)

        for section_name, items in self.SHORTCUTS:
            group = QGroupBox(section_name)
            gl = QGridLayout(group)
            gl.setContentsMargins(12, 14, 12, 12)
            gl.setHorizontalSpacing(16)
            gl.setVerticalSpacing(4)
            for i, (key, desc) in enumerate(items):
                k_lbl = QLabel(key)
                k_lbl.setStyleSheet(
                    f"color:{C_LAVENDER}; font-family:'JetBrains Mono','Consolas',monospace; "
                    f"font-weight:bold; font-size:11px;"
                )
                gl.addWidget(k_lbl, i, 0)
                d_lbl = QLabel(desc)
                d_lbl.setStyleSheet(f"color:{C_TEXT};")
                gl.addWidget(d_lbl, i, 1)
            v.addWidget(group)

        btn = QPushButton("Close")
        btn.setObjectName("btnPrimary")
        btn.clicked.connect(self.accept)
        v.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)


# ────────────────────────────────────────────────────────────────────────────
# About dialog
# ────────────────────────────────────────────────────────────────────────────
class AboutDialog(QDialog):
    """Simple about / credits dialog."""

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setMinimumWidth(380)

        v = QVBoxLayout(self)
        v.setSpacing(10)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Video Thumbnail Picker")
        title.setStyleSheet(f"font-size:18px; font-weight:bold; color:{C_LAVENDER};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title)

        ver = QLabel("Version 2.1")
        ver.setStyleSheet(f"color:{C_SUBTEXT}; font-size:12px;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(ver)

        desc = QLabel(
            "Automatically finds the best frames in a video using a\n"
            "weighted set of image-quality metrics (sharpness, contrast,\n"
            "faces, composition, colour, dynamic range and more).\n\n"
            "Built with PySide6, OpenCV and Pillow."
        )
        desc.setStyleSheet(f"color:{C_TEXT}; font-size:11px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(desc)

        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        v.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)


# ────────────────────────────────────────────────────────────────────────────
# Contact sheet export
# ────────────────────────────────────────────────────────────────────────────
class ContactSheetDialog(QDialog):
    """Configure and export a contact-sheet PNG of candidates."""

    def __init__(self, parent, candidates: List[Candidate], video_name: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Contact Sheet")
        self.setMinimumWidth(380)
        self._candidates = candidates
        self._video_name = video_name

        v = QVBoxLayout(self)
        v.setSpacing(10)

        # ── Layout settings ──
        box = QGroupBox("Layout")
        gl = QGridLayout(box)
        gl.setContentsMargins(12, 14, 12, 12)
        gl.setHorizontalSpacing(10)
        gl.setVerticalSpacing(6)

        gl.addWidget(QLabel("Columns:"), 0, 0)
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 10)
        self.cols_spin.setValue(4)
        gl.addWidget(self.cols_spin, 0, 1)

        gl.addWidget(QLabel("Thumb width (px):"), 1, 0)
        self.thumb_w_spin = QSpinBox()
        self.thumb_w_spin.setRange(80, 480)
        self.thumb_w_spin.setValue(240)
        self.thumb_w_spin.setSingleStep(20)
        gl.addWidget(self.thumb_w_spin, 1, 1)

        gl.addWidget(QLabel("Thumb height (px):"), 2, 0)
        self.thumb_h_spin = QSpinBox()
        self.thumb_h_spin.setRange(60, 360)
        self.thumb_h_spin.setValue(135)
        self.thumb_h_spin.setSingleStep(15)
        gl.addWidget(self.thumb_h_spin, 2, 1)

        self.chk_labels = QCheckBox("Show labels (rank, time, score)")
        self.chk_labels.setChecked(True)
        gl.addWidget(self.chk_labels, 3, 0, 1, 2)

        self.chk_starred_only = QCheckBox("Starred only")
        gl.addWidget(self.chk_starred_only, 4, 0, 1, 2)

        v.addWidget(box)

        # ── Preview count ──
        self.count_lbl = QLabel()
        self.count_lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
        v.addWidget(self.count_lbl)
        self._update_count()

        for sp in (self.cols_spin, self.thumb_w_spin, self.thumb_h_spin):
            sp.valueChanged.connect(self._update_count)
        self.chk_starred_only.stateChanged.connect(self._update_count)

        # ── Buttons ──
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._export)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def _update_count(self) -> None:
        cands = self._get_selected()
        cols = self.cols_spin.value()
        rows = (len(cands) + cols - 1) // cols if cols else 0
        self.count_lbl.setText(
            f"{len(cands)} frames → {rows} rows × {cols} cols"
        )

    def _get_selected(self) -> List[Candidate]:
        if self.chk_starred_only.isChecked():
            return [c for c in self._candidates if c.starred]
        return list(self._candidates)

    def _export(self) -> None:
        cands = self._get_selected()
        if not cands:
            QMessageBox.information(self, "No frames", "No frames to export.")
            return

        default_name = f"contact_sheet_{self._video_name or 'thumbnails'}.png"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Contact Sheet", default_name, "PNG (*.png)"
        )
        if not path:
            return

        try:
            self._generate(path, cands)
            QMessageBox.information(self, "Exported", f"Saved contact sheet to:\n{path}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

    def _generate(self, path: str, cands: List[Candidate]) -> None:
        cols = self.cols_spin.value()
        thumb_w = self.thumb_w_spin.value()
        thumb_h = self.thumb_h_spin.value()
        show_labels = self.chk_labels.isChecked()

        label_h = 22 if show_labels else 0
        cell_w = thumb_w
        cell_h = thumb_h + label_h
        padding = 10
        title_h = 36

        rows = (len(cands) + cols - 1) // cols
        sheet_w = cols * cell_w + (cols + 1) * padding
        sheet_h = rows * cell_h + (rows + 1) * padding + title_h

        # Background = C_BG (#1e1e2e → (30, 30, 46))
        sheet = Image.new("RGB", (sheet_w, sheet_h), (30, 30, 46))
        draw = ImageDraw.Draw(sheet)

        try:
            font_title = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16
            )
            font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11
            )
        except Exception:
            font_title = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Title bar
        title_text = f"Contact Sheet — {self._video_name} ({len(cands)} frames)"
        draw.text((padding, 8), title_text, fill=(205, 214, 244), font=font_title)

        for i, c in enumerate(cands):
            row = i // cols
            col = i % cols
            x = padding + col * (cell_w + padding)
            y = title_h + padding + row * (cell_h + padding)

            # Thumbnail
            rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
            pil_thumb = Image.fromarray(rgb).resize(
                (thumb_w, thumb_h), Image.Resampling.LANCZOS
            )
            sheet.paste(pil_thumb, (x, y))

            # Border
            border_color = (249, 226, 175) if c.starred else (69, 71, 90)  # C_YELLOW / C_OVERLAY
            draw.rectangle(
                [(x, y), (x + thumb_w - 1, y + thumb_h - 1)],
                outline=border_color, width=2,
            )

            # Label
            if show_labels:
                ly = y + thumb_h + 2
                label = f"#{i + 1}  {format_time(c.timestamp)}  {c.total_score:.2f}"
                draw.text((x + 2, ly), label, fill=(166, 173, 200), font=font_small)

        sheet.save(path, "PNG")


# ────────────────────────────────────────────────────────────────────────────
# Preferences dialog
# ────────────────────────────────────────────────────────────────────────────
class PreferencesDialog(QDialog):
    """Edit user preferences: theme, gallery card size, filename template.

    Changes are applied immediately to the parent window via callbacks
    set with :meth:`set_callbacks`.
    """

    def __init__(self, parent, *, theme: str, card_size: str,
                 filename_template: str, auto_free_memory: bool) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(480)

        self._on_theme_change = None
        self._on_card_size_change = None
        self._on_template_change = None
        self._on_auto_free_change = None

        v = QVBoxLayout(self)
        v.setSpacing(12)

        # ── Appearance ──
        app_box = QGroupBox("Appearance")
        app_lay = QVBoxLayout(app_box)
        app_lay.setContentsMargins(12, 16, 12, 12)
        app_lay.setSpacing(8)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Theme:"))
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["dark", "light"])
        self.combo_theme.setCurrentText(theme)
        self.combo_theme.currentTextChanged.connect(self._on_theme_changed)
        row1.addWidget(self.combo_theme, stretch=1)
        app_lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Gallery card size:"))
        self.combo_card_size = QComboBox()
        self.combo_card_size.addItems(["Small", "Medium", "Large"])
        self.combo_card_size.setCurrentText(card_size)
        self.combo_card_size.currentTextChanged.connect(self._on_card_size_changed)
        row2.addWidget(self.combo_card_size, stretch=1)
        app_lay.addLayout(row2)
        v.addWidget(app_box)

        # ── Save ──
        save_box = QGroupBox("Save")
        save_lay = QVBoxLayout(save_box)
        save_lay.setContentsMargins(12, 16, 12, 12)
        save_lay.setSpacing(8)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Filename template:"))
        self.combo_template = QComboBox()
        self.combo_template.setEditable(True)
        self.combo_template.addItems([
            "thumb_{timestamp}.jpg",
            "{video}_{timestamp}.jpg",
            "{video}_rank{rank}_{score}.jpg",
            "{video}_{ts_seconds}s_{score}.jpg",
            "thumbnail_{rank:02d}.jpg",
        ])
        self.combo_template.setCurrentText(filename_template)
        self.combo_template.currentTextChanged.connect(self._on_template_changed)
        row3.addWidget(self.combo_template, stretch=1)
        save_lay.addLayout(row3)

        hint = QLabel(
            "Placeholders: {video} {timestamp} {ts_seconds} {score} {rank} {preset}\n"
            "Example: myvideo_00:12-345_0.87.jpg"
        )
        hint.setStyleSheet(f"color:{C_SUBTEXT}; font-size:10px;")
        save_lay.addWidget(hint)
        v.addWidget(save_box)

        # ── Memory ──
        mem_box = QGroupBox("Memory")
        mem_lay = QVBoxLayout(mem_box)
        mem_lay.setContentsMargins(12, 16, 12, 12)
        self.chk_auto_free = QCheckBox(
            "Auto-free full-res frames after analysis (re-fetches on demand)"
        )
        self.chk_auto_free.setChecked(auto_free_memory)
        self.chk_auto_free.setToolTip(
            "Releases all full-resolution frames from memory once analysis "
            "completes. Frames are re-read from the video file when needed. "
            "Saves ~30MB per 1080p candidate."
        )
        self.chk_auto_free.stateChanged.connect(self._on_auto_free_changed)
        mem_lay.addWidget(self.chk_auto_free)
        v.addWidget(mem_box)

        # ── Buttons ──
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        v.addWidget(btns)

    # -- callbacks ---------------------------------------------------------
    def set_callbacks(self, *, on_theme_change=None, on_card_size_change=None,
                      on_template_change=None, on_auto_free_change=None) -> None:
        self._on_theme_change = on_theme_change
        self._on_card_size_change = on_card_size_change
        self._on_template_change = on_template_change
        self._on_auto_free_change = on_auto_free_change

    def _on_theme_changed(self, theme: str) -> None:
        if self._on_theme_change:
            self._on_theme_change(theme)

    def _on_card_size_changed(self, size: str) -> None:
        if self._on_card_size_change:
            self._on_card_size_change(size)

    def _on_template_changed(self, template: str) -> None:
        if self._on_template_change:
            self._on_template_change(template)

    def _on_auto_free_changed(self, state: int) -> None:
        if self._on_auto_free_change:
            self._on_auto_free_change(state != 0)

    # -- getters -----------------------------------------------------------
    @property
    def theme(self) -> str: return self.combo_theme.currentText()
    @property
    def card_size(self) -> str: return self.combo_card_size.currentText()
    @property
    def filename_template(self) -> str: return self.combo_template.currentText()
    @property
    def auto_free_memory(self) -> bool: return self.chk_auto_free.isChecked()


# ────────────────────────────────────────────────────────────────────────────
# Save / Load candidate list (JSON)
# ────────────────────────────────────────────────────────────────────────────
def save_candidates_to_json(path: str, candidates: list, video_path: str,
                             video_info: dict) -> None:
    """Serialise candidate metadata (no frames) to a JSON file.

    The file can be re-loaded to skip re-analysis on a known video.
    """
    import json
    data = {
        "version": 1,
        "video_path": video_path,
        "video_info": video_info,
        "candidates": [
            {
                "timestamp": round(c.timestamp, 3),
                "total_score": round(c.total_score, 6),
                "breakdown": {k: round(float(v), 6) for k, v in c.breakdown.items()},
                "faces": [list(f) for f in c.faces],
                "starred": c.starred,
            }
            for c in candidates
        ],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_candidates_from_json(path: str):
    """Return (candidates, video_path, video_info) from a saved JSON file.

    Candidates are returned as ``Candidate`` objects with ``frame_bgr=None``
    — they will lazy-load from the video file on first access.
    """
    import json
    from analysis import Candidate
    with open(path, "r") as f:
        data = json.load(f)
    video_path = data.get("video_path", "")
    video_info = data.get("video_info", {})
    cands = []
    for d in data.get("candidates", []):
        cands.append(Candidate(
            frame_bgr=None,
            timestamp=float(d["timestamp"]),
            total_score=float(d["total_score"]),
            breakdown={k: float(v) for k, v in d.get("breakdown", {}).items()},
            faces=[tuple(f) for f in d.get("faces", [])],
            starred=bool(d.get("starred", False)),
            video_path=video_path,
        ))
    return cands, video_path, video_info
