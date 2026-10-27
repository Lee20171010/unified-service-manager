"""Managed resource adapters: validated npm scopes and administrator command recipes."""

import asyncio
import json
import re
import shlex
from pathlib import PurePosixPath
from . import ssh
from .adapters.contracts import ConfigField, Descriptor, ServiceResult
from .adapters.demo import simulate

PACKAGE = re.compile(r"(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*")
EXACT = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?")


def path(value):
    if (
        not value.startswith("/")
        or ".." in PurePosixPath(value).parts
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("請使用不含 .. 的絕對路徑")
    return str(PurePosixPath(value))


def npm_command(s, action, version=None):
    # Absolute Node/npm paths select the remote runtime; never infer central HOME.
    args = [s["node"], s["npm"]]
    scope = ["--global"] if s["scope"] == "user" else []
    if action == "resolve":
        args += ["view", s["package_name"] + "@" + s["version"], "version", "--json"]
    elif action == "refresh":
        # Read only one package.json, never npm config or credential files.
        location = (
            PurePosixPath(s["directory"])
            / ("lib/node_modules" if s["scope"] == "user" else "node_modules")
            / s["package_name"]
            / "package.json"
        )
        script = "const fs=require('fs');try{let p=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));console.log(p.version)}catch(e){if(e.code==='ENOENT')console.log('absent');else{console.error('PACKAGE_READ_FAILED');process.exit(1)}}"
        args = [s["node"], "-e", script, str(location)]
    elif action in ("install", "upgrade"):
        if not version or not EXACT.fullmatch(version):
            raise ValueError("Exact version must be resolved before installation")
        args += [
            "install",
            *scope,
            "--prefix",
            s["directory"],
            "--save-exact",
            "--no-audit",
            "--no-fund",
            s["package_name"] + "@" + version,
        ]
    elif action == "uninstall":
        args += [
            "uninstall",
            *scope,
            "--prefix",
            s["directory"],
            "--no-audit",
            "--no-fund",
            s["package_name"],
        ]
    elif action == "doctor":
        args = [s["node"], "--version"]
    else:
        raise ValueError("Unsupported npm operation")
    return (
        "env "
        + shlex.quote(
            "PATH="
            + str(PurePosixPath(s["node"]).parent)
            + ":/usr/local/bin:/usr/bin:/bin"
        )
        + " "
        + shlex.join(args)
    )


async def capture(config, host, command):
    async with asyncio.timeout(60):
        async with ssh.connect(config, host) as conn:
            async with conn.create_process(command) as process:

                async def bounded(reader):
                    parts = []
                    length = 0
                    while chunk := await reader.read(4096):
                        length += len(chunk.encode())
                        if length > 16384:
                            raise RuntimeError(
                                "REMOTE_RESULT_LIMIT: observation exceeds 16 KiB"
                            )
                        parts.append(chunk)
                    return "".join(parts)

                out, _ = await asyncio.gather(
                    bounded(process.stdout), bounded(process.stderr)
                )
                result = await process.wait()
                if result.exit_status != 0:
                    raise RuntimeError(
                        "REMOTE_CHECK_FAILED: 請檢查執行路徑、帳號及網路"
                    )
                return out.strip()


async def execute_command(config, host, command, context):
    async with ssh.connect(config, host) as conn:
        async with conn.create_process(command) as process:

            async def pump(reader, stream):
                while chunk := await reader.read(4096):
                    await context.log(stream, chunk)

            await asyncio.gather(
                pump(process.stdout, "stdout"), pump(process.stderr, "stderr")
            )
            result = await process.wait()
            if result.exit_status != 0:
                raise RuntimeError(
                    f"COMMAND_EXIT_{result.exit_status}: 查看輸出並重新檢查狀態"
                )


class ResourceAdapter:
    def __init__(self, config, manifest, sessions=None):
        self.config, self.manifest, self.sessions = config, manifest, sessions
        self.descriptor = Descriptor(
            manifest["id"],
            "service",
            manifest["label"],
            tuple(manifest["operations"]),
            tuple(ConfigField(**f) for f in manifest.get("fields", [])),
            version=manifest["version"],
            resource_kind=manifest.get("resource_kind", "service"),
        )

    def validate(self, settings):
        fields = {f.name: f for f in self.descriptor.fields}
        if set(settings) - set(fields):
            raise ValueError("Unknown resource configuration field")
        result = {k: settings.get(k, f.initial).strip() for k, f in fields.items()}
        for k, f in fields.items():
            if (
                (f.required and not result[k])
                or len(result[k]) > 16384
                or "\x00" in result[k]
            ):
                raise ValueError("Invalid configuration: " + k)
            if f.choices and result[k] not in f.choices:
                raise ValueError("Invalid choice: " + k)
        if self.manifest["driver"] == "npm":
            if (
                not PACKAGE.fullmatch(result["package_name"])
                or len(result["package_name"]) > 214
            ):
                raise ValueError("填寫 npm 套件名稱，版本請填在版本欄位")
            if (
                self.manifest.get("package_name")
                and result["package_name"] != self.manifest["package_name"]
            ):
                raise ValueError("Dedicated integration package mismatch")
            for k in ("directory", "node", "npm"):
                result[k] = path(result[k])
            if result["directory"] == "/":
                raise ValueError("Installation directory cannot be /")
            if result["version"] != "latest" and not EXACT.fullmatch(result["version"]):
                raise ValueError("版本須為 latest 或完整版本號")
        else:
            result["directory"] = path(result["directory"])
        return result

    def identity(self, settings):
        if self.manifest["driver"] == "npm":
            return json.dumps(
                [settings[k] for k in ("node", "scope", "directory", "package_name")]
            )
        return settings.get("identity", settings["directory"])

    async def resolve(self, host, settings):
        if self.config.mode == "demo":
            return (
                settings["version"] if settings["version"] != "latest" else "1.0.0-demo"
            )
        version = json.loads(
            await capture(self.config, host, npm_command(settings, "resolve"))
        )
        # npm releases emit either a scalar or a list for a single version.
        # Multiple matches cannot supply one unambiguous installation target.
        if isinstance(version, list) and len(version) == 1:
            version = version[0]
        if not isinstance(version, str) or not EXACT.fullmatch(version):
            raise ValueError(
                "VERSION_RESOLUTION: registry did not return an exact version"
            )
        return version

    def command(self, s, action):
        command = self.manifest.get("commands", {}).get(action) or s.get(
            "cmd_" + action
        )
        if not command:
            raise ValueError("請設定此操作的命令：" + action)
        # Commands are saved administrator-authored recipes. Values bind as env, not shell source.
        env = " ".join(
            shlex.quote("UNIFIED_" + k.upper() + "=" + v)
            for k, v in s.items()
            if not k.startswith("cmd_")
        )
        return (
            "cd -- "
            + shlex.quote(s["directory"])
            + " && env "
            + env
            + " sh -c "
            + shlex.quote(command)
        )

    async def execute(self, host, service, action, context):
        s = service["settings"]
        if self.config.mode == "demo":
            if self.sessions:
                await self.sessions.demo(context, host, simulate)
            else:
                await simulate(self.config, context)
            if self.manifest["driver"] == "npm":
                v = (
                    "absent"
                    if action == "uninstall"
                    else service.get(
                        "resolved_version", service.get("version", "unknown")
                    )
                )
                return ServiceResult(
                    (
                        "stopped"
                        if v == "absent"
                        else "online" if v not in ("unknown", "尚未讀取") else "unknown"
                    ),
                    v,
                )
            return ServiceResult(
                "stopped" if action == "stop" else "online",
                service.get("version", "unknown"),
            )
        if self.manifest["driver"] == "npm":
            if action != "refresh":
                command = npm_command(s, action, service.get("resolved_version"))
                if self.sessions:
                    await self.sessions.execute(context, host, command)
                else:
                    await execute_command(self.config, host, command, context)
            version = await capture(self.config, host, npm_command(s, "refresh"))
            if version != "absent" and not EXACT.fullmatch(version):
                raise ValueError("PACKAGE_VERSION: unexpected package version")
            if (
                action in ("install", "upgrade")
                and version != service["resolved_version"]
            ):
                raise RuntimeError(
                    "PACKAGE_VERSION_MISMATCH: installed version differs from requested version"
                )
            return ServiceResult(
                "stopped" if version == "absent" else "online", version
            )
        if action == "refresh":
            text = await capture(self.config, host, self.command(s, "refresh"))
            await context.log("stdout", text + "\n")
            return parse_observation(text, service.get("version", "unknown"))
        command = self.command(s, action)
        if self.sessions:
            await self.sessions.execute(context, host, command)
        else:
            await execute_command(self.config, host, command, context)
        if s.get("cmd_refresh") or self.manifest.get("commands", {}).get("refresh"):
            return parse_observation(
                await capture(self.config, host, self.command(s, "refresh")),
                service.get("version", "unknown"),
            )
        return ServiceResult("unknown", service.get("version", "unknown"))


def parse_observation(text, version):
    try:
        value = json.loads(text)
    except ValueError:
        value = None
    if isinstance(value, dict):
        return ServiceResult(
            value.get("status", "unknown"), str(value.get("version", version))[:500]
        )
    statuses = {
        "active": "online",
        "running": "online",
        "online": "online",
        "inactive": "stopped",
        "stopped": "stopped",
        "failed": "degraded",
    }
    return ServiceResult(statuses.get(text.strip(), "unknown"), version)
