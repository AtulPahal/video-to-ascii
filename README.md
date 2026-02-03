# Video To ASCII
A python generator that converts youtube videos to ascii art in your console. 

# Example
## Full Screen Mode
Now supports full screen rendering and audio playback!

# How to use
### Installation
1. Clone the repository
2. Install dependencies:
   ```bash
   pip3 install yt-dlp opencv-python sty cursor pillow
   ```
   (Note: `pynput` is no longer required)

### Usage
Run the script with a YouTube URL:
```bash
python3 video_render.py "yt-url"
```

### Features
- **Full Screen**: Automatically detects terminal size.
- **Audio Support**: Plays video audio in sync (macOS only currently via `afplay`).
- **High Resolution ASCII**: Uses an expanded character set for better detail.
- **Smooth Playback**: Uses ANSI escape codes to prevent flickering.

### Interactive Mode
You can also run the interactive CLI:
```bash
python3 ascii.py
```

# Todo
- [x] Add CLI
- [x] Allow for other modes
- [x] Make it easier to use
- [x] Allow screen capture real time
- [ ] Allow for windows audio support
