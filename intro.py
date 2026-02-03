from colours import Colours
import time
import os


def intro():
    os.system("clear")
    print(f"{Colours.FAIL}{Colours.BOLD}{Colours.UNDERLINE}Video is starting...{Colours.END}")
    for countdown in range(3, 0, -1):
        print(f"{Colours.WARNING}{Colours.BOLD}{countdown}{Colours.END}")
        time.sleep(1)
    return True
