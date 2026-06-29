"""Video Thumbnail Picker — single-file concise version."""
import json, logging, math, os, sys, time, threading, traceback
import concurrent.futures
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import Qt, QTimer, QRectF, QPoint, Signal, QSettings
from PySide6.QtGui import (QPixmap, QImage, QPainter, QColor, QFont, QPen,
    QPainterPath, QMouseEvent, QKeySequence, QShortcut, QAction,
    QDragEnterEvent, QDropEvent)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QComboBox, QSpinBox, QProgressBar,
    QScrollArea, QFileDialog, QMessageBox, QSplitter, QFrame, QToolBar,
    QCheckBox, QGridLayout, QSizePolicy, QTabWidget, QSlider, QMenu,
    QGraphicsView, QGraphicsScene, QDialog, QDialogButtonBox, QGroupBox,
    QLineEdit, QDoubleSpinBox)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S", stream=sys.stdout, force=True)
log = logging.getLogger("vtp")
os.environ.setdefault("OMP_NUM_THREADS", "1")
try:
    cv2.setNumThreads(0); cv2.ocl.setUseOpenCL(True)
except Exception as e:
    log.warning(f"OpenCV config: {e}")

# ── Config ──────────────────────────────────────────────────────────────
PRESETS = {"Original": None, "YouTube 720p": (1280, 720), "YouTube 1080p": (1920, 1080),
           "Instagram Square": (1080, 1080), "Instagram Portrait": (1080, 1350),
           "Twitter Header": (1500, 500), "TikTok": (1080, 1920)}

ALGO_PROFILES = {
    "General": {"sharpness": .15, "colorfulness": .08, "contrast": .07, "brightness": .05,
                "entropy": .08, "composition": .10, "skin_tone": .04, "faces": .12,
                "motion": .03, "exposure": .08, "dynamic_range": .06, "complexity": .04,
                "color_harmony": .05, "center_weight": .05},
    "Portrait": {"sharpness": .18, "faces": .35, "skin_tone": .12, "center_weight": .12,
                 "exposure": .10, "brightness": .05, "composition": .04, "contrast": .04},
    "Scenery": {"composition": .20, "color_harmony": .15, "dynamic_range": .12,
                "sharpness": .12, "exposure": .10, "complexity": .08, "contrast": .08,
                "colorfulness": .07, "entropy": .05, "center_weight": .03},
    "Action": {"sharpness": .18, "contrast": .14, "dynamic_range": .10, "complexity": .10,
               "exposure": .08, "entropy": .08, "colorfulness": .07, "composition": .07,
               "center_weight": .07, "faces": .05, "motion": .03, "brightness": .03},
}

CRIT_LABELS = {"sharpness": "Sharp", "colorfulness": "Color", "contrast": "Contr",
    "brightness": "Bright", "entropy": "Entropy", "composition": "Compos",
    "skin_tone": "Skin", "faces": "Faces", "motion": "Motion", "exposure": "Expos",
    "dynamic_range": "Range", "complexity": "Complex", "color_harmony": "Harmony",
    "center_weight": "Center"}

SCORING_DIM = 720
GALLERY_W, GALLERY_H, FILM_H, GALLERY_COLS = 200, 110, 64, 3
BATCH_MS, FILM_FRAMES, ETA_MS = 80, 200, 500
SORT_OPTS = [("Score", None, True), ("Starred", "__starred__", True),
    ("Time", "timestamp", False)] + [(L.title(), k, True) for k, L in CRIT_LABELS.items()]
CARD_SIZES = {"Small": (160, 95), "Medium": (200, 110), "Large": (260, 145)}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".wmv"}

# ── Theme ───────────────────────────────────────────────────────────────
THEMES = {"dark": {"BG":"#171717","SF":"#262626","CD":"#2E2E2E","OV":"#404040",
                   "TX":"#D4D4D4","ST":"#737373","AC":"#888888"},
          "light": {"BG":"#FAFAFA","SF":"#F0F0F0","CD":"#E8E8E8","OV":"#D4D4D4",
                    "TX":"#1A1A1A","ST":"#737373","AC":"#525252"}}

def ss(c):
    return f"""QMainWindow{{background:{c['BG']}}}QWidget{{color:{c['TX']};font-family:Segoe UI,sans-serif;font-size:12px}}
QToolTip{{background:{c['OV']};color:{c['TX']};border:1px solid {c['SF']};padding:4px;border-radius:4px}}
QGroupBox{{border:1px solid {c['OV']};border-radius:6px;margin-top:14px;padding:12px 10px;font-weight:bold;background:{c['SF']}}}
QPushButton{{background:{c['OV']};color:{c['TX']};border:none;border-radius:5px;padding:7px 14px;font-weight:600}}
QPushButton:hover{{background:{c['AC']};color:{c['BG']}}}QPushButton:disabled{{background:{c['OV']};color:{c['ST']}}}
QPushButton#btnPrimary{{background:{c['TX']};color:{c['BG']}}}QPushButton#btnPrimary:hover{{background:{c['AC']};color:{c['BG']}}}
QComboBox,QSpinBox,QDoubleSpinBox{{background:{c['CD']};border:1px solid {c['OV']};border-radius:5px;padding:5px}}
QComboBox QAbstractItemView{{background:{c['CD']};selection-background-color:{c['AC']}}}
QScrollArea{{border:none;background:transparent}}
QScrollBar:vertical{{background:{c['SF']};width:10px;border-radius:5px}}
QScrollBar::handle:vertical{{background:{c['OV']};border-radius:5px;min-height:24px}}
QScrollBar::handle:vertical:hover{{background:{c['AC']}}}
QStatusBar{{background:{c['SF']};color:{c['ST']};border-top:1px solid {c['OV']}}}
QSlider::groove:horizontal{{height:4px;background:{c['OV']};border-radius:2px}}
QSlider::handle:horizontal{{background:{c['TX']};width:14px;height:14px;margin:-5px 0;border-radius:7px}}
QCheckBox::indicator{{width:14px;height:14px;border-radius:3px;border:1px solid {c['OV']};background:{c['CD']}}}
QCheckBox::indicator:checked{{background:{c['TX']}}}
QProgressBar{{border:none;border-radius:5px;background:{c['OV']};text-align:center;color:{c['BG']};font-weight:bold}}
QProgressBar::chunk{{background:{c['TX']};border-radius:4px}}
QFrame#Card{{background:{c['CD']};border-radius:8px}}
QTabWidget::pane{{border:1px solid {c['OV']};border-radius:6px;background:{c['SF']}}}
QTabBar::tab{{background:{c['CD']};color:{c['ST']};padding:8px 18px;border-top-left-radius:5px;border-top-right-radius:5px;margin-right:2px}}
QTabBar::tab:selected{{background:{c['SF']};color:{c['TX']};font-weight:bold}}
QToolBar{{background:{c['SF']};border-bottom:1px solid {c['OV']};spacing:4px;padding:4px}}
QMenu{{background:{c['CD']};border:1px solid {c['OV']};border-radius:5px;padding:4px}}
QMenu::item:selected{{background:{c['AC']};color:{c['BG']}}}
QLabel#title{{font-size:15px;font-weight:bold;color:{c['TX']}}}"""

# ── Settings ────────────────────────────────────────────────────────────
class Settings:
    def __init__(self):
        self._s = QSettings("VTP", "Video Thumbnail Picker")
    def save_win(self, w):
        self._s.setValue("geo", w.saveGeometry())
        if hasattr(w, "_sp"): self._s.setValue("sp", w._sp.sizes())
    def restore_win(self, w):
        g = self._s.value("geo")
        if g: w.restoreGeometry(g)
    def sp_sizes(self):
        r = self._s.value("sp"); return [int(x) for x in r] if isinstance(r, (list, tuple)) else []
    def save_ana(self, **kw):
        for k, v in kw.items(): self._s.setValue(f"a/{k}", v)
    def load_ana(self):
        return {"algo": self._s.value("a/algo", "General", type=str),
                "preset": self._s.value("a/preset", "Original", type=str),
                "samples": self._s.value("a/samples", 80, type=int),
                "cands": self._s.value("a/cands", 15, type=int),
                "scene": self._s.value("a/scene", False, type=bool),
                "sort": self._s.value("a/sort", "Score", type=str),
                "thr": self._s.value("a/thr", 0.0, type=float)}
    @property
    def card_size(self): return self._s.value("ui/card", "Medium", type=str)
    @card_size.setter
    def card_size(self, v): self._s.setValue("ui/card", v)
    @property
    def theme(self): return self._s.value("ui/theme", "dark", type=str)
    @theme.setter
    def theme(self, v): self._s.setValue("ui/theme", v)
    @property
    def template(self): return self._s.value("ui/tpl", "thumb_{timestamp}.jpg", type=str)
    @template.setter
    def template(self, v): self._s.setValue("ui/tpl", v)
    @property
    def auto_free(self): return self._s.value("ui/af", False, type=bool)
    @auto_free.setter
    def auto_free(self, v): self._s.setValue("ui/af", bool(v))
    @property
    def quality(self): return self._s.value("io/q", 95, type=int)
    @quality.setter
    def quality(self, v): self._s.setValue("io/q", max(1, min(100, int(v))))
    @property
    def fmt(self): return self._s.value("io/fmt", "JPEG", type=str)
    @fmt.setter
    def fmt(self, v): self._s.setValue("io/fmt", v)
    @property
    def re_radius(self): return self._s.value("a/rer", 2.0, type=float)
    @re_radius.setter
    def re_radius(self, v): self._s.setValue("a/rer", float(v))
    @property
    def re_samples(self): return self._s.value("a/res", 12, type=int)
    @re_samples.setter
    def re_samples(self, v): self._s.setValue("a/res", max(4, int(v)))
    @property
    def recent(self):
        r = self._s.value("recent", [])
        if isinstance(r, str): r = [r]
        return [str(f) for f in r if isinstance(r, (list, tuple)) and Path(f).exists()] if isinstance(r, (list, tuple)) else []
    def add_recent(self, p):
        r = self.recent; n = str(Path(p).resolve())
        r = [f for f in r if Path(f).resolve() != Path(n)]
        r.insert(0, n); self._s.setValue("recent", r[:10])
    @property
    def profiles(self):
        r = self._s.value("prof", {})
        return {k: {kk: float(vv) for kk, vv in v.items()} for k, v in r.items() if isinstance(v, dict)} if isinstance(r, dict) else {}
    def save_profile(self, n, w):
        p = self.profiles; p[n] = {k: float(v) for k, v in w.items()}; self._s.setValue("prof", p)
    @property
    def last_dir(self): return self._s.value("io/dir", "", type=str)
    @last_dir.setter
    def last_dir(self, v): self._s.setValue("io/dir", v)
    def sync(self): self._s.sync()

