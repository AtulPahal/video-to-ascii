"""
Video renderer for video-to-ascii.
Downloads YouTube videos or loads local files and renders them as
coloured ASCII art in the terminal.
"""

from __future__ import print_function

import argparse
import atexit
import datetime
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from threading import Lock, Thread

import cursor
import cv2
from PIL import Image
from sty import fg, bg

from ascii_convert import convert_frame, list_charsets
from ascii_html import write_html
from audio import detect_player, play_audio, stop_audio
from colours import Colours
from controls import PlaybackControls
from errors import VideoNotYoutubeLink
import youtubedl_saver as ydls
from intro import intro
__version__ = "1.1.0"
# Module-level temp dir for the atexit cleanup handler.
_temp_dir = None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render a YouTube video or local file as coloured ASCII art "
                    "in the terminal."
    )
    parser.add_argument("vid", nargs="?",
                        help="YouTube URL or path to a local video file")
    parser.add_argument("--framerate", type=int, default=30,
                        help="Target framerate (default: 30, auto-detected for local files)")
    parser.add_argument("--buffer", type=float, default=0,
                        help="Pre-buffer amount as fraction of total frames, 0-1 (default: 0)")
    parser.add_argument("--video-mode", dest="video_mode", action="store_true",
                        help="Use background-coloured blocks for more vibrant output")
    parser.add_argument("--chars", default="standard",
                        help="Character set for colour mode: "
                             + ", ".join(list_charsets().keys())
                             + " (default: standard)")
    parser.add_argument("--list-charsets", action="store_true",
                        help="List available character sets and exit")
    parser.add_argument("--export-html", metavar="FILE",
                        help="Save ASCII animation to an HTML file for sharing")
    parser.add_argument("--no-audio", action="store_true",
                        help="Disable audio playback")
    parser.add_argument("--width", type=int, default=0,
                        help="Override output width in character columns")
    parser.add_argument("--height", type=int, default=0,
                        help="Override output height in character rows")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Playback speed multiplier (e.g. 0.5 = half speed, 2.0 = double)")
    parser.add_argument("--version", action="store_true",
                        help="Show version number and exit")
    parser.add_argument("--no-intro", action="store_true",
                        help="Skip the 3-2-1 countdown before playback")
    parser.add_argument("--loop", nargs="?", const=-1, default=0, type=int,
                        help="Loop playback: --loop for infinite, "
                             "--loop N for N times total (default: play once)")
    return parser.parse_args()


def cleanup():
    """Restore cursor visibility and remove temporary frame directory."""
    cursor.show()
    global _temp_dir
    if _temp_dir and os.path.isdir(_temp_dir):
        try:
            shutil.rmtree(_temp_dir)
        except OSError:
            pass


def _signal_handler(signum, frame):
    """Convert termination signals into KeyboardInterrupt."""
    raise KeyboardInterrupt()


