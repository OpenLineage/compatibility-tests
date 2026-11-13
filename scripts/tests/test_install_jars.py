"""Runs the shared Dataproc init action (dev/dataproc/install_jars.sh) with stub metadata and gsutil."""
import json
import os
import subprocess

import pytest

from conftest import REPO_ROOT

SCRIPT = REPO_ROOT / "dev" / "dataproc" / "install_jars.sh"


@pytest.fixture
def node(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "gsutil-calls.jsonl"
    # gsutil stub: records its arguments and "copies" by creating the target file
    (bin_dir / "gsutil").write_text(f"""#!/bin/bash
python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "$@" >> {calls}
[[ "$*" == *fail* ]] && exit 1
target="${{@: -1}}"; touch "$target/$(basename "${{@: -2:1}}")"
""")
    (bin_dir / "gsutil").chmod(0o755)

    def run(metadata, dataproc_lib_dir_exists=True):
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(metadata))
        stub = tmp_path / "get_metadata_value"
        stub.write_text(f"""#!/bin/bash
python3 -c 'import json,sys; m=json.load(open("{meta_file}")); k=sys.argv[1].split("/",1)[1]; print(m[k]) if k in m else sys.exit(1)' "$1"
""")
        stub.chmod(0o755)
        dataproc_lib = tmp_path / "dataproc-lib"
        hadoop_lib = tmp_path / "hadoop-lib"
        hadoop_lib.mkdir(exist_ok=True)
        if dataproc_lib_dir_exists:
            dataproc_lib.mkdir(exist_ok=True)
        env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "GET_METADATA": str(stub),
               "DATAPROC_LIB_DIR": str(dataproc_lib), "HADOOP_LIB_DIR": str(hadoop_lib)}
        result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
        copied = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
        return result, copied, dataproc_lib, hadoop_lib

    return run


def test_jars_go_to_the_target_dir_on_every_node(node, tmp_path):
    target = tmp_path / "spark-jars"
    target.mkdir()
    result, copied, _, _ = node({"JARS": "gs://b/a.jar;gs://b/b.jar", "JARS_TARGET_DIR": str(target), "dataproc-role": "Worker"})
    assert result.returncode == 0, result.stderr
    assert copied == [["cp", "gs://b/a.jar", f"{target}/"], ["cp", "gs://b/b.jar", f"{target}/"]]


def test_master_jars_only_on_the_master(node, tmp_path):
    ol_dir = tmp_path / "opt" / "openlineage" / "1.55.0"
    metadata = {"MASTER_JARS": f"{ol_dir}=gs://b/openlineage-spark-1.55.0.jar"}

    _, on_worker, _, _ = node({**metadata, "dataproc-role": "Worker"})
    assert on_worker == []

    result, on_master, _, _ = node({**metadata, "dataproc-role": "Master"})
    assert result.returncode == 0, result.stderr
    assert on_master == [["cp", "gs://b/openlineage-spark-1.55.0.jar", f"{ol_dir}/"]]
    assert (ol_dir / "openlineage-spark-1.55.0.jar").exists()


def test_default_target_is_the_dataproc_lib_dir(node):
    _, copied, dataproc_lib, _ = node({"JARS": "gs://b/hive.jar", "dataproc-role": "Master"})
    assert copied == [["cp", "gs://b/hive.jar", f"{dataproc_lib}/"]]


def test_default_target_falls_back_to_hadoop_lib(node):
    _, copied, _, hadoop_lib = node({"JARS": "gs://b/hive.jar", "dataproc-role": "Master"}, dataproc_lib_dir_exists=False)
    assert copied == [["cp", "gs://b/hive.jar", f"{hadoop_lib}/"]]


def test_failed_copy_fails_the_init_action(node):
    result, _, _, _ = node({"JARS": "gs://b/fail.jar", "dataproc-role": "Worker"})
    assert result.returncode != 0


def test_no_jars_listed_copies_nothing(node):
    result, copied, _, _ = node({"dataproc-role": "Master"})
    assert result.returncode == 0
    assert copied == []


def test_jars_get_the_same_mtime_on_every_node(node, tmp_path):
    # Tez refuses a localized jar whose mtime differs between nodes, so it mustn't depend on the copy time
    target = tmp_path / "lib"
    target.mkdir()
    result, _, _, _ = node({"JARS": "gs://b/a.jar", "JARS_TARGET_DIR": str(target), "dataproc-role": "Worker"})
    assert result.returncode == 0, result.stderr
    assert (target / "a.jar").stat().st_mtime == 946684800  # 2000-01-01 00:00 UTC
