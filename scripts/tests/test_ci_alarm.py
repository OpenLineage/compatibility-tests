import json
from datetime import datetime, timedelta, timezone

import pytest

import ci_alarm
from ci_alarm import health_checks, plan, run_status_check
from issue_common import Issue, render_body

RUN = "https://github.com/o/r/actions/runs/2"
NOW = datetime(2026, 11, 23, 6, 0, tzinfo=timezone.utc)


def job(name, conclusion="success"):
    return {"name": name, "conclusion": conclusion, "html_url": f"https://github.com/o/r/actions/runs/2/job/{name}"}


def issue_for(check, number=7, state="OPEN"):
    """The issue as the bot left it after `check`."""
    [action] = plan([check], [])
    return Issue(number=number, title=action.title, body=action.body, state=state)


def status(jobs):
    return run_status_check("Release check", RUN, jobs, "pipeline-alarm")


# ---------- run-status ----------

def test_failed_job_creates_an_issue():
    [action] = plan([status([job("dbt"), job("collect", "failure"), job("pipeline-alarm", None)])], [])
    assert action.kind == "create"
    assert action.title == "CI pipeline failing: Release check"
    assert action.labels == ["ci-broken"]
    assert "| [collect](https://github.com/o/r/actions/runs/2/job/collect) | failure |" in action.body
    assert "dbt" not in action.body
    assert "<!-- compat-tests:issue key=workflow:Release check -->" in action.body


def test_cancelled_and_timed_out_jobs_count():
    check = status([job("a", "cancelled"), job("b", "timed_out"), job("c", "skipped")])
    assert check.signature == ["a", "b"]


def test_the_alarm_job_itself_is_not_counted():
    assert not status([job("pipeline-alarm", "failure")]).alarm


def test_same_failed_jobs_update_the_body_only():
    existing = issue_for(status([job("collect", "failure")]))
    later = run_status_check("Release check", "https://github.com/o/r/actions/runs/3", [job("collect", "failure")],
                             "pipeline-alarm")
    [action] = plan([later], [existing])
    assert action.kind == "update"
    assert action.comment is None
    assert "runs/3" in action.body


def test_identical_run_is_a_no_op():
    check = status([job("collect", "failure")])
    assert plan([check], [issue_for(check)]) == []


def test_different_failed_jobs_comment():
    existing = issue_for(status([job("collect", "failure")]))
    [action] = plan([status([job("stage-openlineage-jars", "failure")])], [existing])
    assert action.kind == "comment"
    assert "Now failing: `stage-openlineage-jars`" in action.comment
    assert "No longer failing: `collect`" in action.comment


def test_all_green_closes_the_issue():
    existing = issue_for(status([job("collect", "failure")]))
    [action] = plan([status([job("collect")])], [existing])
    assert action.kind == "close"
    assert action.issue == 7
    assert RUN in action.comment


def test_green_run_that_skipped_the_failed_job_keeps_the_issue_open():
    existing = issue_for(status([job("collect", "failure")]))
    check = run_status_check("Release check", "https://github.com/o/r/actions/runs/3",
                             [job("initialize_workflow"), job("collect", "skipped")], "pipeline-alarm",
                             existing.stored_state)
    [action] = plan([check], [existing])
    assert action.kind == "update"  # no comment, nothing new failed
    assert "haven't run since" in action.body and "- `collect`" in action.body
    later = run_status_check("Release check", RUN, [job("collect")], "pipeline-alarm", existing.stored_state)
    assert [a.kind for a in plan([later], [existing])] == ["close"]


