"""GUI entry point for the electronic rifle shooting scoring application.

Works with or without a camera:
    python3 main.py                  # demo mode if no camera, live if found
    python3 main.py --demo           # force demo mode (no camera needed)
    python3 main.py --fullscreen     # competition fullscreen display

On Windows:  .\\.venv\\Scripts\\python.exe main.py
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Electronic Rifle Shooting Scoring System (GUI)")
    parser.add_argument("--fullscreen", action="store_true",
                        help="start in fullscreen (competition) mode")
    parser.add_argument("--demo", action="store_true",
                        help="force demo mode even if a camera is present")
    args = parser.parse_args()

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QSharedMemory

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Electronic Rifle Scoring")

    # Single-instance guard: only one Display Panel window may exist. A second
    # launch (e.g. double-clicking the launcher again) exits immediately
    # instead of opening a duplicate GUI.
    guard = QSharedMemory("rifle_club_display_panel")
    if not guard.create(1):
        if guard.error() == QSharedMemory.AlreadyExists:
            return 0

    from app.gui.main_window import run
    sys.exit(run(fullscreen=args.fullscreen, force_demo=args.demo))


if __name__ == "__main__":
    main()