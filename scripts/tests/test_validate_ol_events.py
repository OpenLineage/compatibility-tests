"""End-to-end tests of scripts/validate_ol_events.py through its command line, on small generated fixtures."""
import json
import subprocess
import sys

import pytest

from conftest import REPO_ROOT, SCRIPTS_DIR

COMPONENT = "fake_producer"
CV = "1.0.0"
OL = "1.40.0"


def write_json(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content))


def run_event(job_name="job", event_type="COMPLETE", run_facets=None):
    return {
        "eventType": event_type,
        "eventTime": "2026-01-01T00:00:00Z",
        "producer": "https://example.com/producer",
        "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent",
        "run": {"runId": "0190a4b2-0000-7000-8000-000000000000", "facets": run_facets or {}},
        "job": {"namespace": "ns", "name": job_name, "facets": {}},
        "inputs": [],
        "outputs": [],
    }


@pytest.fixture
def env(tmp_path):
    """A spec dir, a producer dir and an event dir; returns a helper namespace."""
    specs = tmp_path / "specs" / OL
    write_json(specs / "OpenLineage.json", {"$id": "https://openlineage.io/spec/2-0-2/OpenLineage.json", "type": "object",
                                             "required": ["eventType", "job"]})
    # a facet schema whose $ref points nowhere: jsonschema raises while validating, like a broken schema in a release
    write_json(specs / "BoomRunFacet.json", {"$id": "https://openlineage.io/spec/facets/1-0-0/BoomRunFacet.json",
                                              "properties": {"boom": {"$ref": "#/$defs/missing"}}})

    class Env:
        root = tmp_path
        producer = tmp_path / "producer"
        events = tmp_path / "events"

        @staticmethod
        def scenario(name, tests=None, component_versions=None, openlineage_versions=None, expected=None):
            config = {"tests": tests or []}
            if component_versions:
                config["component_versions"] = component_versions
            if openlineage_versions:
                config["openlineage_versions"] = openlineage_versions
            base = tmp_path / "producer" / COMPONENT / "scenarios" / name
            write_json(base / "config.json", config)
            for file_name, body in (expected or {}).items():
                write_json(base / "events" / file_name, body)

        @staticmethod
        def emitted(scenario, file_name, body):
            target = tmp_path / "events" / scenario / file_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body if isinstance(body, str) else json.dumps(body))

        @staticmethod
        def validate(*extra, ol=OL):
            Env.events.mkdir(exist_ok=True)
            target = tmp_path / "report.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "validate_ol_events.py"),
                 f"--event_base_dir={Env.events}", f"--spec_base_dir={tmp_path / 'specs'}",
                 f"--producer_dir={Env.producer}", f"--component={COMPONENT}", f"--component_version={CV}",
                 f"--openlineage_version={ol}", f"--target={target}", *extra],
                cwd=REPO_ROOT, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
            [component] = json.loads(target.read_text())
            return {s["name"]: s for s in component["scenarios"]}

    return Env


def by_name(scenario):
    return {t["name"]: t for t in scenario["tests"]}


def semantic_test(name, job_name="job"):
    return {"name": name, "path": f"events/{name}.json", "tags": {}}


def test_validator_error_fails_that_scenario_and_keeps_the_others(env):
    env.scenario("broken")
    env.scenario("fine")
    env.emitted("broken", "e.json", run_event(run_facets={"boom": {"_producer": "x", "_schemaURL": "y"}}))
    env.emitted("fine", "e.json", run_event())

    scenarios = env.validate()

    assert scenarios["broken"]["status"] == "FAILURE"
    [syntax] = [t for t in scenarios["broken"]["tests"] if t["validation_type"] == "syntax"]
    assert syntax["status"] == "FAILURE"
    assert any("validator error" in d and "boom" in d for d in syntax["details"])
    assert scenarios["fine"]["status"] == "SUCCESS"


def test_scenario_valid_for_the_version_without_events_fails(env):
    env.scenario("silent")

    scenarios = env.validate()

    events = by_name(scenarios["silent"])["events"]
    assert scenarios["silent"]["status"] == "FAILURE"
    assert events["status"] == "FAILURE"
    assert events["details"] == ["scenario produced no events"]


def test_empty_event_directory_fails(env):
    env.scenario("empty")
    (env.events / "empty").mkdir(parents=True)

    scenarios = env.validate()

    assert by_name(scenarios["empty"])["events"]["status"] == "FAILURE"


