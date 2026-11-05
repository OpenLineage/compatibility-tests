"""The merged dev/dataproc/dataproc_workflow.py keeps every subcommand and option the Spark and Hive copies had."""
import importlib.util
import subprocess
import sys

import pytest

from conftest import REPO_ROOT

SCRIPT = REPO_ROOT / "dev" / "dataproc" / "dataproc_workflow.py"


def parse(argv, monkeypatch):
    spec = importlib.util.spec_from_file_location("dataproc_workflow", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parsed = {}
    monkeypatch.setattr(module.asyncio, "run", lambda coro: (parsed.setdefault("coro", coro), coro.close()))
    monkeypatch.setattr(sys, "argv", ["dataproc_workflow.py", *argv])
    module.main()
    return parsed["coro"].__name__


@pytest.mark.parametrize("command", ["create-cluster", "run-job", "run-scenarios", "terminate-cluster", "run-hive-query"])
def test_subcommand_help(command):
    result = subprocess.run([sys.executable, str(SCRIPT), command, "--help"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# the invocations of the Spark and Hive workflows
@pytest.mark.parametrize("argv, handler", [
    (["create-cluster", "--project-id", "p", "--region", "r", "--dataproc-image-version", "2.2-ubuntu22", "--cluster-name", "c",
      "--credentials-file", "k.json", "--metadata", "A=1,B=2", "--master-machine-type", "n1-standard-4",
      "--initialization-actions", "gs://b/x.sh,gs://b/y.sh"], "create_cluster_command"),
    (["run-scenarios", "--project-id", "p", "--region", "r", "--cluster-name", "c", "--gcs-bucket", "b",
      "--scenarios-dir", "producer/spark_dataproc/scenarios", "--scenarios", "bigquery;hive", "--openlineage-jars-dir",
      "/opt/openlineage/1.55.0", "--jars", "gs://b/t.jar", "--events-prefix", "events/x", "--spark-properties", "a=b",
      "--max-concurrency", "3", "--logs-directory", "/tmp/logs", "--credentials-file", "k.json"], "run_scenarios_command"),
    (["create-cluster", "--project-id", "p", "--region", "r", "--cluster-name", "c", "--dataproc-image-version", "2.1-debian11",
      "--cluster-properties", "hive:hive.conf.validation=false", "--metadata", "A=1", "--initialization-actions", "gs://b/i.sh",
      "--credentials-file", "k.json"], "create_cluster_command"),
    (["run-hive-query", "--project-id", "p", "--region", "r", "--cluster-name", "c", "--query", "SELECT 1",
      "--credentials-file", "k.json", "--output-directory", "/tmp/e", "--properties", "a=b"], "run_hive_query_command"),
    (["terminate-cluster", "--project-id", "p", "--region", "r", "--cluster-name", "c"], "terminate_cluster_command"),
])
def test_ci_invocations_parse(argv, handler, monkeypatch):
    assert parse(argv, monkeypatch) == handler
