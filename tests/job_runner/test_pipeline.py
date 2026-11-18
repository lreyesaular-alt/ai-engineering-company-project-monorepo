from datetime import date
from unittest.mock import patch

import scripts.nightly_export as nightly


def test_pipeline_uses_correct_week_start():
    target_date = date(2026, 11, 18)

    with patch.object(nightly.subprocess, "run") as run:
        nightly.run_pipeline(target_date)

        run.assert_called_once_with(
            [
                nightly.sys.executable,
                str(
                    nightly.REPO_ROOT
                    / "data"
                    / "pipelines"
                    / "pipeline.py"
                ),
                "--week-start",
                "2026-11-16",
            ],
            cwd=nightly.REPO_ROOT,
            check=True,
        )

def test_pipeline_propagates_subprocess_error():
    import subprocess

    target_date = date(2026, 11, 18)
    error = subprocess.CalledProcessError(1, ["pipeline.py"])

    with patch.object(
        nightly.subprocess,
        "run",
        side_effect=error,
    ):
        try:
            nightly.run_pipeline(target_date)
        except subprocess.CalledProcessError as caught:
            assert caught is error
        else:
            raise AssertionError(
                "El pipeline debe propagar el error del subproceso"
            )
