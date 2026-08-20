"""Application state shared between the camera pipeline and Flask routes."""

import math
import threading

import config
from app import db
from app.scoring import score_from_distance, is_inner_ten

MODE_IDLE = "idle"           # scanning for a user QR code
MODE_CALIBRATING = "calibrating"  # detecting the target before scoring starts
MODE_SHOOTING = "shooting"   # live shot detection for the active user
MODE_MANUAL = "manual"       # no camera; entry handled by the UI

GUEST_USER_ID = "guest"
GUEST_USER_NAME = "Guest"


class AppState:
    def __init__(self):
        self.lock = threading.RLock()
        self.mode = MODE_IDLE
        self.active_user = None        # {'id','name'} or None
        self.active_game_id = None
        self.game = None               # latest game dict w/ shots
        self.calibration = None
        self.detector = None
        self.calibration_state = "none"   # 'none' | 'searching' | 'ready'
        self.events = []               # recent events: {ts, text, score?}
        self.overlay_jpeg = None       # latest processed view (JPEG bytes)
        self.pipeline_error = None
        self.pending_qr_id = None      # QR seen for an unregistered user

    # ------------------------------------------------------------ helpers --
    def log(self, text, **extra):
        ev = {"text": text, **extra}
        self.events.append(ev)
        self.events = self.events[-80:]

    def set_mode(self, mode):
        with self.lock:
            self.mode = mode

    # ------------------------------------------------------------- users --
    def select_user(self, user_id, name=None):
        """Identify a user (QR or manual). Starts or resumes their game."""
        with self.lock:
            user = db.find_user(user_id)
            if user is None:
                user = db.create_user(user_id, name or user_id)
            self.active_user = {"id": user["id"], "name": user["name"]}
            game = db.active_game_for(user_id)
            if game is None:
                gid = db.start_game(user_id)
            else:
                gid = game["id"]
            self.active_game_id = gid
            self.game = db.game_with_shots(gid)
            self.log(f"User {user['name']} ({user['id']}) ready.")
            return user

    def ensure_session(self):
        """Make sure an active user + game exists so calibration can score.

        When the display panel starts calibration without a shooter selected,
        a Guest session is created automatically. Returns True when a scoring
        session is active.
        """
        with self.lock:
            if self.active_game_id and self.game:
                return True
            if self.active_user is None:
                user = db.find_user(GUEST_USER_ID)
                if user is None:
                    user = db.create_user(GUEST_USER_ID, GUEST_USER_NAME)
                self.active_user = {"id": user["id"], "name": user["name"]}
            game = db.active_game_for(self.active_user["id"])
            if game is None:
                gid = db.start_game(self.active_user["id"])
            else:
                gid = game["id"]
            self.active_game_id = gid
            self.game = db.game_with_shots(gid)
            return True

    def add_manual_shot(self, mm_x=None, mm_y=None, score=None):
        """Record one shot in the active game. Returns the updated shot dict."""
        with self.lock:
            if self.active_game_id is None:
                raise ValueError("No active user selected.")
            game = self.game or db.game_with_shots(self.active_game_id)
            shot_no = len(game["shots"]) + 1
            if shot_no > config.SHOTS_PER_GAME:
                db.finish_game(self.active_game_id)
                raise ValueError("Game already complete (10 shots). Start a new game.")
            if score is None:
                score = score_from_distance((mm_x ** 2 + mm_y ** 2) ** 0.5)
            score = round(float(score), 1)
            is_x = is_inner_ten((mm_x ** 2 + mm_y ** 2) ** 0.5) if mm_x is not None else (score == 10.9)
            db.add_shot(self.active_game_id, shot_no, score, is_x, mm_x, mm_y,
                        mode="manual" if mm_x is None else "tap")
            shot = {"shot_no": shot_no, "score": score, "is_x": is_x,
                    "x_mm": mm_x, "y_mm": mm_y}
            if shot_no == config.SHOTS_PER_GAME:
                db.finish_game(self.active_game_id)
                self.log(f"Game complete: total {self.game_total():.1f}")
            self.refresh_game()
            return shot

    def add_detected_shot(self, mm_x, mm_y):
        """Called by the camera pipeline when a new hole is confirmed."""
        with self.lock:
            if self.mode != MODE_SHOOTING or self.active_game_id is None:
                return
            try:
                shot = self.add_manual_shot(mm_x=mm_x, mm_y=mm_y)
                self.log(f"Shot {shot['shot_no']}: {shot['score']:.1f} "
                         f"(auto, {mm_x:.1f},{mm_y:.1f} mm)", score=shot["score"])
            except ValueError as e:
                self.log(str(e))

    def refresh_game(self):
        if self.active_game_id:
            self.game = db.game_with_shots(self.active_game_id)

    def game_total(self):
        g = self.game or {}
        return round(sum(s["score"] for s in g.get("shots", [])), 1)

    def x_count(self):
        g = self.game or {}
        return sum(1 for s in g.get("shots", []) if s["is_x"])

    def start_new_game(self):
        with self.lock:
            if self.active_user is None:
                raise ValueError("No active user.")
            if self.active_game_id and self.game and \
                    len(self.game["shots"]) and len(self.game["shots"]) < config.SHOTS_PER_GAME:
                db.finish_game(self.active_game_id)
            gid = db.start_game(self.active_user["id"])
            self.active_game_id = gid
            self.game = db.game_with_shots(gid)
            self.log(f"New game started for {self.active_user['name']}.")
            return self.game

    # ------------------------------------------------------------ summary --
    def calibration_info(self):
        """Serialisable summary of the current target calibration."""
        cal = self.calibration
        if cal is None:
            return None
        return {
            "cx": round(cal.cx, 1),
            "cy": round(cal.cy, 1),
            "scale_px_per_mm": round(cal.scale_px_per_mm, 3),
            "aspect": round(cal.aspect, 3),
            "state": self.calibration_state,
            "ready": self.mode == MODE_SHOOTING and self.detector is not None,
        }

    def status_info(self):
        """Derived status flags for the live UI (camera/target/calibration)."""
        target_detected = (self.calibration is not None
                           and self.calibration_state != "none")
        calibration_complete = (self.mode == MODE_SHOOTING
                                and self.detector is not None
                                and self.calibration_state == "ready")
        if calibration_complete:
            status = "READY"
        elif self.mode == MODE_CALIBRATING:
            status = "CALIBRATING"
        elif self.mode == MODE_MANUAL:
            status = "MANUAL"
        else:
            status = "WAITING"
        return {
            "camera": _camera_available(),
            "target_detected": target_detected,
            "calibration_complete": calibration_complete,
            "status": status,
        }

    def public_state(self):
        with self.lock:
            g = self.game or {}
            shots = []
            for s in g.get("shots", []):
                x, y = s["x_mm"], s["y_mm"]
                dist = (math.hypot(x, y)
                        if x is not None and y is not None else None)
                shots.append({
                    "shot_no": s["shot_no"], "score": s["score"],
                    "is_x": bool(s["is_x"]),
                    "x_mm": x, "y_mm": y,
                    "distance_mm": round(dist, 1) if dist is not None else None,
                })
            return {
                "mode": self.mode,
                "user": self.active_user,
                "game_id": self.active_game_id,
                "shots": shots,
                "shot_count": len(shots),
                "shots_per_game": config.SHOTS_PER_GAME,
                "total": self.game_total(),
                "x_count": self.x_count(),
                "camera": _camera_available(),
                "calibration": self.calibration_info(),
                "target_detected": self.calibration is not None
                                   and self.calibration_state != "none",
                "calibration_complete": self.mode == MODE_SHOOTING
                                        and self.detector is not None
                                        and self.calibration_state == "ready",
                "status": self.status_info()["status"],
                "current_shot": shots[-1] if shots else None,
                "session": {
                    "game_id": self.active_game_id,
                    "date": (self.game or {}).get("started_at", "")[:10],
                },
                "events": list(reversed(self.events[-8:])),
                "error": self.pipeline_error,
            }


def _camera_available():
    from app import camera
    return camera.available()


STATE = AppState()