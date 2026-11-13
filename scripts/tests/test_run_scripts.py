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
