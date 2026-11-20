# Hive Dataproc

Checks the OpenLineage Hive integration (`openlineage-hive`, a Hive post-execution hook) by running each scenario's
`test/*.sql` as a Hive job on a Dataproc cluster and validating the events the hook writes to GCS.

```
producer/hive_dataproc/
├── scenarios/<scenario>/          config.json, events/ (expected events), test/<query>.sql, scenario.md
├── runner/cluster.json            per Hive release: Dataproc image and Hive properties
├── runner/create_cluster.sh       creates the cluster with the hook and the GCS transport installed
├── runner/run_scenarios.sh        runs the scenarios on a cluster, downloads the events, writes status.json
├── run_hive_dataproc_tests.sh     runs everything locally, as CI does
├── versions.json                  tested Hive and OpenLineage versions
└── dataproc_images.json           Dataproc image family per Hive release (the release check watches it for new images)
```

CI (`.github/workflows/producer_hive_dataproc.yml`) runs on pull requests that touch Hive and in the scheduled release
check. It calls the same `runner/` scripts as the local run.

**GCS transport:** released `transports-gcs` 1.40.0–1.55.0 break Hive on Dataproc, so for now the cluster gets a fixed
snapshot (`runner/create_cluster.sh`, `DEFAULT_GCS_TRANSPORT_JAR`) instead of the transport of the OpenLineage release
being tested.

## Run locally, as CI does

Use this to test a new or changed scenario before you commit it. The cluster, the jobs and the validation are the same
as in CI; only the cluster name (yours, with a timestamp) and the credentials differ.

**Prerequisites:** see [`dev/README.md`](../../dev/README.md#prerequisites-for-running-producers-locally): Python 3.11+,
`jq`, `git`, `curl`, the gcloud CLI logged in (`gcloud auth login` and `gcloud auth application-default login`) with
access to `gcp-open-lineage-testing`, or your own project and bucket (`--project`, `--region`, `--bucket`).

**Pick the versions** from `versions.json` (Hive: a key of `runner/cluster.json`; OpenLineage: the latest release, or
the one you're testing). Scenarios only run for the versions in their `config.json`.

**Cost and time:** a cluster (1 master, 2 workers) is created for the run and deleted at the end, also when a step
fails or you press Ctrl-C. In CI, creating it takes about 5 minutes, the `aggregate_job` scenario about 2 minutes and
deleting the cluster about 1 minute.

### One command

From the repository root:

```bash
producer/hive_dataproc/run_hive_dataproc_tests.sh --component-version 3.1.3 --openlineage-version 1.55.0
```

Options (`--help` lists everything):
- `--scenarios 'aggregate_job'` runs only the given scenarios.
- `--hive-jar path/to/openlineage-hive.jar` tests your own build of the integration instead of the release.
- `--keep-cluster` keeps the cluster for more runs; `--cluster-name <name>` then runs on it without creating or deleting
  one. Delete it when you're done: `dev/dataproc/delete_cluster.sh --cluster-name <name>`. `dev/dataproc/delete_cluster.sh
  --list-mine` lists clusters left behind under your name.
- `--events-dir` and `--report-dir` move the output.

### The same steps by hand

One command per CI step, so you can stop after any of them, look at the output, or re-run just one:

```bash
V=3.1.3 OL=1.55.0 EVENTS=$PWD/hive-dataproc-events-$V-$OL CLUSTER=hive-$USER-test

# "initialize tests": the scenarios valid for the versions
SCENARIOS=$(scripts/get_valid_test_scenarios.sh producer/hive_dataproc/scenarios $V $OL); echo "$SCENARIOS"

# "Install dependencies" (any virtualenv outside the repo; the scripts call `python`)
python3 -m venv ~/.venvs/dataproc && source ~/.venvs/dataproc/bin/activate
pip install -r dev/dataproc/requirements.txt

# "Get OL artifacts" and "Upload openlineage hive integration to GCS"
curl -fsSLO https://repo1.maven.org/maven2/io/openlineage/openlineage-hive/$OL/openlineage-hive-$OL.jar
HIVE_JAR=$(dev/dataproc/gcs_upload.sh openlineage-hive-$OL.jar gs://open-lineage-e2e/jars)

# "Start producer"
producer/hive_dataproc/runner/create_cluster.sh --hive-release $V --cluster-name $CLUSTER --hive-jar "$HIVE_JAR"

# "Run producer jobs and create OL events"
producer/hive_dataproc/runner/run_scenarios.sh --cluster-name $CLUSTER --scenarios "$SCENARIOS" --events-dir "$EVENTS"

# "Validation"
dev/validation/validate_locally.sh --component hive_dataproc --component-version $V --openlineage-version $OL --events-dir "$EVENTS"

# the cluster action's cleanup
dev/dataproc/delete_cluster.sh --cluster-name $CLUSTER
```

### What you get

- `hive-dataproc-events-<V>-<OL>/<scenario>/*.json`: the events the hook wrote (also kept in GCS under
  `gs://<bucket>/events/<scenario>/<timestamp>/`).
- `hive-dataproc-events-<V>-<OL>/status.json`: how each scenario's Hive job ended (`DONE`, or e.g. `ERROR` with the
  Dataproc job id). A scenario not in `DONE` fails validation with a "producer job" test. To see why, open the job in
  the Cloud Console (Dataproc → Jobs) or run `gcloud dataproc jobs describe <job id> --region us-west1`.
- `hive-dataproc-<V>-<OL>-report.json`: the report, with the same name and format as the CI artifact. The script prints
  a line per scenario with its status and the tests that didn't pass, and exits 1 if a scenario failed. A test that
  doesn't match its expected event lists the differences in its `details`:

  ```bash
  jq '.[].scenarios[] | {name, status, failed: [.tests[] | select(.status == "FAILURE") | {name, details}]}' hive-dataproc-3.1.3-1.55.0-report.json
  ```

Both outputs are git-ignored when they're in the repository root.
