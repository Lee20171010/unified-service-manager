package dev.unified.app

import android.content.Context
import android.os.StrictMode
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.net.InetAddress
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicBoolean
import okhttp3.ConnectionPool
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import okhttp3.tls.HandshakeCertificates
import okhttp3.tls.HeldCertificate
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class HttpsRecoveryDeviceTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun pooledHttps502AtColdStartRecoversUnderMainThreadNetworkPolicy() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        check(context.packageName == "dev.unified.app.acceptance")
        val owner = ViewModelStore()
        val ready = AtomicBoolean(false)
        val clients = CopyOnWriteArrayList<OkHttpClient>()
        val certificate =
            HeldCertificate.Builder()
                .addSubjectAlternativeName("localhost")
                .addSubjectAlternativeName("127.0.0.1")
                .addSubjectAlternativeName("::1")
                .build()
        val serverTls = HandshakeCertificates.Builder().heldCertificate(certificate).build()
        val clientTls =
            HandshakeCertificates.Builder().addTrustedCertificate(certificate.certificate).build()
        val server = MockWebServer()
        server.useHttps(serverTls.sslSocketFactory(), false)
        server.protocols = listOf(Protocol.HTTP_1_1)
        server.dispatcher =
            object : okhttp3.mockwebserver.Dispatcher() {
                override fun dispatch(request: RecordedRequest): MockResponse =
                    if (ready.get())
                        MockResponse()
                            .setBody(
                                """{"mode":"ssh","hosts":[],"services":[],"backups":[],"jobs":[],"destination":"Fixture"}"""
                            )
                    else MockResponse().setResponseCode(502).setBody("updating")
            }
        server.start(InetAddress.getByName("127.0.0.1"), 0)
        val credentials = Credentials(context)
        val base = server.url("/").newBuilder().host("127.0.0.1").build().toString().trimEnd('/')
        credentials.save(base, "fixture-token")
        val vm =
            ViewModelProvider(
                owner,
                object : ViewModelProvider.Factory {
                    @Suppress("UNCHECKED_CAST")
                    override fun <T : androidx.lifecycle.ViewModel> create(
                        modelClass: Class<T>
                    ): T =
                        MainViewModel(credentials) { url, token ->
                            val http =
                                OkHttpClient.Builder()
                                    .sslSocketFactory(
                                        clientTls.sslSocketFactory(),
                                        clientTls.trustManager,
                                    )
                                    .connectionPool(ConnectionPool())
                                    .protocols(listOf(Protocol.HTTP_1_1))
                                    .retryOnConnectionFailure(false)
                                    .followRedirects(false)
                                    .build()
                            clients += http
                            Api(url, token, http)
                        }
                            as T
                },
            )[MainViewModel::class.java]
        var originalPolicy: StrictMode.ThreadPolicy? = null
        try {
            compose.runOnIdle {
                originalPolicy = StrictMode.getThreadPolicy()
                StrictMode.setThreadPolicy(
                    StrictMode.ThreadPolicy.Builder(originalPolicy!!)
                        .detectNetwork()
                        .penaltyDeathOnNetwork()
                        .build()
                )
            }
            compose.setContent {
                UnifiedTheme(ThemeMode.System) { AppRoute(vm, ThemeMode.System) {} }
            }
            compose.waitUntil(15_000) {
                vm.state.value.connectionError != null && !vm.state.value.busy
            }
            assertTrue(
                "Expected fixture 502, got ${vm.state.value.connectionError}; requests=${server.requestCount}",
                vm.state.value.connectionError?.startsWith("HTTP 502") == true,
            )
            assertFalse(vm.state.value.connected)
            assertFalse(vm.state.value.needsCredentials)
            assertEquals(base to "fixture-token", credentials.read())
            compose.waitUntil(5000) { clients.first().connectionPool.connectionCount() == 0 }
            ready.set(true)
            compose.waitUntil(15_000) { vm.state.value.connected }
            assertNull(vm.state.value.connectionError)
            assertEquals(base to "fixture-token", credentials.read())
            assertTrue(server.requestCount >= 2)
            // Clearing the ViewModel also closes a successful pooled TLS connection.
            compose.runOnIdle { owner.clear() }
            compose.waitUntil(5000) { clients.all { it.connectionPool.connectionCount() == 0 } }
        } finally {
            compose.runOnIdle {
                owner.clear()
                originalPolicy?.let(StrictMode::setThreadPolicy)
            }
            clients.forEach {
                it.dispatcher.cancelAll()
                it.connectionPool.evictAll()
                it.dispatcher.executorService.shutdown()
            }
            server.shutdown()
        }
    }
}
