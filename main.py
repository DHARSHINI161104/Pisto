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

    from app.gui.main_window import run
    sys.exit(run(fullscreen=args.fullscreen, force_demo=args.demo))


if __name__ == "__main__":
    main()