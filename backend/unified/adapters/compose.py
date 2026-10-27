from .. import ssh
from ..models import ComposeSettings
from .contracts import (
    ConfigField,
    Descriptor,
    JobContext,
    ServiceResult,
    SERVICE_ACTIONS,
)


class ComposeAdapter:
    descriptor = Descriptor(
        "compose",
        "service",
        "Docker Compose",
        SERVICE_ACTIONS,
        (ConfigField("compose_dir", "Compose 專案目錄", "/opt/stacks/"),),
    )

    def __init__(self, config):
        self.config = config

    def validate(self, settings):
        return ComposeSettings.model_validate(settings).model_dump()

    def identity(self, settings):
        return settings["compose_dir"]

    async def execute(self, host, service, action, context: JobContext):
        status, version = await ssh.operate(
            self.config, service["settings"], host, action, context.log
        )
        return ServiceResult(status, version)
