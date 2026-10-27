"""Installation-controlled, immutable JSON plugin packages. Discovery executes nothing."""

import hashlib
import json
import re
import os
import tempfile
from pathlib import Path
from .adapters.contracts import AdapterError, ConfigField, Descriptor

ID = re.compile(r"[a-z][a-z0-9-]{0,63}")
VERSION = re.compile(r"\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?")
ACTIONS = {
    "refresh",
    "start",
    "stop",
    "restart",
    "upgrade",
    "install",
    "uninstall",
    "doctor",
    "run",
}


MAX_DOCUMENT_BYTES = 131072

# Exact v1 factory templates can remain in an existing OMV catalog volume.
# Installed copies still appear via catalog() and retain their lifecycle/commands.
RETIRED_FACTORY_TEMPLATES = {
    "ssh-service": "7d4a7c648e968960851e49b0c107524756b7dc9d4cbdb7142f5f7eaa9a277927",
    "ssh-tool": "e59a7f3143fb4ab9f2d2123d6993d37b1a6c9438749c2a85de5234c8ede822e0",
}


def manifest_bytes(m):
    try:
        raw = (json.dumps(m, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise ValueError("PLUGIN_MANIFEST: invalid JSON document") from None
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError("PLUGIN_MANIFEST: document exceeds 128 KiB")
    return raw


def validate_shape(m):
    """Validate untrusted document types before the interface v1 validator."""
    manifest_bytes(m)
    if not isinstance(m, dict):
        raise ValueError("PLUGIN_MANIFEST: expected an object")
    allowed = {"id", "version", "interface_version", "label", "driver", "category",
               "resource_kind", "operations", "fields", "commands", "author",
               "description", "hosts", "package_name", "dependencies"}
    if set(m) - allowed:
        raise ValueError("PLUGIN_MANIFEST: unknown manifest fields")
    for key in ("id", "version", "label", "driver", "category", "resource_kind",
                "author", "description", "package_name"):
        if key in m and (not isinstance(m[key], str) or "\0" in m[key]):
            raise ValueError("PLUGIN_MANIFEST: invalid text field " + key)
    fields = m.get("fields", [])
    if not isinstance(fields, list) or len(fields) > 24:
        raise ValueError("PLUGIN_MANIFEST: invalid fields")
    for f in fields:
        if not isinstance(f, dict) or set(f) - {"name", "label", "initial", "required", "choices"}:
            raise ValueError("PLUGIN_MANIFEST: invalid field definition")
        for key in ("name", "label"):
            if not isinstance(f.get(key), str) or not f[key]:
                raise ValueError("PLUGIN_MANIFEST: field name and label required")
        if not isinstance(f.get("initial", ""), str) or type(f.get("required", True)) is not bool:
            raise ValueError("PLUGIN_MANIFEST: invalid field default/required")
        choices = f.get("choices", [])
        if not isinstance(choices, list) or len(choices) > 100 or any(not isinstance(v, str) for v in choices):
            raise ValueError("PLUGIN_MANIFEST: invalid choices")
    commands = m.get("commands", {})
    if not isinstance(commands, dict) or any(not isinstance(v, str) or "\0" in v for v in commands.values()):
        raise ValueError("PLUGIN_MANIFEST: invalid commands")
    hosts = m.get("hosts", [])
    if not isinstance(hosts, list) or any(not isinstance(h, str) or not ID.fullmatch(h) for h in hosts):
        raise ValueError("PLUGIN_MANIFEST: invalid host integrations")
    if type(m.get("interface_version")) is not int:
        raise ValueError("PLUGIN_MANIFEST: invalid interface version")


def validate_manifest(m):
    validate_shape(m)
    if (
        not isinstance(m, dict)
        or not ID.fullmatch(m.get("id", ""))
        or not VERSION.fullmatch(m.get("version", ""))
    ):
        raise ValueError("PLUGIN_MANIFEST: invalid identity/version")
    if m.get("interface_version") != 1 or m.get("driver") not in (
        "compose",
        "commands",
        "npm",
        "backup",
        "webdav",
    ):
        raise ValueError("PLUGIN_MANIFEST: unsupported interface/driver")
    if m.get("category") not in (
        "service-management",
        "package-management",
        "application-backup",
        "backup-storage",
    ):
        raise ValueError("PLUGIN_MANIFEST: invalid category")
    if not m.get("label") or len(m["label"]) > 100:
        raise ValueError("PLUGIN_MANIFEST: invalid label")
    if (
        (m["driver"] == "compose" and m["id"] != "compose")
        or (m["driver"] == "backup" and m["id"] not in ("magpie", "serverbox"))
        or (m["driver"] == "webdav" and m["id"] != "webdav")
    ):
        raise ValueError("PLUGIN_MANIFEST: primitive identity mismatch")
    if m.get("dependencies"):
        raise ValueError(
            "PLUGIN_MANIFEST: dependencies are not supported by interface v1"
        )
    if m.get("resource_kind", "service") not in (
        "service",
        "package",
        "extension",
        "tool",
    ):
        raise ValueError("PLUGIN_MANIFEST: invalid resource kind")
    if not isinstance(m.get("operations"), list) or any(
        not isinstance(a, str) for a in m["operations"]
    ):
        raise ValueError("PLUGIN_MANIFEST: invalid operations")
    fields = m.get("fields", [])
    if not isinstance(fields, list):
        raise ValueError("PLUGIN_MANIFEST: invalid fields")
    if m["driver"] == "commands" and not any(
        f.get("name") == "directory" for f in fields
    ):
        raise ValueError("PLUGIN_MANIFEST: command directory field required")
    if len(fields) > 24 or len({f["name"] for f in fields}) != len(fields):
        raise ValueError("PLUGIN_MANIFEST: invalid fields")
    for f in fields:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", f["name"]):
            raise ValueError("PLUGIN_MANIFEST: invalid field name")
        ConfigField(**f)
    if m["driver"] in ("compose", "commands", "npm") and (
        not m.get("operations") or not set(m["operations"]) <= ACTIONS
    ):
        raise ValueError("PLUGIN_MANIFEST: invalid operations")
    if m["driver"] == "commands":
        for a, command in m.get("commands", {}).items():
            if (
                a not in m["operations"]
                or not isinstance(command, str)
                or len(command) > 16384
            ):
                raise ValueError("PLUGIN_MANIFEST: invalid command")
    if m["driver"] == "npm":
        for name in ("package_name", "scope", "directory", "node", "npm", "version"):
            if name not in [f["name"] for f in fields]:
                raise ValueError("PLUGIN_MANIFEST: npm fields missing")
    return m


class Plugins:
    def __init__(self, config, store):
        self.config, self.store = config, store
        self.root = config.data_dir / "plugins" / "packages"
        self.root.mkdir(parents=True, exist_ok=True)
        self.catalog_root = config.data_dir / "plugins" / "catalog"
        self.catalog_root.mkdir(parents=True, exist_ok=True)

    def discover(self):
        found = {}
        for path in sorted(self.config.plugin_catalog.glob("*/*/plugin.json")):
            try:
                if path.is_symlink() or path.stat().st_size > 131072:
                    continue
                m = validate_manifest(json.loads(path.read_text()))
                if hashlib.sha256(manifest_bytes(m)).hexdigest() == RETIRED_FACTORY_TEMPLATES.get(m["id"]):
                    continue
                if m["id"] in found:
                    raise ValueError("PLUGIN_MANIFEST: duplicate catalog id")
                found[m["id"]] = m
            except (OSError, ValueError, KeyError, TypeError) as e:
                # A malformed package never contributes capabilities.
                found[
                    "invalid:" + str(path.relative_to(self.config.plugin_catalog))
                ] = {
                    "id": "invalid",
                    "label": path.parent.name,
                    "error": str(e),
                    "available": False,
                }
        # Uploaded documents take precedence over the read-only supplied catalog.
        for path in sorted(self.catalog_root.glob("*/plugin.json")):
            try:
                if path.is_symlink() or path.stat().st_size > MAX_DOCUMENT_BYTES:
                    continue
                m = validate_manifest(json.loads(path.read_text()))
                if m["id"] != path.parent.name:
                    raise ValueError("PLUGIN_MANIFEST: catalog identity mismatch")
                found[m["id"]] = m
            except (OSError, ValueError, KeyError, TypeError):
                found[path.parent.name] = {"id": path.parent.name, "label": path.parent.name,
                                          "error": "Uploaded plugin document is invalid", "available": False}
        return found

    def preview_document(self, m):
        validate_manifest(m)
        raw = manifest_bytes(m)
        previous = self.discover().get(m["id"])
        if previous and not previous.get("error") and previous["version"] == m["version"] and manifest_bytes(previous) != raw:
            raise ValueError("PLUGIN_IMMUTABLE: increment package version before changing content")
        installed_path = self.root / m["id"] / m["version"] / "plugin.json"
        if installed_path.exists() and installed_path.read_bytes() != raw:
            raise ValueError("PLUGIN_IMMUTABLE: increment package version before changing content")
        return {"manifest": m, "replaces_version": previous.get("version") if previous else None,
                "installed_version": self.installed().get(m["id"], {}).get("version")}

    def import_document(self, m):
        preview = self.preview_document(m)
        folder = self.catalog_root / m["id"]
        folder.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".import-", dir=folder)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(manifest_bytes(m))
                stream.flush()
                os.fsync(stream.fileno())
            Path(name).replace(folder / "plugin.json")
        finally:
            Path(name).unlink(missing_ok=True)
        return preview

    def export_document(self, id):
        if not ID.fullmatch(id):
            raise ValueError("Invalid plugin id")
        m = self.discover().get(id)
        if m is None:
            record = self.installed().get(id)
            if record is None:
                raise KeyError(id)
            m = self.manifest(record)
        if m.get("error"):
            raise ValueError("PLUGIN_UNAVAILABLE: package not available")
        return validate_manifest(m)

    def installed(self):
        return {p["id"]: p for p in self.store.list("plugins")}

    def catalog(self):
        available = self.discover()
        installed = self.installed()
        for id, p in installed.items():
            if id not in available:
                try:
                    available[id] = self.manifest(p)
                except (OSError, ValueError):
                    available[id] = {
                        "id": id,
                        "label": id,
                        "error": "Installed package checksum or manifest invalid",
                        "available": False,
                    }
        return [
            dict(m, installed=installed.get(id), available="error" not in m)
            for id, m in available.items()
        ]

    def manifest(self, p):
        path = self.root / p["id"] / p["version"] / "plugin.json"
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != p["checksum"]:
            raise ValueError("PLUGIN_CHECKSUM: installed package changed")
        return validate_manifest(json.loads(raw))

    def active(self):
        result = []
        for p in self.installed().values():
            if p.get("enabled"):
                try:
                    result.append(self.manifest(p))
                except (OSError, ValueError):
                    pass
        return result

    def change(self, id, action):
        if not ID.fullmatch(id):
            raise ValueError("Invalid plugin id")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            jobs = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT body FROM jobs WHERE status IN ('queued','running')"
                )
            ]
            if any(id in j.get("plugins", []) for j in jobs):
                raise ValueError("PLUGIN_BUSY: 等待相關任務完成")
            row = db.execute(
                "SELECT body FROM entities WHERE kind='plugins' AND id=?", (id,)
            ).fetchone()
            old = json.loads(row[0]) if row else None
            if action in ("install", "update"):
                m = self.discover().get(id)
                if not m or m.get("error"):
                    raise ValueError("PLUGIN_UNAVAILABLE: package not available")
                raw = (
                    json.dumps(m, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
                ).encode()
                digest = hashlib.sha256(raw).hexdigest()
                folder = self.root / id / m["version"]
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / "plugin.json"
                if path.exists() and path.read_bytes() != raw:
                    raise ValueError(
                        "PLUGIN_IMMUTABLE: increment package version before changing content"
                    )
                temp = folder / "plugin.tmp"
                temp.write_bytes(raw)
                temp.replace(path)
                record = dict(
                    id=id, version=m["version"], checksum=digest, enabled=True
                )
                if old and old["version"] != m["version"]:
                    record["previous"] = old
            elif old and action in ("enable", "disable", "remove", "rollback"):
                record = dict(old)
                if action == "rollback":
                    if not old.get("previous"):
                        raise ValueError("No previous version")
                    record = dict(
                        old["previous"],
                        previous={k: v for k, v in old.items() if k != "previous"},
                    )
                    self.manifest(record)
                else:
                    record["enabled"] = action == "enable"
                    record["removed"] = action == "remove"
            else:
                raise ValueError("Plugin not installed or invalid action")
            db.execute(
                "INSERT OR REPLACE INTO entities VALUES (?,?,?)",
                ("plugins", id, json.dumps(record)),
            )
        return record

    def require(self, id):
        p = self.installed().get(id)
        if not p or not p.get("enabled"):
            raise AdapterError("PLUGIN_UNAVAILABLE", "請先到插件頁面安裝／啟用 " + id)
        return self.manifest(p)
