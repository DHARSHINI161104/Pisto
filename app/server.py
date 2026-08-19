"""Flask routes and JSON API."""

import os
from datetime import date

from flask import Flask, Response, jsonify, render_template, request, send_file

import config
from app import db, results, state
from app.target_view import (target_geometry, target_svg_page, target_svg,
                             target_display_svg)

MODE_TO_TEMPLATE = {
    state.MODE_MANUAL: "manual.html",
    state.MODE_IDLE: "idle.html",
    state.MODE_CALIBRATING: "calibrating.html",
    state.MODE_SHOOTING: "shooting.html",
}


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app():
    app = Flask(__name__,
                template_folder=os.path.join(_ROOT, "templates"),
                static_folder=os.path.join(_ROOT, "static"))
    db.init_db()

    # ------------------------------------------------------------- pages --
    @app.route("/")
    def index():
        st = state.STATE.public_state()
        template = MODE_TO_TEMPLATE.get(st["mode"], "idle.html")
        return render_template(template, st=st, cfg=config,
                               geometry=target_geometry(),
                               users=db.list_users(),
                               target_svg=target_svg())

    @app.route("/display")
    def display():
        st = state.STATE.public_state()
        shots = st["shots"]
        target_svg_html = target_display_svg(
            shots=shots,
            current_shot_no=(st["current_shot"] or {}).get("shot_no"))
        return render_template("display.html", st=st, cfg=config,
                               geometry=target_geometry(),
                               target_svg=target_svg_html)

    @app.route("/history")
    @app.route("/history/<user_id>")
    def history(user_id=None):
        users = db.list_users()
        user = db.find_user(user_id) if user_id else None
        games = db.games_for_user(user_id) if user else None
        for g in games or []:
            g["shots"] = db.shots_for_game(g["id"])
        return render_template("history.html", users=users, user=user,
                               games=games, date=date.today().isoformat())

    @app.route("/print/target")
    def print_target():
        return Response(target_svg_page(), mimetype="text/html")

    # ----------------------------------------------------------- exports --
    @app.route("/export/results")
    @app.route("/export/results/<day>")
    def export_results(day=None):
        day = day or date.today().isoformat()
        path = results.write_day(day)
        if not os.path.exists(path):
            return jsonify({"ok": False, "error": "No results for that day"}), 404
        return send_file(path, as_attachment=True,
                         download_name=f"results-{day}.csv")

    @app.route("/results/today")
    def results_today():
        path = results.write_day()
        return render_template("results.html", rows=results.read_day(),
                               day=date.today().isoformat(), path=path)

    # ----------------------------------------------------------- streams --
    @app.route("/video_feed")
    def video_feed():
        def gen():
            st = state.STATE
            import time
            while True:
                frame = st.overlay_jpeg
                if frame:
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                           + frame + b"\r\n")
                time.sleep(0.04)
        return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

    # -------------------------------------------------------------- api ---
    @app.route("/api/state")
    def api_state():
        return jsonify(state.STATE.public_state())

    @app.route("/api/users")
    def api_users():
        return jsonify(db.list_users())

    @app.post("/api/select_user")
    def api_select_user():
        data = request.get_json(silent=True) or request.form
        user_id = (data.get("user_id") or "").strip()
        name = (data.get("name") or "").strip()
        if not user_id:
            return jsonify({"ok": False, "error": "Missing user_id"}), 400
        st = state.STATE
        user = st.select_user(user_id, name or None)
        st.pending_qr_id = None
        st.calibration = None
        st.detector = None
        st.calibration_state = "none"
        if st.mode != state.MODE_MANUAL:
            # Camera present: calibrate the target before any shots are scored.
            st.set_mode(state.MODE_CALIBRATING)
            st.log("Aim the camera at the target to calibrate.")
        return jsonify({"ok": True, "user": user,
                        "state": st.public_state()})

    @app.post("/api/start_game")
    def api_start_game():
        try:
            game = state.STATE.start_new_game()
            return jsonify({"ok": True, "game": game})
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.post("/api/shot")
    def api_shot():
        data = request.get_json(silent=True) or request.form
        try:
            if data.get("score") is not None:
                shot = state.STATE.add_manual_shot(score=float(data["score"]))
            else:
                mm_x = float(data.get("x_mm", 0))
                mm_y = float(data.get("y_mm", 0))
                shot = state.STATE.add_manual_shot(mm_x=mm_x, mm_y=mm_y)
            return jsonify({"ok": True, "shot": shot,
                            "state": state.STATE.public_state()})
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.post("/api/reset_calibration")
    def api_reset_calibration():
        st = state.STATE
        st.calibration = None
        st.detector = None
        st.calibration_state = "none"
        if st.mode != state.MODE_MANUAL:
            st.set_mode(state.MODE_CALIBRATING)
            st.log("Re-calibrating - keep the target centred in view.")
        return jsonify({"ok": True})

    @app.post("/api/clear_user")
    def api_clear_user():
        st = state.STATE
        st.active_user = None
        st.active_game_id = None
        st.game = None
        camera_on = False
        try:
            from app import camera
            camera_on = camera.available()
        except Exception:
            pass
        st.set_mode(state.MODE_IDLE if camera_on else state.MODE_MANUAL)
        return jsonify({"ok": True})

    return app