# Video To ASCII

A Python generator that converts YouTube videos or local video files to
coloured ASCII art in your terminal.

## Features

- **YouTube & local files** — paste a URL or point at a local MP4/AVI/etc.
- **HTML export** — `--export-html output.html` saves the ASCII animation as a
  self-contained web page you can share with anyone.
- **Discover charsets** — `--list-charsets` prints available character sets and
  exits.
- **Loop playback** — `--loop` for infinite replay, `--loop N` to repeat N times
- **Skip intro** — `--no-intro` bypasses the 3-2-1 countdown
- **Full-screen** — automatically adapts to your terminal size.
- **Cross-platform audio** — macOS (`afplay`), Linux (`ffplay`/`aplay`/`paplay`),
  Windows (`ffplay`).
- **Interactive controls** — **Space** to pause, **Q** to quit,
  **Left/Right arrows** to seek during playback.
- **Real-time progress bar** — shows `[====>.......]` with frame counter
  and elapsed/duration time.
- **Speed control** — `--speed 0.5` for slow-motion, `--speed 2` to double
  the playback rate.
- **Multiple character sets** — `standard`, `compact`, `minimal`.
- **Video mode** — background-coloured blocks for more vibrant output.
- **Smooth playback** — ANSI escape codes prevent flickering.
- **Live screen capture** — render your desktop (or a region) as ASCII in
  real time.

## Installation

```bash
git clone <repo>
cd video-to-ascii
uv venv && uv pip install -r requirements.txt
```

Or with plain pip:

```bash
pip3 install -r requirements.txt
```

## Usage

### Play a YouTube video

```bash
uv run python3 video_render.py "https://youtube.com/watch?v=..."
```

### Play a local video file

```bash
uv run python3 video_render.py /path/to/video.mp4
```

### Loop playback

```bash
# Infinite loop
uv run python3 video_render.py video.mp4 --loop

# Play 3 times
uv run python3 video_render.py video.mp4 --loop 3
```

### Skip countdown

```bash
uv run python3 video_render.py video.mp4 --no-intro
```

### Check version

```bash
uv run python3 video_render.py --version
```

### Interactive CLI

```bash
uv run python3 ascii.py
```

### Options

| Flag | Description |
|---|---|
| `--video-mode` | Use background-coloured blocks (more vibrant) |
| `--chars` | Character set: `standard`, `compact`, `minimal` |
| `--speed` | Playback speed multiplier (e.g. `0.5`, `2.0`) |
| `--no-audio` | Disable audio playback |
| `--buffer` | Pre-buffer fraction (0–1) before starting |
| `--width`, `--height` | Override output size in character cells |
| `--framerate` | Target framerate |
| `--list-charsets` | List available character sets and exit |
| `--export-html FILE` | Save the ASCII animation as a shareable HTML file |
| `--loop` | Loop playback: `--loop` = infinite, `--loop N` = N times |
| `--no-intro` | Skip the 3-2-1 countdown before playback |
| `--version` | Show version number and exit |

### Live screen capture

```bash
uv run python3 live_render.py
```
(Toggle video mode with Right Shift.)

### Interactive controls during playback

| Key | Action |
|---|---|
| **Space** | Pause / resume |
| **Q** | Quit |
| **← / →** | Seek backward / forward ~5 seconds |

## How it works

1. Video is downloaded (YouTube) or opened (local file) via OpenCV.
2. Each frame is resized to fit your terminal, then every pixel is mapped
   to an ASCII character based on brightness.
3. Characters are coloured with ANSI true-colour escape codes matching
   the original pixel colour (or background-coloured in video mode).
4. Frames are printed at the video's native framerate using `\033[H`
   to overwrite in place — no flickering or scrolling.
5. Audio plays in a background process synced to the video duration.

## Requirements

- Python 3.9+
- `uv` or `pip` for dependencies
- macOS, Linux, or Windows terminal with true-colour ANSI support
