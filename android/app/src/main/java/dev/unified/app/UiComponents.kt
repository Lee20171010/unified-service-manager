package dev.unified.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

internal val Green = Color(0xFF173E35)

internal fun date(value: Long) =
    if (value == 0L) "尚未讀取" else SimpleDateFormat("MM/dd HH:mm", Locale.TAIWAN).format(Date(value))

@Composable
internal fun ContentCard(
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    Card(
        modifier,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            content = content,
        )
    }
}

@Composable
internal fun Metric(title: String, value: String, modifier: Modifier = Modifier) {
    ContentCard(modifier) {
        Text(title, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, fontSize = 26.sp, color = MaterialTheme.colorScheme.primary)
    }
}

@Composable
internal fun Status(status: String) {
    Surface(
        color =
            if (status == "failed") MaterialTheme.colorScheme.errorContainer
            else MaterialTheme.colorScheme.secondaryContainer,
        shape = MaterialTheme.shapes.small,
    ) {
        Text(
            statusNames[status] ?: status,
            Modifier.padding(8.dp, 4.dp),
            fontSize = 11.sp,
            color =
                if (status == "failed") MaterialTheme.colorScheme.onErrorContainer
                else MaterialTheme.colorScheme.onSecondaryContainer,
        )
    }
}

@Composable
internal fun Choice(
    label: String,
    value: String,
    choices: List<Pair<String, String>>,
    change: (String) -> Unit,
) {
    var open by remember { mutableStateOf(false) }
    Box {
        OutlinedButton(onClick = { open = true }, modifier = Modifier.fillMaxWidth()) {
            Text("$label：${choices.find { it.first == value }?.second.orEmpty()}")
            Spacer(Modifier.weight(1f))
            Icon(Icons.Outlined.ArrowDropDown, null)
        }
        DropdownMenu(open, { open = false }) {
            choices.forEach { (id, text) ->
                DropdownMenuItem(
                    text = { Text(text) },
                    onClick = {
                        change(id)
                        open = false
                    },
                )
            }
        }
    }
}

@Composable
internal fun DetailDialog(
    title: String,
    dismiss: () -> Unit,
    content: @Composable ColumnScope.() -> Unit,
) {
    AlertDialog(
        onDismissRequest = dismiss,
        title = { Text(title) },
        text = {
            Column(
                Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                content = content,
            )
        },
        confirmButton = { TextButton(onClick = dismiss) { Text("關閉") } },
    )
}