def test_cli_closes_only_when_the_failed_job_passed(tmp_path, capsys):
    existing = issue_for(status([job("collect", "failure")]))
    issues = tmp_path / "issues.json"
    issues.write_text(json.dumps([existing.__dict__]))
    jobs = tmp_path / "jobs.json"
    for jobs_list, expected in (([job("dbt")], "### update #7"), ([job("collect")], "### close #7")):
        jobs.write_text(json.dumps(jobs_list))
        ci_alarm.main(["run-status", "--repo", "o/r", "--workflow", "Release check", "--run-id", "2",
                       "--jobs-file", str(jobs), "--issues-file", str(issues), "--dry-run"])
        assert expected in capsys.readouterr().out


def test_all_green_without_an_issue_is_a_no_op():
    assert plan([status([job("collect")])], []) == []


def test_closed_issue_is_reopened_when_it_fails_again():
    existing = issue_for(status([job("collect", "failure")]), state="CLOSED")
    [action] = plan([status([job("collect", "failure")])], [existing])
    assert action.kind == "reopen"
    assert action.comment.startswith("Failing again.")


def test_issues_without_the_marker_are_never_touched():
    human = Issue(number=292, title="CI pipeline failing: Release check", body="written by a person", state="OPEN")
    [action] = plan([status([job("collect", "failure")])], [human])
    assert action.kind == "create"
    assert plan([status([job("collect")])], [human]) == []


def test_workflows_have_separate_issues():
    release = issue_for(status([job("collect", "failure")]))
    spec = run_status_check("Check for changes in OL", RUN, [job("collect", "failure")], "pipeline-alarm")
    [action] = plan([spec], [release])
    assert action.kind == "create"


# ---------- run-status: parts without a result ----------

FIRST = "https://github.com/o/r/actions/runs/1"


def part(failures, component="spark_dataproc", cv="3.5.1", ol="1.55.0"):
    return {"component": component, "component_version": cv, "openlineage_version": ol, "failures": failures,
            "first_failed_run": FIRST, "last_failed_run": RUN}


def run(jobs, pending, existing=None, run_url=RUN):
    previous = existing.stored_state if existing and existing.is_open else None
    return run_status_check("Release check", run_url, jobs, "pipeline-alarm", previous, pending)


def test_part_below_the_limit_is_listed_without_a_comment():
    existing = issue_for(status([job("spark", "failure")]))
    [action] = plan([run([job("spark", "failure")], [part(2)], existing)], [existing])
    assert action.kind == "update" and action.comment is None
    assert "| spark_dataproc 3.5.1 × OL 1.55.0 | 2 | [run](https://github.com/o/r/actions/runs/1) |" in action.body


def test_part_below_the_limit_with_green_jobs_opens_nothing():
    assert plan([run([job("spark")], [part(2)])], []) == []


def test_part_reaching_the_limit_gets_one_comment():
    existing = issue_for(run([job("spark", "failure")], [part(2)]))
    reached = run([job("spark", "failure")], [part(3)], existing, "https://github.com/o/r/actions/runs/3")
    [action] = plan([reached], [existing])
    assert action.kind == "comment"
    assert "No result for 3 runs in a row: `spark_dataproc 3.5.1 × OL 1.55.0`" in action.comment
    assert "Now failing" not in action.comment
    assert "| spark_dataproc 3.5.1 × OL 1.55.0 | **3** |" in action.body
    after = Issue(number=7, title=existing.title, body=action.body, state="OPEN")
    [later] = plan([run([job("spark", "failure")], [part(4)], after, "https://github.com/o/r/actions/runs/4")], [after])
    assert later.kind == "update" and later.comment is None
    assert "| **4** |" in later.body


def test_stuck_part_keeps_the_issue_open_when_every_job_passed():
    existing = issue_for(run([job("spark", "failure")], [part(3)]))
    [action] = plan([run([job("spark")], [part(3)], existing)], [existing])
    assert action.kind == "comment"  # the failed job passed, the part is still stuck
    assert "No longer failing: `spark`" in action.comment
    assert "Every job of **Release check** passed" in action.body
    assert "no part has gone 3 runs without a result" in action.body


