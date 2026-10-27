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
class ResourceTest {
    @get:Rule val compose = createComposeRule()
    private val plugin =
        PluginInfo(
            "npm-packages",
            "npm 套件／CLI",
            "package-management",
            "1.0.0",
            "npm integration",
            null,
            false,
            false,
            true,
            emptyList(),
        )
    private val pkg =
        Service(
            "p",
            "Example CLI",
            "h",
            "",
            "1.0.0",
            "online",
            0,
            "npm-packages",
            "npm",
            operations = listOf("refresh", "install", "upgrade", "uninstall"),
            kind = "package",
        )
    private val snapshot =
        Snapshot(
            "demo",
            listOf(Host("h", "Fixture", "localhost", 22, "test", "key", "online")),
            listOf(pkg),
            emptyList(),
            emptyList(),
            "Demo",
            plugins = listOf(plugin),
        )
    private var submitted: Pair<String, JSONObject>? = null

    private fun screen() {
        compose.setContent {
            MaterialTheme {
                UnifiedScreen(
                    UiState(snapshot = snapshot, connected = true),
                    "" to "",
                    { _, _ -> },
                    { p, b, done ->
                        submitted = p to b
                        done()
                    },
                    {},
                    {},
                    {},
                )
            }
        }
    }

    @Test
    fun pluginInstallationUsesCentralEndpoint() {
        screen()
        compose.onNodeWithText("插件", useUnmergedTree = true).performClick()
        compose.onNodeWithText("Install").performScrollTo().performClick()
        assertEquals("/plugins/npm-packages", submitted?.first)
        assertEquals("install", submitted?.second?.getString("action"))
    }

    @Test
    fun packagesHaveNoServiceLifecycleAndUninstallNeedsConfirmation() {
        screen()
        compose.onNodeWithText("受管對象詳情與操作 →").performScrollTo().performClick()
        compose.onNodeWithText("啟動", substring = false).assertDoesNotExist()
        compose.onNodeWithText("卸載套件", substring = false).performScrollTo().performClick()
        compose.onNodeWithText("確認", substring = false).assertIsNotEnabled()
        compose.onNode(isToggleable()).performClick()
        compose.onNodeWithText("確認", substring = false).performClick()
        assertEquals("/resources/p/jobs", submitted?.first)
        assertTrue(submitted!!.second.getBoolean("confirm"))
        assertEquals("uninstall", submitted!!.second.getString("action"))
    }

    @Test
    fun consoleSendsInputAndCloseIsSeparate() {
        val inputs = mutableListOf<Pair<String, Boolean>>()
        var dismissed = false
        compose.setContent {
            MaterialTheme {
                JobConsole(
                    Job("j", "Example CLI", "upgrade", "running", "p", 0, 10, null),
                    emptyList(),
                    { dismissed = true },
                    { "" },
                    JobSession("running", "generation"),
                    false,
                    { text, close -> inputs += text to close },
                )
            }
        }
        compose.onNodeWithText("任務或 shell 輸入").performTextInput("yes")
        compose.onNodeWithText("送出", substring = false).performClick()
        assertEquals(listOf("yes\n" to false), inputs)
        compose.onNodeWithText("Ctrl+C").performClick()
        assertEquals("\u0003" to false, inputs.last())
        compose.onNodeWithText("關閉", substring = false).performClick()
        assertTrue(dismissed)
        assertEquals(2, inputs.size)
    }
}
