"""
Integration tests for /api/consensus/* endpoints.

Covers:
  - GET /api/consensus/picks  (all user picks — consensus view)
  - GET /api/consensus/locked
  - POST /api/consensus/lock  (millions 5-pick limit, survivor reuse)
  - DELETE /api/consensus/lock/{id}
  - Auth requirements
"""


LOCK_URL      = "/api/consensus/lock"
LOCKED_URL    = "/api/consensus/locked"
ALL_PICKS_URL = "/api/consensus/picks"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _lock(client, headers, team_id, contest_type, week=1, game_id=None, season=2025):
    payload = {"picked_team_id": team_id, "contest_type": contest_type, "game_id": game_id}
    return client.post(
        LOCK_URL,
        json=payload,
        params={"week": week, "season": season},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

class TestConsensusAuthGuards:
    def test_all_picks_requires_auth(self, client):
        assert client.get(ALL_PICKS_URL).status_code == 401

    def test_locked_requires_auth(self, client):
        assert client.get(LOCKED_URL).status_code == 401

    def test_lock_requires_auth(self, client, teams):
        payload = {"picked_team_id": teams["KC"].id, "contest_type": "millions"}
        assert client.post(LOCK_URL, json=payload, params={"week": 1}).status_code == 401

    def test_unlock_requires_auth(self, client):
        assert client.delete(f"{LOCK_URL}/1").status_code == 401


# ---------------------------------------------------------------------------
# GET /api/consensus/picks  (all user picks, visible to authenticated users)
# ---------------------------------------------------------------------------

class TestConsensusAllPicks:
    def test_empty_returns_empty_list(self, client, auth_headers_alice):
        r = client.get(ALL_PICKS_URL, headers=auth_headers_alice)
        assert r.status_code == 200
        assert r.json() == []

    def test_shows_all_users_picks(
        self, client, db_session, auth_headers_alice,
        user_alice, user_bob, sample_games, teams
    ):
        from app.models import Pick
        game = sample_games[0]
        db_session.add(Pick(
            user_id=user_alice.id, game_id=game.id,
            season=2025, week=1, contest_type="millions",
            picked_team_id=teams["KC"].id,
        ))
        db_session.add(Pick(
            user_id=user_bob.id, game_id=game.id,
            season=2025, week=1, contest_type="millions",
            picked_team_id=teams["BUF"].id,
        ))
        db_session.flush()

        r = client.get(ALL_PICKS_URL, params={"week": 1}, headers=auth_headers_alice)
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_filter_by_contest_type(
        self, client, db_session, auth_headers_alice,
        user_alice, sample_games, teams
    ):
        from app.models import Pick
        game = sample_games[0]
        db_session.add(Pick(
            user_id=user_alice.id, game_id=game.id,
            season=2025, week=1, contest_type="millions",
            picked_team_id=teams["KC"].id,
        ))
        db_session.add(Pick(
            user_id=user_alice.id, game_id=game.id,
            season=2025, week=1, contest_type="survivor",
            picked_team_id=teams["BUF"].id,
        ))
        db_session.flush()

        r = client.get(ALL_PICKS_URL, params={"contest_type": "millions"}, headers=auth_headers_alice)
        body = r.json()
        assert all(p["contest_type"] == "millions" for p in body)


# ---------------------------------------------------------------------------
# GET /api/consensus/locked
# ---------------------------------------------------------------------------

class TestGetLockedConsensus:
    def test_empty_returns_empty_list(self, client, auth_headers_alice):
        r = client.get(LOCKED_URL, headers=auth_headers_alice)
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_locked_pick(self, client, auth_headers_alice, sample_games, teams):
        _lock(client, auth_headers_alice, teams["KC"].id, "millions", game_id=sample_games[0].id)
        r = client.get(LOCKED_URL, headers=auth_headers_alice)
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_response_shape(self, client, auth_headers_alice, sample_games, teams):
        _lock(client, auth_headers_alice, teams["KC"].id, "millions", game_id=sample_games[0].id)
        r = client.get(LOCKED_URL, headers=auth_headers_alice)
        item = r.json()[0]
        for field in ("id", "season", "week", "contest_type", "picked_team", "decided_at"):
            assert field in item

    def test_filter_by_week(self, client, auth_headers_alice, sample_games, teams):
        _lock(client, auth_headers_alice, teams["KC"].id, "millions", week=1, game_id=sample_games[0].id)
        _lock(client, auth_headers_alice, teams["SF"].id, "millions", week=2, game_id=sample_games[1].id)
        r = client.get(LOCKED_URL, params={"week": 1}, headers=auth_headers_alice)
        body = r.json()
        assert all(p["week"] == 1 for p in body)

    def test_filter_by_contest_type(self, client, auth_headers_alice, sample_games, teams):
        _lock(client, auth_headers_alice, teams["KC"].id,  "millions",  week=1, game_id=sample_games[0].id)
        _lock(client, auth_headers_alice, teams["BUF"].id, "survivor", week=1, game_id=sample_games[0].id)
        r = client.get(LOCKED_URL, params={"contest_type": "millions"}, headers=auth_headers_alice)
        body = r.json()
        assert all(p["contest_type"] == "millions" for p in body)


# ---------------------------------------------------------------------------
# POST /api/consensus/lock
# ---------------------------------------------------------------------------

class TestLockConsensus:
    def test_lock_millions_pick_success(self, client, auth_headers_alice, sample_games, teams):
        r = _lock(client, auth_headers_alice, teams["KC"].id, "millions", game_id=sample_games[0].id)
        assert r.status_code == 201
        body = r.json()
        assert body["contest_type"] == "millions"
        assert body["picked_team"]["abbreviation"] == "KC"
        assert body["week"] == 1
        assert body["season"] == 2025

    def test_lock_survivor_pick_success(self, client, auth_headers_alice, sample_games, teams):
        r = _lock(client, auth_headers_alice, teams["KC"].id, "survivor", game_id=sample_games[0].id)
        assert r.status_code == 201

    def test_lock_response_has_game(self, client, auth_headers_alice, sample_games, teams):
        r = _lock(client, auth_headers_alice, teams["KC"].id, "millions", game_id=sample_games[0].id)
        assert r.json()["game"] is not None

    def test_lock_without_game_id_allowed(self, client, auth_headers_alice, teams):
        # game_id is nullable on ConsensusPick
        r = _lock(client, auth_headers_alice, teams["KC"].id, "millions", game_id=None)
        assert r.status_code == 201
        assert r.json()["game"] is None


# ---------------------------------------------------------------------------
# Millions 5-pick limit
# ---------------------------------------------------------------------------

class TestMillionsFivePickLimit:
    def _lock_n(self, client, headers, games, teams_list, week=1, n=5):
        """Lock N different teams for millions in a week."""
        for i in range(n):
            team = teams_list[i]
            game = games[i % len(games)]
            r = _lock(client, headers, team.id, "millions", week=week, game_id=game.id)
            assert r.status_code == 201, f"Lock {i+1} failed: {r.json()}"

    def test_five_picks_allowed(self, client, auth_headers_alice, sample_games, teams):
        team_list = list(teams.values())
        self._lock_n(client, auth_headers_alice, sample_games, team_list, week=1, n=5)
        r = client.get(LOCKED_URL, params={"week": 1, "contest_type": "millions"},
                        headers=auth_headers_alice)
        assert len(r.json()) == 5

    def test_sixth_pick_rejected(self, client, auth_headers_alice, sample_games, teams):
        team_list = list(teams.values())
        self._lock_n(client, auth_headers_alice, sample_games, team_list, week=1, n=5)
        sixth_team = team_list[5]
        r = _lock(client, auth_headers_alice, sixth_team.id, "millions", week=1)
        assert r.status_code == 400
        assert "5" in r.json()["detail"]

    def test_limit_is_per_week(self, client, auth_headers_alice, sample_games, teams):
        """Filling week 1 should not prevent picks in week 2."""
        team_list = list(teams.values())
        self._lock_n(client, auth_headers_alice, sample_games, team_list, week=1, n=5)
        # week 2 should still allow a lock
        r = _lock(client, auth_headers_alice, team_list[0].id, "millions", week=2)
        assert r.status_code == 201

    def test_survivor_not_counted_in_millions_limit(self, client, auth_headers_alice, sample_games, teams):
        """5 survivor picks should not affect the millions counter."""
        team_list = list(teams.values())
        # Lock 5 survivor picks
        for i in range(5):
            r = _lock(client, auth_headers_alice, team_list[i].id, "survivor", week=1)
            assert r.status_code == 201
        # millions picks should still be available up to 5
        r = _lock(client, auth_headers_alice, team_list[5].id, "millions", week=1)
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# Survivor reuse in consensus
# ---------------------------------------------------------------------------

class TestConsensusLockSurvivorReuse:
    def test_survivor_reuse_blocked(self, client, auth_headers_alice, sample_games, teams):
        _lock(client, auth_headers_alice, teams["KC"].id, "survivor", week=1)
        r = _lock(client, auth_headers_alice, teams["KC"].id, "survivor", week=2)
        assert r.status_code == 400
        assert "already used" in r.json()["detail"].lower()

    def test_survivor_different_team_allowed_in_different_week(
        self, client, auth_headers_alice, teams
    ):
        _lock(client, auth_headers_alice, teams["KC"].id, "survivor", week=1)
        r = _lock(client, auth_headers_alice, teams["BUF"].id, "survivor", week=2)
        assert r.status_code == 201

    def test_survivor_reuse_check_is_season_scoped(self, client, auth_headers_alice, teams):
        _lock(client, auth_headers_alice, teams["KC"].id, "survivor", week=1, season=2025)
        # Different season should be fine
        r = _lock(client, auth_headers_alice, teams["KC"].id, "survivor", week=1, season=2024)
        assert r.status_code == 201

    def test_millions_team_can_be_reused_in_survivor(self, client, auth_headers_alice, teams):
        _lock(client, auth_headers_alice, teams["KC"].id, "millions", week=1)
        r = _lock(client, auth_headers_alice, teams["KC"].id, "survivor", week=1)
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# DELETE /api/consensus/lock/{id}
# ---------------------------------------------------------------------------

class TestUnlockConsensus:
    def test_unlock_existing_pick(self, client, auth_headers_alice, teams):
        r = _lock(client, auth_headers_alice, teams["KC"].id, "millions", week=1)
        pick_id = r.json()["id"]
        del_r = client.delete(f"{LOCK_URL}/{pick_id}", headers=auth_headers_alice)
        assert del_r.status_code == 204

    def test_unlocked_pick_no_longer_in_locked_list(self, client, auth_headers_alice, teams):
        r = _lock(client, auth_headers_alice, teams["KC"].id, "millions", week=1)
        pick_id = r.json()["id"]
        client.delete(f"{LOCK_URL}/{pick_id}", headers=auth_headers_alice)
        listed = client.get(LOCKED_URL, headers=auth_headers_alice).json()
        assert not any(p["id"] == pick_id for p in listed)

    def test_unlock_nonexistent_returns_404(self, client, auth_headers_alice):
        r = client.delete(f"{LOCK_URL}/99999", headers=auth_headers_alice)
        assert r.status_code == 404

    def test_unlock_allows_relocking_same_team_survivor(self, client, auth_headers_alice, teams):
        r = _lock(client, auth_headers_alice, teams["KC"].id, "survivor", week=1)
        pick_id = r.json()["id"]
        client.delete(f"{LOCK_URL}/{pick_id}", headers=auth_headers_alice)
        # After unlock, KC should be lockable again
        r2 = _lock(client, auth_headers_alice, teams["KC"].id, "survivor", week=2)
        assert r2.status_code == 201

    def test_unlock_restores_millions_capacity(self, client, auth_headers_alice, sample_games, teams):
        team_list = list(teams.values())
        ids = []
        for i in range(5):
            r = _lock(client, auth_headers_alice, team_list[i].id, "millions", week=1)
            ids.append(r.json()["id"])

        # 6th should be blocked
        r6 = _lock(client, auth_headers_alice, team_list[5].id, "millions", week=1)
        assert r6.status_code == 400

        # Unlock one
        client.delete(f"{LOCK_URL}/{ids[0]}", headers=auth_headers_alice)

        # Now 6th should succeed
        r6b = _lock(client, auth_headers_alice, team_list[5].id, "millions", week=1)
        assert r6b.status_code == 201
