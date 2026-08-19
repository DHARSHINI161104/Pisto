"""Main GUI window. One application for both demo and live camera modes.

* Demo mode (no camera / forced): buttons drive a GuiSession with sample shots.
* Live mode (camera detected): a LiveWorker thread feeds detected shots into
  the same GuiSession. The window itself never scores anything.
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication, QLabel, QMainWindow, QSplitter,
                               QToolBar, QVBoxLayout, QWidget)

from app import camera
from app.gui.camera_widget import CameraWidget
from app.gui.live import LiveWorker
from app.gui.scoreboard_widget import ScoreboardWidget
from app.gui.session import GuiSession
from app.gui.target_widget import TargetWidget


class MainWindow(QMainWindow):
    def __init__(self, force_demo=False):
        super().__init__()
        self.setWindowTitle("Electronic Rifle Shooting Scoring System")
        self.resize(1080, 640)

        self.session = GuiSession(self)
        self.worker = None

        self._build_ui()
        self._build_toolbar()
        self._build_statusbar()

        self.session.shots_changed.connect(self._refresh)
        self.session.status_changed.connect(self._refresh_status)
        self._refresh()

        self._start_camera(force_demo)

    # --------------------------------------------------------------- UI --
    def _build_ui(self):
        self.target = TargetWidget()
        self.camera_view = CameraWidget()
        self.camera_view.hide()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.addWidget(self.target, 1)
        left_layout.addWidget(self.camera_view)

        self.scoreboard = ScoreboardWidget()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.scoreboard)
        splitter.setSizes([700, 360])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        self.setCentralWidget(splitter)

    def _build_toolbar(self):
        bar = QToolBar("Controls")
        bar.setMovable(False)
        self.addToolBar(bar)

        self.add_demo_act = QAction("Add Demo Shot", self)
        self.add_demo_act.triggered.connect(self.session.add_demo_shot)
        bar.addAction(self.add_demo_act)

        self.clear_act = QAction("Clear Shots", self)
        self.clear_act.triggered.connect(self.session.clear_shots)
        bar.addAction(self.clear_act)

        self.reset_act = QAction("Reset Match", self)
        self.reset_act.triggered.connect(self.session.reset_match)
        bar.addAction(self.reset_act)

        bar.addSeparator()

        self.show_camera_act = QAction("Show Camera", self)
        self.show_camera_act.setCheckable(True)
        self.show_camera_act.triggered.connect(self._toggle_camera_view)
        bar.addAction(self.show_camera_act)

        self.fullscreen_act = QAction("Fullscreen", self)
        self.fullscreen_act.setCheckable(True)
        self.fullscreen_act.triggered.connect(self._toggle_fullscreen)
        bar.addAction(self.fullscreen_act)

        bar.addSeparator()

        self.mode_act = QAction("Use Camera", self)
        self.mode_act.triggered.connect(self._toggle_mode)
        bar.addAction(self.mode_act)

    def _build_statusbar(self):
        self.sys_status = QLabel("SYSTEM: READY")
        self.cam_status = QLabel("CAMERA: STANDBY")
        self.mode_status = QLabel("MODE: DEMO")
        for lbl in (self.sys_status, self.cam_status, self.mode_status):
            lbl.setStyleSheet("padding: 2px 14px;")
            self.statusBar().addPermanentWidget(lbl)

    # ------------------------------------------------------------ updates --
    def _refresh(self):
        self.target.set_shots(self.session.shots)
        self.scoreboard.refresh(self.session)

    def _refresh_status(self):
        mode = self.session.mode.upper()
        cam = self.session.camera_state.upper()
        self.sys_status.setText(f"SYSTEM: {self.session.system_state}")
        self.cam_status.setText(f"CAMERA: {cam}")
        self.mode_status.setText(f"MODE: {mode}")

        live = self.session.mode == "live"
        self.add_demo_act.setEnabled(not live)
        self.mode_act.setText("Demo Mode" if live else "Use Camera")
        self.show_camera_act.setEnabled(live)

    # ------------------------------------------------------------- camera --
    def _start_camera(self, force_demo):
        if not force_demo:
            camera.start()
            if camera.available():
                self._enter_live()
                return
        self._enter_demo(seed=True)

    def _enter_live(self):
        self.session.set_live()
        self.worker = LiveWorker(self)
        self.worker.shot_detected.connect(self._on_shot)
        self.worker.frame_ready.connect(self.camera_view.set_frame)
        self.worker.status_changed.connect(self._on_camera_status)
        self.worker.start()
        self.show_camera_act.setChecked(True)
        self.camera_view.show()

    def _enter_demo(self, seed=False):
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(3000)
            self.worker = None
        self.camera_view.set_standby()
        self.show_camera_act.setChecked(False)
        self.camera_view.hide()
        self.session.set_demo()
        if seed and not self.session.shots:
            for _ in range(3):
                self.session.add_demo_shot()

    def _on_shot(self, mm_x, mm_y):
        self.session.add_shot(mm_x, mm_y)

    def _on_camera_status(self, state):
        # Neutral camera states: READY (no camera), CONNECTED (found),
        # ACTIVE (processing). Never show a negative message for no camera.
        display = {"connected": "connected", "searching": "active",
                   "ready": "active", "standby": "ready"}.get(state, state)
        self.session.set_camera_state(display)

    def _toggle_mode(self):
        if self.session.mode == "live":
            self._enter_demo()
        else:
            camera.start()
            if camera.available():
                self._enter_live()
            else:
                self.session.set_camera_state("ready")

    # ----------------------------------------------------------- toggles --
    def _toggle_camera_view(self):
        self.camera_view.setVisible(self.show_camera_act.isChecked())

    def _toggle_fullscreen(self):
        if self.fullscreen_act.isChecked():
            self.showFullScreen()
        else:
            self.showNormal()

    def closeEvent(self, event):
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(3000)
        super().closeEvent(event)


def run(fullscreen=False, force_demo=False):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Electronic Rifle Scoring")
    win = MainWindow(force_demo=force_demo)
    win.showFullScreen() if fullscreen else win.show()
    return app.exec()