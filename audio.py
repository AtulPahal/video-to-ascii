"""
Cross-platform audio playback for video-to-ascii.
Supports macOS (afplay), Linux (ffplay / aplay / paplay), and Windows (ffplay).

Usage:
    from audio import detect_player, play_audio, stop_audio

    player = detect_player()
    if player:
        proc = play_audio("video.mp4", player=player)
        # ... later ...
        stop_audio(proc)
"""

from __future__ import print_function

import os
import subprocess
import sys


def detect_player():
    """
    Detect the best available audio player for the current platform.

    Returns a player name string (suitable for ``play_audio``) or *None*.
    """
    if sys.platform == "darwin":
        # afplay is built into macOS — no dependency needed
        return "afplay"

    # Check *nix players
    for candidate in ("ffplay", "aplay", "paplay"):
        try:
            subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                timeout=2,
            )
            return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # check via sh/which as fallback
            try:
                subprocess.run(
                    ["sh", "-c", f"command -v {candidate}"],
                    capture_output=True,
                    timeout=2,
                )
                return candidate
            except Exception:
                continue

    # Windows fallback — try ffplay (from ffmpeg)
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["ffplay", "-version"],
                capture_output=True,
                timeout=2,
            )
            return "ffplay"
        except Exception:
            pass

    return None


def play_audio(path, player):
    """
    Play an audio file and return the ``subprocess.Popen`` handle.

    Returns *None* if playback could not be started.
    """
    if not path or not os.path.isfile(path):
        return None

    try:
        if player == "afplay":
            return subprocess.Popen(
                ["afplay", path, "-q", "1"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        if player == "ffplay":
            return subprocess.Popen(
                [
                    "ffplay", "-nodisp", "-autoexit",
                    "-loglevel", "quiet", path,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        if player == "aplay":
            return subprocess.Popen(
                ["aplay", "-q", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        if player == "paplay":
            return subprocess.Popen(
                ["paplay", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass
    return None


def stop_audio(process):
    """Gracefully stop an audio subprocess."""
    if process is None:
        return
    try:
        process.terminate()
        process.wait(timeout=3)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
