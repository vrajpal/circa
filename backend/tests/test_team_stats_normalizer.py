"""Unit tests for the team stats normalization layer.

These tests never touch the network or database — they validate that the
mapping from raw ESPN JSON to our unified schema is correct.
"""
import pytest

from ingestion.team_stats_normalizer import normalize_espn_team_stats, normalize_espn_standing


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_categories(stats: dict[str, float]) -> list[dict]:
    """Build a minimal ESPN-style categories payload from a flat stat dict."""
    return [
        {
            "name": "general",
            "stats": [{"name": k, "value": v} for k, v in stats.items()],
        }
    ]


# ---------------------------------------------------------------------------
# normalize_espn_team_stats
# ---------------------------------------------------------------------------

class TestNormalizeEspnTeamStats:
    def test_per_game_rates_computed_correctly(self):
        categories = _make_categories({
            "totalPoints": 224,
            "totalYards": 2800,
            "netPassingYards": 1900,
            "rushingYards": 900,
        })
        result = normalize_espn_team_stats(categories, games_played=8)
        assert result["points_per_game"] == 28.0
        assert result["total_yards_per_game"] == 350.0
        assert result["passing_yards_per_game"] == 237.5
        assert result["rushing_yards_per_game"] == 112.5

    def test_red_zone_td_pct_calculated(self):
        categories = _make_categories({
            "redZoneAttempts": 20,
            "redZoneTouchdowns": 15,
        })
        result = normalize_espn_team_stats(categories, games_played=8)
        assert result["red_zone_td_pct"] == 75.0
        assert result["red_zone_attempts"] == 20

    def test_third_down_pct_calculated(self):
        categories = _make_categories({
            "thirdDownConversions": 40,
            "thirdDownAttempts": 80,
        })
        result = normalize_espn_team_stats(categories, games_played=8)
        assert result["third_down_pct"] == 50.0

    def test_takeaways_aggregates_int_and_fumbles(self):
        categories = _make_categories({
            "interceptions": 8,
            "fumblesRecovered": 4,
        })
        result = normalize_espn_team_stats(categories, games_played=8)
        # 12 total takeaways / 8 games = 1.5
        assert result["takeaways_per_game"] == 1.5

    def test_point_differential_computed_when_both_sides_present(self):
        categories = _make_categories({
            "totalPoints": 224,  # 28 ppg
            "pointsAllowed": 160,  # 20 ppg
        })
        result = normalize_espn_team_stats(categories, games_played=8)
        assert result["point_differential_per_game"] == 8.0  # 28 - 20

    def test_point_differential_none_when_defense_missing(self):
        categories = _make_categories({"totalPoints": 224})
        result = normalize_espn_team_stats(categories, games_played=8)
        assert result["point_differential_per_game"] is None

    def test_missing_stats_return_none_not_error(self):
        # Empty categories should not raise; all fields should be None
        result = normalize_espn_team_stats([], games_played=1)
        assert result["points_per_game"] is None
        assert result["total_yards_per_game"] is None
        assert result["sacks_per_game"] is None

    def test_games_played_zero_does_not_divide_by_zero(self):
        """Guard against bad data: ESPN can return 0 for games played early in season."""
        categories = _make_categories({"totalPoints": 28})
        # Should not raise even with games_played=0
        result = normalize_espn_team_stats(categories, games_played=0)
        # gp is clamped to 1 internally
        assert result["points_per_game"] == 28.0

    def test_sacks_computed_per_game(self):
        categories = _make_categories({"sacks": 16})
        result = normalize_espn_team_stats(categories, games_played=8)
        assert result["sacks_per_game"] == 2.0

    def test_all_expected_keys_present(self):
        result = normalize_espn_team_stats([], games_played=1)
        expected_keys = {
            "games_played",
            "points_per_game",
            "total_yards_per_game",
            "passing_yards_per_game",
            "rushing_yards_per_game",
            "turnovers_per_game",
            "red_zone_attempts",
            "red_zone_td_pct",
            "third_down_pct",
            "points_allowed_per_game",
            "yards_allowed_per_game",
            "passing_yards_allowed_per_game",
            "rushing_yards_allowed_per_game",
            "sacks_per_game",
            "takeaways_per_game",
            "point_differential_per_game",
        }
        assert set(result.keys()) == expected_keys

    def test_direct_per_game_field_takes_precedence(self):
        """If ESPN provides totalPointsPerGame directly, use it as-is."""
        categories = _make_categories({
            "totalPointsPerGame": 31.4,
            "totalPoints": 251,  # would compute to 31.375 over 8 games
        })
        result = normalize_espn_team_stats(categories, games_played=8)
        assert result["points_per_game"] == 31.4


# ---------------------------------------------------------------------------
# normalize_espn_standing
# ---------------------------------------------------------------------------

class TestNormalizeEspnStanding:
    def _make_entry(self, stats: dict) -> dict:
        return {
            "team": {"abbreviation": "KC"},
            "stats": [
                {"name": k, "value": v, "displayValue": str(v)}
                for k, v in stats.items()
            ],
        }

    def test_basic_record_parsed(self):
        entry = self._make_entry({"wins": 6, "losses": 2, "ties": 0, "winPercent": 0.75})
        result = normalize_espn_standing(entry)
        assert result["wins"] == 6
        assert result["losses"] == 2
        assert result["ties"] == 0
        assert result["win_pct"] == 0.75

    def test_home_away_splits_parsed(self):
        entry = self._make_entry({
            "homeWins": 3, "homeLosses": 1,
            "roadWins": 3, "roadLosses": 1,
        })
        result = normalize_espn_standing(entry)
        assert result["home_wins"] == 3
        assert result["home_losses"] == 1
        assert result["away_wins"] == 3
        assert result["away_losses"] == 1

    def test_strength_of_schedule_parsed(self):
        entry = self._make_entry({"opponentWinPercent": 0.512})
        result = normalize_espn_standing(entry)
        assert result["strength_of_schedule"] == 0.512

    def test_division_and_conf_rank_default_none(self):
        """These come from the caller, not the entry itself."""
        entry = self._make_entry({"wins": 5})
        result = normalize_espn_standing(entry)
        assert result["division_rank"] is None
        assert result["conference_rank"] is None
        assert result["playoff_seed"] is None

    def test_missing_stats_return_none(self):
        entry = {"team": {"abbreviation": "KC"}, "stats": []}
        result = normalize_espn_standing(entry)
        assert result["wins"] is None
        assert result["losses"] is None
        assert result["strength_of_schedule"] is None

    def test_all_expected_keys_present(self):
        entry = {"team": {"abbreviation": "KC"}, "stats": []}
        result = normalize_espn_standing(entry)
        expected = {
            "wins", "losses", "ties", "win_pct",
            "division_rank", "conference_rank", "playoff_seed",
            "strength_of_schedule",
            "home_wins", "home_losses", "away_wins", "away_losses",
        }
        assert set(result.keys()) == expected
