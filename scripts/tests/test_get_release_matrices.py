"""Runs scripts/get_release_matrices.sh against the repo's versions.json files with a temporary pending list."""
import json
import os
import subprocess

from conftest import REPO_ROOT

LATEST_OL = "9.9.0"


def run(tmp_path, pending=None, **env):
    pending_file = tmp_path / "pending_runs.json"
    pending_file.write_text(json.dumps(pending or []))
    full_env = {**os.environ, "LATEST_OL": LATEST_OL, "PENDING_FILE": str(pending_file), **env}
    out = subprocess.run(["bash", "scripts/get_release_matrices.sh"], cwd=REPO_ROOT, env=full_env,
                         capture_output=True, text=True, check=True).stdout
    values = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    return {k: (json.loads(v) if v.startswith("{") else v) for k, v in values.items()}


def pending_part(component, cv="", ol="", failures=1):
    return {"component": component, "component_version": cv, "openlineage_version": ol, "failures": failures,
            "first_failed_run": "r", "last_failed_run": "r"}


def test_nothing_changed_nothing_pending_runs_nothing(tmp_path):
    out = run(tmp_path)
    assert out["any_run"] == "false"
    assert out["spark_dataproc_matrix"] == ""
    assert out["run_spark_dataproc"] == "false"


def test_pending_part_runs_alone(tmp_path):
    out = run(tmp_path, [pending_part("spark_dataproc", "3.5.1", "1.55.0")])
    assert out["spark_dataproc_matrix"] == {"openlineage_versions": ["1.55.0"], "component_version": ["3.5.1"]}
    assert out["run_spark_dataproc"] == "true"
    assert out["run_hive_dataproc"] == "false"
    assert out["any_run"] == "true"
    # consumers run when anything runs
    assert out["run_dataplex"] == "true"


def test_pending_part_is_added_to_a_changed_matrix(tmp_path):
    # a new OL release runs every spark version with it; the pending pair with an older OL is added
    out = run(tmp_path, [pending_part("spark_dataproc", "3.5.1", "1.55.0")], OL_CHANGED="true")
    matrix = out["spark_dataproc_matrix"]
    assert "1.55.0" in matrix["openlineage_versions"] and LATEST_OL in matrix["openlineage_versions"]
    assert "3.5.1" in matrix["component_version"]
    assert len(matrix["openlineage_versions"]) == len(set(matrix["openlineage_versions"]))


def test_pending_scenarios_runs_the_scenarios_check(tmp_path):
    out = run(tmp_path, [pending_part("scenarios")])
    assert out["run_scenarios"] == "true"
    assert out["any_run"] == "true"


def test_pending_dataplex_runs_dataplex(tmp_path):
    out = run(tmp_path, [pending_part("dataplex")])
    assert out["run_dataplex"] == "true"
    assert out["any_run"] == "true"
    assert out["run_spark_dataproc"] == "false"


def test_missing_pending_file_is_like_an_empty_one(tmp_path):
    out = run(tmp_path, PENDING_FILE=str(tmp_path / "missing.json"))
    assert out["any_run"] == "false"
