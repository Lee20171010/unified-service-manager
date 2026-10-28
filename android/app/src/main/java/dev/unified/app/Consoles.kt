package dev.unified.app

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
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
internal fun JobConsole(
    job: Job,
    logs: List<LogLine>,
    close: () -> Unit,
    fullLog: suspend (String) -> String,
    session: JobSession = JobSession(),
    inputBusy: Boolean = false,
    sendInput: (String, Boolean) -> Unit = { _, _ -> },
    draft: MutableState<String> = remember(job.id) { mutableStateOf("") },
) {
    var jobInput by draft
    var stream by rememberSaveable { mutableStateOf("all") }
    var exportError by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val launcher =
        rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/plain")) {
            uri ->
            if (uri != null)
                scope.launch {
                    try {
                        val text = fullLog(job.id)
                        withContext(Dispatchers.IO) {
                            requireNotNull(context.contentResolver.openOutputStream(uri)).use {
                                it.write(text.toByteArray())
                            }
                        }
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: Exception) {
                        exportError = e.message
                    }
                }
        }
    Dialog(close, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(
            Modifier.fillMaxWidth().fillMaxHeight(.92f).padding(12.dp),
            shape = MaterialTheme.shapes.large,
        ) {
            Column(
                Modifier.padding(18.dp).imePadding(),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Row {
                    Text(
                        "Job Console",
                        Modifier.weight(1f),
                        style = MaterialTheme.typography.titleLarge,
                    )
                    TextButton(onClick = close) { Text("關閉") }
                }
                Text("${job.target} / ${actionNames[job.action]}", fontSize = 12.sp)
                Status(job.status)
                if (session.phase in listOf("running", "shell")) {
                    Text(
                        if (session.phase == "shell") "排錯 shell · 輸出不寫入任務日誌" else "前台程序 · PTY 合併輸出",
                        fontSize = 11.sp,
                    )
                    OutlinedTextField(
                        jobInput,
                        { jobInput = it },
                        label = { Text("任務或 shell 輸入") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                    )
                    Row {
                        TextButton(
                            enabled = !inputBusy,
                            onClick = {
                                sendInput(jobInput + "\n", false)
                                jobInput = ""
                            },
                        ) {
                            Text("送出")
                        }
                        TextButton(enabled = !inputBusy, onClick = { sendInput("\u0003", false) }) {
                            Text("Ctrl+C")
                        }
                        TextButton(enabled = !inputBusy, onClick = { sendInput("", true) }) {
                            Text("結束會話")
                        }
                    }
                }
                if (session.output.isNotBlank())
                    SelectionContainer {
                        Text(
                            session.output.takeLast(4000),
                            Modifier.heightIn(max = 120.dp).verticalScroll(rememberScrollState()),
                            fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp,
                        )
                    }
                Choice(
                    "輸出串流",
                    stream,
                    listOf("all" to "全部", "stdout" to "stdout", "stderr" to "stderr"),
                    { stream = it },
                )
                val scroll = rememberScrollState()
                LaunchedEffect(logs.size) {
                    if (scroll.maxValue - scroll.value < 200)
                        scroll.animateScrollTo(scroll.maxValue)
                }
                SelectionContainer(
                    Modifier.weight(1f).fillMaxWidth().background(Green).padding(12.dp)
                ) {
                    Column(Modifier.verticalScroll(scroll)) {
                        logs
                            .filter { stream == "all" || it.stream == stream }
                            .forEach {
                                Text(
                                    "[${date(it.time)}] ${it.stream} ${it.text}",
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 11.sp,
                                    color =
                                        if (it.stream == "stderr") Color(0xFFE4A38C)
                                        else Color(0xFFDAE6D8),
                                )
                            }
                    }
                }
                job.error?.let {
                    Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
                }
                exportError?.let {
                    Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
                }
                Text(
                    "關閉視窗後，任務仍由中央服務持續執行。",
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedButton(onClick = { launcher.launch("${job.id}.log") }) { Text("儲存完整日誌") }
            }
        }
    }
}

@Composable
internal fun TerminalDialog(
    host: String,
    output: String,
    input: (String) -> Unit,
    close: () -> Unit,
    draft: MutableState<String> = remember(host) { mutableStateOf("") },
) {
    var command by draft
    Dialog(close, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(
            Modifier.fillMaxWidth().fillMaxHeight(.92f).padding(12.dp),
            shape = MaterialTheme.shapes.large,
        ) {
            Column(
                Modifier.padding(16.dp).imePadding(),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text("Interactive SSH Terminal", style = MaterialTheme.typography.titleLarge)
                Text("Terminal Gateway · 行式互動指令", fontSize = 11.sp)
                val scroll = rememberScrollState()
                LaunchedEffect(output) { scroll.animateScrollTo(scroll.maxValue) }
                SelectionContainer(
                    Modifier.weight(1f).fillMaxWidth().background(Green).padding(12.dp)
                ) {
                    Text(
                        output,
                        Modifier.verticalScroll(scroll),
                        color = Color(0xFFDAE6D8),
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                    )
                }
                OutlinedTextField(
                    command,
                    { command = it },
                    label = { Text("輸入指令") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { input("\u0003") }) { Text("Ctrl+C") }
                    OutlinedButton(onClick = { input("\u0004") }) { Text("Ctrl+D") }
                    Button(
                        onClick = {
                            input(command + "\n")
                            command = ""
                        }
                    ) {
                        Text("送出")
                    }
                }
                Text(
                    "全螢幕 TUI 請使用專用 SSH 客戶端。",
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                TextButton(onClick = close) { Text("關閉工作階段") }
            }
        }
    }
}