S = Settings()

class Sidecar:
    @staticmethod
    def path(v): return Path(v).with_suffix(".vtp.json")
    @staticmethod
    def save(v, cands):
        try: Sidecar.path(v).write_text(json.dumps({"v": 1, "video": v,
            "starred": [round(c.timestamp, 3) for c in cands if c.starred]}, indent=2))
        except Exception as e: log.warning(f"Sidecar save: {e}")
    @staticmethod
    def load(v):
        p = Sidecar.path(v)
        if not p.exists(): return {}
        try: return json.loads(p.read_text())
        except Exception: return {}

# ── Utils ───────────────────────────────────────────────────────────────
def fmt_t(t):
    if t < 0 or not np.isfinite(t): return "00:00.000"
    m, s = divmod(int(t), 60); return f"{m:02d}:{s:02d}.{int((t-int(t))*1000):03d}"

def fmt_dur(t):
    if t <= 0: return "0s"
    h, r = divmod(int(t), 3600); m, s = divmod(r, 60)
    p = []; (p.append(f"{h}h") if h else None); (p.append(f"{m}m") if m or h else None); p.append(f"{s}s")
    return " ".join(p)

def bgr2qim(b):
    if b is None or b.size == 0: return None
    rgb = cv2.cvtColor(b, cv2.COLOR_BGR2RGB); h, w = rgb.shape[:2]
    q = QImage(rgb.data, w, h, 3*w, QImage.Format.Format_RGB888); q._buf = rgb; return q

def bgr2qpm(b):
    q = bgr2qim(b); return QPixmap.fromImage(q) if q else QPixmap()

def scaled_pm(b, w, h):
    if b is None or b.size == 0: return QPixmap()
    sh, sw = b.shape[:2]; sc = min(w/sw, h/sh)
    r = cv2.resize(b, (max(1, int(sw*sc)), max(1, int(sh*sc))), interpolation=cv2.INTER_AREA)
    return bgr2qpm(r)

def fit_crop(img, t):
    tw, th = t
    if img.size == (tw, th): return img
    r = max(tw/img.width, th/img.height)
    img = img.resize((int(img.width*r), int(img.height*r)), Image.Resampling.LANCZOS)
    l, tp = (img.width-tw)//2, (img.height-th)//2
    return img.crop((l, tp, l+tw, tp+th))

def downscale(b, mx):
    if b is None or b.size == 0: return np.zeros((0,0,3), np.uint8), np.zeros((0,0), np.uint8)
    h, w = b.shape[:2]; L = max(h, w)
    s = b if L <= mx else cv2.resize(b, (int(w*mx/L), int(h*mx/L)), interpolation=cv2.INTER_AREA)
    return s, cv2.cvtColor(s, cv2.COLOR_BGR2GRAY)

class ThumbCache:
    def __init__(self):
        self._l = threading.Lock(); self._g = {}; self._f = {}
    def gal(self, i, b):
        with self._l:
            p = self._g.get(i)
            if p is None or p.isNull(): p = scaled_pm(b, GALLERY_W, GALLERY_H); self._g[i] = p
            return p
    def film(self, i, b):
        with self._l:
            p = self._f.get(i)
            if p is None or p.isNull():
                sh, sw = b.shape[:2]; w = max(1, int(sw*FILM_H/sh))
                p = bgr2qpm(cv2.resize(b, (w, FILM_H), interpolation=cv2.INTER_AREA)); self._f[i] = p
            return p
    def inv(self, i=None):
        with self._l:
            if i is None: self._g.clear(); self._f.clear()
            else: self._g.pop(i, None); self._f.pop(i, None)
TC = ThumbCache()

class FrameStore:
    def __init__(self, mx=50):
        self._mx = mx; self._c = OrderedDict(); self._l = threading.RLock()
        self._caps = {}; self._cl = threading.Lock()
    def get(self, v, t):
        k = (v, round(t, 3))
        with self._l:
            c = self._c.get(k)
            if c is not None: self._c.move_to_end(k); return c
        f = self._fetch(v, t)
        if f is None: return None
        with self._l:
            self._c[k] = f; self._c.move_to_end(k)
            while len(self._c) > self._mx: self._c.popitem(last=False)
        return f
    def _fetch(self, v, t):
        c = self._cap(v)
        if c is None: return None
        try:
            c.set(cv2.CAP_PROP_POS_MSEC, t*1000); r, f = c.read()
            return f if r and f is not None else None
        except Exception: return None
    def _cap(self, v):
        with self._cl:
            c = self._caps.get(v)
            if c is not None: return c
            c = cv2.VideoCapture(v)
            if not c.isOpened(): return None
            self._caps[v] = c; return c
    def clear(self):
        with self._l: self._c.clear()
        with self._cl:
            for c in self._caps.values():
                try: c.release()
                except: pass
            self._caps.clear()
    def stats(self):
        with self._l: return {"n": len(self._c), "mx": self._mx}
FS = FrameStore()

# ── Scoring ─────────────────────────────────────────────────────────────
_face_c = _prof_c = None
def cascades():
    global _face_c, _prof_c
    if _face_c is None:
        try:
            _face_c = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            _prof_c = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
            if _face_c.empty(): raise IOError
        except Exception: _face_c = _prof_c = None
    return _face_c, _prof_c

@dataclass(eq=False)
class Cand:
    frame: Optional[np.ndarray]
    timestamp: float
    score: float
    bd: Dict[str, float]
    faces: List[Tuple[int,int,int,int]] = field(default_factory=list)
    starred: bool = False
    video: Optional[str] = None
    _h: Optional[np.ndarray] = field(default=None, repr=False)
    _eh: Optional[np.ndarray] = field(default=None, repr=False)
    @property
    def hist(self):
        if self._h is None:
            f = self.ensure()
            if f is None: return np.zeros(200, np.float32)
            hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
            h = cv2.calcHist([hsv], [0,1], None, [20,10], [0,180,0,256]).flatten()
            self._h = h / (h.sum() + 1e-8)
        return self._h
    def ensure(self):
        if self.frame is not None: return self.frame
        if not self.video or self.timestamp < 0: return None
        f = FS.get(self.video, self.timestamp)
        if f is not None: self.frame = f
        return f
    def release(self):
        self.frame = None; self._h = None; self._eh = None

def asat(x, sc=1.0, of=0.0):
    return float((2.0/math.pi) * math.atan((max(0.0, x) + of) / sc))

def prefilter(b):
    if b is None or b.size == 0: return False
    g = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY); m = float(np.mean(g))
    if m < 18 or m > 242: return False
    pl, ph = np.percentile(g, [10, 90])
    if (ph - pl) < 25: return False
    if sum(1 for c in range(3) if float(np.std(b[:,:,c])) < 8) >= 2: return False
    if cv2.Laplacian(g, cv2.CV_64F).var() < 12: return False
    return True

def s_faces(b):
    fc, pc = cascades()
    if fc is None or fc.empty(): return 0.0, []
    g = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    fs = fc.detectMultiScale(g, 1.2, 5, minSize=(40,40))
    if len(fs) == 0 and pc and not pc.empty(): fs = pc.detectMultiScale(g, 1.2, 5, minSize=(40,40))
    if len(fs) == 0: return 0.0, []
    H, W = b.shape[:2]; L = max(fs, key=lambda r: r[2]*r[3])
    fx = (L[0]+L[2]/2)/W; fy = (L[1]+L[3]/2)/H
    d = math.sqrt((fx-0.5)**2 + (fy-0.5)**2)
    cb = max(0.0, 0.4*(1-d*2)); ar = (L[2]*L[3])/(H*W)
    sb = 0.2 if 0.05 < ar < 0.5 else 0.0
    return min(0.4+cb+sb, 1.0), [tuple(int(v) for v in f) for f in fs]

def s_sharp(g):
    if g is None or g.size == 0: return 0.0
    gx = cv2.Sobel(g, cv2.CV_64F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_64F, 0, 1, ksize=3)
    t = float(np.mean(gx*gx+gy*gy))/1000; l = cv2.Laplacian(g, cv2.CV_64F).var()/100
    tn, ln = asat(t, 0.55), asat(l, 0.50)
    return 0.0 if tn+ln < 1e-9 else float(2*tn*ln/(tn+ln))

def s_contr(g):
    if g is None or g.size == 0: return 0.0
    r = asat(float(np.std(g))/40, 0.45, 0.10)
    bf = cv2.GaussianBlur(g, (7,7), 1.5); bc = cv2.GaussianBlur(g, (21,21), 5.0)
    lf = asat(float(np.mean(np.abs(g.astype(np.float64)-bf.astype(np.float64))))/15, 0.50)
    lc = asat(float(np.mean(np.abs(g.astype(np.float64)-bc.astype(np.float64))))/25, 0.50)
    return float(0.40*r + 0.35*lf + 0.25*lc)

def s_bright(g):
    if g is None or g.size == 0: return 0.0
    mu = float(np.mean(g)); gs = math.exp(-0.5*((mu-135)/55)**2)
    bb = 1.0 + 0.15*math.log1p(math.exp((mu-128)/20))
    return float(min(gs*min(bb, 1.15), 1.0))

def s_ent(g):
    if g is None or g.size == 0: return 0.0
    h = cv2.calcHist([g], [0], None, [256], [0,256]).flatten(); t = h.sum()
    if t < 1: return 0.0
    p = h/t; pnz = p[p>0]; H = float(-np.sum(pnz*np.log2(pnz)))
    return float(min(asat(H/8, 0.40, 0.05), 1.0))

