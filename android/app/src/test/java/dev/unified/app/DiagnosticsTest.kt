package dev.unified.app

import java.io.File
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28], application = android.app.Application::class)
class DiagnosticsTest {
    @get:Rule val temporary = TemporaryFolder()

    @Test
    fun crashReportPersistsCodeFramesWithoutMessagesOrPrivateFilenames() {
        val file = File(temporary.root, "events.txt")
        val store = DiagnosticStore(file)
        val secret = "Bearer private-token https://private.example.test /private/user/file"
        val cause =
            IllegalStateException(secret).apply {
                stackTrace =
                    arrayOf(
                        StackTraceElement(
                            "dev.unified.app.MainViewModel",
                            "connectWorkspace",
                            secret,
                            77,
                        )
                    )
            }
        val error = ApiException(401, secret).apply { initCause(cause) }
        store.append(DiagnosticEvent.FETCH_SNAPSHOT)
        var delegated: Throwable? = null
        DiagnosticCrashHandler(
                { failure ->
                    store.append(DiagnosticEvent.UNCAUGHT, failure)
                    store.persist()
                },
                Thread.UncaughtExceptionHandler { _, failure -> delegated = failure },
            )
            .uncaughtException(Thread.currentThread(), error)
        assertSame(error, delegated)
        val restored = DiagnosticStore(file).snapshot()
        assertTrue(restored.contains("FETCH_SNAPSHOT"))
        assertTrue(restored.contains("UNCAUGHT"))
        assertTrue(restored.contains("http=401"))
        assertTrue(restored.contains("java.lang.IllegalStateException"))
        assertTrue(restored.contains("dev.unified.app.MainViewModel#connectWorkspace:77"))
        listOf("private-token", "private.example.test", "/private/user/file", "Bearer").forEach {
            assertFalse(restored.contains(it))
        }
    }

    @Test
    fun failedCaptureStillDelegatesOriginalCrash() {
        val original = IllegalStateException("fixture")
        var delegated: Throwable? = null
        DiagnosticCrashHandler(
                { throw java.io.IOException("disk unavailable") },
                Thread.UncaughtExceptionHandler { _, error -> delegated = error },
            )
            .uncaughtException(Thread.currentThread(), original)
        assertSame(original, delegated)
    }

    @Test
    fun storageBoundsHistoryAndClearSurvivesQueuedPersistenceAndRestart() {
        val file = File(temporary.root, "events.txt")
        val store = DiagnosticStore(file)
        repeat(450) { store.append(DiagnosticEvent.CONNECT_MANUAL, number = it) }
        store.persist()
        assertEquals(200, DiagnosticStore(file).snapshot().lines().size)
        assertTrue(file.length() <= DiagnosticStore.MAX_BYTES)
        store.clear()
        store.persist()
        assertEquals("", DiagnosticStore(file).snapshot())
    }

    @Test
    fun oversizedAndInjectedFilesAreNotExported() {
        val file = File(temporary.root, "events.txt")
        file.writeText(
            "Bearer private-token\n2026-10-27T12:00:00Z CONNECT_FAILED url=https://private.example.test"
        )
        assertEquals("", DiagnosticStore(file).snapshot())
        file.writeText("x".repeat(DiagnosticStore.MAX_BYTES + 1))
        assertEquals("", DiagnosticStore(file).snapshot())
    }

    @Test
    fun longCauseChainsRemainValidAndBoundedAfterRestart() {
        val file = File(temporary.root, "events.txt")
        val store = DiagnosticStore(file)
        val error =
            IllegalStateException(
                "omit",
                IllegalStateException("omit", IllegalStateException("omit")),
            )
        var cause: Throwable? = error
        while (cause != null) {
            cause.stackTrace =
                Array(8) {
                    StackTraceElement(
                        "dev.unified.app." + "A".repeat(60),
                        "a".repeat(60),
                        "private",
                        Int.MIN_VALUE,
                    )
                }
            cause = cause.cause
        }
        repeat(200) { store.append(DiagnosticEvent.CONNECT_FAILED, error) }
        store.persist()
        assertTrue(file.length() <= DiagnosticStore.MAX_BYTES)
        assertEquals(store.snapshot(), DiagnosticStore(file).snapshot())
        assertFalse(store.snapshot().contains("private"))
    }
}
