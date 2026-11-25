"""Alarms for a broken CI pipeline, as `ci-broken` issues (compatibility failures are reported elsewhere).

  run-status  the final job of a workflow run: one issue per workflow while any job of its latest run failed or was cancelled.
              A failed job always means the pipeline broke (infra, a script crash, an expired token): compatibility
              failures never fail a job, they end up in the report. With --pending (the release check's
              pending_runs.json), the issue also lists the parts without a result, and stays open while a part has
              had none for --escalate-after runs in a row.
  health      a weekly check: a push token expired or expiring within 30 days (one issue per token), the compatibility
              site behind the report, the release check not running.

Each alarm is an issue with a hidden key. It is created when the alarm starts, gets a comment only when what is wrong
changes, is reopened if it comes back, and is closed (with a comment) when it is over. --dry-run prints the plan.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from issue_common import Action, Gh, Issue, format_actions, owned_issues, render_body

LABEL = "ci-broken"
LABEL_COLOR = "B60205"
LABEL_DESCRIPTION = "The CI pipeline itself is broken (not a compatibility failure)"
FAILED_CONCLUSIONS = {"failure", "cancelled", "timed_out", "startup_failure"}
TOKEN_WARNING_DAYS = 30
SITE_MAX_LAG = timedelta(days=3)
RELEASE_CHECK_MAX_AGE = timedelta(days=3)
RELEASE_CHECK_WORKFLOW = "main_new_release.yml"
ESCALATE_AFTER = 3
STUCK = "no result: "  # signature entries for stuck parts; the other entries are job names
SITE_REPO = "OpenLineage/openlineage-site"

TOKENS = {
    "CI_PUSH_TOKEN": {
        "repo": "OpenLineage/compatibility-tests",
        "used_by": "`update-repo-files` in the release check (`main_new_release.yml`) and the spec-change check "
                   "(`main_ol_spec_changes.yml`): pushes the updated report and the `[bot]` commits to `main`.",
        "after": "Dispatch the release check (`main_new_release.yml`) or wait for the next scheduled run.",
    },
    "OL_SITE_PUSH_TOKEN": {
        "repo": "OpenLineage/openlineage-site",
        "used_by": "`update-site` in the release check (`main_new_release.yml`) and `publish_site.yml`: pushes the "
                   "compatibility tables to the site.",
        "after": "Dispatch `publish_site.yml` to bring the site up to date with `main`'s report.",
    },
}


@dataclass
class Check:
    """One alarm. `signature` is what a comment is about: when it changes, the issue gets `changed_comment(old_state)`."""
    key: str
    alarm: bool
    title: str = ""
    text: str = ""
    state: dict = field(default_factory=dict)
    signature: list = field(default_factory=list)
    changed_comment: Callable[[dict], str] = lambda old: ""
    resolved_comment: str = ""


def plan(checks, issues):
    owned = owned_issues(issues)
    actions = []
    for check in checks:
        existing = owned.get(check.key)
        if not check.alarm:
            if existing and existing.is_open:
                actions.append(Action("close", check.key, existing.number, comment=check.resolved_comment))
            continue
        body = render_body(check.key, check.text, {**check.state, "signature": check.signature})
        if existing is None:
            actions.append(Action("create", check.key, title=check.title, body=body, labels=[LABEL]))
            continue
        old = existing.stored_state
        title = check.title if check.title != existing.title else None
        if not existing.is_open:
            actions.append(Action("reopen", check.key, existing.number, title=title, body=body,
                                  comment=f"Failing again.\n\n{check.changed_comment(old)}".rstrip()))
        elif old.get("signature") != check.signature:
            actions.append(Action("comment", check.key, existing.number, title=title, body=body,
                                  comment=check.changed_comment(old)))
        elif body != existing.body or title:
            actions.append(Action("update", check.key, existing.number, title=title, body=body))
    return actions


# ---------- run-status ----------

def part_label(part):
    label = part["component"]
    if part.get("component_version"):
        label += f" {part['component_version']}"
    if part.get("openlineage_version"):
        label += f" × OL {part['openlineage_version']}"
    return label


def pending_table(pending, escalate_after):
    rows = "\n".join(f"| {part_label(p)} | {'**' if p['failures'] >= escalate_after else ''}{p['failures']}"
                     f"{'**' if p['failures'] >= escalate_after else ''} | [run]({p['first_failed_run']}) |"
                     for p in pending)
    return ("### Parts without a result\n\n"
            "Every scheduled run retries them (`generated-files/pending_runs.json`). A part without a result for "
            f"{escalate_after} runs in a row keeps this issue open until it gets one.\n\n"
            f"| Part | Runs in a row without a result | Since |\n|---|---|---|\n{rows}")


def run_status_check(workflow, run_url, jobs, self_job, previous=None, pending=(), escalate_after=ESCALATE_AFTER):
    """previous: the stored state of the workflow's open issue, if any. A job that failed before must run again and pass
    before the issue closes: a run that skips it (nothing changed, or an earlier job failed) proves nothing.
    pending: the parts without a result after this run (pending_runs.json); a part at `escalate_after` runs or more is
    stuck: it keeps the issue open (even when every job passed) and gets one comment when it gets stuck."""
    key = f"workflow:{workflow}"
    old_signature = (previous or {}).get("signature", [])
    old_jobs = [n for n in old_signature if not n.startswith(STUCK)]
    failed = sorted((j for j in jobs if j.get("conclusion") in FAILED_CONCLUSIONS and j["name"] != self_job),
                    key=lambda j: j["name"])
    passed = {j["name"] for j in jobs if j.get("conclusion") == "success"}
    not_rerun = [n for n in old_jobs if n not in passed]
    stuck = [p for p in pending if p["failures"] >= escalate_after]

    if failed:
        job_names = [j["name"] for j in failed]
        rows = "\n".join(f"| [{j['name']}]({j.get('html_url') or run_url}) | {j['conclusion']} |" for j in failed)
        text = (f"Jobs of **{workflow}** failed in its latest run: {run_url}\n\n| Job | Result |\n|---|---|\n{rows}\n\n"
                "A failed job means the pipeline itself broke (infrastructure, a script crash, an expired token): "
                "compatibility failures never fail a job, they go to the report. Jobs that depend on a failed one "
                "(report update, compatibility tables, site, issues) may have been skipped.")
        closes = "Closed automatically once the failed jobs run again and pass"
    elif not_rerun:
        job_names = old_jobs  # unchanged, so no comment
        listed = "\n".join(f"- `{n}`" for n in not_rerun)
        text = (f"No job of **{workflow}** failed in its latest run ({run_url}), but these jobs failed earlier and "
                f"haven't run since (dispatch the workflow to run them):\n\n{listed}")
        closes = "Closed automatically once they run and pass"
    elif stuck:
        job_names = []
        text = (f"Every job of **{workflow}** passed in its latest run ({run_url}), but some parts have had no result "
                f"for {escalate_after} runs in a row or more. A job can pass without a result, e.g. when its "
                "producer job didn't run and validation was skipped, so check the job logs of the runs listed.")
        closes = "Closed automatically once"
    else:
        return Check(key, alarm=False, resolved_comment=f"All jobs passed in {run_url}.")

    if pending:
        text += "\n\n" + pending_table(pending, escalate_after)
    if stuck:
        closes += ("" if closes.endswith("once") else " and") + f" no part has gone {escalate_after} runs without a result"
    text += f"\n\n{closes}."
    stuck_entries = [STUCK + part_label(p) for p in stuck]

    def changed(old):
        before = old.get("signature", [])
        before_jobs = {n for n in before if not n.startswith(STUCK)}
        before_stuck = {n for n in before if n.startswith(STUCK)}
        lines = [f"What changed in {run_url}:"]
        new = [n for n in job_names if n not in before_jobs]
        fixed = sorted(before_jobs - set(job_names))
        if new:
            lines.append("Now failing: " + ", ".join(f"`{n}`" for n in new))
        if fixed:
            lines.append("No longer failing: " + ", ".join(f"`{n}`" for n in fixed))
        for part, entry in zip(stuck, stuck_entries):
            if entry not in before_stuck:
                lines.append(f"No result for {part['failures']} runs in a row: `{part_label(part)}` "
                             f"(since [this run]({part['first_failed_run']})).")
        recovered = sorted(before_stuck - set(stuck_entries))
        if recovered:
            lines.append("Has a result again: " + ", ".join(f"`{n[len(STUCK):]}`" for n in recovered))
        return "\n\n".join(lines)

    return Check(key, alarm=True, title=f"CI pipeline failing: {workflow}", text=text, state={"run": run_url},
                 signature=job_names + stuck_entries, changed_comment=changed)


def fetch_jobs(repo, run_id, run_attempt):
    out = subprocess.run(["gh", "api", "--paginate", f"repos/{repo}/actions/runs/{run_id}/attempts/{run_attempt}/jobs",
                          "--jq", ".jobs[] | {name, conclusion, html_url}"],
                         capture_output=True, text=True, check=True).stdout
    return [json.loads(line) for line in out.splitlines() if line.strip()]


# ---------- health ----------

def parse_expiration(value):
    """The `github-authentication-token-expiration` header, e.g. `2027-11-18 13:20:00 UTC` or `... +0000`."""
    for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S %z"):
        try:
            parsed = datetime.strptime(value.strip(), fmt)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def token_check(name, status, expiration, now):
    """status: HTTP status of GET https://api.github.com/ with the token; expiration: the header value or None."""
    info = TOKENS[name]
    key = f"token:{name}"
    expires = parse_expiration(expiration) if expiration else None
    if status == 401:
        title, problem, signature = (f"CI token expired/invalid: {name}",
                                     f"`{name}` is rejected by GitHub (401): it expired or was revoked.", ["invalid"])
    elif expires and expires - now <= timedelta(days=TOKEN_WARNING_DAYS):
        day = expires.strftime("%Y-%m-%d")
        title, problem, signature = (f"CI token expiring: {name} ({day})",
                                     f"`{name}` expires on {expires:%Y-%m-%d %H:%M} UTC.", ["expiring", day])
    else:
        later = f" (it now expires on {expires:%Y-%m-%d})" if expires else ""
        return Check(key, alarm=False, resolved_comment=f"`{name}` works again{later}.")
    text = f"""{problem}

**Used by:** {info['used_by']}

**Rotate it:**
1. Create a fine-grained personal access token: resource owner `OpenLineage`, repository access **only**
   `{info['repo']}`, permission **Contents: read and write**, expiration 1 year.
2. Update the repository secret `{name}` in `OpenLineage/compatibility-tests` (Settings → Secrets and variables → Actions).
3. {info['after']}

**Possible blockers:**
- The `OpenLineage` organization may require approval for fine-grained tokens: an org owner approves it under
  Settings → Personal access tokens → Pending requests.
- Branch protection on `{info['repo']}`'s `main` may reject the bot's direct push.
- If fine-grained tokens aren't allowed, a classic token with the `public_repo` scope works too.

Closed automatically by the weekly health check (`ci_health.yml`) once the token works and expires in more than
{TOKEN_WARNING_DAYS} days."""
    return Check(key, alarm=True, title=title, text=text, signature=signature,
                 changed_comment=lambda old: problem)


