package dev.unified.app

import java.io.IOException
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine
import okhttp3.*
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class ApiException(val statusCode: Int, message: String) : IOException(message)

/** Only HTTP/WS transport. Operation policy lives on Application Layer. */
interface ApplicationClient {
    val base: String

    suspend fun request(path: String, body: JSONObject? = null): String

    fun terminal(host: String, onOutput: (String) -> Unit): WebSocket

    fun close()
}

class Api
internal constructor(
    override val base: String,
    private val token: String,
    private val http: OkHttpClient,
) : ApplicationClient {
    constructor(
        base: String,
        token: String,
    ) : this(
        base,
        token,
        OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .retryOnConnectionFailure(false)
            .followRedirects(false)
            .build(),
    )

    private val closed = AtomicBoolean(false)

    init {
        val url = base.toHttpUrl()
        require(
            url.isHttps &&
                url.username.isEmpty() &&
                url.password.isEmpty() &&
                url.query == null &&
                url.fragment == null
        ) {
            "請使用不含帳密的 HTTPS 伺服器網址"
        }
    }

    override suspend fun request(path: String, body: JSONObject?): String =
        suspendCancellableCoroutine { continuation ->
            check(!closed.get()) { "HTTP client is closed" }
            val request =
                Request.Builder()
                    .url(base.trimEnd('/') + "/api/v1" + path)
                    .header("Authorization", "Bearer $token")
            if (body != null)
                request.post(body.toString().toRequestBody("application/json".toMediaType()))
            val call = http.newCall(request.build())
            continuation.invokeOnCancellation { call.cancel() }
            call.enqueue(
                object : Callback {
                    override fun onFailure(call: Call, e: IOException) {
                        if (continuation.isActive) continuation.resumeWithException(e)
                    }

                    override fun onResponse(call: Call, response: Response) {
                        response.use {
                            try {
                                val text = it.body?.string().orEmpty()
                                if (!it.isSuccessful) {
                                    val detail =
                                        try {
                                            JSONObject(text).optString("detail")
                                        } catch (_: Exception) {
                                            ""
                                        }
                                    throw ApiException(
                                        it.code,
                                        "HTTP ${it.code}: ${detail.take(400)}",
                                    )
                                }
                                if (continuation.isActive) continuation.resume(text)
                            } catch (e: Exception) {
                                if (continuation.isActive) continuation.resumeWithException(e)
                            }
                        }
                    }
                }
            )
        }

    override fun terminal(host: String, onOutput: (String) -> Unit): WebSocket {
        check(!closed.get()) { "HTTP client is closed" }
        return http.newWebSocket(
            Request.Builder()
                .url(
                    base.trimEnd('/').replaceFirst("https://", "wss://") +
                        "/api/v1/hosts/$host/terminal"
                )
                .build(),
            object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    webSocket.send(JSONObject().put("token", token).toString())
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    try {
                        onOutput(JSONObject(text).optString("text"))
                    } catch (_: Exception) {
                        onOutput("\n無法讀取終端訊息\n")
                    }
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    onOutput("\n[連線中斷：${t.javaClass.simpleName}]\n")
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    onOutput("\n[工作階段已結束]\n")
                }
            },
        )
    }

    override fun close() {
        if (!closed.compareAndSet(false, true)) return
        // TLS close can write close_notify. The transport owns cleanup even after UI cancellation.
        http.dispatcher.executorService.execute {
            http.dispatcher.cancelAll()
            http.connectionPool.evictAll()
        }
    }
}