class ASCIIVideoPlayer:
    """Orchestrates loading, buffering, and terminal playback of a video as ASCII."""

    def __init__(self, args):
        self.args = args
        self.watching_video = args.video_mode
        self.charset = args.chars
        self.no_audio = args.no_audio
        self.speed = args.speed
        self.loop_count = args.loop
        self.no_intro = args.no_intro
        self.override_w = args.width
        self.override_h = args.height

        # Populated by load_video()
        self.framerate = args.framerate
        self.total_frames = 0
        self.duration = 0
        self.video_cap = None
        self.audio_path = None
        self._owned_video_path = None   # set only for downloaded YouTube files

        self.export_html = args.export_html
        self._all_ascii_frames = []       # accumulated for loop cache / HTML export

        # Threading state
        self.stopped = False
        self.frames_written = 0     # frames saved as JPEG
        self.frames_converted = 0   # frames turned into ASCII (sequential watermark)
        self.all_frames_read = False
        self.playback_started = False

        self.queue = {}             # index -> ASCII string
        self.lock = Lock()

        self.temp_dir = None
        self.begin_time = None
        self.frame_begin_time = None
        self.audio_process = None
        self.audio_player = None    # name of detected audio player
        self.controls = PlaybackControls()

        # Thread references
        self._reader = None
        self._converters = []
        self._player = None

    # ------------------------------------------------------------------
    # Video loading
    # ------------------------------------------------------------------

    def load_video(self):
        """Open a local file or download a YouTube URL.  Returns True on success."""
        vid = self.args.vid

        if os.path.isfile(vid):
            # --- Local file ---
            cap = cv2.VideoCapture(vid)
            if not cap.isOpened():
                print(f"{Colours.FAIL}Error: cannot open video file '{vid}'{Colours.END}")
                return False
            self.framerate = cap.get(cv2.CAP_PROP_FPS) or float(self.args.framerate)
            self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.duration = self.total_frames / self.framerate if self.framerate > 0 else 0
            cap.release()
            self.video_cap = cv2.VideoCapture(vid)
            self.audio_path = vid
            print(f"{Colours.GREEN}Local file: {vid}  "
                  f"{self.total_frames} frames @ {self.framerate:.1f} fps, "
                  f"{self.duration:.1f}s{Colours.END}")
            return True

        # --- YouTube URL ---
        if not re.match(
            r'^(http(s)?://)?(www\.)?((youtube\.com/watch\?v=)|(youtu\.be/))([a-zA-Z0-9_-]{11})',
            vid
        ):
            print(f"{Colours.FAIL}Error: not a valid file path or YouTube URL{Colours.END}")
            return False
        # Download to a unique temp path so we never collide with user files
        temp_download = os.path.join(tempfile.mkdtemp(prefix="ytdl_"), "video.mp4")
        video_location, self.framerate, self.total_frames, self.duration = ydls.save_file(
            vid, outtmpl=temp_download
        )
        if video_location == "error":
            return False
        self.audio_path = temp_download
        self._owned_video_path = temp_download
        self.video_cap = cv2.VideoCapture(temp_download)
        return True

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def _render_size(self, frame_w, frame_h):
        """Return (target_w, target_h) in character-cells."""
        if self.override_w > 0 and self.override_h > 0:
            return self.override_w, self.override_h

        cols, lines = shutil.get_terminal_size((80, 24))
        max_w = cols // 2
        max_h = max(lines - 12, 10)

        if self.override_w > 0:
            max_w = self.override_w
        if self.override_h > 0:
            max_h = self.override_h

        scale = min(max_w / frame_w, max_h / frame_h)
        return max(int(frame_w * scale), 1), max(int(frame_h * scale), 1)

    # ------------------------------------------------------------------
    # Thread targets
    # ------------------------------------------------------------------

    def _read_frames(self):
        """Reader thread: read video -> resize -> save JPEG to temp dir."""
        try:
            while not self.stopped:
                ok, frame = self.video_cap.read()
                if not ok:
                    with self.lock:
                        self.all_frames_read = True
                    break
                h, w = frame.shape[:2]
                tw, th = self._render_size(w, h)
                resized = cv2.resize(frame, (tw, th))
                with self.lock:
                    idx = self.frames_written
                # Write to disk FIRST, then publish the index
                cv2.imwrite(os.path.join(self.temp_dir, f"f{idx}.jpg"), resized)
                with self.lock:
                    self.frames_written = idx + 1
        except KeyboardInterrupt:
            self.stopped = True

    def _convert_frames(self, tid, nthreads):
        """Converter thread: pick JPEGs assigned to this tid, convert to ASCII."""
        while not self.stopped:
            # Find the next unconverted frame this thread owns
            idx = None
            with self.lock:
                start = self.frames_converted
                end = self.frames_written
                for i in range(start, end):
                    if i % nthreads == tid and i not in self.queue:
                        idx = i
                        break
                if idx is None and self.all_frames_read and start >= end:
                    break

            if idx is None:
                time.sleep(0.005)
                continue

            path = os.path.join(self.temp_dir, f"f{idx}.jpg")
            try:
                pil_img = Image.open(path).convert("RGB")
                lines = convert_frame(pil_img, charset=self.charset,
                                      video_mode=self.watching_video)
                ascii_str = "\n".join(lines)
                with self.lock:
                    self.queue[idx] = ascii_str
                    while self.frames_converted in self.queue:
                        self.frames_converted += 1
                os.remove(path)
            except Exception as e:
                if not self.stopped:
                    print(f"{Colours.FAIL}Error converting frame {idx}: {e}{Colours.END}", file=sys.stderr)

    def _play_loop(self):
        """Playback thread: consume queue at the correct framerate.
        Supports --loop (infinite or N repeats).
        """
        delay = 1.0 / (self.framerate * self.speed)
        idx = 0
        paused_frame = None
        times_played = 0
        max_plays = self.loop_count  # 0 = once, -1 = infinite, N = N times
        all_cached = False

        while not self.stopped:
            if self.controls.should_quit():
                self.stopped = True
                break

            # --- Seek ---
            seek = self.controls.consume_seek()
            if seek != 0:
                # seek is in seconds; convert to frames
                seek_frames = int(seek * self.framerate) if self.framerate > 0 else int(seek * 30)
                idx = max(0, min(idx + seek_frames, self.total_frames - 1))
                if not all_cached:
                    with self.lock:
                        for stale in range(idx):
                            self.queue.pop(stale, None)

            # --- Pause ---
            if self.controls.is_paused():
                if paused_frame is None:
                    paused_frame = self._make_paused_frame()
                print(f"\033[H{paused_frame}")
                time.sleep(0.1)
                continue
            paused_frame = None

            # --- Check end / loop ---
            if idx >= self.total_frames:
                times_played += 1
                if max_plays == 0:
                    break
                if max_plays > 0 and times_played >= max_plays:
                    break
                # Reset for next loop
                idx = 0
                all_cached = True
                self.begin_time = datetime.datetime.now()
                self.frame_begin_time = datetime.datetime.now()
                # Restart audio for new loop
                stop_audio(self.audio_process)
                self._start_audio()
                continue

            # --- Consume next frame ---
            if not all_cached:
                with self.lock:
                    item = self.queue.pop(idx, None)
                if item is None:
                    time.sleep(0.001)
                    continue
            else:
                item = self._all_ascii_frames[idx]

            idx += 1

            # --- Timing ---
            now = datetime.datetime.now()
            elapsed = (now - self.frame_begin_time).total_seconds()
            remaining = delay - elapsed
            if remaining > 0:
                time.sleep(remaining)
                now = datetime.datetime.now()  # re-read after sleep
            self.frame_begin_time = now

            self._show_frame(item, idx, now)
            self._all_ascii_frames.append(item)

        self.stopped = True
        self._finish()


    def _make_paused_frame(self):
        """Return a paused overlay string."""
        elapsed = datetime.datetime.now() - self.begin_time
        return (
            f"{Colours.FAIL}{Colours.BOLD}{Colours.UNDERLINE}"
            f"Information about the video{Colours.END}\n"
            f"{Colours.WARNING}{Colours.BOLD}"
            f"PAUSED — press Space to resume, Q to quit{Colours.END}\n"
            f"{Colours.GREEN}{Colours.BOLD}"
            f"{elapsed}/{datetime.timedelta(seconds=self.duration)}{Colours.END}\n"
            f"\n{Colours.WARNING}PAUSED{Colours.END}\n"
        )

    def _show_frame(self, item, num, now=None):
        """Print one frame to the terminal with progress bar and control hints."""
        if now is None:
            now = datetime.datetime.now()
        elapsed = now - self.begin_time

        # Progress bar
        pct = min(100, int(num / max(self.total_frames, 1) * 100))
        bar_w = 20
        filled = int(bar_w * pct / 100)
        bar = "[" + "=" * filled + ">" * min(1, bar_w - filled) + "." * (bar_w - filled - 1) + "]"

        info = (
            f"{Colours.FAIL}{Colours.BOLD}{Colours.UNDERLINE}"
            f"Video-to-ASCII{Colours.END}\n"
            f"{Colours.GREEN}{Colours.BOLD}"
            f"Frame {num}/{self.total_frames} "
            f"({pct}%)  "
            f"{elapsed}/{datetime.timedelta(seconds=self.duration)}"
            f"{Colours.END}\n"
            f"{Colours.CYAN}{bar}{Colours.END}\n"
            f"{Colours.WARNING}"
            f"[Space] pause  [Q] quit  [←/→] seek 5s{Colours.END}\n"
            f"{item}\n"
            f"Made by Atul Pahal"
        )
        # Check terminal resize each frame
        self._check_terminal_size()
        print(f"\033[H{info}")

    _last_terminal_size = (0, 0)

    def _check_terminal_size(self):
        """Detect terminal resize and log if changed (recalc on next frame load)."""
        cur = shutil.get_terminal_size((80, 24))
        if cur != self._last_terminal_size:
            self._last_terminal_size = cur

    def _cleanup_owned(self):
        """Remove the downloaded video file if we created it."""
        if self._owned_video_path:
            try:
                os.remove(self._owned_video_path)
            except FileNotFoundError:
                pass


    def _finish(self):
        """Stop audio, stop controls listener, write HTML export, print goodbye."""
        stop_audio(self.audio_process)
        self.controls.stop()

        # Write HTML export if requested
        if self.export_html and self._all_ascii_frames:
            try:
                write_html(self._all_ascii_frames, self.framerate, self.export_html)

                print(f"{Colours.GREEN}ASCII animation saved to {self.export_html}{Colours.END}")
            except Exception as e:
                print(f"{Colours.FAIL}Error saving HTML export: {e}{Colours.END}")

        self._cleanup_owned()
        print(f"\n{Colours.FAIL}{Colours.BOLD}{Colours.UNDERLINE}Goodbye!{Colours.END}")

    def run(self):
        if not self.load_video():
            return

        # Detect audio player
        self.audio_player = detect_player()

        # Start keyboard controls listener
        self.controls.start()

        # Temp directory
        self.temp_dir = tempfile.mkdtemp(prefix="ascii_frames_")
        global _temp_dir
        _temp_dir = self.temp_dir

        # Start reader
        self._reader = Thread(target=self._read_frames, daemon=True)
        self._reader.start()

        # Start converters
        nconv = 3
        for i in range(nconv):
            t = Thread(target=self._convert_frames, args=(i, nconv), daemon=True)
            t.start()
            self._converters.append(t)

        # --- Buffer phase ---
        target = max(int(self.total_frames * self.args.buffer), 1)
        if self.args.buffer > 0:
            print(f"{Colours.GREEN}Pre-buffering up to {target} frames…{Colours.END}")


        while not self.stopped:
            if self.args.buffer > 0 and self.frames_converted < target:
                pct = int(self.frames_converted / max(self.total_frames, 1) * 100)
                print(f"\r{Colours.GREEN}{Colours.BOLD}"
                      f"Buffering: {self.frames_converted}/{self.total_frames} ({pct}%)"
                      f"{Colours.END}",
                      end="")
                time.sleep(0.1)
                continue

            if not self.playback_started:
                if self.no_intro:
                    print("\033[2J\033[H", end="", flush=True)
                else:
                    intro()
                self.playback_started = True

                self._start_audio()
                self.begin_time = datetime.datetime.now()
                self.frame_begin_time = datetime.datetime.now()
                self._player = Thread(target=self._play_loop, daemon=True)
                self._player.start()

            time.sleep(0.1)

        # Join everything
        self._reader.join()
        for t in self._converters:
            t.join()
        if self._player and self._player.is_alive():
            self._player.join()
    def _start_audio(self):
        """Launch audio playback using the cross-platform audio module."""
        if self.no_audio:
            return
        if not self.audio_path or not os.path.isfile(self.audio_path):
            return
        if not self.audio_player:
            return
        self.audio_process = play_audio(self.audio_path, self.audio_player)


def main():
    args = parse_args()
    if args.version:
        print(f"video-to-ascii v{__version__}")
        sys.exit(0)

    # Handle --list-charsets
    if args.list_charsets:
        print("Available character sets:")
        for name, desc in list_charsets().items():
            print(f"  {name}  — {desc}")
        sys.exit(0)

    # vid is required unless --list-charsets was used
    if not args.vid:
        print(f"{Colours.FAIL}Error: a video URL or file path is required{Colours.END}")
        print("Usage: uv run python3 video_render.py <video-url-or-path> [options]")
        sys.exit(1)

    # Validate charset
    available = list_charsets()
    if args.chars not in available:
        print(f"{Colours.FAIL}Error: unknown charset '{args.chars}'. "
              f"Available: {', '.join(available)}{Colours.END}")
        sys.exit(1)

    atexit.register(cleanup)
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    player = None
    try:
        cursor.hide()
        player = ASCIIVideoPlayer(args)
        player.run()
    except KeyboardInterrupt:
        if player:
            player.stopped = True
    finally:
        cleanup()

if __name__ == "__main__":
    main()
