package dev.unified.app

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.StateRestorationTester
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.DpSize
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w1200dp-h1000dp")
class AdaptiveWorkspaceTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun resizingAndRestorationKeepSelectedDetailAndReturnToList() {
        var size by mutableStateOf(DpSize(390.dp, 844.dp))
        val restoration = StateRestorationTester(compose)
        restoration.setContent {
            DeviceConfigurationOverride(DeviceConfigurationOverride.WindowSize(size)) {
                UnifiedTheme(ThemeMode.Dark) {
                    var selected by rememberSaveable { mutableStateOf<String?>("fixture") }
                    AdaptiveWorkspace(
                        "hosts",
                        selected,
                        true,
                        { selected = null },
                        Modifier.fillMaxSize(),
                        detail = { _, wide ->
                            DetailPane("Fixture detail", wide, { selected = null }) {
                                Text("Selected host")
                            }
                        },
                    ) {
                        Box(Modifier.fillMaxSize()) { Text("Host list") }
                    }
                }
            }
        }
        compose.onNodeWithText("Selected host").assertIsDisplayed()
        compose.onNodeWithText("Host list").assertDoesNotExist()
        compose.onNodeWithContentDescription("返回列表").assertIsDisplayed()
        compose.runOnIdle { size = DpSize(780.dp, 844.dp) }
        compose.onNodeWithText("Host list").assertIsDisplayed()
        compose.onNodeWithText("Selected host").assertIsDisplayed()
        compose.onNodeWithContentDescription("返回列表").assertDoesNotExist()
        restoration.emulateSavedInstanceStateRestore()
        compose.onNodeWithText("Selected host").assertIsDisplayed()
        compose.runOnIdle { size = DpSize(390.dp, 844.dp) }
        compose.onNodeWithText("Host list").assertDoesNotExist()
        compose.onNodeWithContentDescription("返回列表").performClick()
        compose.onNodeWithText("Host list").assertIsDisplayed()
        compose.onNodeWithText("Selected host").assertDoesNotExist()
    }

    @Test
    fun retainedFormSurvivesRecreationWithoutSubmitting() {
        val drafts = WorkspaceDrafts()
        drafts.form.value = FormSpec("新增主機", "/hosts", listOf(FormField("name", "主機名稱")))
        var submissions = 0
        val restoration = StateRestorationTester(compose)
        restoration.setContent {
            UnifiedTheme(ThemeMode.Light) {
                FormDialog(drafts.form.value!!, false, null, {}) { submissions++ }
            }
        }
        compose.onNodeWithText("主機名稱").performTextInput("Fixture draft")
        restoration.emulateSavedInstanceStateRestore()
        compose.onNodeWithText("Fixture draft").assertExists()
        assertEquals(0, submissions)
        compose.onNodeWithText("確認").performClick()
        assertEquals(1, submissions)
    }

    @Test
    fun automaticConnectionDoesNotDismissAnEditedDraft() {
        var state by
            mutableStateOf(UiState(connectionConfigured = true, connecting = true, busy = true))
        compose.setContent {
            UnifiedTheme(ThemeMode.Light) {
                UnifiedScreen(
                    state,
                    "https://fixture.test" to "fixture-token",
                    { _, _ -> },
                    { _, _, _ -> },
                    {},
                    {},
                    {},
                )
            }
        }
        compose.onNodeWithContentDescription("伺服器：fixture.test").performClick()
        compose.onNodeWithText("HTTPS 伺服器網址").performTextReplacement("https://draft.example.test")
        compose.runOnIdle {
            state =
                state.copy(
                    connected = true,
                    connecting = false,
                    busy = false,
                    connectionVersion = 1,
                )
        }
        compose.onNodeWithText("HTTPS 伺服器網址").assertTextContains("https://draft.example.test")
        compose.onNodeWithText("儲存並連線").assertIsDisplayed()
    }

    @Test
    fun fullWorkspaceRetainsTabAcrossWindowSizes() {
        var size by mutableStateOf(DpSize(390.dp, 844.dp))
        var hosts by mutableStateOf(emptyList<Host>())
        var requests = 0
        compose.setContent {
            DeviceConfigurationOverride(DeviceConfigurationOverride.WindowSize(size)) {
                UnifiedTheme(ThemeMode.Light) {
                    UnifiedScreen(
                        UiState(
                            snapshot =
                                Snapshot(
                                    "demo",
                                    hosts,
                                    emptyList(),
                                    emptyList(),
                                    emptyList(),
                                    "Fixture",
                                ),
                            connected = true,
                        ),
                        "https://fixture.test" to "fixture-token",
                        { _, _ -> requests++ },
                        { _, _, _ -> requests++ },
                        {},
                        {},
                        {},
                    )
                }
            }
        }
        assertBottomNavigation()
        compose.onNode(hasText("主機") and hasClickAction()).performClick()
        compose.onNodeWithText("主機.").assertIsDisplayed()
        compose.runOnIdle { size = DpSize(820.dp, 900.dp) }
        compose.onNodeWithText("主機.").assertIsDisplayed()
        compose.onNodeWithText("選擇一個項目查看詳情").assertIsDisplayed()
        val first = compose.onNode(hasText("受管對象") and hasClickAction()).getUnclippedBoundsInRoot()
        val last = compose.onNode(hasText("插件") and hasClickAction()).getUnclippedBoundsInRoot()
        assertEquals(first.left.value, last.left.value, 1f)
        compose.runOnIdle {
            hosts =
                listOf(
                    Host(
                        "fixture",
                        "Fresh host snapshot",
                        "host.example.test",
                        22,
                        "unified",
                        "fixture-key",
                        "online",
                    )
                )
        }
        compose.onNodeWithText("Fresh host snapshot").assertIsDisplayed()
        compose.runOnIdle { size = DpSize(390.dp, 844.dp) }
        compose.onNodeWithText("主機.").assertIsDisplayed()
        compose.onNodeWithText("選擇一個項目查看詳情").assertDoesNotExist()
        assertEquals(0, requests)
        assertBottomNavigation()
    }

    private fun assertBottomNavigation() {
        val first = compose.onNode(hasText("受管對象") and hasClickAction()).getUnclippedBoundsInRoot()
        val last = compose.onNode(hasText("插件") and hasClickAction()).getUnclippedBoundsInRoot()
        assertEquals(first.top.value, last.top.value, 1f)
    }
}
