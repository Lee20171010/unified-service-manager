package dev.unified.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment

@RunWith(RobolectricTestRunner::class)
class CredentialsTest {
    @Test
    fun freshInstallationHasNoServerOrToken() {
        val context = RuntimeEnvironment.getApplication()
        context.getSharedPreferences("connection", 0).edit().clear().commit()
        val credentials = Credentials(context)
        assertFalse(credentials.hasSavedConnection())
        assertEquals("" to "", credentials.read())
    }
}
