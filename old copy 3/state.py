"""Persistent application state: settings, recent files, custom profiles, project sidecars.

All state that should survive an app restart lives here:
  * Window geometry / splitter sizes (via QSettings)
  * Last-used analysis settings (algorithm, preset, samples, etc.)
  * Recently opened files
  * User-defined custom algorithm profiles
  * Per-video starred-state sidecar (.vtp.json next to the video)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import QSettings

logger = logging.getLogger("thumbnail_picker")

RECENT_FILES_MAX = 10
SIDECAR_SUFFIX = ".vtp.json"
SIDECAR_VERSION = 1


class AppSettings:
    """Thin wrapper around QSettings for persistent app configuration."""

    def __init__(self) -> None:
        self._s = QSettings("ThumbnailPicker", "Video Thumbnail Picker")

    # ── Window state ──────────────────────────────────────────────────
    def save_window_state(self, window) -> None:
        self._s.setValue("ui/windowGeometry", window.saveGeometry())
        # Splitter sizes stored as a list of ints
        splitter = getattr(window, "_splitter", None)
        if splitter is not None:
            self._s.setValue("ui/splitterSizes", splitter.sizes())

    def restore_window_state(self, window) -> None:
        geo = self._s.value("ui/windowGeometry")
        if geo is not None:
            window.restoreGeometry(geo)
        # Splitter sizes are applied after UI is built (caller does this)

    def splitter_sizes(self) -> List[int]:
        raw = self._s.value("ui/splitterSizes")
        if raw is None:
            return []
        if isinstance(raw, (list, tuple)):
            return [int(x) for x in raw]
        return []

    # ── Analysis settings ─────────────────────────────────────────────
    def save_analysis_settings(self, *, algo: str, preset: str, samples: int,
                               cands: int, scene: bool, sort: str,
                               threshold: float) -> None:
        self._s.setValue("analysis/algo", algo)
        self._s.setValue("analysis/preset", preset)
        self._s.setValue("analysis/samples", int(samples))
        self._s.setValue("analysis/cands", int(cands))
        self._s.setValue("analysis/scene", bool(scene))
        self._s.setValue("analysis/sort", sort)
        self._s.setValue("analysis/threshold", float(threshold))

    def restore_analysis_settings(self) -> Dict[str, Any]:
        return {
            "algo":      self._s.value("analysis/algo", "General (Balanced)", type=str),
            "preset":    self._s.value("analysis/preset", "Original", type=str),
            "samples":   self._s.value("analysis/samples", 80, type=int),
            "cands":     self._s.value("analysis/cands", 15, type=int),
            "scene":     self._s.value("analysis/scene", False, type=bool),
            "sort":      self._s.value("analysis/sort", "Score", type=str),
            "threshold": self._s.value("analysis/threshold", 0.0, type=float),
        }

    # ── UI preferences ────────────────────────────────────────────────
    @property
    def card_size(self) -> str:
        return self._s.value("ui/cardSize", "Medium", type=str)

    @card_size.setter
    def card_size(self, value: str) -> None:
        self._s.setValue("ui/cardSize", str(value))

    @property
    def theme(self) -> str:
        return self._s.value("ui/theme", "dark", type=str)

    @theme.setter
    def theme(self, value: str) -> None:
        self._s.setValue("ui/theme", str(value))

    @property
    def filename_template(self) -> str:
        return self._s.value("ui/filenameTemplate", "thumb_{timestamp}.jpg", type=str)

    @filename_template.setter
    def filename_template(self, value: str) -> None:
        self._s.setValue("ui/filenameTemplate", str(value))

    @property
    def auto_free_memory(self) -> bool:
        """If True, release full-res frames after analysis to save RAM."""
        return self._s.value("ui/autoFreeMemory", False, type=bool)

    @auto_free_memory.setter
    def auto_free_memory(self, value: bool) -> None:
        self._s.setValue("ui/autoFreeMemory", bool(value))

    # ── Recent files ──────────────────────────────────────────────────
    @property
    def recent_files(self) -> List[str]:
        raw = self._s.value("recent/files", [])
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, (list, tuple)):
            return []
        # Filter out files that no longer exist
        return [str(f) for f in raw if Path(f).exists()]

    def add_recent_file(self, path: str) -> None:
        files = self.recent_files
        norm = str(Path(path).resolve())
        files = [f for f in files if Path(f).resolve() != Path(norm)]
        files.insert(0, norm)
        files = files[:RECENT_FILES_MAX]
        self._s.setValue("recent/files", files)

    def clear_recent_files(self) -> None:
        self._s.setValue("recent/files", [])

    # ── Custom algorithm profiles ─────────────────────────────────────
    @property
    def custom_profiles(self) -> Dict[str, Dict[str, float]]:
        raw = self._s.value("profiles/custom", {})
        if not isinstance(raw, dict):
            return {}
        # Sanitise: ensure values are floats
        out: Dict[str, Dict[str, float]] = {}
        for name, weights in raw.items():
            if isinstance(weights, dict):
                out[name] = {k: float(v) for k, v in weights.items()}
        return out

    def save_custom_profile(self, name: str, weights: Dict[str, float]) -> None:
        profiles = self.custom_profiles
        profiles[name] = {k: float(v) for k, v in weights.items()}
        self._s.setValue("profiles/custom", profiles)

    def remove_custom_profile(self, name: str) -> None:
        profiles = self.custom_profiles
        profiles.pop(name, None)
        self._s.setValue("profiles/custom", profiles)

    # ── I/O defaults ──────────────────────────────────────────────────
    @property
    def last_dir(self) -> str:
        return self._s.value("io/lastDir", "", type=str)

    @last_dir.setter
    def last_dir(self, value: str) -> None:
        self._s.setValue("io/lastDir", str(value))

    # ── Flush ─────────────────────────────────────────────────────────
    def sync(self) -> None:
        self._s.sync()


class ProjectState:
    """Per-video sidecar file for starred candidates.

    Saves a small JSON file next to the video (``<video>.vtp.json``) so
    starred frames survive across sessions.
    """

    @staticmethod
    def sidecar_path(video_path: str) -> Path:
        return Path(video_path).with_suffix(SIDECAR_SUFFIX)

    @staticmethod
    def save(video_path: str, candidates: List) -> None:
        """Persist starred-candidate timestamps to a sidecar JSON file."""
        sidecar = ProjectState.sidecar_path(video_path)
        data = {
            "version": SIDECAR_VERSION,
            "video": str(video_path),
            "starred_timestamps": [
                round(c.timestamp, 3) for c in candidates if c.starred
            ],
        }
        try:
            sidecar.write_text(json.dumps(data, indent=2))
            logger.info(f"Saved project state to {sidecar.name}")
        except Exception as e:
            logger.warning(f"Could not save project state: {e}")

    @staticmethod
    def load(video_path: str) -> Dict[str, Any]:
        """Load sidecar state. Returns an empty dict if not found / invalid."""
        sidecar = ProjectState.sidecar_path(video_path)
        if not sidecar.exists():
            return {}
        try:
            data = json.loads(sidecar.read_text())
            if not isinstance(data, dict):
                return {}
            logger.info(f"Loaded project state from {sidecar.name}")
            return data
        except Exception as e:
            logger.warning(f"Could not load project state: {e}")
            return {}

    @staticmethod
    def delete(video_path: str) -> None:
        sidecar = ProjectState.sidecar_path(video_path)
        try:
            if sidecar.exists():
                sidecar.unlink()
        except Exception:
            pass


# Module-level singleton
SETTINGS = AppSettings()
