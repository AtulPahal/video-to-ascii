from __future__ import unicode_literals

import yt_dlp as youtube_dl


def save_file(url, outtmpl=None):
    if outtmpl is None:
        outtmpl = "video"
    ydl_opts = {
        "format": "best[height<=480][ext=mp4]/best[ext=mp4]/best",
        "outtmpl": outtmpl,
        "quiet": False,
        "extractor_args": {"youtube": {"player_client": ["android", "web_creator"]}}
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url=url, download=True)
            fps = info.get('fps', 30)
            duration = info.get('duration') or 0
            total_frames = int(fps * duration)
        except Exception as e:
            print(f"Error downloading video: {e}")
            return "error", 0, 0, 0
        return outtmpl, fps, total_frames, duration
