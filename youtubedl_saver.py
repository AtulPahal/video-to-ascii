from __future__ import unicode_literals

import yt_dlp as youtube_dl


def save_file(url):
    ydl_opts = {
        "format": "best[height<=480][ext=mp4]/best[ext=mp4]/best",
        "outtmpl": "video",
        "quiet": True,
        "extractor_args": {"youtube": {"player_client": ["android", "web_creator"]}}
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
            info = ydl.extract_info(url=url, download=False)
            fps = info.get('fps')
            if fps is None:
                fps = 30
            total_frames = fps * info['duration']
            duration = info['duration']
        except Exception as e:
            print(f"Error downloading video: {e}")
            return "error", 0, 0, 0
        return "video", fps, total_frames, duration
