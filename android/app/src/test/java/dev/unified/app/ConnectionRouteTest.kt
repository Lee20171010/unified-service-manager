package dev.unified.app

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import okhttp3.WebSocket
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28], qualifiers = "w320dp-h891dp")
class ConnectionRouteTest {
    @get:Rule val compose = createComposeRule()
    private val owner = ViewModelStore()

    @After
    fun cleanup() {
        compose.runOnIdle { owner.clear() }
    }

    @Test
    fun editAndSwitchServerPersistsAcceptedConnection() {
        val credentials =
            object : ConnectionStore {
                var value = "" to ""

                override fun hasSavedConnection() = value.first.isNotBlank()

                override fun read() = value

                override fun save(base: String, token: String) {
                    value = base to token
                }
            }
        credentials.save("https://old.example.test", "fixture-old")
        val vm =
            ViewModelProvider(
                owner,
                object : ViewModelProvider.Factory {
                    @Suppress("UNCHECKED_CAST")
                    override fun <T : androidx.lifecycle.ViewModel> create(
                        modelClass: Class<T>
                    ): T = MainViewModel(credentials) { base, _ -> FixtureClient(base) } as T
                },
            )[MainViewModel::class.java]
        compose.setContent { UnifiedTheme(ThemeMode.System) { AppRoute(vm, ThemeMode.System) {} } }
        compose.waitUntil(10_000) { vm.state.value.connected }
        compose.onNodeWithContentDescription("伺服器：old.example.test").performClick()
        compose.onNodeWithText("編輯連線").performClick()
        compose.onNodeWithText("HTTPS 伺服器網址").performTextReplacement("https://new.example.test")
        compose.onNodeWithText("管理員 Token").performTextReplacement("fixture-new")
        compose.onNodeWithText("儲存並連線").performClick()
        compose.waitUntil(10_000) { vm.connection.first == "https://new.example.test" }
        compose.onNodeWithContentDescription("伺服器：new.example.test").assertIsDisplayed()
        compose.onNodeWithText("儲存並連線").assertDoesNotExist()
        assertEquals("https://new.example.test" to "fixture-new", credentials.read())
        compose.onNodeWithContentDescription("伺服器：new.example.test").performClick()
        compose.onNodeWithText("https://new.example.test").assertIsDisplayed()
    }

    private class FixtureClient(override val base: String) : ApplicationClient {
        override suspend fun request(path: String, body: JSONObject?): String =
            """{"mode":"ssh","hosts":[],"services":[],"backups":[],"jobs":[],"destination":"Fixture"}"""

        override fun terminal(host: String, onOutput: (String) -> Unit): WebSocket =
            error("Terminal is outside this test")

        override fun close() {}
    }
}
