
from unittest.mock import MagicMock, patch

from services.job_runner import run_registry


def test_advisory_lock_is_acquired_and_released():
    engine = MagicMock()
    connection = engine.connect.return_value

    connection.execute.return_value.scalar_one.return_value = True

    with patch.object(
        run_registry, "get_engine", return_value=engine
    ):
        with run_registry.job_execution_lock() as acquired:
            assert acquired is True

    assert connection.execute.call_count == 2
    connection.commit.assert_called()
    connection.close.assert_called_once()
    engine.dispose.assert_called_once()

    acquire_sql = str(connection.execute.call_args_list[0].args[0])
    release_sql = str(connection.execute.call_args_list[1].args[0])

    assert "pg_try_advisory_lock" in acquire_sql
    assert "pg_advisory_unlock" in release_sql


def test_advisory_lock_rejection_does_not_unlock():
    engine = MagicMock()
    connection = engine.connect.return_value

    connection.execute.return_value.scalar_one.return_value = False

    with patch.object(
        run_registry, "get_engine", return_value=engine
    ):
        with run_registry.job_execution_lock() as acquired:
            assert acquired is False

    connection.execute.assert_called_once()
    connection.close.assert_called_once()
    engine.dispose.assert_called_once()


def test_abandoned_jobs_are_marked_as_failed():
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 2

    with patch.object(
        run_registry, "get_engine", return_value=engine
    ):
        recovered = run_registry.recover_abandoned_job_runs()

    assert recovered == 2

    query = str(connection.execute.call_args.args[0])
    params = connection.execute.call_args.args[1]

    assert "UPDATE reporting.job_runs" in query
    assert "status = 'failed'" in query
    assert "status = 'processing'" in query
    assert params["job_name"] == run_registry.JOB_NAME
    assert "abandonada" in params["error_message"]

    engine.dispose.assert_called_once()


def test_no_abandoned_jobs_returns_zero():
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 0

    with patch.object(
        run_registry, "get_engine", return_value=engine
    ):
        recovered = run_registry.recover_abandoned_job_runs()

    assert recovered == 0
    engine.dispose.assert_called_once()
