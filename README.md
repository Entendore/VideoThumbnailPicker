# Video Thumbnail Picker

A PySide6 desktop application that scans a video file, scores sample frames
using a weighted set of image-quality metrics, and lets you pick the best
frame for use as a thumbnail.

## Quick start

```bash
pip install PySide6 opencv-python numpy pillow
python app.py
```

## Keyboard shortcuts

| Shortcut       | Action                  |
|----------------|-------------------------|
| `Ctrl+O`       | Open video              |
| `Ctrl+S`       | Save selected frame     |
| `Ctrl+Shift+S` | Save all starred frames |
| `Ctrl+J`       | Load candidate list     |
| `Ctrl+Shift+J` | Save candidate list     |
| `Ctrl+E`       | Export contact sheet    |
| `Ctrl+Q`       | Quit                    |
| `Ctrl+T`       | Toggle theme            |
| `Ctrl+M`       | Free memory             |
| `Ctrl+,`       | Preferences             |
| `←` / `→`      | Previous / next frame   |
| `F2`           | Fit to view             |
| `Ctrl+=` / `Ctrl+-` | Zoom in / out       |
| `Ctrl+0`       | Reset zoom to fit       |
| `G`            | Toggle grid overlay     |
| `F`            | Toggle face overlay     |
| `Space`        | Run / stop analysis     |
| `Esc`          | Clear multi-select / stop analysis |
| `S`            | Star / unstar current   |
| `R`            | Re-analyze ±2s          |
| `Ctrl+Space`   | Auto-select best        |
| `F1`           | Show shortcut help      |

## Algorithm profiles

Four built-in weight profiles are defined in `config.py`:

- **General (Balanced)** — default all-rounder
- **Face Focus (Portrait)** — boosts face/skin/center weight
- **Scenery (Landscape)** — composition, color harmony, dynamic range
- **Action (Motion)** — motion, sharpness, contrast

You can also create **custom profiles** via `Edit ▶ Edit Algorithm Weights…`.
Custom profiles are saved to QSettings and persist across sessions.

## Customising

- Tune `SCORING_MAX_DIMENSION` in `config.py` to trade accuracy for speed.
- Add new output presets to the `PRESETS` dict in `config.py`.
- Tweak `ANALYSIS_BATCH_INTERVAL_MS` to control UI update frequency.
- Adjust `REANALYZE_RADIUS_SEC` and `REANALYZE_SAMPLES` to control the
  re-analyze neighborhood window.
- Add new scorers in `analysis.py` and register them in `SCORERS`, then
  weight them via the Weights Editor dialog.
- Add sort criteria by extending `SORT_OPTIONS` in `config.py`.

## Project sidecar files

When you star candidates, a `<video_name>.vtp.json` file is created next
to the video. This file stores the timestamps of starred frames so they
can be restored when you reopen the video. The file is safe to delete or
share alongside the video.
