"""Transport-independent use cases and one lifecycle-owned durable job worker."""

import asyncio
import fcntl
import shlex
import threading
from .plugins import Plugins
from .resources import ResourceAdapter, EXACT, capture
from .job_sessions import JobSessions
from .adapters.registry import Registry
from . import ssh
from contextlib import suppress
from .store import Store, Conflict, identifier, now
from .backups import BackupService, DemoBackups
from .adapters import builtins
from .adapters.contracts import JobContext, AdapterError


class Application:
    def __init__(self, config, registry=None):
        config.validate()
        self.config = config
        self.store = Store(config.data_dir / "unified.sqlite3")
        # Never execute records from a demo database against real infrastructure.
        with self.store.connect() as db:
            row = db.execute("SELECT value FROM metadata WHERE key='mode'").fetchone()
            if row and row[0] != config.mode:
                raise RuntimeError(
                    "Database mode differs. Use separate data volumes for demo and real deployments."
                )
            db.execute(
                "INSERT OR IGNORE INTO metadata VALUES ('mode',?)", (config.mode,)
            )
        self.guard = threading.RLock()
        self.sessions = JobSessions(config)
        self.plugins = None if registry else Plugins(config, self.store)
        self.registry = registry or self.plugin_registry()
        self.backups = (DemoBackups if config.mode == "demo" else BackupService)(
            config, self.registry
        )
        self.wake = asyncio.Event()
        self.worker = None
        self.lock_file = None

    async def start(self):
        self.lock_file = (self.config.data_dir / "worker.lock").open("a")
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock_file.close()
            raise RuntimeError(
                "A worker already owns this data directory; run exactly one application instance"
            )
        self.store.recover()
        if self.config.mode == "demo" and not self.store.list("hosts"):
            self.seed()
        self.worker = asyncio.create_task(self.run(), name="unified-job-worker")

    async def close(self):
        if self.worker:
            self.worker.cancel()
            with suppress(asyncio.CancelledError):
                await self.worker
        await self.sessions.close()
        if self.lock_file:
            self.lock_file.close()

    def seed(self):
        for h in [
            dict(
                id="h1",
                name="nas-host",
                address="192.0.2.10",
                platform="OpenMediaVault",
            ),
            dict(id="h2", name="compute-host", address="192.0.2.20", platform="Ubuntu"),
            dict(id="h3", name="remote-host", address="192.0.2.30", platform="Debian"),
        ]:
            self.store.put(
                "hosts",
                dict(
                    port=22, username="unified", key="id_ed25519", status="online", **h
                ),
            )
        for i, (name, host, version, status) in enumerate(
            [
                ("Magpie", "h1", "0.9.2", "online"),
                ("ServerBox WebDAV", "h1", "2.5.1", "online"),
                ("Immich", "h1", "1.118.0", "online"),
                ("AdGuard Home", "h2", "0.107.53", "online"),
                ("Uptime Kuma", "h2", "1.23.15", "online"),
                ("Nginx Proxy Manager", "h3", "2.12.1", "stopped"),
            ]
        ):
            self.store.put(
                "services",
                dict(
                    id=f"s{i + 1}",
                    name=name,
                    host=host,
                    compose_dir=f"/opt/stacks/service-{i + 1}",
                    version=version,
                    status=status,
                    checked=now(),
                ),
            )

    def plugin_registry(self):
        base = builtins(self.config)
        services = []
        apps = []
        storages = []
        for m in self.plugins.active():
            driver = m["driver"]
            if driver == "compose":
                services.append(base.service("compose"))
            elif driver in ("commands", "npm"):
                services.append(ResourceAdapter(self.config, m, self.sessions))
            elif driver == "backup" and m["id"] in base.applications:
                apps.append(base.application(m["id"]))
            elif driver == "webdav" and m["id"] == "webdav":
                storages.append(base.storage("webdav"))
        return Registry(services, apps, storages)

    def change_plugin(self, id, action):
        with self.guard:
            if not self.plugins:
                raise ValueError("Custom registry has no plugin catalog")
            result = self.plugins.change(id, action)
            self.registry = self.plugin_registry()
            self.backups.registry = self.registry
            return result

    def plugin_document(self, action, document=None, id=None):
        with self.guard:
            if not self.plugins:
                raise ValueError("Custom registry has no plugin catalog")
            if action == "validate":
                return self.plugins.preview_document(document)
            if action == "import":
                return self.plugins.import_document(document)
            if action == "export":
                return self.plugins.export_document(id)
            raise ValueError("Invalid document action")

    def snapshot(self):
        configured = bool(
            self.backup_operations("Magpie")
            or self.backup_operations("Flutter ServerBox")
        )
        resources = [self.service_view(s) for s in self.store.list("services")]
        return dict(
            mode=self.config.mode,
            hosts=self.store.list("hosts"),
            plugins=self.plugins.catalog() if self.plugins else [],
            adapters=self.registry.catalog(),
            resources=resources,
            services=[s for s in resources if s.get("kind", "service") == "service"],
            backup_applications=[
                dict(
                    a.descriptor.public(),
                    client=a.descriptor.label,
                    operations=self.backup_operations(a.descriptor.label),
                )
                for a in self.registry.applications.values()
            ],
            backups=sorted(
                [
                    dict(b, operations=self.backup_operations(b["client"], b))
                    for b in self.store.list("backups")
                ],
                key=lambda b: b["date"],
                reverse=True,
            ),
            jobs=self.store.jobs(),
            backup_configured=configured,
            destination=("DEMO · " if self.config.mode == "demo" else "")
            + "WebDAV "
            + ("已就緒" if configured else "請安裝應用備份與 WebDAV 插件並設定儲存"),
        )

    def add_host(self, value):
        return self.store.add("hosts", dict(id=identifier(), status="unknown", **value))

    def service_record(self, value):
        value = dict(value)
        adapter = self.registry.service(value.get("adapter", "compose"))
        settings = dict(value.get("settings") or {})
        legacy = value.get("compose_dir")
        if legacy is not None:
            if adapter.descriptor.id != "compose" or (
                "compose_dir" in settings and settings["compose_dir"] != legacy
            ):
                raise ValueError("compose_dir 與接入設定不一致")
            settings["compose_dir"] = legacy
        settings = adapter.validate(settings)
        value.update(
            adapter=adapter.descriptor.id,
            settings=settings,
            target_identity=adapter.identity(settings),
            kind=adapter.descriptor.resource_kind,
        )
        value.pop("compose_dir", None)
        if adapter.descriptor.id == "compose":
            value["compose_dir"] = settings["compose_dir"]
        return value

    def service_view(self, value):
        try:
            service = self.service_record(value)
            adapter = self.registry.service(service["adapter"])
            return dict(
                service,
                adapter_label=adapter.descriptor.label,
                operations=[
                    a
                    for a in adapter.descriptor.operations
                    if not isinstance(adapter, ResourceAdapter)
                    or adapter.manifest["driver"] != "commands"
                    or adapter.manifest.get("commands", {}).get(a)
                    or service["settings"].get("cmd_" + a)
                ],
                bindings=value.get("bindings", []),
                available=True,
            )
        except (ValueError, AdapterError):
            return dict(
                value,
                adapter=value.get("adapter", "compose"),
                operations=[],
                available=False,
            )

    def backup_operations(self, client, backup=None):
        try:
            app = self.registry.application_for_backup(backup or {"client": client})
            storage = self.registry.storage(
                backup.get("storage_adapter", "webdav")
                if backup
                else self.registry.default_storage
            )
            if self.config.mode != "demo":
                storage.validate()
            return [
                action
                for action in app.descriptor.operations
                if "download" in storage.descriptor.operations
                and (action != "backup" or "upload" in storage.descriptor.operations)
            ]
        except (ValueError, RuntimeError):
            return []

    def edit_resource(self, id, value):
        with self.guard:
            old = self.store.get("services", id)
            item = self.service_record(value)
            if (
                item["host"] != old["host"]
                or item["adapter"] != old.get("adapter", "compose")
                or item["target_identity"]
                != old.get("target_identity", old.get("compose_dir"))
            ):
                raise ValueError("編輯保留安裝身份；不同主機／目錄請新增對象")
            if any(
                j["status"] in ("queued", "running")
                and set(self.resource_locks(old)).intersection(
                    j.get("locks", [j["target_key"]])
                )
                for j in self.store.jobs()
            ):
                raise Conflict("請等待相關任務完成")
            if any(
                r["id"] != id
                and r["host"] == item["host"]
                and r["name"].casefold() == item["name"].casefold()
                for r in self.store.list("services")
            ):
                raise Conflict("同名項目已登記")
            return self.service_view(self.store.put("services", dict(old, **item)))

    def add_service(self, value):
        self.store.get("hosts", value["host"])
        value = self.service_record(value)
        return self.service_view(
            self.store.add(
                "services",
                dict(
                    id=identifier(),
                    status="unknown",
                    version="尚未讀取",
                    checked=None,
                    **value,
                ),
            )
        )

    async def submit_resource(self, id, body):
        # Resolve once before queuing. Never repeat resolution on reconnect or worker retry.
        item = self.service_record(self.store.get("services", id))
        adapter = self.registry.service(item["adapter"])
        resolved = None
        if (
            body.action in ("install", "upgrade")
            and isinstance(adapter, ResourceAdapter)
            and adapter.manifest["driver"] == "npm"
        ):
            try:
                resolved = await adapter.resolve(
                    self.store.get("hosts", item["host"]), item["settings"]
                )
            except Exception as exc:
                # External transport exceptions can contain credential-bearing URLs.
                detail = (
                    str(exc)
                    if isinstance(exc, (RuntimeError, ValueError))
                    else type(exc).__name__
                )
                raise AdapterError("VERSION_RESOLUTION", detail[:1000]) from exc
        with self.guard:
            current = self.service_record(self.store.get("services", id))
            if (
                current["settings"] != item["settings"]
                or self.registry.service(current["adapter"]).descriptor.version
                != adapter.descriptor.version
            ):
                raise Conflict("CONFIG_CHANGED: 版本解析期間設定已變更，請重新提交")
            if body.action in ("uninstall", "unregister") and not body.confirm:
                raise ValueError("請明確確認此操作")
            return self.submit(
                body.action, "service", id, body.scenario, resolved, body.binding
            )

    def bind_resource(self, id, body):
        with self.guard:
            item = self.service_record(self.store.get("services", id))
            parent = self.service_record(self.store.get("services", body["parent"]))
            adapter = self.registry.service(item["adapter"])
            if (
                not isinstance(adapter, ResourceAdapter)
                or parent["adapter"] not in adapter.manifest.get("hosts", [])
                or parent["host"] != item["host"]
            ):
                raise ValueError("只能關聯同一主機帳號的相容應用")
            if any(
                j["status"] in ("queued", "running")
                and set(
                    self.resource_locks(item) + ["service:" + parent["id"]]
                ).intersection(j.get("locks", [j["target_key"]]))
                for j in self.store.jobs()
            ):
                raise Conflict("請等待相關任務完成")
            bindings = item.setdefault("bindings", [])
            existing = next((b for b in bindings if b["parent"] == parent["id"]), None)
            if existing:
                existing.update(body)
            else:
                bindings.append(
                    dict(
                        body,
                        id=identifier(),
                        registered=False,
                        loaded_version="unknown",
                        needs_restart=False,
                    )
                )
            self.store.put("services", item)
            return self.service_view(item)

    def resource_locks(self, item):
        parents = [b["parent"] for b in item.get("bindings", [])]
        return (
            ["service:" + item["id"]]
            + ["service:" + p for p in parents]
            + [
                "installation:"
                + item["host"]
                + ":"
                + item.get("target_identity", item["id"])
            ]
        )

    def submit(
        self, action, target, id, scenario="normal", resolved=None, binding=None
    ):
        if self.config.mode != "demo" and scenario != "normal":
            raise ValueError("模擬情境只適用於 demo 模式")
        if target == "service":
            item = self.service_record(self.store.get("services", id))
            if action in ("register", "unregister", "verify"):
                relation = next(
                    (b for b in item.get("bindings", []) if b["id"] == binding), None
                )
                if not relation:
                    raise ValueError("Unknown host binding")
                parent = self.service_record(
                    self.store.get("services", relation["parent"])
                )
                if (
                    action == "register"
                    and not EXACT.fullmatch(item.get("version", ""))
                    and not item.get("version", "").endswith("-demo")
                ):
                    raise ValueError("請先檢查或安裝套件")
                if action == "verify" and not relation.get("verify_command"):
                    raise ValueError(
                        "請設定載入版本檢查命令；不能從重啟成功推測載入版本"
                    )
            else:
                self.registry.require(self.registry.service(item["adapter"]), action)
            if action == "uninstall" and any(
                b.get("registered") or b.get("loaded_version") != "none"
                for b in item.get("bindings", [])
            ):
                raise ValueError("仍有宿主引用或載入狀態未知；請先解除接入並檢查已卸載")
            name = item["name"]
            key = "service:" + id
        elif target == "backup" and action == "restore":
            item = self.store.get("backups", id)
            name = item["client"]
            key = "backup:" + name
        elif target == "client" and action == "backup":
            name = id
            key = "backup:" + id
        else:
            raise ValueError("不支援的任務類型")
        if target != "service" and action not in self.backup_operations(
            name, item if target == "backup" else None
        ):
            raise AdapterError(
                "OPERATION_UNSUPPORTED", "備份接入或儲存設定不支援這項操作"
            )
        job = dict(
            id=identifier(),
            target_key=key,
            action=action,
            target=name,
            resource_type=target,
            resource_id=id,
            scenario=scenario,
            status="queued",
            date=now(),
            progress=0,
            error=None,
        )
        if target == "service":
            job.update(
                locks=self.resource_locks(item),
                plugin_versions=(
                    {p["id"]: p["version"] for p in self.plugins.active()}
                    if self.plugins
                    else {}
                ),
                plugins=[item["adapter"]]
                + [
                    self.store.get("services", b["parent"]).get("adapter", "compose")
                    for b in item.get("bindings", [])
                ],
                bound_resource=item,
                binding=binding,
                resolved_version=resolved,
            )
        else:
            app = self.registry.application_for_backup(
                item if target == "backup" else {"client": name}
            )
            job["plugins"] = [
                app.descriptor.id,
                (
                    item.get("storage_adapter", "webdav")
                    if target == "backup"
                    else self.registry.default_storage
                ),
            ]
        self.store.create_job(job)
        self.wake.set()
        return job

    async def run(self):
        while True:
            self.wake.clear()
            queued = [j for j in reversed(self.store.jobs()) if j["status"] == "queued"]
            if not queued:
                await self.wake.wait()
                continue
            j = queued[0]
            j["status"] = "running"
            self.store.update_job(j)
            log_bytes = 0

            async def log(stream, text):
                nonlocal log_bytes
                log_bytes += len(text.encode())
                if log_bytes > 10 * 1024 * 1024:
                    raise RuntimeError("LOG_LIMIT: 單一任務輸出超過 10 MiB，操作已中斷")
                if stream not in ("stdout", "stderr"):
                    raise AdapterError("ADAPTER_STREAM", "無效的輸出串流")
                self.store.log(j["id"], stream, text)

            async def progress(value):
                j["progress"] = max(0, min(99, int(value)))
                self.store.update_job(j)

            context = JobContext(j["id"], j["scenario"], log, progress)
            try:
                await log(
                    "stdout",
                    f"Application Layer accepted {j['action']} · {j['target']}\n",
                )
                async with asyncio.timeout(self.config.job_timeout):
                    if j["resource_type"] == "service":
                        service = self.service_record(
                            self.store.get("services", j["resource_id"])
                        )
                        host = self.store.get("hosts", service["host"])
                        adapter = self.registry.service(service["adapter"])
                        if (
                            j.get("bound_resource")
                            and service["settings"] != j["bound_resource"]["settings"]
                        ):
                            raise ValueError("CONFIG_CHANGED: 請重新提交")
                        if j.get("resolved_version"):
                            service["resolved_version"] = j["resolved_version"]
                            await log(
                                "stdout",
                                "固定目標版本：" + j["resolved_version"] + "\n",
                            )
                        if j["action"] in ("register", "unregister", "verify"):
                            await self.execute_binding(service, host, j, context)
                        else:
                            self.registry.require(adapter, j["action"])
                            if j["action"] == "uninstall" and any(
                                b.get("registered") or b.get("loaded_version") != "none"
                                for b in service.get("bindings", [])
                            ):
                                raise ValueError("HOST_REFERENCE: 仍有宿主引用")
                            if (
                                self.config.mode != "demo"
                                and service["adapter"] == "compose"
                            ):
                                await self.sessions.execute(
                                    context,
                                    host,
                                    ssh.compose_command(
                                        service["settings"], j["action"]
                                    ),
                                )
                                status, version = ssh.parse_status(
                                    await capture(
                                        self.config,
                                        host,
                                        ssh.compose_command(
                                            service["settings"], "refresh"
                                        ),
                                    )
                                )
                                from .adapters.contracts import ServiceResult

                                result = ServiceResult(status, version)
                            else:
                                result = await adapter.execute(
                                    host, service, j["action"], context
                                )
                            service.update(
                                status=result.status,
                                version=result.version,
                                checked=now(),
                            )
                            service.pop("resolved_version", None)
                            for b in service.get("bindings", []):
                                if (
                                    b.get("registered")
                                    and b.get("loaded_version") != result.version
                                ):
                                    b["needs_restart"] = True
                            self.store.put("services", service)
                            if j["action"] in ("start", "restart", "stop"):
                                for pkg in self.store.list("services"):
                                    changed = False
                                    for b in pkg.get("bindings", []):
                                        if b["parent"] == service["id"]:
                                            # Reload remains unknown until a configured probe verifies it.
                                            b["loaded_version"] = "unknown"
                                            changed = True
                                    if changed:
                                        self.store.put("services", pkg)
                        self.store.put(
                            "hosts", dict(host, status="online", checked=now())
                        )
                    else:
                        backup = (
                            self.store.get("backups", j["resource_id"])
                            if j["action"] == "restore"
                            else None
                        )
                        if j["action"] not in self.backup_operations(
                            j["target"], backup
                        ):
                            raise AdapterError(
                                "OPERATION_UNSUPPORTED",
                                "備份接入或儲存設定不支援這項操作",
                            )
                        if j["action"] == "backup":
                            self.store.put(
                                "backups",
                                await self.backups.create(j["target"], context),
                            )
                        else:
                            await self.backups.apply(backup, context)
                j.update(status="success", progress=100, finished=now())
                await log("stdout", "Operation completed. Exit code: 0\n")
            except asyncio.CancelledError:
                j.update(
                    status="failed",
                    finished=now(),
                    error="SERVER_STOPPED: 服務中斷；請檢查遠端狀態後再操作",
                )
                self.store.log(j["id"], "stderr", j["error"] + "\n")
                self.store.update_job(j)
                raise
            except Exception as exc:
                # HTTP errors can contain credential-bearing URLs: expose class only for external exceptions.
                message = (
                    str(exc)
                    if isinstance(exc, (RuntimeError, ValueError))
                    else type(exc).__name__
                )
                j.update(status="failed", finished=now(), error=message[:1000])
                self.store.log(j["id"], "stderr", j["error"] + "\nExit code: 1\n")
            finally:
                self.store.update_job(j)

    async def execute_binding(self, service, host, j, context):
        b = next(b for b in service["bindings"] if b["id"] == j["binding"])
        parent = self.service_record(self.store.get("services", b["parent"]))
        action = j["action"]
        if self.config.mode == "demo":
            from .adapters.demo import simulate

            await self.sessions.demo(context, host, simulate)
            observed = service["version"] if b.get("registered") else "none"
        else:
            command = b[
                {
                    "register": "register_command",
                    "unregister": "unregister_command",
                    "verify": "verify_command",
                }[action]
            ]
            env = {
                "UNIFIED_PACKAGE": service["settings"]["package_name"],
                "UNIFIED_DIRECTORY": service["settings"]["directory"],
                "UNIFIED_VERSION": service["version"],
            }
            command = (
                "env "
                + " ".join(shlex.quote(k + "=" + v) for k, v in env.items())
                + " sh -c "
                + shlex.quote(command)
            )
            if action == "verify":
                observed = await capture(self.config, host, command)
            else:
                await self.sessions.execute(context, host, command)
        if action == "verify":
            if observed not in ("none", "unknown") and not EXACT.fullmatch(observed):
                raise ValueError("載入版本命令只能輸出完整版本號、none 或 unknown")
            b["loaded_version"] = observed
            b["needs_restart"] = (
                b["registered"]
                and observed != service["version"]
                or not b["registered"]
                and observed != "none"
            )
        else:
            b["registered"] = action == "register"
            b["needs_restart"] = True
        self.store.put("services", service)
