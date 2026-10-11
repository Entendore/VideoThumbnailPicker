from __future__ import annotations
import math
import logging
import traceback
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import concurrent.futures
import os

from PySide6.QtCore import QThread, Signal

# ────────────────────────────────────────────────────────────────────────────
# Logging & Globals
# ────────────────────────────────────────────────────────────────────────────
logger = logging.getLogger("thumbnail_picker")
_face_cascade = _profile_cascade = None

def _get_cascades():
    global _face_cascade, _profile_cascade
    if _face_cascade is None:
        try:
            _face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            _profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
            if _face_cascade.empty() or _profile_cascade.empty():
                raise IOError("Cascades files are empty")
            logger.info("Haar cascades loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load cascades: {e}. Face detection disabled.")
            _face_cascade = None
            _profile_cascade = None
    return _face_cascade, _profile_cascade

# ────────────────────────────────────────────────────────────────────────────
# Data Classes
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class Candidate:
    frame_bgr: np.ndarray
    timestamp: float
    total_score: float
    breakdown: dict
    faces: List[Tuple[int, int, int, int]] = field(default_factory=list)
    starred: bool = False

# ────────────────────────────────────────────────────────────────────────────
# Scoring Logic
# ────────────────────────────────────────────────────────────────────────────

def prefilter_frame(bgr) -> bool:
    if bgr is None or bgr.size == 0: return False
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    m = np.mean(gray)
    if m < 20 or m > 240: return False
    if cv2.Laplacian(gray, cv2.CV_8U).var() < 15: return False
    return True

def score_faces(bgr):
    fc, pc = _get_cascades()
    if fc is None or fc.empty(): return 0.0, []
    
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = fc.detectMultiScale(g, 1.2, 5, minSize=(40,40))
    if len(faces) == 0 and pc and not pc.empty():
        faces = pc.detectMultiScale(g, 1.2, 5, minSize=(40,40))
    
    if len(faces) == 0: return 0.0, []
    
    H, W = bgr.shape[:2]
    largest = max(faces, key=lambda r: r[2]*r[3])
    fx = (largest[0] + largest[2]/2) / W
    fy = (largest[1] + largest[3]/2) / H
    dist = math.sqrt((fx-0.5)**2 + (fy-0.5)**2)
    center_bonus = max(0, 0.4 * (1 - dist*2))
    area_ratio = (largest[2]*largest[3]) / (H*W)
    size_bonus = 0.2 if 0.05 < area_ratio < 0.5 else 0.0
    return min(0.4 + center_bonus + size_bonus, 1.0), faces

def score_sharpness(gray): 
    if gray is None: return 0.0
    return min(cv2.Laplacian(gray, cv2.CV_64F).var() / 400, 1)
    
def score_contrast(gray): 
    if gray is None: return 0.0
    return min(np.std(gray) / 60, 1)

def score_brightness(gray): 
    if gray is None: return 0.0
    return float(np.exp(-0.5 * ((np.mean(gray) - 128) / 60.0) ** 2))

def score_composition(bgr):
    if bgr is None: return 0.0
    H, W = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150) / 255.0
    wt = np.zeros_like(edges)
    for f in (1/3, 2/3):
        y, x = int(H*f), int(W*f)
        wt[max(0,y-10):min(H,y+10), :] += 0.5
        wt[:, max(0,x-10):min(W,x+10)] += 0.5
    return min(np.mean(edges * wt) * 20, 1.0)

def score_dynamic_range(bgr):
    if bgr is None: return 0.0
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    p_lo, p_hi = np.percentile(g, [5, 95])
    return min((p_hi - p_lo) / 255.0, 1.0)

def score_colorfulness(bgr):
    if bgr is None: return 0.0
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    return min(np.std(lab[:,:,1:]) / 50.0, 1.0)

