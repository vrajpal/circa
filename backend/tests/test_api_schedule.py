"""
Integration tests for /api/schedule/* endpoints.

Covers: teams list, games list (filtering), get single game.
"""


TEAMS_URL = "/api/schedule/teams"
GAMES_URL = "/api/schedule/games"


class TestTeamsEndpoint:
    def test_empty_db_returns_empty_list(self, client):
        r = client.get(TEAMS_URL)
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_seeded_teams(self, client, teams):
        r = client.get(TEAMS_URL)
        assert r.status_code == 200
        body = r.json()
        assert len(body) == len(teams)

    def test_response_shape(self, client, teams):
        r = client.get(TEAMS_URL)
        first = r.json()[0]
        assert set(first.keys()) == {"id", "abbreviation", "name", "conference", "division"}

    def test_teams_returned_alphabetically(self, client, teams):
        r = client.get(TEAMS_URL)
        abbreviations = [t["abbreviation"] for t in r.json()]
        assert abbreviations == sorted(abbreviations)

    def test_all_team_conferences_valid(self, client, teams):
        r = client.get(TEAMS_URL)
        for t in r.json():
            assert t["conference"] in ("AFC", "NFC")

    def test_all_team_divisions_valid(self, client, teams):
        r = client.get(TEAMS_URL)
        for t in r.json():
            assert t["division"] in ("North", "South", "East", "West")


class TestGamesEndpoint:
    def test_no_games_returns_empty_list(self, client, teams):
        r = client.get(GAMES_URL)
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_games_for_current_season(self, client, sample_games):
        r = client.get(GAMES_URL)
        assert r.status_code == 200
        # all fixture games are in 2025
        assert len(r.json()) >= 2

    def test_filter_by_week(self, client, sample_games):
        r = client.get(GAMES_URL, params={"week": 1})
        body = r.json()
        assert len(body) == 2
        for g in body:
            assert g["week"] == 1

    def test_filter_by_week_2(self, client, sample_games):
        r = client.get(GAMES_URL, params={"week": 2})
        body = r.json()
        assert len(body) == 1
        assert body[0]["week"] == 2

    def test_filter_by_team_home(self, client, sample_games):
        r = client.get(GAMES_URL, params={"team": "KC"})
        body = r.json()
        assert len(body) == 1
        teams_in_game = {body[0]["home_team"]["abbreviation"], body[0]["away_team"]["abbreviation"]}
        assert "KC" in teams_in_game

    def test_filter_by_team_away(self, client, sample_games):
        r = client.get(GAMES_URL, params={"team": "BUF"})
        body = r.json()
        # BUF appears in week1 game (away) and week2 game (home) and thanksgiving
        abbreviations = {
            t
            for g in body
            for t in (g["home_team"]["abbreviation"], g["away_team"]["abbreviation"])
        }
        assert "BUF" in abbreviations

    def test_filter_team_case_insensitive(self, client, sample_games):
        r_upper = client.get(GAMES_URL, params={"team": "KC"})
        r_lower = client.get(GAMES_URL, params={"team": "kc"})
        assert r_upper.json() == r_lower.json()

    def test_filter_unknown_team_returns_empty(self, client, sample_games):
        r = client.get(GAMES_URL, params={"team": "XXX"})
        assert r.json() == []

    def test_explicit_season_filter(self, client, sample_games):
        r = client.get(GAMES_URL, params={"season": 2025})
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_wrong_season_returns_empty(self, client, sample_games):
        r = client.get(GAMES_URL, params={"season": 1999})
        assert r.json() == []

    def test_game_response_shape(self, client, sample_games):
        r = client.get(GAMES_URL, params={"week": 1})
        g = r.json()[0]
        for key in ("id", "season", "week", "home_team", "away_team", "game_time", "slate"):
            assert key in g
        for key in ("id", "abbreviation", "name", "conference", "division"):
            assert key in g["home_team"]

    def test_games_ordered_by_game_time(self, client, sample_games):
        r = client.get(GAMES_URL, params={"week": 1})
        times = [g["game_time"] for g in r.json()]
        assert times == sorted(times)

    def test_thanksgiving_slate_games(self, client, sample_games):
        r = client.get(GAMES_URL, params={"week": 12})
        body = r.json()
        assert len(body) == 3
        for g in body:
            assert g["slate"] == "thanksgiving"


class TestGetSingleGame:
    def test_get_existing_game(self, client, sample_games):
        game_id = sample_games[0].id
        r = client.get(f"/api/schedule/games/{game_id}")
        assert r.status_code == 200
        assert r.json()["id"] == game_id

    def test_get_nonexistent_game(self, client):
        r = client.get("/api/schedule/games/99999")
        assert r.status_code == 404

    def test_get_game_contains_team_info(self, client, sample_games):
        game_id = sample_games[0].id
        r = client.get(f"/api/schedule/games/{game_id}")
        body = r.json()
        assert body["home_team"]["abbreviation"] == "KC"
        assert body["away_team"]["abbreviation"] == "BUF"
