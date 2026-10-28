package dev.unified.app

import android.content.Context
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.DpSize
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class WorkspaceLayoutDeviceTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun emptyWideWorkspaceAndExplicitHostKey() {
        check(
            ApplicationProvider.getApplicationContext<Context>().packageName ==
                "dev.unified.app.acceptance"
        )
        var submitted: JSONObject? = null
        compose.setContent {
            DeviceConfigurationOverride(
                DeviceConfigurationOverride.WindowSize(DpSize(820.dp, 900.dp))
            ) {
                UnifiedTheme(ThemeMode.Dark) {
                    UnifiedScreen(
                        UiState(
                            snapshot =
                                Snapshot(
                                    "demo",
                                    emptyList(),
                                    emptyList(),
                                    emptyList(),
                                    emptyList(),
                                    "Fixture",
                                ),
                            connected = true,
                        ),
                        "https://fixture.test" to "fixture-token",
                        { _, _ -> },
                        { path, body, done ->
                            assertEquals("/hosts", path)
                            submitted = body
                            done()
                        },
                        {},
                        {},
                        {},
                    )
                }
            }
        }
        compose.onNodeWithTag("single-pane").assertIsDisplayed()
        compose.onNodeWithText("選擇一個項目查看詳情").assertDoesNotExist()
        compose.onNode(hasText("主機") and hasClickAction()).performClick()
        compose.onNodeWithTag("single-pane").assertIsDisplayed()
        compose.onNodeWithContentDescription("新增").performClick()
        compose.onNodeWithText("主機名稱").performScrollTo().performTextInput("Fixture")
        compose.onNodeWithText("IP / DNS 位址").performScrollTo().performTextInput("fixture.test")
        compose.onNodeWithText("確認").assertIsNotEnabled()
        compose.onNodeWithText("私鑰檔案名稱").performScrollTo().performTextInput("fixture_key")
        compose.onNodeWithText("確認").performClick()
        assertEquals("fixture_key", submitted?.getString("key"))
    }
}
