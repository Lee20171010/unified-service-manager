package dev.unified.app

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
internal fun DiagnosticsDialog(
    dismiss: () -> Unit,
    export: () -> String = Diagnostics::export,
    clear: () -> Unit = Diagnostics::clear,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var preview by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    suspend fun load() {
        preview = withContext(Dispatchers.IO) { export() }
    }
    LaunchedEffect(Unit) {
        try {
            load()
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            message = "無法讀取診斷日誌。"
        }
    }
    val save =
        rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/plain")) {
            uri ->
            if (uri != null)
                scope.launch {
                    busy = true
                    try {
                        withContext(Dispatchers.IO) {
                            val text = export()
                            requireNotNull(context.contentResolver.openOutputStream(uri)).use {
                                it.write(text.toByteArray(Charsets.UTF_8))
                            }
                        }
                        message = "診斷日誌已匯出。"
                    } catch (e: CancellationException) {
                        throw e
                    } catch (_: Exception) {
                        message = "無法匯出診斷日誌。"
                    } finally {
                        busy = false
                    }
                }
        }
    Dialog(dismiss, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(
            Modifier.fillMaxWidth().fillMaxHeight(.9f).padding(16.dp),
            shape = MaterialTheme.shapes.large,
        ) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("診斷日誌", style = MaterialTheme.typography.titleLarge)
                Text(
                    "在手機保留最近 200 筆事件（最多 64 KiB）。記錄連線階段、異常堆疊及上次退出原因；不記錄網址、Token、指令或回應內容。重現問題後可匯出給開發者。",
                    fontSize = 12.sp,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(
                        enabled = !busy,
                        onClick = {
                            try {
                                save.launch("unified-diagnostics.txt")
                            } catch (_: Exception) {
                                message = "無法開啟檔案選擇器。"
                            }
                        },
                    ) {
                        Text("匯出 .txt")
                    }
                    TextButton(
                        enabled = !busy,
                        onClick = {
                            scope.launch {
                                busy = true
                                try {
                                    val text = withContext(Dispatchers.IO) { export() }
                                    context.startActivity(
                                        Intent.createChooser(
                                            Intent(Intent.ACTION_SEND).apply {
                                                type = "text/plain"
                                                putExtra(Intent.EXTRA_TEXT, text)
                                            },
                                            "分享診斷日誌",
                                        )
                                    )
                                } catch (e: CancellationException) {
                                    throw e
                                } catch (_: Exception) {
                                    message = "無法分享診斷日誌。"
                                } finally {
                                    busy = false
                                }
                            }
                        },
                    ) {
                        Text("分享")
                    }
                }
                SelectionContainer(
                    Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())
                ) {
                    Text(
                        preview.ifBlank { "尚無診斷事件。" },
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp,
                    )
                }
                message?.let { Text(it, fontSize = 12.sp) }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    TextButton(
                        enabled = !busy,
                        onClick = {
                            scope.launch {
                                busy = true
                                try {
                                    withContext(Dispatchers.IO) { clear() }
                                    load()
                                    message = "診斷日誌已清除。"
                                } catch (e: CancellationException) {
                                    throw e
                                } catch (_: Exception) {
                                    message = "無法清除診斷日誌。"
                                } finally {
                                    busy = false
                                }
                            }
                        },
                    ) {
                        Text("清除日誌")
                    }
                    TextButton(onClick = dismiss) { Text("關閉") }
                }
            }
        }
    }
}
