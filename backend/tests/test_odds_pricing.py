"""
Unit tests for app/services/odds_pricing.py

The derived moneyline is a fair, no-vig estimate from the spread. We check the
anchors (pick'em is symmetric, favourites are negative) and the key invariant:
fair odds means the two implied probabilities sum to 1.
"""
from app.services.odds_pricing import (
    spread_to_home_win_prob,
    prob_to_american,
    spread_to_moneyline,
)


def _implied_prob(american: int) -> float:
    if american < 0:
        return -american / (-american + 100)
    return 100 / (american + 100)


class TestWinProb:
    def test_pickem_is_even(self):
        assert spread_to_home_win_prob(0.0) == 0.5

    def test_home_favourite_above_half(self):
        assert spread_to_home_win_prob(-7.0) > 0.5

    def test_home_underdog_below_half(self):
        assert spread_to_home_win_prob(7.0) < 0.5

    def test_symmetry(self):
        assert spread_to_home_win_prob(-3.0) + spread_to_home_win_prob(3.0) == 1.0


class TestProbToAmerican:
    def test_even_money(self):
        assert prob_to_american(0.5) == 100

    def test_favourite_is_negative(self):
        assert prob_to_american(0.7) < 0

    def test_underdog_is_positive(self):
        assert prob_to_american(0.3) > 0

    def test_extremes_are_finite(self):
        assert isinstance(prob_to_american(0.0), int)
        assert isinstance(prob_to_american(1.0), int)


class TestSpreadToMoneyline:
    def test_pickem_symmetric(self):
        home, away = spread_to_moneyline(0.0)
        assert home == away == 100

    def test_favourite_side_negative(self):
        home, away = spread_to_moneyline(-7.0)  # home favoured
        assert home < 0 < away

    def test_fair_no_vig(self):
        # Implied probabilities of a fair line sum to ~1 (no bookmaker margin).
        home, away = spread_to_moneyline(-6.0)
        assert abs(_implied_prob(home) + _implied_prob(away) - 1.0) < 0.02
