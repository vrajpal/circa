"""
Integration tests for /api/picks/* endpoints.

Covers:
  - GET /api/picks/ (list, filter)
  - POST /api/picks/ (create, replace, invalid team, invalid contest_type)
  - DELETE /api/picks/{id}
  - GET /api/picks/survivor/used
  - GET /api/picks/survivor/slate-warning
  - Auth requirements on every endpoint
  - Survivor team-reuse prevention
"""
import pytest


PICKS_URL    = "/api/picks/"
SURVIVOR_USED_URL = "/api/picks/survivor/used"
SLATE_WARN_URL    = "/api/picks/survivor/slate-warning"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _create_pick(client, headers, game_id, team_id, contest_type="millions", comment=None):
    payload = {"game_id": game_id, "picked_team_id": team_id, "contest_type": contest_type}
    if comment:
        payload["comment"] = comment
    return client.post(PICKS_URL, json=payload, headers=headers)


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

class TestPicksAuthGuards:
    def test_list_requires_auth(self, client):
        assert client.get(PICKS_URL).status_code == 401

    def test_create_requires_auth(self, client, sample_games, teams):
        payload = {"game_id": sample_games[0].id, "picked_team_id": teams["KC"].id, "contest_type": "millions"}
        assert client.post(PICKS_URL, json=payload).status_code == 401

    def test_delete_requires_auth(self, client):
        assert client.delete(f"{PICKS_URL}1").status_code == 401

    def test_survivor_used_requires_auth(self, client):
        assert client.get(SURVIVOR_USED_URL).status_code == 401

    def test_slate_warning_requires_auth(self, client, teams):
        assert client.get(SLATE_WARN_URL, params={"picked_team_id": teams["KC"].id}).status_code == 401


# ---------------------------------------------------------------------------
# Create pick
# ---------------------------------------------------------------------------

class TestCreatePick:
    def test_create_millions_pick_success(self, client, auth_headers_alice, sample_games, teams):
        game = sample_games[0]
        r = _create_pick(client, auth_headers_alice, game.id, teams["KC"].id, "millions")
        assert r.status_code == 201
        body = r.json()
        assert body["contest_type"] == "millions"
        assert body["picked_team"]["abbreviation"] == "KC"
        assert body["season"] == 2025
        assert body["week"] == 1

    def test_create_survivor_pick_success(self, client, auth_headers_alice, sample_games, teams):
        game = sample_games[0]
        r = _create_pick(client, auth_headers_alice, game.id, teams["BUF"].id, "survivor")
        assert r.status_code == 201
        assert r.json()["contest_type"] == "survivor"

    def test_pick_includes_comment(self, client, auth_headers_alice, sample_games, teams):
        r = _create_pick(client, auth_headers_alice, sample_games[0].id,
                         teams["KC"].id, "millions", comment="Good matchup")
        assert r.json()["comment"] == "Good matchup"

    def test_pick_game_not_found(self, client, auth_headers_alice, teams):
        r = _create_pick(client, auth_headers_alice, 99999, teams["KC"].id, "millions")
        assert r.status_code == 404

    def test_pick_team_not_in_game(self, client, auth_headers_alice, sample_games, teams):
        # SF is not in game 0 (KC vs BUF)
        r = _create_pick(client, auth_headers_alice, sample_games[0].id, teams["SF"].id, "millions")
        assert r.status_code == 400
        assert "not in this game" in r.json()["detail"]

    def test_invalid_contest_type(self, client, auth_headers_alice, sample_games, teams):
        payload = {
            "game_id": sample_games[0].id,
            "picked_team_id": teams["KC"].id,
            "contest_type": "fantasy",
        }
        r = client.post(PICKS_URL, json=payload, headers=auth_headers_alice)
        assert r.status_code == 400
        assert "contest_type" in r.json()["detail"]

    def test_pick_replaces_existing_for_same_game_and_contest(
        self, client, auth_headers_alice, sample_games, teams
    ):
        game = sample_games[0]
        # first pick KC
        _create_pick(client, auth_headers_alice, game.id, teams["KC"].id, "millions")
        # switch to BUF
        r2 = _create_pick(client, auth_headers_alice, game.id, teams["BUF"].id, "millions")
        assert r2.status_code == 201

        # now list and verify only one pick exists for this game/contest
        listed = client.get(
            PICKS_URL,
            params={"week": 1, "contest_type": "millions"},
            headers=auth_headers_alice,
        ).json()
        game_picks = [p for p in listed if p["game"]["id"] == game.id]
        assert len(game_picks) == 1
        assert game_picks[0]["picked_team"]["abbreviation"] == "BUF"

    def test_different_contest_types_do_not_collide(
        self, client, auth_headers_alice, sample_games, teams
    ):
        game = sample_games[0]
        _create_pick(client, auth_headers_alice, game.id, teams["KC"].id, "millions")
        _create_pick(client, auth_headers_alice, game.id, teams["BUF"].id, "survivor")

        listed = client.get(
            PICKS_URL, params={"week": 1}, headers=auth_headers_alice
        ).json()
        game_picks = [p for p in listed if p["game"]["id"] == game.id]
        assert len(game_picks) == 2

    def test_two_users_can_pick_same_team(
        self, client, auth_headers_alice, auth_headers_bob,
        sample_games, teams
    ):
        game = sample_games[0]
        r1 = _create_pick(client, auth_headers_alice, game.id, teams["KC"].id, "millions")
        r2 = _create_pick(client, auth_headers_bob,  game.id, teams["KC"].id, "millions")
        assert r1.status_code == 201
        assert r2.status_code == 201


