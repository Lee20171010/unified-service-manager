package dev.unified.app

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyGridScope
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteScaffold
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun UnifiedScreen(
    state: UiState,
    connection: Pair<String, String>,
    connect: (String, String) -> Any,
    mutate: (String, JSONObject, () -> Unit) -> Any,
    showJob: (Job) -> Unit,
    terminal: (String) -> Unit,
    dismissError: () -> Unit,
    themeMode: ThemeMode = ThemeMode.System,
    onThemeChange: (ThemeMode) -> Unit = {},
    pluginDocument: suspend (String, JSONObject?) -> String = { _, _ -> error("請先連線") },
    onDiagnostics: () -> Unit = {},
    drafts: WorkspaceDrafts = remember { WorkspaceDrafts() },
) {
    var pluginEditor by rememberSaveable { mutableStateOf<String?>(null) }
    var exportPluginId by rememberSaveable { mutableStateOf("") }
    pluginEditor?.let { mode ->
        PluginDocumentDialog(mode, exportPluginId, pluginDocument) { pluginEditor = null }
    }
    var appearanceOpen by rememberSaveable { mutableStateOf(false) }
    if (appearanceOpen) AppearanceDialog(themeMode, onThemeChange) { appearanceOpen = false }
    var page by rememberSaveable { mutableIntStateOf(0) }
    var connectionOpen by rememberSaveable { mutableStateOf(false) }
    var connectionSubmitted by rememberSaveable { mutableStateOf(false) }
    var observedConnectionVersion by rememberSaveable { mutableIntStateOf(state.connectionVersion) }
    LaunchedEffect(state.connectionVersion, state.busy) {
        if (
            connectionSubmitted &&
                state.connected &&
                observedConnectionVersion != state.connectionVersion
        ) {
            connectionOpen = false
            drafts.connection = null
        }
        observedConnectionVersion = state.connectionVersion
        if (!state.busy) connectionSubmitted = false
    }
    var form by drafts.form
    var detailService by rememberSaveable { mutableStateOf<String?>(null) }
    var detailHost by rememberSaveable { mutableStateOf<String?>(null) }
    var query by rememberSaveable { mutableStateOf("") }
    var hostFilter by rememberSaveable { mutableStateOf("") }
    var pluginCategory by rememberSaveable { mutableStateOf("") }
    var pluginInstalled by rememberSaveable { mutableStateOf("") }
    var kindFilter by rememberSaveable { mutableStateOf("") }
    var statusFilter by rememberSaveable { mutableStateOf("") }
    val snapshot = state.snapshot
    val tabs = listOf("受管對象", "主機", "備份還原", "執行紀錄", "插件")
    val icons =
        listOf(
            Icons.Outlined.Dashboard,
            Icons.Outlined.Dns,
            Icons.Outlined.CloudUpload,
            Icons.Outlined.History,
            Icons.Outlined.Extension,
        )
    fun scenario() =
        if (snapshot?.mode == "demo")
            listOf(
                FormField(
                    "scenario",
                    "模擬情境",
                    "normal",
                    listOf("normal" to "正常完成", "long" to "長時間背景任務", "fail" to "失敗與 stderr"),
                )
            )
        else emptyList()
    fun addService(host: String = "") {
        val hosts = snapshot?.hosts.orEmpty()
        if (hosts.isNotEmpty() && snapshot?.serviceAdapters?.isNotEmpty() == true)
            form =
                FormSpec(
                    "新增受管對象",
                    "/resources",
                    listOf(
                        FormField("name", "服務名稱"),
                        FormField(
                            "host",
                            "所在主機",
                            host.ifBlank { hosts.first().id },
                            hosts.map { it.id to it.name },
                        ),
                        FormField(
                            "adapter",
                            "接入類型",
                            snapshot.serviceAdapters.first().id,
                            snapshot.serviceAdapters.map { it.id to it.label },
                        ),
                    ),
                    adapters = snapshot.serviceAdapters,
                )
    }
    fun addHost() {
        form =
            FormSpec(
                "新增主機",
                "/hosts",
                listOf(
                    FormField("name", "主機名稱"),
                    FormField("address", "IP / DNS 位址"),
                    FormField("port", "SSH Port", "22"),
                    FormField("username", "SSH 使用者", "unified"),
                    FormField("key", "私鑰檔案名稱", "id_ed25519"),
                ),
                "私鑰與經驗證的 known_hosts 由中央服務掛載管理。",
            )
    }
    fun backup() {
        val apps = snapshot?.backupApplications.orEmpty().filter { "backup" in it.operations }
        if (apps.isEmpty()) return
        form =
            FormSpec(
                "建立備份",
                "/backups",
                listOf(
                    FormField(
                        "client",
                        "應用程式",
                        apps.first().client,
                        apps.map { it.client to it.label },
                    )
                ) + scenario(),
                "將應用程式設定備份至中央指定的儲存位置，並驗證遠端副本。",
            )
    }
    val details: @Composable (String, Boolean) -> Unit = { selectedKey, twoPane ->
        val selectedService =
            selectedKey.takeIf { it.startsWith("service:") }?.removePrefix("service:")
        val selectedHost = selectedKey.takeIf { it.startsWith("host:") }?.removePrefix("host:")
        if (
            (selectedService != null &&
                snapshot?.services?.none { it.id == selectedService } != false) ||
                (selectedHost != null && snapshot?.hosts?.none { it.id == selectedHost } != false)
        ) {
            DetailPane(
                "項目無法使用",
                twoPane,
                {
                    detailService = null
                    detailHost = null
                },
            ) {
                Text("此項目已移除或目前無法讀取，請返回列表重新選擇。")
            }
        }
        snapshot
            ?.services
            ?.find { it.id == selectedService }
            ?.let { s ->
                DetailPane("受管對象詳情", twoPane, { detailService = null }) {
                    Text(s.name, style = MaterialTheme.typography.titleLarge)
                    Status(s.displayStatus())
                    Text(
                        "主機：${snapshot.hosts.find { it.id == s.host }?.name}\n接入類型：${s.adapterLabel}\n映像：${s.version}\n狀態讀取：${date(s.checked)}",
                        fontSize = 12.sp,
                    )
                    s.settings.forEach { (name, value) ->
                        val label =
                            snapshot.serviceAdapters
                                .find { it.id == s.adapter }
                                ?.fields
                                ?.find { it.name == name }
                                ?.label ?: name
                        Text("$label：$value", fontSize = 12.sp)
                    }
                    if (!s.available)
                        Text("接入類型未就緒，請檢查伺服器設定。", color = MaterialTheme.colorScheme.error)
                    val active =
                        snapshot.jobs.find {
                            it.resourceId == s.id && it.status in listOf("queued", "running")
                        }
                    if (active != null) Button(onClick = { showJob(active) }) { Text("查看執行中任務") }
                    else
                        s.supportedActions().forEach { action ->
                            OutlinedButton(
                                onClick = {
                                    form =
                                        FormSpec(
                                            "${actionNames[action]} ${s.name}",
                                            "/resources/${s.id}/jobs",
                                            listOf(
                                                FormField(
                                                    "action",
                                                    "操作",
                                                    action,
                                                    listOf(action to actionNames.getValue(action)),
                                                )
                                            ) + scenario(),
                                            "依已登記的範圍與版本策略執行。套件更新不會自動重啟宿主。",
                                            confirm = action == "uninstall",
                                        )
                                },
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text(actionNames.getValue(action))
                            }
                        }
                    HorizontalDivider()
                    if (s.available)
                        OutlinedButton(
                            onClick = {
                                val adapter = snapshot.serviceAdapters.find { it.id == s.adapter }
                                form =
                                    FormSpec(
                                        "編輯設定",
                                        "/resources/${s.id}",
                                        listOf(
                                            FormField("name", "名稱", s.name),
                                            FormField(
                                                "host",
                                                "主機",
                                                s.host,
                                                listOf(
                                                    s.host to
                                                        (snapshot.hosts
                                                            .find { it.id == s.host }
                                                            ?.name ?: s.host)
                                                ),
                                            ),
                                            FormField(
                                                "adapter",
                                                "管理插件",
                                                s.adapter,
                                                listOf(s.adapter to s.adapterLabel),
                                            ),
                                        ),
                                        "保留主機與安裝身份，可修改版本策略及操作命令。",
                                        adapters =
                                            listOfNotNull(
                                                adapter?.copy(
                                                    fields =
                                                        adapter.fields.map {
                                                            it.copy(
                                                                initial =
                                                                    s.settings[it.name]
                                                                        ?: it.initial
                                                            )
                                                        }
                                                )
                                            ),
                                    )
                            }
                        ) {
                            Text("編輯設定")
                        }
                    Text("宿主關係", fontWeight = FontWeight.SemiBold)
                    snapshot.services.forEach { pkg ->
                        pkg.bindings
                            .filter { it.parent == s.id }
                            .forEach { b ->
                                Text(
                                    "${pkg.name} · 安裝 ${pkg.version} · 載入 ${b.loadedVersion}",
                                    fontSize = 12.sp,
                                )
                            }
                    }
                    s.bindings.forEach { b ->
                        Text(
                            "${snapshot.services.find { it.id==b.parent }?.name} · ${if(b.registered) "已接入" else "未接入"} · 載入 ${b.loadedVersion}${if(b.needsRestart) " · 需重啟／檢查" else ""}",
                            fontSize = 12.sp,
                        )
                        (if (s.available)
                                listOf("register", "unregister") +
                                    (if (b.canVerify) listOf("verify") else emptyList())
                            else emptyList())
                            .forEach { action ->
                                OutlinedButton(
                                    onClick = {
                                        form =
                                            FormSpec(
                                                actionNames.getValue(action),
                                                "/resources/${s.id}/jobs",
                                                listOf(
                                                    FormField(
                                                        "action",
                                                        "操作",
                                                        action,
                                                        listOf(
                                                            action to actionNames.getValue(action)
                                                        ),
                                                    ),
                                                    FormField(
                                                        "binding",
                                                        "關係",
                                                        b.id,
                                                        listOf(
                                                            b.id to
                                                                (snapshot.services
                                                                    .find { it.id == b.parent }
                                                                    ?.name ?: b.parent)
                                                        ),
                                                    ),
                                                ) + scenario(),
                                                confirm = action == "unregister",
                                            )
                                    }
                                ) {
                                    Text(actionNames.getValue(action))
                                }
                            }
                    }
                    val allowed = snapshot.plugins.find { it.id == s.adapter }?.hosts.orEmpty()
                    val parents =
                        snapshot.services.filter { it.host == s.host && it.adapter in allowed }
                    if (parents.isNotEmpty() && s.available)
                        OutlinedButton(
                            onClick = {
                                form =
                                    FormSpec(
                                        "關聯宿主",
                                        "/resources/${s.id}/bindings",
                                        listOf(
                                            FormField(
                                                "parent",
                                                "宿主",
                                                parents.first().id,
                                                parents.map { it.id to it.name },
                                            ),
                                            FormField("register_command", "接入命令"),
                                            FormField("unregister_command", "解除接入命令"),
                                            FormField(
                                                "verify_command",
                                                "載入版本檢查命令",
                                                required = false,
                                            ),
                                        ),
                                        "儲存關係不會執行命令。使用實際安裝方式的命令；可用 UNIFIED_PACKAGE、UNIFIED_DIRECTORY、UNIFIED_VERSION。檢查命令只輸出版本號、none 或 unknown。",
                                    )
                            }
                        ) {
                            Text("關聯宿主")
                        }
                    HorizontalDivider()
                    Text("手動排錯", fontWeight = FontWeight.SemiBold)
                    Button(onClick = { terminal(s.host) }) { Text("開啟 SSH Terminal") }
                }
            }
        snapshot
            ?.hosts
            ?.find { it.id == selectedHost }
            ?.let { h ->
                DetailPane("主機詳情", twoPane, { detailHost = null }) {
                    Text(h.name, style = MaterialTheme.typography.titleLarge)
                    Text("${h.username}@${h.address}:${h.port}\n私鑰參照：${h.key}", fontSize = 12.sp)
                    Button(onClick = { addService(h.id) }) { Text("新增受管對象") }
                    snapshot.services
                        .filter { it.host == h.id }
                        .forEach { s ->
                            TextButton(
                                onClick = {
                                    detailHost = null
                                    detailService = s.id
                                }
                            ) {
                                Text(s.name + " →")
                            }
                        }
                    HorizontalDivider()
                    Button(onClick = { terminal(h.id) }) { Text("開啟 SSH Terminal") }
                }
            }
    }
    val listStates = (0..4).map { rememberLazyGridState() }
    NavigationSuiteScaffold(
        modifier = Modifier.testTag("unified-screen"),
        navigationSuiteItems = {
            tabs.forEachIndexed { index, title ->
                item(
                    selected = page == index,
                    onClick = {
                        if (page != index) {
                            page = index
                            detailService = null
                            detailHost = null
                        }
                    },
                    icon = { Icon(icons[index], title) },
                    label = { Text(title, fontSize = 11.sp) },
                )
            }
        },
    ) {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        Column {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Image(
                                    painterResource(R.drawable.unified_brand),
                                    contentDescription = null,
                                    modifier = Modifier.size(30.dp).clip(RoundedCornerShape(7.dp)),
                                )
                                Spacer(Modifier.width(8.dp))
                                Text("unified", fontWeight = FontWeight.Bold)
                            }
                            if (snapshot?.mode == "demo") Text("示範模式", fontSize = 10.sp)
                        }
                    },
                    actions = {
                        IconButton(onClick = { appearanceOpen = true }) {
                            Icon(Icons.Outlined.Brightness6, "外觀模式")
                        }
                        TextButton(
                            onClick = { connectionOpen = true },
                            modifier =
                                Modifier.semantics {
                                    contentDescription = "伺服器：${serverName(connection.first)}"
                                },
                        ) {
                            Icon(
                                Icons.Outlined.Circle,
                                contentDescription = null,
                                modifier = Modifier.size(7.dp),
                                tint =
                                    if (state.connected) MaterialTheme.colorScheme.primary
                                    else MaterialTheme.colorScheme.tertiary,
                            )
                            Spacer(Modifier.width(6.dp))
                            Text(
                                serverName(connection.first),
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.widthIn(max = 110.dp),
                            )
                            Icon(
                                Icons.Outlined.ArrowDropDown,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp),
                            )
                        }
                    },
                )
            },
            floatingActionButton = {
                if (
                    snapshot != null &&
                        page < 3 &&
                        (page != 0 || snapshot.serviceAdapters.isNotEmpty()) &&
                        (page != 2 || snapshot.backupApplications.any { "backup" in it.operations })
                )
                    FloatingActionButton(
                        onClick = {
                            when (page) {
                                0 -> if (snapshot.hosts.isEmpty()) addHost() else addService()
                                1 -> addHost()
                                2 -> backup()
                            }
                        }
                    ) {
                        Icon(Icons.Outlined.Add, "新增")
                    }
            },
        ) { padding ->
            AdaptiveWorkspace(
                pageKey = page.toString(),
                detailKey = detailService?.let { "service:$it" } ?: detailHost?.let { "host:$it" },
                supportsDetails = page == 0 || page == 1,
                onBack = {
                    detailService = null
                    detailHost = null
                },
                modifier = Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding),
                detail = details,
            ) { shownPage ->
                val displayedPage = shownPage.toInt()
                Column(Modifier.fillMaxSize()) {
                    if (state.connectionError != null)
                        Surface(color = MaterialTheme.colorScheme.secondaryContainer) {
                            Row(Modifier.fillMaxWidth().padding(12.dp)) {
                                Text(
                                    if (state.needsCredentials) "連線憑證需要更新，請開啟伺服器設定。"
                                    else "連線暫時中斷，將自動重試。已保留目前畫面。",
                                    Modifier.weight(1f),
                                    fontSize = 12.sp,
                                )
                                TextButton(onClick = { connectionOpen = true }) { Text("伺服器設定") }
                            }
                        }
                    if (state.error != null)
                        Surface(color = MaterialTheme.colorScheme.errorContainer) {
                            Row(
                                Modifier.fillMaxWidth().padding(12.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                            ) {
                                Text(state.error, Modifier.weight(1f), fontSize = 12.sp)
                                TextButton(onClick = dismissError) { Text("關閉") }
                            }
                        }
                    if (snapshot == null) {
                        Column(
                            Modifier.padding(24.dp),
                            verticalArrangement = Arrangement.spacedBy(16.dp),
                        ) {
                            Text(
                                if (state.connectionConfigured) "正在連接伺服器" else "連接伺服器",
                                style = MaterialTheme.typography.headlineMedium,
                            )
                            Text(
                                if (state.connectionConfigured)
                                    "會自動連接最後保存的伺服器。請確認 Tailscale 與伺服器可連線。"
                                else "首次使用請設定伺服器網址與管理員 Token；之後開啟 App 會自動連線。"
                            )
                            Button(onClick = { connectionOpen = true }) {
                                Text(if (state.connectionConfigured) "伺服器設定" else "連接伺服器")
                            }
                        }
                    } else {
                        val activeJobs =
                            snapshot.jobs.filter { it.status in listOf("queued", "running") }
                        if (activeJobs.isNotEmpty())
                            TextButton(
                                onClick = { showJob(activeJobs.first()) },
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text("${activeJobs.size} 個背景任務 · 查看執行輸出 →")
                            }
                        LazyVerticalGrid(
                            columns = GridCells.Adaptive(320.dp),
                            modifier = Modifier.fillMaxSize().testTag("inventory-list"),
                            state = listStates[displayedPage],
                            contentPadding = PaddingValues(18.dp, 12.dp, 18.dp, 90.dp),
                            verticalArrangement = Arrangement.spacedBy(12.dp),
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            fullWidthItem {
                                Text(
                                    tabs[displayedPage] + ".",
                                    style = MaterialTheme.typography.headlineLarge,
                                    fontWeight = FontWeight.SemiBold,
                                )
                            }
                            when (displayedPage) {
                                0 -> {
                                    fullWidthItem {
                                        Choice(
                                            "類型",
                                            kindFilter,
                                            listOf(
                                                "" to "全部",
                                                "service" to "常駐服務",
                                                "package" to "套件／CLI",
                                                "extension" to "應用插件",
                                                "tool" to "一次性工具",
                                            ),
                                            { kindFilter = it },
                                        )
                                        if (snapshot.serviceAdapters.isEmpty())
                                            Text("請先到插件頁 Install 管理插件。")
                                    }
                                    fullWidthItem {
                                        Row(
                                            Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                                        ) {
                                            Metric(
                                                "主機",
                                                snapshot.hosts.size.toString(),
                                                Modifier.weight(1f),
                                            )
                                            Metric(
                                                "運行中",
                                                snapshot.services
                                                    .count {
                                                        it.kind == "service" &&
                                                            it.status == "online"
                                                    }
                                                    .toString(),
                                                Modifier.weight(1f),
                                            )
                                            Metric(
                                                "備份",
                                                snapshot.backups.size.toString(),
                                                Modifier.weight(1f),
                                            )
                                        }
                                    }
                                    fullWidthItem {
                                        OutlinedTextField(
                                            query,
                                            { query = it },
                                            label = { Text("搜尋服務") },
                                            modifier = Modifier.fillMaxWidth(),
                                            singleLine = true,
                                        )
                                    }
                                    fullWidthItem {
                                        Choice(
                                            "主機",
                                            hostFilter,
                                            listOf("" to "所有主機") +
                                                snapshot.hosts.map { it.id to it.name },
                                            { hostFilter = it },
                                        )
                                    }
                                    fullWidthItem {
                                        Choice(
                                            "狀態",
                                            statusFilter,
                                            listOf(
                                                "" to "全部",
                                                "online" to "運行中",
                                                "stopped" to "已停止",
                                                "unknown" to "待確認",
                                            ),
                                            { statusFilter = it },
                                        )
                                    }
                                    val services =
                                        snapshot.services.filter {
                                            it.name.contains(query, true) &&
                                                (kindFilter.isBlank() || it.kind == kindFilter) &&
                                                (hostFilter.isBlank() || it.host == hostFilter) &&
                                                (statusFilter.isBlank() ||
                                                    it.status == statusFilter)
                                        }
                                    if (services.isEmpty())
                                        fullWidthItem { Text("尚無符合條件的服務。使用 ＋ 新增。") }
                                    items(services, key = { it.id }) { service ->
                                        ContentCard(Modifier.fillMaxWidth()) {
                                            Row(
                                                Modifier.fillMaxWidth(),
                                                horizontalArrangement = Arrangement.SpaceBetween,
                                            ) {
                                                Text(
                                                    service.name,
                                                    Modifier.weight(1f),
                                                    fontWeight = FontWeight.SemiBold,
                                                )
                                                Status(
                                                    activeJobs
                                                        .find { it.resourceId == service.id }
                                                        ?.status ?: service.displayStatus()
                                                )
                                            }
                                            Text(
                                                snapshot.hosts
                                                    .find { it.id == service.host }
                                                    ?.name
                                                    .orEmpty(),
                                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                fontSize = 12.sp,
                                            )
                                            Text(service.version, fontSize = 11.sp)
                                            TextButton(onClick = { detailService = service.id }) {
                                                Text("受管對象詳情與操作 →")
                                            }
                                        }
                                    }
                                }
                                1 -> {
                                    if (snapshot.hosts.isEmpty())
                                        fullWidthItem { Text("使用 ＋ 加入第一台主機。") }
                                    items(snapshot.hosts, key = { it.id }) { h ->
                                        ContentCard(Modifier.fillMaxWidth()) {
                                            Row {
                                                Icon(Icons.Outlined.Dns, null)
                                                Spacer(Modifier.width(10.dp))
                                                Text(
                                                    h.name,
                                                    Modifier.weight(1f),
                                                    fontWeight = FontWeight.SemiBold,
                                                )
                                                Status(h.status)
                                            }
                                            Text("${h.address}:${h.port}", fontSize = 12.sp)
                                            Text(
                                                "${snapshot.services.count { it.host == h.id }} 個服務",
                                                fontSize = 12.sp,
                                            )
                                            TextButton(onClick = { detailHost = h.id }) {
                                                Text("主機詳情 →")
                                            }
                                        }
                                    }
                                }
                                2 -> {
                                    fullWidthItem {
                                        Text(
                                            snapshot.destination,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                        Text("應用程式設定快照", fontSize = 12.sp)
                                        if (
                                            snapshot.backupApplications.none {
                                                "backup" in it.operations
                                            }
                                        )
                                            Text("備份接入或儲存設定尚未就緒。", fontSize = 12.sp)
                                    }
                                    if (snapshot.backups.isEmpty())
                                        fullWidthItem { Text("尚無備份。使用 ＋ 建立第一份設定快照。") }
                                    items(snapshot.backups, key = { it.id }) { b ->
                                        ContentCard(Modifier.fillMaxWidth()) {
                                            Text(b.client, fontWeight = FontWeight.SemiBold)
                                            Text(b.name, fontSize = 12.sp)
                                            Text(
                                                "${date(b.date)} · ${b.bytes / 1024} KiB",
                                                fontSize = 11.sp,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            )
                                            OutlinedButton(
                                                enabled = "restore" in b.operations,
                                                onClick = {
                                                    form =
                                                        FormSpec(
                                                            "還原 ${b.client}",
                                                            "/backups/${b.id}/restore",
                                                            scenario(),
                                                            "${b.name}\n\n此操作會覆蓋應用程式設定。請先停止寫入這些設定的應用程式。上一份設定會保留供回復。",
                                                            confirm = true,
                                                        )
                                                },
                                            ) {
                                                Text("還原")
                                            }
                                        }
                                    }
                                }
                                4 -> {
                                    fullWidthItem { Text("安裝管理插件後才會出現對象表單。此動作不安裝遠端軟體。") }
                                    fullWidthItem {
                                        val catalog = snapshot.pluginCatalog
                                        Text(
                                            if (catalog.refreshing) "官方目錄：檢查中…"
                                            else if (catalog.checked > 0) "官方目錄已取得；更新目錄不會自動替換已安裝插件。"
                                            else "尚未取得官方目錄"
                                        )
                                        if (catalog.error.isNotBlank()) Text(catalog.error)
                                        OutlinedButton(
                                            enabled = !state.busy && !catalog.refreshing,
                                            onClick = {
                                                mutate("/plugin-catalog/refresh", JSONObject(), {})
                                            },
                                        ) {
                                            Text("檢查插件更新")
                                        }
                                    }
                                    fullWidthItem {
                                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                            OutlinedButton(
                                                enabled = !state.busy,
                                                onClick = { pluginEditor = "create" },
                                            ) {
                                                Text("建立插件")
                                            }
                                            OutlinedButton(
                                                enabled = !state.busy,
                                                onClick = { pluginEditor = "import" },
                                            ) {
                                                Text("匯入插件")
                                            }
                                        }
                                    }
                                    fullWidthItem {
                                        Choice(
                                            "插件分類",
                                            pluginCategory,
                                            listOf(
                                                "" to "全部",
                                                "service-management" to "服務管理",
                                                "package-management" to "套件與應用插件",
                                                "application-backup" to "應用備份",
                                                "backup-storage" to "備份儲存",
                                            ),
                                            { pluginCategory = it },
                                        )
                                        Choice(
                                            "安裝狀態",
                                            pluginInstalled,
                                            listOf(
                                                "" to "全部",
                                                "available" to "可安裝",
                                                "installed" to "已安裝",
                                            ),
                                            { pluginInstalled = it },
                                        )
                                    }
                                    items(
                                        snapshot.plugins.filter {
                                            (pluginCategory.isBlank() ||
                                                it.category == pluginCategory) &&
                                                (pluginInstalled.isBlank() ||
                                                    if (pluginInstalled == "installed")
                                                        it.installedVersion != null
                                                    else it.installedVersion == null)
                                        },
                                        key = { it.id },
                                    ) { p ->
                                        ContentCard(Modifier.fillMaxWidth()) {
                                            Text(
                                                p.label,
                                                style = MaterialTheme.typography.titleMedium,
                                            )
                                            Text("${p.category} · ${p.version}", fontSize = 12.sp)
                                            Text(
                                                when (p.source) {
                                                    "builtin" -> "內建"
                                                    "github" -> "GitHub 官方"
                                                    "installed" -> "已安裝副本"
                                                    else -> "自訂"
                                                },
                                                fontSize = 12.sp,
                                            )
                                            Text(p.description, fontSize = 12.sp)
                                            Text(
                                                p.installedVersion?.let {
                                                    "已安裝 $it · ${if(p.enabled) "啟用" else "停用"}"
                                                } ?: "尚未安裝"
                                            )
                                            val actions =
                                                if (!p.available) emptyList()
                                                else if (p.installedVersion == null)
                                                    listOf("install" to "Install")
                                                else
                                                    listOf(
                                                        (if (p.enabled) "disable" else "enable") to
                                                            (if (p.enabled) "停用" else "啟用"),
                                                        "update" to "更新插件",
                                                        "remove" to "移除",
                                                    ) +
                                                        (if (p.rollback) listOf("rollback" to "回退")
                                                        else emptyList())
                                            if (p.available)
                                                OutlinedButton(
                                                    enabled = !state.busy,
                                                    onClick = {
                                                        exportPluginId = p.id
                                                        pluginEditor = "export"
                                                    },
                                                ) {
                                                    Text("匯出 JSON")
                                                }
                                            if (
                                                p.available &&
                                                    p.category in
                                                        listOf(
                                                            "service-management",
                                                            "package-management",
                                                        )
                                            )
                                                OutlinedButton(
                                                    enabled = !state.busy,
                                                    onClick = {
                                                        exportPluginId = p.id
                                                        pluginEditor = "copy"
                                                    },
                                                ) {
                                                    Text("複製並自訂")
                                                }
                                            actions.forEach { (action, label) ->
                                                OutlinedButton(
                                                    enabled = !state.busy,
                                                    onClick = {
                                                        mutate(
                                                            "/plugins/${p.id}",
                                                            JSONObject()
                                                                .put("action", action)
                                                                .apply {
                                                                    if (
                                                                        action == "install" ||
                                                                            action == "update"
                                                                    ) {
                                                                        put("version", p.version)
                                                                        if (p.checksum.isNotBlank())
                                                                            put(
                                                                                "checksum",
                                                                                p.checksum,
                                                                            )
                                                                    }
                                                                },
                                                            {},
                                                        )
                                                    },
                                                ) {
                                                    Text(label)
                                                }
                                            }
                                        }
                                    }
                                }
                                3 -> {
                                    if (snapshot.jobs.isEmpty()) fullWidthItem { Text("尚無執行紀錄。") }
                                    items(snapshot.jobs, key = { it.id }) { j ->
                                        ContentCard(Modifier.fillMaxWidth()) {
                                            Row {
                                                Text(
                                                    "${j.target} · ${actionNames[j.action]}",
                                                    Modifier.weight(1f),
                                                    fontWeight = FontWeight.SemiBold,
                                                )
                                                Status(j.status)
                                            }
                                            Text(
                                                date(j.date),
                                                fontSize = 11.sp,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            )
                                            j.error?.let {
                                                Text(
                                                    it,
                                                    fontSize = 12.sp,
                                                    color = MaterialTheme.colorScheme.error,
                                                )
                                            }
                                            TextButton(onClick = { showJob(j) }) {
                                                Text("查看 Job Console →")
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    if (connectionOpen)
        ConnectionDialog(
            connection,
            state.busy,
            state.error ?: state.connectionError,
            onDismiss = {
                connectionOpen = false
                drafts.connection = null
            },
            onConnect = { base, token ->
                connectionSubmitted = true
                connect(base, token)
            },
            connected = state.connected,
            draft =
                remember(drafts, connectionOpen) {
                    drafts.connection
                        ?: ConnectionDraft(connection, state.connected).also {
                            drafts.connection = it
                        }
                },
            onDiagnostics = {
                connectionOpen = false
                drafts.connection = null
                onDiagnostics()
            },
        )
    form?.let { spec ->
        FormDialog(spec, state.busy, state.error, { form = null }) { body ->
            mutate(spec.path, body) { form = null }
        }
    }
}

private fun LazyGridScope.fullWidthItem(content: @Composable ColumnScope.() -> Unit) {
    item(span = { GridItemSpan(maxLineSpan) }) {
        Column(
            Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            content = content,
        )
    }
}
