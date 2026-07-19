"""
Live screen-capture renderer for video-to-ascii.
Captures a region of the screen and renders it as coloured ASCII art
in real time in the terminal.
"""

from __future__ import print_function

import sys
import time
from datetime import datetime as dt
from threading import Lock, Thread

import cursor
try:
    import mss
except ImportError:
    import sys
    print("Missing dependency: mss. Install with: uv pip install mss")
    sys.exit(1)
from PIL import Image
try:
    from pynput import keyboard
except ImportError:
    import sys
    print("Missing dependency: pynput. Install with: uv pip install pynput")
    sys.exit(1)
from sty import fg, bg

from ascii_convert import convert_frame
from colours import Colours


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
    global fps_counter, image_buffer, reset, has_started, last_second, stopped

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
    elapsed = dt.now() - start_time if start_time else 0
    with _watching_video_lock:
        _vm = watching_video
    output = (
        f"{Colours.FAIL}{Colours.BOLD}{Colours.UNDERLINE}Information{Colours.END}\n"
        f"{Colours.WARNING}{Colours.BOLD}Rendered on thread: {tid}{Colours.END}\n"
        f"{Colours.WARNING}{Colours.BOLD}"
        f"Video mode (Right Shift to toggle): {_vm}{Colours.END}\n"
        f"{Colours.GREEN}{Colours.BOLD}{elapsed}{Colours.END}\n"
        f"{item}\n"
        f"Made by Atul Pahal"
    )
    print(f"\033[H{output}", end="")


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