# ---------------------------------------------------------------------------
# Survivor team reuse
# ---------------------------------------------------------------------------

class TestSurvivorReuse:
    def test_survivor_reuse_blocked_after_consensus_lock(
        self, client, db_session, auth_headers_alice, sample_games, teams
    ):
        from app.models import ConsensusPick
        # Lock KC in via consensus
        cp = ConsensusPick(
            season=2025, week=1, contest_type="survivor",
            picked_team_id=teams["KC"].id,
        )
        db_session.add(cp)
        db_session.flush()

        # Now alice tries to pick KC for survivor
        r = _create_pick(client, auth_headers_alice, sample_games[0].id, teams["KC"].id, "survivor")
        assert r.status_code == 400
        assert "already used in survivor" in r.json()["detail"]

    def test_survivor_different_team_not_blocked(
        self, client, db_session, auth_headers_alice, sample_games, teams
    ):
        from app.models import ConsensusPick
        cp = ConsensusPick(
            season=2025, week=1, contest_type="survivor",
            picked_team_id=teams["KC"].id,
        )
        db_session.add(cp)
        db_session.flush()

        # BUF is fine
        r = _create_pick(client, auth_headers_alice, sample_games[0].id, teams["BUF"].id, "survivor")
        assert r.status_code == 201

    def test_millions_not_affected_by_survivor_consensus(
        self, client, db_session, auth_headers_alice, sample_games, teams
    ):
        from app.models import ConsensusPick
        cp = ConsensusPick(
            season=2025, week=1, contest_type="survivor",
            picked_team_id=teams["KC"].id,
        )
        db_session.add(cp)
        db_session.flush()

        r = _create_pick(client, auth_headers_alice, sample_games[0].id, teams["KC"].id, "millions")
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# List picks
# ---------------------------------------------------------------------------