def test_stuck_part_with_green_jobs_opens_an_issue():
    [action] = plan([run([job("spark")], [part(5)])], [])
    assert action.kind == "create"
    assert "| spark_dataproc 3.5.1 × OL 1.55.0 | **5** |" in action.body


def test_part_with_a_result_again_is_removed_and_the_issue_closes():
    existing = issue_for(run([job("spark")], [part(3), part(1, "dbt", "1.8.0")]))
    still = run([job("spark")], [part(3)], existing)
    [action] = plan([still], [existing])
    assert action.kind == "update" and "dbt" not in action.body
    [action] = plan([run([job("spark")], [], existing)], [existing])
    assert action.kind == "close"


def test_stuck_part_recovering_while_a_job_still_fails_comments():
    existing = issue_for(run([job("spark", "failure")], [part(3)]))
    [action] = plan([run([job("spark", "failure")], [], existing)], [existing])
    assert action.kind == "comment"
    assert "Has a result again: `spark_dataproc 3.5.1 × OL 1.55.0`" in action.comment
    assert "Parts without a result" not in action.body


def test_consumer_parts_have_no_versions_in_the_label():
    [action] = plan([run([job("spark")], [part(3, "dataplex", "", "")])], [])
    assert "| dataplex | **3** |" in action.body


def test_cli_reads_the_pending_file(tmp_path, capsys):
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps([job("spark")]))
    issues = tmp_path / "issues.json"
    issues.write_text("[]")
    pending = tmp_path / "pending.json"
    pending.write_text(json.dumps([part(2)]))
    args = ["run-status", "--repo", "o/r", "--workflow", "Release check", "--run-id", "2", "--jobs-file", str(jobs),
            "--issues-file", str(issues), "--pending", str(pending), "--dry-run"]
    ci_alarm.main(args)
    assert "### create" not in capsys.readouterr().out
    ci_alarm.main(args + ["--escalate-after", "2"])
    assert "### create" in capsys.readouterr().out


# ---------- health ----------

def health(tokens=None, report="2026-11-22T11:00:00Z", site="2026-11-22T11:01:00Z", last_run="2026-11-22T10:00:00Z"):
    """tokens: name -> (status, expiration header)"""
    tokens = tokens if tokens is not None else {name: (200, "2027-11-18 13:20:00 UTC") for name in ci_alarm.TOKENS}

    def get(url, token):
        return tokens[token]

    def api(path, jq):
        if "openlineage-site" in path:
            return site
        if "/runs" in path:
            return last_run
        return report

    return health_checks("o/r", {name: name for name in tokens}, NOW, get=get, api=api)


def by_key(checks):
    return {c.key: c for c in checks}


def test_all_fine_raises_no_alarm():
    assert not any(c.alarm for c in health())


def test_expired_token_alarms():
    checks = by_key(health({"CI_PUSH_TOKEN": (401, None), "OL_SITE_PUSH_TOKEN": (200, "2027-11-18 13:20:00 UTC")}))
    assert checks["token:CI_PUSH_TOKEN"].alarm
    assert checks["token:CI_PUSH_TOKEN"].title == "CI token expired/invalid: CI_PUSH_TOKEN"
    assert not checks["token:OL_SITE_PUSH_TOKEN"].alarm


