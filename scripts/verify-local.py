#!/usr/bin/env python3
"""Opt-in real SSH acceptance. Refresh/doctor/probe existing resources.

Run inside unified-tests with a reviewed JSON plan, an empty data directory and
read-only SSH mounts. Optional npm lifecycle uses a fresh temporary prefix.
Synthetic PTY commands use only printf/read/sleep/exit.
Reports intentionally omit credentials, shell startup output and application logs.
"""

import argparse
import json
import re
import secrets
import shlex
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from unified.api import create_app
from unified.config import Config
from unified.resources import capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--ssh", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.data.exists() and any(args.data.iterdir()):
        parser.error("Use an empty, isolated data directory")
    plan = json.loads(args.plan.read_text())
    token = secrets.token_hex(32)
    api = create_app(
        Config(
            mode="ssh",
            token=token,
            data_dir=args.data,
            ssh_dir=args.ssh,
            job_timeout=180,
        )
    )
    results = []

    def record(name, fn):
        try:
            detail = fn()
            row = dict(check=name, result="pass", detail=detail)
        except Exception as exc:
            # Assertions below contain only bounded, deliberately selected facts.
            row = dict(check=name, result="fail", detail=str(exc)[:500])
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)

    with TestClient(api, headers={"Authorization": "Bearer " + token}) as client:

        def post(route, body, expected=200):
            response = client.post("/api/v1/" + route, json=body)
            assert (
                response.status_code == expected
            ), f"{route}: HTTP {response.status_code}"
            return response.json()

        def get(route):
            response = client.get("/api/v1/" + route)
            assert response.status_code == 200, f"{route}: HTTP {response.status_code}"
            return response.json()

        def wait_job(job, status="success"):
            deadline = time.monotonic() + 190
            while time.monotonic() < deadline:
                observed = get("jobs/" + job["id"])
                if observed["status"] in ("success", "failed"):
                    assert observed["status"] == status, str(
                        observed.get("error", "unexpected job result")
                    )
                    return observed
                time.sleep(0.05)
            raise AssertionError("job timed out")

        def logs(job):
            return "".join(r["text"] for r in get("jobs/" + job["id"] + "/logs"))

        def wait_output(job, text):
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if text in logs(job):
                    return
                time.sleep(0.05)
            raise AssertionError("Expected controlled output missing")

        def input_job(job, data="", close=False):
            route = "jobs/" + job["id"] + "/session"
            session = get(route)
            return post(
                route,
                dict(
                    generation=session["generation"],
                    sequence=session["sequence"] + 1,
                    data=data,
                    close=close,
                ),
            )

        def close_job(job):
            if get("jobs/" + job["id"] + "/session")["phase"] != "closed":
                input_job(job, close=True)

        def run(resource, action, **extra):
            return post(
                "resources/" + resource["id"] + "/jobs",
                dict(action=action, **extra),
                202,
            )

        host = post("hosts", plan["host"], 201)
        for plugin in sorted({r["adapter"] for r in plan["resources"]} | {"ssh-tool"}):
            post("plugins/" + plugin, dict(action="install"))
        resources = {}
        for entry in plan["resources"]:
            resource = post(
                "resources",
                dict(
                    name=entry["name"],
                    host=host["id"],
                    adapter=entry["adapter"],
                    settings=entry["settings"],
                ),
                201,
            )
            resources[entry["name"]] = resource

            def observe(entry=entry, resource=resource):
                job = run(resource, "refresh")
                wait_job(job)
                observed = next(
                    r for r in get("resources") if r["id"] == resource["id"]
                )
                for key, value in entry.get("expect", {}).items():
                    assert (
                        observed[key] == value
                    ), f"{key}: expected {value}, got {observed[key]}"
                assert (
                    client.get("/api/v1/jobs/" + job["id"] + "/log.txt").status_code
                    == 200
                )
                close_job(job)
                return dict(
                    status=observed["status"],
                    version=observed["version"],
                    job=job["id"],
                )

            record(entry["name"] + " refresh + durable history", observe)
            if entry.get("doctor"):

                def doctor(resource=resource):
                    job = run(resource, "doctor")
                    wait_job(job)
                    assert re.search(
                        r"v\d+\.\d+\.\d+", logs(job)
                    ), "Node output missing"
                    close_job(job)
                    return "real Node executed through SSH PTY"

                record(entry["name"] + " doctor", doctor)
            if entry.get("resolve"):

                def resolve(resource=resource):
                    adapter = api.state.application.registry.service(
                        resource["adapter"]
                    )
                    version = client.portal.call(
                        adapter.resolve, host, resource["settings"]
                    )
                    return dict(resolved_version=version, installed=False)

                record(entry["name"] + " registry resolution", resolve)

        if sandbox := plan.get("sandbox_package"):

            def package_lifecycle():
                cfg = api.state.application.config
                prefix = client.portal.call(
                    capture, cfg, host, "mktemp -d /tmp/unified-npm-acceptance.XXXXXXXX"
                )
                assert re.fullmatch(
                    r"/tmp/unified-npm-acceptance\.[A-Za-z0-9]{8}", prefix
                ), "Unexpected scratch directory"
                source = resources[sandbox["resource"]]
                settings = dict(
                    source["settings"], directory=prefix, version=sandbox["from"]
                )
                resource = post(
                    "resources",
                    dict(
                        name="Isolated npm acceptance",
                        host=host["id"],
                        adapter=source["adapter"],
                        settings=settings,
                    ),
                    201,
                )
                observations = []
                try:
                    for action, expected in [
                        ("install", sandbox["from"]),
                        ("upgrade", sandbox["to"]),
                        ("uninstall", "absent"),
                    ]:
                        if action == "upgrade":
                            settings["version"] = sandbox["to"]
                            post(
                                "resources/" + resource["id"],
                                dict(
                                    name=resource["name"],
                                    host=host["id"],
                                    adapter=source["adapter"],
                                    settings=settings,
                                ),
                            )
                        job = run(resource, action, confirm=action == "uninstall")
                        try:
                            wait_job(job)
                            observed = next(
                                r for r in get("resources") if r["id"] == resource["id"]
                            )
                            assert (
                                observed["version"] == expected
                            ), f"{action}: version mismatch"
                            observations.append(
                                dict(action=action, version=observed["version"])
                            )
                            print(
                                f"Isolated npm {action}: {observed['version']}",
                                flush=True,
                            )
                        finally:
                            close_job(job)
                    return observations
                finally:
                    client.portal.call(
                        capture, cfg, host, "rm -rf -- " + shlex.quote(prefix)
                    )

            record(
                "Actual npm install/upgrade/uninstall in temporary prefix",
                package_lifecycle,
            )

        for binding in plan.get("bindings", []):

            def probe(binding=binding):
                resource = resources[binding["resource"]]
                bound = post(
                    "resources/" + resource["id"] + "/bindings",
                    dict(
                        parent=resources[binding["parent"]]["id"],
                        register_command="false",
                        unregister_command="false",
                        verify_command=binding["verify_command"],
                    ),
                    201,
                )
                relation = bound["bindings"][0]
                job = run(resource, "verify", binding=relation["id"])
                wait_job(job)
                updated = next(r for r in get("resources") if r["id"] == resource["id"])
                loaded = updated["bindings"][0]["loaded_version"]
                assert loaded == binding["expect"], "Unexpected loaded version"
                return dict(
                    installed=updated["version"],
                    loaded=loaded,
                    differs=updated["version"] != loaded,
                )

            record(binding["resource"] + " loaded in " + binding["parent"], probe)

        def terminal_case(
            label, command, interaction=None, status="success", marker=None
        ):
            resource = post(
                "resources",
                dict(
                    name=label,
                    host=host["id"],
                    adapter="ssh-tool",
                    settings=dict(directory="/tmp", identity=label, cmd_run=command),
                ),
                201,
            )
            job = run(resource, "run")
            try:
                if interaction is not None:
                    wait_output(job, "READY")
                    input_job(job, interaction)
                done = wait_job(job, status)
                if marker:
                    assert marker in logs(job), "Controlled execution output missing"
                session = get("jobs/" + job["id"] + "/session")
                assert session["phase"] == "shell", "Diagnostic shell unavailable"
                input_job(job, "printf 'DIAG_%s\\n' PROBE\n")
                deadline = time.monotonic() + 10
                while (
                    "DIAG_PROBE" not in get("jobs/" + job["id"] + "/session")["output"]
                ):
                    assert (
                        time.monotonic() < deadline
                    ), "Diagnostic shell did not respond"
                    time.sleep(0.05)
                assert "DIAG_PROBE" not in logs(
                    job
                ), "Diagnostic output leaked to job history"
                return dict(
                    status=done["status"], shell="interactive", output="verified"
                )
            finally:
                close_job(job)

        record(
            "PTY prompt/input + separate diagnostic output",
            lambda: terminal_case(
                "acceptance-input",
                "printf 'READY\\n'; read answer; printf 'ANSWER=%s\\n' \"$answer\"; printf 'STDERR_MARK\\n' >&2",
                "acceptance-ok\n",
                marker="ANSWER=acceptance-ok",
            ),
        )
        record(
            "PTY nonzero exit + diagnostic shell",
            lambda: terminal_case(
                "acceptance-failure",
                "printf 'EXPECTED_FAILURE\\n' >&2; exit 7",
                status="failed",
                marker="EXPECTED_FAILURE",
            ),
        )
        record(
            "PTY Ctrl+C + durable failed result",
            lambda: terminal_case(
                "acceptance-interrupt", "printf 'READY\\n'; sleep 30", "\x03", "failed"
            ),
        )

    report = dict(
        time=datetime.now(timezone.utc).isoformat(),
        mode="ssh",
        host=plan["host"]["name"],
        transport="system OpenSSH, verified host key",
        results=results,
    )
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    raise SystemExit(any(r["result"] != "pass" for r in results))


if __name__ == "__main__":
    main()
