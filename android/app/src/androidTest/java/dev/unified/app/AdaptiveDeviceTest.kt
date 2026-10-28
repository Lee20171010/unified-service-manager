package dev.unified.app

import android.content.Context
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertFalse
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Real Activity recreation without changing the shared emulator's display or posture. */
@RunWith(AndroidJUnit4::class)
class AdaptiveDeviceTest {
    @get:Rule val compose = createEmptyComposeRule()

    @Test
    fun connectionDraftSurvivesActivityRecreationWithoutSavingOrConnecting() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        check(context.packageName == "dev.unified.app.acceptance")
        context.getSharedPreferences("connection", Context.MODE_PRIVATE).edit().clear().commit()
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            compose.onNodeWithContentDescription("伺服器：伺服器").performClick()
            compose.onNodeWithText("HTTPS 伺服器網址").performTextInput("https://draft.example.test")
            compose.onNodeWithText("管理員 Token").performTextInput("fixture-unsaved-token")
            scenario.recreate()
            compose.onNodeWithText("HTTPS 伺服器網址").assertTextContains("https://draft.example.test")
            compose.onNodeWithText("管理員 Token").assertTextContains("fixture-unsaved-token")
            compose.onNodeWithText("儲存並連線").assertIsEnabled()
            assertFalse(Credentials(context).hasSavedConnection())
            compose.onNodeWithText("關閉").performClick()
            compose.onNodeWithContentDescription("伺服器：伺服器").performClick()
            compose.onNodeWithText("HTTPS 伺服器網址").assertTextContains("")
            compose.onNodeWithText("https://draft.example.test").assertDoesNotExist()
        }
    }
}
