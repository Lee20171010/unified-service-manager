package dev.unified.app

import org.json.JSONArray
import org.json.JSONObject

data class Host(
    val id: String,
    val name: String,
    val address: String,
    val port: Int,
    val username: String,
    val key: String,
    val status: String,
)

data class Service(
    val id: String,
    val name: String,
    val host: String,
    val directory: String,
    val version: String,
    val status: String,
    val checked: Long,
    val adapter: String = "compose",
    val adapterLabel: String = "Docker Compose",
    val settings: Map<String, String> = emptyMap(),
    val operations: List<String> = emptyList(),
    val available: Boolean = true,
    val kind: String = "service",
    val bindings: List<Binding> = emptyList(),
)

data class Backup(
    val id: String,
    val client: String,
    val name: String,
    val date: Long,
    val bytes: Long,
    val operations: List<String> = emptyList(),
)

data class Job(
    val id: String,
    val target: String,
    val action: String,
    val status: String,
    val resourceId: String,
    val date: Long,
    val progress: Int,
    val error: String?,
)

data class LogLine(val seq: Long, val time: Long, val stream: String, val text: String)

data class Snapshot(
    val mode: String,
    val hosts: List<Host>,
    val services: List<Service>,
    val backups: List<Backup>,
    val jobs: List<Job>,
    val destination: String,
    val serviceAdapters: List<ServiceAdapterInfo> = emptyList(),
    val backupApplications: List<BackupApplicationInfo> = emptyList(),
    val plugins: List<PluginInfo> = emptyList(),
    val pluginCatalog: CatalogStatus = CatalogStatus(),
)

data class AdapterField(
    val name: String,
    val label: String,
    val initial: String,
    val required: Boolean,
    val choices: List<String> = emptyList(),
)

data class ServiceAdapterInfo(val id: String, val label: String, val fields: List<AdapterField>)

data class BackupApplicationInfo(
    val client: String,
    val label: String,
    val operations: List<String>,
)

internal fun JSONObject.stringList(key: String): List<String> =
    optJSONArray(key)
        ?.let { array -> (0 until array.length()).map { array.getString(it) } }
        .orEmpty()

internal fun JSONObject.stringMap(): Map<String, String> =
    keys().asSequence().associateWith { getString(it) }

internal val serviceVocabulary =
    listOf(
        "refresh",
        "start",
        "stop",
        "restart",
        "upgrade",
        "install",
        "uninstall",
        "doctor",
        "run",
    )

internal fun Service.supportedActions() = serviceVocabulary.filter { it in operations }

internal fun <T> JSONArray.mapObjects(transform: (JSONObject) -> T): List<T> =
    (0 until length()).map { transform(getJSONObject(it)) }

internal fun JSONObject.optionalString(key: String): String? =
    if (isNull(key)) null else optString(key).ifBlank { null }

internal fun parseJob(j: JSONObject) =
    Job(
        j.getString("id"),
        j.getString("target"),
        j.getString("action"),
        j.getString("status"),
        j.getString("resource_id"),
        j.getLong("date"),
        j.getInt("progress"),
        j.optionalString("error"),
    )

internal fun parseLogs(text: String) =
    JSONArray(text).mapObjects {
        LogLine(it.getLong("seq"), it.getLong("time"), it.getString("stream"), it.getString("text"))
    }

