import re
from .contracts import AdapterError, SERVICE_ACTIONS


class Registry:
    def __init__(self, services, applications, storages, default_storage="webdav"):
        self.services = self._index(
            services,
            "service",
            SERVICE_ACTIONS + ("install", "uninstall", "doctor", "run"),
        )
        self.applications = self._index(applications, "backup", ("backup", "restore"))
        self.storages = self._index(storages, "storage", ("upload", "download"))
        self.default_storage = default_storage
        # Storage may be uninstalled on a fresh instance.
        labels = [a.descriptor.label for a in self.applications.values()]
        if len(labels) != len(set(labels)):
            raise ValueError("Duplicate backup application label")

    @staticmethod
    def _index(adapters, kind, operations):
        result = {}
        for adapter in adapters:
            d = adapter.descriptor
            if (
                d.kind != kind
                or d.interface_version != 1
                or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", d.id)
                or d.id in result
                or not d.operations
                or not set(d.operations) <= set(operations)
            ):
                raise ValueError("Invalid or duplicate adapter descriptor")
            fields = [f.name for f in d.fields]
            if (
                len(fields) != len(set(fields))
                or len(fields) > 24
                or any(not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", f) for f in fields)
                or (kind != "service" and fields)
            ):
                raise ValueError("Invalid adapter configuration fields")
            result[d.id] = adapter
        return result

    def _get(self, group, id):
        if id not in group:
            raise AdapterError("ADAPTER_UNAVAILABLE", f"未註冊的接入類型：{id}")
        return group[id]

    def service(self, id):
        return self._get(self.services, id)

    def application(self, id):
        return self._get(self.applications, id)

    def storage(self, id):
        return self._get(self.storages, id)

    def application_for_backup(self, backup):
        if backup.get("application_adapter"):
            app = self.application(backup["application_adapter"])
            if app.descriptor.label != backup["client"]:
                raise AdapterError("BACKUP_IDENTITY", "備份應用程式與接入類型不一致")
            return app
        for app in self.applications.values():
            if app.descriptor.label == backup["client"]:
                return app
        raise AdapterError("ADAPTER_UNAVAILABLE", "找不到備份應用程式接入類型")

    @staticmethod
    def require(adapter, action):
        if action not in adapter.descriptor.operations:
            raise AdapterError("OPERATION_UNSUPPORTED", "此接入類型不支援這項操作")

    def catalog(self):
        return {
            "interface_version": 1,
            "adapters": [
                a.descriptor.public()
                for group in (self.services, self.applications, self.storages)
                for a in group.values()
            ],
        }
