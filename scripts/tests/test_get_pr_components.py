import pytest

from get_pr_components import select_components

ALL_REAL = {"scenarios", "dataplex", "spark_dataproc", "hive_dataproc", "dbt"}


def real(selection):
    return {c for c, run in selection["run"].items() if run}


@pytest.mark.parametrize("path, expected_real", [
    # today's paths keep their behaviour
    ("producer/dbt/scenarios/csv_to_postgres/config.json", {"dbt"}),
    ("producer/spark_dataproc/scenarios/bigquery/test/test.py", {"spark_dataproc"}),
    ("producer/hive_dataproc/runner/dataproc_workflow.py", {"hive_dataproc"}),
    ("consumer/scenarios/airflow/events/event.json", {"scenarios"}),
    ("consumer/consumers/dataplex/validator/validator.py", {"dataplex"}),
    # workflow files of a component
    (".github/workflows/producer_spark_dataproc.yml", {"spark_dataproc"}),
    (".github/workflows/producer_hive_dataproc.yml", {"hive_dataproc"}),
    (".github/workflows/producer_dbt.yml", {"dbt"}),
    (".github/workflows/check_scenarios.yml", {"scenarios"}),
    (".github/workflows/consumer_dataplex.yml", {"dataplex"}),
    # shared actions and scripts run every component using them
    (".github/actions/dataproc_cluster/action.yml", {"spark_dataproc", "hive_dataproc"}),
    (".github/actions/get_openlineage_artifacts/action.yml", {"hive_dataproc"}),
    ("scripts/get_valid_test_scenarios.sh", {"spark_dataproc", "hive_dataproc", "dbt"}),
    ("dev/dataproc/dataproc_workflow.py", {"spark_dataproc", "hive_dataproc"}),
    ("dev/dataproc/install_jars.sh", {"spark_dataproc", "hive_dataproc"}),
    ("dev/defaults.env", {"spark_dataproc", "hive_dataproc"}),
    ("dev/lib/status.sh", {"spark_dataproc", "hive_dataproc", "dbt"}),
])
def test_real_runs(path, expected_real):
    selection = select_components([path])
    assert real(selection) == expected_real
    assert selection["revalidate"] == []
    assert selection["any_run"]


def test_validator_change_revalidates_dataproc_and_runs_cheap_components():
    selection = select_components(["scripts/validate_ol_events.py"])
    assert real(selection) == {"dbt", "scenarios"}
    assert selection["revalidate"] == ["hive_dataproc", "spark_dataproc"]
    assert selection["any_run"]


@pytest.mark.parametrize("path", ["scripts/report.py", "scripts/compare_events.py"])
def test_modules_imported_by_dataplex_also_run_dataplex(path):
    selection = select_components([path])
    assert real(selection) == {"dbt", "scenarios", "dataplex"}
    assert selection["revalidate"] == ["hive_dataproc", "spark_dataproc"]


def test_local_validation_helpers_count_as_validation_code():
    selection = select_components(["dev/validation/validate_locally.sh"])
    assert real(selection) == {"dbt", "scenarios"}
    assert selection["revalidate"] == ["hive_dataproc", "spark_dataproc"]


def test_validation_action_counts_as_validation_code():
    selection = select_components([".github/actions/run_event_validation/action.yml"])
    assert real(selection) == {"dbt", "scenarios"}
    assert selection["revalidate"] == ["hive_dataproc", "spark_dataproc"]


def test_real_run_replaces_revalidation_of_the_same_component():
    selection = select_components(["producer/spark_dataproc/scenarios/bigquery/config.json",
                                   "scripts/validate_ol_events.py"])
    assert real(selection) == {"spark_dataproc", "dbt", "scenarios"}
    assert selection["revalidate"] == ["hive_dataproc"]


def test_revalidation_workflow_only_revalidates():
    selection = select_components([".github/workflows/revalidate_stored_events.yml"])
    assert real(selection) == set()
    assert selection["revalidate"] == ["hive_dataproc", "spark_dataproc"]
    assert selection["any_run"]


@pytest.mark.parametrize("paths", [[], ["README.md"], ["generated-files/report.json"], [".github/workflows/main_pr.yml"]])
def test_unrelated_changes_run_nothing(paths):
    selection = select_components(paths)
    assert real(selection) == set()
    assert selection["revalidate"] == []
    assert not selection["any_run"]


def test_prefix_match_is_anchored():
    # the old grep matched the path anywhere in the file name
    selection = select_components(["docs/producer/dbt/notes.md"])
    assert not selection["any_run"]


def test_github_outputs_format():
    from get_pr_components import to_github_outputs
    lines = to_github_outputs(select_components(["scripts/validate_ol_events.py"]))
    assert "dbt_changed=true" in lines
    assert "scenarios_changed=true" in lines
    assert "spark_dataproc_changed=false" in lines
    assert 'revalidate=["hive_dataproc","spark_dataproc"]' in lines
    assert "any_changed=true" in lines
    assert all(c in ALL_REAL for c in (line.split("_changed")[0] for line in lines if "_changed=" in line and not line.startswith("any")))
