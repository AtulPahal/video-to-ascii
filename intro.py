from __future__ import print_function
from colours import Colours
import time


def intro():
    print("\033[2J\033[H", end="", flush=True)
    print(f"{Colours.FAIL}{Colours.BOLD}{Colours.UNDERLINE}Video is starting...{Colours.END}")
    for countdown in range(3, 0, -1):
        print(f"{Colours.WARNING}{Colours.BOLD}{countdown}{Colours.END}")
        time.sleep(1)
    return True 
