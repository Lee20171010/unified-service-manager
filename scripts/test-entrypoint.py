#!/usr/bin/env python3
"""Check image entrypoint behavior without network or application operations."""

import json
import runpy
from pathlib import Path
import subprocess
import tempfile


VERSION = runpy.run_path(str(Path(__file__).resolve().parents[1] / "backend/unified/__init__.py"))["__version__"]
IMAGE = "unified-application:" + VERSION


def run(options, command):
    return subprocess.run(["docker", "run", "--rm", "--network", "none", *options,
                           IMAGE, *command], text=True, capture_output=True, timeout=30)


probe = ["python", "-c", "import json,os,sys; print(json.dumps([os.getuid(),os.getgid(),sys.argv[1:]]))",
         "argument with spaces", "literal;$HOME"]
normal = run([], probe)
assert normal.returncode == 0, normal.stderr
assert json.loads(normal.stdout) == [10001, 10001, ["argument with spaces", "literal;$HOME"]]

explicit = run(["--user", "10001:10001", "--read-only", "--cap-drop", "ALL"], probe)
assert explicit.returncode == 0, explicit.stderr
assert json.loads(explicit.stdout) == [10001, 10001, ["argument with spaces", "literal;$HOME"]]

with tempfile.TemporaryDirectory(prefix="unified-entrypoint-test-") as root:
    directory = Path(root) / "readonly-data"
    denied = run(["-v", f"{directory}:/data:ro"], ["python", "-c", "print('SERVER_STARTED')"])
    assert denied.returncode != 0
    assert "SERVER_STARTED" not in denied.stdout
    assert "Read-only file system" in denied.stderr
    assert not list(directory.iterdir())

print("PASS: root startup drops user; argv preserved; stdout stays clean; explicit non-root/read-only supported; failed initialization prevents program start")
