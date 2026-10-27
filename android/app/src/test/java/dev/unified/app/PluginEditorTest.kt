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
class PluginEditorTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun importPreviewsThenSavesWithoutInstalling() {
        val calls = mutableListOf<String>()
        val m = """{"id":"my-tool","label":"My tool","version":"1.0.0"}"""
        compose.setContent {
            MaterialTheme {
                PluginDocumentDialog(
                    "import",
                    request = { path, body ->
                        calls += path
                        assertEquals("my-tool", body!!.getJSONObject("manifest").getString("id"))
                        JSONObject().put("manifest", JSONObject(m)).toString()
                    },
                    onDismiss = {},
                )
            }
        }
        compose.onNodeWithText("或貼上 plugin.json").performTextInput(m)
        compose.onNodeWithText("校驗與預覽").performClick()
        compose.waitForIdle()
        assertEquals(listOf("/plugin-documents/validate"), calls)
        compose.onNodeWithText("儲存到可安裝").performClick()
        compose.waitForIdle()
        assertEquals(listOf("/plugin-documents/validate", "/plugin-documents"), calls)
        compose.onNodeWithText("已儲存到可安裝。請關閉此視窗，再按 Install／更新插件。").assertExists()
    }

    @Test
    fun invalidImportRetainsDraftWithoutSaving() {
        var calls = 0
        compose.setContent {
            MaterialTheme {
                PluginDocumentDialog(
                    "import",
                    request = { _, _ ->
                        calls++
                        error("PLUGIN_IMMUTABLE")
                    },
                    onDismiss = {},
                )
            }
        }
        compose.onNodeWithText("或貼上 plugin.json").performTextInput("{\"id\":\"same\"}")
        compose.onNodeWithText("校驗與預覽").performClick()
        compose.waitForIdle()
        compose.onNodeWithText("PLUGIN_IMMUTABLE").assertExists()
        compose.onNodeWithText("儲存到可安裝").assertDoesNotExist()
        compose.onNodeWithText("或貼上 plugin.json").assertTextContains("same", substring = true)
        assertEquals(1, calls)
    }

    @Test
    fun createFormSubmitsCommandsAndParametersForPreview() {
        var submitted: JSONObject? = null
        compose.setContent {
            MaterialTheme {
                PluginDocumentDialog(
                    "create",
                    request = { path, body ->
                        assertEquals("/plugin-documents/validate", path)
                        submitted = body!!.getJSONObject("manifest")
                        JSONObject().put("manifest", submitted).toString()
                    },
                    onDismiss = {},
                )
            }
        }
        compose
            .onNodeWithText("插件 ID（小寫英文、數字、連字號）")
            .performScrollTo()
            .performTextInput("native-tool")
        compose
            .onNodeWithText("顯示名稱", substring = false)
            .performScrollTo()
            .performTextInput("Native Tool")
        compose
            .onNodeWithText("執行命令", substring = false)
            .performScrollTo()
            .performTextInput("printf done")
        compose.onNodeWithText("增加參數").performScrollTo().performClick()
        compose.onNodeWithText("欄位名稱", substring = false).performScrollTo().performTextInput("mode")
        compose.onNodeWithText("顯示標籤", substring = false).performScrollTo().performTextInput("Mode")
        compose.onNodeWithText("校驗與預覽").performClick()
        compose.waitForIdle()
        assertEquals("native-tool", submitted!!.getString("id"))
        assertEquals("printf done", submitted!!.getJSONObject("commands").getString("run"))
        assertEquals("mode", submitted!!.getJSONArray("fields").getJSONObject(2).getString("name"))
        compose.onNodeWithText("儲存到可安裝").assertExists()
    }

    @Test
    fun exportLoadsCleanManifestBeforeOfferingSave() {
        var path = ""
        compose.setContent {
            MaterialTheme {
                PluginDocumentDialog(
                    "export",
                    "example",
                    request = { p, body ->
                        path = p
                        assertNull(body)
                        "{\"id\":\"example\",\"version\":\"1.0.0\"}"
                    },
                    onDismiss = {},
                )
            }
        }
        compose.waitForIdle()
        assertEquals("/plugins/example/manifest", path)
        compose.onNodeWithText("儲存 JSON 文件").assertIsEnabled()
    }

    @Test
    fun builderBindsParameterAndPreservesMultilineCommand() {
        val draft =
            JSONObject(
                    """{"id":"my-tool","label":"Tool","version":"1.0.0","directory":"/opt","kind":"tool","parameters":[{"name":"mode","label":"Mode","choices":"check,repair","initial":"check"}]}"""
                )
                .put("cmd_run", "printf '%s' \"\$UNIFIED_MODE\"\nprintf done")
        val m = commandPluginDocument(draft)
        assertEquals("run", m.getJSONArray("operations").getString(0))
        assertEquals(draft.getString("cmd_run"), m.getJSONObject("commands").getString("run"))
        assertEquals("mode", m.getJSONArray("fields").getJSONObject(2).getString("name"))
        assertEquals(2, m.getJSONArray("fields").getJSONObject(2).getJSONArray("choices").length())
        assertThrows(IllegalArgumentException::class.java) {
            readPluginBytes(ByteArray(131073).inputStream())
        }
    }
}
