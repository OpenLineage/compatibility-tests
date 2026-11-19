"""The Hive runner scripts (producer/hive_dataproc/runner/) with stub `python` and `gcloud`, and run-hive-query's exit code."""
import asyncio
import importlib.util
import json
import os
import re
import subprocess
from types import SimpleNamespace

import pytest

from conftest import REPO_ROOT

RUNNER = REPO_ROOT / "producer" / "hive_dataproc" / "runner"
SNAPSHOT_TRANSPORT = "gs://open-lineage-e2e/jars/transports-gcs-1.56.0-SNAPSHOT-conscrypt-fix.jar"


@pytest.fixture
def stubs(tmp_path):
    """Stub `python` (dataproc_workflow.py) and `gcloud` on PATH; returns (run, calls) helpers."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.jsonl"
    record = f"""python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "$(basename "$0")" "$@" >> {calls}"""
    # python: a query containing "-- fail" ends in ERROR, one containing "-- nosubmit" fails before submitting
    (bin_dir / "python").write_text(f"""#!/bin/bash
{record}
case "$*" in
  *"-- nosubmit"*) echo "permission denied" >&2; exit 1 ;;
  *"-- fail"*) echo "Submitted Hive job with job_id: job-fail"; echo "Hive job job-fail ended in state ERROR"; exit 1 ;;
  *run-hive-query*) echo "Submitted Hive job with job_id: job-ok"; echo "Hive job job-ok ended in state DONE" ;;
