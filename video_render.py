
import youtubedl_saver as ydls

from colours import Colours
from intro import intro
from errors import *


import cv2
import os
import sys
import argparse
import time
import subprocess
import shutil
import regex as re
import cursor
import datetime

from threading import Thread
from sty import fg, bg
from PIL import Image




def finished_render():
    global stopped, audio_process

    cursor.show()
    
    try:
        if 'audio_process' in globals() and audio_process:
            audio_process.terminate()
            audio_process.wait()
    except Exception:
        pass

    stopped = True
    try:
        render_thread.join()
        queue_thread.join()

        try:
            os.remove("video")
        except FileNotFoundError:
            print("DEBUG: No previous video found.")

        for i in range(image_buffer):
            try:
                os.remove(f"frames/frame{i}.jpg")
            except FileNotFoundError:
                pass
    except NameError:
        print("DEBUG: Threads have not been started yet.")


    print(f"\n{Colours.FAIL}{Colours.BOLD}{Colours.UNDERLINE}Goodbye!{Colours.END}")
    sys.exit()



def render_frame():
    global buffer, queue, inverted, global_width, global_height, image_buffer, rendered_images, stopped

    try:
        while not stopped:
            _success, _image = vidcap.read()
            if _success:
                resize_image(_image)
            elif not _success and not rendered_images:
                rendered_images = True
                for thread in range(3):
                    render_frame_thread = Thread(target=render_frame_buffer, args=[thread])
                    try:
                        render_frame_thread.start()
                    except KeyboardInterrupt:
                        render_frame_thread.join()
                        finished_render()
            elif frames == total_frames:
                os.remove("video")
                print(f"{Colours.FAIL}{Colours.BOLD}{Colours.UNDERLINE}Goodbye!{Colours.END}")
                stopped = True
    except KeyboardInterrupt:
        finished_render()


def resize_image(_image):
    global buffer, queue, inverted, global_width, global_height, image_buffer
    
    cols, lines = shutil.get_terminal_size((80, 24))
    
    
    max_w = cols // 2
    max_h = max(lines - 12, 10)
    
    v_height, v_width = _image.shape[:2]
    
    scale_w = max_w / v_width
    scale_h = max_h / v_height
    scale = min(scale_w, scale_h)
    
    target_w = int(v_width * scale)
    target_h = int(v_height * scale)
    
    target_w = max(target_w, 1)
    target_h = max(target_h, 1)


    resized_image = cv2.resize(_image, (target_w, target_h))
    cv2.imwrite(f"frames/frame{image_buffer}.jpg", resized_image)
    image_buffer += 1


def render_frame_buffer(thread):
    global image_buffer, buffer
    for frame in range(image_buffer):
        if frame % 3 == thread:
            try:
                _img = Image.open(f"frames/frame{frame}.jpg")

                width, height = _img.size
                pix = _img.load()

                queue[frame] = "\n".join(get_full_frame(0, 0, height, width, [], pix))
                os.remove(f"frames/frame{frame}.jpg")
                buffer += 1
            except Exception:
                pass


def get_x_frame(x, y, height, width, outputs, pix):
    if x == width - 2:
        return outputs 
    else:
        if watching_video:
            ascii_outputs = {50: ["  ", fg.white],
                             70: ["..", fg.li_grey],
                             130: ["--", fg.li_grey],
                             230: ["~~", fg.grey],
                             240: ["++", fg.da_black],
                             255: ["  ", fg.black]}
        else:
            ascii_outputs = {
                25: "  ", 
                50: "..", 
                75: "::", 
                100: "--", 
                125: "==", 
                150: "++", 
                175: "**", 
                200: "##", 
                225: "%%", 
                255: "@@"
            }
        r, g, b = pix[x, y]
        brightness = sum([r, g, b]) / 3
        
        thresholds = sorted(ascii_outputs.keys())
        
        for output in thresholds:
            if brightness <= output:
                if not watching_video:
                    outputs.append(fg(r, g, b) + ascii_outputs[output] + fg.rs)
                    return get_x_frame(x + 1, y, height, width, outputs, pix)
                else:
                    outputs.append(bg(r, g, b) + ascii_outputs[output][1] + ascii_outputs[output][0] + fg.rs + bg.rs)
                    return get_x_frame(x + 1, y, height, width, outputs, pix)


def get_full_frame(x, y, height, width, full_frame, pix):
    if y == height - 2:
        return full_frame
    else:
        x_frame = "".join(get_x_frame(0, y, height, width, [], pix))
        full_frame.append(x_frame)
        return get_full_frame(x, y + 1, height, width, full_frame, pix)


