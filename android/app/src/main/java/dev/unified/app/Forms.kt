package dev.unified.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject

internal data class FormField(
    val name: String,
    val label: String,
    val initial: String = "",
    val choices: List<Pair<String, String>> = emptyList(),
    val secret: Boolean = false,
    val required: Boolean = true,
)

internal data class FormSpec(
    val title: String,
    val path: String,
    val fields: List<FormField>,
    val note: String = "",
    val confirm: Boolean = false,
    val adapters: List<ServiceAdapterInfo> = emptyList(),
)

internal fun serverName(base: String): String {
    val host =
        try {
            java.net.URI(base).host.orEmpty()
        } catch (_: Exception) {
            ""
        }
    return when {
        host.isBlank() -> "伺服器"
        host.endsWith(".ts.net") -> host.substringBefore('.')
        else -> host
    }
}

@Composable
internal fun ConnectionDialog(
    connection: Pair<String, String>,
    busy: Boolean,
    error: String?,
    onDismiss: () -> Unit,
    onConnect: (String, String) -> Unit,
    connected: Boolean = false,
) {
    var editing by remember { mutableStateOf(!connected) }
    var base by remember { mutableStateOf(connection.first) }
    var token by remember { mutableStateOf(connection.second) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (editing) "連接伺服器" else "伺服器") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (!editing) {
                    Text(serverName(connection.first), style = MaterialTheme.typography.titleMedium)
                    Text(connection.first, fontSize = 12.sp)
                    Text(if (connected) "已連線 · 開啟時自動連接" else "正在重新連線…", fontSize = 12.sp)
                } else {
                    Text("填寫伺服器網址與 Token，儲存後會自動連接。使用 Tailnet 網址時請先連上 Tailscale。", fontSize = 12.sp)
                    OutlinedTextField(
                        base,
                        { base = it },
                        label = { Text("HTTPS 伺服器網址") },
                        singleLine = true,
                    )
                    OutlinedTextField(
                        token,
                        { token = it },
                        label = { Text("管理員 Token") },
                        visualTransformation = PasswordVisualTransformation(),
                        singleLine = true,
                    )
                    if (error != null)
                        Text(error, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
                }
            }
        },
        confirmButton = {
            TextButton(
                enabled = !busy && (!editing || (base.isNotBlank() && token.isNotBlank())),
                onClick = { if (editing) onConnect(base, token) else editing = true },
            ) {
                Text(if (editing) "儲存並連線" else "編輯連線")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("關閉") } },
    )
}

@Composable
internal fun FormDialog(
    spec: FormSpec,
    busy: Boolean,
    error: String?,
    dismiss: () -> Unit,
    submit: (JSONObject) -> Unit,
) {
    val values =
        remember(spec) {
            mutableStateMapOf<String, String>().apply {
                spec.fields.forEach { put(it.name, it.initial) }
                spec.adapters.firstOrNull()?.fields?.forEach {
                    put("settings." + it.name, it.initial)
                }
            }
        }
    val fields =
        spec.fields +
            spec.adapters
                .find { it.id == values["adapter"] }
                ?.fields
                .orEmpty()
                .map {
                    FormField(
                        "settings." + it.name,
                        it.label,
                        it.initial,
                        choices = it.choices.map { v -> v to v },
                        required = it.required,
                    )
                }
    var confirmed by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = { if (!busy) dismiss() },
        title = { Text(spec.title) },
        text = {
            Column(
                Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                if (spec.note.isNotBlank()) Text(spec.note, fontSize = 12.sp)
                fields.forEach { field ->
                    if (field.choices.isNotEmpty())
                        Choice(
                            field.label,
                            values[field.name].orEmpty(),
                            field.choices,
                            { choice ->
                                values[field.name] = choice
                                if (field.name == "adapter") {
                                    values.keys
                                        .filter { it.startsWith("settings.") }
                                        .forEach { values.remove(it) }
                                    spec.adapters
                                        .find { it.id == choice }
                                        ?.fields
                                        ?.forEach { values["settings." + it.name] = it.initial }
                                }
                            },
                        )
                    else
                        OutlinedTextField(
                            values[field.name].orEmpty(),
                            { choice ->
                                values[field.name] = choice
                                if (field.name == "adapter") {
                                    values.keys
                                        .filter { it.startsWith("settings.") }
                                        .forEach { values.remove(it) }
                                    spec.adapters
                                        .find { it.id == choice }
                                        ?.fields
                                        ?.forEach { values["settings." + it.name] = it.initial }
                                }
                            },
                            label = { Text(field.label) },
                            singleLine = true,
                            visualTransformation =
                                if (field.secret) PasswordVisualTransformation()
                                else VisualTransformation.None,
                        )
                }
                if (spec.confirm)
                    Row {
                        Checkbox(confirmed, { confirmed = it })
                        Text("確認執行此操作", Modifier.padding(top = 12.dp))
                    }
                if (error != null)
                    Text(error, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
            }
        },
        confirmButton = {
            TextButton(
                enabled =
                    !busy &&
                        fields.filter { it.required }.all { !values[it.name].isNullOrBlank() } &&
                        (!spec.confirm || confirmed) &&
                        (values["port"] == null || values["port"]?.toIntOrNull() in 1..65535),
                onClick = {
                    val body = formBody(values, spec.confirm)
                    submit(body)
                },
            ) {
                Text(if (busy) "送出中…" else "確認")
            }
        },
        dismissButton = { TextButton(enabled = !busy, onClick = dismiss) { Text("取消") } },
    )
}

internal fun formBody(values: Map<String, String>, confirm: Boolean): JSONObject {
    val body = JSONObject()
    val settings = JSONObject()
    values.forEach { (key, value) ->
        if (key.startsWith("settings.")) settings.put(key.removePrefix("settings."), value.trim())
        else body.put(key, if (key == "port") value.toInt() else value.trim())
    }
    if (values.containsKey("adapter")) body.put("settings", settings)
    if (confirm) body.put("confirm", true)
    return body
}
