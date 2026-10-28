package dev.unified.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material3.*
import androidx.compose.material3.adaptive.ExperimentalMaterial3AdaptiveApi
import androidx.compose.material3.adaptive.currentWindowAdaptiveInfoV2
import androidx.compose.material3.adaptive.layout.calculatePaneScaffoldDirective
import androidx.compose.material3.adaptive.navigation3.ListDetailSceneStrategy
import androidx.compose.material3.adaptive.navigation3.rememberListDetailSceneStrategy
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.navigation3.runtime.NavEntry
import androidx.navigation3.ui.NavDisplay

/** Navigation keys are IDs only; resizing never submits an operation or opens a connection. */
@OptIn(ExperimentalMaterial3AdaptiveApi::class)
@Composable
internal fun AdaptiveWorkspace(
    pageKey: String,
    detailKey: String?,
    supportsDetails: Boolean,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
    detail: @Composable (String, Boolean) -> Unit,
    content: @Composable (String) -> Unit,
) {
    val windowInfo = currentWindowAdaptiveInfoV2()
    val currentDetail by rememberUpdatedState(detail)
    val currentContent by rememberUpdatedState(content)
    BoxWithConstraints(modifier) {
        // Measure after the navigation rail and insets. Each pane gets at least 320dp.
        val twoPane = supportsDetails && maxWidth >= 664.dp
        val currentTwoPane by rememberUpdatedState(twoPane)
        val directive =
            calculatePaneScaffoldDirective(windowInfo)
                .copy(
                    maxHorizontalPartitions = if (twoPane) 2 else 1,
                    horizontalPartitionSpacerSize = if (twoPane) 24.dp else 0.dp,
                    defaultPanePreferredWidth = 320.dp,
                )
        val strategy = rememberListDetailSceneStrategy<String>(directive = directive)
        val listKey = "list:$pageKey"
        NavDisplay(
            backStack = listOfNotNull(listKey, detailKey),
            modifier = Modifier.fillMaxSize().testTag(if (twoPane) "two-pane" else "single-pane"),
            onBack = onBack,
            sceneStrategies = if (supportsDetails) listOf(strategy) else emptyList(),
            entryProvider = { key ->
                if (key == listKey) {
                    NavEntry(
                        key,
                        metadata =
                            ListDetailSceneStrategy.listPane(
                                detailPlaceholder = {
                                    Box(Modifier.fillMaxSize().padding(24.dp)) {
                                        Text(
                                            "選擇一個項目查看詳情",
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                }
                            ),
                    ) {
                        currentContent(key.removePrefix("list:"))
                    }
                } else {
                    NavEntry(key, metadata = ListDetailSceneStrategy.detailPane()) {
                        currentDetail(key, currentTwoPane)
                    }
                }
            },
        )
    }
}

@Composable
internal fun DetailPane(
    title: String,
    twoPane: Boolean,
    dismiss: () -> Unit,
    content: @Composable ColumnScope.() -> Unit,
) {
    Surface(Modifier.fillMaxSize().testTag("detail-pane"), tonalElevation = 1.dp) {
        Column(Modifier.padding(16.dp)) {
            Row {
                if (!twoPane)
                    IconButton(onClick = dismiss) {
                        Icon(Icons.AutoMirrored.Outlined.ArrowBack, "返回列表")
                    }
                Text(
                    title,
                    Modifier.weight(1f).padding(vertical = 12.dp),
                    style = MaterialTheme.typography.titleMedium,
                )
                if (twoPane) TextButton(onClick = dismiss) { Text("關閉詳情") }
            }
            Column(
                Modifier.fillMaxWidth()
                    .verticalScroll(rememberScrollState())
                    .padding(bottom = 88.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                content = content,
            )
        }
    }
}