def test_scenario_gated_out_without_events_is_not_reported(env):
    env.scenario("future", openlineage_versions={"min": "9.0.0"})
    env.scenario("now")
    env.emitted("now", "e.json", run_event())

    scenarios = env.validate()

    assert "future" not in scenarios
    assert "now" in scenarios


def test_syntax_failure_adds_a_note_instead_of_skipping_semantics_silently(env):
    expected = run_event()
    env.scenario("bad_syntax", tests=[semantic_test("run_test")], expected={"run_test.json": expected})
    bad = run_event()
    del bad["eventType"]
    env.emitted("bad_syntax", "e.json", bad)

    scenarios = env.validate()

    semantics = by_name(scenarios["bad_syntax"])["semantics"]
    assert semantics["status"] == "SKIPPED"
    assert semantics["details"] == ["semantic checks skipped because syntax validation failed"]
    assert scenarios["bad_syntax"]["status"] == "FAILURE"


def test_no_semantic_test_for_the_version_is_a_warning(env):
    gated = dict(semantic_test("run_test"), openlineage_versions={"min": "9.0.0"})
    env.scenario("gated_tests", tests=[gated], expected={"run_test.json": run_event()})
    env.emitted("gated_tests", "e.json", run_event())

    scenarios = env.validate()

    semantics = by_name(scenarios["gated_tests"])["semantics"]
    assert semantics["status"] == "WARNING"
    assert semantics["details"] == [f"no semantic tests apply to {COMPONENT} {CV} / OpenLineage {OL}"]
    assert scenarios["gated_tests"]["status"] == "SUCCESS"


def test_semantic_tests_still_run(env):
    env.scenario("ok", tests=[semantic_test("run_test")], expected={"run_test.json": run_event()})
    env.emitted("ok", "e.json", run_event())

    scenarios = env.validate()

    assert by_name(scenarios["ok"])["run_test"]["status"] == "SUCCESS"
    assert "semantics" not in by_name(scenarios["ok"])


def test_run_status_marks_unfinished_producer_jobs(env, tmp_path):
    env.scenario("crashed")
    env.scenario("done")
    env.emitted("crashed", "e.json", run_event())
    env.emitted("done", "e.json", run_event())
    status = tmp_path / "status.json"
    write_json(status, [{"scenario": "crashed", "state": "ERROR", "job_id": "job-123"},
                        {"scenario": "done", "state": "DONE", "job_id": "job-456"}])

    scenarios = env.validate(f"--run_status={status}")

    job = by_name(scenarios["crashed"])["producer job"]
    assert job["status"] == "FAILURE"
    assert job["details"] == ["producer job ended in state ERROR, job 'job-123'"]
    assert scenarios["crashed"]["status"] == "FAILURE"
    assert "producer job" not in by_name(scenarios["done"])
    assert scenarios["done"]["status"] == "SUCCESS"


def test_invalid_event_file_fails_only_its_scenario(env):
    env.scenario("garbled")
    env.scenario("fine")
    env.emitted("garbled", "e.json", "{not json")
    env.emitted("fine", "e.json", run_event())

    scenarios = env.validate()

    validation = by_name(scenarios["garbled"])["validation"]
    assert validation["status"] == "FAILURE"
    assert validation["details"][0].startswith("validation failed:")
    assert scenarios["fine"]["status"] == "SUCCESS"


def test_openlineage_release_gates_when_the_spec_tag_is_not_a_version(env, tmp_path):
    (tmp_path / "specs" / OL).rename(tmp_path / "specs" / "main")
    env.scenario("future", openlineage_versions={"min": "9.0.0"})
    env.scenario("now", openlineage_versions={"min": "1.0.0"})

    scenarios = env.validate(f"--openlineage_release={OL}", ol="main")

    assert set(scenarios) == {"now"}


def test_unreadable_config_fails_only_its_scenario(env):
    env.scenario("fine")
    env.emitted("fine", "e.json", run_event())
    broken = env.producer / COMPONENT / "scenarios" / "broken_config"
    broken.mkdir(parents=True)
    (broken / "config.json").write_text("{oops")

    scenarios = env.validate()

    assert by_name(scenarios["broken_config"])["validation"]["status"] == "FAILURE"
    assert scenarios["fine"]["status"] == "SUCCESS"