def site_check(report_date, site_date):
    key = "site-stale"
    if report_date is None or site_date is None or report_date - site_date <= SITE_MAX_LAG:
        return Check(key, alarm=False, resolved_comment="The compatibility site is up to date with the report again.")
    text = (f"The last report update on `main` is from {report_date:%Y-%m-%d}, but the last compatibility-table update "
            f"on `{SITE_REPO}` is from {site_date:%Y-%m-%d}.\n\n"
            "Check the `update-site` job of the latest release check, and whether `OL_SITE_PUSH_TOKEN` works. Once "
            "fixed, dispatch `publish_site.yml` to publish `main`'s report.")
    site_day = f"{site_date:%Y-%m-%d}"
    return Check(key, alarm=True, title="CI: the compatibility site is behind the report", text=text,
                 signature=[site_day], changed_comment=lambda old: f"Still behind: the site was last updated {site_day}, "
                                                                     f"the report {report_date:%Y-%m-%d}.")


def release_check_age_check(last_run, now):
    key = "release-check-age"
    if last_run is not None and now - last_run <= RELEASE_CHECK_MAX_AGE:
        return Check(key, alarm=False, resolved_comment="The release check runs again.")
    when = f"{last_run:%Y-%m-%d}" if last_run else "never"
    text = (f"The last run of the release check (`{RELEASE_CHECK_WORKFLOW}`) started: {when}. It is scheduled daily; "
            "GitHub disables scheduled workflows of repositories without activity for 60 days. Re-enable it under "
            "Actions → Release check, or dispatch it.")
    return Check(key, alarm=True, title="CI: the release check stopped running", text=text, signature=[when],
                 changed_comment=lambda old: f"Last run: {when}.")


