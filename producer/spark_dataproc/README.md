# Spark Dataproc

Checks the OpenLineage Spark integration (`openlineage-spark`) by running each scenario's `test/test.py` as a PySpark job
on a Dataproc cluster and validating the events it writes to GCS (the `transports-gcs` transport).

```
producer/spark_dataproc/
├── scenarios/<scenario>/              config.json, events/ (expected events), test/test.py, scenario.md
├── runner/cluster.json                per Spark release: Dataproc image, BigQuery connector, extra jars; jars and
│                                      metadata every cluster gets
├── runner/stage_openlineage_jars.sh   puts the OpenLineage spark and GCS transport jars in gs://<bucket>/jars
├── runner/create_cluster.sh           creates a cluster for one Spark release and any number of OpenLineage versions
├── runner/run_scenarios.sh            runs the scenarios for one OpenLineage version, writes status.json and driver logs
├── runner/cloud_sql_proxy.sh          init action: Cloud SQL proxy for the cloudsql scenario
├── run_spark_dataproc_tests.sh        runs everything locally, as CI does
├── versions.json                      tested Spark and OpenLineage versions
└── dataproc_images.json               Dataproc image family per Spark release (the release check watches it for new images)
```

CI (`.github/workflows/producer_spark_dataproc.yml`) creates one cluster per Spark release and runs every OpenLineage
version on it, one after another. Each version's spark jar is in `/opt/openlineage/<version>/` on the master, and a job
picks one with `spark.driver.extraClassPath`. The GCS transport is passed with `--jars`, not installed on the cluster:
since 1.40.0 it bundles its own Woodstox, which breaks Hadoop's configuration parsing on the system classpath. A
separate `validate` job per Spark × OpenLineage pair downloads the events and validates them. The local run uses the
same `runner/` scripts for a single pair.

## Run locally, as CI does

Use this to test a new or changed scenario before you commit it, or a local build of `openlineage-spark`. The cluster,
the jobs and the validation are the same as in CI. Only these differ: the cluster name (yours, with a timestamp), the
GCS directory of the events, the table suffix (so your tables don't clash with CI's), and the credentials.

**Prerequisites:** see [`dev/README.md`](../../dev/README.md#prerequisites-for-running-producers-locally): Python 3.11+,
`jq`, `git`, `curl`, the gcloud CLI logged in (`gcloud auth login` and `gcloud auth application-default login`) with
access to `gcp-open-lineage-testing`. The scenarios use BigQuery, Bigtable, Spanner and Cloud SQL resources of that
project; in another project (`--project`, `--region`, `--bucket`) most of them fail. The `cloudsql` scenario also needs
`POSTGRESQL_USER` and `POSTGRESQL_PASSWORD` in the environment (the `postgresqlUser` / `postgresqlPassword` secrets
CI uses); without them only that scenario fails.

**Pick the versions** from `versions.json` (Spark: a key of `releases` in `runner/cluster.json`; OpenLineage: the
latest release, or the one you're testing). Scenarios only run for the versions in their `config.json`.

**Cost and time:** a cluster (an `n1-standard-4` master and 2 `n1-standard-2` workers) is created for the run and deleted at the end, also
when a step fails or you press Ctrl-C. In CI, creating it takes 6–9 minutes, the scenarios of one OpenLineage version
1–6 minutes (3.5.1 runs the most) and deleting the cluster 1–2 minutes.

### One command

From the repository root:

```bash
producer/spark_dataproc/run_spark_dataproc_tests.sh --component-version 3.5.1 --openlineage-version 1.55.0
```

Options (`--help` lists everything):
- `--scenarios 'bigquery;hive'` runs only the given scenarios.
- `--spark-jar path/to/openlineage-spark_2.12-<version>.jar` tests your own build (e.g.
  `integration/spark/app/build/libs/openlineage-spark_2.12-*-SNAPSHOT.jar` after `./gradlew :app:shadowJar`) instead
  of the release; the GCS transport is still the `--openlineage-version` release.
- `--keep-cluster` keeps the cluster for more runs; `--cluster-name <name>` then runs on it without creating or deleting
  one (it must have been created with the same OpenLineage version). Delete it when you're done:
  `dev/dataproc/delete_cluster.sh --cluster-name <name>`. `dev/dataproc/delete_cluster.sh --list-mine` lists clusters
  left behind under your name.
- `--events-dir`, `--logs-dir` and `--report-dir` move the output.

### The same steps by hand

One command per CI step, so you can stop after any of them, look at the output, or re-run just one:

```bash
V=3.5.1 OL=1.55.0 U=$(echo "$USER" | tr "[:upper:]" "[:lower:]")
CLUSTER=dataproc-producer-test-$U-manual RUN_KEY=local-$U-$(date +%s)

# "initialize tests": the scenarios valid for the versions
SCENARIOS=$(scripts/get_valid_test_scenarios.sh producer/spark_dataproc/scenarios $V $OL); echo "$SCENARIOS"

# "Install dependencies" (any virtualenv outside the repo; the scripts call `python`)
python3 -m venv ~/.venvs/dataproc && source ~/.venvs/dataproc/bin/activate
pip install -r dev/dataproc/requirements.txt

# "Stage OL jars in GCS"
JARS=$(producer/spark_dataproc/runner/stage_openlineage_jars.sh $OL); echo "$JARS"

# "Start producer"
producer/spark_dataproc/runner/create_cluster.sh --spark-release $V --cluster-name $CLUSTER --openlineage-jars "$JARS"

# "Run producer jobs and create OL events" (CI downloads the events in the validate job instead of --events-dir)
producer/spark_dataproc/runner/run_scenarios.sh --cluster-name $CLUSTER --spark-release $V --ol-release $OL \
  --scenarios "$SCENARIOS" --openlineage-jars "$JARS" --run-key $RUN_KEY --scenario-suffix $U-manual \
  --logs-dir spark-dataproc-logs-$V-$OL --events-dir spark-dataproc-events-$V-$OL

# "Validation"
dev/validation/validate_locally.sh --component spark_dataproc --component-version $V --openlineage-version $OL \
  --events-dir spark-dataproc-events-$V-$OL

# the cluster action's cleanup
dev/dataproc/delete_cluster.sh --cluster-name $CLUSTER
```

### What you get

- `spark-dataproc-events-<V>-<OL>/<scenario>/*.json`: the events (also kept in GCS under
  `gs://<bucket>/events/<run key>/<V>/<OL>/<scenario>/`).
- `spark-dataproc-events-<V>-<OL>/status.json`: how each scenario's job ended (`DONE`, `ERROR`, …, with the Dataproc
  job id). A scenario not in `DONE` fails validation with a "producer job" test.
- `spark-dataproc-logs-<V>-<OL>/<scenario>.log`: each job's driver output, the first place to look when a scenario
  fails.
- `spark-dataproc-<V>-<OL>-report.json`: the report, with the same name and format as the CI artifact. The script prints
  a line per scenario with its status and the tests that didn't pass, and exits 1 if a scenario failed. A test that
  doesn't match its expected event lists the differences in its `details`:

  ```bash
  jq '.[].scenarios[] | {name, status, failed: [.tests[] | select(.status == "FAILURE") | {name, details}]}' spark-dataproc-3.5.1-1.55.0-report.json
  ```

All three are git-ignored when they're in the repository root.
