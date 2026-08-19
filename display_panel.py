"""Display Panel launcher (started by 'Display Panel.bat').

Starts the existing scoring server + camera pipeline exactly as run.py does,
waits for it to be ready, then opens the existing professional scoreboard
(/display) in the default browser. The panel stays ready even before a camera
is connected; when the webcam/scoring pipeline detects shots, the SAME open
panel updates automatically. If a server is already running, this just opens
the panel. Nothing in the camera/scoring pipeline is modified.
"""

import os
import subprocess
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
PANEL_URL = "http://127.0.0.1:5000/display"
SERVER_LOG = os.path.join(ROOT, "panel_server.log")
PYTHON = os.path.join(ROOT, ".venv", "Scripts", "python.exe")


def _panel_up():
    try:
        urllib.request.urlopen(PANEL_URL, timeout=1).close()
        return True
    except Exception:
        return False


def main():
    if not _panel_up():
        log = open(SERVER_LOG, "a", encoding="utf-8")
        subprocess.Popen(
            [PYTHON, "run.py"],
            cwd=ROOT,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for _ in range(60):
            if _panel_up():
                break
            time.sleep(0.5)
    import webbrowser
    webbrowser.open(PANEL_URL)


if __name__ == "__main__":
    main()