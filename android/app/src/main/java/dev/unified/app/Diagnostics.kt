package dev.unified.app

import android.app.ActivityManager
import android.app.Application
import android.content.Context
import android.os.Build
import android.util.AtomicFile
import java.io.File
import java.time.Instant
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit

internal enum class DiagnosticEvent {
    APP_START,
    ACTIVITY_CREATE,
    ACTIVITY_START,
    ACTIVITY_STOP,
    CONNECT_MANUAL,
    CONNECT_AUTO,
    VALIDATE_ADDRESS,
    FETCH_SNAPSHOT,
    PARSE_SNAPSHOT,
    SAVE_CREDENTIALS,
    ACTIVATE_CONNECTION,
    CONNECT_OK,
    CONNECT_FAILED,
    CONNECT_CANCELLED,
    POLL_FAILED,
    POLL_RECOVERED,
    UNCAUGHT,
    PREVIOUS_EXIT,
}

/** No free-form messages, URLs, credentials, response bodies or stack filenames enter storage. */
internal class DiagnosticStore(private val file: File) {
    private val entries = ArrayDeque<String>()
    private val disk = AtomicFile(file)

    init {
        runCatching {
            if (file.length() <= MAX_BYTES) {
                disk.openRead().bufferedReader().useLines { lines ->
                    lines.forEach { line ->
                        if (line.length <= MAX_ENTRY && VALID_LINE.matches(line))
                            entries.addLast(line)
                    }
                }
                trim()
            }
        }
    }

    @Synchronized
    fun append(event: DiagnosticEvent, error: Throwable? = null, number: Int? = null) {
        val details = buildString {
            fun field(value: String) {
                if (length + value.length <= MAX_ENTRY - 80) append(value)
            }
            if (number != null) field(" number=$number")
            if (error is ApiException && error.statusCode in 100..599)
                field(" http=${error.statusCode}")
            var cause = error
            repeat(3) {
                val current = cause ?: return@repeat
                field(" exception=${safeClass(current.javaClass.name)}")
                current.stackTrace.take(8).forEach { frame ->
                    val method = frame.methodName.takeIf { METHOD.matches(it) } ?: "unknown"
                    field(" at=${safeClass(frame.className)}#$method:${frame.lineNumber}")
                }
                cause = current.cause.takeUnless { it === current }
            }
        }
        entries.addLast("${Instant.now()} ${event.name}$details")
        trim()
    }

    @Synchronized fun snapshot(): String = entries.joinToString("\n")

    // Serialize clear and flush together: a queued writer can never restore cleared entries.
    @Synchronized
    fun clear() {
        entries.clear()
        persist()
    }

    @Synchronized
    fun persist() {
        file.parentFile?.mkdirs()
        val output = disk.startWrite()
        try {
            output.write(snapshot().toByteArray(Charsets.UTF_8))
            disk.finishWrite(output)
        } catch (error: Throwable) {
            disk.failWrite(output)
            throw error
        }
    }

    private fun trim() {
        while (entries.size > 200 || entries.sumOf { it.length + 1 } > MAX_BYTES) entries
            .removeFirst()
    }

    companion object {
        const val MAX_BYTES = 64 * 1024
        private const val MAX_ENTRY = 4096
        private val SYMBOL = Regex("[A-Za-z_$][A-Za-z0-9_$.]{0,79}")
        private val METHOD = Regex("(?:[A-Za-z_$][A-Za-z0-9_$-]{0,59}|<init>|<clinit>)")
        private val CLASS =
            "(?:android|androidx|java|javax|kotlin|kotlinx|okhttp3|okio|dev\\.unified\\.app|com\\.android)\\.[A-Za-z0-9_$.]+"
        private val VALID_LINE =
            Regex(
                "[0-9T:.Z-]{20,35} (?:${DiagnosticEvent.entries.joinToString("|") { it.name }})" +
                    "(?: number=-?[0-9]{1,11})?(?: http=[1-5][0-9]{2})?" +
                    "(?: exception=(?:$CLASS|other.Exception)(?: at=(?:$CLASS|other.Exception)#[A-Za-z0-9_$<>-]+:-?[0-9]{1,11})*)*"
            )

        private fun safeClass(value: String): String =
            if (SYMBOL.matches(value) && Regex(CLASS).matches(value)) value else "other.Exception"
    }
}

internal class DiagnosticCrashHandler(
    private val capture: (Throwable) -> Unit,
    private val delegate: Thread.UncaughtExceptionHandler,
) : Thread.UncaughtExceptionHandler {
    override fun uncaughtException(thread: Thread, error: Throwable) {
        try {
            capture(error)
        } catch (_: Throwable) {
            /* Reporting must never replace the original crash. */
        } finally {
            delegate.uncaughtException(thread, error)
        }
    }
}

internal object Diagnostics {
    @Volatile private var store: DiagnosticStore? = null
    private val writer =
        ThreadPoolExecutor(
            1,
            1,
            30,
            TimeUnit.SECONDS,
            ArrayBlockingQueue(16),
            ThreadPoolExecutor.DiscardPolicy(),
        )

    fun initialize(context: Context) {
        runCatching {
            store = DiagnosticStore(File(context.noBackupFilesDir, "diagnostics/events.txt"))
        }
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        if (previous != null && previous !is DiagnosticCrashHandler) {
            Thread.setDefaultUncaughtExceptionHandler(
                DiagnosticCrashHandler(
                    { error ->
                        store?.append(DiagnosticEvent.UNCAUGHT, error)
                        store?.persist()
                    },
                    previous,
                )
            )
        }
        record(DiagnosticEvent.APP_START, number = BuildConfig.VERSION_CODE)
        if (Build.VERSION.SDK_INT >= 30) {
            runCatching {
                val manager = context.getSystemService(ActivityManager::class.java)
                manager
                    .getHistoricalProcessExitReasons(context.packageName, 0, 1)
                    .firstOrNull()
                    ?.let { record(DiagnosticEvent.PREVIOUS_EXIT, number = it.reason) }
            }
        }
    }

    fun record(event: DiagnosticEvent, error: Throwable? = null, number: Int? = null) {
        // Append in memory now so the fatal handler also sees events not yet flushed by the writer.
        try {
            store?.append(event, error, number)
            writer.execute { runCatching { store?.persist() } }
        } catch (_: Throwable) {
            /* Diagnostic storage failure must not change app behavior. */
        }
    }

    fun export(): String {
        val current = checkNotNull(store) { "Diagnostics unavailable" }
        return "Unified Android ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})\n" +
            "format=1 sdk=${Build.VERSION.SDK_INT}\n" +
            "Local events; exception messages, URLs, credentials and response bodies omitted.\n\n" +
            current.snapshot()
    }

    fun clear() = checkNotNull(store).clear()
}

class UnifiedApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        Diagnostics.initialize(this)
    }
}
