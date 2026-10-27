package dev.unified.app

import android.content.Context
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28], qualifiers = "w411dp-h891dp")
class ThemeTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun preferenceDefaultsToSystemAndSurvivesReopening() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val raw = context.getSharedPreferences("appearance", Context.MODE_PRIVATE)
        raw.edit().clear().commit()
        assertEquals(ThemeMode.System, ThemePreferences(context).read())
        ThemeMode.entries.forEach { choice ->
            ThemePreferences(context).write(choice)
            assertEquals(choice, ThemePreferences(context).read())
        }
        raw.edit().putString("mode", "unknown").commit()
        assertEquals(ThemeMode.System, ThemePreferences(context).read())
    }

    @Test
    fun appearanceControlsSwitchPaletteAndSystemRemainsLive() {
        var mode by mutableStateOf(ThemeMode.System)
        var systemDark by mutableStateOf(false)
        var background = Color.Unspecified
        compose.setContent {
            UnifiedTheme(mode, systemDark) {
                val color = MaterialTheme.colorScheme.background
                SideEffect { background = color }
                UnifiedScreen(
                    UiState(),
                    "" to "",
                    { _, _ -> },
                    { _, _, _ -> },
                    {},
                    {},
                    {},
                    mode,
                    { mode = it },
                )
            }
        }
        compose.onNodeWithContentDescription("外觀模式").performClick()
        compose.onNodeWithText("跟隨系統").assertIsSelected()
        val light = compose.runOnIdle { background }
        compose.runOnIdle { systemDark = true }
        val dark = compose.runOnIdle { background }
        assertNotEquals(light, dark)
        compose.onNodeWithText("淺色").performClick().assertIsSelected()
        compose.runOnIdle { assertEquals(light, background) }
        compose.onNodeWithText("深色").performClick().assertIsSelected()
        compose.runOnIdle { systemDark = false }
        compose.runOnIdle { assertEquals(dark, background) }
        compose.onNodeWithText("跟隨系統").performClick().assertIsSelected()
        compose.runOnIdle { assertEquals(light, background) }
        compose.onNodeWithText("完成").performClick()
        compose.onNodeWithText("跟隨系統").assertDoesNotExist()
    }
}
