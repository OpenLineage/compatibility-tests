import * as core from "@actions/core";
import * as exec from "@actions/exec";

const POST_STEP = "POST"

async function run() {
    const nextStep = core.getState("nextStep");

    if (nextStep === POST_STEP) {
        await post();
    } else {
        core.saveState("nextStep", POST_STEP);
        try {
            await pre();
            await main();
        } catch (err) {
            core.setFailed(err.message);
        }
    }
}

async function pre() {
    const preCommand = core.getInput("pre-command");

    if (preCommand) {
        core.info("Running PRE step...");
        await exec.exec("bash", ["-c", preCommand]);
        core.info("Done PRE step!");
    }
}

async function main() {
    core.info("Running MAIN step...");

    const command = core.getInput("command");
    await exec.exec("bash", ["-c", command]);

    core.info("Done MAIN step!");
}

async function post() {
    core.info("Running POST step...");
    try {
        const postCommand = core.getInput("post-command");
        await exec.exec("bash", ["-c", postCommand]);
    } catch (err) {
        core.setFailed(err.message);
    }
    core.info("Done POST step!");
}

run();