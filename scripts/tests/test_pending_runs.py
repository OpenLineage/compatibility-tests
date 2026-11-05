import json

import pytest

from pending_runs import plan, update

RUN_1 = "https://github.com/o/r/actions/runs/1"
RUN_2 = "https://github.com/o/r/actions/runs/2"


@pytest.fixture
def producer_dir(tmp_path):
    def scenario(component, name, component_versions=None, openlineage_versions=None):
        config = {"tests": []}
        if component_versions:
            config["component_versions"] = component_versions
        if openlineage_versions:
            config["openlineage_versions"] = openlineage_versions
        path = tmp_path / "producer" / component / "scenarios" / name / "config.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(config))

    scenario("spark_dataproc", "bigquery")
    # like bigtable: never valid for the tested versions
    scenario("spark_dataproc", "bigtable", openlineage_versions={"min": "1.0.0", "max": "1.0.0"})
    scenario("dbt", "csv_to_postgres", component_versions={"min": "1.8.0", "max": "1.8.0"})
    return tmp_path / "producer"


def part(component, cv="", ol=""):
    return {"component": component, "component_version": cv, "openlineage_version": ol}


def test_plan_is_the_cross_product_of_each_matrix(producer_dir):
    planned = plan({"spark_dataproc": {"component_version": ["3.5.1", "3.3.2"], "openlineage_versions": ["1.55.0"]}},
                   run_scenarios=False, run_dataplex=False, producer_dir=producer_dir)
    assert planned == [part("spark_dataproc", "3.3.2", "1.55.0"), part("spark_dataproc", "3.5.1", "1.55.0")]


def test_plan_drops_pairs_without_a_valid_scenario(producer_dir):
    # dbt 1.12.6 has no scenario (csv_to_postgres is gated to 1.8.0), so it can never produce a report
    planned = plan({"dbt": {"component_version": ["1.8.0", "1.12.6"], "openlineage_versions": ["1.55.0"]}},
                   run_scenarios=False, run_dataplex=False, producer_dir=producer_dir)
    assert planned == [part("dbt", "1.8.0", "1.55.0")]


def test_plan_includes_consumers_without_versions(producer_dir):
    planned = plan({}, run_scenarios=True, run_dataplex=True, producer_dir=producer_dir)
    assert planned == [part("dataplex"), part("scenarios")]


def test_plan_skips_producers_that_dont_run(producer_dir):
    assert plan({"spark_dataproc": None, "dbt": ""}, run_scenarios=False, run_dataplex=False,
                producer_dir=producer_dir) == []


def report_entry(name, cv="", ol=""):
    return {"name": name, "component_type": "producer", "component_version": cv, "openlineage_version": ol,
            "scenarios": []}


def test_update_drops_done_parts_and_records_new_failures():
    planned = [part("spark_dataproc", "3.5.1", "1.55.0"), part("dbt", "1.8.0", "1.55.0")]
    reports = [report_entry("dbt", "1.8.0", "1.55.0")]

    pending = update(planned, reports, [], RUN_1)

    assert pending == [dict(part("spark_dataproc", "3.5.1", "1.55.0"), failures=1,
                            first_failed_run=RUN_1, last_failed_run=RUN_1)]


def test_update_counts_consecutive_failures_and_keeps_the_first_run():
    planned = [part("spark_dataproc", "3.5.1", "1.55.0")]
    old = [dict(part("spark_dataproc", "3.5.1", "1.55.0"), failures=2, first_failed_run=RUN_1, last_failed_run=RUN_1)]

    [entry] = update(planned, [], old, RUN_2)

    assert entry["failures"] == 3
    assert entry["first_failed_run"] == RUN_1
    assert entry["last_failed_run"] == RUN_2


def test_update_drops_a_recovered_part():
    planned = [part("spark_dataproc", "3.5.1", "1.55.0")]
    old = [dict(part("spark_dataproc", "3.5.1", "1.55.0"), failures=4, first_failed_run=RUN_1, last_failed_run=RUN_1)]

    assert update(planned, [report_entry("spark_dataproc", "3.5.1", "1.55.0")], old, RUN_2) == []


def test_update_keeps_pending_parts_that_werent_planned():
    # e.g. a manual run with only dbt enabled
    old = [dict(part("hive_dataproc", "3.1.3", "1.55.0"), failures=1, first_failed_run=RUN_1, last_failed_run=RUN_1)]

    assert update([part("dbt", "1.8.0", "1.55.0")], [report_entry("dbt", "1.8.0", "1.55.0")], old, RUN_2) == old


def test_update_without_any_report_makes_everything_pending():
    planned = [part("dataplex"), part("scenarios")]

    pending = update(planned, [], [], RUN_1)

    assert [(p["component"], p["failures"]) for p in pending] == [("dataplex", 1), ("scenarios", 1)]


def test_update_matches_consumers_by_name():
    planned = [part("dataplex")]
    assert update(planned, [report_entry("dataplex")], [], RUN_1) == []


def test_read_reports_ignores_files_produced_by_the_comparison(tmp_path):
    from pending_runs import read_reports
    (tmp_path / "spark-dataproc-3.5.1-1.55.0-report.json").write_text(json.dumps([report_entry("spark_dataproc", "3.5.1", "1.55.0")]))
    for name in ["report.json", "updated-report.json", "new-report.json", "retention-failures-report.json"]:
        (tmp_path / name).write_text(json.dumps([report_entry("dbt", "1.8.0", "1.55.0")]))
    (tmp_path / "planned.json").write_text("[]")

    assert [(e["name"], e["component_version"]) for e in read_reports(tmp_path)] == [("spark_dataproc", "3.5.1")]


def test_summary_lists_pending_parts():
    from pending_runs import summary
    text = summary([dict(part("spark_dataproc", "3.5.1", "1.55.0"), failures=3, first_failed_run=RUN_1, last_failed_run=RUN_2)])
    assert "spark_dataproc" in text and "3.5.1" in text and "1.55.0" in text and "| 3 |" in text
    assert summary([]) == "No parts without a result.\n"
