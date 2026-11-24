# dev/: helpers for running producers

The scripts here are shared by the CI workflows and by local runs, so a producer runs the same way in both. The
report/release pipeline (comparing reports, issues, the site) lives in `scripts/`.

| Path | What it does |
|---|---|
| `defaults.env` | GCP project, region and bucket used by default (CI and local) |
| `dataproc/dataproc_workflow.py` | Python CLI for Dataproc: `create-cluster`, `terminate-cluster`, `run-job`, `run-scenarios` (Spark), `run-hive-query` (Hive) |
| `dataproc/create_cluster.sh` | creates a cluster; the producer's `runner/create_cluster.sh` passes the image, metadata and init actions |
| `dataproc/delete_cluster.sh` | deletes a cluster; `--list-mine` lists clusters with your user name in it (leftovers of local runs) |
| `dataproc/gcs_upload.sh` | uploads a file to GCS unless it's already there, prints the `gs://` URL |
| `dataproc/install_jars.sh` | the Dataproc init action of every Dataproc producer: copies the jars listed in the cluster metadata, nothing else |
| `lib/status.sh` | writes `status.json`, how each scenario's producer job ended (validation fails scenarios not in `DONE`) |
| `validation/get_ol_specs.sh` | copies the OpenLineage spec of given releases (also used by the CI validation action) |
| `validation/validate_locally.sh` | validates one run's events like CI does and prints a status per scenario |

Every script prints its options with `--help`.

## Prerequisites for running producers locally

- Python 3.11+, `jq`, `git`.
- Dataproc producers (`spark_dataproc`, `hive_dataproc`): the [gcloud CLI](https://cloud.google.com/sdk/docs/install) and
  access to the test project (`gcp-open-lineage-testing`), or your own project and bucket passed with `--project` and
  `--bucket`. Log in once with `gcloud auth login` and `gcloud auth application-default login`; no key file is needed
  (a service account key can still be passed with `--credentials-file`).
- dbt: Docker (for the Postgres the scenarios write to).

How to run a producer's scenarios is described in that producer's README.
