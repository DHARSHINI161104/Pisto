"""Write completed games to daily result files (CSV) under config.RESULTS_DIR.

A file per day: results/YYYY-MM-DD.csv. Rows are one per completed game.
The file is rewritten (not appended) so it always reflects the latest totals.
"""

import csv
import os
from datetime import date

import config
from app import db


def _path(day=None):
    day = day or date.today().isoformat()
    return os.path.join(config.RESULTS_DIR, f"{day}.csv")


def write_day(day=None):
    """Rewrite today's results file from the DB. Returns the path or None."""
    day = day or date.today().isoformat()
    games = db.games_on(day)
    path = _path(day)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["user_id", "name", "started_at", "completed_at",
                         "shots", "total", "x_count", "series"])
        for g in games:
            user = db.find_user(g["user_id"]) or {"id": g["user_id"], "name": "?"}
            shots = db.shots_for_game(g["id"])
            series = ";".join(f"{s['shot_no']}:{s['score']:.1f}" for s in shots)
            writer.writerow([
                g["user_id"], user["name"], g["started_at"], g["completed_at"],
                len(shots), f"{g['total']:.1f}", g["x_count"], series,
            ])
    return path


def read_day(day=None):
    """Return the CSV rows for a day as a list of dicts."""
    day = day or date.today().isoformat()
    path = _path(day)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))