internal fun parseSnapshot(text: String): Snapshot {
    val j = JSONObject(text)
    return Snapshot(
        j.getString("mode"),
        j.getJSONArray("hosts").mapObjects {
            Host(
                it.getString("id"),
                it.getString("name"),
                it.getString("address"),
                it.getInt("port"),
                it.getString("username"),
                it.getString("key"),
                it.getString("status"),
            )
        },
        (j.optJSONArray("resources") ?: j.getJSONArray("services")).mapObjects {
            Service(
                it.getString("id"),
                it.getString("name"),
                it.getString("host"),
                it.optString("compose_dir", ""),
                it.getString("version"),
                it.getString("status"),
                it.optLong("checked", 0),
                it.optString("adapter", "compose"),
                it.optString("adapter_label", it.optString("adapter", "compose")),
                it.optJSONObject("settings")?.stringMap().orEmpty(),
                it.stringList("operations"),
                it.optBoolean("available", false),
                it.optString("kind", "service"),
                it.optJSONArray("bindings")
                    ?.mapObjects { b ->
                        Binding(
                            b.getString("id"),
                            b.getString("parent"),
                            b.optBoolean("registered"),
                            b.optString("loaded_version", "unknown"),
                            b.optBoolean("needs_restart"),
                            b.optString("verify_command").isNotBlank(),
                        )
                    }
                    .orEmpty(),
            )
        },
        j.getJSONArray("backups").mapObjects {
            Backup(
                it.getString("id"),
                it.getString("client"),
                it.getString("name"),
                it.getLong("date"),
                it.getLong("bytes"),
                it.stringList("operations"),
            )
        },
        j.getJSONArray("jobs").mapObjects(::parseJob),
        j.getString("destination"),
        j.optJSONObject("adapters")
            ?.takeIf { it.optInt("interface_version") == 1 }
            ?.optJSONArray("adapters")
            ?.mapObjects { it }
            ?.filter { it.optString("kind") == "service" && it.optInt("interface_version") == 1 }
            ?.map { a ->
                ServiceAdapterInfo(
                    a.getString("id"),
                    a.getString("label"),
                    a.getJSONArray("fields").mapObjects { f ->
                        AdapterField(
                            f.getString("name"),
                            f.getString("label"),
                            f.optString("initial"),
                            f.optBoolean("required", true),
                            f.stringList("choices"),
                        )
                    },
                )
            }
            .orEmpty(),
        j.optJSONArray("backup_applications")
            ?.mapObjects {
                BackupApplicationInfo(
                    it.getString("client"),
                    it.getString("label"),
                    it.stringList("operations"),
                )
            }
            .orEmpty(),
        j.optJSONArray("plugins")
            ?.mapObjects { p ->
                val installed = p.optJSONObject("installed")
                PluginInfo(
                    p.getString("id"),
                    p.getString("label"),
                    p.optString("category"),
                    p.optString("version"),
                    p.optString("description", p.optString("error")),
                    installed?.optString("version"),
                    installed?.optBoolean("enabled") == true,
                    installed?.has("previous") == true,
                    p.optBoolean("available", true),
                    p.stringList("hosts"),
                    p.optString("source", "custom"),
                    p.optString("artifact_checksum"),
                )
            }
            .orEmpty(),
        j.optJSONObject("plugin_catalog")?.let {
            CatalogStatus(
                it.optLong("checked"),
                it.optString("error").takeUnless { e -> e == "null" }.orEmpty(),
                it.optBoolean("refreshing"),
            )
        } ?: CatalogStatus(),
    )
}

data class CatalogStatus(
    val checked: Long = 0,
    val error: String = "",
    val refreshing: Boolean = false,
)

data class Binding(
    val id: String,
    val parent: String,
    val registered: Boolean,
    val loadedVersion: String,
    val needsRestart: Boolean,
    val canVerify: Boolean,
)

data class PluginInfo(
    val id: String,
    val label: String,
    val category: String,
    val version: String,
    val description: String,
    val installedVersion: String?,
    val enabled: Boolean,
    val rollback: Boolean,
    val available: Boolean,
    val hosts: List<String>,
    val source: String = "custom",
    val checksum: String = "",
)

data class JobSession(
    val phase: String = "closed",
    val generation: String = "",
    val output: String = "",
    val sequence: Int = 0,
)

internal fun parseSession(text: String): JobSession {
    val j = JSONObject(text)
    return JobSession(
        j.getString("phase"),
        j.optString("generation"),
        j.optString("output"),
        j.optInt("sequence"),
    )
}

val actionNames =
    mapOf(
        "refresh" to "重新整理狀態",
        "start" to "啟動",
        "stop" to "停止",
        "restart" to "重啟",
        "upgrade" to "更新",
        "backup" to "備份",
        "restore" to "還原",
        "install" to "安裝套件",
        "uninstall" to "卸載套件",
        "doctor" to "檢查執行環境",
        "run" to "執行",
        "register" to "接入宿主",
        "unregister" to "解除接入",
        "verify" to "檢查載入版本",
    )
val statusNames =
    mapOf(
        "online" to "運行中",
        "stopped" to "已停止",
        "unknown" to "待確認",
        "degraded" to "部分異常",
        "queued" to "排隊中",
        "running" to "執行中",
        "success" to "成功",
        "failed" to "失敗",
    )

internal fun Service.displayStatus(): String =
    when {
        !available -> "插件未就緒"
        kind in listOf("package", "extension") ->
            when {
                status == "unknown" -> "unknown"
                version == "absent" -> "未安裝"
                bindings.any { it.needsRestart } -> "宿主需重啟／檢查"
                else -> "已安裝"
            }
        else -> status
    }
