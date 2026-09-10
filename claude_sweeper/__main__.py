import os
import sys

if getattr(sys, "frozen", False):
    os.chdir(sys._MEIPASS)

from claude_sweeper.app import main

if __name__ == "__main__":
    main()
