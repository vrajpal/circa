"""Integration tests for the /api/team-stats/* endpoints.

Uses the same in-memory DB and rollback fixture pattern as the rest of
the test suite. No network calls — stats are seeded directly into the DB.
"""
from datetime import datetime

import pytest

from app.models.team_stats import TeamStatSnapshot, TeamStanding


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def kc_stats(db_session, teams):
    """Stat snapshots for KC across two weeks."""
    kc = teams["KC"]
    week1 = TeamStatSnapshot(
        team_id=kc.id, season=2025, week=1, source="espn",
        games_played=1,
        points_per_game=34.0,
        total_yards_per_game=420.0,
        passing_yards_per_game=290.0,
        rushing_yards_per_game=130.0,
        turnovers_per_game=0.0,
        red_zone_attempts=4,
        red_zone_td_pct=75.0,
        third_down_pct=52.0,
        points_allowed_per_game=17.0,
        yards_allowed_per_game=310.0,
        passing_yards_allowed_per_game=200.0,
        rushing_yards_allowed_per_game=110.0,
        sacks_per_game=3.0,
        takeaways_per_game=2.0,
        point_differential_per_game=17.0,
        fetched_at=datetime(2025, 9, 15),
    )
    week2 = TeamStatSnapshot(
        team_id=kc.id, season=2025, week=2, source="espn",
        games_played=2,
        points_per_game=31.5,
        total_yards_per_game=400.0,
        passing_yards_per_game=275.0,
        rushing_yards_per_game=125.0,
        turnovers_per_game=0.5,
        red_zone_attempts=8,
        red_zone_td_pct=62.5,
        third_down_pct=48.0,
        points_allowed_per_game=20.0,
        yards_allowed_per_game=330.0,
        passing_yards_allowed_per_game=220.0,
        rushing_yards_allowed_per_game=110.0,
        sacks_per_game=2.5,
        takeaways_per_game=1.5,
        point_differential_per_game=11.5,
        fetched_at=datetime(2025, 9, 22),
    )
    db_session.add_all([week1, week2])
    db_session.flush()
    return [week1, week2]


@pytest.fixture()
def buf_stats(db_session, teams):
    """One stat snapshot for BUF."""
    buf = teams["BUF"]
    snap = TeamStatSnapshot(
        team_id=buf.id, season=2025, week=2, source="espn",
        games_played=2,
        points_per_game=28.0,
        total_yards_per_game=380.0,
        passing_yards_per_game=260.0,
        rushing_yards_per_game=120.0,
        turnovers_per_game=1.0,
        red_zone_attempts=7,
        red_zone_td_pct=57.0,
        third_down_pct=44.0,
        points_allowed_per_game=22.0,
        yards_allowed_per_game=350.0,
        passing_yards_allowed_per_game=240.0,
        rushing_yards_allowed_per_game=110.0,
        sacks_per_game=2.0,
        takeaways_per_game=1.0,
        point_differential_per_game=6.0,
        fetched_at=datetime(2025, 9, 22),
    )
    db_session.add(snap)
    db_session.flush()
    return snap


@pytest.fixture()
def kc_standing(db_session, teams):
    kc = teams["KC"]
    s = TeamStanding(
        team_id=kc.id, season=2025, source="espn",
        wins=2, losses=0, ties=0, win_pct=1.0,
        division_rank=1, conference_rank=1, playoff_seed=1,
        strength_of_schedule=0.48,
        home_wins=1, home_losses=0,
        away_wins=1, away_losses=0,
        updated_at=datetime(2025, 9, 22),
    )
    db_session.add(s)
    db_session.flush()
    return s


@pytest.fixture()
def buf_standing(db_session, teams):
    buf = teams["BUF"]
    s = TeamStanding(
        team_id=buf.id, season=2025, source="espn",
        wins=2, losses=0, ties=0, win_pct=1.0,
        division_rank=1, conference_rank=2, playoff_seed=2,
        strength_of_schedule=0.51,
        home_wins=1, home_losses=0,
        away_wins=1, away_losses=0,
        updated_at=datetime(2025, 9, 22),
    )
    db_session.add(s)
    db_session.flush()
    return s


