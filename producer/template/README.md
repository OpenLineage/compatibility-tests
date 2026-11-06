# Template producer

Copy this directory to `producer/<producer>/` to add a producer, and replace this README with the producer's own. Keep
the sections below: contributors use them to test scenarios before committing. `producer/dbt/README.md` is a complete example.

## Scenarios

What each scenario in `scenarios/` does and which versions it applies to (`config.json`).

## Run locally, as CI does

The steps and scripts are the same as in the producer's CI workflow (`.github/workflows/producer_<producer>.yml`); say what
differs locally, if anything.

**Prerequisites:** what to install and what access is needed (see [`dev/README.md`](../../dev/README.md) for the common
ones, e.g. gcloud login for Dataproc producers).

**Pick the versions** from `versions.json`.

### One command

```bash
producer/<producer>/run_<producer>_tests.sh --component-version <V> --openlineage-version <OL>
```

Its options (`--help`), and what the first run sets up and caches.

### The same steps by hand

One command per CI step, with the step's name, so a contributor can stop after any of them or re-run one:

```bash
V=<V> OL=<OL> EVENTS=$PWD/<producer>-events-$V-$OL

# "Initialize tests"
SCENARIOS=$(scripts/get_valid_test_scenarios.sh producer/<producer>/scenarios $V $OL)

# the setup steps, e.g. installing packages or creating a cluster

# "Run scenarios"
producer/<producer>/runner/run_scenarios.sh --events-dir "$EVENTS" --scenarios "$SCENARIOS"

# "Validation"
dev/validation/validate_locally.sh --component <producer> --component-version $V --openlineage-version $OL --events-dir "$EVENTS"
```

### What you get

Where the events, `status.json` and the report land, how to read a failed test, and how to clean up (containers,
clusters: `dev/dataproc/delete_cluster.sh --list-mine`).