SCORERS = {
    "sharpness": lambda f, p: score_sharpness(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) if f is not None else None),
    "contrast": lambda f, p: score_contrast(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) if f is not None else None),
    "brightness": lambda f, p: score_brightness(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) if f is not None else None),
    "composition": lambda f, p: score_composition(f),
    "motion": lambda f, p: 0.0, 
    "dynamic_range": lambda f, p: score_dynamic_range(f),
    "colorfulness": lambda f, p: score_colorfulness(f),
    "exposure_quality": lambda f, p: 0.5,
    "visual_complexity": lambda f, p: 0.5,
    "color_harmony": lambda f, p: 0.5,
    "center_weight": lambda f, p: 0.5,
    "skin_tone": lambda f, p: 0.5,
    "entropy": lambda f, p: 0.5,
}

def _color_hist(bgr):
    if bgr is None: return np.zeros(200)
    h = cv2.calcHist([cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)], [0,1], None, [20,10], [0,180,0,256]).flatten()
    return h / (h.sum() + 1e-8)

def filter_similar(cands: List[Candidate]):
    if len(cands) <= 1: return cands
    kept = [cands[0]]
    kept_h = [_color_hist(cands[0].frame_bgr)]
    for c in cands[1:]:
        h = _color_hist(c.frame_bgr)
        if all(cv2.compareHist(h, kh, cv2.HISTCMP_CORREL) < 0.85 for kh in kept_h):
            kept.append(c)
            kept_h.append(h)
    return kept

# ────────────────────────────────────────────────────────────────────────────
# Worker Function for Parallel Execution
# ────────────────────────────────────────────────────────────────────────────

def _process_single_frame(path, t, weights):
    cap = cv2.VideoCapture(path)
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, frame = cap.read()
        
        if not ret or frame is None: return None
        if not prefilter_frame(frame): return None
        
        face_score, faces = score_faces(frame)
        scores = {n: s(frame, None) for n, s in SCORERS.items()}
        scores['faces'] = face_score
        
        total = sum(scores[k] * w for k, w in weights.items())
        
        return Candidate(frame, float(t), total, scores, faces=faces)
    except Exception as e:
        # Log errors from worker threads
        logging.error(f"Worker error: {e}")
        return None
    finally:
        cap.release()

# ────────────────────────────────────────────────────────────────────────────
# Backend Thread
# ────────────────────────────────────────────────────────────────────────────

