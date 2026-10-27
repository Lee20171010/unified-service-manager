package dev.unified.app

import android.content.Context
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp

internal enum class ThemeMode(val id: String, val label: String) {
    System("system", "跟隨系統"),
    Light("light", "淺色"),
    Dark("dark", "深色");

    fun isDark(systemDark: Boolean) = this == Dark || (this == System && systemDark)

    companion object {
        fun fromId(id: String?) = entries.find { it.id == id } ?: System
    }
}

internal class ThemePreferences(context: Context) {
    private val preferences = context.getSharedPreferences("appearance", Context.MODE_PRIVATE)

    fun read() = ThemeMode.fromId(preferences.getString("mode", null))

    fun write(mode: ThemeMode) {
        preferences.edit().putString("mode", mode.id).apply()
    }
}

private val LightColors =
    lightColorScheme(
        primary = Green,
        onPrimary = Color.White,
        background = Color(0xFFF6F7F4),
        onBackground = Color(0xFF20352B),
        surface = Color.White,
        onSurface = Color(0xFF20352B),
        surfaceVariant = Color(0xFFE9EFE6),
        onSurfaceVariant = Color(0xFF506257),
        secondaryContainer = Color(0xFFE9EFE6),
        onSecondaryContainer = Green,
    )
private val DarkColors =
    darkColorScheme(
        primary = Color(0xFFA3D9B8),
        onPrimary = Color(0xFF112C1D),
        background = Color(0xFF101916),
        onBackground = Color(0xFFE5EEE8),
        surface = Color(0xFF1A2721),
        onSurface = Color(0xFFE5EEE8),
        surfaceVariant = Color(0xFF253D30),
        onSurfaceVariant = Color(0xFFADBBB2),
        secondaryContainer = Color(0xFF253D30),
        onSecondaryContainer = Color(0xFFA3D9B8),
        outline = Color(0xFF8A9E90),
        error = Color(0xFFFFB4A6),
        errorContainer = Color(0xFF492B28),
        onErrorContainer = Color(0xFFFFB4A6),
    )

@Composable
internal fun UnifiedTheme(
    mode: ThemeMode,
    systemDark: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (mode.isDark(systemDark)) DarkColors else LightColors,
        content = content,
    )
}

@Composable
internal fun AppearanceDialog(mode: ThemeMode, change: (ThemeMode) -> Unit, dismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = dismiss,
        title = { Text("外觀模式") },
        text = {
            Column(Modifier.selectableGroup()) {
                Text("設定儲存在此裝置，跟隨系統會自動切換。")
                ThemeMode.entries.forEach { choice ->
                    Row(
                        Modifier.fillMaxWidth()
                            .heightIn(min = 56.dp)
                            .selectable(
                                selected = mode == choice,
                                role = Role.RadioButton,
                                onClick = { change(choice) },
                            )
                            .padding(vertical = 8.dp),
                        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                    ) {
                        RadioButton(selected = mode == choice, onClick = null)
                        Spacer(Modifier.width(12.dp))
                        Text(choice.label)
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = dismiss) { Text("完成") } },
    )
}
