"""Server-owned foreground PTYs and transient post-job diagnostic shells.

Output while the operation runs is durable job output. Diagnostic output and raw
input stay in memory. A separate SSH process opens a fresh diagnostic shell on
that connection after the managed process exits, preserving its exit status.
"""

import asyncio
import secrets
from . import ssh


class JobSessions:
    def __init__(self, config):
        self.config = config
        self.sessions = {}

    def view(self, id):
        s = self.sessions.get(id)
        if not s:
            return {"phase": "closed", "generation": "", "output": "", "sequence": 0}
        return {k: s[k] for k in ("phase", "generation", "output", "sequence")}

    async def input(self, id, generation, sequence, text, close=False):
        s = self.sessions.get(id)
        if not s or generation != s["generation"] or s["phase"] == "closed":
            raise ValueError("SESSION_CLOSED: 重新開啟 Console 查看目前會話")
        if sequence != s["sequence"] + 1:
            raise ValueError("INPUT_SEQUENCE: 輸入未重送，請刷新會話")
        if len(text) > 8192:
            raise ValueError("Input too large")
        if s.get("demo"):
            s["sequence"] = sequence
            s["last"] = asyncio.get_running_loop().time()
            if close or text.strip() == "exit":
                s["phase"] = "closed"
            elif s["phase"] == "running":
                if text == "\x03":
                    s["interrupted"] = True
                else:
                    await s["log"]("stdout", "[DEMO] 前台程序收到輸入（內容不記錄）\n")
            else:
                commands = {
                    "pwd": "/home/" + s["host"]["username"],
                    "whoami": s["host"]["username"],
                    "hostname": s["host"]["name"],
                    "help": "DEMO: pwd, whoami, hostname, exit",
                }
                s["output"] = (
                    s["output"]
                    + commands.get(text.strip(), "DEMO: 輸入已收到，不執行真實命令")
                    + "\n$ "
                )[-200000:]
            return self.view(id)
        s["sequence"] = sequence
        s["last"] = asyncio.get_running_loop().time()
        if close:
            s["phase"] = "closed"
            s["process"].close()
            s["connection"].close()
        else:
            s["process"].stdin.write(text)
        return self.view(id)

    async def demo(self, context, host, simulate):
        self.prune()
        if len([s for s in self.sessions.values() if s["phase"] != "closed"]) >= 16:
            raise RuntimeError("SESSION_LIMIT: 請先結束其他排錯會話")
        s = dict(
            phase="running",
            generation=secrets.token_hex(16),
            sequence=0,
            output="",
            demo=True,
            log=context.log,
            host=host,
            interrupted=False,
            last=asyncio.get_running_loop().time(),
        )
        self.sessions[context.job_id] = s
        try:
            await simulate(self.config, context)
            if s["interrupted"] or s["phase"] == "closed":
                raise RuntimeError("DEMO_INTERRUPTED: 操作已中斷")
        finally:
            if s["phase"] != "closed":
                s.update(
                    phase="shell",
                    output="[DEMO 排錯 shell；輸入不執行真實指令]\n$ ",
                    last=asyncio.get_running_loop().time(),
                )
                s["task"] = asyncio.create_task(self._demo_idle(s))

    async def _demo_idle(self, s):
        try:
            while (
                s["phase"] != "closed"
                and asyncio.get_running_loop().time() - s["last"] < 900
            ):
                await asyncio.sleep(10)
        finally:
            s["phase"] = "closed"

    def prune(self):
        closed = [id for id, s in self.sessions.items() if s["phase"] == "closed"]
        for id in closed[:-32]:
            self.sessions.pop(id, None)

    async def execute(self, context, host, command):
        self.prune()
        if len([s for s in self.sessions.values() if s["phase"] != "closed"]) >= 16:
            raise RuntimeError("SESSION_LIMIT: 請先結束其他排錯會話")
        conn = await ssh.connect(self.config, host)
        s = None
        try:
            process = await conn.create_process(
                command, term_type="dumb", term_size=(100, 30)
            )
            s = dict(
                phase="running",
                generation=secrets.token_hex(16),
                output="",
                sequence=0,
                process=process,
                connection=conn,
                last=asyncio.get_running_loop().time(),
            )
            self.sessions[context.job_id] = s
            await context.log(
                "stdout", "[PTY · stdout/stderr 合併輸出；可輸入、Ctrl+C]\n"
            )

            async def pump(reader):
                while chunk := await reader.read(4096):
                    await context.log("stdout", chunk)

            await asyncio.gather(pump(process.stdout), pump(process.stderr))
            result = await process.wait()
            if s["phase"] != "closed":
                shell = await conn.create_process(term_type="dumb", term_size=(100, 30))
                s.update(
                    process=shell,
                    phase="shell",
                    output="\n[受管程序已退出。已開啟新的排錯 shell；不會改寫任務結果。]\n",
                    last=asyncio.get_running_loop().time(),
                )
                s["task"] = asyncio.create_task(self._shell(s))
            if result.exit_status != 0:
                raise RuntimeError(
                    f"COMMAND_EXIT_{result.exit_status}: 操作未成功，可在排錯 shell 檢查"
                )
        except BaseException:
            if not s or s["phase"] != "shell":
                conn.close()
                if s:
                    s["phase"] = "closed"
            raise

    async def _shell(self, s):
        async def output(reader):
            while chunk := await reader.read(4096):
                s["output"] = (s["output"] + chunk)[-200000:]

        async def idle():
            while asyncio.get_running_loop().time() - s["last"] < 900:
                await asyncio.sleep(10)

        tasks = [
            asyncio.create_task(output(s["process"].stdout)),
            asyncio.create_task(idle()),
        ]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            s["connection"].close()
            s["phase"] = "closed"

    async def close(self):
        tasks = []
        for s in self.sessions.values():
            if s.get("connection"):
                s["connection"].close()
            s["phase"] = "closed"
            if s.get("task"):
                s["task"].cancel()
                tasks.append(s["task"])
        await asyncio.gather(*tasks, return_exceptions=True)
