"""Command line behaviour of the scripts used to run producers (CI steps and local runs)."""
import subprocess

import pytest

from conftest import REPO_ROOT

SCRIPTS = [
    "dev/dataproc/create_cluster.sh",
    "dev/dataproc/delete_cluster.sh",
    "dev/dataproc/gcs_upload.sh",
    "dev/validation/get_ol_specs.sh",
    "dev/validation/validate_locally.sh",
    "producer/dbt/run_dbt_tests.sh",
    "producer/dbt/runner/run_scenarios.sh",
    "producer/hive_dataproc/run_hive_dataproc_tests.sh",
    "producer/hive_dataproc/runner/create_cluster.sh",
    "producer/hive_dataproc/runner/run_scenarios.sh",
    "producer/spark_dataproc/run_spark_dataproc_tests.sh",
    "producer/spark_dataproc/runner/create_cluster.sh",
    "producer/spark_dataproc/runner/run_scenarios.sh",
    "producer/template/run_template_tests.sh",
]


@pytest.mark.parametrize("script", SCRIPTS)
def test_help_exits_zero(script):
    result = subprocess.run(["bash", str(REPO_ROOT / script), "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Usage:" in result.stderr


@pytest.mark.parametrize("script", [s for s in SCRIPTS if s != "dev/validation/get_ol_specs.sh"])
def test_unknown_option_fails_with_usage(script):
    result = subprocess.run(["bash", str(REPO_ROOT / script), "--no-such-option"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "Usage:" in result.stderr


@pytest.mark.parametrize("script", SCRIPTS)
def test_missing_required_arguments_fail(script):
    result = subprocess.run(["bash", str(REPO_ROOT / script)], capture_output=True, text=True)
    assert result.returncode != 0


# ---------- dbt csv_to_postgres: a stuck Docker engine fails fast ----------

FAKE_DOCKER = """#!/bin/bash
# compose v2 is found; `info` or `compose up` hang like a stuck engine when asked to
[ "$1 $2" = "compose version" ] && exit 0
[ "$1" = info ] && { [ -n "$STUCK_INFO" ] && exec sleep 600; exit 0; }
[ "$1 $4" = "compose up" ] && [ -n "$STUCK_UP" ] && exec sleep 600
exit 0
"""


def free_port():
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]  # closed when the block ends, so nothing listens there


@pytest.mark.parametrize("stuck, message", [("STUCK_INFO", "The Docker engine didn't answer within 2s"),
                                            ("STUCK_UP", "took more than 2s")])
def test_dbt_scenario_fails_fast_when_docker_hangs(tmp_path, stuck, message):
    import os
    import time
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(0o755)
    events = tmp_path / "events"
    events.mkdir()
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", stuck: "1", "DBT_POSTGRES_HOST": "127.0.0.1",
           "DBT_POSTGRES_PORT": str(free_port()), "DOCKER_CHECK_TIMEOUT": "2", "DOCKER_UP_TIMEOUT": "2"}
    started = time.monotonic()
    result = subprocess.run(["bash", str(REPO_ROOT / "producer/dbt/scenarios/csv_to_postgres/test/run.sh"), str(events)],
                            capture_output=True, text=True, env=env, timeout=60)
    assert result.returncode != 0
    assert message in result.stderr
    assert time.monotonic() - started < 15
