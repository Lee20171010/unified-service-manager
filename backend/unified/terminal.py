"""Separate transient terminal gateway; managed jobs never accept shell input."""

import asyncio
import json
from contextlib import suppress
from fastapi import WebSocket, WebSocketDisconnect
from .ssh import connect


async def terminal_session(socket: WebSocket, app, host):
    if app.config.mode == "demo":
        await socket.send_json(
            {
                "type": "output",
                "text": f"DEMO Terminal Gateway → {host['name']}\nType help for demo commands.\n$ ",
            }
        )
        while True:
            msg = await asyncio.wait_for(socket.receive_json(), 900)
            if msg.get("type") != "input":
                continue
            command = str(msg.get("data", "")).strip()
            if command == "exit":
                return
            responses = {
                "help": "help, hostname, whoami, pwd, docker ps, exit",
                "hostname": host["name"],
                "whoami": host["username"],
                "pwd": "/home/" + host["username"],
                "docker ps": "\n".join(
                    s["name"] + "  " + s["status"]
                    for s in app.store.list("services")
                    if s["host"] == host["id"]
                ),
            }
            await socket.send_json(
                {
                    "type": "output",
                    "text": command
                    + "\n"
                    + responses.get(command, "Demo: command not simulated.")
                    + "\n$ ",
                }
            )
    else:
        async with connect(app.config, host) as connection:
            async with connection.create_process(
                term_type="dumb", term_size=(100, 30)
            ) as process:

                async def upstream():
                    while True:
                        msg = await asyncio.wait_for(socket.receive_json(), 900)
                        if msg.get("type") == "input":
                            data = str(msg.get("data", ""))
                            if len(data) > 8192:
                                raise ValueError("Input too large")
                            process.stdin.write(data)
                        elif msg.get("type") == "resize":
                            process.change_terminal_size(
                                max(20, min(240, int(msg.get("cols", 100)))),
                                max(5, min(100, int(msg.get("rows", 30)))),
                            )

                async def downstream():
                    while chunk := await process.stdout.read(4096):
                        await socket.send_json({"type": "output", "text": chunk})

                tasks = [
                    asyncio.create_task(upstream()),
                    asyncio.create_task(downstream()),
                ]
                try:
                    done, _ = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        task.result()
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)


async def serve_terminal(socket, app, host_id):
    # Token is the first frame, never a query-string credential.
    await socket.accept()
    try:
        import secrets

        auth = await asyncio.wait_for(socket.receive_json(), 10)
        if not secrets.compare_digest(str(auth.get("token", "")), app.config.token):
            await socket.close(code=4401)
            return
        host = app.store.get("hosts", host_id)
        await terminal_session(socket, app, host)
    except WebSocketDisconnect:
        return
    except Exception as exc:
        with suppress(Exception):
            await socket.send_json(
                {
                    "type": "error",
                    "text": (
                        str(exc)
                        if isinstance(exc, RuntimeError)
                        else type(exc).__name__
                    ),
                }
            )
    finally:
        with suppress(Exception):
            await socket.close()
