from datetime import date
from unittest.mock import patch

import scripts.nightly_export as nightly


def test_completed_job_is_skipped():
    with (
        patch.object(nightly, "get_target_date", return_value=date(2099, 6, 3)),
        patch.object(nightly, "has_completed_for_date", return_value=True),
        patch.object(nightly, "create_job_run") as create,
        patch.object(nightly, "export_telemetry_csv") as export,
        patch.object(nightly, "run_pipeline") as pipeline,
    ):
        nightly.main()

        create.assert_not_called()
        export.assert_not_called()
        pipeline.assert_not_called()


def test_active_job_blocks_new_execution():
    with (
        patch.object(nightly, "get_target_date", return_value=date(2099, 6, 4)),
        patch.object(nightly, "has_completed_for_date", return_value=False),
        patch.object(nightly, "has_processing_lock", return_value=True),
        patch.object(nightly, "create_job_run") as create,
        patch.object(nightly, "export_telemetry_csv") as export,
        patch.object(nightly, "run_pipeline") as pipeline,
    ):
        nightly.main()

        create.assert_not_called()
        export.assert_not_called()
        pipeline.assert_not_called()
from datetime import date
from pathlib import Path
from unittest.mock import patch

import scripts.nightly_export as nightly


def test_successful_job_is_completed():
    target_date = date(2099, 6, 2)
    csv_path = Path("data/raw/telemetry_2099-06-02.csv")

    with (
        patch.object(nightly, "get_target_date", return_value=target_date),
        patch.object(nightly, "has_completed_for_date", return_value=False),
        patch.object(nightly, "has_processing_lock", return_value=False),
        patch.object(nightly, "create_job_run", return_value="test-success-id"),
        patch.object(nightly, "start_job_run", return_value=True),
        patch.object(nightly, "export_telemetry_csv", return_value=csv_path) as export,
        patch.object(nightly, "run_pipeline") as pipeline,
        patch.object(nightly, "finish_job_run") as finish,
    ):
        nightly.main()

        export.assert_called_once_with(target_date)
        pipeline.assert_called_once_with(target_date)
        finish.assert_called_once_with(
            "test-success-id",
            status="completed",
            csv_path=str(csv_path),
        )
import pytest


def test_export_failure_marks_job_as_failed():
    target_date = date(2099, 6, 7)

    with (
        patch.object(nightly, "get_target_date", return_value=target_date),
        patch.object(nightly, "has_completed_for_date", return_value=False),
        patch.object(nightly, "has_processing_lock", return_value=False),
        patch.object(nightly, "create_job_run", return_value="test-failed-id"),
        patch.object(nightly, "start_job_run", return_value=True),
        patch.object(
            nightly,
            "export_telemetry_csv",
            side_effect=RuntimeError("Fallo simulado"),
        ),
        patch.object(nightly, "run_pipeline") as pipeline,
        patch.object(nightly, "finish_job_run") as finish,
    ):
        with pytest.raises(RuntimeError, match="Fallo simulado"):
            nightly.main()

        pipeline.assert_not_called()
        finish.assert_called_once()

        assert finish.call_args.args[0] == "test-failed-id"
        assert finish.call_args.kwargs["status"] == "failed"
        assert "Fallo simulado" in finish.call_args.kwargs["error_message"]
def test_atomic_lock_rejection_skips_execution():
    target_date = date(2099, 6, 8)

    with (
        patch.object(nightly, "get_target_date", return_value=target_date),
        patch.object(nightly, "has_completed_for_date", return_value=False),
        patch.object(nightly, "has_processing_lock", return_value=False),
        patch.object(nightly, "create_job_run", return_value="test-blocked-id"),
        patch.object(nightly, "start_job_run", return_value=False) as start,
        patch.object(nightly, "export_telemetry_csv") as export,
        patch.object(nightly, "run_pipeline") as pipeline,
        patch.object(nightly, "finish_job_run") as finish,
    ):
        nightly.main()

        start.assert_called_once_with("test-blocked-id")
        export.assert_not_called()
        pipeline.assert_not_called()
        finish.assert_not_called()
