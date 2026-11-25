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


RUN_SCRIPT = "producer/dbt/run_dbt_tests.sh"


@pytest.mark.parametrize("run_script", [RUN_SCRIPT, "producer/template/run_template_tests.sh"])
def test_empty_run_script_fails(tree, run_script):
    (tree / run_script).write_text("")
    result = check(tree)
    assert result.returncode == 1
    assert f"Empty: {tree / run_script}" in result.stdout


def test_run_script_that_isnt_executable_fails(tree):
    (tree / RUN_SCRIPT).chmod(0o644)
    result = check(tree)
    assert result.returncode == 1
    assert f"Not executable: {tree / RUN_SCRIPT}" in result.stdout


def test_run_script_with_a_syntax_error_fails(tree):
    with open(tree / RUN_SCRIPT, "a") as f:
        f.write("\nif true; then\n")
    result = check(tree)
    assert result.returncode == 1
    assert f"Syntax error: {tree / RUN_SCRIPT}" in result.stdout
