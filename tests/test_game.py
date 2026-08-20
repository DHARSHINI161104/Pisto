import pytest

import config
from app import db, results, state


@pytest.fixture(autouse=True)
def clean_db():
    db.init_db()
    conn = db._connect()
    conn.execute("DELETE FROM shots")
    conn.execute("DELETE FROM games")
    conn.execute("DELETE FROM users")
    conn.commit()
    yield


def _fresh_state():
    st = state.AppState()
    return st


def test_create_and_select_user():
    st = _fresh_state()
    user = st.select_user("CLUB-001", "Alice")
    assert user["id"] == "CLUB-001"
    assert st.active_user["name"] == "Alice"
    assert st.active_game_id is not None
    assert len(st.game["shots"]) == 0


def test_ten_shot_game_and_cap():
    st = _fresh_state()
    st.select_user("CLUB-001", "Alice")
    for n in range(config.SHOTS_PER_GAME):
        st.add_manual_shot(score=10.0)
    assert len(st.game["shots"]) == 10
    assert st.game_total() == 100.0
    with pytest.raises(ValueError):
        st.add_manual_shot(score=10.0)   # 11th shot rejected


def test_x_count():
    st = _fresh_state()
    st.select_user("CLUB-001", "Alice")
    st.add_manual_shot(mm_x=0.0, mm_y=0.0)   # inner ten
    st.add_manual_shot(mm_x=4.0, mm_y=0.0)   # 10.3, not X
    assert st.game["shots"][0]["score"] == 10.9
    assert st.game["shots"][0]["is_x"]  # db stores is_x as 0/1
    assert st.x_count() == 1


def test_mm_scoring_via_manual():
    st = _fresh_state()
    st.select_user("CLUB-001", "Alice")
    shot = st.add_manual_shot(mm_x=10.0, mm_y=0.0)  # d=10 -> 9.4
    assert shot["score"] == 9.4


def test_new_game_after_completion():
    st = _fresh_state()
    st.select_user("CLUB-001", "Alice")
    for _ in range(config.SHOTS_PER_GAME):
        st.add_manual_shot(score=9.5)
    games = db.games_for_user("CLUB-001")
    assert len(games) == 1
    assert games[0]["status"] == "done"
    assert games[0]["total"] == 95.0
    st.start_new_game()
    assert len(st.game["shots"]) == 0
    assert len(db.games_for_user("CLUB-001")) == 2


def test_resume_active_game():
    st = _fresh_state()
    st.select_user("CLUB-001", "Alice")
    st.add_manual_shot(score=8.0)
    st2 = _fresh_state()
    st2.select_user("CLUB-001")
    assert len(st2.game["shots"]) == 1
    assert st2.game["shots"][0]["score"] == 8.0


def test_results_file_written():
    st = _fresh_state()
    st.select_user("CLUB-001", "Alice")
    for _ in range(config.SHOTS_PER_GAME):
        st.add_manual_shot(score=9.0)
    path = results.write_day()
    assert path.endswith(".csv")
    rows = results.read_day()
    assert len(rows) == 1
    assert rows[0]["user_id"] == "CLUB-001"
    assert rows[0]["total"] == "90.0"
    assert rows[0]["shots"] == "10"


def test_ensure_session_creates_guest():
    st = _fresh_state()
    assert st.active_game_id is None
    assert st.ensure_session() is True
    assert st.active_user["id"] == state.GUEST_USER_ID
    assert st.active_user["name"] == state.GUEST_USER_NAME
    assert st.active_game_id is not None
    # A second call reuses the same session, not a new game.
    game_id = st.active_game_id
    assert st.ensure_session() is True
    assert st.active_game_id == game_id


def test_ensure_session_reuses_selected_user():
    st = _fresh_state()
    st.select_user("CLUB-001", "Alice")
    game_id = st.active_game_id
    assert st.ensure_session() is True
    assert st.active_user["id"] == "CLUB-001"
    assert st.active_game_id == game_id


def test_round_complete_after_ten_shots():
    st = _fresh_state()
    st.ensure_session()
    assert st.player == "PLAYER 01"
    assert st.round_complete is False
    for _ in range(config.SHOTS_PER_GAME):
        st.add_manual_shot(score=10.0)
    assert st.round_complete is True
    assert len(st.game["shots"]) == 10
    # Shot 11 is rejected even on the detected-shot path.
    st.mode = state.MODE_SHOOTING
    st.add_detected_shot(3.0, 3.0)
    assert len(st.game["shots"]) == 10
    with pytest.raises(ValueError):
        st.add_manual_shot(score=10.0)


def test_next_player_starts_clean_round():
    st = _fresh_state()
    st.ensure_session()
    for _ in range(config.SHOTS_PER_GAME):
        st.add_manual_shot(score=9.0)
    st.next_player()
    assert st.player == "PLAYER 02"
    assert st.round_complete is False
    assert len(st.game["shots"]) == 0
    assert st.game_total() == 0.0
    pub = st.public_state()
    assert pub["player"] == "PLAYER 02"
    assert pub["round_complete"] is False
    assert pub["shot_count"] == 0
    assert pub["total"] == 0.0


def test_next_player_advances_counter():
    st = _fresh_state()
    st.ensure_session()
    st.next_player()
    st.next_player()
    assert st.player == "PLAYER 03"