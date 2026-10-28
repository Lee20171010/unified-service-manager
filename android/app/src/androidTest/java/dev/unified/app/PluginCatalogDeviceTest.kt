package dev.unified.app

import android.content.Context
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PluginCatalogDeviceTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun catalogStatusAndPinnedInstallUseCentralApplication() {
        check(
            ApplicationProvider.getApplicationContext<Context>().packageName ==
                "dev.unified.app.acceptance"
        )
        val checksum = "a".repeat(64)
        val snapshot =
            parseSnapshot(
                """{"mode":"ssh","hosts":[],"services":[],"backups":[],"jobs":[],"destination":"Fixture","plugins":[{"id":"billion-context","label":"billion-context","category":"package-management","version":"1.1.0","source":"github","artifact_checksum":"$checksum","description":"Fixture","available":true}],"plugin_catalog":{"checked":123,"error":"Offline fixture","refreshing":false}}"""
            )
        var submitted: Pair<String, JSONObject>? = null
        compose.setContent {
            MaterialTheme {
                UnifiedScreen(
                    UiState(snapshot = snapshot, connected = true),
                    "https://fixture.test" to "fixture-token",
                    { _, _ -> },
                    { path, body, done ->
                        submitted = path to body
                        done()
                    },
                    {},
                    {},
                    {},
                )
            }
        }
        compose.onNodeWithText("插件").performClick()
        compose.onNodeWithText("Offline fixture").assertExists()
        compose.onNodeWithText("檢查插件更新").performClick()
        assertEquals("/plugin-catalog/refresh", submitted?.first)
        compose.onNodeWithText("GitHub 官方").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Install").performScrollTo().performClick()
        assertEquals("/plugins/billion-context", submitted?.first)
        assertEquals("1.1.0", submitted?.second?.getString("version"))
        assertEquals(checksum, submitted?.second?.getString("checksum"))
        assertEquals("install", submitted?.second?.getString("action"))
    }
}
