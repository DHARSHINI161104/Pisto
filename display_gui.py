"""Standalone desktop Display Panel.

Double-click 'Display Panel.bat' to open the shooting scoreboard as a native
desktop window - no web server, no browser, no URL. The exact existing display
page (target, rings, shot markers, scoreboard, total, history) is rendered in a
QtWebEngine window and fed live state + camera frames from the same
camera/detection/scoring pipeline used by the web app.
"""

import base64
import json
import os

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

import config
from app import pipeline, state
from app.server import calibrate_state, capture_state, create_app
from app.target_view import target_display_svg, target_geometry

ROOT = os.path.dirname(os.path.abspath(__file__))


class DisplayBridge(QObject):
    """JS <-> Python bridge: pushes live state and frames to the page."""

    frameReady = Signal(str)      # base64 JPEG of the latest processed frame
    stateReady = Signal(str)      # JSON payload of state.STATE.public_state()
    actionResult = Signal(str)    # JSON {path, ok, error?}

    @Slot(str)
    def action(self, path):
        try:
            if path == "/api/calibrate":
                payload, _ = calibrate_state()
                ok = bool(payload.get("ok", True))
                error = payload.get("error")
            elif path == "/api/capture":
                payload, _ = capture_state()
                ok = bool(payload.get("ok", True))
                error = payload.get("error")
            elif path == "/api/next_player":
                state.STATE.next_player()
                ok, error = True, None
            else:
                ok, error = False, "unknown action " + path
        except ValueError as exc:
            ok, error = False, str(exc)
        self.actionResult.emit(json.dumps({
            "path": path, "ok": ok,
            "error": error if error else None,
        }))
        self.stateReady.emit(json.dumps(state.STATE.public_state()))


def render_display_html():
    """Render the existing display.html with the shared pipeline state.

    The HTML/CSS/markers/scoreboard are unchanged; only the data layer is
    swapped from HTTP to the in-process bridge, and the stylesheet is inlined
    so the standalone window needs no /static server.
    """
    app = create_app()
    with app.app_context():
        st = state.STATE.public_state()
        target_svg_html = target_display_svg(
            shots=st["shots"],
            current_shot_no=(st["current_shot"] or {}).get("shot_no"))
        html = app.jinja_env.get_template("display.html").render(
            st=st, cfg=config, geometry=target_geometry(),
            target_svg=target_svg_html)

    css_path = os.path.join(ROOT, "static", "css", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as fh:
            css = fh.read()
        html = html.replace(
            '<link rel="stylesheet" href="/static/css/style.css">',
            "<style>" + css + "</style>")

    # Bootstraps the QWebChannel bridge after the page scripts have run (so
    # window.onDesktopBridgeReady is already defined by the page).
    bridge_script = (
        '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'
        '<script>'
        'new QWebChannel(qt.webChannelTransport, function(channel){'
        '  window.desktopBridge = channel.objects.bridge;'
        '  if (window.onDesktopBridgeReady) window.onDesktopBridgeReady();'
        '});'
        '</script>'
    )
    html = html.replace("</body>", bridge_script + "</body>")
    return html


class DisplayWindow:
    def __init__(self):
        self.window = QMainWindow()
        self.window.setWindowTitle("Rifle Club - Score Display")
        self.window.resize(1280, 800)
        self.view = QWebEngineView()
        self.window.setCentralWidget(self.view)

        self.channel = QWebChannel()
        self.bridge = DisplayBridge()
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        self.view.setHtml(render_display_html(),
                          QUrl.fromLocalFile(ROOT + os.sep))

        # Push the latest processed camera frame to the page's <img>.
        self.video_timer = QTimer()
        self.video_timer.timeout.connect(self._push_frame)
        self.video_timer.start(50)

        # Push the live scoreboard state to the page (mirrors the web page's
        # 500 ms poll, but in-process).
        self.state_timer = QTimer()
        self.state_timer.timeout.connect(self._push_state)
        self.state_timer.start(500)

    def _push_frame(self):
        jpeg = state.STATE.overlay_jpeg
        if jpeg:
            self.bridge.frameReady.emit(
                base64.b64encode(jpeg).decode("ascii"))

    def _push_state(self):
        self.bridge.stateReady.emit(json.dumps(state.STATE.public_state()))

    def show(self):
        self.window.show()


def main():
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Rifle Club Score Display")
    pipeline.start()
    win = DisplayWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())