class TestListPicks:
    def test_list_returns_own_picks(self, client, auth_headers_alice, sample_games, teams):
        _create_pick(client, auth_headers_alice, sample_games[0].id, teams["KC"].id, "millions")
        r = client.get(PICKS_URL, headers=auth_headers_alice)
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_filter_by_week(self, client, auth_headers_alice, sample_games, teams):
        _create_pick(client, auth_headers_alice, sample_games[0].id, teams["KC"].id, "millions")
        _create_pick(client, auth_headers_alice, sample_games[2].id, teams["BUF"].id, "millions")

        wk1 = client.get(PICKS_URL, params={"week": 1}, headers=auth_headers_alice).json()
        wk2 = client.get(PICKS_URL, params={"week": 2}, headers=auth_headers_alice).json()
        assert all(p["week"] == 1 for p in wk1)
        assert all(p["week"] == 2 for p in wk2)

    def test_filter_by_contest_type(self, client, auth_headers_alice, sample_games, teams):
        _create_pick(client, auth_headers_alice, sample_games[0].id, teams["KC"].id, "millions")
        _create_pick(client, auth_headers_alice, sample_games[0].id, teams["BUF"].id, "survivor")

        m = client.get(PICKS_URL, params={"contest_type": "millions"}, headers=auth_headers_alice).json()
        s = client.get(PICKS_URL, params={"contest_type": "survivor"}, headers=auth_headers_alice).json()
        assert all(p["contest_type"] == "millions" for p in m)
        assert all(p["contest_type"] == "survivor" for p in s)

    def test_response_contains_user_info(self, client, auth_headers_alice, sample_games, teams, user_alice):
        _create_pick(client, auth_headers_alice, sample_games[0].id, teams["KC"].id, "millions")
        r = client.get(PICKS_URL, headers=auth_headers_alice).json()
        assert r[0]["user"]["username"] == "alice"

    def test_filter_by_user_id(
        self, client, auth_headers_alice, auth_headers_bob, sample_games, teams, user_alice, user_bob
    ):
        """Passing user_id should only return that user's picks."""
        _create_pick(client, auth_headers_alice, sample_games[0].id, teams["KC"].id, "millions")
        _create_pick(client, auth_headers_bob, sample_games[0].id, teams["BUF"].id, "millions")

        alice_picks = client.get(
            PICKS_URL, params={"user_id": user_alice.id}, headers=auth_headers_alice
        ).json()
        assert all(p["user"]["id"] == user_alice.id for p in alice_picks)

        bob_picks = client.get(
            PICKS_URL, params={"user_id": user_bob.id}, headers=auth_headers_alice
        ).json()
        assert all(p["user"]["id"] == user_bob.id for p in bob_picks)


# ---------------------------------------------------------------------------
# Delete pick
# ---------------------------------------------------------------------------

class TestDeletePick:
    def test_delete_own_pick(self, client, auth_headers_alice, sample_games, teams):
        r = _create_pick(client, auth_headers_alice, sample_games[0].id, teams["KC"].id, "millions")
        pick_id = r.json()["id"]
        del_r = client.delete(f"{PICKS_URL}{pick_id}", headers=auth_headers_alice)
        assert del_r.status_code == 204

    def test_deleted_pick_no_longer_listed(self, client, auth_headers_alice, sample_games, teams):
        r = _create_pick(client, auth_headers_alice, sample_games[0].id, teams["KC"].id, "millions")
        pick_id = r.json()["id"]
        client.delete(f"{PICKS_URL}{pick_id}", headers=auth_headers_alice)
        listed = client.get(PICKS_URL, headers=auth_headers_alice).json()
        assert not any(p["id"] == pick_id for p in listed)

    def test_cannot_delete_others_pick(
        self, client, auth_headers_alice, auth_headers_bob, sample_games, teams
    ):
        r = _create_pick(client, auth_headers_alice, sample_games[0].id, teams["KC"].id, "millions")
        pick_id = r.json()["id"]
        del_r = client.delete(f"{PICKS_URL}{pick_id}", headers=auth_headers_bob)
        assert del_r.status_code == 404

    def test_delete_nonexistent_pick(self, client, auth_headers_alice):
        r = client.delete(f"{PICKS_URL}99999", headers=auth_headers_alice)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Survivor used teams
# ---------------------------------------------------------------------------

