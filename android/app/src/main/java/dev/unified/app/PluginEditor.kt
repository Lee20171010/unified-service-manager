package dev.unified.app

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

internal val pluginCommandActions =
    linkedMapOf(
        "refresh" to "狀態",
        "start" to "啟動",
        "stop" to "停止",
        "restart" to "重啟",
        "upgrade" to "升級",
        "install" to "安裝軟體",
        "uninstall" to "卸載軟體",
        "doctor" to "檢查環境",
        "run" to "執行",
    )

internal fun commandPluginDocument(draft: JSONObject): JSONObject {
    val commands = JSONObject()
    pluginCommandActions.keys.forEach { action ->
        val command = draft.optString("cmd_$action")
        if (command.isNotBlank()) commands.put(action, command)
    }
    require(commands.length() > 0) { "請至少填寫一項操作命令" }
    val fields =
        JSONArray()
            .put(
                JSONObject()
                    .put("name", "directory")
                    .put("label", "工作目錄")
                    .put("initial", draft.optString("directory").trim())
                    .put("required", true)
            )
            .put(
                JSONObject()
                    .put("name", "identity")
                    .put("label", "實例名稱")
                    .put("initial", draft.optString("id").trim())
                    .put("required", true)
            )
    val params = draft.optJSONArray("parameters") ?: JSONArray()
    for (i in 0 until params.length()) {
        val p = params.getJSONObject(i)
        fields.put(
            JSONObject()
                .put("name", p.optString("name").trim())
                .put("label", p.optString("label").trim())
                .put("initial", p.optString("initial"))
                .put("required", p.optBoolean("required", true))
                .put(
                    "choices",
                    JSONArray(
                        p.optString("choices")
                            .split(',')
                            .map { it.trim() }
                            .filter { it.isNotEmpty() }
                    ),
                )
        )
    }
    return JSONObject()
        .put("id", draft.optString("id").trim())
        .put("label", draft.optString("label").trim())
        .put("version", draft.optString("version").trim())
        .put("author", draft.optString("author").trim())
        .put("description", draft.optString("description").trim())
        .put("interface_version", 1)
        .put("driver", "commands")
        .put(
            "category",
            if (draft.optString("kind") in listOf("package", "extension")) "package-management"
            else "service-management",
        )
        .put("resource_kind", draft.optString("kind", "service"))
        .put("fields", fields)
        .put("commands", commands)
        .put("operations", JSONArray(commands.keys().asSequence().toList()))
}

internal fun parsePluginDocument(text: String): JSONObject {
    require(text.toByteArray(Charsets.UTF_8).size <= 131072) { "插件文件上限為 128 KiB" }
    return JSONObject(text)
}

internal fun readPluginBytes(input: java.io.InputStream): ByteArray {
    val output = java.io.ByteArrayOutputStream()
    val buffer = ByteArray(8192)
    while (output.size() <= 131072) {
        val count = input.read(buffer, 0, minOf(buffer.size, 131073 - output.size()))
        if (count < 0) break
        output.write(buffer, 0, count)
    }
    require(output.size() <= 131072) { "插件文件上限為 128 KiB" }
    return output.toByteArray()
}

