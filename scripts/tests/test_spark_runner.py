"""The Spark runner scripts (producer/spark_dataproc/runner/) with stub `python`, `gcloud` and `curl`."""
import json
import os
import subprocess

import pytest

from conftest import REPO_ROOT

RUNNER = REPO_ROOT / "producer" / "spark_dataproc" / "runner"
OL_JARS = ("1.32.0:openlineage-spark_2.12-1.32.0.jar:transports-gcs-1.32.0.jar;"
           "1.55.0:openlineage-spark_2.12-1.55.0.jar:transports-gcs-1.55.0.jar")


@pytest.fixture
def stubs(tmp_path):
    """Stub commands on PATH; returns (run, recorded). STUB_RUNNER=crash makes run-scenarios fail without status.json,
    STUB_GCS_HAS lists the gs:// objects that exist."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.jsonl"
    record = f"""python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "$(basename "$0")" "$@" >> {calls}"""
    (bin_dir / "python").write_text(f"""#!/bin/bash
{record}
if [[ "$2" == run-scenarios ]]; then
  [[ "${{STUB_RUNNER:-}}" == crash ]] && exit 1
  logs=""; while [[ $# -gt 0 ]]; do [[ "$1" == --logs-directory ]] && logs="$2"; shift; done
  echo '[{{"scenario": "bigquery", "state": "DONE", "job_id": "j1"}}]' > "$logs/status.json"
  echo "driver output" > "$logs/bigquery.log"
fi
exit 0
""")
    (bin_dir / "gcloud").write_text(f"""#!/bin/bash
{record}
if [[ "$1 $2" == "storage ls" ]]; then [[ " ${{STUB_GCS_HAS:-}} " == *" $3 "* ]]; exit; fi
exit 0
""")
    (bin_dir / "curl").write_text(f"""#!/bin/bash
{record}
while [[ $# -gt 0 ]]; do [[ "$1" == -o ]] && touch "$2"; shift; done
""")
    for stub in bin_dir.iterdir():
        stub.chmod(0o755)

    def run(script, *args, env=None):
        full_env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", **(env or {})}
        for name in ("GITHUB_ACTIONS", "POSTGRESQL_USER", "POSTGRESQL_PASSWORD"):
            full_env.pop(name, None)
        full_env.update(env or {})
        return subprocess.run(["bash", str(RUNNER / script), *args], env=full_env, capture_output=True, text=True)

    def recorded(command=None):
        lines = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
        return [c for c in lines if command is None or c[0] == command]

    return run, recorded


def option(argv, name):
    return argv[argv.index(name) + 1]


def metadata(create):
    return dict(item.split("=", 1) for item in option(create, "--metadata").split(","))


def test_create_cluster_for_3_5_1(stubs):
    run, recorded = stubs
    result = run("create_cluster.sh", "--spark-release", "3.5.1", "--cluster-name", "c1", "--openlineage-jars", OL_JARS,
                 env={"STUB_GCS_HAS": "gs://open-lineage-e2e/jars/spark-3.5-bigquery-0.42.0.jar"})
    assert result.returncode == 0, result.stderr

    assert recorded("curl") == []  # the connector is already staged
    [create] = recorded("python")
    assert create[2] == "create-cluster"
    assert option(create, "--dataproc-image-version") == "2.2-ubuntu22"
    assert option(create, "--master-machine-type") == "n1-standard-4"
    assert metadata(create) == {
        "SPARK_BQ_CONNECTOR_URL": "gs://open-lineage-e2e/jars/spark-3.5-bigquery-0.42.0.jar",
        "JARS": ";".join([
            "gs://open-lineage-e2e/jars/spark-3.5-bigquery-0.42.0.jar",
            "gs://spark-lib/spanner/spark-3.1-spanner-1.1.0.jar",
            "gs://open-lineage-e2e/jars/spark-bigtable_2.12-0.5.0-SNAPSHOT.jar",
            "gs://open-lineage-e2e/jars/postgresql-42.5.6.jar",
            "gs://open-lineage-e2e/jars/delta-spark_2.12-3.3.1.jar",
            "gs://open-lineage-e2e/jars/delta-storage-3.3.1.jar",
            "gs://open-lineage-e2e/jars/iceberg-spark-runtime-3.5_2.12-1.10.0.jar",
            "gs://open-lineage-e2e/jars/iceberg-gcp-bundle-1.10.0.jar",
            "gs://open-lineage-e2e/jars/iceberg-bigquery-1.10.0.jar",
        ]),
        "JARS_TARGET_DIR": "/usr/lib/spark/jars",
        "MASTER_JARS": "/opt/openlineage/1.32.0=gs://open-lineage-e2e/jars/openlineage-spark_2.12-1.32.0.jar;"
                       "/opt/openlineage/1.55.0=gs://open-lineage-e2e/jars/openlineage-spark_2.12-1.55.0.jar",
        "enable-cloud-sql-hive-metastore": "false",
        "additional-cloud-sql-instances": "gcp-open-lineage-testing:us-central1:open-lineage-e2e=tcp:3307",
    }
    scripts = "gs://open-lineage-e2e/scripts/c1"
    assert option(create, "--initialization-actions") == f"{scripts}/install_jars.sh,{scripts}/cloud_sql_proxy.sh"
    gcloud = recorded("gcloud")
    assert ["gcloud", "storage", "cp", str(REPO_ROOT / "dev/dataproc/install_jars.sh"), f"{scripts}/install_jars.sh"] in gcloud
    assert gcloud[-1] == ["gcloud", "storage", "rm", "-r", scripts]  # removed once the cluster is created


def test_create_cluster_for_3_1_3_stages_the_connector(stubs):
    run, recorded = stubs
    result = run("create_cluster.sh", "--spark-release", "3.1.3", "--cluster-name", "c1", "--openlineage-jars", OL_JARS,
                 "--bucket", "mine")
    assert result.returncode == 0, result.stderr

    [curl] = recorded("curl")
    assert curl[-1] == ("https://repo1.maven.org/maven2/com/google/cloud/spark/spark-3.1-bigquery/0.42.0/"
                        "spark-3.1-bigquery-0.42.0.jar")
    [create] = recorded("python")
    assert option(create, "--dataproc-image-version") == "2.0-ubuntu18"
    jars = metadata(create)["JARS"].split(";")
    assert jars[0] == "gs://mine/jars/spark-3.1-bigquery-0.42.0.jar"
    assert metadata(create)["SPARK_BQ_CONNECTOR_URL"] == "gs://mine/jars/spark-3.1-bigquery-0.42.0.jar"
    assert not any("iceberg" in j or "delta" in j for j in jars)
    assert metadata(create)["MASTER_JARS"].startswith("/opt/openlineage/1.32.0=gs://mine/jars/")


@pytest.mark.parametrize("args, message", [
    (["--spark-release", "9.9.9", "--openlineage-jars", OL_JARS], "9.9.9"),
    (["--spark-release", "3.5.1", "--openlineage-jars", "1.55.0"], "Bad --openlineage-jars entry"),
])
def test_create_cluster_rejects_bad_input(stubs, args, message):
    run, recorded = stubs
    result = run("create_cluster.sh", "--cluster-name", "c1", *args,
                 env={"STUB_GCS_HAS": "gs://open-lineage-e2e/jars/spark-3.5-bigquery-0.42.0.jar"})
    assert result.returncode != 0
    assert message in result.stderr
    assert recorded("python") == []


RUN_ARGS = ["--cluster-name", "c1", "--spark-release", "3.5.1", "--ol-release", "1.55.0", "--scenarios", "bigquery;hive",
            "--openlineage-jars", OL_JARS, "--run-key", "123-1"]


def test_run_scenarios_runs_one_openlineage_version(stubs, tmp_path):
    run, recorded = stubs
    logs = tmp_path / "logs"
    result = run("run_scenarios.sh", *RUN_ARGS, "--logs-dir", str(logs),
                 env={"POSTGRESQL_USER": "u", "POSTGRESQL_PASSWORD": "p"})
    assert result.returncode == 0, result.stderr

    [job] = recorded("python")
    assert job[2] == "run-scenarios"
    assert option(job, "--scenarios") == "bigquery;hive"
    assert option(job, "--scenarios-dir") == str(REPO_ROOT / "producer/spark_dataproc/scenarios")
    assert option(job, "--openlineage-jars-dir") == "/opt/openlineage/1.55.0"
    assert option(job, "--jars") == "gs://open-lineage-e2e/jars/transports-gcs-1.55.0.jar"
    assert option(job, "--events-prefix") == "events/123-1/3.5.1/1.55.0"
    assert option(job, "--max-concurrency") == "3"
    assert "--output-directory" not in job
    assert option(job, "--spark-properties").split(",") == [
        "spark.scenario.suffix=351-1550", "spark.driver.POSTGRESQL_USER=u", "spark.driver.POSTGRESQL_PASSWORD=p"]
    assert ["gcloud", "storage", "cp", "-r", f"{logs}/*", "gs://open-lineage-e2e/logs/123-1/3.5.1/1.55.0/"] in recorded("gcloud")
    assert json.loads((logs / "status.json").read_text())[0]["state"] == "DONE"


def test_run_scenarios_downloads_events_for_local_runs(stubs, tmp_path):
    run, recorded = stubs
    events = tmp_path / "events"
    (events / "bigquery").mkdir(parents=True)
    (events / "bigquery" / "stale.json").write_text("{}")  # from an earlier run into the same directory
    result = run("run_scenarios.sh", *RUN_ARGS, "--logs-dir", str(tmp_path / "logs"), "--events-dir", str(events),
                 "--scenario-suffix", "me-351-1550")
    assert result.returncode == 0, result.stderr

    [job] = recorded("python")
    assert option(job, "--output-directory") == str(events)
    assert option(job, "--spark-properties") == "spark.scenario.suffix=me-351-1550"
    assert not (events / "bigquery" / "stale.json").exists()
    assert json.loads((events / "status.json").read_text()) == [{"scenario": "bigquery", "state": "DONE", "job_id": "j1"}]


def test_run_scenarios_records_runner_failed_when_the_runner_crashes(stubs, tmp_path):
    run, _ = stubs
    logs = tmp_path / "logs"
    (logs).mkdir()
    (logs / "status.json").write_text("[]")  # from an earlier run, must not count as this run's status
    result = run("run_scenarios.sh", *RUN_ARGS, "--logs-dir", str(logs), env={"STUB_RUNNER": "crash"})
    assert result.returncode == 0, result.stderr
    assert json.loads((logs / "status.json").read_text()) == [
        {"scenario": "bigquery", "state": "RUNNER_FAILED", "job_id": ""},
        {"scenario": "hive", "state": "RUNNER_FAILED", "job_id": ""},
    ]


def test_run_scenarios_needs_the_transport_of_the_version(stubs, tmp_path):
    run, recorded = stubs
    args = [a if a != "1.55.0" else "1.99.0" for a in RUN_ARGS]
    result = run("run_scenarios.sh", *args, "--logs-dir", str(tmp_path / "logs"))
    assert result.returncode != 0
    assert "No GCS transport jar for 1.99.0" in result.stderr
    assert recorded("python") == []
