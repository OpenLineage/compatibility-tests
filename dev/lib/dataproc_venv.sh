# shellcheck shell=bash
# Sourced by the local run scripts of the Dataproc producers.

# dataproc_venv <cache dir>: creates (or reuses) a virtualenv with dev/dataproc/requirements.txt, recreated when the
# requirements change, and puts it first on PATH: the dev/ and runner/ scripts call `python`.
# PYTHON (default python3) creates it.
dataproc_venv() {
  local repo_root venv requirements_hash
  repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  venv="$1/venvs/dataproc"
  requirements_hash=$(shasum "$repo_root/dev/dataproc/requirements.txt" | cut -d' ' -f1)
  if [[ ! -x "$venv/bin/python" || "$(cat "$venv/.requirements-hash" 2> /dev/null)" != "$requirements_hash" ]]; then
    rm -rf "$venv"
    "${PYTHON:-python3}" -m venv "$venv"
    "$venv/bin/python" -m pip install --quiet --upgrade pip
    "$venv/bin/python" -m pip install --quiet -r "$repo_root/dev/dataproc/requirements.txt"
    echo "$requirements_hash" > "$venv/.requirements-hash"
  fi
  export PATH="$venv/bin:$PATH"
  echo "virtualenv: $venv"
}

# dataproc_user_slug: your user name as it can appear in a cluster name (lowercase letters, digits, dashes; at most 10)
dataproc_user_slug() {
  echo "${USER:-user}" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9\n' '-' | cut -c1-10
}
