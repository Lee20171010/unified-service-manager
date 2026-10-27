import asyncio
from .compose import ComposeAdapter
from .contracts import ServiceResult


async def simulate(config, context):
    steps = (
        "Connecting to target…",
        "Reading configuration…",
        "Preparing operation…",
        "Applying operation…",
        "Checking result…",
        "Verification complete.",
    )
    for index, step in enumerate(steps):
        await asyncio.sleep(
            config.demo_delay * (5 if context.scenario == "long" else 1)
        )
        if context.scenario == "fail" and index == 3:
            raise RuntimeError("DEMO_TIMEOUT: 模擬連線逾時，可選正常情境重新執行")
        await context.log("stdout", "[DEMO] " + step + "\n")
        await context.progress(int((index + 1) / len(steps) * 95))


class DemoComposeAdapter(ComposeAdapter):
    async def execute(self, host, service, action, context):
        await simulate(self.config, context)
        status = (
            "stopped"
            if action == "stop"
            else (
                "online"
                if action != "refresh"
                else "online" if service["status"] == "unknown" else service["status"]
            )
        )
        return ServiceResult(
            status, "demo-updated" if action == "upgrade" else service["version"]
        )