def s_expos(b, g=None):
    if b is None or b.size == 0: return 0.0
    if g is None: g = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    h = cv2.calcHist([g], [0], None, [256], [0,256]).flatten(); t = h.sum()
    if t < 1: return 0.0
    p = h/t; sc = float(np.sum(p[:5])); hc = float(np.sum(p[251:]))
    cs = max(0.0, 1.0-(sc+hc)*10)
    cdf = np.cumsum(p); p2 = float(np.searchsorted(cdf, 0.02)); p98 = float(np.searchsorted(cdf, 0.98))
    ss = asat((p98-p2)/255, 0.45, 0.05)
    bins = np.arange(256, np.float64); mu = float(np.sum(bins*p))
    if mu < 1e-9: sh = 0.3
    else:
        v = float(np.sum(((bins-mu)**2)*p))
        if v < 1e-9: sh = 0.3
        else:
            m4 = float(np.sum(((bins-mu)**4)*p)); k = m4/(v**2)-3
            sh = math.exp(-0.5*((k-2.5)/4)**2)
    return float(min((cs*ss*sh)**(1/3), 1.0))

def s_comp(b, g=None):
    if b is None or b.size == 0: return 0.0
    H, W = b.shape[:2]
    if g is None: g = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    e = cv2.Canny(g, 50, 150).astype(np.float64)/255
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    def gs(cx, cy, sx, sy):
        gg = np.exp(-0.5*(((xx/W-cx)/sx)**2+((yy/H-cy)/sy)**2)); return float(np.sum(e*gg))
    sx, sy = 0.09, 0.09
    th = sum(gs(fx, fy, sx, sy) for fx in (1/3, 2/3) for fy in (1/3, 2/3))
    gh = sum(gs(fx, fy, sx*0.8, sy*0.8) for fx in (0.382, 0.618) for fy in (0.382, 0.618))
    a = H*W; gsm = float(np.exp(0))*a
    tn = asat(th/(gsm*0.05), 0.45); gn = asat(gh/(gsm*0.05), 0.45)
    te = e.sum()+1e-9; cx = float((e*xx).sum()/te)/W; cy = float((e*yy).sum()/te)/H
    cd = math.sqrt((cx-0.5)**2+(cy-0.5)**2); cs = max(0.0, 1.0-cd/0.5)
    return float(min(0.55*tn+0.20*gn+0.25*cs, 1.0))

def s_dr(b, g=None):
    if b is None or b.size == 0: return 0.0
    if g is None: g = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    pl, ph = float(np.percentile(g, 1)), float(np.percentile(g, 99))
    rs = asat((ph-pl)/255, 0.40, 0.05)
    h = cv2.calcHist([g], [0], None, [256], [0,256]).flatten()
    gr = float(np.sum(h==0))/256 if h.sum() > 0 else 0.5
    return float(min(rs*(1-0.3*gr), 1.0))

def s_col(b):
    if b is None or b.size == 0: return 0.0
    rgb = b[:,:,::-1].astype(np.float64); rg = rgb[:,:,0]-rgb[:,:,1]
    yb = 0.5*(rgb[:,:,0]+rgb[:,:,1])-rgb[:,:,2]
    C = math.sqrt(np.std(rg)**2+np.std(yb)**2)+0.3*math.sqrt(np.mean(rg)**2+np.mean(yb)**2)
    return float(min(asat(C/100, 0.45, 0.02), 1.0))

def s_cplx(b, g=None):
    if b is None or b.size == 0: return 0.0
    if g is None: g = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    H, W = g.shape[:2]; e = cv2.Canny(g, 50, 150)
    ds = asat(float(np.count_nonzero(e))/(H*W)*3, 0.40, 0.02)
    gx = cv2.Sobel(g, cv2.CV_64F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_64F, 0, 1, ksize=3)
    m = np.sqrt(gx**2+gy**2); mk = m > 10
    if mk.sum() < 10: return ds
    an = np.mod(np.arctan2(gy[mk], gx[mk]), np.pi)
    hi, _ = np.histogram(an, bins=12, range=(0, np.pi)); p = hi/hi.sum()
    on = float(-np.sum(p[p>0]*np.log2(p[p>0])))/math.log2(12)
    return float(min(0.55*ds+0.45*on, 1.0))

def s_harm(b):
    if b is None or b.size == 0: return 0.0
    hsv = cv2.cvtColor(b, cv2.COLOR_BGR2HSV).astype(np.float64)
    hu = hsv[:,:,0]/180*np.pi; sa = hsv[:,:,1]/255
    mk = sa > 0.15
    if mk.sum() < 20: return 0.5
    hs, ws = hu[mk], sa[mk]; wsm = ws.sum()
    if wsm < 1e-9: return 0.5
    cs = float(np.sum(ws*np.cos(2*hs)))/wsm; sn = float(np.sum(ws*np.sin(2*hs)))/wsm
    co = math.sqrt(cs**2+sn**2)
    return float(min(0.50*co+0.25, 1.0))

def s_cw(b, g=None):
    if b is None or b.size == 0: return 0.0
    H, W = b.shape[:2]
    if g is None: g = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(g, cv2.CV_64F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_64F, 0, 1, ksize=3)
    ee = np.sqrt(gx**2+gy**2)
    hsv = cv2.cvtColor(b, cv2.COLOR_BGR2HSV).astype(np.float64)
    sw = hsv[:,:,1]/255; sal = ee*(0.5+0.5*sw)
    sm = sal.max(); sal = sal/sm if sm > 1e-9 else sal
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64); cx, cy = W/2, H/2
    sig = min(W, H)*0.35; rad = np.exp(-0.5*((xx-cx)**2+(yy-cy)**2)/(sig**2))
    sf, rf = sal.flatten(), rad.flatten()
    cs = float(np.dot(sf, rf)/(np.linalg.norm(sf)*np.linalg.norm(rf)+1e-9))
    return float(min(0.55*max(cs, 0)+0.225, 1.0))

def s_skin(b):
    if b is None or b.size == 0: return 0.0
    H, W = b.shape[:2]; ycrcb = cv2.cvtColor(b, cv2.COLOR_BGR2YCrCb); hsv = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)
    cb, cr = ycrcb[:,:,1], ycrcb[:,:,2]
    sy = (cb>=80)&(cb<=120)&(cr>=133)&(cr<=173)
    h, s, v = hsv[:,:,0], hsv[:,:,1], hsv[:,:,2]
    sh = (h<=50)&(s>=20)&(s<=204)&(v>=40)
    sm = sy&sh; sf = float(sm.sum())/(H*W)
    return float(min(asat(sf*5, 0.45, 0.01), 1.0))

def _ehist(g, n=16):
    if g is None or g.size == 0: return np.zeros(n, np.float32)
    gx = cv2.Sobel(g, cv2.CV_64F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_64F, 0, 1, ksize=3)
    m = np.sqrt(gx**2+gy**2); mk = m > 15
    if mk.sum() < 5: return np.zeros(n, np.float32)
    an = np.mod(np.arctan2(gy, gx)[mk], np.pi)
    hi, _ = np.histogram(an, bins=n, range=(0, np.pi), weights=m[mk])
    t = hi.sum(); return (hi/t).astype(np.float32) if t > 0 else np.zeros(n, np.float32)

def s_motion(g, pg=None):
    if pg is None or g is None or g.size == 0: return 0.0
    try:
        f = cv2.calcOpticalFlowFarneback(pg, g, None, 0.5, 3, 15, 2, 5, 1.2, 0)
        mg = np.sqrt(f[:,:,0]**2+f[:,:,1]**2)
        return float(asat(float(np.mean(mg))/4, 0.45, 0.05))
    except: return 0.0

SCORERS = {"sharpness": lambda f,g: s_sharp(g), "contrast": lambda f,g: s_contr(g),
    "brightness": lambda f,g: s_bright(g), "composition": lambda f,g: s_comp(f,g),
    "motion": lambda f,g: 0.0, "dynamic_range": lambda f,g: s_dr(f,g),
    "colorfulness": lambda f,g: s_col(f), "exposure": lambda f,g: s_expos(f,g),
    "complexity": lambda f,g: s_cplx(f,g), "color_harmony": lambda f,g: s_harm(f),
    "center_weight": lambda f,g: s_cw(f,g), "skin_tone": lambda f,g: s_skin(f),
    "entropy": lambda f,g: s_ent(g)}

def norm_scores(cs):
    if len(cs) < 2: return cs
    ks = set(); [ks.update(c.bd.keys()) for c in cs]
    rng = {k: (min(c.bd.get(k,0) for c in cs), max(c.bd.get(k,0) for c in cs)) for k in ks}
    for c in cs:
        for k, (lo, hi) in rng.items():
            if k in c.bd and hi > lo: c.bd[k] = (c.bd[k]-lo)/(hi-lo)
    return cs

def dedup(cs, thr=0.85):
    if len(cs) <= 1: return cs
    for c in cs:
        if c._eh is None:
            f = c.ensure()
            c._eh = _ehist(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)) if f is not None else np.zeros(16, np.float32)
    kept = [cs[0]]; st = thr*0.9
    for c in cs[1:]:
        sim = False
        for k in kept:
            if cv2.compareHist(c.hist, k.hist, cv2.HISTCMP_CORREL) < thr: continue
            if 1-cv2.compareHist(c._eh, k._eh, cv2.HISTCMP_BHATTACHARYYA) > st: sim = True; break
        if not sim: kept.append(c)
    return kept

def proc_frame(p, t, w, get_cap=None, ret_cap=None):
    cap = get_cap() if get_cap else cv2.VideoCapture(p)
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, t*1000); r, f = cap.read()
        if not r or f is None: return None
        if not prefilter(f): return None
        fs, faces = s_faces(f); sm, gr = downscale(f, SCORING_DIM)
        sc = {n: fn(sm, gr) for n, fn in SCORERS.items()}; sc["faces"] = fs
        tot = sum(sc.get(k, 0)*w.get(k, 0) for k in w)
        return Cand(f, float(t), tot, sc, faces, video=p)
    except Exception as e:
        log.error(f"Worker t={t:.2f}: {e}"); return None
    finally:
        (ret_cap(cap) if ret_cap else cap.release())

def grab_film(p, t, h):
    cap = cv2.VideoCapture(p)
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, t*1000); r, f = cap.read()
        if not r or f is None: return None
        w = max(1, int(f.shape[1]*h/f.shape[0]))
        return (t, cv2.resize(f, (w, h), interpolation=cv2.INTER_AREA))
    except: return None
    finally: cap.release()

