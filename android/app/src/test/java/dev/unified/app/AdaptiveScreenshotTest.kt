package dev.unified.app

import android.graphics.Bitmap
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.DpSize
import androidx.compose.ui.unit.dp
import java.io.File
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Deterministic review captures; reference images are approved separately, never overwritten. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w1200dp-h1000dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class AdaptiveScreenshotTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun capturePhoneFoldableAndTabletWithSameSelection() {
        var size by mutableStateOf(DpSize(390.dp, 844.dp))
        var theme by mutableStateOf(ThemeMode.Light)
        val snapshot =
            Snapshot(
                "demo",
                listOf(
                    Host(
                        "fixture",
                        "Demo host",
                        "host.example.test",
                        22,
                        "unified",
                        "fixture-key",
                        "online",
                    )
                ),
                listOf(
                    Service(
                        "service",
                        "Example service",
                        "fixture",
                        "/demo/service",
                        "1.0.0",
                        "online",
                        0,
                    )
                ),
                emptyList(),
                emptyList(),
                "Fixture storage",
            )
        compose.setContent {
            DeviceConfigurationOverride(DeviceConfigurationOverride.WindowSize(size)) {
                UnifiedTheme(theme) {
                    UnifiedScreen(
                        UiState(snapshot = snapshot, connected = true),
                        "https://demo.example.test" to "fixture-token",
                        { _, _ -> },
                        { _, _, _ -> },
                        {},
                        {},
                        {},
                    )
                }
            }
        }
        compose.onNode(hasText("主機") and hasClickAction()).performClick()
        capture("phone-list")
        compose.onNodeWithText("主機詳情 →").performClick()
        compose.onNodeWithText("主機詳情").assertIsDisplayed()
        capture("phone-detail")
        compose.runOnIdle { size = DpSize(820.dp, 900.dp) }
        compose.onNodeWithText("主機詳情 →").assertIsDisplayed()
        compose.onNodeWithText("主機詳情").assertIsDisplayed()
        capture("fold-open-light")
        compose.runOnIdle { theme = ThemeMode.Dark }
        capture("fold-open-dark")
        compose.runOnIdle { size = DpSize(1200.dp, 800.dp) }
        capture("tablet-landscape")
        compose.runOnIdle { size = DpSize(390.dp, 844.dp) }
        compose.onNodeWithContentDescription("返回列表").assertIsDisplayed()
        capture("fold-closed-detail")
        compose.onNodeWithText("插件").performClick()
        capture("plugins-phone")
        compose.runOnIdle { size = DpSize(820.dp, 900.dp) }
        capture("plugins-wide")
    }

    private fun capture(name: String) {
        val file = File("build/reports/adaptive-screenshots/$name.png")
        requireNotNull(file.parentFile).mkdirs()
        compose.onNodeWithTag("unified-screen").captureToImage().asAndroidBitmap().let { bitmap ->
            file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        }
    }
}
