package dev.unified.app

import java.net.InetAddress
import java.net.Socket
import java.util.concurrent.CopyOnWriteArrayList
import javax.net.SocketFactory
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.tls.HandshakeCertificates
import okhttp3.tls.HeldCertificate
import org.junit.Assert.*
import org.junit.Test

class ApiCloseTest {
    @Test fun closesPooledHttpsSocketOffCallerAfter502() = verifyClose(502)

    @Test fun closesPooledHttpsSocketOffCallerAfterSuccess() = verifyClose(200)

    private fun verifyClose(status: Int) = runTest {
        val owner = Thread.currentThread()
        val socketCloseThreads = CopyOnWriteArrayList<Thread>()
        val certificate = HeldCertificate.Builder().addSubjectAlternativeName("localhost").build()
        val serverTls = HandshakeCertificates.Builder().heldCertificate(certificate).build()
        val clientTls =
            HandshakeCertificates.Builder().addTrustedCertificate(certificate.certificate).build()
        val server = MockWebServer()
        server.useHttps(serverTls.sslSocketFactory(), false)
        server.protocols = listOf(Protocol.HTTP_1_1)
        server.enqueue(MockResponse().setResponseCode(status).setBody("{}"))
        server.start(InetAddress.getLoopbackAddress(), 0)
        val http =
            OkHttpClient.Builder()
                .sslSocketFactory(clientTls.sslSocketFactory(), clientTls.trustManager)
                .socketFactory(
                    object : SocketFactory() {
                        override fun createSocket(): Socket =
                            object : Socket() {
                                override fun close() {
                                    socketCloseThreads += Thread.currentThread()
                                    super.close()
                                }
                            }

                        override fun createSocket(host: String, port: Int): Socket =
                            error("Unused fixture path")

                        override fun createSocket(
                            host: String,
                            port: Int,
                            local: InetAddress,
                            localPort: Int,
                        ): Socket = error("Unused fixture path")

                        override fun createSocket(host: InetAddress, port: Int): Socket =
                            error("Unused fixture path")

                        override fun createSocket(
                            host: InetAddress,
                            port: Int,
                            local: InetAddress,
                            localPort: Int,
                        ): Socket = error("Unused fixture path")
                    }
                )
                .protocols(listOf(Protocol.HTTP_1_1))
                .retryOnConnectionFailure(false)
                .build()
        val api = Api(server.url("/").toString().trimEnd('/'), "fixture-token", http)
        try {
            try {
                assertEquals("{}", api.request("/snapshot"))
                assertEquals(200, status)
            } catch (error: ApiException) {
                assertEquals(status, error.statusCode)
            }
            assertEquals(1, http.connectionPool.idleConnectionCount())
            assertSame(owner, Thread.currentThread())
            api.close()
            api.close()
            withContext(Dispatchers.IO) {
                withTimeout(5000) {
                    while (
                        http.connectionPool.connectionCount() != 0 || socketCloseThreads.isEmpty()
                    ) delay(10)
                }
            }
            assertFalse(
                "TLS pool cleanup ran on the calling/UI thread",
                socketCloseThreads.any { it === owner },
            )
            try {
                api.request("/snapshot")
                fail("Closed client accepted another request")
            } catch (_: IllegalStateException) {
                // The closed client must not create another socket.
            }
            assertThrows(IllegalStateException::class.java) { api.terminal("fixture") {} }
            assertEquals(1, server.requestCount)
        } finally {
            withContext(Dispatchers.IO) {
                http.dispatcher.cancelAll()
                http.connectionPool.evictAll()
                http.dispatcher.executorService.shutdown()
                server.shutdown()
            }
        }
    }
}