class AnaThread(QThread):
    progress = Signal(int, int); stage = Signal(str)
    ok = Signal(list, dict); err = Signal(str)
    cand_ready = Signal(object, int, int); film_ready = Signal(list)
    def __init__(self, p, n, w, nc, sc, mw=None, ov=None, sf=False):
        super().__init__()
        self.p, self.n, self.w, self.nc, self.sc = p, n, w, nc, sc
        self.mw = mw or (os.cpu_count() or 4); self.ab = False
        self.ov, self.sf = ov, sf
    def abort(self): self.ab = True
    def run(self):
        cap = cv2.VideoCapture(self.p)
        if not cap.isOpened(): self.err.emit("Cannot open video"); return
        try:
            tf = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); fps = cap.get(cv2.CAP_PROP_FPS) or 30
            dur = tf/fps if fps > 0 else 0; w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); cap.release()
            if dur <= 0: self.err.emit("Zero duration"); return
            if not self.sf:
                self.stage.emit("Scanning"); fl = self._film(dur)
                if self.ab: return
                self.film_ready.emit(fl)
            else: self.film_ready.emit([])
            self.stage.emit("Scenes"); st = self._stimes(tf, fps, dur)
            if self.ab: return
            self.stage.emit("Scoring"); cs = self._score(st, 0)
            if self.ab: return
            cs.sort(key=lambda c: c.score, reverse=True); cs = dedup(cs)[:self.nc]
            if len(cs) > 1:
                cs = norm_scores(cs)
                for c in cs: c.score = sum(c.bd.get(k,0)*self.w.get(k,0) for k in self.w)
                cs.sort(key=lambda c: c.score, reverse=True)
            self.ok.emit(cs, {"path": self.p, "duration": dur, "fps": fps, "width": w, "height": h, "total_frames": tf})
        except Exception as e:
            traceback.print_exc(); self.err.emit(str(e))
    def _film(self, dur):
        n = min(FILM_FRAMES, max(20, int(dur/2))); ts = [dur*(i+0.5)/n for i in range(n)]
        fl = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.mw) as ex:
            fs = {ex.submit(grab_film, self.p, t, 64): t for t in ts}; d = 0
            for f in concurrent.futures.as_completed(fs):
                if self.ab: return []
                d += 1; self.progress.emit(d, n+self.n)
                try:
                    r = f.result()
                    if r: fl.append(r)
                except: pass
        fl.sort(key=lambda r: r[0]); return fl
    def _stimes(self, tf, fps, dur):
        if self.ov is not None: return [max(0, min(t, dur)) for t in self.ov]
        st = []
        if self.sc and fps > 0:
            sc = cv2.VideoCapture(self.p); step = max(1, int(fps)); pg, ph = None, None
            try:
                for i in range(0, tf, step):
                    if self.ab: return []
                    sc.set(cv2.CAP_PROP_POS_FRAMES, i); r, f = sc.read()
                    if not r: continue
                    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
                    if pg is not None:
                        ch = cv2.calcHist([g], [0], None, [64], [0,256]); cv2.normalize(ch, ch)
                        csq = cv2.compareHist(ph, ch, cv2.HISTCMP_CHISQR) if ph is not None else 0
                        pd = float(np.mean(cv2.absdiff(g, pg)))
                        if pd > 20 and csq > 0.5:
                            t = i/fps
                            if not st or (t-st[-1]) >= 1.0: st.append(t)
                        ph = ch.copy()
                    pg = g
            finally: sc.release()
        if not st: st = list(np.linspace(0.05, 0.95, self.n)*dur)
        return st
    def _score(self, st, ns):
        cs = []; tot = len(st)
        if tot == 0: return cs
        le, pr = {"t": 0.0}, {"n": 0}
        def me(c):
            pr["n"] += 1; now = time.monotonic()*1000
            if c and (now-le["t"]) >= BATCH_MS: self.cand_ready.emit(c, pr["n"], tot); le["t"] = now
        cl, cp = threading.Lock(), []
        def gc():
            with cl:
                if cp: return cp.pop()
            return cv2.VideoCapture(self.p)
        def rc(c):
            with cl: cp.append(c)
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.mw) as ex:
            ft = {ex.submit(proc_frame, self.p, t, self.w, gc, rc): t for t in st}
            for f in concurrent.futures.as_completed(ft):
                if self.ab:
                    with cl:
                        for c in cp: c.release()
                        cp.clear()
                    return []
                self.progress.emit(ns+pr["n"], ns+tot)
                try:
                    c = f.result()
                    if c: cs.append(c); me(c)
                    else: pr["n"] += 1
                except: pr["n"] += 1
        with cl:
            for c in cp: c.release()
            cp.clear()
        return cs

# ── Widgets ─────────────────────────────────────────────────────────────
class Preview(QGraphicsView):
    def __init__(self):
        super().__init__(); self._z = 1.0; self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setStyleSheet("background:transparent;border:none")
        self._pi = None; self.sg = self.sf = self.sc = False; self._cs = None; self._cc = None
    def set_pm(self, pm, c=None):
        self.scene().clear(); self._pi = self.scene().addPixmap(pm)
        self.scene().setSceneRect(QRectF(pm.rect()))
        self.fitInView(self._pi, Qt.AspectRatioMode.KeepAspectRatio)
        self._cc, self._z = c, 1.0; self.viewport().update()
    def set_ov(self, grid=None, faces=None, crop=None, cs=None):
        if grid is not None: self.sg = grid
        if faces is not None: self.sf = faces
        if crop is not None: self.sc = crop
        if cs is not None: self._cs = cs
        self.viewport().update()
    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            f = 1.2**(e.angleDelta().y()/120); self.scale(f, f); self._z *= f
        else: super().wheelEvent(e)
    def zi(self): self.scale(1.2, 1.2); self._z *= 1.2
    def zo(self): self.scale(1/1.2, 1/1.2); self._z /= 1.2
    def fit(self):
        if self._pi: self.fitInView(self._pi, Qt.AspectRatioMode.KeepAspectRatio); self._z = 1.0
    def drawForeground(self, p, r):
        if not self._pi: return
        p.save(); w, h = self._pi.pixmap().width(), self._pi.pixmap().height()
        if self.sg:
            pg = QPen(QColor(255,255,255,90), 1); pg.setCosmetic(True); p.setPen(pg)
            for i in range(1, 3):
                p.drawLine(int(w*i/3), 0, int(w*i/3), h); p.drawLine(0, int(h*i/3), w, int(h*i/3))
        if self.sf and self._cc:
            pn = QPen(QColor(THEMES["dark"]["TX"]), 3); pn.setCosmetic(True); p.setPen(pn)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for (x, y, fw, fh) in self._cc.faces: p.drawRect(int(x), int(y), int(fw), int(fh))
        p.restore()

class HistW(QWidget):
    def __init__(self):
        super().__init__(); self.setMinimumHeight(120); self._hd = None; self._ps = []
    def set_data(self, b):
        if b is None or b.size == 0: self._hd = None; self._ps = []; self.update(); return
        self._hd = []
        for i in range(3):
            h = cv2.calcHist([b], [i], None, [256], [0,256]); cv2.normalize(h, h, 0, 1, cv2.NORM_MINMAX)
            self._hd.append(h.flatten())
        self._rp(); self.update()
    def _rp(self):
        self._ps = []
        if not self._hd: return
        w, h = self.width(), self.height(); m, gw, gh = 8, w-2*m, h-2*m
        for hi in self._hd:
            p = QPainterPath(); p.moveTo(m, h-m)
            for i, v in enumerate(hi): p.lineTo(m+(i/255)*gw, h-m-float(v)*gh)
            p.lineTo(m+gw, h-m); self._ps.append(p)
    def resizeEvent(self, e): super().resizeEvent(e); self._rp(); self.update()
    def paintEvent(self, e):
        p = QPainter(self); c = THEMES["dark"]
        p.fillRect(self.rect(), QColor(c["CD"]))
        if not self._ps:
            p.setPen(QColor(c["ST"])); p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data"); return
        cc = [(220,60,60),(60,200,60),(80,130,230)]
        for i, pa in enumerate(self._ps):
            r, g, b = cc[i]; p.fillPath(pa, QColor(r,g,b,80)); p.setPen(QColor(r,g,b)); p.drawPath(pa)

class ScoreW(QWidget):
    def __init__(self):
        super().__init__(); self._s = {}
        self.setMinimumHeight(20+14*len(CRIT_LABELS)+6*(len(CRIT_LABELS)-1))
    def set_scores(self, s): self._s = s or {}; self.update()
    def paintEvent(self, e):
        p = QPainter(self); c = THEMES["dark"]
        p.fillRect(self.rect(), QColor(c["CD"])); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self._s:
            p.setPen(QColor(c["ST"])); p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No candidate"); return
        ks = sorted(k for k in self._s if k in CRIT_LABELS)
        bh, sp, lw, vw, mx, my = 14, 6, 70, 38, 10, 10
        bx, bw = mx+lw, max(40, self.width()-mx-lw-vw-mx)
        p.setFont(QFont("Segoe UI", 9))
        for i, k in enumerate(ks):
            y = my+i*(bh+sp); v = float(self._s.get(k, 0))
            p.setPen(QColor(c["ST"]))
            p.drawText(mx, y, lw-6, bh, Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignRight, CRIT_LABELS.get(k, k))
            p.setBrush(QColor(c["OV"])); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(bx, y, bw, bh), 4, 4)
            fw = max(0, min(bw*v, bw))
            if fw > 0:
                col = c["TX"] if v > 0.7 else (c["ST"] if v < 0.3 else c["AC"])
                p.setBrush(QColor(col)); p.drawRoundedRect(QRectF(bx, y, fw, bh), 4, 4)
            p.setPen(QColor(c["TX"]))
            p.drawText(bx+bw+4, y, vw, bh, Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft, f"{v:.2f}")

class Filmstrip(QScrollArea):
    clicked = Signal(float)
    def __init__(self):
        super().__init__(); self.setFixedHeight(100); self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"QScrollArea{{background:{THEMES['dark']['OV']};border-radius:8px;border:none}}")
        self.ct = QWidget(); self.ly = QHBoxLayout(self.ct)
        self.ly.setContentsMargins(6,4,6,4); self.ly.setSpacing(4); self.setWidget(self.ct)
    def set_frames(self, fs):
        while self.ly.count():
            it = self.ly.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        for t, b in fs:
            if b is None or b.size == 0: continue
            cl = _FCell(t, b); cl.clicked.connect(self.clicked.emit); self.ly.addWidget(cl)

