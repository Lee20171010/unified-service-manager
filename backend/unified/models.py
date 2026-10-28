import re
from pathlib import PurePosixPath
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class HostInput(Input):
    name: str = Field(min_length=1, max_length=60)
    address: str = Field(min_length=1, max_length=253)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(default="unified", pattern=r"^[a-zA-Z_][a-zA-Z0-9_-]{0,31}$")
    key: str = Field(
        default="id_ed25519", pattern=r"^[a-zA-Z0-9_-][a-zA-Z0-9_.-]{0,63}$"
    )
    platform: str = Field(default="Linux", max_length=60)

    @field_validator("address")
    @classmethod
    def address_format(cls, v):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.:-]*", v):
            raise ValueError("Use an IP address or DNS hostname")
        return v


class ComposeSettings(Input):
    compose_dir: str = Field(min_length=2, max_length=500)

    @field_validator("compose_dir")
    @classmethod
    def absolute_path(cls, v):
        if (
            not v.startswith("/")
            or ".." in PurePosixPath(v).parts
            or any(ord(c) < 32 for c in v)
        ):
            raise ValueError(
                "Use an absolute Compose project directory without traversal"
            )
        return str(PurePosixPath(v))


class ServiceInput(Input):
    name: str = Field(min_length=1, max_length=80)
    host: str
    adapter: str = Field(default="compose", pattern=r"^[a-z][a-z0-9-]{0,63}$")
    settings: dict[str, str] = Field(default_factory=dict, max_length=24)
    compose_dir: str | None = Field(default=None, max_length=500)


class Operation(Input):
    action: Literal["refresh", "start", "stop", "restart", "upgrade"]
    scenario: Literal["normal", "long", "fail"] = "normal"


class BackupInput(Input):
    client: str = Field(min_length=1, max_length=80)
    scenario: Literal["normal", "long", "fail"] = "normal"


class RestoreInput(Input):
    confirm: Literal[True]
    scenario: Literal["normal", "long", "fail"] = "normal"


class ResourceOperation(Input):
    action: Literal[
        "refresh",
        "start",
        "stop",
        "restart",
        "upgrade",
        "install",
        "uninstall",
        "doctor",
        "run",
        "register",
        "unregister",
        "verify",
    ]
    scenario: Literal["normal", "long", "fail"] = "normal"
    confirm: bool = False
    binding: str | None = None


class PluginOperation(Input):
    version: str | None = Field(default=None, max_length=100)
    checksum: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    action: Literal["install", "update", "enable", "disable", "remove", "rollback"]


class BindingInput(Input):
    parent: str
    register_command: str = Field(min_length=1, max_length=16384)
    unregister_command: str = Field(min_length=1, max_length=16384)
    verify_command: str = Field(default="", max_length=16384)


class SessionInput(Input):
    generation: str
    sequence: int = Field(ge=1)
    data: str = Field(default="", max_length=8192)
    close: bool = False
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class PluginDocument(Input):
    manifest: dict
