from datetime import date
from unittest.mock import patch

from scripts.nightly_export import get_target_date, get_week_start


def test_week_start_from_wednesday():
    assert get_week_start(date(2026, 11, 18)) == date(2026, 11, 16)


def test_week_start_from_sunday():
    assert get_week_start(date(2026, 11, 22)) == date(2026, 11, 16)


def test_target_date_from_environment():
    with patch.dict("os.environ", {"TARGET_DATE": "2026-11-17"}):
        assert get_target_date() == date(2026, 11, 17)