class _FCell(QFrame):
    clicked = Signal(float)
    def __init__(self, t, b):
        super().__init__(); self._t = t; self.setFixedSize(96, 84)
        self.setCursor(Qt.CursorShape.PointingHandCursor); self.setToolTip(fmt_t(t))
        ly = QVBoxLayout(self); ly.setContentsMargins(2,2,2,2)
        lb = QLabel(); lb.setPixmap(bgr2qpm(b).scaled(92, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        lb.setAlignment(Qt.AlignmentFlag.AlignCenter); ly.addWidget(lb)
        tl = QLabel(fmt_t(t)); tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl.setStyleSheet(f"color:{THEMES['dark']['TX']};background:{THEMES['dark']['SF']};border-radius:3px;padding:1px 4px;font-size:10px")
        ly.addWidget(tl); self._rs(False)
    def _rs(self, h):
        b = THEMES["dark"]["AC"] if h else "transparent"
        self.setStyleSheet(f"QFrame{{background:{THEMES['dark']['SF']};border:2px solid {b};border-radius:6px}}")
    def enterEvent(self, e): self._rs(True)
    def leaveEvent(self, e): self._rs(False)
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit(self._t)

class GCard(QFrame):
    clicked = Signal(int); star_tog = Signal(int); re_req = Signal(int); ms_tog = Signal(int, bool)
    def __init__(self, i, c, sz="Medium"):
        super().__init__(); self.i, self.c, self._sel, self._ms = i, c, False, False
        self._sz = sz if sz in CARD_SIZES else "Medium"; w, h = CARD_SIZES[self._sz]
        self.setFixedSize(w, h); self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx)
        ly = QVBoxLayout(self); ly.setContentsMargins(6,6,6,6); ly.setSpacing(4)
        self.im = QLabel(); f = c.ensure()
        if f is not None: self.im.setPixmap(TC.gal(id(c), f))
        self.im.setAlignment(Qt.AlignmentFlag.AlignCenter); self.im.setMinimumHeight(max(40, h-50))
        ly.addWidget(self.im, stretch=1)
        rw = QHBoxLayout(); rw.setContentsMargins(0,0,0,0); rw.setSpacing(4)
        tc = THEMES["dark"]["TX"] if c.score >= 0.7 else (THEMES["dark"]["AC"] if c.score >= 0.4 else THEMES["dark"]["ST"])
        rl = QLabel(f"#{i+1}"); rl.setStyleSheet(f"color:{tc};font-weight:bold;font-size:11px"); rw.addWidget(rl)
        tl = QLabel(fmt_t(c.timestamp)); tl.setStyleSheet(f"font-size:10px;color:{THEMES['dark']['ST']}"); rw.addWidget(tl)
        rw.addStretch()
        sl = QLabel(f"{c.score:.2f}"); sl.setStyleSheet(f"font-size:11px;font-weight:bold;color:{tc}"); rw.addWidget(sl)
        self.sb = QPushButton("☆"); self.sb.setFixedSize(22, 22); self.sb.setFlat(True)
        self.sb.setStyleSheet("font-size:14px;padding:0;margin:0")
        self.sb.clicked.connect(lambda: self.star_tog.emit(self.i)); rw.addWidget(self.sb)
        ly.addLayout(rw); self._rs()
    def _rs(self):
        c = THEMES["dark"]
        if self._sel: b, bg = c["TX"], c["SF"]
        elif self._ms: b, bg = c["AC"], c["SF"]
        elif self.c.starred: b, bg = c["TX"], c["SF"]
        else: b, bg = "transparent", c["CD"]
        self.setStyleSheet(f"QFrame{{background:{bg};border:2px solid {b};border-radius:8px}}QFrame:hover{{border-color:{c['AC']}}}")
    def set_sel(self, s):
        if self._sel != s: self._sel = s; self._rs()
    def set_ms(self, s):
        if self._ms != s: self._ms = s; self._rs()
    def ref_star(self):
        self.sb.setText("★" if self.c.starred else "☆"); self._rs()
    def ref_thumb(self):
        f = self.c.ensure()
        if f is not None: TC.inv(id(self.c)); self.im.setPixmap(TC.gal(id(self.c), f))
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if e.modifiers() & (Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier):
                self.ms_tog.emit(self.i, True)
            else: self.clicked.emit(self.i)
    def _ctx(self, pos):
        m = QMenu(self); a1 = m.addAction("Save frame…"); a2 = m.addAction("Copy to clipboard")
        a3 = m.addAction("Unstar" if self.c.starred else "Star"); m.addSeparator()
        a4 = m.addAction("Re-analyze ±2s"); act = m.exec(self.mapToGlobal(pos))
        if act == a1: self.clicked.emit(self.i)
        elif act == a2:
            f = self.c.ensure()
            if f is not None: QApplication.clipboard().setPixmap(bgr2qpm(f))
        elif act == a3: self.star_tog.emit(self.i)
        elif act == a4: self.re_req.emit(self.i)

class Heatmap(QWidget):
    clicked = Signal(int)
    def __init__(self):
        super().__init__(); self.setMinimumHeight(56); self.setMaximumHeight(56)
        self._cs, self._d, self._hi, self._si = [], 0.0, -1, -1; self.setMouseTracking(True)
    def set_data(self, cs, d): self._cs, self._d = list(cs), max(d, 0.001); self.update()
    def clear(self): self._cs, self._d = [], 0.0; self.update()
    def _cr(self, i):
        if not self._cs or i < 0 or i >= len(self._cs): return None
        c = self._cs[i]; w, h, m = self.width(), self.height(), 4
        bw, bh = w-2*m, h-2*m; xn = c.timestamp/self._d; cw = max(3, bw/max(len(self._cs), 1))
        x = m+xn*bw-cw/2; return QRectF(max(m, x), m, min(cw, bw), bh)
    def _ht(self, x, y):
        for i in range(len(self._cs)):
            r = self._cr(i)
            if r is not None and r.contains(x, y): return i
        return -1
    def paintEvent(self, e):
        p = QPainter(self); c = THEMES["dark"]; p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(c["CD"]))
        if not self._cs:
            p.setPen(QColor(c["ST"])); p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Run analysis"); return
        m, w, h = 4, self.width(), self.height()
        p.setPen(QPen(QColor(c["OV"]), 1)); p.drawLine(m, h-m, w-m, h-m)
        for i, cd in enumerate(self._cs):
            r = self._cr(i)
            if r is None: continue
            v = int(40+(212-40)*max(0, min(1, cd.score))); cl = QColor(v, v, v)
            if i == self._hi: cl = cl.lighter(130)
            p.setBrush(cl); p.setPen(Qt.PenStyle.NoPen); p.drawRoundedRect(r, 2, 2)
        if 0 <= self._si < len(self._cs):
            r = self._cr(self._si)
            if r is not None:
                p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(c["TX"]), 2))
                p.drawRoundedRect(r.adjusted(-1,-1,1,1), 3, 3)
    def mouseMoveEvent(self, e):
        i = self._ht(e.position().x(), e.position().y())
        if i != self._hi:
            self._hi = i
            if i >= 0:
                cd = self._cs[i]; self.setToolTip(f"#{i+1} {fmt_t(cd.timestamp)}\nScore: {cd.score:.3f}")
            else: self.setToolTip("")
            self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            i = self._ht(e.position().x(), e.position().y())
            if i >= 0: self.clicked.emit(i)
    def leaveEvent(self, e): self._hi = -1; self.update()
    def set_sel(self, i): self._si = i; self.update()

