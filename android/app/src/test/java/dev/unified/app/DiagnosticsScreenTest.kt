package dev.unified.app

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28], qualifiers = "w320dp-h891dp", application = android.app.Application::class)
class DiagnosticsScreenTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun diagnosticsEntryWorksWithoutAConnection() {
        var opened = false
        compose.setContent {
            MaterialTheme {
                ConnectionDialog(
                    "" to "",
                    false,
                    null,
                    {},
                    { _, _ -> },
                    onDiagnostics = { opened = true },
                )
            }
        }
        compose.onNodeWithText("診斷日誌").performClick()
        assertTrue(opened)
    }

    @Test
    fun previewAndClearDoNotNeedServerAccess() {
        var content = "Fixture diagnostic event"
        compose.setContent {
            MaterialTheme { DiagnosticsDialog({}, { content }, { content = "" }) }
        }
        compose.waitUntil(10_000) {
            compose
                .onAllNodesWithText("Fixture diagnostic event")
                .fetchSemanticsNodes()
                .isNotEmpty()
        }
        compose.onNodeWithText("匯出 .txt").assertIsEnabled()
        compose.onNodeWithText("分享").assertIsEnabled()
        compose.onNodeWithText("清除日誌").performClick()
        compose.waitUntil(10_000) {
            compose.onAllNodesWithText("診斷日誌已清除。").fetchSemanticsNodes().isNotEmpty()
        }
        assertEquals("", content)
        compose.onNodeWithText("Fixture diagnostic event").assertDoesNotExist()
    }
}
