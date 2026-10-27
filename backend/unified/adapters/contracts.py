"""Adapter API v1: trusted, image-bundled implementations; no store/HTTP ownership."""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Awaitable, Callable, Protocol, Literal
from ..config import Config

SERVICE_ACTIONS = ("refresh", "start", "stop", "restart", "upgrade")


@dataclass(frozen=True)
class ConfigField:
    name: str
    label: str
    initial: str = ""
    required: bool = True
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Descriptor:
    id: str
    kind: Literal["service", "backup", "storage"]
    label: str
    operations: tuple[str, ...]
    fields: tuple[ConfigField, ...] = ()
    version: str = "1.0.0"
    interface_version: int = 1
    resource_kind: str = "service"

    def public(self):
        return asdict(self)


class AdapterError(RuntimeError):
    """Only credential-free messages may cross the job error boundary."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class JobContext:
    job_id: str
    scenario: str
    log: Callable[[str, str], Awaitable[None]]
    progress: Callable[[int], Awaitable[None]]


@dataclass(frozen=True)
class ServiceResult:
    status: str
    version: str

    def __post_init__(self):
        if self.status not in ("online", "stopped", "degraded", "unknown"):
            raise AdapterError("ADAPTER_RESULT", "無效的服務狀態")


class ServiceAdapter(Protocol):
    descriptor: Descriptor

    def validate(self, settings: dict[str, str]) -> dict[str, str]: ...
    def identity(self, settings: dict[str, str]) -> str: ...
    async def execute(
        self, host: dict, service: dict, action: str, context: JobContext
    ) -> ServiceResult: ...


class BackupApplication(Protocol):
    descriptor: Descriptor

    def source(self, config: Config) -> Path: ...
    async def prepare(self, action: str, context: JobContext) -> None: ...
    def validate_restore(self, staged: Path) -> None: ...


class BackupStorage(Protocol):
    descriptor: Descriptor

    def validate(self) -> None: ...
    async def upload(self, name: str, path: Path) -> None: ...
    async def download(self, name: str, path: Path) -> None: ...
