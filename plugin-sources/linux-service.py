"""Embedded into interface-v1 JSON recipes; runs on the selected Linux SSH host."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

program, action = sys.argv[1:3]
SUPPORTED = {"opencode", "openchamber", "hermes", "chatgpt"}

def fail(message):
    print("PLUGIN_CHECK: " + message, file=sys.stderr)
    raise SystemExit(1)

def capture(args):
    result = subprocess.run(args, text=True, capture_output=True, timeout=30)
    if result.returncode:
        fail("Command failed: " + args[0] + "; check permissions and configured paths")
    return result.stdout.strip()

def run(args):
    # Inherit the Job Console's PTY/stdin and output. Credentials never enter argv here.
    result = subprocess.run(args)
    if result.returncode:
        raise SystemExit(result.returncode if result.returncode > 0 else 1)

def binary(name):
    if "/" in name:
        candidate = Path(name)
        if not candidate.is_absolute() or not candidate.is_file() or not os.access(candidate, os.X_OK):
            fail("Executable path is unavailable; set the executable parameter")
        return str(candidate)
    located = shutil.which(name)
    if located:
        return located
    home = Path.home()
    roots = [home / ".local/bin", home / ".opencode/bin"]
    roots += sorted((home / ".nvm/versions/node").glob("*/bin"))
    candidates = [p / name for p in roots if (p / name).is_file() and os.access(p / name, os.X_OK)]
    if len(candidates) != 1:
        fail("Executable not uniquely found; set its absolute path")
    return str(candidates[0])

if program not in SUPPORTED or action not in {"refresh", "start", "stop", "restart", "upgrade", "doctor"}:
    fail("Unsupported operation")
unit = os.environ["UNIFIED_UNIT"]
scope = os.environ["UNIFIED_SERVICE_SCOPE"]
if not re.fullmatch(r"[A-Za-z0-9_@.:-]+\.service", unit) or unit.startswith("-"):
    fail("Set one exact .service unit name; patterns are not supported")
if scope not in {"user", "system"}:
    fail("Invalid systemd scope")
exe = binary(os.environ["UNIFIED_BINARY"])
os.environ["PATH"] = str(Path(exe).parent) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")
systemctl = binary("systemctl")
control = [systemctl] + (["--user"] if scope == "user" else [])

def property_value(name):
    return capture(control + ["show", "--property=" + name, "--value", "--", unit])

def state():
    if property_value("LoadState") != "loaded":
        fail("Configured systemd unit is not installed; select the existing unit")
    active = property_value("ActiveState")
    return {"active": "online", "inactive": "stopped", "failed": "degraded"}.get(active, "unknown")

def version():
    if program == "chatgpt":
        text = capture([binary("dpkg-query"), "-W", "-f=${Version}", "chatgpt"])
    else:
        text = capture([exe, "--version"])
    match = re.search(r"\b\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?\b", text)
    return match.group() if match else "unknown"

def npm_installation():
    # Support npm's global layout only; never infer a different installation's prefix.
    for root in Path(exe).resolve().parents:
        manifest = root / "package.json"
        if manifest.is_file() and root.name == "web" and root.parent.name == "@openchamber":
            data = json.loads(manifest.read_text())
            if data.get("name") != "@openchamber/web":
                continue
            modules = root.parent.parent
            if modules.name != "node_modules" or modules.parent.name != "lib":
                fail("OpenChamber default upgrade supports an npm global installation")
            prefix = modules.parent.parent
            return binary("npm"), str(prefix)
    fail("OpenChamber npm installation not found; select the installed CLI or customize upgrade")

before = state()
if action == "refresh":
    print(json.dumps({"status": before, "version": version()}))
elif action == "doctor":
    print("Executable available; systemd unit loaded; scope=" + scope)
    print("Version: " + version())
    if program == "openchamber":
        npm_installation()
        print("npm global installation confirmed")
    elif program == "chatgpt":
        binary("apt-get")
        print("APT upgrade requires a configured package source and package-manager privileges")
    elif program == "hermes":
        help_text = capture([exe, "update", "--help"])
        if "--no-gateway-restart" not in help_text:
            fail("This Hermes version cannot defer gateway restarts; customize the upgrade operation")
        print("Updater supports deferring gateway restarts")
elif action in {"start", "stop", "restart"}:
    run(control + [action, "--", unit])
    after = state()
    expected = "stopped" if action == "stop" else "online"
    if after != expected:
        fail("Service did not reach the requested state; inspect its host journal")
    print("Service state: " + after)
elif action == "upgrade":
    if program == "opencode":
        run([exe, "upgrade"])
    elif program == "hermes":
        if "--no-gateway-restart" not in capture([exe, "update", "--help"]):
            fail("This Hermes version cannot defer gateway restarts; customize upgrade")
        run([exe, "update", "--no-gateway-restart"])
    elif program == "openchamber":
        npm, prefix = npm_installation()
        target = os.environ.get("UNIFIED_VERSION", "latest")
        if target != "latest" and not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", target):
            fail("Use latest or one exact version")
        resolved = json.loads(capture([npm, "view", "@openchamber/web@" + target, "version", "--json"]))
        if isinstance(resolved, list) and len(resolved) == 1:
            resolved = resolved[0]
        if not isinstance(resolved, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", resolved):
            fail("Registry did not resolve one exact version")
        print("Installing @openchamber/web@" + resolved, flush=True)
        run([npm, "install", "--global", "--prefix", prefix, "--no-audit", "--no-fund", "@openchamber/web@" + resolved])
        if version() != resolved:
            fail("Installed OpenChamber version differs from the requested version")
    else:
        apt = [binary("apt-get"), "install", "--only-upgrade", "chatgpt"]
        # Keep the package-manager confirmation interactive in the Job Console.
        run(apt if os.geteuid() == 0 else [binary("sudo"), "-n", *apt])
    if before == "online":
        run(control + ["restart", "--", unit])
        if state() != "online":
            fail("Upgrade completed but the selected service did not restart")
    print("Installed version: " + version(), flush=True)
