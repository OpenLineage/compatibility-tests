"""Runs scripts/check_structure.sh on a copy of the repo's structure, broken in one place at a time."""
import shutil
import subprocess

import pytest

from conftest import REPO_ROOT


@pytest.fixture
def tree(tmp_path):
    for directory in ["consumer", "producer", "generated-files"]:
        shutil.copytree(REPO_ROOT / directory, tmp_path / directory)
    return tmp_path


def check(base):
    return subprocess.run(["bash", str(REPO_ROOT / "scripts" / "check_structure.sh"), str(base)],
                          capture_output=True, text=True)


def test_repo_structure_passes(tree):
    result = check(tree)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("scenario_md", [
    "producer/spark_dataproc/scenarios/bigquery/scenario.md",
    "consumer/scenarios/airflow/scenario.md",
    "consumer/consumers/dataplex/scenarios/airflow/scenario.md",
])
def test_empty_scenario_md_fails(tree, scenario_md):
    (tree / scenario_md).write_text("")
    result = check(tree)
    assert result.returncode == 1
    assert f"Empty: {tree / scenario_md}" in result.stdout


def test_missing_scenario_md_still_fails(tree):
    (tree / "producer/spark_dataproc/scenarios/bigquery/scenario.md").unlink()
    assert check(tree).returncode == 1
