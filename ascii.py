"""
Interactive CLI launcher for video-to-ascii.
Prompts the user for mode, URL, buffer, and display settings,
then runs the appropriate renderer.
"""

from __future__ import print_function, unicode_literals

import os
import re
import subprocess
import sys

from colours import Colours
try:
    import questionary
    from questionary import ValidationError, Validator
except ImportError:
    print(f"{Colours.FAIL}Missing dependency: questionary. Install with: uv pip install questionary{Colours.END}")
    sys.exit(1)

from ascii_convert import list_charsets


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

class URLValidator(Validator):
    def validate(self, document):
        text = document.text.strip()
        is_valid = re.match(
            r'^(http(s)?://)?(www\.)?((youtube\.com/watch\?v=)|(youtu\.be/))([a-zA-Z0-9_-]{11})',
            text
        )
        if not is_valid:
            raise ValidationError(
                message="Please enter a valid YouTube URL "
                        "(e.g. https://youtube.com/watch?v=VIDEO_ID)",
                cursor_position=len(document.text),
            )


class FileValidator(Validator):
    def validate(self, document):
        path = document.text.strip()
        if not os.path.isfile(path):
            raise ValidationError(
                message=f"File not found: {path}",
                cursor_position=len(document.text),
            )


class BufferValidator(Validator):
    def validate(self, document):
        try:
            val = float(document.text.strip())
            if not 0 <= val <= 1:
                raise ValidationError(
                    message="Buffer amount must be between 0 and 1",
                    cursor_position=len(document.text),
                )
        except ValueError:
            raise ValidationError(
                message="Buffer amount must be a number between 0 and 1",
                cursor_position=len(document.text),
            )


# ---------------------------------------------------------------------------
# Build command
# ---------------------------------------------------------------------------

def build_command():
    answers = questionary.select(
        "What do you want to do?",
        choices=[
            "Video — render a YouTube video or local file",
            "Screen — capture and render your screen live (laggy, lower quality)",
        ],
    ).ask()

    if answers is None:
        sys.exit(0)

    if answers.startswith("Video"):
        return _build_video_command()
    else:
        return ["uv", "run", "python3", "live_render.py"]


def _build_video_command():
    # Source
    source = questionary.select(
        "Where is the video?",
        choices=["YouTube URL", "Local file"],
    ).ask()
    if source is None:
        sys.exit(0)

    vid_arg = ""
    if source == "YouTube URL":
        url = questionary.text(
            "What's the YouTube URL?",
            validate=URLValidator,
        ).ask()
        if url is None:
            sys.exit(0)
        vid_arg = url.strip()
    else:
        path = questionary.text(
            "Path to the video file:",
            validate=FileValidator,
        ).ask()
        if path is None:
            sys.exit(0)
        vid_arg = path.strip()

    # Buffer
    buffer_val = questionary.text(
        "How much to pre-buffer (0-1, 0 = minimal):",
        validate=BufferValidator,
        default="0",
    ).ask()
    if buffer_val is None:
        sys.exit(0)

    # Video mode
    video_mode = questionary.confirm(
        "Use video mode? (background-coloured blocks, more vibrant)",
        default=False,
    ).ask()
    if video_mode is None:
        sys.exit(0)

    # Character set (only in non-video mode)
    if not video_mode:
        charsets = list_charsets()
        charset = questionary.select(
            "Character set:",
            choices=[f"{k} — {v}" for k, v in charsets.items()],
            default="standard",
        ).ask()
        if charset is None:
            sys.exit(0)
        charset_name = charset.split(" —")[0]
    else:
        charset_name = "standard"  # unused in video mode

    cmd_parts = ["uv", "run", "python3", "video_render.py", vid_arg]
    cmd_parts.append(f"--buffer={float(buffer_val.strip())}")
    if video_mode:
        cmd_parts.append("--video-mode")
    if charset_name != "standard":
        cmd_parts.append(f"--chars={charset_name}")

    return cmd_parts


# ---------------------------------------------------------------------------
# Warning prompt
# ---------------------------------------------------------------------------

def show_warning():
    print()
    print("-" * 40)
    print(f"{Colours.FAIL}{Colours.BOLD}PLEASE READ{Colours.END}")
    print(
        "The following program can lag or crash your computer. "
        "It is not designed for all computers. If you experience "
        "any issues with your computer as a result of this program "
        "it is your fault. Only run this program if you know your "
        "PC will handle it. To end the program press Ctrl+C (may "
        "need to press it a couple times)."
    )
    print()
    print(f"{Colours.FAIL}{Colours.BOLD}RUN AT YOUR OWN RISK.{Colours.END}")
    print()
    print(f"{Colours.GREEN}Tip: press Right Shift to toggle video "
          f"mode during playback!{Colours.END}")
    print("-" * 40)
    print()

    agree = questionary.confirm(
        "I have read and agree to the statement above",
        default=False,
    ).ask()

    if not agree:
        print("Cannot run program — you did not agree.")
        sys.exit(0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        argv = build_command()
        show_warning()

        print(f"\n{Colours.GREEN}Running: {' '.join(argv)}{Colours.END}\n")
        subprocess.run(argv)

    except KeyboardInterrupt:
        print(f"\n{Colours.FAIL}Cancelled.{Colours.END}")
        sys.exit(0)
    except Exception as e:
        print(f"{Colours.FAIL}Error: {e}{Colours.END}")
        sys.exit(1)

if __name__ == "__main__":
    main()
