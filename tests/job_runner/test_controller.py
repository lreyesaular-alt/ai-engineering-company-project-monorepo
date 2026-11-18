
from contextlib import nullcontext
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

import scripts.nightly_export as nightly


def test_completed_job_is_skipped():
    with (
        patch.object(
            nightly, "job_execution_lock",
            return_value=nullcontext(True),
        ),
        patch.object(nightly, "recover_abandoned_job_runs") as recover,
        patch.object(
            nightly, "get_target_date",
            return_value=date(2099, 6, 3),
        ),
        patch.object(nightly, "has_completed_for_date", return_value=True),
        patch.object(nightly, "create_job_run") as create,
        patch.object(nightly, "export_telemetry_csv") as export,
        patch.object(nightly, "run_pipeline") as pipeline,
    ):
        nightly.main()

        recover.assert_called_once()
        create.assert_not_called()
        export.assert_not_called()
        pipeline.assert_not_called()


def test_active_job_blocks_new_execution():
    with (
        patch.object(
            nightly, "job_execution_lock",
            return_value=nullcontext(True),
        ),
        patch.object(nightly, "recover_abandoned_job_runs"),
        patch.object(
            nightly, "get_target_date",
            return_value=date(2099, 6, 4),
        ),
        patch.object(nightly, "has_completed_for_date", return_value=False),
        patch.object(nightly, "create_job_run", return_value="test-id"),
        patch.object(nightly, "start_job_run", return_value=False),
        patch.object(nightly, "export_telemetry_csv") as export,
        patch.object(nightly, "run_pipeline") as pipeline,
    ):
        nightly.main()

        export.assert_not_called()
        pipeline.assert_not_called()


def test_successful_job_is_completed():
    target_date = date(2099, 6, 2)
    csv_path = Path("data/raw/telemetry_2099-06-02.csv")

    with (
        patch.object(
            nightly, "job_execution_lock",
            return_value=nullcontext(True),
        ),
        patch.object(nightly, "recover_abandoned_job_runs"),
        patch.object(nightly, "get_target_date", return_value=target_date),
        patch.object(nightly, "has_completed_for_date", return_value=False),
        patch.object(nightly, "create_job_run", return_value="test-success-id"),
        patch.object(nightly, "start_job_run", return_value=True),
        patch.object(
            nightly, "export_telemetry_csv", return_value=csv_path
        ) as export,
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


def test_export_failure_marks_job_as_failed():
    target_date = date(2099, 6, 7)

    with (
        patch.object(
            nightly, "job_execution_lock",
            return_value=nullcontext(True),
        ),
        patch.object(nightly, "recover_abandoned_job_runs"),
        patch.object(nightly, "get_target_date", return_value=target_date),
        patch.object(nightly, "has_completed_for_date", return_value=False),
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
        patch.object(
            nightly, "job_execution_lock",
            return_value=nullcontext(True),
        ),
        patch.object(nightly, "recover_abandoned_job_runs"),
        patch.object(nightly, "get_target_date", return_value=target_date),
        patch.object(nightly, "has_completed_for_date", return_value=False),
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


def test_pipeline_failure_marks_job_as_failed():
    target_date = date(2099, 6, 9)
    csv_path = Path("data/raw/telemetry_2099-06-09.csv")

    with (
        patch.object(
            nightly, "job_execution_lock",
            return_value=nullcontext(True),
        ),
        patch.object(nightly, "recover_abandoned_job_runs"),
        patch.object(nightly, "get_target_date", return_value=target_date),
        patch.object(nightly, "has_completed_for_date", return_value=False),
        patch.object(nightly, "create_job_run", return_value="test-pipeline-id"),
        patch.object(nightly, "start_job_run", return_value=True),
        patch.object(
            nightly, "export_telemetry_csv", return_value=csv_path
        ),
        patch.object(
            nightly,
            "run_pipeline",
            side_effect=RuntimeError("Fallo simulado del pipeline"),
        ),
        patch.object(nightly, "finish_job_run") as finish,
    ):
        with pytest.raises(
            RuntimeError,
            match="Fallo simulado del pipeline",
        ):
            nightly.main()

        finish.assert_called_once()

        assert finish.call_args.args[0] == "test-pipeline-id"
        assert finish.call_args.kwargs["status"] == "failed"
        assert "Fallo simulado del pipeline" in (
            finish.call_args.kwargs["error_message"]
        )


def test_advisory_lock_rejection_skips_everything():
    with (
        patch.object(
            nightly, "job_execution_lock",
            return_value=nullcontext(False),
        ),
        patch.object(nightly, "recover_abandoned_job_runs") as recover,
        patch.object(nightly, "get_target_date") as get_date,
        patch.object(nightly, "create_job_run") as create,
        patch.object(nightly, "export_telemetry_csv") as export,
        patch.object(nightly, "run_pipeline") as pipeline,
    ):
        nightly.main()

        recover.assert_not_called()
        get_date.assert_not_called()
        create.assert_not_called()
        export.assert_not_called()
        pipeline.assert_not_called()


def test_abandoned_jobs_are_recovered_before_new_execution():
    target_date = date(2099, 6, 10)

    with (
        patch.object(
            nightly, "job_execution_lock",
            return_value=nullcontext(True),
        ),
        patch.object(
            nightly, "recover_abandoned_job_runs", return_value=2
        ) as recover,
        patch.object(nightly, "get_target_date", return_value=target_date),
        patch.object(nightly, "has_completed_for_date", return_value=True),
    ):
        nightly.main()

        recover.assert_called_once()
