"""SQLite persistence for users, games and shots.

A *game* is exactly SHOTS_PER_GAME shots by one user on a given day. Games are
never edited after completion; shots are appended while the game is active.
All access goes through this module so the camera thread and Flask threads can
share the database safely (each connection is thread-local).
"""

import os
import sqlite3
import threading
from datetime import date, datetime

from config import SHOTS_PER_GAME, RESULTS_DIR

DB_PATH = os.environ.get("RIFLE_DB", "rifleclub.db")

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,          -- QR code value / manual id
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL REFERENCES users(id),
    started_at  TEXT NOT NULL,
    completed_at TEXT,
    status      TEXT NOT NULL DEFAULT 'active',   -- 'active' | 'done'
    total       REAL NOT NULL DEFAULT 0,
    x_count     INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS shots (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id),
    shot_no INTEGER NOT NULL,
    score   REAL NOT NULL,
    is_x    INTEGER NOT NULL DEFAULT 0,
    x_mm    REAL,
    y_mm    REAL,
    mode    TEXT NOT NULL DEFAULT 'manual',
    UNIQUE(game_id, shot_no)
);
CREATE INDEX IF NOT EXISTS idx_games_user ON games(user_id);
CREATE INDEX IF NOT EXISTS idx_shots_game ON shots(game_id);
"""


def _connect():
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db():
    conn = _connect()
    conn.executescript(SCHEMA)
    conn.commit()
    os.makedirs(RESULTS_DIR, exist_ok=True)


# ---------------------------------------------------------------- users ----
def find_user(user_id: str):
    row = _connect().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_users():
    rows = _connect().execute(
        "SELECT * FROM users ORDER BY name COLLATE NOCASE"
    ).fetchall()
    return [dict(r) for r in rows]


def create_user(user_id: str, name: str):
    conn = _connect()
    conn.execute(
        "INSERT OR IGNORE INTO users (id, name, created_at) VALUES (?,?,?)",
        (user_id, name, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return find_user(user_id)


# ---------------------------------------------------------------- games ----
def start_game(user_id: str):
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO games (user_id, started_at) VALUES (?,?)",
        (user_id, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return cur.lastrowid


def active_game_for(user_id: str):
    row = _connect().execute(
        "SELECT * FROM games WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def finish_game(game_id: int):
    conn = _connect()
    row = conn.execute("SELECT game_id, COUNT(*) FROM shots WHERE game_id=? GROUP BY game_id",
                       (game_id,)).fetchone()
    count = row[1] if row else 0
    totals = conn.execute(
        "SELECT SUM(score) AS total, SUM(is_x) AS x FROM shots WHERE game_id=?",
        (game_id,),
    ).fetchone()
    total = totals["total"] or 0.0
    x_count = totals["x"] or 0
    conn.execute(
        "UPDATE games SET status='done', completed_at=?, total=?, x_count=? WHERE id=?",
        (datetime.now().isoformat(timespec="seconds"), round(total, 1), x_count, game_id),
    )
    conn.commit()


# ---------------------------------------------------------------- shots ----
def add_shot(game_id: int, shot_no: int, score: float, is_x: bool,
             x_mm=None, y_mm=None, mode="manual"):
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO shots (game_id, shot_no, score, is_x, x_mm, y_mm, mode)"
        " VALUES (?,?,?,?,?,?,?)",
        (game_id, shot_no, score, int(bool(is_x)), x_mm, y_mm, mode),
    )
    conn.commit()


def shots_for_game(game_id: int):
    rows = _connect().execute(
        "SELECT * FROM shots WHERE game_id=? ORDER BY shot_no", (game_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def games_for_user(user_id: str):
    rows = _connect().execute(
        "SELECT * FROM games WHERE user_id=? ORDER BY started_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def game_with_shots(game_id: int):
    game = _connect().execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
    if not game:
        return None
    g = dict(game)
    g["shots"] = shots_for_game(game_id)
    return g


def games_on(date_str: str):
    """All completed games started on a given date (YYYY-MM-DD), newest first."""
    rows = _connect().execute(
        "SELECT * FROM games WHERE status='done' AND substr(started_at,1,10)=? "
        "ORDER BY started_at DESC, id DESC",
        (date_str,),
    ).fetchall()
    return [dict(r) for r in rows]


def today_results():
    return games_on(date.today().isoformat())
