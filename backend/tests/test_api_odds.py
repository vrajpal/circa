"""
Integration tests for /api/odds/* endpoints.

Covers: full history (with optional source filter), latest odds per source.
"""


class TestOddsHistory:
    def test_empty_returns_empty_list(self, client, sample_games):
        # game with no snapshots — use the week-2 game which has none in fixture
        game_id = sample_games[2].id  # week-2 game
        r = client.get(f"/api/odds/game/{game_id}")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_all_snapshots(self, client, sample_odds, sample_games):
        game_id = sample_games[0].id
        r = client.get(f"/api/odds/game/{game_id}")
        assert r.status_code == 200
        # 3 snapshots for game 0 (2 pinnacle, 1 draftkings)
        assert len(r.json()) == 3

    def test_response_shape(self, client, sample_odds, sample_games):
        game_id = sample_games[0].id
        r = client.get(f"/api/odds/game/{game_id}")
        snap = r.json()[0]
        for field in ("id", "game_id", "source", "spread_home", "total",
                      "moneyline_home", "moneyline_away", "is_opening", "captured_at"):
            assert field in snap

    def test_ordered_by_captured_at(self, client, sample_odds, sample_games):
        game_id = sample_games[0].id
        r = client.get(f"/api/odds/game/{game_id}")
        times = [s["captured_at"] for s in r.json()]
        assert times == sorted(times)

    def test_filter_by_source(self, client, sample_odds, sample_games):
        game_id = sample_games[0].id
        r = client.get(f"/api/odds/game/{game_id}", params={"source": "pinnacle"})
        body = r.json()
        assert len(body) == 2
        for s in body:
            assert s["source"] == "pinnacle"

    def test_filter_by_unknown_source(self, client, sample_odds, sample_games):
        game_id = sample_games[0].id
        r = client.get(f"/api/odds/game/{game_id}", params={"source": "betway"})
        assert r.json() == []

    def test_is_opening_flag(self, client, sample_odds, sample_games):
        game_id = sample_games[0].id
        r = client.get(f"/api/odds/game/{game_id}")
        opening_snaps = [s for s in r.json() if s["is_opening"]]
        assert len(opening_snaps) == 1
        assert opening_snaps[0]["source"] == "pinnacle"

    def test_different_game_snaps_isolated(self, client, sample_odds, sample_games):
        """Odds for game 0 should not appear when querying game 1."""
        game_1_id = sample_games[1].id
        r = client.get(f"/api/odds/game/{game_1_id}")
        assert len(r.json()) == 1


class TestLatestOdds:
    def test_latest_one_per_source(self, client, sample_odds, sample_games):
        game_id = sample_games[0].id
        r = client.get(f"/api/odds/game/{game_id}/latest")
        assert r.status_code == 200
        body = r.json()
        # game 0 has pinnacle + draftkings => 2 unique sources
        assert len(body) == 2
        sources = {s["source"] for s in body}
        assert sources == {"pinnacle", "draftkings"}

    def test_latest_is_most_recent_snapshot(self, client, sample_odds, sample_games):
        """For pinnacle, the latest snapshot should have spread_home=-3.5 (closing)."""
        game_id = sample_games[0].id
        r = client.get(f"/api/odds/game/{game_id}/latest")
        pinnacle = next(s for s in r.json() if s["source"] == "pinnacle")
        assert pinnacle["spread_home"] == -3.5

    def test_latest_empty_game_returns_empty(self, client, sample_games):
        game_id = sample_games[2].id
        r = client.get(f"/api/odds/game/{game_id}/latest")
        assert r.status_code == 200
        assert r.json() == []
