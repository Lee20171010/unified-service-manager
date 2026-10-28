"""Official GitHub metadata cache and checksum-pinned package downloads."""
import hashlib
import json
import os
import re
import tempfile
import threading
import time
from pathlib import Path
import httpx

BASE_URL = "https://raw.githubusercontent.com/Lee20171010/unified-service-manager/main/catalog/"
BUILTIN_IDS = frozenset({"compose", "npm-packages", "webdav"})
INDEX_LIMIT = 262144
PACKAGE_LIMIT = 131072


def atomic_write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".catalog-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        Path(name).replace(path)
    finally:
        Path(name).unlink(missing_ok=True)


def validate_index(document):
    from .plugins import ID, VERSION
    if not isinstance(document, dict) or set(document) != {"schema_version", "plugins"} or document["schema_version"] != 1:
        raise ValueError("CATALOG_INVALID: invalid index")
    entries = document["plugins"]
    if not isinstance(entries, list) or len(entries) > 200:
        raise ValueError("CATALOG_INVALID: too many entries")
    found = {}
    for p in entries:
        keys = {"id", "label", "version", "category", "description", "sha256", "hosts"}
        if not isinstance(p, dict) or set(p) != keys:
            raise ValueError("CATALOG_INVALID: invalid metadata")
        if any(not isinstance(p[k], str) or "\0" in p[k] for k in keys - {"hosts"}):
            raise ValueError("CATALOG_INVALID: invalid text")
        if (not ID.fullmatch(p["id"]) or p["id"] in found or p["id"] in BUILTIN_IDS
                or not VERSION.fullmatch(p["version"]) or not re.fullmatch(r"[a-f0-9]{64}", p["sha256"])
                or not 1 <= len(p["label"]) <= 100 or len(p["description"]) > 2000
                or p["category"] not in {"service-management", "package-management", "application-backup", "backup-storage"}
                or not isinstance(p["hosts"], list) or len(p["hosts"]) > 100
                or any(not isinstance(h, str) or not ID.fullmatch(h) for h in p["hosts"])):
            raise ValueError("CATALOG_INVALID: invalid entry")
        found[p["id"]] = dict(p)
    return found


class RemoteCatalog:
    def __init__(self, config):
        self.root = config.data_dir / "plugins" / "official"
        self.config = config
        self.lock = threading.RLock()
        self.refresh_lock = threading.Lock()
        self.entries = {}
        self.checked = None
        self.error = None
        self.refreshing = False
        try:
            raw = (self.root / "index.json").read_bytes()
            if len(raw) > INDEX_LIMIT:
                raise ValueError("cache too large")
            cached = json.loads(raw)
            self.entries = validate_index(cached["index"])
            self.checked = cached["checked"] if isinstance(cached["checked"], (int, float)) else None
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError, TypeError, RecursionError):
            self.error = "官方目錄快取無法讀取，請檢查更新。"

    def _fetch(self, relative, limit):
        if self.config.mode == "demo":
            raise ValueError("Demo 模式不連線 GitHub；可匯入測試插件。")
        # Paths are generated from validated identities/digests, never supplied URLs.
        with httpx.Client(timeout=8, follow_redirects=False, trust_env=False) as client:
            with client.stream("GET", BASE_URL + relative, headers={"Accept": "application/json"}) as response:
                response.raise_for_status()
                raw = bytearray()
                started = time.monotonic()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > limit or time.monotonic() - started > 15:
                        raise ValueError("CATALOG_LIMIT: download exceeds limits")
                return bytes(raw)

    def status(self):
        with self.lock:
            return dict(checked=self.checked, error=self.error, refreshing=self.refreshing,
                        count=len(self.entries), source="GitHub · Lee20171010/unified-service-manager")

    def available(self):
        with self.lock:
            return {k: dict(v) for k, v in self.entries.items()}

    def refresh(self):
        if not self.refresh_lock.acquire(blocking=False):
            return self.status()
        with self.lock:
            self.refreshing = True
        try:
            raw = self._fetch("index.json", INDEX_LIMIT)
            document = json.loads(raw)
            entries = validate_index(document)
            checked = int(time.time() * 1000)
            atomic_write(self.root / "index.json", json.dumps(dict(index=document, checked=checked)).encode())
            with self.lock:
                self.entries, self.checked, self.error = entries, checked, None
        except (httpx.HTTPError, OSError, ValueError, TypeError, RecursionError):
            with self.lock:
                self.error = "無法更新 GitHub 目錄；保留上次目錄，已安裝插件可繼續使用。"
        finally:
            with self.lock:
                self.refreshing = False
            self.refresh_lock.release()
        return self.status()

    def manifest(self, entry):
        from .plugins import validate_manifest
        name = f'{entry["id"]}/{entry["version"]}-{entry["sha256"]}.json'
        path = self.root / "downloads" / name
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            try:
                raw = self._fetch("packages/" + name, PACKAGE_LIMIT)
            except (httpx.HTTPError, OSError, ValueError):
                raise ValueError("PLUGIN_DOWNLOAD: 無法下載插件，請稍後重試；目前安裝未變更。") from None
        if len(raw) > PACKAGE_LIMIT or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("PLUGIN_CHECKSUM: downloaded package does not match catalog")
        try:
            m = validate_manifest(json.loads(raw))
            if any(m.get(k, [] if k == "hosts" else "") != entry[k] for k in ("id", "version", "label", "category", "description", "hosts")):
                raise ValueError("metadata mismatch")
        except (ValueError, TypeError, KeyError, RecursionError):
            raise ValueError("PLUGIN_MANIFEST: downloaded package does not match catalog") from None
        atomic_write(path, raw)
        return m