class AnalysisThread(QThread):
    progress = Signal(int, int) 
    stage_changed = Signal(str) 
    finished_ok = Signal(list, dict)
    finished_err = Signal(str)
    candidate_ready = Signal(object, int, int)
    filmstrip_ready = Signal(list) 

    def __init__(self, path, n_samples, weights, n_cands, use_scene):
        super().__init__()
        self.path = path
        self.n_samples = n_samples
        self.weights = weights
        self.n_cands = n_cands
        self.use_scene = use_scene
        self._abort = False

    def run(self):
        logger.info(f"Starting PARALLEL analysis for: {self.path}")
        cap = cv2.VideoCapture(self.path)
        if not cap.isOpened(): 
            msg = "Cannot open video file."
            logger.error(msg)
            self.finished_err.emit(msg)
            return
        
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            dur = total_frames / fps if fps > 0 else 0
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if dur == 0:
                self.finished_err.emit("Video has zero duration.")
                return

            logger.info(f"Video Info: {w}x{h} @ {fps:.2f}fps, Duration: {dur:.2f}s")
            
            # --- 1. FILMSTRIP ---
            self.stage_changed.emit("Phase 1: Scanning Video")
            filmstrip = []
            
            n_strip = min(200, int(dur / 2))
            if n_strip < 20: n_strip = min(20, int(dur))
            
            logger.info(f"Phase 1: Scanning {n_strip} frames for filmstrip...")
            
            for i in range(n_strip):
                if self._abort: return
                t = dur * (i + 0.5) / n_strip
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ret, f = cap.read()
                
                if ret and f is not None:
                    f_small = cv2.resize(f, (int(f.shape[1] * (64/f.shape[0])), 64))
                    filmstrip.append((t, f_small))
                
                # Log every 10% of filmstrip generation
                if n_strip > 10 and (i+1) % (n_strip // 10) == 0:
                    pct = int(100 * (i+1) / n_strip)
                    logger.info(f"Filmstrip scan: {pct}% complete ({i+1}/{n_strip})")
                    
                self.progress.emit(i + 1, n_strip + self.n_samples)
            
            self.filmstrip_ready.emit(filmstrip)
            logger.info("Filmstrip generation complete.")
            cap.release()
            
            # --- 2. SAMPLING ---
            self.stage_changed.emit("Phase 2: Detecting Scenes")
            sample_times = []
            
            if self.use_scene:
                logger.info("Performing scene detection...")
                s_cap = cv2.VideoCapture(self.path)
                prev_gray = None
                step = int(fps)
                
                # Log progress for scene detection (can be slow on 5hr video)
                log_interval = int(total_frames / 10) # Log every 10%
                
                for i in range(0, total_frames, step):
                    if self._abort: return
                    s_cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, f = s_cap.read()
                    if not ret: continue
                    gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
                    if prev_gray is not None:
                        diff = np.mean(cv2.absdiff(gray, prev_gray))
                        if diff > 25: sample_times.append(i/fps)
                    prev_gray = gray
                    
                    if log_interval > 0 and i % log_interval < step:
                         logger.info(f"Scene scan: {int(100*i/total_frames)}% complete")
                         
                s_cap.release()
                logger.info(f"Detected {len(sample_times)} scene changes.")
            
            if not sample_times:
                sample_times = list(np.linspace(0.05, 0.95, self.n_samples) * dur)

            # --- 3. PARALLEL ANALYSIS ---
            self.stage_changed.emit("Phase 3: Analyzing (Parallel)")
            cands = []
            
            logger.info(f"Phase 3: Dispatching {len(sample_times)} tasks to CPU threads...")
            
            max_workers = os.cpu_count() or 4
            total_analysis_tasks = len(sample_times)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_time = {
                    executor.submit(_process_single_frame, self.path, t, self.weights): t 
                    for t in sample_times
                }
                
                processed_count = 0
                last_log_pct = 0
                
                for future in concurrent.futures.as_completed(future_to_time):
                    if self._abort:
                        logger.warning("Aborting analysis...")
                        executor.shutdown(wait=False, cancel_futures=True)
                        return
                        
                    processed_count += 1
                    self.progress.emit(n_strip + processed_count, n_strip + total_analysis_tasks)
                    
                    # Log every 10% completion
                    if total_analysis_tasks > 0:
                        current_pct = int(10 * processed_count / total_analysis_tasks) * 10
                        if current_pct > last_log_pct:
                            last_log_pct = current_pct
                            logger.info(f"Analysis: {current_pct}% complete ({processed_count}/{total_analysis_tasks} frames)")
                    
                    try:
                        cand = future.result()
                        if cand:
                            cands.append(cand)
                            if len(cands) % 5 == 0: 
                                self.candidate_ready.emit(cand, processed_count, total_analysis_tasks)
                    except Exception as e:
                        logger.error(f"Error processing frame: {e}")

            logger.info(f"Parallel analysis complete. Found {len(cands)} raw candidates.")
            
            cands.sort(key=lambda c: c.total_score, reverse=True)
            cands = filter_similar(cands)[:self.n_cands]
            
            info = dict(path=self.path, duration=dur, fps=fps, width=w, height=h)
            logger.info(f"Analysis complete. Returning {len(cands)} candidates.")
            self.finished_ok.emit(cands, info)
            
        except Exception as e: 
            traceback.print_exc()
            logger.error(f"Analysis error: {e}")
            self.finished_err.emit(str(e))

    def abort(self): 
        self._abort = True