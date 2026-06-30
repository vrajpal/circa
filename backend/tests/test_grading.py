"""
Unit tests for app/services/grading.py

Pure functions — no DB, no fixtures. We lean on this to cover every edge:
home/away covers, pushes, ties, and games with no line.
"""
from app.services.grading import (
    grade_game,
    grade_ats_pick,
    grade_survivor_pick,
    HOME,
    AWAY,
    PUSH,
)


class TestGradeGame:
    def test_no_score_returns_none(self):
        assert grade_game(None, None, -3.0, 45.0) is None
        assert grade_game(21, None, -3.0, 45.0) is None

    def test_straight_up_winner(self):
        g = grade_game(24, 20, None, None)
        assert g.su_winner == HOME
        g = grade_game(17, 27, None, None)
        assert g.su_winner == AWAY

    def test_tie_has_no_su_winner(self):
        g = grade_game(20, 20, None, None)
        assert g.su_winner is None

    def test_home_favourite_covers(self):
        # home wins by 10 as a 7-point favourite (spread_home -7) -> home covers
        g = grade_game(30, 20, -7.0, None)
        assert g.ats_winner == HOME
        assert g.ats_margin_home == 3.0

    def test_home_favourite_fails_to_cover(self):
        # home wins by 4 as a 7-point favourite -> away covers
        g = grade_game(24, 20, -7.0, None)
        assert g.ats_winner == AWAY
        assert g.ats_margin_home == -3.0

    def test_ats_push(self):
        # home wins by exactly the spread -> push
        g = grade_game(27, 20, -7.0, None)
        assert g.ats_winner is None
        assert g.ats_margin_home == 0.0

    def test_home_underdog_covers_outright(self):
        # home is a 3-point dog (spread_home +3) and wins -> home covers easily
        g = grade_game(21, 17, 3.0, None)
        assert g.ats_winner == HOME
        assert g.ats_margin_home == 7.0

    def test_no_spread_leaves_ats_unset(self):
        g = grade_game(24, 20, None, 50.0)
        assert g.ats_winner is None
        assert g.ats_margin_home is None  # disambiguates "no line" from "push"

    def test_total_over_under_push(self):
        assert grade_game(28, 24, None, 45.0).total_result == "over"   # 52 > 45
        assert grade_game(10, 7, None, 45.0).total_result == "under"   # 17 < 45
        assert grade_game(24, 21, None, 45.0).total_result == PUSH     # 45 == 45

    def test_no_total_leaves_total_unset(self):
        assert grade_game(28, 24, -3.0, None).total_result is None


class TestGradeAtsPick:
    def test_pick_winner_side(self):
        g = grade_game(30, 20, -7.0, None)  # home covers
        assert grade_ats_pick(HOME, g) == "win"
        assert grade_ats_pick(AWAY, g) == "loss"

    def test_push_for_both_sides(self):
        g = grade_game(27, 20, -7.0, None)  # push
        assert grade_ats_pick(HOME, g) == PUSH
        assert grade_ats_pick(AWAY, g) == PUSH

    def test_no_line_returns_none(self):
        g = grade_game(30, 20, None, None)
        assert grade_ats_pick(HOME, g) is None


class TestGradeSurvivorPick:
    def test_pick_winner_survives(self):
        g = grade_game(24, 20, None, None)  # home wins SU
        assert grade_survivor_pick(HOME, g) == "win"
        assert grade_survivor_pick(AWAY, g) == "loss"

    def test_tie_is_push(self):
        g = grade_game(20, 20, None, None)
        assert grade_survivor_pick(HOME, g) == PUSH

    def test_survivor_ignores_spread(self):
        # home loses SU but covered the spread; survivor still grades on SU
        g = grade_game(20, 24, 7.0, None)  # away wins SU, home covers
        assert grade_survivor_pick(HOME, g) == "loss"
        assert grade_survivor_pick(AWAY, g) == "win"
