import json
import subprocess
import sys

import pytest

from check_scenario_coverage import find_gaps
from conftest import REPO_ROOT, SCRIPTS_DIR


@pytest.fixture
def producer_dir(tmp_path):
    def producer(name, component_versions, openlineage_versions, scenarios):
        base = tmp_path / "producer" / name
        base.mkdir(parents=True)
        (base / "versions.json").write_text(json.dumps(
            {"component_version": component_versions, "openlineage_versions": openlineage_versions}))
        for scenario, config in scenarios.items():
            (base / "scenarios" / scenario).mkdir(parents=True)
            (base / "scenarios" / scenario / "config.json").write_text(json.dumps({"tests": [], **config}))

    producer("spark_dataproc", ["3.5.1", "3.3.2"], ["1.30.0"], {
        "bigquery": {},
        "bigtable": {"openlineage_versions": {"min": "1.0.0", "max": "1.0.0"}},
        "iceberg": {"component_versions": {"min": "3.5.0"}},
    })
    producer("dbt", ["1.8.0"], ["1.30.0"], {"csv_to_postgres": {"component_versions": {"min": "1.8.0", "max": "1.8.0"}}})
    return tmp_path / "producer"


def test_scenario_valid_for_no_tested_pair_is_reported(producer_dir):
    gaps = find_gaps(producer_dir, latest_ol="1.55.0", latest_components={})
    assert [(g.producer, g.scenario) for g in gaps.never_running] == [("spark_dataproc", "bigtable")]


def test_component_version_without_scenarios_is_reported(producer_dir):
    gaps = find_gaps(producer_dir, latest_ol="1.55.0", latest_components={"dbt": "1.12.6"})
    assert [(g.producer, g.component_version) for g in gaps.uncovered_versions] == [("dbt", "1.12.6")]


def test_latest_openlineage_counts_as_tested(producer_dir):
    (producer_dir / "spark_dataproc" / "scenarios" / "new_feature").mkdir(parents=True)
    (producer_dir / "spark_dataproc" / "scenarios" / "new_feature" / "config.json").write_text(
        json.dumps({"tests": [], "openlineage_versions": {"min": "1.55.0"}}))
    gaps = find_gaps(producer_dir, latest_ol="1.55.0", latest_components={})
    assert "new_feature" not in [g.scenario for g in gaps.never_running]


def test_command_line_warns_and_exits_zero(tmp_path):
    summary = tmp_path / "summary.md"
    result = subprocess.run([sys.executable, str(SCRIPTS_DIR / "check_scenario_coverage.py"), "--summary", str(summary)],
                            cwd=REPO_ROOT, capture_output=True, text=True)
    assert result.returncode == 0
    # the repo's current gaps (2026-11): bigtable is capped at OL 1.0.0, dbt's latest release has no scenario
    assert "::warning file=producer/spark_dataproc/scenarios/bigtable/config.json::" in result.stdout
    assert "dbt" in summary.read_text()