@Composable
internal fun PluginDocumentDialog(
    mode: String,
    pluginId: String = "",
    request: suspend (String, JSONObject?) -> String,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var draft by rememberSaveable {
        mutableStateOf("{\"version\":\"1.0.0\",\"directory\":\"/opt\",\"kind\":\"service\"}")
    }
    var document by rememberSaveable { mutableStateOf("") }
    var preview by rememberSaveable { mutableStateOf<String?>(null) }
    var note by rememberSaveable { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var saved by rememberSaveable { mutableStateOf(false) }
    val importFile =
        rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null)
                scope.launch {
                    busy = true
                    error = null
                    try {
                        val text =
                            withContext(Dispatchers.IO) {
                                val bytes =
                                    context.contentResolver.openInputStream(uri)?.use {
                                        readPluginBytes(it)
                                    } ?: error("無法讀取文件")
                                require(bytes.size <= 131072) { "插件文件上限為 128 KiB" }
                                bytes.toString(Charsets.UTF_8)
                            }
                        parsePluginDocument(text)
                        document = text
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: Exception) {
                        error = e.message ?: "無法讀取文件"
                    } finally {
                        busy = false
                    }
                }
        }
    val exportFile =
        rememberLauncherForActivityResult(
            ActivityResultContracts.CreateDocument("application/json")
        ) { uri ->
            if (uri != null)
                scope.launch {
                    busy = true
                    error = null
                    try {
                        val text = document
                        withContext(Dispatchers.IO) {
                            val output =
                                context.contentResolver.openOutputStream(uri) ?: error("無法寫入文件")
                            output.use { it.write((text + "\n").toByteArray(Charsets.UTF_8)) }
                        }
                        note = "已匯出插件 JSON"
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: Exception) {
                        error = e.message ?: "匯出失敗"
                    } finally {
                        busy = false
                    }
                }
        }
    suspend fun loadExport() {
        busy = true
        error = null
        try {
            val source = JSONObject(request("/plugins/$pluginId/manifest", null))
            document = (if (mode == "copy") copyPluginDocument(source) else source).toString(2)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            error = e.message ?: "讀取失敗"
        } finally {
            busy = false
        }
    }
    LaunchedEffect(pluginId, mode) {
        if ((mode == "export" || mode == "copy") && document.isEmpty()) loadExport()
    }
    PluginEditorWindow(
        onDismissRequest = { if (!busy) onDismiss() },
        title = {
            Text(
                when (mode) {
                    "create" -> "建立插件"
                    "copy" -> "複製並自訂插件"
                    "export" -> "匯出插件"
                    else -> "匯入插件"
                }
            )
        },
        text = {
            Column(
                Modifier.fillMaxWidth().verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text("儲存到中央插件目錄後，請再按 Install。命令在所選主機執行；請勿填入密碼或私鑰。")
                if (saved) Text("已儲存到可安裝。請關閉此視窗，再按 Install／更新插件。")
                else if (mode == "export" || preview != null) {
                    if (note.isNotBlank()) Text(note)
                    SelectionContainer {
                        Text(if (mode == "export") document else preview.orEmpty())
                    }
                } else if (mode == "import" || mode == "copy") {
                    if (mode == "copy") {
                        Text("請填寫新的 ID；完整設定已保留，可在 JSON 中修改。原插件保留。")
                        if (document.isEmpty())
                            TextButton(
                                enabled = !busy,
                                onClick = { scope.launch { loadExport() } },
                            ) {
                                Text("重新讀取")
                            }
                    }
                    if (mode == "import")
                        OutlinedButton(
                            enabled = !busy,
                            onClick = {
                                importFile.launch(
                                    arrayOf(
                                        "application/json",
                                        "text/*",
                                        "application/octet-stream",
                                    )
                                )
                            },
                        ) {
                            Text("選擇 JSON 文件")
                        }
                    OutlinedTextField(
                        document,
                        { document = it },
                        label = { Text("或貼上 plugin.json") },
                        enabled = !busy,
                        minLines = 8,
                        modifier = Modifier.fillMaxWidth(),
                    )
                } else {
                    CommandPluginForm(draft, !busy) { draft = it }
                }
                if (error != null) Text(error.orEmpty(), color = MaterialTheme.colorScheme.error)
                if (busy) Text("處理中…")
            }
        },
        confirmButton = {
            TextButton(
                enabled = !busy,
                onClick = {
                    if (saved) onDismiss()
                    else if (mode == "export") {
                        if (document.isBlank()) scope.launch { loadExport() }
                        else {
                            val m = JSONObject(document)
                            exportFile.launch("${m.getString("id")}-${m.getString("version")}.json")
                        }
                    } else
                        scope.launch {
                            busy = true
                            error = null
                            try {
                                if (preview != null) {
                                    request(
                                        "/plugin-documents",
                                        JSONObject()
                                            .put("manifest", JSONObject(preview!!))
                                            .put("create_only", mode == "copy"),
                                    )
                                    saved = true
                                } else {
                                    val manifest =
                                        if (mode == "create") pluginDocument(JSONObject(draft))
                                        else parsePluginDocument(document)
                                    if (mode == "copy")
                                        require(manifest.optString("id") != pluginId) {
                                            "請使用不同於原插件的新 ID"
                                        }
                                    val response =
                                        JSONObject(
                                            request(
                                                "/plugin-documents/validate",
                                                JSONObject()
                                                    .put("manifest", manifest)
                                                    .put("create_only", mode == "copy"),
                                            )
                                        )
                                    if (mode == "copy")
                                        require(
                                            response.isNull("replaces_version") &&
                                                response.isNull("installed_version")
                                        ) {
                                            "此 ID 已存在，請選擇新的 ID"
                                        }
                                    preview = response.getJSONObject("manifest").toString(2)
                                    note =
                                        "請確認完整參數與命令。" +
                                            (if (!response.isNull("replaces_version"))
                                                "取代可安裝版本 ${response.getString("replaces_version")}。"
                                            else "") +
                                            (if (!response.isNull("installed_version"))
                                                "目前已安裝 ${response.getString("installed_version")}；儲存後需手動更新。"
                                            else "儲存後尚未安裝。")
                                }
                            } catch (e: CancellationException) {
                                throw e
                            } catch (e: Exception) {
                                error = e.message ?: "操作失敗"
                            } finally {
                                busy = false
                            }
                        }
                },
            ) {
                Text(
                    when {
                        saved -> "完成"
                        mode == "export" -> if (document.isBlank()) "重新讀取" else "儲存 JSON 文件"
                        preview != null -> "儲存到可安裝"
                        else -> "校驗與預覽"
                    }
                )
            }
        },
        dismissButton = {
            Row {
                if (preview != null && !saved)
                    TextButton(
                        enabled = !busy,
                        onClick = {
                            preview = null
                            error = null
                        },
                    ) {
                        Text("返回編輯")
                    }
                TextButton(enabled = !busy, onClick = onDismiss) { Text("關閉") }
            }
        },
    )
}

