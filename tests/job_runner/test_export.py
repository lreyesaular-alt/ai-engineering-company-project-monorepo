import csv
from datetime import date
from unittest.mock import MagicMock, patch

import scripts.nightly_export as nightly


def test_csv_export_and_no_overwrite(tmp_path):
    target_date = date(2099, 6, 6)

    result = MagicMock()
    result.keys.return_value = ["id", "timestamp", "event_type"]
    result.__iter__.return_value = iter([
        [1, "2099-06-06T10:00:00+00:00", "page_view"],
        [2, "2099-06-06T11:00:00+00:00", "click"],
    ])

    connection = MagicMock()
    connection.execute.return_value = result

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection

    with (
        patch.object(nightly, "RAW_DIR", tmp_path),
        patch.object(nightly, "get_engine", return_value=engine),
    ):
        csv_path = nightly.export_telemetry_csv(target_date)

        with csv_path.open(newline="", encoding="utf-8") as file:
            rows = list(csv.reader(file))

        assert rows == [
            ["id", "timestamp", "event_type"],
            ["1", "2099-06-06T10:00:00+00:00", "page_view"],
            ["2", "2099-06-06T11:00:00+00:00", "click"],
        ]

        original_content = csv_path.read_bytes()
        second_path = nightly.export_telemetry_csv(target_date)

        assert second_path == csv_path
        assert csv_path.read_bytes() == original_content
        assert connection.execute.call_count == 1
        engine.dispose.assert_called_once()
