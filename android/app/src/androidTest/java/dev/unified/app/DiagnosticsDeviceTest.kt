package dev.unified.app

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** The device script induces an OS crash of the isolated package before this test. */
@RunWith(AndroidJUnit4::class)
class DiagnosticsDeviceTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun previousProcessCrashIsAvailableForExportAfterRestart() {
        check(
            ApplicationProvider.getApplicationContext<android.content.Context>().packageName ==
                "dev.unified.app.acceptance"
        )
        val report = Diagnostics.export()
        assertTrue(report.contains("UNCAUGHT"))
        assertTrue(report.contains("PREVIOUS_EXIT"))
        assertFalse(report.contains("fixture-old"))
        assertFalse(report.contains("fixture-new"))
        compose.setContent { UnifiedTheme(ThemeMode.System) { DiagnosticsDialog({}) } }
        compose.onNodeWithText("匯出 .txt").assertIsDisplayed()
        compose.waitUntil(10_000) {
            compose
                .onAllNodesWithText("UNCAUGHT", substring = true)
                .fetchSemanticsNodes()
                .isNotEmpty()
        }
    }
}