@Composable
private fun CommandPluginForm(raw: String, enabled: Boolean, update: (String) -> Unit) {
    val values = JSONObject(raw)
    fun set(key: String, value: Any) {
        update(JSONObject(raw).put(key, value).toString())
    }
    fun parameter(index: Int, key: String, value: Any) {
        val next = JSONObject(raw)
        next.getJSONArray("parameters").getJSONObject(index).put(key, value)
        update(next.toString())
    }
    listOf(
            "id" to "插件 ID（小寫英文、數字、連字號）",
            "label" to "顯示名稱",
            "version" to "版本",
            "author" to "作者",
            "description" to "說明",
        )
        .forEach { (key, label) ->
            OutlinedTextField(
                values.optString(key),
                { set(key, it) },
                enabled = enabled,
                label = { Text(label) },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    val kind = values.optString("kind", "service")
    val driver = values.optString("driver", "commands")
    if (enabled) {
        Choice(
            "對象類型",
            kind,
            listOf(
                "service" to "常駐服務",
                "tool" to "一次性工具",
                "package" to "套件／CLI",
                "extension" to "擴充插件",
            ),
            {
                val next = JSONObject(raw).put("kind", it)
                if (
                    (driver == "compose" && it != "service") ||
                        (driver == "npm" && it !in listOf("package", "extension"))
                )
                    next.put("driver", "commands")
                update(next.toString())
            },
        )
        Choice(
            "管理方式",
            driver,
            listOf("commands" to "自訂命令") +
                (if (kind == "service") listOf("compose" to "Docker Compose")
                else if (kind in listOf("package", "extension")) listOf("npm" to "npm")
                else emptyList()),
            { set("driver", it) },
        )
    }
    @Composable
    fun input(key: String, label: String, default: String = "") {
        OutlinedTextField(
            values.optString(key, default),
            { set(key, it) },
            enabled = enabled,
            label = { Text(label) },
            modifier = Modifier.fillMaxWidth(),
        )
    }
    if (kind == "extension") input("hosts", "相容的宿主插件 ID（逗號分隔，可留空）")
    if (driver == "compose") {
        input("compose_dir", "Compose 專案絕對目錄", "/opt/stacks/example")
        Text("提供狀態、啟動、停止、重啟及升級。遠端須已有 Compose 專案。")
        return
    }
    if (driver == "npm") {
        input("package_name", "npm 套件名稱")
        if (enabled)
            Choice(
                "安裝範圍",
                values.optString("scope", "user"),
                listOf("user" to "使用者 prefix", "project" to "專案"),
                { set("scope", it) },
            )
        input("npm_directory", "安裝 prefix／專案絕對目錄", "/opt/npm")
        input("node", "Node 絕對路徑", "/usr/bin/node")
        input("npm", "npm CLI 絕對路徑", "/usr/share/nodejs/npm/bin/npm-cli.js")
        input("package_version", "遠端套件版本（latest 或完整版本號）", "latest")
        Text("提供狀態、安裝、升級、卸載及環境檢查。插件版本與遠端套件版本分開管理。")
        return
    }
    input("directory", "遠端工作目錄", "/opt")
    Text("操作命令：只填需要的操作。狀態命令輸出 active / stopped 或狀態 JSON。遠端程式及腳本須先準備好。")
    pluginCommandActions.forEach { (action, label) ->
        OutlinedTextField(
            values.optString("cmd_$action"),
            { set("cmd_$action", it) },
            enabled = enabled,
            label = { Text("${label}命令") },
            minLines = 2,
            modifier = Modifier.fillMaxWidth(),
        )
    }
    Text("自訂參數：欄位 mode 對應環境變數，命令中使用 \"\$UNIFIED_MODE\"。")
    val parameters = values.optJSONArray("parameters") ?: JSONArray()
    for (i in 0 until parameters.length()) {
        val p = parameters.getJSONObject(i)
        HorizontalDivider()
        listOf("name" to "欄位名稱", "label" to "顯示標籤", "initial" to "預設值", "choices" to "選項（逗號分隔，可留空）")
            .forEach { (key, label) ->
                OutlinedTextField(
                    p.optString(key),
                    { parameter(i, key, it) },
                    enabled = enabled,
                    label = { Text(label) },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        Row {
            Checkbox(
                p.optBoolean("required", true),
                { parameter(i, "required", it) },
                enabled = enabled,
            )
            Text("必填")
        }
        TextButton(
            enabled = enabled,
            onClick = {
                val next = JSONArray(parameters.toString())
                next.remove(i)
                set("parameters", next)
            },
        ) {
            Text("移除參數")
        }
    }
    OutlinedButton(
        enabled = enabled && parameters.length() < 22,
        onClick = {
            val next = JSONArray(parameters.toString())
            next.put(JSONObject().put("required", true))
            set("parameters", next)
        },
    ) {
        Text("增加參數")
    }
}

@Composable
private fun PluginEditorWindow(
    onDismissRequest: () -> Unit,
    title: @Composable () -> Unit,
    text: @Composable () -> Unit,
    confirmButton: @Composable () -> Unit,
    dismissButton: @Composable () -> Unit,
) {
    Dialog(onDismissRequest, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(
            Modifier.widthIn(max = 760.dp).fillMaxWidth().fillMaxHeight(.92f).padding(12.dp),
            shape = MaterialTheme.shapes.large,
        ) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                ProvideTextStyle(MaterialTheme.typography.titleLarge) { title() }
                Box(Modifier.weight(1f).fillMaxWidth()) { text() }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    dismissButton()
                    confirmButton()
                }
            }
        }
    }
}
