"""
Export ANSI-coloured ASCII frames to a self-contained HTML page.
The page preserves colours and includes play/pause/seek controls.

Usage:
    from ascii_html import write_html

    write_html(frames, fps=30, "output.html")
"""

from __future__ import print_function

import html as html_mod
import re

# Regex to match ANSI escape sequences used by sty
_ANSI_RE = re.compile(r'\x1b\[([\d;]*)m')


def _ansi_to_html(text):
    """
    Convert a string with ANSI colour codes to HTML with inline styles.

    Handles the subset of ANSI codes emitted by ``sty``:
      ``\\x1b[38;2;R;G;Bm``  — 24-bit foreground
      ``\\x1b[48;2;R;G;Bm``  — 24-bit background
      ``\\x1b[39m`` / ``\\x1b[49m`` / ``\\x1b[0m``  — reset
      ``\\x1b[1m`` (bold), ``\\x1b[4m`` (underline),
      ``\\x1b[91m``–``\\x1b[96m`` (bright ANSI colours)
    """
    parts = []
    pos = 0
    span_open = False

    for m in _ANSI_RE.finditer(text):
        # Emit text before this escape
        if m.start() > pos:
            parts.append(html_mod.escape(text[pos:m.start()]))

        code = m.group(1)
        pos = m.end()

        # Reset
        if code in ("0", "", "39", "49"):
            if span_open:
                parts.append("</span>")
                span_open = False
            continue

        # Bold / underline — use <strong>/<u> for semantic HTML
        if code == "1":
            parts.append("<strong>")
            continue
        if code == "4":
            parts.append("<u>")
            continue

        # Bright ANSI colours (used by sty for fg.rs / bg.rs fallbacks)
        bright_fg = {
            "91": "255;85;85", "92": "85;255;85", "93": "255;255;85",
            "94": "85;85;255", "95": "255;85;255", "96": "85;255;255",
        }
        if code in bright_fg:
            if span_open:
                parts.append("</span>")
            rgb = bright_fg[code]
            parts.append(f'<span style="color:rgb({rgb})">')
            span_open = True
            continue

        # 24-bit foreground
        if code.startswith("38;2;"):
            try:
                _, _, r, g, b = code.split(";")
                if span_open:
                    parts.append("</span>")
                parts.append(f'<span style="color:rgb({r},{g},{b})">')
                span_open = True
            except ValueError:
                pass
            continue

        # 24-bit background
        if code.startswith("48;2;"):
            try:
                _, _, r, g, b = code.split(";")
                if span_open:
                    parts.append("</span>")
                parts.append(f'<span style="background:rgb({r},{g},{b})">')
                span_open = True
            except ValueError:
                pass
            continue

    # Remaining text
    if pos < len(text):
        parts.append(html_mod.escape(text[pos:]))

    if span_open:
        parts.append("</span>")

    return "".join(parts)


def _build_html(frames, fps):
    """Build a complete HTML page from a list of ANSI-coloured frame strings."""
    total = len(frames)
    if total == 0:
        return "<html><body><p>No frames.</p></body></html>"

    frame_divs = []
    for i, ansi_text in enumerate(frames):
        active = " active" if i == 0 else ""
        html_content = _ansi_to_html(ansi_text)
        frame_divs.append(
            f'<pre class="frame{active}" id="f{i}">{html_content}</pre>'
        )

    frames_joined = "\n".join(frame_divs)
    delay_ms = int(1000 / fps)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ASCII Video — {total} frames @ {fps}fps</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#000; display:flex; justify-content:center;
       align-items:center; min-height:100vh;
       font-family:"Courier New","Consolas","Liberation Mono",monospace; }}
#player {{ background:#000; padding:20px; border-radius:8px; }}
pre {{ color:#fff; line-height:1.1; font-size:13px; white-space:pre; }}
.frame {{ display:none; }}
.frame.active {{ display:block; }}
#controls {{ text-align:center; margin-top:16px; color:#888;
             font-family:sans-serif; font-size:13px; }}
#controls button {{ background:#333; color:#fff; border:1px solid #555;
                    padding:5px 14px; margin:0 3px; cursor:pointer;
                    border-radius:4px; font-size:13px; }}
#controls button:hover {{ background:#555; }}
#controls button:active {{ background:#777; }}
#controls .info {{ margin-left:10px; }}
</style>
</head>
<body>
<div id="player">
{frames_joined}
<div id="controls">
<button id="playBtn">⏸</button>
<button id="prevBtn">⏮</button>
<button id="nextBtn">⏭</button>
<span class="info" id="frameInfo">1 / {total}</span>
</div>
</div>
<script>
(function() {{
const frames = document.querySelectorAll(".frame");
const total = frames.length;
let current = 0;
let playing = true;
let timer = null;
const delay = {delay_ms};

function showFrame(idx) {{
  frames.forEach((f, i) => f.classList.toggle("active", i === idx));
  document.getElementById("frameInfo").textContent = (idx + 1) + " / " + total;
}}

function play() {{
  if (timer) clearInterval(timer);
  timer = setInterval(function() {{
    if (!playing) return;
    current = (current + 1) % total;
    showFrame(current);
  }}, delay);
}}

document.getElementById("playBtn").onclick = function() {{
  playing = !playing;
  this.textContent = playing ? "⏸" : "▶";
  if (playing) play();
}};

document.getElementById("prevBtn").onclick = function() {{
  current = (current - 1 + total) % total;
  showFrame(current);
}};

document.getElementById("nextBtn").onclick = function() {{
  current = (current + 1) % total;
  showFrame(current);
}};

document.addEventListener("keydown", function(e) {{
  if (e.key === " ") {{ e.preventDefault(); document.getElementById("playBtn").click(); }}
  if (e.key === "ArrowLeft") {{ document.getElementById("prevBtn").click(); }}
  if (e.key === "ArrowRight") {{ document.getElementById("nextBtn").click(); }}
}});

showFrame(0);
play();
}})();
</script>
</body>
</html>"""


def write_html(frames, fps, path):
    """Write an HTML page of the ASCII animation to *path*.

    Args:
        frames: list of ANSI-coloured frame strings (one per frame)
        fps: frames per second for playback timing
        path: output file path
    """
    html = _build_html(frames, fps)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
