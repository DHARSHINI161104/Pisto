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