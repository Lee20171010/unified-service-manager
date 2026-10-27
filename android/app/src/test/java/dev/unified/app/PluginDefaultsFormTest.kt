package dev.unified.app

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
// Robolectric dialog measurement workaround #8460; see docs/TESTING.md.
@Config(sdk = [28], qualifiers = "w320dp-h891dp", application = android.app.Application::class)
class PluginDefaultsFormTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun collapsingAdvancedCommandsPreservesAnExistingOverrideOnSave() {
        var submitted: JSONObject? = null
        val spec =
            FormSpec(
                "編輯",
                "/resources/example",
                listOf(
                    FormField("adapter", "插件", "opencode", listOf("opencode" to "OpenCode")),
                    FormField("settings.unit", "服務單元", "opencode.service"),
                    FormField("settings.cmd_restart", "自訂重啟", "printf existing", required = false),
                ),
            )
        showForm(spec) { submitted = it }
        compose.onNodeWithText("自訂重啟").assertDoesNotExist()
        compose.onNodeWithText("進階：自訂操作命令").performClick()
        compose.onNodeWithText("自訂重啟").performScrollTo().performTextReplacement("printf updated")
        compose.onNodeWithText("收起自訂操作命令").performScrollTo().performClick()
        compose.onNodeWithText("自訂重啟").assertDoesNotExist()
        compose.onNodeWithText("確認", substring = false).performClick()
        assertEquals(
            "printf updated",
            submitted!!.getJSONObject("settings").getString("cmd_restart"),
        )
        assertEquals("opencode.service", submitted!!.getJSONObject("settings").getString("unit"))
    }

    @Test
    fun requiredCommandInAnAuthoredPluginRemainsVisible() {
        val spec =
            FormSpec(
                "工具",
                "/resources",
                listOf(
                    FormField("adapter", "插件", "my-tool", listOf("my-tool" to "My tool")),
                    FormField("settings.cmd_run", "執行命令", required = true),
                ),
            )
        showForm(spec) {}
        compose.onNodeWithText("執行命令").assertExists()
        compose.onNodeWithText("進階：自訂操作命令").assertDoesNotExist()
        compose.onNodeWithText("確認", substring = false).assertIsNotEnabled()
        compose.onNodeWithText("執行命令").performTextInput("printf ready")
        compose.onNodeWithText("確認", substring = false).assertIsEnabled()
    }

    private fun showForm(spec: FormSpec, submit: (JSONObject) -> Unit) {
        compose.setContent {
            MaterialTheme {
                var opened by remember { mutableStateOf(false) }
                Box(Modifier.fillMaxSize()) {
                    Button(onClick = { opened = true }) { Text("編輯設定") }
                    if (opened) FormDialog(spec, false, null, { opened = false }, submit)
                }
            }
        }
        compose.onNodeWithText("編輯設定").performClick()
    }
}