# ---------------------------------------------------------------------------
# GET /api/team-stats/stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_returns_latest_snapshot_per_team(self, client, kc_stats, buf_stats):
        resp = client.get("/api/team-stats/stats", params={"season": 2025})
        assert resp.status_code == 200
        data = resp.json()
        # KC has two snapshots; should return only the week=2 one
        kc_rows = [r for r in data if r["team"]["abbreviation"] == "KC"]
        assert len(kc_rows) == 1
        assert kc_rows[0]["week"] == 2

    def test_filter_by_team(self, client, kc_stats):
        resp = client.get("/api/team-stats/stats", params={"season": 2025, "team": "KC"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["team"]["abbreviation"] == "KC"

    def test_filter_by_week_returns_specific_snapshot(self, client, kc_stats):
        resp = client.get("/api/team-stats/stats", params={"season": 2025, "week": 1, "team": "KC"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["week"] == 1

    def test_unknown_team_returns_404(self, client):
        resp = client.get("/api/team-stats/stats", params={"team": "ZZZ"})
        assert resp.status_code == 404

    def test_no_data_returns_empty_list(self, client, teams):
        resp = client.get("/api/team-stats/stats", params={"season": 2025})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_snapshot_shape(self, client, kc_stats):
        resp = client.get("/api/team-stats/stats", params={"season": 2025, "team": "KC"})
        row = resp.json()[0]
        assert "points_per_game" in row
        assert "points_allowed_per_game" in row
        assert "point_differential_per_game" in row
        assert "team" in row
        assert row["team"]["abbreviation"] == "KC"


# ---------------------------------------------------------------------------
# GET /api/team-stats/stats/{team_abbr}/history
# ---------------------------------------------------------------------------

class TestGetStatsHistory:
    def test_returns_all_weeks_in_order(self, client, kc_stats):
        resp = client.get("/api/team-stats/stats/KC/history", params={"season": 2025})
        assert resp.status_code == 200
        weeks = [r["week"] for r in resp.json()]
        assert weeks == [1, 2]

    def test_unknown_team_returns_404(self, client):
        resp = client.get("/api/team-stats/stats/ZZZ/history")
        assert resp.status_code == 404

    def test_empty_history_returns_empty_list(self, client, teams):
        resp = client.get("/api/team-stats/stats/KC/history", params={"season": 2025})
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/team-stats/rankings
# ---------------------------------------------------------------------------

class TestGetRankings:
    def test_ranks_by_points_per_game_descending(self, client, kc_stats, buf_stats):
        resp = client.get(
            "/api/team-stats/rankings",
            params={"stat": "points_per_game", "season": 2025},
        )
        assert resp.status_code == 200
        data = resp.json()
        abbrs = [r["team"]["abbreviation"] for r in data]
        # KC (31.5 ppg) should rank above BUF (28.0 ppg)
        assert abbrs.index("KC") < abbrs.index("BUF")

    def test_ascending_order_for_defensive_stat(self, client, kc_stats, buf_stats):
        resp = client.get(
            "/api/team-stats/rankings",
            params={"stat": "points_allowed_per_game", "season": 2025, "ascending": "true"},
        )
        assert resp.status_code == 200
        data = resp.json()
        abbrs = [r["team"]["abbreviation"] for r in data]
        # KC (17 ppg allowed) is better defense than BUF (22 ppg allowed)
        assert abbrs.index("KC") < abbrs.index("BUF")

    def test_invalid_stat_returns_400(self, client):
        resp = client.get(
            "/api/team-stats/rankings",
            params={"stat": "fake_column", "season": 2025},
        )
        assert resp.status_code == 400
        assert "fake_column" in resp.json()["detail"]

    def test_no_data_returns_empty_list(self, client, teams):
        resp = client.get(
            "/api/team-stats/rankings",
            params={"stat": "points_per_game", "season": 2025},
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/team-stats/standings
# ---------------------------------------------------------------------------

class TestGetStandings:
    def test_returns_standings_for_season(self, client, kc_standing, buf_standing):
        resp = client.get("/api/team-stats/standings", params={"season": 2025})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        abbrs = {r["team"]["abbreviation"] for r in data}
        assert "KC" in abbrs
        assert "BUF" in abbrs

    def test_filter_by_conference(self, client, kc_standing, buf_standing):
        resp = client.get(
            "/api/team-stats/standings",
            params={"season": 2025, "conference": "AFC"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Both KC and BUF are AFC so both should be present
        assert len(data) == 2

    def test_standing_shape(self, client, kc_standing):
        resp = client.get("/api/team-stats/standings", params={"season": 2025})
        row = resp.json()[0]
        assert "wins" in row
        assert "losses" in row
        assert "division_rank" in row
        assert "playoff_seed" in row
        assert "strength_of_schedule" in row

    def test_sorted_by_conference_rank(self, client, kc_standing, buf_standing):
        resp = client.get("/api/team-stats/standings", params={"season": 2025})
        ranks = [r["conference_rank"] for r in resp.json()]
        assert ranks == sorted(ranks)

    def test_empty_returns_empty_list(self, client, teams):
        resp = client.get("/api/team-stats/standings", params={"season": 2025})
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/team-stats/matchup
# ---------------------------------------------------------------------------

class TestGetMatchup:
    def test_returns_both_teams_with_stats(self, client, kc_stats, buf_stats, kc_standing, buf_standing):
        resp = client.get(
            "/api/team-stats/matchup",
            params={"home": "KC", "away": "BUF", "season": 2025},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["home_team"]["abbreviation"] == "KC"
        assert data["away_team"]["abbreviation"] == "BUF"
        assert data["home_stats"] is not None
        assert data["away_stats"] is not None
        assert data["home_standing"] is not None
        assert data["away_standing"] is not None

    def test_stats_are_latest_when_week_not_specified(self, client, kc_stats):
        resp = client.get(
            "/api/team-stats/matchup",
            params={"home": "KC", "away": "BUF", "season": 2025},
        )
        assert resp.status_code == 200
        data = resp.json()
        # KC has weeks 1 and 2; should return week 2
        assert data["home_stats"]["week"] == 2

    def test_specific_week_snapshot_returned(self, client, kc_stats):
        resp = client.get(
            "/api/team-stats/matchup",
            params={"home": "KC", "away": "BUF", "season": 2025, "week": 1},
        )
        assert resp.status_code == 200
        assert resp.json()["home_stats"]["week"] == 1

    def test_missing_stats_returns_none_not_error(self, client, teams, kc_standing):
        # KC has a standing but no stats; BUF has nothing
        resp = client.get(
            "/api/team-stats/matchup",
            params={"home": "KC", "away": "BUF", "season": 2025},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["home_stats"] is None
        assert data["away_stats"] is None
        assert data["home_standing"] is not None
        assert data["away_standing"] is None

    def test_unknown_home_team_returns_404(self, client, teams):
        resp = client.get(
            "/api/team-stats/matchup",
            params={"home": "ZZZ", "away": "BUF", "season": 2025},
        )
        assert resp.status_code == 404

    def test_unknown_away_team_returns_404(self, client, teams):
        resp = client.get(
            "/api/team-stats/matchup",
            params={"home": "KC", "away": "ZZZ", "season": 2025},
        )
        assert resp.status_code == 404

    def test_response_includes_season_and_week(self, client, kc_stats, buf_stats):
        resp = client.get(
            "/api/team-stats/matchup",
            params={"home": "KC", "away": "BUF", "season": 2025},
        )
        data = resp.json()
        assert data["season"] == 2025
        assert data["week"] == 2  # latest available
