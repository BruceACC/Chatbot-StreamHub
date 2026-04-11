"""
main.py — KickBot entry point
"""

import sys
import os

# Ensure sessions dir exists relative to the exe location
if getattr(sys, "frozen", False):
    # Running as PyInstaller bundle — set CWD to exe directory
    os.chdir(os.path.dirname(sys.executable))

from gui.main_window import MainWindow


def main():
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