def test_token_expiring_within_30_days_gets_its_own_issue_with_the_date_and_runbook():
    soon = (NOW + timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S UTC")
    checks = health({"CI_PUSH_TOKEN": (200, soon), "OL_SITE_PUSH_TOKEN": (200, soon)})
    actions = plan(checks, [])
    titles = sorted(a.title for a in actions)
    assert titles == ["CI token expiring: CI_PUSH_TOKEN (2026-12-03)", "CI token expiring: OL_SITE_PUSH_TOKEN (2026-12-03)"]
    site = next(a for a in actions if "OL_SITE" in a.title)
    assert "only**\n   `OpenLineage/openlineage-site`" in site.body
    assert "Contents: read and write" in site.body
    assert "publish_site.yml" in site.body


def test_token_expiring_in_90_days_is_fine():
    later = (NOW + timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S +0000")
    assert not by_key(health({"CI_PUSH_TOKEN": (200, later)}))["token:CI_PUSH_TOKEN"].alarm


def test_token_without_expiry_is_fine():
    assert not by_key(health({"CI_PUSH_TOKEN": (200, None)}))["token:CI_PUSH_TOKEN"].alarm


def test_rotated_token_closes_its_issue():
    soon = (NOW + timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S UTC")
    [old] = [c for c in health({"CI_PUSH_TOKEN": (200, soon)}) if c.key == "token:CI_PUSH_TOKEN"]
    existing = issue_for(old)
    actions = plan(health({"CI_PUSH_TOKEN": (200, "2027-11-23 10:00:00 UTC")}), [existing])
    assert [(a.kind, a.issue) for a in actions] == [("close", 7)]
    assert "2027-11-23" in actions[0].comment


def test_missing_token_is_skipped_not_closed():
    soon = (NOW + timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S UTC")
    existing = issue_for(by_key(health({"CI_PUSH_TOKEN": (200, soon)}))["token:CI_PUSH_TOKEN"])
    assert plan(health({}), [existing]) == []


def test_site_five_days_behind_alarms():
    check = by_key(health(report="2026-11-22T11:00:00Z", site="2026-11-17T11:00:00Z"))["site-stale"]
    assert check.alarm
    assert "2026-11-17" in check.text


def test_site_a_day_behind_is_fine():
    assert not by_key(health(report="2026-11-22T11:00:00Z", site="2026-11-21T11:00:00Z"))["site-stale"].alarm


def test_release_check_four_days_old_alarms():
    check = by_key(health(last_run="2026-11-19T05:00:00Z"))["release-check-age"]
    assert check.alarm
    assert "2026-11-19" in check.text


def test_all_fine_closes_the_open_health_issues():
    stale = issue_for(by_key(health(site="2026-11-01T00:00:00Z"))["site-stale"], number=8)
    old = issue_for(by_key(health(last_run="2026-11-01T00:00:00Z"))["release-check-age"], number=9)
    assert sorted((a.kind, a.issue) for a in plan(health(), [stale, old])) == [("close", 8), ("close", 9)]


def test_unchanged_weekly_alarm_does_not_comment():
    check = by_key(health(site="2026-11-01T00:00:00Z"))["site-stale"]
    assert plan([check], [issue_for(check)]) == []


# ---------- state block ----------

def test_state_survives_the_body_round_trip():
    body = render_body("k", "text", {"signature": ["a--b"], "x": 1})
    issue = Issue(number=1, title="t", body=body, state="OPEN")
    assert issue.key == "k"
    assert issue.stored_state == {"signature": ["a--b"], "x": 1}
    assert "a--b" not in body.split("compat-tests:state")[1]


# ---------- CLI ----------

def test_cli_dry_run(tmp_path, capsys):
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps([job("collect", "failure")]))
    issues = tmp_path / "issues.json"
    issues.write_text("[]")
    assert ci_alarm.main(["run-status", "--repo", "o/r", "--workflow", "Release check", "--run-id", "2",
                          "--jobs-file", str(jobs), "--issues-file", str(issues), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "### create new issue (workflow:Release check)" in out
    assert "**Title:** CI pipeline failing: Release check" in out


@pytest.mark.parametrize("value, expected", [
    ("2027-11-18 13:20:00 UTC", datetime(2027, 11, 18, 13, 20, tzinfo=timezone.utc)),
    ("2027-11-18 13:20:00 +0100", datetime(2027, 11, 18, 12, 20, tzinfo=timezone.utc)),
    ("garbage", None),
])
def test_parse_expiration(value, expected):
    assert ci_alarm.parse_expiration(value) == expected