class EmptyOv(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self._m = "no_file"; self._cb = None
        ly = QVBoxLayout(self); ly.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ic = QLabel("🎬"); self._ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ic.setStyleSheet("font-size:64px"); ly.addWidget(self._ic)
        self._ti = QLabel("No Video Loaded"); self._ti.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ti.setStyleSheet(f"font-size:18px;font-weight:bold;color:{THEMES['dark']['TX']}"); ly.addWidget(self._ti)
        self._hi = QLabel("Open a video file (Ctrl+O)"); self._hi.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hi.setStyleSheet(f"color:{THEMES['dark']['ST']};font-size:12px"); ly.addWidget(self._hi)
        self._bt = QPushButton("  Open Video  "); self._bt.setObjectName("btnPrimary"); self._bt.setFixedWidth(160)
        br = QHBoxLayout(); br.addStretch(); br.addWidget(self._bt); br.addStretch(); ly.addLayout(br)
        self._uc()
    def set_cb(self, cb): self._cb = cb; self._bt.clicked.connect(cb)
    def set_mode(self, m): self._m = m; self._uc(); self.setVisible(m != "hidden")
    def _uc(self):
        if self._m == "no_file":
            self._ic.setText("🎬"); self._ti.setText("No Video Loaded")
            self._hi.setText("Open a video file (Ctrl+O)"); self._bt.setVisible(True)
        elif self._m == "no_analysis":
            self._ic.setText("🔍"); self._ti.setText("Ready to Analyze")
            self._hi.setText("Click Analyze to find thumbnails"); self._bt.setVisible(False)
        else: self._bt.setVisible(False)
    def paintEvent(self, e):
        bg = QColor(THEMES["dark"]["BG"]); bg.setAlpha(220)
        p = QPainter(self); p.fillRect(self.rect(), bg); p.end(); super().paintEvent(e)

# ── Dialogs ─────────────────────────────────────────────────────────────
class WeightsDlg(QDialog):
    def __init__(self, parent, name, w, existing):
        super().__init__(parent); self.setWindowTitle("Edit Profile"); self.setMinimumWidth(520)
        self._iw = dict(w); v = QVBoxLayout(self)
        rw = QHBoxLayout(); rw.addWidget(QLabel("Name:")); self.ne = QLineEdit(name)
        rw.addWidget(self.ne, stretch=1); v.addLayout(rw)
        bx = QGroupBox("Weights"); sg = QGridLayout(bx); self._sl, self._vl = {}, {}
        for i, k in enumerate(sorted(CRIT_LABELS.keys())):
            sg.addWidget(QLabel(CRIT_LABELS[k]), i, 0)
            s = QSlider(Qt.Orientation.Horizontal); s.setRange(0, 100)
            s.setValue(int(round(w.get(k, 0)*100))); s.valueChanged.connect(self._ch)
            sg.addWidget(s, i, 1); self._sl[k] = s
            vl = QLabel(f"{w.get(k, 0):.2f}"); sg.addWidget(vl, i, 2); self._vl[k] = vl
        v.addWidget(bx)
        bn = QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        bn.accepted.connect(self.accept); bn.rejected.connect(self.reject); v.addWidget(bn); self._ch()
    def _ch(self, *_):
        w = self.get_w()
        for k, s in self._sl.items(): self._vl[k].setText(f"{w.get(k, 0):.2f}")
    def get_w(self):
        r = {k: s.value()/100 for k, s in self._sl.items() if s.value() > 0}
        t = sum(r.values())
        return {k: 1/len(self._sl) for k in self._sl} if t == 0 else {k: v/t for k, v in r.items()}
    def get_name(self): return self.ne.text().strip() or "Custom"

class ShortcutsDlg(QDialog):
    def __init__(self, parent):
        super().__init__(parent); self.setWindowTitle("Shortcuts")
        v = QVBoxLayout(self)
        for sn, its in [("File", [("Ctrl+O","Open"), ("Ctrl+S","Save"), ("Ctrl+Shift+S","Save starred"), ("Ctrl+E","Contact sheet")]),
                        ("Nav", [("←/→","Prev/Next"), ("F2","Fit"), ("Ctrl+=/-","Zoom")]),
                        ("Analysis", [("Space","Run/Stop"), ("Esc","Stop"), ("F1","Help")])]:
            g = QGroupBox(sn); gl = QGridLayout(g)
            for i, (k, d) in enumerate(its): gl.addWidget(QLabel(k), i, 0); gl.addWidget(QLabel(d), i, 1)
            v.addWidget(g)
        b = QPushButton("Close"); b.setObjectName("btnPrimary"); b.clicked.connect(self.accept)
        v.addWidget(b, alignment=Qt.AlignmentFlag.AlignRight)

class AboutDlg(QDialog):
    def __init__(self, parent):
        super().__init__(parent); self.setWindowTitle("About")
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Video Thumbnail Picker v2.1"))
        v.addWidget(QLabel("Finds best frames using weighted metrics."))
        b = QPushButton("Close"); b.clicked.connect(self.accept); v.addWidget(b)

class ContactDlg(QDialog):
    def __init__(self, parent, cs, vn=""):
        super().__init__(parent); self.setWindowTitle("Contact Sheet"); self._cs, self._vn = cs, vn
        v = QVBoxLayout(self); bx = QGroupBox("Layout"); gl = QGridLayout(bx)
        gl.addWidget(QLabel("Cols:"), 0, 0); self.csp = QSpinBox(); self.csp.setRange(1, 10); self.csp.setValue(4)
        gl.addWidget(self.csp, 0, 1); self.cks = QCheckBox("Starred only"); gl.addWidget(self.cks, 1, 0, 1, 2)
        v.addWidget(bx)
        bn = QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        bn.accepted.connect(self._exp); bn.rejected.connect(self.reject); v.addWidget(bn)
    def _gs(self): return [c for c in self._cs if c.starred] if self.cks.isChecked() else list(self._cs)
    def _exp(self):
        cs = self._gs()
        if not cs: QMessageBox.information(self, "No frames", "No frames to export"); return
        p, _ = QFileDialog.getSaveFileName(self, "Save", f"contact_{self._vn}.png", "PNG (*.png)")
        if not p: return
        try:
            co, tw, th = self.csp.value(), 240, 135; ro = (len(cs)+co-1)//co
            sw, sh = co*tw+(co+1)*10, ro*th+(ro+1)*10+36
            sheet = Image.new("RGB", (sw, sh), (23,23,23))
            for i, c in enumerate(cs):
                f = c.ensure()
                if f is None: continue
                r, cl = i//co, i%co; x, y = 10+cl*(tw+10), 36+10+r*(th+10)
                rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
                sheet.paste(Image.fromarray(rgb).resize((tw, th), Image.Resampling.LANCZOS), (x, y))
            sheet.save(p, "PNG"); QMessageBox.information(self, "Exported", f"Saved to:\n{p}"); self.accept()
        except Exception as e: QMessageBox.critical(self, "Failed", str(e))

class PrefsDlg(QDialog):
    def __init__(self, parent, *, theme, card, tpl, af, q, fmt, rr, rs):
        super().__init__(parent); self.setWindowTitle("Preferences")
        v = QVBoxLayout(self); bx = QGroupBox("Appearance"); al = QVBoxLayout(bx)
        r1 = QHBoxLayout(); r1.addWidget(QLabel("Theme:"))
        self.ct = QComboBox(); self.ct.addItems(["dark","light"]); self.ct.setCurrentText(theme)
        r1.addWidget(self.ct, stretch=1); al.addLayout(r1); v.addWidget(bx)
        bn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bn.rejected.connect(self.reject); bn.accepted.connect(self.accept); v.addWidget(bn)
    @property
    def theme(self): return self.ct.currentText()

def save_json(p, cs, vp, vi):
    data = {"v": 1, "video": vp, "info": vi,
            "cands": [{"t": round(c.timestamp,3), "s": round(c.score,6),
                       "bd": {k: round(float(v),6) for k,v in c.bd.items()},
                       "f": [list(f) for f in c.faces], "st": c.starred} for c in cs]}
    with open(p, "w") as f: json.dump(data, f, indent=2)

def load_json(p):
    with open(p) as f: data = json.load(f)
    vp, vi = data.get("video",""), data.get("info",{})
    cs = [Cand(None, float(d["t"]), float(d["s"]), {k:float(v) for k,v in d.get("bd",{}).items()},
               [tuple(f) for f in d.get("f",[])], bool(d.get("st",False)), vp) for d in data.get("cands",[])]
    return cs, vp, vi

# ── Main Window ─────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Video Thumbnail Picker")
        self.resize(1600, 950); self.setMinimumSize(1200, 720); self.setAcceptDrops(True)
        self.vp, self.vi, self.cs, self.si = None, {}, [], -1
        self._w, self._sso, self._st = None, False, 0.0
        self._gc, self._ap, self._am = {}, {}, False
        self._ast, self._et = 0.0, QTimer(self); self._et.timeout.connect(self._uet)
        self._csz, self._th = "Medium", "dark"; self._tpl, self._af = "thumb_{timestamp}.jpg", False
        self._ms = set(); self._ui(); self._mb(); self._tb(); self._sc()
        self.setStyleSheet(ss(THEMES[self._th])); self._rs()
    def _ui(self):
        ct = QWidget(); self.setCentralWidget(ct); rt = QVBoxLayout(ct)
        rt.setContentsMargins(8,4,8,8); rt.setSpacing(8)
        hd = QFrame(); hd.setObjectName("Card"); hl = QHBoxLayout(hd)
        ti = QLabel("Video Thumbnail Picker"); ti.setObjectName("title"); hl.addWidget(ti); hl.addStretch()
        self.hfl = QLabel("No file"); self.hfl.setStyleSheet(f"color:{THEMES['dark']['ST']};font-size:11px"); hl.addWidget(self.hfl)
        rt.addWidget(hd)
        self._sp = QSplitter(Qt.Orientation.Horizontal); self._sp.setHandleWidth(6); rt.addWidget(self._sp, stretch=1)
        lw = QWidget(); ll = QVBoxLayout(lw); ll.setContentsMargins(0,0,0,0); ll.setSpacing(8)
        self.pc = QFrame(); self.pc.setStyleSheet(f"background:{THEMES['dark']['CD']};border-radius:8px")
        pl = QVBoxLayout(self.pc); pl.setContentsMargins(0,0,0,0)
        self.pv = Preview(); self.pv.setMinimumHeight(420); pl.addWidget(self.pv)
        self.eo = EmptyOv(self.pc); self.eo.set_cb(self._of); pl.addWidget(self.eo)
        ll.addWidget(self.pc, stretch=1)
        self.fs = Filmstrip(); self.fs.clicked.connect(self._skt); ll.addWidget(self.fs)
        self.hm = Heatmap(); self.hm.clicked.connect(self._sel); ll.addWidget(self.hm)
        self._sp.addWidget(lw)
        rw = QWidget(); rw.setMaximumWidth(520); rl = QVBoxLayout(rw)
        rl.setContentsMargins(0,0,0,0); rl.setSpacing(10); rl.addWidget(self._bcc())
        self.tb = QTabWidget(); self.tb.setDocumentMode()
        self._bgt(); self._bat(); self._bit(); rl.addWidget(self.tb, stretch=1)
        self._sp.addWidget(rw); self._sp.setStretchFactor(0, 3); self._sp.setStretchFactor(1, 1)
        self._sp.setSizes([1000, 520])
        self.ssl = QLabel("Ready"); self.statusBar().addWidget(self.ssl, 1)
        self.sel = QLabel(""); self.statusBar().addWidget(self.sel)
        self.scl = QLabel("0 cands"); self.statusBar().addPermanentWidget(self.scl)
        self.pb = QProgressBar(); self.pb.setFixedWidth(240); self.pb.setVisible(False)
        self.pb.setFormat("%p%"); self.statusBar().addPermanentWidget(self.pb)
    def _bcc(self):
        cd = QFrame(); cd.setObjectName("Card"); v = QVBoxLayout(cd)
        r1 = QHBoxLayout(); r1.addWidget(QLabel("Algorithm"))
        self.ca = QComboBox(); self.ca.currentTextChanged.connect(self._cha); r1.addWidget(self.ca, stretch=1)
        self.bew = QPushButton("Edit…"); self.bew.clicked.connect(self._ew); r1.addWidget(self.bew); v.addLayout(r1)
        r2 = QHBoxLayout(); r2.addWidget(QLabel("Output"))
        self.cp = QComboBox(); self.cp.addItems(PRESETS.keys()); r2.addWidget(self.cp, stretch=1); v.addLayout(r2)
        r3 = QHBoxLayout(); self.csc = QCheckBox("Scene"); r3.addWidget(self.csc)
        r3.addWidget(QLabel("Samples:")); self.sps = QSpinBox(); self.sps.setRange(20, 400); self.sps.setValue(80)
        r3.addWidget(self.sps); r3.addWidget(QLabel("Max:")); self.spc = QSpinBox()
        self.spc.setRange(4, 60); self.spc.setValue(15); r3.addWidget(self.spc); r3.addStretch(); v.addLayout(r3)
        r4 = QHBoxLayout(); self.bsv = QPushButton("  Save Selected  "); self.bsv.setObjectName("btnPrimary")
        self.bsv.clicked.connect(self._sv); r4.addWidget(self.bsv, stretch=1)
        self.bbs = QPushButton("  Save Starred  "); self.bbs.clicked.connect(self._bsv); r4.addWidget(self.bbs, stretch=1)
        v.addLayout(r4); return cd
    def _bgt(self):
        tb = QWidget(); ly = QVBoxLayout(tb)
        fr = QHBoxLayout(); self.cks = QCheckBox("Starred only"); self.cks.stateChanged.connect(self._ofc)
        fr.addWidget(self.cks); fr.addStretch(); fr.addWidget(QLabel("Sort:"))
        self.cso = QComboBox()
        for n,_,_ in SORT_OPTS: self.cso.addItem(n)
        self.cso.currentTextChanged.connect(self._osc); fr.addWidget(self.cso); ly.addLayout(fr)
        fr2 = QHBoxLayout(); fr2.addWidget(QLabel("Min:"))
        self.tsl = QSlider(Qt.Orientation.Horizontal); self.tsl.setRange(0, 100)
        self.tsl.valueChanged.connect(self._otc); fr2.addWidget(self.tsl, stretch=1)
        self.tlb = QLabel("0.00"); fr2.addWidget(self.tlb); ly.addLayout(fr2)
        self.ga = QScrollArea(); self.ga.setWidgetResizable(True)
        self.ga.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.gct = QWidget(); self.gly = QGridLayout(self.gct)
        self.gly.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignLeft)
        self.ga.setWidget(self.gct); ly.addWidget(self.ga, stretch=1)
        self.tb.addTab(tb, "Gallery")
    def _bat(self):
        tb = QWidget(); ly = QVBoxLayout(tb)
        ly.addWidget(QLabel("RGB Histogram")); self.hw = HistW(); ly.addWidget(self.hw)
        ly.addWidget(QLabel("Score Breakdown")); self.bw = ScoreW(); ly.addWidget(self.bw, stretch=1)
        self.tb.addTab(tb, "Analysis")
    def _bit(self):
        tb = QWidget(); ly = QVBoxLayout(tb)
        ly.addWidget(QLabel("VIDEO")); self.ivg = self._big([("File",""),("Duration",""),("Resolution",""),("FPS",""),("Frames","")])
        ly.addWidget(self.ivg); ly.addWidget(QLabel("CANDIDATE"))
        self.icg = self._big([("Rank","—"),("Time","—"),("Score","—"),("Faces","—"),
                              ("Sharp","—"),("Contr","—"),("Bright","—"),("Compos","—")])
        ly.addWidget(self.icg); ly.addStretch(); self.tb.addTab(tb, "Info")
    def _big(self, rows):
        fr = QFrame(); fr.setStyleSheet(f"QFrame{{background:{THEMES['dark']['CD']};border-radius:6px}}")
        gr = QGridLayout(fr)
        for i, (l, v) in enumerate(rows):
            ll = QLabel(l); ll.setStyleSheet(f"color:{THEMES['dark']['ST']};font-size:11px")
            vl = QLabel(v); vl.setStyleSheet(f"color:{THEMES['dark']['TX']};font-size:11px")
            gr.addWidget(ll, i, 0); gr.addWidget(vl, i, 1)
            setattr(self, f"_i_{l.lower()}", vl)
        return fr
    def _mb(self):
        mb = self.menuBar(); fm = mb.addMenu("&File")
        self.ao = QAction("&Open…", self); self.ao.setShortcut("Ctrl+O"); self.ao.triggered.connect(self._of)
        fm.addAction(self.ao)
        self.aq = QAction("&Quit", self); self.aq.setShortcut("Ctrl+Q"); self.aq.triggered.connect(self.close)
        fm.addAction(self.aq)
        em = mb.addMenu("&Edit"); self.aew = QAction("Edit &Weights…", self)
        self.aew.triggered.connect(self._ew); em.addAction(self.aew)
        vm = mb.addMenu("&View")
        self.ag = QAction("&Grid", self, checkable=True); self.ag.setShortcut("G")
        self.ag.triggered.connect(lambda: self.pv.set_ov(grid=self.ag.isChecked())); vm.addAction(self.ag)
        self.af = QAction("&Faces", self, checkable=True); self.af.setShortcut("F")
        self.af.triggered.connect(lambda: self.pv.set_ov(faces=self.af.isChecked())); vm.addAction(self.af)
        hm = mb.addMenu("&Help")
        self.ash = QAction("&Shortcuts", self); self.ash.setShortcut("F1")
        self.ash.triggered.connect(lambda: ShortcutsDlg(self).exec()); hm.addAction(self.ash)
        self.aab = QAction("&About", self); self.aab.triggered.connect(lambda: AboutDlg(self).exec()); hm.addAction(self.aab)
    def _tb(self):
        tb = QToolBar("Main"); tb.setMovable(False); self.addToolBar(tb)
        self.bo = QPushButton("  Open"); self.bo.setObjectName("btnPrimary"); self.bo.clicked.connect(self._of); tb.addWidget(self.bo)
        self.ba = QPushButton("  Analyze"); self.ba.setEnabled(False); self.ba.clicked.connect(self._sa); tb.addWidget(self.ba)
        self.bt = QPushButton("  Stop"); self.bt.setVisible(False); self.bt.clicked.connect(self._sta); tb.addWidget(self.bt)
        sp = QWidget(); sp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred); tb.addWidget(sp)
    def _sc(self):
        QShortcut(QKeySequence("Ctrl+S"), self, self._sv)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self._bsv)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self._nv(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self._nv(1))
        QShortcut(QKeySequence("Ctrl+="), self, self.pv.zi)
        QShortcut(QKeySequence("Ctrl+-"), self, self.pv.zo)
        QShortcut(QKeySequence("Ctrl+0"), self, self.pv.fit)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._ta)
        QShortcut(QKeySequence(Qt.Key.Key_S), self, self._scu)
        QShortcut(QKeySequence(Qt.Key.Key_G), self, lambda: self.ag.toggle())
        QShortcut(QKeySequence(Qt.Key.Key_F), self, lambda: self.af.toggle())
        QShortcut(QKeySequence("Escape"), self, self._sta)
    def _rs(self):
        S.restore_win(self); sz = S.sp_sizes()
        if sz and len(sz) == 2: self._sp.setSizes(sz)
        s = S.load_ana(); self._ap = dict(ALGO_PROFILES); self._ap.update(S.profiles)
        self.ca.blockSignals(True); self.ca.clear()
        for n in self._ap: self.ca.addItem(n)
        if s["algo"] in self._ap: self.ca.setCurrentText(s["algo"])
        self.ca.blockSignals(False)
        if s["preset"] in PRESETS: self.cp.setCurrentText(s["preset"])
        self.sps.setValue(s["samples"]); self.spc.setValue(s["cands"]); self.csc.setChecked(s["scene"])
        if any(s["sort"] == n for n,_,_ in SORT_OPTS): self.cso.setCurrentText(s["sort"])
        self._st = s["thr"]; self.tsl.setValue(int(s["thr"]*100)); self.tlb.setText(f"{s['thr']:.2f}")
    def _ss(self):
        S.save_win(self); S.save_ana(algo=self.ca.currentText(), preset=self.cp.currentText(),
            samples=self.sps.value(), cands=self.spc.value(), scene=self.csc.isChecked(),
            sort=self.cso.currentText(), thr=self._st); S.sync()
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            for u in e.mimeData().urls():
                if Path(u.toLocalFile()).suffix.lower() in VIDEO_EXTS: e.acceptProposedAction(); return
        e.ignore()
    def dropEvent(self, e):
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if Path(p).suffix.lower() in VIDEO_EXTS: self._ofp(p); e.acceptProposedAction(); return
        e.ignore()
    def _of(self):
        p, _ = QFileDialog.getOpenFileName(self, "Open", S.last_dir,
            "Video (*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.flv *.wmv);;All (*)")
        if p: self._ofp(p)
    def _ofp(self, p):
        if not Path(p).exists(): QMessageBox.warning(self, "Not found", p); return
        self.vp = p; self.hfl.setText(Path(p).name); self.ba.setEnabled(True)
        S.add_recent(p); S.last_dir = str(Path(p).parent)
        self.cs.clear(); self._gc.clear(); TC.inv(); self.si = -1; self._ms.clear()
        self._rg(); self.fs.set_frames([]); self.hm.clear(); self.pv.scene().clear()
        self.eo.set_mode("no_analysis")
    def _ta(self):
        if self._w and self._w.isRunning(): self._sta()
        else: self._sa()
    def _sa(self, ap=False, ov=None):
        if not self.vp: return
        self._am = ap
        if not ap:
            self.cs.clear(); self._gc.clear(); TC.inv(); self.si = -1; self._rg()
        else: self._gc.clear()
        self.pb.setVisible(True); self.pb.setValue(0); self.ssl.setText("Init…")
        self.ba.setVisible(False); self.bt.setVisible(True); self.bo.setEnabled(False)
        self.eo.set_mode("hidden"); self._ast = time.monotonic(); self._et.start(ETA_MS)
        w = self._ap.get(self.ca.currentText(), ALGO_PROFILES["General"])
        self._w = AnaThread(self.vp, self.sps.value(), w, self.spc.value(),
                           self.csc.isChecked(), ov=ov, sf=ap)
        self._w.stage.connect(lambda t: self.ssl.setText(t))
        self._w.progress.connect(lambda c,t: self.pb.setValue(int(100*c/t)) if t > 0 else None)
        self._w.cand_ready.connect(lambda c,_,__: QTimer.singleShot(0, lambda cc=c: self._acm(cc)))
        self._w.film_ready.connect(lambda fs: self.fs.set_frames(fs) if fs else None)
        self._w.ok.connect(self._fa); self._w.err.connect(lambda m: (self._fa([],{}), QMessageBox.critical(self,"Err",m)))
        self._w.start()
    def _sta(self):
        if self._w and self._w.isRunning(): self._w.abort(); self._w.wait(1500)
        self._fa([], {})
    def _uet(self):
        if not self._ast: return
        el = time.monotonic()-self._ast; pc = self.pb.value()
        if pc > 0:
            te = el/(pc/100); et = max(0, te-el)
            self.sel.setText(f"⏱ {int(el)}s / ~{int(et)}s")
        else: self.sel.setText(f"⏱ {int(el)}s")
    def _acm(self, c):
        self.cs.append(c); self.scl.setText(f"{len(self.cs)} cands"); self._mc(c)
        if self.si < 0: self._sel(0)
    def _fa(self, cs, info):
        self._et.stop(); self.sel.setText("")
        if self._am:
            if cs: self.cs.extend(cs)
            self._asrt(); self._ass()
        else:
            if cs: self.cs = cs; self._gc.clear(); TC.inv()
            if info: self.vi = info; self._riv(info)
            self._ass()
        self.pb.setVisible(False); self.bt.setVisible(False); self.ba.setVisible(True); self.bo.setEnabled(True)
        self.ssl.setText("Done"); self._rg(); self.scl.setText(f"{len(self.cs)} cands")
        if self.cs: self._sel(0)
        else: self.eo.set_mode("no_analysis")
    def _ass(self):
        if not self.vp: return
        d = Sidecar.load(self.vp); sts = d.get("starred", [])
        if not sts: return
        for c in self.cs:
            if any(abs(c.timestamp-ts) < 0.05 for ts in sts): c.starred = True
    def _svs(self):
        if self.vp and self.cs: Sidecar.save(self.vp, self.cs)
    def _mc(self, c):
        if id(c) in self._gc: return self._gc[id(c)]
        try: ri = self.cs.index(c)
        except ValueError: return None
        cd = GCard(ri, c, self._csz); cd.clicked.connect(self._sel); cd.star_tog.connect(self._ts)
        cd.re_req.connect(self._ri); cd.ms_tog.connect(self._omt)
        if id(c) in self._ms: cd.set_ms(True)
        self._gc[id(c)] = cd; return cd
    def _asrt(self):
        if not self.cs: return
        sn = self.cso.currentText()
        for n, k, r in SORT_OPTS:
            if n == sn:
                if k is None: self.cs.sort(key=lambda c: c.score, reverse=r)
                elif k == "__starred__": self.cs.sort(key=lambda c: (not c.starred, -c.score))
                else: self.cs.sort(key=lambda c: c.bd.get(k, 0) if k != "timestamp" else c.timestamp, reverse=r)
                break
    def _rg(self):
        while self.gly.count():
            it = self.gly.takeAt(0)
            if it.widget(): it.widget().setParent(None)
        self._asrt(); d = list(self.cs)
        if self._sso: d = [c for c in d if c.starred]
        if self._st > 0: d = [c for c in d if c.score >= self._st]
        itp = {id(c): i for i, c in enumerate(self.cs)}
        for i, c in enumerate(d):
            cd = self._gc.get(id(c)) or self._mc(c)
            if cd is None: continue
            ri = itp.get(id(c), -1)
            if ri < 0: continue
            cd.i = ri; cd.set_sel(ri == self.si); cd.ref_star()
            cd.set_ms(id(c) in self._ms); cd.setParent(self.gct)
            self.gly.addWidget(cd, i//GALLERY_COLS, i%GALLERY_COLS)
        self.hm.set_data(self.cs, self.vi.get("duration", 0)); self.hm.set_sel(self.si)
    def _ofc(self, _): self._sso = self.cks.isChecked(); self._rg()
    def _osc(self, _): self._gc.clear(); self._rg()
    def _otc(self, v): self._st = v/100; self.tlb.setText(f"{self._st:.2f}"); self._rg()
    def _sel(self, i):
        if i < 0 or i >= len(self.cs): return
        pv = self.si; self.si = i; c = self.cs[i]; f = c.ensure()
        if f is None: return
        rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB); pi = Image.fromarray(rgb)
        pr = PRESETS.get(self.cp.currentText())
        if pr: pi = fit_crop(pi, pr)
        da = pi.tobytes("raw", "RGB")
        qi = QImage(da, pi.width, pi.height, 3*pi.width, QImage.Format.Format_RGB888); qi._buf = da
        self.pv.set_pm(QPixmap.fromImage(qi), c); self.eo.set_mode("hidden")
        self.hw.set_data(f); self.bw.set_scores(c.bd); self._ric(c); self.hm.set_sel(i)
        if pv != i:
            if 0 <= pv < len(self.cs):
                pc = self._gc.get(id(self.cs[pv]))
                if pc: pc.set_sel(False)
            cc = self._gc.get(id(c))
            if cc: cc.set_sel(True)
    def _ts(self, i):
        if 0 <= i < len(self.cs):
            self.cs[i].starred = not self.cs[i].starred
            cd = self._gc.get(id(self.cs[i]))
            if cd: cd.ref_star()
            if self._sso and not self.cs[i].starred: self._rg()
            self._svs()
    def _scu(self):
        if 0 <= self.si < len(self.cs): self._ts(self.si)
    def _nv(self, d):
        if not self.cs: return
        self._sel((self.si+d)%len(self.cs))
    def _skt(self, ts):
        if not self.vp: return
        cap = cv2.VideoCapture(self.vp)
        try: cap.set(cv2.CAP_PROP_POS_MSEC, ts*1000); r, f = cap.read()
        finally: cap.release()
        if not r or f is None: return
        if not prefilter(f): return
        w = self._ap.get(self.ca.currentText(), ALGO_PROFILES["General"])
        fs, faces = s_faces(f); sm, gr = downscale(f, 720)
        sc = {n: s(sm, gr) for n, s in SCORERS.items()}; sc["faces"] = fs
        tot = sum(sc.get(k,0)*w.get(k,0) for k in w)
        c = Cand(f, float(ts), tot, sc, faces, video=self.vp)
        self.cs.insert(0, c); self._rg(); self._sel(0)
    def _ri(self, i):
        if i < 0 or i >= len(self.cs): return
        c = self.cs[i]; ct = c.timestamp; rd = S.re_radius; n = S.re_samples
        ts = list(np.linspace(max(0, ct-rd), ct+rd, n)); self._sa(ap=True, ov=ts)
    def _riv(self, info):
        if not info: return
        p = info.get("path", ""); self._i_file.setText(Path(p).name if p else "—")
        self._i_duration.setText(fmt_dur(info.get("duration", 0)))
        w, h = info.get("width"), info.get("height")
        self._i_resolution.setText(f"{w}×{h}" if w and h else "—")
        fps = info.get("fps"); self._i_fps.setText(f"{fps:.2f}" if fps else "—")
        tf = info.get("total_frames"); self._i_frames.setText(str(tf) if tf else "—")
    def _ric(self, c):
        ks = ["rank","time","score","faces","sharp","contr","bright","compos"]
        if c is None:
            for k in ks:
                a = getattr(self, f"_i_{k}", None)
                if a: a.setText("—")
            return
        b = c.bd; self._i_rank.setText(f"#{self.si+1}"); self._i_time.setText(fmt_t(c.timestamp))
        self._i_score.setText(f"{c.score:.3f}"); self._i_faces.setText(str(len(c.faces)))
        self._i_sharp.setText(f"{b.get('sharpness',0):.3f}"); self._i_contr.setText(f"{b.get('contrast',0):.3f}")
        self._i_bright.setText(f"{b.get('brightness',0):.3f}"); self._i_compos.setText(f"{b.get('composition',0):.3f}")
    def _cha(self, n):
        if not self.cs: return
        w = self._ap.get(n, ALGO_PROFILES["General"])
        for c in self.cs: c.score = sum(c.bd.get(k,0)*w.get(k,0) for k in w)
        self._asrt(); self._gc.clear(); self._rg()
        if 0 <= self.si < len(self.cs): self._sel(self.si)
    def _ew(self):
        n = self.ca.currentText(); w = self._ap.get(n, {})
        d = WeightsDlg(self, n, w, list(self._ap.keys()))
        if d.exec() == WeightsDlg.DialogCode.Accepted:
            nn, nw = d.get_name(), d.get_w(); self._ap[nn] = nw
            if nn not in ALGO_PROFILES: S.save_profile(nn, nw)
            self.ca.blockSignals(True)
            if self.ca.findText(nn) < 0: self.ca.addItem(nn)
            self.ca.setCurrentText(nn); self.ca.blockSignals(False); self._cha(nn)
    def _od(self):
        o = Path.cwd()/"thumbnails"; o.mkdir(parents=True, exist_ok=True); return o
    def _sv(self):
        if self.si < 0 or self.si >= len(self.cs): return
        c = self.cs[self.si]; od = self._od(); r = self.si+1
        fn = self._ffn(c, r); self._si2(c, str(od/fn))
    def _ffn(self, c, r):
        vn = Path(self.vp).stem if self.vp else "video"; pn = self.cp.currentText()
        try:
            return self._tpl.format(video=vn, timestamp=fmt_t(c.timestamp).replace(":","-"),
                ts_seconds=f"{c.timestamp:.3f}", score=f"{c.score:.3f}", rank=r, preset=pn)
        except: return f"thumb_{fmt_t(c.timestamp).replace(':','-')}.jpg"
    def _bsv(self):
        st = [c for c in self.cs if c.starred]
        if not st: QMessageBox.information(self, "Info", "No starred"); return
        fo = str(self._od())
        for i, c in enumerate(st, 1): self._si2(c, os.path.join(fo, self._ffn(c, i)))
    def _si2(self, c, p=None):
        f = c.ensure()
        if f is None: QMessageBox.critical(self, "Err", "No frame"); return
        pi = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        pr = PRESETS.get(self.cp.currentText())
        if pr: pi = fit_crop(pi, pr)
        if not p:
            r = self.si+1 if self.cs and c in self.cs else 1; p = str(self._od()/self._ffn(c, r))
        try:
            ex = Path(p).suffix.lower()
            if ex == ".png": pi.save(p, "PNG", optimize=True)
            elif ex == ".webp": pi.save(p, "WEBP", quality=S.quality)
            else: pi.save(p, "JPEG", quality=S.quality)
        except Exception as e: QMessageBox.critical(self, "Err", str(e))
    def _omt(self, i, _):
        if i < 0 or i >= len(self.cs): return
        c = self.cs[i]
        if id(c) in self._ms: self._ms.discard(id(c))
        else: self._ms.add(id(c))
        cd = self._gc.get(id(c))
        if cd: cd.set_ms(id(c) in self._ms)
    def closeEvent(self, e):
        self._ss(); self._svs()
        if self._w and self._w.isRunning(): self._w.abort(); self._w.wait(2000)
        super().closeEvent(e)

def main():
    log.info("Init…"); app = QApplication(sys.argv)
    app.setOrganizationName("VTP"); app.setApplicationName("Video Thumbnail Picker")
    try: cascades()
    except Exception as e: log.warning(f"Cascades: {e}")
    w = MainWindow(); w.show(); log.info("Ready"); return app.exec()

if __name__ == "__main__": sys.exit(main())