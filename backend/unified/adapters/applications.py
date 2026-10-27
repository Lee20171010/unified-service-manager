from dataclasses import dataclass
from pathlib import Path
from .contracts import Descriptor, JobContext


@dataclass(frozen=True)
class DirectorySnapshot:
    """Unified ZIP v1 configuration directory; native export formats need their own hooks."""

    descriptor: Descriptor
    directory: str

    def source(self, config):
        return config.source_dir / self.directory

    async def prepare(self, action: str, context: JobContext):
        await context.log(
            "stdout", f"{self.descriptor.label}: configuration snapshot {action}\n"
        )

    def validate_restore(self, staged: Path):
        # Common archive/path/checksum validation runs before this application hook.
        pass


MAGPIE = DirectorySnapshot(
    Descriptor("magpie", "backup", "Magpie", ("backup", "restore")), "magpie"
)
SERVERBOX = DirectorySnapshot(
    Descriptor("serverbox", "backup", "Flutter ServerBox", ("backup", "restore")),
    "serverbox",
)
