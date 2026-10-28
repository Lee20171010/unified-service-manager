package dev.unified.app

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.StateRestorationTester
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
class ScreenTest {
    @get:Rule val compose = createComposeRule()
    private val snapshot =
        Snapshot(
            "demo",
            listOf(Host("h1", "test-host", "192.0.2.1", 22, "unified", "id_ed25519", "online")),
            listOf(
                Service(
                    "s1",
                    "Magpie",
                    "h1",
                    "/opt/magpie",
                    "1.0",
                    "online",
                    0,
                    operations = serviceVocabulary,
                )
            ),
            listOf(Backup("b1", "Magpie", "settings.zip", 0, 1024, listOf("restore"))),
            emptyList(),
            "Demo WebDAV",
            listOf(
                ServiceAdapterInfo(
                    "compose",
                    "Docker Compose",
                    listOf(AdapterField("compose_dir", "Compose 專案目錄", "/opt/stacks/", true)),
                )
            ),
            listOf(
                BackupApplicationInfo("Magpie", "Magpie", listOf("backup", "restore")),
                BackupApplicationInfo(
                    "Flutter ServerBox",
                    "Flutter ServerBox",
                    listOf("backup", "restore"),
                ),
            ),
        )
    private var submitted: Pair<String, JSONObject>? = null
    private var terminalHost: String? = null

    private fun screen() {
        compose.setContent {
            MaterialTheme {
                UnifiedScreen(
                    UiState(snapshot = snapshot, connected = true),
                    "https://review.test" to "token",
                    { _, _ -> },
                    { path, body, done ->
                        submitted = path to body
                        done()
                    },
                    {},
                    { terminalHost = it },
                    {},
                )
            }
        }
    }

    @Test
    @Config(qualifiers = "w320dp-h891dp")
    fun newHostRequiresExplicitPrivateKeyFilename() {
        screen()
        compose.onNode(hasText("主機") and hasClickAction()).performClick()
        compose.onNodeWithContentDescription("新增").performClick()
        compose.onNodeWithText("主機名稱").performScrollTo().performTextInput("Fixture")
        compose.onNodeWithText("IP / DNS 位址").performScrollTo().performTextInput("fixture.test")
        compose.onNodeWithText("私鑰檔案名稱").performScrollTo().assertTextEquals("私鑰檔案名稱", "")
        compose.onNodeWithText("確認").assertIsNotEnabled()
        compose.onNodeWithText("私鑰檔案名稱").performTextInput("nas_key")
        compose.onNodeWithText("確認").performClick()
        assertEquals("/hosts", submitted?.first)
        assertEquals("nas_key", submitted?.second?.getString("key"))
    }

    @Test
    fun serviceOperationsAndTerminalHaveDistinctCallbacks() {
        screen()
        compose.onNodeWithText("受管對象詳情與操作 →").performScrollTo().performClick()
        listOf("重新整理狀態", "啟動", "停止", "重啟", "更新").forEach {
            compose.onNodeWithText(it).assertExists()
        }
        compose.onNodeWithText("重啟").performScrollTo().performClick()
        compose.onNodeWithText("確認").performClick()
        assertEquals("/resources/s1/jobs", submitted?.first)
        assertEquals("restart", submitted?.second?.getString("action"))
        assertNull(terminalHost)
        compose.onNodeWithText("受管對象詳情").assertIsDisplayed()
        compose.onNodeWithText("開啟 SSH Terminal").performScrollTo().performClick()
        assertEquals("h1", terminalHost)
    }

    @Test
    fun restoreNeedsConfirmationAndBackupSupportsBothApplications() {
        screen()
        compose.onNodeWithText("備份還原", useUnmergedTree = true).performClick()
        compose.onNodeWithText("還原", substring = false).performClick()
        compose.onNodeWithText("確認").assertIsNotEnabled()
        compose.onNode(isToggleable()).performClick()
        compose.onNodeWithText("確認").assertIsEnabled().performClick()
        assertEquals("/backups/b1/restore", submitted?.first)
        assertTrue(submitted!!.second.getBoolean("confirm"))
        compose.onNodeWithContentDescription("新增").performClick()
        compose.onNodeWithText("應用程式：Magpie").performClick()
        compose.onNodeWithText("Flutter ServerBox", substring = false).performClick()
        compose.onNodeWithText("確認").performClick()
        assertEquals("/backups", submitted?.first)
        assertEquals("Flutter ServerBox", submitted?.second?.getString("client"))
    }

    @Test
    fun restoredNavigationRetainsSelectedPage() {
        val restoration = StateRestorationTester(compose)
        restoration.setContent {
            MaterialTheme {
                UnifiedScreen(
                    UiState(snapshot = snapshot, connected = true),
                    "https://review.test" to "token",
                    { _, _ -> },
                    { _, _, _ -> },
                    {},
                    {},
                    {},
                )
            }
        }
        compose.onNodeWithText("執行紀錄", useUnmergedTree = true).performClick()
        compose.onNodeWithText("尚無執行紀錄。").assertIsDisplayed()
        restoration.emulateSavedInstanceStateRestore()
        compose.onNodeWithText("尚無執行紀錄。").assertIsDisplayed()
    }

    @Test
    // Robolectric #8460: platform-width dialogs with text fields can loop above 320dp.
    @Config(qualifiers = "w320dp-h891dp")
    fun connectionDialogStaysOpenUntilServerAcceptsConnection() {
        screen()
        compose.onNodeWithContentDescription("伺服器：review.test").performClick()
        compose.onNodeWithText("https://review.test", substring = false).assertIsDisplayed()
        compose.onNodeWithText("管理員 Token", substring = false).assertDoesNotExist()
        compose.onNodeWithText("編輯連線", substring = false).performClick()
        compose.onNodeWithText("儲存並連線", substring = false).performClick()
        compose.onNodeWithText("連接伺服器").assertIsDisplayed()
        compose.onNodeWithText("HTTPS 伺服器網址").assertIsDisplayed()
    }

    @Test
    fun terminalSendsLinesAndControlCharacters() {
        val sent = mutableListOf<String>()
        compose.setContent { MaterialTheme { TerminalDialog("h1", "$ ", { sent += it }, {}) } }
        compose.onNodeWithText("輸入指令").performTextInput("hostname")
        compose.onNodeWithText("送出").performClick()
        compose.onNodeWithText("Ctrl+C").performClick()
        compose.onNodeWithText("Ctrl+D").performClick()
        assertEquals(listOf("hostname\n", "\u0003", "\u0004"), sent)
    }
}