def github_get(url, token):
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                                   "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.headers.get("github-authentication-token-expiration")
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get("github-authentication-token-expiration")


def gh_api(path, jq):
    out = subprocess.run(["gh", "api", path, "--jq", jq], capture_output=True, text=True, check=True).stdout.strip()
    return out or None


def to_datetime(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def health_checks(repo, env, now, get=github_get, api=gh_api):
    checks = []
    for name in TOKENS:
        token = env.get(name)
        if not token:
            print(f"::warning::{name} is not set; its expiry isn't checked", file=sys.stderr)
            continue
        status, expiration = get("https://api.github.com/", token)
        checks.append(token_check(name, status, expiration, now))
    first_date = 'map(select(.commit.message | startswith("{}"))) | .[0].commit.committer.date // empty'
    report_date = to_datetime(api(f"repos/{repo}/commits?sha=main&per_page=100", first_date.format("[bot] update report")))
    site_date = to_datetime(api(f"repos/{SITE_REPO}/commits?per_page=100",
                                first_date.format("[bot] update compatibility tables")))
    checks.append(site_check(report_date, site_date))
    last_run = to_datetime(api(f"repos/{repo}/actions/workflows/{RELEASE_CHECK_WORKFLOW}/runs?per_page=1",
                               ".workflow_runs[0].created_at // empty"))
    checks.append(release_check_age_check(last_run, now))
    return checks


# ---------- main ----------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run-status", help="alarm for the failed jobs of a workflow run")
    run.add_argument("--workflow", required=True, help="workflow name, one issue per workflow")
    run.add_argument("--run-id", required=True)
    run.add_argument("--run-attempt", default="1")
    run.add_argument("--self-job", default="pipeline-alarm", help="the job running this script, not counted")
    run.add_argument("--jobs-file", help="JSON list of {name, conclusion, html_url} instead of asking GitHub")
    run.add_argument("--pending", help="the pending parts after this run (the release check's pending_runs.json)")
    run.add_argument("--escalate-after", type=int, default=ESCALATE_AFTER,
                     help="runs in a row without a result after which a part keeps the issue open")
    health = sub.add_parser("health", help="token expiry, site staleness, release check age")
    for p in (run, health):
        p.add_argument("--repo", required=True)
        p.add_argument("--dry-run", action="store_true", help="print the planned changes, change nothing")
        p.add_argument("--issues-file", help="JSON list of {number, title, body, state} instead of asking GitHub")
    args = parser.parse_args(argv)

    gh = Gh(args.repo)
    if args.issues_file:
        with open(args.issues_file) as f:
            issues = [Issue(**i) for i in json.load(f)]
    else:
        issues = gh.list_issues(LABEL)
    if args.command == "run-status":
        run_url = f"https://github.com/{args.repo}/actions/runs/{args.run_id}"
        if args.jobs_file:
            with open(args.jobs_file) as f:
                jobs = json.load(f)
        else:
            jobs = fetch_jobs(args.repo, args.run_id, args.run_attempt)
        existing = owned_issues(issues).get(f"workflow:{args.workflow}")
        previous = existing.stored_state if existing and existing.is_open else None
        pending = []
        if args.pending:
            with open(args.pending) as f:
                pending = json.load(f)
        checks = [run_status_check(args.workflow, run_url, jobs, args.self_job, previous, pending,
                                   args.escalate_after)]
    else:
        checks = health_checks(args.repo, os.environ, datetime.now(timezone.utc))

    actions = plan(checks, issues)
    if args.dry_run:
        print(format_actions(actions))
        return 0
    if actions:
        gh.ensure_label(LABEL, LABEL_COLOR, LABEL_DESCRIPTION)
        gh.apply(actions)
    for action in actions:
        print(f"{action.kind} {f'#{action.issue}' if action.issue else ''} {action.key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
