from datetime import date

import pytest

from src.models import DailyStats


def test_daily_stats_from_prices() -> None:
    stats = DailyStats.from_prices(date(2025, 1, 1), [10, 20, 30])
    assert stats.count == 3
    assert stats.min_price == 10
    assert stats.max_price == 30
    assert stats.mean_price == 20.0
    assert stats.median_price == 20.0


def test_daily_stats_from_prices_empty() -> None:
    with pytest.raises(ValueError):
        DailyStats.from_prices(date(2025, 1, 1), [])
