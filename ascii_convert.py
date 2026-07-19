"""
ASCII conversion module for video-to-ascii.
Converts PIL images to ASCII art with ANSI color codes.

Usage:
    from ascii_convert import convert_frame, list_charsets

    lines = convert_frame(pil_image, charset="standard", video_mode=False)
    for row in lines:
        print(row)
"""

from __future__ import print_function
import numpy as np

from sty import fg, bg

# Character sets for colour mode (foreground-coloured characters on default bg)
# Keys are brightness thresholds, values are the character(s) to draw.
CHARSETS = {
    "standard": {
        25: "  ",
        50: "..",
        75: "::",
        100: "--",
        125: "==",
        150: "++",
        175: "**",
        200: "##",
        225: "%%",
        255: "@@",
    },
    "compact": {
        51: "  ",
        102: "..",
        153: "--",
        204: "**",
        255: "@@",
    },
    "minimal": {
        64: ".",
        128: "-",
        192: "+",
        255: "#",
    },
}

# Character set for "video" mode (background-coloured blocks + fixed foreground).
# Each entry is (display_chars, foreground_style).
VIDEO_CHARSET = {
    50: ("  ", fg.white),
    70: ("..", fg.li_grey),
    130: ("--", fg.li_grey),
    230: ("~~", fg.grey),
    240: ("++", fg.da_black),
    255: ("  ", fg.black),
}

CHARSET_DESCRIPTIONS = {
    "standard": "10-level density ramp (default, matches original colour mode)",
    "compact": "5-level compact ramp",
    "minimal": "4-level single-character ramp",
}


def list_charsets():
    """Return dict of {name: description} for available colour-mode charsets."""
    return dict(CHARSET_DESCRIPTIONS)


def convert_frame(pil_image, charset="standard", video_mode=False):
    """
    Convert a PIL image to a list of ASCII strings with ANSI colour codes.

    Args:
        pil_image: PIL Image object (RGB mode).
        charset: Name of the character set to use (only applies in colour mode).
        video_mode: If True, uses background-coloured blocks (more vibrant,
                    matches the original --video_mode flag). If False, uses
                    foreground-coloured characters on the terminal background.

    Returns:
        list[str]: Each element is one row of ASCII art including ANSI codes.
    """
    pixels = np.array(pil_image, dtype=np.uint8)
    height, width = pixels.shape[:2]

    frame_lines = []

    if video_mode:
        # --- "Video" / blocks mode: bg = pixel colour, fg = fixed style ---
        thresholds = sorted(VIDEO_CHARSET.keys())

        for y in range(height):
            line_chars = []
            for x in range(width):
                r, g, b = pixels[y, x]
                brightness = (r + g + b) / 3

                chosen_chars, chosen_fg = VIDEO_CHARSET[thresholds[0]]
                for t in thresholds:
                    if brightness <= t:
                        chosen_chars, chosen_fg = VIDEO_CHARSET[t]
                        break

                line_chars.append(
                    bg(r, g, b) + chosen_fg + chosen_chars + fg.rs + bg.rs
                )

            frame_lines.append("".join(line_chars))

    else:
        # --- Colour mode: fg = pixel colour, chars from charset ---
        char_map = CHARSETS.get(charset, CHARSETS["standard"])
        thresholds = sorted(char_map.keys())

        for y in range(height):
            line_chars = []
            for x in range(width):
                r, g, b = pixels[y, x]
                brightness = (r + g + b) / 3

                chosen_chars = char_map[thresholds[0]]
                for t in thresholds:
                    if brightness <= t:
                        chosen_chars = char_map[t]
                        break

                line_chars.append(fg(r, g, b) + chosen_chars + fg.rs)

            frame_lines.append("".join(line_chars))

    return frame_lines
