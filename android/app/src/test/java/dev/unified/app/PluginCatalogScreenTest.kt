package dev.unified.app

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28], qualifiers = "w411dp-h891dp")
class PluginCatalogScreenTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun catalogStatusAndPinnedInstallUseCentralApplication() {
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
        val status = compose.onNodeWithText("Offline fixture").getUnclippedBoundsInRoot()
        val refresh = compose.onNodeWithText("檢查插件更新").getUnclippedBoundsInRoot()
        assertTrue("Catalog error must not overlap refresh", status.bottom <= refresh.top)
        compose.onNodeWithText("檢查插件更新").performClick()
        assertEquals("/plugin-catalog/refresh", submitted?.first)
        compose.onNodeWithText("安裝狀態：全部").performScrollTo()
        val category = compose.onNodeWithText("插件分類：全部").getUnclippedBoundsInRoot()
        val installation = compose.onNodeWithText("安裝狀態：全部").getUnclippedBoundsInRoot()
        assertTrue("Plugin filters must not overlap", category.bottom <= installation.top)
        compose.onNodeWithText("GitHub 官方").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Install").performScrollTo().performClick()
        assertEquals("/plugins/billion-context", submitted?.first)
        assertEquals("1.1.0", submitted?.second?.getString("version"))
        assertEquals(checksum, submitted?.second?.getString("checksum"))
        assertEquals("install", submitted?.second?.getString("action"))
    }
}
