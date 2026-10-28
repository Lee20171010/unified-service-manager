package dev.unified.app

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/** ViewModel-owned memory, deliberately excluded from saved state and diagnostic exports. */
internal class WorkspaceDrafts {
    val form = mutableStateOf<FormSpec?>(null)
    var connection: ConnectionDraft? = null
    val jobInput = mutableStateOf("")
    val terminalInput = mutableStateOf("")

    fun clear() {
        form.value = null
        connection = null
        jobInput.value = ""
        terminalInput.value = ""
    }
}

internal class ConnectionDraft(connection: Pair<String, String>, connected: Boolean) {
    var editing by mutableStateOf(!connected)
    var base by mutableStateOf(connection.first)
    var token by mutableStateOf(connection.second)
}
