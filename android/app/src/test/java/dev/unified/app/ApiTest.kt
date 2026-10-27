package dev.unified.app

import org.junit.Assert.assertThrows
import org.junit.Test

class ApiTest {
    @Test
    fun rejectsCleartextAndCredentialUrls() {
        assertThrows(IllegalArgumentException::class.java) { Api("http://example.com", "token") }
        assertThrows(IllegalArgumentException::class.java) {
            Api("https://user:password@example.com", "token")
        }
        assertThrows(IllegalArgumentException::class.java) {
            Api("https://example.com?token=secret", "token")
        }
    }

    @Test
    fun acceptsHttpsTailnetOrigin() {
        Api("https://server.example.test:9443", "token").close()
    }
}
