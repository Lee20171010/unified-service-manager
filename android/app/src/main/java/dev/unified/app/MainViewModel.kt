package dev.unified.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import java.util.concurrent.atomic.AtomicLong
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.WebSocket
import org.json.JSONObject

data class UiState(
    val snapshot: Snapshot? = null,
    val connectionConfigured: Boolean = false,
    val connecting: Boolean = false,
    val connectionError: String? = null,
    val needsCredentials: Boolean = false,
    val error: String? = null,
    val connected: Boolean = false,
    val busy: Boolean = false,
    val job: Job? = null,
    val logs: List<LogLine> = emptyList(),
    val terminalHost: String? = null,
    val terminalOutput: String = "",
    val connectionVersion: Int = 0,
    val session: JobSession = JobSession(),
    val inputBusy: Boolean = false,
)

class MainViewModel(
    private val credentials: ConnectionStore,
    private val clientFactory: (String, String) -> ApplicationClient = ::Api,
) : ViewModel() {
    var connection = credentials.read()
        private set

    private val mutable =
        MutableStateFlow(UiState(connectionConfigured = credentials.hasSavedConnection()))
    val state = mutable.asStateFlow()

    private var api: ApplicationClient? = null
    private var socket: WebSocket? = null
    private val terminalGeneration = AtomicLong()
    private var jobGeneration = 0L

    fun connect(base: String, token: String) =
        viewModelScope.launch { connectWorkspace(base, token, automatic = false) }

    private suspend fun connectWorkspace(base: String, token: String, automatic: Boolean) {
        if (state.value.busy) return
        Diagnostics.record(
            if (automatic) DiagnosticEvent.CONNECT_AUTO else DiagnosticEvent.CONNECT_MANUAL
        )
        if (automatic && (base.isBlank() || token.isBlank())) {
            mutable.update {
                it.copy(needsCredentials = true, connectionError = "無法讀取已保存的連線，請開啟連線設定重新填寫 Token。")
            }
            return
        }
        mutable.update {
            it.copy(busy = true, connecting = true, error = if (automatic) it.error else null)
        }
        var candidate: ApplicationClient? = null
        try {
            Diagnostics.record(DiagnosticEvent.VALIDATE_ADDRESS)
            val next = clientFactory(base.trim().trimEnd('/'), token.trim())
            candidate = next
            Diagnostics.record(DiagnosticEvent.FETCH_SNAPSHOT)
            val response = next.request("/snapshot")
            Diagnostics.record(DiagnosticEvent.PARSE_SNAPSHOT)
            val snapshot = parseSnapshot(response)
            if (!automatic) {
                Diagnostics.record(DiagnosticEvent.SAVE_CREDENTIALS)
                credentials.save(next.base, token.trim())
            }
            Diagnostics.record(DiagnosticEvent.ACTIVATE_CONNECTION)
            val sameWorkspace = api?.base == next.base
            closeTerminal()
            api?.close()
            api = next
            connection = next.base to token.trim()
            mutable.update {
                val current =
                    if (sameWorkspace || automatic) it
                    else UiState(connectionVersion = it.connectionVersion)
                current.copy(
                    snapshot = snapshot,
                    connected = true,
                    connectionConfigured = true,
                    connectionVersion = it.connectionVersion + 1,
                    connectionError = null,
                    needsCredentials = false,
                    connecting = false,
                )
            }
            Diagnostics.record(DiagnosticEvent.CONNECT_OK)
        } catch (e: CancellationException) {
            Diagnostics.record(DiagnosticEvent.CONNECT_CANCELLED)
            throw e
        } catch (e: Exception) {
            Diagnostics.record(DiagnosticEvent.CONNECT_FAILED, e)
            mutable.update {
                if (automatic)
                    it.copy(
                        connected = false,
                        connectionError = e.message ?: "連線中斷，將自動重試",
                        needsCredentials = e is ApiException && e.statusCode in listOf(401, 403),
                    )
                else it.copy(error = e.message ?: "連線失敗")
            }
        } finally {
            if (api !== candidate) candidate?.close()
            mutable.update { it.copy(busy = false, connecting = false) }
        }
    }

    /** Called by a STARTED lifecycle effect, so polling stops when UI is backgrounded. */
    suspend fun observe() {
        while (kotlin.coroutines.coroutineContext.isActive) {
            val current = api
            if (
                current == null && state.value.connectionConfigured && !state.value.needsCredentials
            ) {
                connectWorkspace(connection.first, connection.second, automatic = true)
            } else if (current != null && !state.value.needsCredentials)
                try {
                    val snapshot = parseSnapshot(current.request("/snapshot"))
                    if (api !== current) continue
                    if (state.value.connectionError != null)
                        Diagnostics.record(DiagnosticEvent.POLL_RECOVERED)
                    if (api === current)
                        mutable.update {
                            it.copy(snapshot = snapshot, connected = true, connectionError = null)
                        }
                    val selected = state.value.job
                    val selection = jobGeneration
                    if (selected != null) {
                        val job = parseJob(JSONObject(current.request("/jobs/${selected.id}")))
                        val cursor = state.value.logs.lastOrNull()?.seq ?: 0
                        val rows =
                            parseLogs(current.request("/jobs/${selected.id}/logs?after=$cursor"))
                        val session = parseSession(current.request("/jobs/${selected.id}/session"))
                        mutable.update {
                            if (
                                api === current &&
                                    jobGeneration == selection &&
                                    it.job?.id == selected.id
                            )
                                it.copy(
                                    job = job,
                                    session =
                                        if (
                                            it.session.generation == session.generation &&
                                                it.session.sequence > session.sequence
                                        )
                                            it.session
                                        else session,
                                    logs = (it.logs + rows).distinctBy { line -> line.seq },
                                )
                            else it
                        }
                    }
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    if (api === current && state.value.connectionError == null)
                        Diagnostics.record(DiagnosticEvent.POLL_FAILED, e)
                    if (api === current)
                        mutable.update {
                            it.copy(
                                connected = false,
                                connectionError = e.message ?: "連線中斷，將自動重試",
                                needsCredentials =
                                    e is ApiException && e.statusCode in listOf(401, 403),
                            )
                        }
                }
            delay(if (state.value.connectionError != null) 5000 else 1000)
        }
    }

    fun mutate(path: String, body: JSONObject, onSuccess: () -> Unit = {}) =
        viewModelScope.launch {
            if (state.value.busy) return@launch
            val current = api ?: return@launch
            mutable.update { it.copy(busy = true, error = null) }
            try {
                val response = JSONObject(current.request(path, body))
                val job = if (response.has("action")) parseJob(response) else null
                if (job != null) jobGeneration++
                mutable.update {
                    it.copy(job = job ?: it.job, logs = if (job != null) emptyList() else it.logs)
                }
                onSuccess()
                val snapshot = parseSnapshot(current.request("/snapshot"))
                mutable.update { it.copy(snapshot = snapshot, connected = true) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                mutable.update { it.copy(error = e.message ?: "操作失敗") }
            } finally {
                mutable.update { it.copy(busy = false) }
            }
        }

    suspend fun pluginDocument(path: String, body: JSONObject?): String {
        val current = api ?: error("請先連線")
        val result = current.request(path, body)
        check(api === current) { "連線已變更，請重新操作" }
        return result
    }

    fun showJob(job: Job) {
        jobGeneration++
        mutable.update { it.copy(job = job, logs = emptyList(), session = JobSession()) }
    }

    fun closeJob() {
        jobGeneration++
        mutable.update { it.copy(job = null, logs = emptyList(), session = JobSession()) }
    }

    fun jobInput(text: String, close: Boolean = false) =
        viewModelScope.launch {
            val current = api ?: return@launch
            val selected = state.value.job ?: return@launch
            val session = state.value.session
            val generation = jobGeneration
            if (state.value.inputBusy || session.phase !in listOf("running", "shell")) return@launch
            mutable.update { it.copy(inputBusy = true) }
            try {
                val result =
                    parseSession(
                        current.request(
                            "/jobs/${selected.id}/session",
                            JSONObject()
                                .put("generation", session.generation)
                                .put("sequence", session.sequence + 1)
                                .put("data", text)
                                .put("close", close),
                        )
                    )
                if (api === current && generation == jobGeneration)
                    mutable.update { it.copy(session = result) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (api === current) mutable.update { it.copy(error = e.message ?: "輸入失敗；不會自動重送") }
            } finally {
                if (api === current) mutable.update { it.copy(inputBusy = false) }
            }
        }

    suspend fun fullLog(id: String): String = requireNotNull(api).request("/jobs/$id/log.txt")

    fun dismissError() {
        mutable.update { it.copy(error = null) }
    }

    fun openTerminal(host: String) {
        closeTerminal()
        val generation = terminalGeneration.get()
        mutable.update { it.copy(terminalHost = host, terminalOutput = "Connecting…\n") }
        socket =
            api?.terminal(host) { text ->
                mutable.update {
                    if (it.terminalHost == host && terminalGeneration.get() == generation)
                        it.copy(terminalOutput = (it.terminalOutput + text).takeLast(200000))
                    else it
                }
            }
    }

    fun terminalInput(text: String) {
        socket?.send(JSONObject().put("type", "input").put("data", text).toString())
    }

    fun closeTerminal() {
        terminalGeneration.incrementAndGet()
        socket?.close(1000, "Closed by user")
        socket = null
        mutable.update { it.copy(terminalHost = null) }
    }

    override fun onCleared() {
        socket?.cancel()
        api?.close()
    }
}
