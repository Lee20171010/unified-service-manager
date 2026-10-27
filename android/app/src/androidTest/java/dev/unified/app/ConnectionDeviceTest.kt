package dev.unified.app

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.delay
import okhttp3.WebSocket
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Synthetic responses and a refused loopback connection; no external server or user credentials.
 */
@RunWith(AndroidJUnit4::class)
class ConnectionDeviceTest {
    @get:Rule val compose = createComposeRule()
    private val owner = ViewModelStore()

    @After
    fun cleanup() {
        compose.runOnIdle { owner.clear() }
    }

    @Test
    fun editAndSwitchServerPersistsAcceptedConnection() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        check(context.packageName == "dev.unified.app.acceptance") {
            "Build with -PisolatedDeviceTest=true; device tests must not touch the installed app"
        }
        val credentials = Credentials(context)
        credentials.save("https://old.example.test", "fixture-old")
        val vm =
            ViewModelProvider(
                owner,
                object : ViewModelProvider.Factory {
                    @Suppress("UNCHECKED_CAST")
                    override fun <T : androidx.lifecycle.ViewModel> create(
                        modelClass: Class<T>
                    ): T =
                        MainViewModel(credentials) { base, token ->
                            if (base == "https://127.0.0.1:1") Api(base, token)
                            else FixtureClient(base, token)
                        }
                            as T
                },
            )[MainViewModel::class.java]
        compose.setContent { UnifiedTheme(ThemeMode.System) { AppRoute(vm, ThemeMode.System) {} } }
        compose.waitUntil(10_000) { vm.state.value.connected }
        compose.onNodeWithContentDescription("伺服器：old.example.test").performClick()
        compose.onNodeWithText("編輯連線").performClick()
        compose
            .onNodeWithText("HTTPS 伺服器網址")
            .performClick()
            .performTextReplacement("https://127.0.0.1:1")
        compose.onNodeWithText("儲存並連線").performClick()
        compose.waitUntil(20_000) { vm.state.value.error != null && !vm.state.value.busy }
        assertTrue(vm.state.value.connected)
        assertEquals("https://old.example.test" to "fixture-old", credentials.read())
        compose
            .onNodeWithText("HTTPS 伺服器網址")
            .performClick()
            .performTextReplacement("https://new.example.test")
        compose.onNodeWithText("管理員 Token").performClick().performTextReplacement("fixture-wrong")
        compose.onNodeWithText("儲存並連線").performClick()
        compose.waitUntil(10_000) {
            vm.state.value.error == "HTTP 401: Unauthorized" && !vm.state.value.busy
        }
        compose.onNodeWithText("HTTPS 伺服器網址").assertIsDisplayed()
        assertEquals("https://old.example.test" to "fixture-old", credentials.read())
        compose.onNodeWithText("管理員 Token").performClick().performTextReplacement("fixture-new")
        compose.onNodeWithText("儲存並連線").performClick()
        compose.waitUntil(10_000) { vm.connection.first == "https://new.example.test" }
        compose.onNodeWithContentDescription("伺服器：new.example.test").assertIsDisplayed()
        compose.onNodeWithText("儲存並連線").assertDoesNotExist()
        assertEquals("https://new.example.test" to "fixture-new", credentials.read())
        compose.onNodeWithContentDescription("伺服器：new.example.test").performClick()
        compose.onNodeWithText("https://new.example.test").assertIsDisplayed()
        compose.onNodeWithText("診斷日誌").performClick()
        compose.onNodeWithText("匯出 .txt").assertIsDisplayed()
        compose.waitUntil(10_000) {
            compose
                .onAllNodesWithText("CONNECT_FAILED", substring = true)
                .fetchSemanticsNodes()
                .isNotEmpty()
        }
        val report = Diagnostics.export()
        assertTrue(report.contains("CONNECT_OK"))
        assertTrue(!report.contains("fixture-new") && !report.contains("new.example.test"))
    }

    private class FixtureClient(override val base: String, val token: String) : ApplicationClient {
        override suspend fun request(path: String, body: JSONObject?): String {
            delay(250)
            if (token == "fixture-wrong") throw ApiException(401, "HTTP 401: Unauthorized")
            return """{"mode":"ssh","hosts":[],"services":[],"backups":[],"jobs":[],"destination":"Fixture"}"""
        }

        override fun terminal(host: String, onOutput: (String) -> Unit): WebSocket =
            error("Terminal is outside this test")

        override fun close() {}
    }
}
