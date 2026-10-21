// Creates a Dataproc cluster in the main step and deletes it in the post step.
// Uses only Node built-ins, so there is nothing to install or bundle.

const { spawnSync } = require("child_process");
const fs = require("fs");

function input(name) {
  return (process.env[`INPUT_${name.toUpperCase()}`] || "").trim();
}

function saveState(name, value) {
  fs.appendFileSync(process.env.GITHUB_STATE, `${name}=${value}\n`);
}

function fail(message) {
  console.log(`::error::${message}`);
  process.exitCode = 1;
}

function run(command, args, stdio = "inherit") {
  return spawnSync(command, args, { stdio }).status;
}

function gcloudCluster(action, cluster, args = [], stdio = "inherit") {
  return run("gcloud", ["dataproc", "clusters", action, cluster.name,
    "--project", cluster.project, "--region", cluster.region, ...args], stdio);
}

function main() {
  // saved before creating, so the post step also deletes a cluster left behind by a failed create
  saveState("cluster_name", input("cluster-name"));
  saveState("project_id", input("project-id"));
  saveState("region", input("region"));

  if (run("bash", ["-e", "-c", input("create-command")]) !== 0) {
    fail(`Creating cluster ${input("cluster-name")} failed`);
  }
}

function post() {
  const cluster = {
    name: process.env.STATE_cluster_name,
    project: process.env.STATE_project_id,
    region: process.env.STATE_region,
  };
  if (gcloudCluster("describe", cluster, ["--format=none"], "ignore") !== 0) {
    console.log(`Cluster ${cluster.name} does not exist`);
    return;
  }
  console.log(`Deleting cluster ${cluster.name}`);
  if (gcloudCluster("delete", cluster, ["--quiet"]) !== 0) {
    fail(`Deleting cluster ${cluster.name} failed, delete it manually`);
  }
}

if (process.env.STATE_cluster_name) {
  post();
} else {
  main();
}
