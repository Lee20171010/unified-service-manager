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
@Config(sdk = [28], qualifiers = "w320dp-h891dp")
class AdapterTest {
    @get:Rule val compose = createComposeRule()
    private val adapter =
        ServiceAdapterInfo(
            "fixture",
            "Fixture adapter",
            listOf(AdapterField("unit", "Unit name", "test-unit", true)),
        )
    private val snapshot =
        Snapshot(
            "demo",
            listOf(Host("h", "Fixture", "localhost", 22, "test", "key", "online")),
            listOf(
                Service(
                    "s",
                    "Read only",
                    "h",
                    "",
                    "1",
                    "online",
                    0,
                    "fixture",
                    "Fixture adapter",
                    mapOf("unit" to "test-unit"),
                    listOf("refresh"),
                )
            ),
            emptyList(),
            emptyList(),
            "Fixture storage",
            listOf(adapter),
            listOf(BackupApplicationInfo("New application", "New application", listOf("backup"))),
        )
    private var submitted: JSONObject? = null

    private fun screen(value: Snapshot = snapshot) {
        compose.setContent {
            MaterialTheme {
                UnifiedScreen(
                    UiState(snapshot = value, connected = true),
                    "" to "",
                    { _, _ -> },
                    { _, body, done ->
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

    @Test
    fun onlyDeclaredServiceOperationsAreShown() {
        screen()
        compose.onNodeWithText("受管對象詳情與操作 →").performScrollTo().performClick()
        compose.onNodeWithText("重新整理狀態").assertExists()
        listOf("啟動", "停止", "重啟", "更新").forEach {
            compose.onNodeWithText(it, substring = false).assertDoesNotExist()
        }
        compose.onNodeWithText("開啟 SSH Terminal").assertExists()
    }

    @Test
    fun newAdapterFieldsProduceNestedSettingsAndSwitchWithoutStaleValues() {
        val alternate =
            ServiceAdapterInfo(
                "other",
                "Other adapter",
                listOf(AdapterField("resource", "Resource", "other-unit", true)),
            )
        screen(snapshot.copy(serviceAdapters = listOf(adapter, alternate)))
        compose.onNodeWithContentDescription("新增").performClick()
        compose.onNodeWithText("服務名稱", substring = false).performTextInput("New service")
        compose.onNodeWithText("Unit name", substring = false).assertExists()
        compose.onNodeWithText("接入類型：Fixture adapter").performClick()
        compose.onNodeWithText("Other adapter", substring = false).performClick()
        compose.onNodeWithText("Unit name", substring = false).assertDoesNotExist()
        compose.onNodeWithText("Resource", substring = false).assertExists()
        compose.onNodeWithText("確認", substring = false).performClick()
        assertEquals("New service", submitted!!.getString("name"))
        assertEquals("other", submitted!!.getString("adapter"))
        assertEquals(
            setOf("resource"),
            submitted!!.getJSONObject("settings").keys().asSequence().toSet(),
        )
        assertEquals("other-unit", submitted!!.getJSONObject("settings").getString("resource"))
    }

    @Test
    fun newBackupApplicationUsesServerChoices() {
        screen()
        compose.onNodeWithText("備份還原", useUnmergedTree = true).performClick()
        compose.onNodeWithContentDescription("新增").performClick()
        compose.onNodeWithText("應用程式：New application").assertExists()
        compose.onNodeWithText("確認", substring = false).performClick()
        assertEquals("New application", submitted!!.getString("client"))
    }

    @Test
    fun snapshotParsesNewAdaptersAndMissingCapabilitiesFailClosed() {
        val text =
            """{"mode":"demo","hosts":[],"services":[{"id":"s","name":"New","host":"h","version":"1","status":"online","adapter":"fixture","adapter_label":"Fixture","settings":{"unit":"u"},"operations":["refresh","unknown"],"available":true}],"backups":[],"jobs":[],"destination":"Fixture","adapters":{"interface_version":1,"adapters":[{"id":"fixture","kind":"service","interface_version":1,"label":"Fixture","fields":[{"name":"unit","label":"Unit","initial":"u","required":true}]}]},"backup_applications":[{"client":"New App","label":"New App","operations":["backup"]}]}"""
        val parsed = parseSnapshot(text)
        assertEquals(listOf("refresh"), parsed.services.single().supportedActions())
        assertEquals("unit", parsed.serviceAdapters.single().fields.single().name)
        assertEquals("New App", parsed.backupApplications.single().client)
        val changed = JSONObject(text)
        changed.getJSONArray("services").getJSONObject(0).remove("operations")
        changed.getJSONObject("adapters").put("interface_version", 2)
        assertTrue(parseSnapshot(changed.toString()).services.single().supportedActions().isEmpty())
        assertTrue(parseSnapshot(changed.toString()).serviceAdapters.isEmpty())
    }
}