class TestSurvivorUsed:
    def test_no_consensus_picks_returns_empty(self, client, auth_headers_alice, teams):
        r = client.get(SURVIVOR_USED_URL, headers=auth_headers_alice)
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_locked_survivor_teams(self, client, db_session, auth_headers_alice, teams):
        from app.models import ConsensusPick
        cp = ConsensusPick(
            season=2025, week=1, contest_type="survivor",
            picked_team_id=teams["KC"].id,
        )
        db_session.add(cp)
        db_session.flush()

        r = client.get(SURVIVOR_USED_URL, headers=auth_headers_alice)
        assert r.status_code == 200
        abbrevs = [t["abbreviation"] for t in r.json()]
        assert "KC" in abbrevs

    def test_millions_consensus_not_included(self, client, db_session, auth_headers_alice, teams):
        from app.models import ConsensusPick
        cp = ConsensusPick(
            season=2025, week=1, contest_type="millions",
            picked_team_id=teams["KC"].id,
        )
        db_session.add(cp)
        db_session.flush()

        r = client.get(SURVIVOR_USED_URL, headers=auth_headers_alice)
        assert r.json() == []


# ---------------------------------------------------------------------------
# Slate warning
# ---------------------------------------------------------------------------

class TestSlateWarning:
    def test_no_special_game_returns_null(self, client, auth_headers_alice, sample_games, teams):
        # KC only plays in a regular-slate game in fixtures
        r = client.get(SLATE_WARN_URL, params={"picked_team_id": teams["KC"].id},
                       headers=auth_headers_alice)
        assert r.status_code == 200
        assert r.json() is None

    def test_special_slate_team_triggers_warning(self, client, auth_headers_alice, sample_games, teams):
        # DET plays in thanksgiving slate
        r = client.get(SLATE_WARN_URL, params={"picked_team_id": teams["DET"].id},
                       headers=auth_headers_alice)
        assert r.status_code == 200
        body = r.json()
        assert body is not None
        assert body["slate"] == "thanksgiving"
        assert "DET" in body["message"]
        assert "remaining_teams" in body

    def test_warning_remaining_teams_excludes_picked(self, client, auth_headers_alice, sample_games, teams):
        r = client.get(SLATE_WARN_URL, params={"picked_team_id": teams["DET"].id},
                       headers=auth_headers_alice)
        body = r.json()
        remaining_abbrevs = [t["abbreviation"] for t in body["remaining_teams"]]
        assert "DET" not in remaining_abbrevs

    def test_warning_remaining_count_accurate(self, client, auth_headers_alice, sample_games, teams):
        # Thanksgiving has 6 teams: DET, CHI, DAL, PHI, MIN, BUF
        r = client.get(SLATE_WARN_URL, params={"picked_team_id": teams["DET"].id},
                       headers=auth_headers_alice)
        body = r.json()
        # 6 total - 1 (DET being picked) - 0 already used = 5 remaining
        assert body["message"].endswith("5 teams")
        assert len(body["remaining_teams"]) == 5

    def test_nonexistent_team_returns_404(self, client, auth_headers_alice):
        r = client.get(SLATE_WARN_URL, params={"picked_team_id": 99999},
                       headers=auth_headers_alice)
        assert r.status_code == 404

    def test_already_used_teams_reduce_remaining(
        self, client, db_session, auth_headers_alice, sample_games, teams
    ):
        from app.models import ConsensusPick
        # Lock CHI via survivor consensus — it's in thanksgiving games
        cp = ConsensusPick(
            season=2025, week=1, contest_type="survivor",
            picked_team_id=teams["CHI"].id,
        )
        db_session.add(cp)
        db_session.flush()

        r = client.get(SLATE_WARN_URL, params={"picked_team_id": teams["DET"].id},
                       headers=auth_headers_alice)
        body = r.json()
        # CHI used + DET being picked -> 4 remaining out of 6
        assert len(body["remaining_teams"]) == 4
        remaining_abbrevs = [t["abbreviation"] for t in body["remaining_teams"]]
        assert "CHI" not in remaining_abbrevs
        assert "DET" not in remaining_abbrevs
