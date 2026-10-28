import os
from dataclasses import dataclass
from pathlib import Path

DEMO_TOKEN = "unified-demo-token-local-only-2026"


@dataclass(frozen=True)
class Config:
    mode: str = "ssh"
    token: str = ""
    data_dir: Path = Path("/data")
    ssh_dir: Path = Path("/run/ssh")
    source_dir: Path = Path("/sources")
    webdav_url: str = ""
    webdav_user: str = ""
    webdav_password: str = ""
    demo_delay: float = 1.0
    job_timeout: int = 1800
    # Optional legacy/custom mount; official definitions live elsewhere.
    plugin_catalog: Path = Path("/plugin-catalog")
    builtin_catalog: Path = Path(os.getenv("BUILTIN_PLUGINS", str(Path(__file__).resolve().parents[2] / "plugins")))

    @classmethod
    def from_env(cls):
        return cls(
            mode=os.getenv("UNIFIED_MODE", "ssh"),
            token=os.getenv("ADMIN_TOKEN", ""),
            data_dir=Path(os.getenv("DATA_DIR", "/data")),
            ssh_dir=Path(os.getenv("SSH_DIR", "/run/ssh")),
            source_dir=Path(os.getenv("SOURCE_DIR", "/sources")),
            webdav_url=os.getenv("WEBDAV_URL", ""),
            webdav_user=os.getenv("WEBDAV_USER", ""),
            webdav_password=os.getenv("WEBDAV_PASSWORD", ""),
            plugin_catalog=Path(os.getenv("PLUGIN_CATALOG", str(cls.plugin_catalog))),
            builtin_catalog=Path(os.getenv("BUILTIN_PLUGINS", str(cls.builtin_catalog))),
            demo_delay=float(os.getenv("DEMO_DELAY", "1")),
        )

    def validate(self):
        if self.mode not in ("demo", "ssh"):
            raise ValueError("UNIFIED_MODE must be demo or ssh")
        if len(self.token) < 32 or (self.mode == "ssh" and self.token == DEMO_TOKEN):
            raise ValueError("Set a unique ADMIN_TOKEN with at least 32 characters")
        self.data_dir.mkdir(parents=True, exist_ok=True)
