"""
Live screen-capture renderer for video-to-ascii.
Captures a region of the screen and renders it as coloured ASCII art
in real time in the terminal.
"""

from __future__ import print_function

import re
import shutil
import sys
import time
from datetime import datetime as dt
from threading import Lock, Thread
import cursor
try:
    import mss
except ImportError:
    print("Missing dependency: mss. Install with: uv pip install mss")
    sys.exit(1)
from PIL import Image
try:
    from pynput import keyboard
except ImportError:
    print("Missing dependency: pynput. Install with: uv pip install pynput")
    sys.exit(1)


from ascii_convert import convert_frame
from colours import Colours



_ANSI_STRIP_RE = re.compile(r'\x1b\[[0-9;]*m')
_last_terminal_size = (0, 0)

def _visible_length(s):
    """Return length of string without ANSI escape sequences."""
    return len(_ANSI_STRIP_RE.sub('', s))
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MONITOR = {"top": 0, "left": 0, "width": 1920, "height": 1080}
FRAMERATE = 30
SCALE_DIVISOR = 30       # Larger = smaller ASCII output (faster)

# ---------------------------------------------------------------------------
# Shared mutable state
# ---------------------------------------------------------------------------

stopped = False
watching_video = False   # Toggled with Right-Shift
_watching_video_lock = Lock()
_counter_lock = Lock()
fps_counter = 0
image_buffer = 0
reset = False
has_started = False
last_second = 0
start_time = None


def input_checker(key):
    """Toggle video mode on Right-Shift."""
    global watching_video
    if key == keyboard.Key.shift_r:
        with _watching_video_lock:
            watching_video = not watching_video


def timing_module():
    """Update the timing state every second."""
    global stopped, reset, last_second, has_started, start_time

    last_second = 0
    start_time = dt.now()
    has_started = True

    while not stopped:
        now = dt.now()
        elapsed = (now - start_time).seconds
        if elapsed >= last_second + 1:
            last_second += 1
            reset = True
        time.sleep(0.05)


def render_image_thread(tid):
    """Capture screen region → convert to ASCII → display."""
    global fps_counter, image_buffer, reset

    local_frames = 0
    sct = mss.mss()

    while not stopped:
        if reset:
            local_frames = 0
            reset = False

        if has_started and last_second > 0:
            desired = FRAMERATE * (last_second + 1)
            with _counter_lock:
                ib = image_buffer
            if ib >= desired:
                time.sleep(0.005)
                continue

        height = max(MONITOR["height"] // SCALE_DIVISOR, 1)
        width = max(MONITOR["width"] // SCALE_DIVISOR, 1)

        sct_img = sct.grab(MONITOR)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        with _watching_video_lock:
            vm = watching_video
        ascii_lines = convert_frame(img, video_mode=vm)
        display_frame("\n".join(ascii_lines), tid)

        local_frames += 1
        with _counter_lock:
            fps_counter += 1
            image_buffer += 1

    sct.close()


def display_frame(item, tid):
    """Print a single frame to the terminal."""
    global _last_terminal_size
    elapsed = dt.now() - start_time if start_time else 0
    elapsed_sec = int(elapsed.total_seconds()) if elapsed else 0
    elapsed_str = f"{elapsed_sec // 60:02d}:{elapsed_sec % 60:02d}"

    with _watching_video_lock:
        _vm = watching_video

    cols, lines = shutil.get_terminal_size((80, 24))
    if (cols, lines) != _last_terminal_size:
        _last_terminal_size = (cols, lines)
        # Clear terminal completely to avoid residual layout artifacts on resize
        print("\033[2J\033[H", end="", flush=True)

    # Parse video dimensions and calculate margins
    video_lines = item.splitlines()
    vw = _visible_length(video_lines[0]) if video_lines else 0
    pad_w = max(0, (cols - 2 - vw) // 2)
    pad_right = max(0, cols - 2 - vw - pad_w)

    # Style colors
    border_color = "\033[90m"
    border_end = "\033[0m"

    # 1. Header
    header_text = f" LIVE SCREEN CAPTURE - THREAD {tid} "
    header_styled = f"\033[96;1m{header_text}\033[0m"
    header_len = len(header_text)

    if cols - 2 >= header_len:
        left_dashes = (cols - 2 - header_len) // 2
        right_dashes = cols - 2 - header_len - left_dashes
        top_line = f"{border_color}┌{'─' * left_dashes}{border_end}{header_styled}{border_color}{'─' * right_dashes}┐{border_end}"
    else:
        top_line = f"{border_color}┌{'─' * (cols - 2)}┐{border_end}"

    # 2. Body lines (centered)
    body_rows = []
    for vl in video_lines:
        body_rows.append(f"{border_color}│{border_end}{' ' * pad_w}{vl}{' ' * pad_right}{border_color}│{border_end}")

    # 3. Divider
    divider_line = f"{border_color}├{'─' * (cols - 2)}┤{border_end}"

    # 4. Footer
    footer_text = f"Status: ACTIVE  |  Video Mode: {_vm}  |  Elapsed: {elapsed_str}"
    footer_visible_len = len(footer_text)
    left_margin = 2
    right_space = cols - 2 - left_margin - footer_visible_len
    if right_space < 0:
        footer_line = f"{border_color}│{border_end}{footer_text}{border_color}│{border_end}"
    else:
        footer_line = f"{border_color}│{border_end}{' ' * left_margin}{footer_text}{' ' * right_space}{border_color}│{border_end}"

    # 5. Bottom border
    bottom_line = f"{border_color}└{'─' * (cols - 2)}┘{border_end}"

    # Assemble and print
    dashboard = []
    dashboard.append(top_line)
    dashboard.extend(body_rows)
    dashboard.append(divider_line)
    dashboard.append(footer_line)
    dashboard.append(bottom_line)

    print(f"\033[H" + "\n".join(dashboard), end="", flush=True)

def main():
    global stopped, fps_counter, image_buffer, watching_video, start_time

    # Start keyboard listener
    listener = keyboard.Listener(on_press=input_checker)
    listener.start()

    # Start capture threads
    num_threads = 4
    threads = []
    for i in range(num_threads):
        t = Thread(target=render_image_thread, args=[i])
        t.start()
        threads.append(t)
        time.sleep(1 / 8)  # Stagger starts

    try:
        cursor.hide()
        timing_module()
    except KeyboardInterrupt:
        pass
    finally:
        stopped = True
        cursor.show()
        for t in threads:
            t.join()
        listener.stop()
        print(f"\n{Colours.FAIL}{Colours.BOLD}Stopped.{Colours.END}")


if __name__ == "__main__":
    if sys.platform == "darwin":
        print(f"{Colours.WARNING}Note: On macOS, screen capture requires "
              f"Screen Recording permission in System Settings.{Colours.END}")
    main()
