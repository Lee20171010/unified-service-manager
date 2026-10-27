"""Real SSH adapter: fixed Compose verbs, verified host keys, no client-side SSH."""

import asyncio
import json
import shlex
import asyncssh


def connect(config, host):
    key = config.ssh_dir / host["key"]
    known = config.ssh_dir / "known_hosts"
    if not key.is_file() or not known.is_file():
        raise RuntimeError("SSH_CONFIG_MISSING: 請掛載指定私鑰與經驗證的 known_hosts")
    return asyncssh.connect(
        host["address"],
        port=host["port"],
        username=host["username"],
        client_keys=[str(key)],
        known_hosts=str(known),
        agent_path=None,
        connect_timeout=15,
        login_timeout=15,
        keepalive_interval=30,
    )


def compose_command(service, action):
    verbs = {
        "refresh": "ps --all --format json",
        "start": "up -d",
        "stop": "stop",
        "restart": "restart",
        "upgrade": "pull && docker compose --ansi never up -d",
    }
    return f"cd -- {shlex.quote(service['compose_dir'])} && docker compose --ansi never {verbs[action]}"


def parse_status(text):
    try:
        value = json.loads(text)
        rows = value if isinstance(value, list) else [value]
    except json.JSONDecodeError:
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    states = [str(r.get("State", "")).lower() for r in rows]
    healthy = all(str(r.get("Health", "")).lower() in ("", "healthy") for r in rows)
    status = (
        "online"
        if states and all(s == "running" for s in states) and healthy
        else (
            "stopped"
            if not states or all(s in ("exited", "created", "dead") for s in states)
            else "degraded"
        )
    )
    images = sorted({r.get("Image", "") for r in rows if r.get("Image")})
    return status, ", ".join(images) or "尚無容器"


async def operate(config, service, host, action, log):
    async with connect(config, host) as connection:
        command = compose_command(service, action)
        await log("stdout", f"{host['name']} · docker compose {action}\n")
        async with connection.create_process(command) as process:

            async def pump(reader, stream):
                while chunk := await reader.read(4096):
                    await log(stream, chunk)

            await asyncio.gather(
                pump(process.stdout, "stdout"), pump(process.stderr, "stderr")
            )
            result = await process.wait()
            if result.exit_status != 0:
                raise RuntimeError(
                    f"COMPOSE_EXIT_{result.exit_status}: 操作未成功，請查看完整輸出並重新整理狀態"
                )
        result = await connection.run(
            compose_command(service, "refresh"), check=True, timeout=30
        )
        return parse_status(result.stdout)
