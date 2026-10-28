package dev.unified.app

import androidx.lifecycle.viewModelScope
import java.io.IOException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.*
import okhttp3.Request
import okhttp3.WebSocket
import okio.ByteString
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class MainViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    private val clients = mutableMapOf<String, FakeClient>()
    private val saved =
        object : ConnectionStore {
            var value = "https://old.test" to "token"

            override fun hasSavedConnection() = true

            override fun read() = value

            override fun save(base: String, token: String) {
                value = base to token
            }
        }
    private lateinit var vm: MainViewModel

    @Before
    fun setup() {
        Dispatchers.setMain(dispatcher)
        vm = MainViewModel(saved) { base, _ -> clients.getValue(base) }
    }

    @After
    fun cleanup() {
        vm.viewModelScope.cancel()
        Dispatchers.resetMain()
    }

    private suspend fun TestScope.connect(client: FakeClient) {
        clients[client.base] = client
        vm.connect(client.base, "token")
        runCurrent()
        assertTrue(vm.state.value.connected)
    }

    @Test
    fun workspaceDraftsClearOnlyAfterAcceptedSwitch() =
        runTest(dispatcher) {
            connect(FakeClient("https://old.test"))
            val draft = FormSpec("Fixture", "/hosts", listOf(FormField("name", "Name")))
            draft.values["name"] = "unsaved fixture"
            vm.drafts.form.value = draft
            vm.drafts.jobInput.value = "unsent fixture"
            val broken =
                FakeClient("https://broken.test").apply {
                    response = { _, _ -> throw IOException("offline") }
                }
            clients[broken.base] = broken
            vm.connect(broken.base, "fixture")
            runCurrent()
            assertSame(draft, vm.drafts.form.value)
            assertEquals("unsent fixture", vm.drafts.jobInput.value)
            connect(FakeClient("https://new.test"))
            assertNull(vm.drafts.form.value)
            assertEquals("", vm.drafts.jobInput.value)
        }

    @Test
    fun failedConnectionClosesCandidateAndPreservesWorkspace() =
        runTest(dispatcher) {
            val old = FakeClient("https://old.test")
            connect(old)
            val broken =
                FakeClient("https://broken.test").apply {
                    response = { _, _ -> throw IOException("offline") }
                }
            clients[broken.base] = broken
            vm.connect(broken.base, "token")
            runCurrent()
            assertTrue(broken.closed)
            assertFalse(old.closed)
            assertEquals(old.base, vm.connection.first)
            assertEquals("offline", vm.state.value.error)
        }

    @Test
    fun oldPollFailureCannotDisconnectNewWorkspace() =
        runTest(dispatcher) {
            val old = FakeClient("https://old.test")
            connect(old)
            val late = CompletableDeferred<String>()
            old.response = { _, _ -> late.await() }
            val observing = backgroundScope.launch { vm.observe() }
            runCurrent()
            val next = FakeClient("https://new.test")
            connect(next)
            late.completeExceptionally(IOException("old connection closed"))
            runCurrent()
            assertTrue(vm.state.value.connected)
            assertNull(vm.state.value.error)
            assertEquals(next.base, vm.state.value.snapshot?.destination)
            observing.cancel()
        }

    @Test
    fun staleTerminalFramesCannotEnterReopenedSession() =
        runTest(dispatcher) {
            val client = FakeClient("https://old.test")
            connect(client)
            vm.openTerminal("h1")
            val previous = client.outputs.single()
            vm.closeTerminal()
            vm.openTerminal("h1")
            previous("OLD SESSION")
            client.outputs.last()("CURRENT SESSION")
            assertFalse(vm.state.value.terminalOutput.contains("OLD SESSION"))
            assertTrue(vm.state.value.terminalOutput.contains("CURRENT SESSION"))
        }

    @Test
    fun repeatedSubmitOnlyCreatesOneRequestWhileBusy() =
        runTest(dispatcher) {
            val client = FakeClient("https://old.test")
            connect(client)
            var writes = 0
            val response = CompletableDeferred<String>()
            client.response = { _, body ->
                if (body != null) {
                    writes++
                    response.await()
                } else snapshot(client.base)
            }
            vm.mutate("/hosts", JSONObject().put("name", "lab"))
            vm.mutate("/hosts", JSONObject().put("name", "lab"))
            runCurrent()
            assertEquals(1, writes)
            response.complete("{}")
            runCurrent()
            assertFalse(vm.state.value.busy)
        }

    @Test
    fun observerCancellationStopsRequests() =
        runTest(dispatcher) {
            val client = FakeClient("https://old.test")
            connect(client)
            val observing = backgroundScope.launch { vm.observe() }
            runCurrent()
            observing.cancel()
            val count = client.requests
            advanceTimeBy(10_000)
            runCurrent()
            assertEquals(count, client.requests)
        }

    @Test
    fun reopeningJobDiscardsPreviousConsoleResponse() =
        runTest(dispatcher) {
            val client = FakeClient("https://old.test")
            connect(client)
            val jobJson =
                """{"id":"j1","target":"Magpie","action":"restart","status":"success","resource_id":"s1","date":0,"progress":100,"error":null}"""
            val job = parseJob(JSONObject(jobJson))
            val oldLogs = CompletableDeferred<String>()
            client.response = { path, _ ->
                when {
                    path.contains("/logs") -> oldLogs.await()
                    path.startsWith("/jobs/") -> jobJson
                    else -> snapshot(client.base)
                }
            }
            vm.showJob(job)
            val observing = backgroundScope.launch { vm.observe() }
            runCurrent()
            vm.closeJob()
            vm.showJob(job)
            oldLogs.complete("""[{"seq":50,"time":0,"stream":"stdout","text":"stale cursor"}]""")
            runCurrent()
            assertTrue(vm.state.value.logs.isEmpty())
            observing.cancel()
        }

    @Test
    fun savedWorkspaceConnectsOnForegroundAndAfterProcessRecreation() =
        runTest(dispatcher) {
            val client = FakeClient(saved.value.first)
            clients[client.base] = client
            val observing = backgroundScope.launch { vm.observe() }
            runCurrent()
            assertTrue(vm.state.value.connected)
            assertEquals(client.base, vm.state.value.snapshot?.destination)
            observing.cancel()
            vm.viewModelScope.cancel()
            vm = MainViewModel(saved) { base, _ -> clients.getValue(base) }
            val reopened = backgroundScope.launch { vm.observe() }
            runCurrent()
            assertTrue(vm.state.value.connected)
            assertEquals(client.base, vm.connection.first)
            reopened.cancel()
        }

    @Test
    fun firstLaunchDoesNotAutomaticallyConnectDemoDefaults() =
        runTest(dispatcher) {
            val fresh =
                object : ConnectionStore {
                    override fun hasSavedConnection() = false

                    override fun read() = "https://demo.test" to "demo-default"

                    override fun save(base: String, token: String) = Unit
                }
            vm.viewModelScope.cancel()
            var created = 0
            vm =
                MainViewModel(fresh) { base, _ ->
                    created++
                    FakeClient(base)
                }
            val observing = backgroundScope.launch { vm.observe() }
            advanceTimeBy(10_000)
            runCurrent()
            assertEquals(0, created)
            assertFalse(vm.state.value.connectionConfigured)
            observing.cancel()
        }

    @Test
    fun offlineColdStartRetriesSavedConnectionWithoutManualAction() =
        runTest(dispatcher) {
            val offline =
                FakeClient(saved.value.first).apply {
                    response = { _, _ -> throw IOException("offline") }
                }
            clients[offline.base] = offline
            val observing = backgroundScope.launch { vm.observe() }
            runCurrent()
            assertTrue(offline.closed)
            assertFalse(vm.state.value.connected)
            assertEquals("offline", vm.state.value.connectionError)
            val online = FakeClient(saved.value.first)
            clients[online.base] = online
            advanceTimeBy(5000)
            runCurrent()
            assertTrue(vm.state.value.connected)
            assertNull(vm.state.value.connectionError)
            assertEquals(1, online.requests)
            observing.cancel()
        }

    @Test
    fun gateway502DuringUpdateRetriesWithoutDiscardingSavedCredentials() =
        runTest(dispatcher) {
            val updating =
                FakeClient(saved.value.first).apply {
                    response = { _, _ -> throw ApiException(502, "HTTP 502") }
                }
            clients[updating.base] = updating
            val observing = backgroundScope.launch { vm.observe() }
            runCurrent()
            assertTrue(updating.closed)
            assertFalse(vm.state.value.connected)
            assertFalse(vm.state.value.needsCredentials)
            assertFalse(vm.state.value.busy)
            assertEquals("HTTP 502", vm.state.value.connectionError)
            assertEquals("https://old.test" to "token", saved.value)
            val recovered = FakeClient(saved.value.first)
            clients[recovered.base] = recovered
            advanceTimeBy(5000)
            runCurrent()
            assertTrue(vm.state.value.connected)
            assertNull(vm.state.value.connectionError)
            assertEquals(1, recovered.requests)
            assertEquals("https://old.test" to "token", saved.value)
            observing.cancel()
        }

    @Test
    fun backgroundResumeRetainsConsoleAndRefreshesWithoutReplayingWrites() =
        runTest(dispatcher) {
            val client = FakeClient(saved.value.first)
            connect(client)
            val jobJson =
                """{"id":"j1","target":"Tool","action":"run","status":"success","resource_id":"s1","date":0,"progress":100,"error":null}"""
            vm.showJob(parseJob(JSONObject(jobJson)))
            var writes = 0
            var offline = false
            client.response = { path, body ->
                if (body != null) writes++
                if (offline) throw IOException("temporary offline")
                when {
                    path.contains("/logs") -> "[]"
                    path.endsWith("/session") -> "{\"phase\":\"closed\"}"
                    path.startsWith("/jobs/") -> jobJson
                    else -> snapshot(client.base)
                }
            }
            var observing = backgroundScope.launch { vm.observe() }
            runCurrent()
            observing.cancel()
            val count = client.requests
            advanceTimeBy(60_000)
            runCurrent()
            assertEquals(count, client.requests)
            assertEquals("j1", vm.state.value.job?.id)
            offline = true
            observing = backgroundScope.launch { vm.observe() }
            runCurrent()
            assertNotNull(vm.state.value.snapshot)
            assertFalse(vm.state.value.connected)
            offline = false
            advanceTimeBy(5000)
            runCurrent()
            assertTrue(vm.state.value.connected)
            assertNull(vm.state.value.connectionError)
            assertEquals("j1", vm.state.value.job?.id)
            assertEquals("closed", vm.state.value.session.phase)
            assertEquals(0, writes)
            observing.cancel()
        }

    @Test
    fun invalidSavedTokenStopsRetriesUntilSettingsAreUpdated() =
        runTest(dispatcher) {
            val rejected =
                FakeClient(saved.value.first).apply {
                    response = { _, _ -> throw ApiException(401, "expired") }
                }
            clients[rejected.base] = rejected
            val observing = backgroundScope.launch { vm.observe() }
            runCurrent()
            assertTrue(vm.state.value.needsCredentials)
            advanceTimeBy(60_000)
            runCurrent()
            assertEquals(1, rejected.requests)
            val corrected = FakeClient(saved.value.first)
            clients[corrected.base] = corrected
            vm.connect(corrected.base, "replacement")
            runCurrent()
            assertTrue(vm.state.value.connected)
            assertFalse(vm.state.value.needsCredentials)
            assertEquals("replacement", saved.value.second)
            observing.cancel()
        }

    @Test
    fun backgroundCancelsPendingAutomaticConnectionAndResumeRetries() =
        runTest(dispatcher) {
            val pending = CompletableDeferred<String>()
            val client =
                FakeClient(saved.value.first).apply { response = { _, _ -> pending.await() } }
            clients[client.base] = client
            val observing = backgroundScope.launch { vm.observe() }
            runCurrent()
            assertTrue(vm.state.value.connecting)
            observing.cancel()
            runCurrent()
            assertTrue(client.closed)
            assertFalse(vm.state.value.busy)
            assertFalse(vm.state.value.connecting)
            assertNull(vm.state.value.connectionError)
            clients[client.base] = FakeClient(client.base)
            val resumed = backgroundScope.launch { vm.observe() }
            runCurrent()
            assertTrue(vm.state.value.connected)
            resumed.cancel()
        }

    private class FakeClient(override val base: String) : ApplicationClient {
        var closed = false
        var requests = 0
        var response: suspend (String, JSONObject?) -> String = { _, _ -> snapshot(base) }
        val outputs = mutableListOf<(String) -> Unit>()

        override suspend fun request(path: String, body: JSONObject?): String {
            requests++
            return response(path, body)
        }

        override fun close() {
            closed = true
        }

        override fun terminal(host: String, onOutput: (String) -> Unit): WebSocket {
            outputs += onOutput
            return object : WebSocket {
                override fun request() = Request.Builder().url(base).build()

                override fun queueSize() = 0L

                override fun send(text: String) = true

                override fun send(bytes: ByteString) = true

                override fun close(code: Int, reason: String?) = true

                override fun cancel() {}
            }
        }
    }

    companion object {
        private fun snapshot(name: String) =
            """{"mode":"demo","hosts":[],"services":[],"backups":[],"jobs":[],"destination":"$name"}"""
    }
}