esac
exit 0
""")
    # gcloud: nothing exists in GCS yet, copies succeed
    (bin_dir / "gcloud").write_text(f"""#!/bin/bash
{record}
[[ "$1 $2" == "storage ls" ]] && exit 1
exit 0
""")
    for stub in bin_dir.iterdir():
        stub.chmod(0o755)

    def run(script, *args, env=None):
        full_env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", **(env or {})}
        full_env.pop("GITHUB_ACTIONS", None)
        return subprocess.run(["bash", str(RUNNER / script), *args], env=full_env, capture_output=True, text=True)

    def recorded():
        return [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []

    return run, recorded


def option(argv, name):
    return argv[argv.index(name) + 1]


def test_create_cluster_uses_cluster_json_and_a_per_cluster_init_action(stubs):
    run, recorded = stubs
    result = run("create_cluster.sh", "--hive-release", "3.1.3", "--cluster-name", "c1", "--hive-jar", "gs://b/hive.jar")
    assert result.returncode == 0, result.stderr

    copies = [c for c in recorded() if c[:3] == ["gcloud", "storage", "cp"]]
    assert copies == [["gcloud", "storage", "cp", str(REPO_ROOT / "dev/dataproc/install_jars.sh"),
                       "gs://open-lineage-e2e/scripts/c1/install_jars.sh"]]
    [create] = [c for c in recorded() if c[0] == "python"]
    assert create[2] == "create-cluster"
    assert option(create, "--cluster-name") == "c1"
    assert option(create, "--dataproc-image-version") == "2.1-debian11"
    assert option(create, "--metadata") == f"JARS=gs://b/hive.jar;{SNAPSHOT_TRANSPORT}"
    assert option(create, "--initialization-actions") == "gs://open-lineage-e2e/scripts/c1/install_jars.sh"
    assert option(create, "--cluster-properties").split(",") == [
        "hive:hive.exec.post.hooks=io.openlineage.hive.hooks.HiveOpenLineageHook",
        "hive:hive.conf.validation=false",
        "hive:hive.server2.logging.operation.level=VERBOSE",
        "hive:hive.root.logger=DEBUG",
        "hive:hive.log.explain.output=true",
    ]
    assert (option(create, "--project-id"), option(create, "--region")) == ("gcp-open-lineage-testing", "us-west1")


def test_create_cluster_takes_another_transport_and_project(stubs):
    run, recorded = stubs
    result = run("create_cluster.sh", "--hive-release", "3.1.3", "--cluster-name", "c1", "--hive-jar", "gs://b/hive.jar",
                 "--gcs-transport-jar", "gs://b/gcs.jar", "--project", "p", "--region", "r", "--bucket", "mine",
                 "--credentials-file", "k.json")
    assert result.returncode == 0, result.stderr
    [create] = [c for c in recorded() if c[0] == "python"]
    assert option(create, "--metadata") == "JARS=gs://b/hive.jar;gs://b/gcs.jar"
    assert option(create, "--initialization-actions") == "gs://mine/scripts/c1/install_jars.sh"
    assert (option(create, "--project-id"), option(create, "--region")) == ("p", "r")
    assert option(create, "--credentials-file") == "k.json"


def test_create_cluster_rejects_an_unknown_hive_release(stubs):
    run, recorded = stubs
    result = run("create_cluster.sh", "--hive-release", "9.9.9", "--cluster-name", "c1", "--hive-jar", "gs://b/hive.jar")
    assert result.returncode != 0
    assert "9.9.9" in result.stderr
    assert recorded() == []


@pytest.fixture
def scenarios_dir(tmp_path):
    root = tmp_path / "scenarios"
    for name, query in [("ok", "SELECT 1; -- ok"), ("broken", "SELECT 1; -- fail"), ("denied", "SELECT 1; -- nosubmit")]:
        (root / name / "test").mkdir(parents=True)
        (root / name / "test" / "test.sql").write_text(query)
    (root / "no_query" / "test").mkdir(parents=True)
    return root


def test_run_scenarios_records_each_job_and_continues_past_failures(stubs, scenarios_dir, tmp_path):
    run, recorded = stubs
    events = tmp_path / "events"
    (events / "ok").mkdir(parents=True)
    (events / "ok" / "stale.json").write_text("{}")  # from an earlier run into the same directory

    result = run("run_scenarios.sh", "--cluster-name", "c1", "--events-dir", str(events),
                 "--scenarios", "ok;broken;denied;no_query", env={"HIVE_SCENARIOS_DIR": str(scenarios_dir)})

    assert result.returncode == 0, result.stderr
    assert json.loads((events / "status.json").read_text()) == [
        {"scenario": "ok", "state": "DONE", "job_id": "job-ok"},
        {"scenario": "broken", "state": "ERROR", "job_id": "job-fail"},
        {"scenario": "denied", "state": "FAILED", "job_id": ""},
        {"scenario": "no_query", "state": "FAILED", "job_id": ""},
    ]
    assert not (events / "ok" / "stale.json").exists()
    assert sorted(p.name for p in events.iterdir()) == ["broken", "denied", "no_query", "ok", "status.json"]

    jobs = [c for c in recorded() if c[0] == "python"]
    assert [option(j, "--query") for j in jobs] == ["SELECT 1; -- ok", "SELECT 1; -- fail", "SELECT 1; -- nosubmit"]
    ok = jobs[0]
    assert option(ok, "--cluster-name") == "c1"
    assert option(ok, "--output-directory") == str(events / "ok")
    props = option(ok, "--properties").split(",")
    assert props[:2] == ["hive.openlineage.transport.type=gcs", "hive.openlineage.transport.bucketName=open-lineage-e2e"]
    assert re.fullmatch(r"hive\.openlineage\.transport\.fileNamePrefix=events/ok/\d{13}/", props[2])


def load_workflow():
    spec = importlib.util.spec_from_file_location("dataproc_workflow", REPO_ROOT / "dev" / "dataproc" / "dataproc_workflow.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("state, fails", [("DONE", False), ("ERROR", True), ("CANCELLED", True), ("RUNNING", True)])
def test_run_hive_query_exits_non_zero_unless_the_job_is_done(monkeypatch, capsys, state, fails):
    module = load_workflow()

    class Client:
        def __init__(self, **kwargs):
            pass

        async def submit_job_as_operation(self, request):
            class Operation:
                async def result(self):
                    return SimpleNamespace(reference=SimpleNamespace(job_id="job-1"))
            return Operation()

    async def wait(**kwargs):
        return {"job_id": "job-1", "state": state}

    monkeypatch.setattr(module, "get_gcp_credentials", lambda credentials_file=None: None)
    monkeypatch.setattr(module, "JobControllerAsyncClient", Client)
    monkeypatch.setattr(module, "wait_for_dataproc_job", wait)
    args = SimpleNamespace(credentials_file=None, region="r", project_id="p", cluster_name="c", query="SELECT 1",
                           properties="", output_directory="")

    if fails:
        with pytest.raises(SystemExit):
            asyncio.run(module.run_hive_query_command(args))
    else:
        asyncio.run(module.run_hive_query_command(args))
    assert f"Hive job job-1 ended in state {state}" in capsys.readouterr().out
