"""Shared pieces of the scripts that keep issues in sync with CI (ci_alarm.py).

An issue owned by a script carries a hidden marker with its key, e.g. `<!-- compat-tests:issue key=workflow:Release check -->`,
and a hidden JSON state block. The scripts only ever touch issues with their marker. Each script first plans its actions
(a pure function of its inputs and the existing issues), then applies them through the `gh` CLI, or prints them with
--dry-run.
"""
import json
import re
import subprocess
from dataclasses import dataclass, field

MARKER = "<!-- compat-tests:issue key={key} -->"
MARKER_RE = re.compile(r"<!-- compat-tests:issue key=(.+?) -->")
STATE_RE = re.compile(r"<!-- compat-tests:state (.*?) -->", re.DOTALL)
OWNED_NOTE = "_This issue is maintained by CI: the description is rewritten on every run. Discuss in comments._"


@dataclass
class Issue:
    number: int
    title: str
    body: str
    state: str  # "OPEN" or "CLOSED"

    @property
    def key(self):
        match = MARKER_RE.search(self.body or "")
        return match.group(1) if match else None

    @property
    def stored_state(self):
        match = STATE_RE.search(self.body or "")
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return {}

    @property
    def is_open(self):
        return self.state.upper() == "OPEN"


@dataclass
class Action:
    """kind: create | update | comment | close | reopen. `issue` is None for create."""
    kind: str
    key: str
    issue: int | None = None
    title: str | None = None
    body: str | None = None
    comment: str | None = None
    labels: list = field(default_factory=list)


def render_body(key, text, state):
    # "--" can't appear inside an HTML comment; the state is JSON, so escape it
    state_json = json.dumps(state, sort_keys=True).replace("--", "\\u002d\\u002d")
    return f"{MARKER.format(key=key)}\n{text.rstrip()}\n\n{OWNED_NOTE}\n<!-- compat-tests:state {state_json} -->\n"


def owned_issues(issues):
    """Issues with a marker, by key. If a key has several issues, the open one (else the newest) wins."""
    by_key = {}
    for issue in sorted(issues, key=lambda i: i.number):
        if issue.key is None:
            continue
        current = by_key.get(issue.key)
        if current is None or issue.is_open or not current.is_open:
            by_key[issue.key] = issue
    return by_key


def format_actions(actions):
    """Markdown for --dry-run."""
    if not actions:
        return "No changes."
    lines = []
    for action in actions:
        target = f"#{action.issue}" if action.issue else "new issue"
        lines.append(f"### {action.kind} {target} ({action.key})")
        if action.title:
            lines.append(f"**Title:** {action.title}")
        if action.comment:
            lines.append(f"**Comment:**\n\n{action.comment}")
        if action.body:
            lines.append(f"**Body:**\n\n{action.body}")
    return "\n\n".join(lines)


class Gh:
    """Thin wrapper around the `gh` CLI for one repository."""

    def __init__(self, repo):
        self.repo = repo

    def _run(self, *args, input_text=None):
        result = subprocess.run(["gh", *args, "--repo", self.repo], input=input_text, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout

    def list_issues(self, label):
        out = self._run("issue", "list", "--label", label, "--state", "all", "--limit", "1000",
                        "--json", "number,title,body,state")
        return [Issue(**item) for item in json.loads(out)]

    def ensure_label(self, label, color, description):
        subprocess.run(["gh", "label", "create", label, "--color", color, "--description", description,
                        "--repo", self.repo], capture_output=True, text=True)  # fails if it exists, which is fine

    def apply(self, actions):
        for action in actions:
            if action.kind == "create":
                args = ["issue", "create", "--title", action.title, "--body-file", "-"]
                for label in action.labels:
                    args += ["--label", label]
                self._run(*args, input_text=action.body)
                continue
            number = str(action.issue)
            if action.kind == "reopen":
                self._run("issue", "reopen", number)
            if action.body is not None or action.title is not None:
                args = ["issue", "edit", number]
                if action.title is not None:
                    args += ["--title", action.title]
                if action.body is not None:
                    args += ["--body-file", "-"]
                self._run(*args, input_text=action.body)
            if action.comment:
                self._run("issue", "comment", number, "--body-file", "-", input_text=action.comment)
            if action.kind == "close":
                self._run("issue", "close", number)
