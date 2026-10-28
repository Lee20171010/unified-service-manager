package dev.unified.app

import org.json.JSONArray
import org.json.JSONObject

internal fun pluginDocument(draft: JSONObject): JSONObject {
    val driver = draft.optString("driver", "commands")
    val kind = draft.optString("kind", "service")
    fun hosts() =
        JSONArray(draft.optString("hosts").split(',').map { it.trim() }.filter { it.isNotEmpty() })
    if (driver == "commands")
        return commandPluginDocument(draft).apply { if (kind == "extension") put("hosts", hosts()) }
    val result = JSONObject()
    listOf("id", "label", "version", "author", "description").forEach {
        result.put(it, draft.optString(it).trim())
    }
    result.put("interface_version", 1).put("driver", driver).put("resource_kind", kind)
    fun field(name: String, label: String, value: String, choices: List<String> = emptyList()) =
        JSONObject()
            .put("name", name)
            .put("label", label)
            .put("initial", value.trim())
            .put("required", true)
            .put("choices", JSONArray(choices))
    if (driver == "compose") {
        require(kind == "service") { "Docker Compose 用於常駐服務" }
        return result
            .put("category", "service-management")
            .put("operations", JSONArray(listOf("refresh", "start", "stop", "restart", "upgrade")))
            .put(
                "fields",
                JSONArray()
                    .put(
                        field(
                            "compose_dir",
                            "Compose 專案目錄",
                            draft.optString("compose_dir", "/opt/stacks/example"),
                        )
                    ),
            )
    }
    require(driver == "npm" && kind in listOf("package", "extension")) { "npm 用於套件或擴充插件" }
    return result
        .put("category", "package-management")
        .put("package_name", draft.optString("package_name").trim())
        .put("hosts", if (kind == "extension") hosts() else JSONArray())
        .put(
            "operations",
            JSONArray(listOf("refresh", "install", "upgrade", "uninstall", "doctor")),
        )
        .put(
            "fields",
            JSONArray()
                .put(field("package_name", "npm 套件名稱", draft.optString("package_name")))
                .put(
                    field(
                        "scope",
                        "安裝範圍",
                        draft.optString("scope", "user"),
                        listOf("user", "project"),
                    )
                )
                .put(
                    field(
                        "directory",
                        "安裝 prefix／專案絕對目錄",
                        draft.optString("npm_directory", "/opt/npm"),
                    )
                )
                .put(field("node", "Node 絕對路徑", draft.optString("node", "/usr/bin/node")))
                .put(
                    field(
                        "npm",
                        "npm CLI 絕對路徑",
                        draft.optString("npm", "/usr/share/nodejs/npm/bin/npm-cli.js"),
                    )
                )
                .put(field("version", "遠端套件版本", draft.optString("package_version", "latest"))),
        )
}

internal fun copyPluginDocument(source: JSONObject): JSONObject {
    require(source.optString("driver") in listOf("commands", "npm", "compose")) {
        "此插件使用專用備份介面，請匯出 JSON 參考其設定"
    }
    return JSONObject(source.toString())
        .put("id", "")
        .put("label", source.getString("label") + "（自訂）")
        .put("version", "1.0.0")
}
