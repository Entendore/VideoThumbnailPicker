"""Lazy frame store: LRU cache for full-res video frames.

Problem: keeping 200 full-res 4K frames in memory uses ~7.6 GB. Most of
those frames are never looked at again after scoring — only the few the
user selects for preview / save / contact-sheet need the full buffer.

Solution: ``Candidate`` keeps an optional reference to its BGR ndarray.
When memory pressure is high (or the user clicks "Free Memory"), we
``release_frame()`` on every candidate, setting ``frame_bgr = None``.
The next time the frame is needed, ``ensure_frame()`` calls into the
``FrameStore``, which re-reads it from the video file at the stored
timestamp. A small LRU cache keeps the N most-recently-fetched frames
hot so repeated accesses don't re-seek the video.
"""
from __future__ import annotations

import logging
import threading
import weakref
from collections import OrderedDict
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("thumbnail_picker")

# Default LRU size — ~50 frames at 1080p ≈ 300 MB, a reasonable hot set.
DEFAULT_LRU_SIZE: int = 50


class FrameStore:
    """Thread-safe LRU cache for video frames keyed by (path, timestamp).

    Each entry is the BGR ndarray returned by ``cv2.VideoCapture.read()``.
    Use :meth:`get` to fetch a frame; if it's already in the cache the
    cached copy is returned without re-seeking the video.
    """

    def __init__(self, max_entries: int = DEFAULT_LRU_SIZE) -> None:
        self._max = max(1, int(max_entries))
        self._cache: "OrderedDict[Tuple[str, float], np.ndarray]" = OrderedDict()
        self._lock = threading.RLock()
        # Track open VideoCapture objects per path (lazy, closed on eviction)
        self._caps: dict = {}
        self._caps_lock = threading.Lock()

    # ── public API ──────────────────────────────────────────────────
    def get(self, video_path: str, timestamp: float) -> Optional[np.ndarray]:
        """Return the BGR frame at ``timestamp`` seconds, or None on failure."""
        key = (video_path, round(timestamp, 3))
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                # Move to end (most-recently-used)
                self._cache.move_to_end(key)
                return cached

        # Not cached — fetch from disk
        frame = self._fetch(video_path, timestamp)
        if frame is None:
            return None

        with self._lock:
            self._cache[key] = frame
            self._cache.move_to_end(key)
            # Evict oldest if over capacity
            while len(self._cache) > self._max:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug(f"Evicted frame {evicted_key} from LRU cache")
        return frame

    def prefetch(self, video_path: str, timestamp: float) -> None:
        """Fetch a frame in the background (best-effort, no return value)."""
        import threading
        threading.Thread(
            target=self.get, args=(video_path, timestamp), daemon=True
        ).start()

    def release_path(self, video_path: str) -> None:
        """Drop all cached frames for a given video path (e.g. on file close)."""
        with self._lock:
            keys_to_drop = [k for k in self._cache if k[0] == video_path]
            for k in keys_to_drop:
                self._cache.pop(k, None)
        with self._caps_lock:
            cap = self._caps.pop(video_path, None)
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    def clear(self) -> None:
        """Drop the entire cache and release all VideoCapture handles."""
        with self._lock:
            self._cache.clear()
        with self._caps_lock:
            for cap in self._caps.values():
                try:
                    cap.release()
                except Exception:
                    pass
            self._caps.clear()

    def stats(self) -> dict:
        """Return cache statistics for diagnostics."""
        with self._lock:
            return {
                "entries": len(self._cache),
                "max": self._max,
                "paths_tracked": len(self._caps),
            }

    def resize(self, max_entries: int) -> None:
        """Change the LRU capacity, evicting excess entries if shrinking."""
        self._max = max(1, int(max_entries))
        with self._lock:
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)

    # ── internal ────────────────────────────────────────────────────
    def _fetch(self, video_path: str, timestamp: float) -> Optional[np.ndarray]:
        """Open (or reuse) a VideoCapture, seek to ``timestamp``, read one frame."""
        cap = self._get_cap(video_path)
        if cap is None:
            return None
        try:
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.warning(f"Failed to read frame at {timestamp:.3f}s from {video_path}")
                return None
            return frame
        except Exception as e:
            logger.error(f"Error reading frame: {e}")
            return None

    def _get_cap(self, video_path: str):
        """Get (or open) a VideoCapture for ``video_path``. Returns None on failure."""
        with self._caps_lock:
            cap = self._caps.get(video_path)
            if cap is not None:
                return cap
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Could not open video: {video_path}")
                return None
            self._caps[video_path] = cap
            return cap


# Module-level singleton
FRAME_STORE = FrameStore()


def ensure_frame(cand) -> Optional[np.ndarray]:
    """Return the candidate's frame, re-fetching from disk if it was released.

    This is the canonical accessor — never read ``cand.frame_bgr`` directly
    from outside ``analysis.py``; always go through this helper (or
    ``cand.ensure_frame()`` which wraps it).
    """
    if cand.frame_bgr is not None:
        return cand.frame_bgr
    if not cand.video_path or cand.timestamp < 0:
        return None
    frame = FRAME_STORE.get(cand.video_path, cand.timestamp)
    if frame is not None:
        cand.frame_bgr = frame  # re-attach so subsequent access is free
    return frame