def run_queue():
    global queue, framerate, frames, frame_begin_time, begin_time, restart
    start = False
    lock = False
    timer = False
    checker_second = 0
    local_image_buffer = 0

    while not stopped:
        if len(queue) >= total_frames * buffer_amount - 1 and rendered_images:
            start = True

        if frames == total_frames:
            return

        if (len(queue) >= total_frames * buffer_amount - 1 or start) and lock:
            if not timer:
                start = True
                timer = True

                begin_time = datetime.datetime.now()
                frame_begin_time = datetime.datetime.now()

                render_second_thread = Thread(target=render_second)
                render_second_thread.start()
                
                global audio_process
                try:
                    audio_process = subprocess.Popen(['afplay', 'video', '-q', '1'], 
                                                   stdout=subprocess.DEVNULL, 
                                                   stderr=subprocess.DEVNULL)
                except Exception:
                    pass

            checker = datetime.datetime.now() - begin_time
            if round(checker.microseconds / 1000000, 1) == 0 and checker_second < checker.seconds:
                restart = True
                checker_second = checker.seconds
        elif not start:
            print(f"{Colours.GREEN}{Colours.BOLD}Buffering: {image_buffer}/{round(total_frames)}{Colours.END}")
        elif not lock:
            intro()
            lock = True


def render_second():
    global queue, framerate, frames, frame_begin_time, begin_time, restart, stopped
    time_delay = (duration / total_frames)
    render_frames = 0
    while not stopped:
        if restart:
            not_rendered = framerate - (render_frames % framerate)
            if framerate > not_rendered > 0:
                for _ in range(not_rendered):
                    try:
                        queue.pop(frames)
                        frames += 1
                    except IndexError:
                        print(f"{Colours.FAIL}{Colours.BOLD}{Colours.UNDERLINE}Goodbye!{Colours.END}")
                        finished_render()
            render_frames = 0
            restart = False
            pass
        else:
            try:
                if render_frames < framerate:
                    item = queue.pop(frames)
                    frames += 1
                    render_frames += 1

                    sleep = time_delay - ((datetime.datetime.now() - frame_begin_time).microseconds / 1000000)
                    if sleep > 0:
                        time.sleep(sleep)
                    frame_begin_time = datetime.datetime.now()
                    display_frame(item)
            except KeyError:
                print(f"{Colours.FAIL}{Colours.BOLD}{Colours.UNDERLINE}Goodbye!{Colours.END}")
                stopped = True
                finished_render()


def display_frame(item):
    output = f"{Colours.FAIL}{Colours.BOLD}{Colours.UNDERLINE}Information about the video{Colours.END}" \
             f"\n{Colours.WARNING}{Colours.BOLD}Tabbing out may crash this, stopping the program is a bit buggy, may need to spam ctrl c till it stops.{Colours.END}" \
             f"\n{Colours.GREEN}{Colours.BOLD}Is running in video mode? {watching_video}" \
             f"\n{Colours.GREEN}{Colours.BOLD}Frame {frames}/{buffer} at {framerate}fps ({total_frames} frames in total){Colours.END}" \
             f"\n{Colours.GREEN}{Colours.BOLD}{(datetime.datetime.now() - begin_time)}/{datetime.timedelta(seconds=duration)}{Colours.END}" \
             f"\n{item}" \
             f"\nMade by Atul Pahal"
    print(f"\033[H{output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("vid", help="Where the video is located", type=str)
    parser.add_argument("--framerate", dest="framerate", help="Frame rate (Default 30)", type=int, default=30)
    parser.add_argument("--buffer", dest="buffer", help="Buffer amount 0-1", type=float, default=0)
    parser.add_argument("--video_mode", dest="video_mode",
                        help="Changes the rendering mode from character to highlighted", type=str, default="False")
    args = parser.parse_args()

    try:
        os.remove("video")
    except FileNotFoundError:
        print("DEBUG: No previous video found.")

    try:
        if re.match('^(http(s)??\:\/\/)?(www\.)?((youtube\.com\/watch\?v=)|(youtu.be\/))([a-zA-Z0-9\-_]){11}',
                    args.vid.lower()):
            video_location, framerate, total_frames, duration = ydls.save_file(args.vid)
            vidcap = cv2.VideoCapture(video_location)
            success, image = vidcap.read()

            begin_time = datetime.datetime.now()
            frame_begin_time = datetime.datetime.now()

            restart = False
            rendered_images = False
            watching_video = True if args.video_mode.lower() == "true" else False
            stopped = False

            frames = 1
            popped = 1
            image_buffer = 0
            buffer = 0
            buffer_amount = args.buffer

            queue = {}
            cv2.imwrite(f"frames/frameTEST.jpg", image)
            img = Image.open(f"frames/frameTEST.jpg")
            global_width, global_height = img.size

            queue_thread = Thread(target=run_queue)
            render_thread = Thread(target=render_frame)
        else:
            finished_render()
            raise VideoNotYoutubeLink(args.vid)

        try:
            cursor.hide()

            try:
                render_thread.start()
            except KeyboardInterrupt:
                render_thread.join()
                finished_render()

            try:
                queue_thread.start()
            except KeyboardInterrupt:
                queue_thread.join()
                finished_render()
        except KeyboardInterrupt:
            finished_render()
    except ValueError:
        finished_render()
