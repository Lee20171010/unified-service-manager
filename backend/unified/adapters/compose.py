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

    def __init__(self, config, manifest=None):
        self.config = config
        if manifest is not None:
            self.descriptor = Descriptor(
                manifest["id"], "service", manifest["label"],
                tuple(manifest["operations"]),
                tuple(ConfigField(**f) for f in manifest["fields"]),
                version=manifest["version"],
            )

    def validate(self, settings):
        values = {f.name: f.initial for f in self.descriptor.fields} | settings
        result = ComposeSettings.model_validate(values).model_dump()
        field = self.descriptor.fields[0]
        if field.choices and result["compose_dir"] not in field.choices:
            raise ValueError("Invalid Compose directory choice")
        return result

    def identity(self, settings):
        return settings["compose_dir"]

    async def execute(self, host, service, action, context: JobContext):
        status, version = await ssh.operate(
            self.config, service["settings"], host, action, context.log
        )
        return ServiceResult(status, version)
