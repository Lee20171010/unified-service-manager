#!/usr/bin/env python3
"""Exercise the shipped OMV Compose using disposable directories and no hosts."""

import json
import runpy
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


repo = Path(__file__).resolve().parents[1]
VERSION = runpy.run_path(str(repo / "backend/unified/__init__.py"))["__version__"]
image = "unified-application:" + VERSION


def run(*args, env=None):
    return subprocess.check_output(args, env=env, text=True, stderr=subprocess.STDOUT, timeout=180).strip()


def main():
    with tempfile.TemporaryDirectory(prefix="unified-omv-test-") as temporary:
        root = Path(temporary)
        shutil.copyfile(repo / "deploy/omv/compose.yaml", root / "compose.yaml")
        token = secrets.token_hex(32)
        env = dict(os.environ, IMAGE_TAG=VERSION, ADMIN_TOKEN=token, PORT="0", BIND_ADDRESS="127.0.0.1",
                   WEBDAV_URL="", WEBDAV_USER="", WEBDAV_PASSWORD="")
        compose = ["docker", "compose", "-p", "unified-storage-test-" + secrets.token_hex(4),
                   "-f", str(root / "compose.yaml")]

        def up():
            run(*compose, "up", "-d", "--force-recreate", "--pull", "never", env=env)
            address = run(*compose, "port", "web", "80", env=env)
            base = "http://" + address
            for _ in range(60):
                try:
                    with urllib.request.urlopen(base + "/healthz", timeout=2) as response:
                        if response.status == 200:
                            return base
                except (OSError, urllib.error.URLError):
                    time.sleep(0.5)
            raise AssertionError("Fixture stack did not become healthy")

        def request(base, path, body=None, authenticated=True):
            headers = {"Authorization": "Bearer " + token} if authenticated else {}
            if body is not None:
                headers["Content-Type"] = "application/json"
            req = urllib.request.Request(base + "/api/v1" + path, headers=headers,
                                         data=None if body is None else json.dumps(body).encode())
            with urllib.request.urlopen(req, timeout=5) as response:
                return json.load(response)

        try:
            assert not any((root / name).exists() for name in ("data", "ssh", "sources"))
            base = up()
            with urllib.request.urlopen(base, timeout=5) as page:
                assert page.headers["X-Frame-Options"] == "DENY"
                assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]
            for name in ("data", "sources"):
                # Host user cannot traverse private app directories; inspect through Docker.
                assert run("docker", "run", "--rm", "--network", "none", "--user", "0:0",
                           "-v", f"{root / name}:/fixture:ro", "--entrypoint", "python", image, "-c",
                           "import os; s=os.stat('/fixture'); print(s.st_uid,s.st_gid,oct(s.st_mode & 0o777))") == "10001 10001 0o700"
            # docker exec defaults to the image user (root); inspect the actual server.
            status = json.loads(run(*compose, "exec", "-T", "application", "python", "-c",
                "import json; from pathlib import Path; pid=Path('/proc/1/task/1/children').read_text().split()[0]; "
                "print(json.dumps(dict(line.split(':',1) for line in Path('/proc/'+pid+'/status').read_text().splitlines() if ':' in line)))", env=env))
            assert set(status["Uid"].split()) == {"10001"}
            assert set(status["Gid"].split()) == {"10001"}
            assert all(int(status[key].strip(),16) == 0 for key in ("CapEff", "CapPrm", "CapBnd", "CapInh", "CapAmb"))
            assert status["NoNewPrivs"].strip() == "1"
            assert request(base, "/info")["version"] == VERSION
            # The SSH directory is mounted read-only even for a root exec.
            run(*compose, "exec", "-T", "application", "python", "-c",
                "import errno; from pathlib import Path\ntry: Path('/run/ssh/probe').touch()\nexcept OSError as e: assert e.errno == errno.EROFS\nelse: raise AssertionError('SSH mount is writable')", env=env)
            snapshot = request(base, "/snapshot")
            assert not snapshot["hosts"] and not snapshot["jobs"]
            assert not any(plugin.get("installed") for plugin in request(base, "/plugins"))
            try:
                request(base, "/snapshot", authenticated=False)
                raise AssertionError("Unauthenticated snapshot succeeded")
            except urllib.error.HTTPError as error:
                assert error.code == 401
            document = dict(id="storage-fixture", version="1.0.0", interface_version=1,
                            label="Storage fixture", category="service-management", driver="commands",
                            resource_kind="tool", operations=["run"],
                            fields=[dict(name="directory", label="Directory", initial="/opt")],
                            commands={"run": "true"})
            request(base, "/plugin-documents", {"manifest": document})
            # A populated SSH directory and root-owned file must survive the next init untouched.
            run("docker", "run", "--rm", "--network", "none", "--user", "0:0",
                "-v", f"{root / 'ssh'}:/fixture", "--entrypoint", "python", image, "-c",
                "from pathlib import Path; p=Path('/fixture/key-fixture'); p.write_text('fixture'); p.chmod(0o600)")
            base = up()
            assert request(base, "/plugins/storage-fixture/manifest") == document
            assert run("docker", "run", "--rm", "--network", "none", "--user", "0:0",
                       "-v", f"{root / 'ssh'}:/fixture:ro", "--entrypoint", "python", image, "-c",
                       "from pathlib import Path; p=Path('/fixture/key-fixture'); s=p.stat(); print(s.st_uid,oct(s.st_mode & 0o777),p.read_text())") == "0 0o600 fixture"
            # Verify SIGTERM reaches the server through the entrypoint exec chain.
            run(*compose, "stop", "-t", "10", "application", env=env)
            container = run(*compose, "ps", "-a", "-q", "application", env=env)
            # Uvicorn completes cleanup and then re-raises SIGTERM (128 + 15).
            assert run("docker", "inspect", "--format", "{{.State.ExitCode}}", container) in {"0", "143"}
            assert "Application shutdown complete." in run(*compose, "logs", "--no-color", "application", env=env)
            print("PASS: automatic directory setup; server UID/GID 10001 and zero capabilities; read-only SSH; authentication; no activated plugins; recreation persistence; existing SSH fixture; graceful shutdown")
        finally:
            run(*compose, "down", "-v", env=env)
            run("docker", "run", "--rm", "--network", "none", "--user", "0:0",
                "-v", f"{root}:/fixture", "--entrypoint", "python", image, "-c",
                "import shutil; [shutil.rmtree('/fixture/'+name, ignore_errors=True) for name in ('data','ssh','sources')]")


if __name__ == "__main__":
    main()
