"""Derive a fair moneyline from a point spread.

Real historical per-book moneylines aren't freely available for a completed
season, but a spread already encodes the market's view of who wins — so we can
derive a *fair* (no-vig) moneyline from it. This is explicitly a model estimate,
not a real market price: snapshots filled this way are tagged
moneyline_derived=True so the UI and any analysis can treat it accordingly.

Model: NFL final margins are roughly normal around the spread. With the
expected home margin = -spread_home and a margin standard deviation of ~13.45
points (a well-worn empirical NFL figure), the home win probability is the
normal CDF of (-spread_home / sd). That probability converts to fair American
odds with no vig, so home and away implied probabilities sum to 1.
"""
from __future__ import annotations

import math

# Empirical standard deviation of NFL game margins. Widely cited (~13–14);
# 13.45 is the common working value.
NFL_MARGIN_SD = 13.45


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def spread_to_home_win_prob(spread_home: float, sd: float = NFL_MARGIN_SD) -> float:
    """Probability the home team wins outright, given the home spread.

    spread_home < 0 means home is favoured, which yields a probability > 0.5.
    """
    expected_home_margin = -spread_home
    return _normal_cdf(expected_home_margin / sd)


def prob_to_american(prob: float) -> int:
    """Convert a win probability to fair (no-vig) American odds.

    p > 0.5 -> negative (favourite), p < 0.5 -> positive (underdog).
    Clamped away from the 0/1 extremes to keep the number finite.
    """
    prob = min(max(prob, 1e-4), 1 - 1e-4)
    if prob > 0.5:
        return round(-100.0 * prob / (1.0 - prob))
    # p == 0.5 (even money) conventionally displays as +100.
    return round(100.0 * (1.0 - prob) / prob)


def spread_to_moneyline(spread_home: float, sd: float = NFL_MARGIN_SD) -> tuple[int, int]:
    """Return fair (home_ml, away_ml) derived from the home spread."""
    p_home = spread_to_home_win_prob(spread_home, sd)
    return prob_to_american(p_home), prob_to_american(1.0 - p_home)
