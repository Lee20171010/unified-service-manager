import { openPluginEditor, downloadPlugin } from "./plugin-editor.js?v=0.4.0";
import {
  serviceActions,
  serviceAdapters,
  backupApplications,
  canRestore,
  serviceBody,
  isCommandOverride,
} from "./capabilities.js?v=0.4.5";
import {
  request,
  setToken,
  connectWorkspace,
  getToken,
  downloadLog,
  terminal,
  DEMO_TOKEN,
} from "./api.js?v=0.4.1";
const $ = (q) => document.querySelector(q);
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const icons = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  host: "M4 3h16v7H4z M4 14h16v7H4z M7 6h.1 M7 17h.1",
  backup: "M12 3v12 M8 7l4-4 4 4 M3 12v8h18v-8",
  history: "M3 11a9 9 0 1 1 2 7 M3 4v7h7 M12 7v5l3 2",
  plus: "M12 5v14 M5 12h14",
  arrow: "M5 12h14 M14 7l5 5-5 5",
  close: "M6 6l12 12 M18 6L6 18",
  terminal: "M4 7l5 5-5 5 M12 17h8",
  update: "M12 20V4 M5 11l7-7 7 7",
  check: "M5 12l4 4L19 6",
  search: "M10 3a7 7 0 1 0 0 14a7 7 0 0 0 0-14 M16 16l5 5",
};
const icon = (n) =>
  `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${icons[n] || icons.grid}"/></svg>`;
const names = {
  refresh: "重新整理狀態",
  upgrade: "更新",
  start: "啟動",
  stop: "停止",
  restart: "重啟",
  backup: "備份",
  restore: "還原",
  install: "安裝套件",
  uninstall: "卸載套件",
  doctor: "檢查執行環境",
  run: "執行",
  register: "接入宿主",
  unregister: "解除接入",
  verify: "檢查載入版本",
};
const states = {
  online: "運行中",
  stopped: "已停止",
  unknown: "待確認",
  degraded: "部分異常",
  queued: "排隊中",
  running: "執行中",
  success: "成功",
  failed: "失敗",
};
const navs = [
  ["services", "受管對象", "grid"],
  ["plugins", "插件", "grid"],
  ["hosts", "主機", "host"],
  ["backups", "備份與還原", "backup"],
  ["history", "執行紀錄", "history"],
];
let data = null,
  page = "services",
  query = "",
  hostFilter = "",
  kindFilter = "",
  pluginCategory = "",
  pluginInstalled = "",
  stateFilter = "",
  jobId = null,
  jobLogs = [],
  jobCursor = 0,
  jobStream = "all",
  socket = null,
  connected = false,
  polling = false,
  authenticationRequired = false,
  nextPollAt = 0,
  toastTimer,
  jobSession = null,
  inputPending = false;
const date = (n) =>
  n
    ? new Date(n).toLocaleString("zh-TW", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "尚未讀取";
const badge = (s) =>
  `<span class="status ${["online", "success"].includes(s) ? "" : ["unknown", "stopped"].includes(s) ? "stopped" : s === "queued" ? "running" : s}"><i class="tiny-dot"></i>${states[s] || esc(s)}</span>`;
const kindNames = {
  service: "常駐服務",
  package: "套件／CLI",
  extension: "應用插件",
  tool: "一次性工具",
};
const resourceBadge = (s) =>
  busy(s.id)
    ? badge(busy(s.id).status)
    : s.available === false
      ? badge("插件未就緒")
      : ["package", "extension"].includes(s.kind)
        ? badge(
            s.status === "unknown"
              ? "unknown"
              : s.version === "absent"
                ? "未安裝"
                : s.bindings?.some((b) => b.needs_restart)
                  ? "宿主需重啟／檢查"
                  : "已安裝",
          )
        : badge(s.status);
const button = (label, action, id = "", style = "", symbol = "") =>
  `<button type="button" class="button ${style}" data-action="${action}" data-id="${esc(id)}">${symbol ? icon(symbol) : ""}${label}</button>`;
const busy = (id) =>
  data.jobs.find(
    (j) => j.resource_id === id && ["queued", "running"].includes(j.status),
  );
const host = (id) => data.hosts.find((h) => h.id === id);
function toast(t) {
  $("#toast").textContent = t;
  $("#toast").classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#toast").classList.remove("show"), 4000);
}
function modal(title, body, form = "", footer = "") {
  const m = $("#modal");
  if (m.open) m.close();
  m.innerHTML = `${form ? `<form id="${form}">` : ""}<div class="modal-head"><h2 id="modal-title">${title}</h2><button type="button" class="icon-button" data-action="close-modal" aria-label="關閉">${icon("close")}</button></div><div class="modal-body">${body}<p id="form-error" role="alert" class="form-error"></p></div>${footer ? `<div class="modal-foot">${footer}</div>` : ""}${form ? "</form>" : ""}`;
  m.showModal();
}
const submit = (t) =>
  `<button class="button primary" type="submit">${t}</button>`;
const field = (label, name, value = "", placeholder = "", type = "text") =>
  `<label class="field">${label}<input name="${name}" type="${type}" value="${esc(value)}" placeholder="${esc(placeholder)}" required></label>`;
function adapterFields(adapter) {
  const render = fields => fields
    .map(
      (f) =>
        `<label class="field">${esc(f.label)}${f.choices?.length ? `<select name="settings.${esc(f.name)}">${f.choices.map((c) => `<option ${c === f.initial ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>` : `<input name="settings.${esc(f.name)}" value="${esc(f.initial)}" ${f.required ? "required" : ""}>`}</label>`,
    )
    .join("");
  const fields = adapter?.fields || [];
  const advanced = fields.filter(f => (isCommandOverride(f.name) && !f.required));
  return render(fields.filter(f => !(isCommandOverride(f.name) && !f.required))) +
    (advanced.length ? `<details><summary>進階：自訂操作命令</summary><p>留空使用插件預設操作。填寫後僅覆寫此受管對象；其他對象不受影響。</p>${render(advanced)}</details>` : "");
}
function head(eyebrow, title, desc, actions = "") {
  return `${data?.mode === "demo" ? '<div class="notice">DEMO · 操作只模擬執行，資料由中央保存；不會連線真實主機。</div>' : ""}<div class="page-head"><div><div class="eyebrow">${eyebrow}</div><h1>${title}<span class="dot">.</span></h1><p class="description">${desc}</p></div><div class="head-actions">${actions}</div></div>`;
}
function serverName() {
  const hostname = location.hostname;
  return hostname.endsWith(".ts.net") ? hostname.split(".")[0] : hostname;
}
function updateConnectionChrome() {
  const control = $("#server-control"), notice = $("#connection-notice");
  const status = connected ? "已連線" : authenticationRequired ? "需要更新憑證" : getToken() ? "正在連線" : "尚未設定";
  control.querySelector("span").textContent = serverName();
  control.dataset.connected = String(connected);
  control.setAttribute("aria-label", `伺服器：${serverName()}，${status}`);
  control.title = `${location.origin} · ${status}`;
  notice.hidden = connected || !getToken();
  notice.innerHTML = notice.hidden ? "" : `${authenticationRequired ? "連線憑證已失效，請更新伺服器設定。" : data ? "正在重新連線，已保留目前畫面。" : "正在連接伺服器…"} ${button("伺服器設定", "connect", "", "compact")}`;
}
function render() {
  updateConnectionChrome();
  $("#navigation").innerHTML = navs
    .map(
      ([id, label, i]) =>
        `<a class="nav-item ${page === id ? "active" : ""}" href="#${id}" ${page === id ? 'aria-current="page"' : ""}>${icon(i)}<span>${label}</span></a>`,
    )
    .join("");
  $("#breadcrumb").textContent = navs.find((x) => x[0] === page)[1];
  if (!data) {
    $("#main").innerHTML = head(
      "UNIFIED / 0.4",
      getToken() ? "正在連接伺服器" : "連接伺服器",
      getToken() ? "正在自動連線；網路恢復後會重新載入最新狀態。" : "首次設定後，此瀏覽器會自動連接目前站點。",
      button("伺服器設定", "connect", "", "primary"),
    );
    return;
  }
  $("#main").innerHTML =
    page === "services"
      ? services()
      : page === "hosts"
        ? hosts()
        : page === "backups"
          ? backups()
          : page === "plugins"
            ? plugins()
            : history();
  const pending = data.jobs.filter((j) =>
    ["queued", "running"].includes(j.status),
  );
  $("#job-dock").innerHTML = pending.length
    ? `<button class="job-dock" data-action="job" data-id="${pending[0].id}"><span class="spinner"></span>${pending.length} 個背景任務 · 查看輸出 ${icon("arrow")}</button>`
    : "";
}
function serviceRows() {
  const list = (data.resources || data.services).filter(
    (s) =>
      (!query || s.name.toLowerCase().includes(query.toLowerCase())) &&
      (!hostFilter || s.host === hostFilter) &&
      (!stateFilter || s.status === stateFilter) &&
      (!kindFilter || (s.kind || "service") === kindFilter),
  );
  return list.length
    ? `<table class="service-table"><thead><tr><th>對象名稱</th><th>主機</th><th>狀態</th><th class="version-col">映像 / 版本</th><th>操作</th></tr></thead><tbody>${list.map((s) => `<tr><td><button class="service-name" data-action="service" data-id="${s.id}"><span class="service-logo">${esc(s.name[0])}</span><span><strong>${esc(s.name)}</strong><small>${esc(kindNames[s.kind || "service"])} · ${esc(s.adapter_label || s.adapter)}</small></span></button></td><td class="host-col">${esc(host(s.host)?.name)}</td><td class="status-col">${resourceBadge(s)}</td><td class="version-col"><span class="version" style="white-space:normal;overflow-wrap:anywhere">${esc(s.version)}</span></td><td class="actions-col">${button("操作", "service", s.id, "compact", "arrow")}</td></tr>`).join("")}</tbody></table>`
    : '<div class="empty">尚無符合條件的服務。新增受管對象後，重新整理狀態即可開始管理。</div>';
}
function services() {
  return `${head("YOUR INFRASTRUCTURE, AT A GLANCE", "受管對象", "跨主機管理服務、套件與工具，每次操作都有輸出。", button("新增受管對象", "add-service", "", "primary", "plus"))}<div class="stats">${[
    ["主機", data.hosts.length, "host"],
    [
      "運行中服務",
      (data.resources || data.services).filter(
        (s) => (s.kind || "service") === "service" && s.status === "online",
      ).length,
      "grid",
    ],
    [
      "背景任務",
      data.jobs.filter((j) => ["running", "queued"].includes(j.status)).length,
      "history",
    ],
    ["可還原備份", data.backups.length, "backup"],
  ]
    .map(
      ([t, n, i]) =>
        `<div class="stat"><div class="stat-label">${t}${icon(i)}</div><div class="stat-value">${n}</div></div>`,
    )
    .join(
      "",
    )}</div><div class="section-top"><h2>主機概況</h2><a class="text-button" href="#hosts">管理主機 →</a></div><div class="hosts-strip">${data.hosts.map((h) => `<button class="host-mini" data-action="host" data-id="${h.id}"><span class="host-icon">${icon("host")}</span><div class="host-info"><div class="host-name">${esc(h.name)}</div><div class="host-meta">${esc(h.address)} · ${(data.resources || data.services).filter((s) => s.host === h.id).length} services</div></div></button>`).join("")}</div><section class="panel"><div class="panel-heading section-top"><h2>所有受管對象</h2><span class="text-button">最近讀取狀態 · 點詳情重新整理</span></div><div class="toolbar"><div class="tabs">${[
    ["", "全部"],
    ["online", "運行中"],
    ["stopped", "已停止"],
    ["unknown", "待確認"],
  ]
    .map(
      ([id, t]) =>
        `<button class="tab ${stateFilter === id ? "active" : ""}" data-action="filter" data-id="${id}">${t}</button>`,
    )
    .join(
      "",
    )}</div><div class="filters"><div class="search">${icon("search")}<input id="search" aria-label="搜尋服務／套件／工具" placeholder="搜尋服務／套件／工具…" value="${esc(query)}"></div><select id="kind-filter" aria-label="類型篩選">${[
    ["", "全部類型"],
    ["service", "常駐服務"],
    ["package", "套件／CLI"],
    ["extension", "應用插件"],
    ["tool", "一次性工具"],
  ]
    .map(
      ([v, l]) =>
        `<option value="${v}" ${kindFilter === v ? "selected" : ""}>${l}</option>`,
    )
    .join(
      "",
    )}</select><select id="host-filter" aria-label="主機篩選"><option value="">所有主機</option>${data.hosts.map((h) => `<option value="${h.id}" ${hostFilter === h.id ? "selected" : ""}>${esc(h.name)}</option>`).join("")}</select></div></div><div id="service-results">${serviceRows()}</div><div class="table-footer">操作提交後，可在執行紀錄查看進度與輸出。</div></section><div class="bottom-grid"><section class="panel small-panel"><div class="section-top"><h2>最近活動</h2><a class="text-button" href="#history">查看全部 →</a></div>${data.jobs.slice(0, 3).map(activity).join("") || '<p class="description">執行第一個操作後，會在這裡留下紀錄。</p>'}</section><section class="panel small-panel"><h2>安心備份，隨時還原</h2><p class="description">集中管理已接入應用程式的設定。</p><div class="backup-summary">${icon("backup")}<div><strong>${esc(data.destination)}</strong><small>${data.backups.length} 份已驗證備份</small></div><a href="#backups">→</a></div></section></div>`;
}
function activity(j) {
  return `<button class="activity-row" data-action="job" data-id="${j.id}" style="width:100%;text-align:left"><span class="activity-symbol ${j.status}">${icon(j.status === "failed" ? "close" : j.status === "success" ? "check" : "history")}</span><div class="activity-content"><strong>${esc(j.target)} · ${names[j.action]}</strong><small>${date(j.date)}</small></div>${badge(j.status)}</button>`;
}
function hosts() {
  return (
    head(
      "CONNECTED MACHINES",
      "主機",
      "主機狀態反映最近一次服務操作的連線結果。",
      button("新增主機", "add-host", "", "primary", "plus"),
    ) +
    `<div class="host-grid">${data.hosts.map((h) => `<section class="panel host-card"><span class="host-icon">${icon("host")}</span><h3>${esc(h.name)}</h3><p class="description">${esc(h.address)}:${h.port} · ${esc(h.platform)}</p><p class="description">${(data.resources || data.services).filter((s) => s.host === h.id).length} 個服務 · ${badge(h.status)}</p>${button("主機詳情", "host", h.id, "", "arrow")}</section>`).join("") || '<div class="empty">新增第一台主機，開始集中管理。</div>'}</div>`
  );
}
function backups() {
  return (
    head(
      "BACK UP. RESTORE. RELAX.",
      "備份與還原",
      "應用程式設定快照",
      button("建立備份", "backup", "", "primary", "plus"),
    ) +
    `<div class="notice">${icon("backup")}${esc(data.destination)} · ${data.mode === "demo" ? "示範資料" : "備份位置與憑證由伺服器環境設定管理"}</div><section class="panel"><div class="panel-heading section-top"><h2>備份檔案</h2></div>${data.backups.map((b) => `<div class="backup-head"><span class="service-logo">${b.client === "Magpie" ? "M" : "S"}</span><div style="min-width:0;flex:1"><h3>${esc(b.client)}</h3><p style="overflow-wrap:anywhere">${esc(b.name)}</p><p>${date(b.date)} · ${(b.bytes / 1024).toFixed(1)} KiB</p></div>${canRestore(b) ? button("還原", "restore", b.id, "compact", "history") : '<span class="description">接入或儲存設定未就緒</span>'}</div>`).join("") || '<div class="empty">尚無備份。建立成功後將顯示在此處。</div>'}</section>`
  );
}
function plugins() {
  return (
    head(
      "INTEGRATIONS",
      "插件",
      "先安裝管理插件，再登記受管對象；安裝插件不會安裝遠端軟體。",
    ) +
    `<div class="toolbar">${button("建立命令插件", "plugin-create")}${button("匯入插件", "plugin-import")}<select id="plugin-category" aria-label="插件分類">${[
      ["", "全部分類"],
      ["service-management", "服務管理"],
      ["package-management", "套件與應用插件"],
      ["application-backup", "應用備份"],
      ["backup-storage", "備份儲存"],
    ]
      .map(
        ([v, l]) =>
          `<option value="${v}" ${v === pluginCategory ? "selected" : ""}>${l}</option>`,
      )
      .join(
        "",
      )}</select><select id="plugin-installed" aria-label="插件安裝狀態">${[
      ["", "全部"],
      ["available", "可安裝"],
      ["installed", "已安裝"],
    ]
      .map(
        ([v, l]) =>
          `<option value="${v}" ${v === pluginInstalled ? "selected" : ""}>${l}</option>`,
      )
      .join("")}</select></div><div class="host-grid">${(data.plugins || [])
      .filter(
        (p) =>
          (!pluginCategory || p.category === pluginCategory) &&
          (!pluginInstalled ||
            (pluginInstalled === "installed"
              ? Boolean(p.installed)
              : !p.installed)),
      )
      .map(
        (p) =>
          `<section class="panel host-card"><h3>${esc(p.label)}</h3><p>${esc(p.category)} · ${esc(p.version)}</p><p class="description">${esc(p.description || p.error)}</p><p>${p.installed ? `已安裝 ${esc(p.installed.version)} · ${p.installed.enabled ? "啟用" : "停用"}` : "尚未安裝"}</p><div class="detail-actions">${p.available !== false ? button("匯出 JSON", "plugin-export", p.id, "compact") : ""}${(p.available === false ? [] : !p.installed ? ["install"] : p.installed.enabled ? ["disable", "update", "remove", ...(p.installed.previous ? ["rollback"] : [])] : ["enable", "update", "remove", ...(p.installed.previous ? ["rollback"] : [])]).map((a) => button({ install: "Install", update: "更新插件", enable: "啟用", disable: "停用", remove: "移除", rollback: "回退" }[a], "plugin-change", p.id + ":" + a, "compact")).join("")}</div></section>`,
      )
      .join("")}</div>`
  );
}
function bindingDetails(s) {
  const rel = s.bindings || [];
  const allowed =
    (data.plugins || []).find((p) => p.id === s.adapter)?.hosts || [];
  const reverse = (data.resources || [])
    .flatMap((r) =>
      (r.bindings || [])
        .filter((b) => b.parent === s.id)
        .map(
          (b) =>
            `<p>${esc(r.name)} · 已安裝 ${esc(r.version)} · 載入 ${esc(b.loaded_version)} ${b.needs_restart ? "· 需重啟／檢查" : ""}</p>`,
        ),
    )
    .join("");
  return `<div class="detail-section"><h2>宿主關係</h2>${reverse}${rel.map((b) => `<div class="panel small-panel"><strong>${esc((data.resources || []).find((r) => r.id === b.parent)?.name)}</strong><p>${b.registered ? "已接入" : "未接入"} · 已載入 ${esc(b.loaded_version)} ${b.needs_restart ? "· 需重啟／檢查" : ""}</p>${(s.available ? ["register", "unregister", ...(b.verify_command ? ["verify"] : [])] : []).map((a) => button(names[a], "binding-job", s.id + ":" + a + ":" + b.id, "compact")).join("")}</div>`).join("")}${allowed.length && s.available ? button("關聯宿主", "bind", s.id) : ""}</div>`;
}
function bindingForm(id) {
  const s = (data.resources || []).find((r) => r.id === id),
    allowed = (data.plugins || []).find((p) => p.id === s.adapter)?.hosts || [];
  const parents = (data.resources || []).filter(
    (r) => r.host === s.host && allowed.includes(r.adapter),
  );
  if (!parents.length) return toast("請先登記同主機的相容應用服務。");
  modal(
    "關聯宿主",
    `<input type="hidden" name="resource" value="${id}"><label class="field">宿主<select name="parent">${parents.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join("")}</select></label><p class="description">填入此安裝方式的接入與解除命令。登記關係不會執行命令。可使用 UNIFIED_PACKAGE、UNIFIED_DIRECTORY、UNIFIED_VERSION 環境參數。載入檢查只輸出版本號、none（未載入）或 unknown。</p>${field("接入命令", "register_command")}${field("解除接入命令", "unregister_command")}<label class="field">載入版本檢查命令（選填）<input name="verify_command"></label>`,
    "binding-form",
    submit("儲存關係"),
  );
}
function history() {
  return (
    head(
      "EVERY ACTION, ACCOUNTED FOR",
      "執行紀錄",
      "任務持續在中央服務執行，可隨時重新開啟完整輸出。",
    ) +
    `<section class="panel small-panel">${data.jobs.map(activity).join("") || '<div class="empty">尚無執行紀錄。</div>'}</section>`
  );
}
function serviceDetail(id) {
  const s = (data.resources || data.services).find((s) => s.id === id);
  modal(
    "受管對象詳情",
    `<div class="detail-top"><span class="service-logo">${esc(s.name[0])}</span><div><h3>${esc(s.name)}</h3><p class="description">${resourceBadge(s)}</p></div></div><dl class="key-values"><div><dt>主機</dt><dd>${esc(host(s.host)?.name)}</dd></div><div><dt>接入類型</dt><dd>${esc(s.adapter_label || s.adapter)}</dd></div>${Object.entries(
      s.settings || {},
    )
      .map(
        ([key, value]) =>
          `<div><dt>${esc(
            serviceAdapters(data)
              .find((a) => a.id === s.adapter)
              ?.fields.find((f) => f.name === key)?.label || key,
          )}</dt><dd>${esc(value)}</dd></div>`,
      )
      .join(
        "",
      )}<div><dt>映像 / 版本</dt><dd>${esc(s.version)}</dd></div><div><dt>狀態讀取時間</dt><dd>${date(s.checked)}</dd></div></dl><div class="detail-actions">${
      busy(id)
        ? button("查看執行中任務", "job", busy(id).id, "primary")
        : serviceActions(s)
            .map((a) =>
              button(
                names[a],
                "operation",
                s.id + ":" + a,
                a === "stop" ? "danger" : "",
              ),
            )
            .join("")
    }${s.available === false ? '<p class="form-error">接入類型未就緒，請檢查伺服器設定。</p>' : ""}</div>${s.available ? button("編輯設定", "edit-resource", s.id) : ""}${bindingDetails(s)}<div class="detail-section"><h2>手動排錯</h2><p>由 Terminal Gateway 提供互動 SSH；操作 Job Console 保持獨立。</p>${button("開啟 SSH Terminal", "ssh", s.host, "", "terminal")}</div>`,
  );
}
function hostDetail(id) {
  const h = host(id);
  modal(
    "主機詳情",
    `<h3>${esc(h.name)}</h3><p class="description">${esc(h.username)}@${esc(h.address)}:${h.port}<br>私鑰參照：${esc(h.key)}</p><div class="detail-actions">${button("新增受管對象", "add-service", id, "primary", "plus")}${button("開啟 SSH Terminal", "ssh", id, "", "terminal")}</div>${(
      data.resources || data.services
    )
      .filter((s) => s.host === id)
      .map(
        (s) =>
          `<div class="activity-row">${button(esc(s.name), "service", s.id, "ghost")}${badge(s.status)}</div>`,
      )
      .join("")}`,
  );
}
function scenario() {
  return data.mode === "demo"
    ? '<label class="field">模擬情境<select name="scenario"><option value="normal">正常完成</option><option value="long">長時間背景任務</option><option value="fail">失敗與 stderr</option></select></label>'
    : "";
}
function operation(value) {
  const [id, action, binding] = value.split(":"),
    s = (data.resources || data.services).find((s) => s.id === id);
  if (!binding && !serviceActions(s).includes(action))
    return toast("此服務不支援這項操作。");
  modal(
    `${names[action]} ${esc(s.name)}`,
    `<input type="hidden" name="service" value="${id}"><input type="hidden" name="action" value="${action}"><input type="hidden" name="binding" value="${esc(binding || "")}"><p>${esc(host(s.host)?.name)} · ${esc(s.adapter_label || s.adapter)}</p>${action === "upgrade" ? '<div class="notice">依已登記的安裝範圍與版本策略更新。套件更新不會自動重啟宿主。</div>' : ""}${["uninstall", "unregister"].includes(action) ? '<label class="field"><input type="checkbox" name="confirm" required>確認卸載／解除接入</label>' : ""}${["stop", "restart", "upgrade"].includes(action) ? '<div class="danger-note">此操作可能造成服務短暫中斷。</div>' : ""}${scenario()}`,
    "operation-form",
    submit("開始執行"),
  );
}
async function sendJobInput(text, close = false) {
  if (inputPending || !jobSession || !jobId) return;
  const id = jobId;
  inputPending = true;
  try {
    const result = await request(`/jobs/${id}/session`, {
      generation: jobSession.generation,
      sequence: jobSession.sequence + 1,
      data: text,
      close,
    });
    if (jobId === id) jobSession = result;
  } finally {
    inputPending = false;
  }
}
async function openJob(id) {
  $("#modal").close();
  closeTerminal();
  jobId = id;
  jobCursor = 0;
  jobSession = null;
  jobLogs = [];
  jobStream = "all";
  const c = $("#console");
  if (c.open) c.close();
  c.innerHTML = `<div class="modal-head"><div><h2 id="console-title">Job Console</h2><div id="job-meta" class="console-title-meta"></div></div>${button("關閉", "close-console", "", "compact")}</div><div id="job-state" class="console-status"></div><div class="console-tools"><span class="tag">EXECUTION OUTPUT</span><label>串流 <select id="stream"><option value="all">全部</option><option>stdout</option><option>stderr</option></select></label></div><div class="terminal" id="output" role="log" aria-label="任務日誌"></div><pre id="session-output" style="max-height:150px;overflow:auto;white-space:pre-wrap"></pre><form id="job-input-form" class="terminal-input"><input name="input" aria-label="任務或 shell 輸入" autocomplete="off"><button type="submit" class="button">送出</button></form><div id="session-controls"></div><div class="console-hint">收起 Console 不會結束中央會話。排錯 shell 輸出不寫入任務日誌。</div><div class="console-foot"><span id="job-error" class="form-error"></span>${button("下載完整日誌", "download", id, "compact")}</div>`;
  c.showModal();
  await pollJob();
}
function renderLogs() {
  const out = $("#output");
  if (!out) return;
  const bottom = out.scrollHeight - out.scrollTop - out.clientHeight < 50;
  out.innerHTML = jobLogs
    .filter((l) => jobStream === "all" || l.stream === jobStream)
    .map(
      (l) =>
        `<div class="log-line"><span class="log-time">${new Date(l.time).toLocaleTimeString()}</span><span class="log-stream ${l.stream}">${l.stream}</span><span class="log-text ${l.stream === "stderr" ? "log-error" : ""}">${esc(l.text)}</span></div>`,
    )
    .join("");
  if (bottom) out.scrollTop = out.scrollHeight;
}
async function pollJob() {
  if (!jobId || !$("#console").open) return;
  const id = jobId;
  const [j, logs, session] = await Promise.all([
    request("/jobs/" + id),
    request("/jobs/" + id + "/logs?after=" + jobCursor),
    request("/jobs/" + id + "/session"),
  ]);
  if (id !== jobId || !$("#output")) return;
  if (
    !jobSession ||
    jobSession.generation !== session.generation ||
    session.sequence >= jobSession.sequence
  )
    jobSession = session;
  $("#session-output").textContent = session.output || "";
  $("#job-input-form input").disabled = !["running", "shell"].includes(
    session.phase,
  );
  $("#job-input-form button").disabled =
    !["running", "shell"].includes(session.phase) || inputPending;
  $("#session-controls").innerHTML = ["running", "shell"].includes(
    session.phase,
  )
    ? `<span>${session.phase === "shell" ? "排錯 shell" : "前台程序 · PTY 合併輸出"}</span>${button("Ctrl+C", "job-interrupt")}${button("結束會話", "job-end")}`
    : "此任務目前沒有互動會話（Demo 操作只模擬輸出）";
  jobLogs.push(...logs);
  if (logs.length) jobCursor = logs.at(-1).seq;
  $("#job-meta").textContent =
    j.target + " / " + names[j.action] + " · " + j.id;
  $("#job-state").innerHTML = badge(j.status) + `<span>${j.progress}%</span>`;
  $("#job-error").textContent = j.error || "";
  renderLogs();
}
function closeTerminal() {
  if (socket) {
    socket.close();
    socket = null;
  }
}
function ssh(id) {
  jobId = null;
  $("#modal").close();
  closeTerminal();
  const c = $("#console");
  if (c.open) c.close();
  c.innerHTML = `<div class="modal-head"><div><h2 id="console-title">Interactive SSH Terminal</h2><p class="console-title-meta">${esc(host(id).name)} · Terminal Gateway</p></div>${button("關閉", "close-console", "", "compact")}</div><div class="terminal" id="terminal-output" role="log"></div><form id="terminal-form" class="terminal-input"><span>$</span><input name="command" aria-label="終端指令" autocomplete="off"><button type="submit">送出 ↵</button></form><div class="console-tools">${button("Ctrl+C", "ctrl-c", "", "compact")}${button("Ctrl+D", "ctrl-d", "", "compact")}</div><div class="console-hint">行式互動終端，適合診斷指令與 shell 提示。全螢幕 TUI（如 vim / top）請使用專用 SSH 客戶端。</div>`;
  c.showModal();
  const out = $("#terminal-output");
  out.textContent = "Connecting…\n";
  socket = terminal(id);
  socket.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    out.textContent += msg.text;
    out.textContent = out.textContent.slice(-200000);
    out.scrollTop = out.scrollHeight;
  };
  socket.onerror = () => {
    out.textContent += "\n連線失敗，請檢查伺服器與 SSH 設定。";
  };
  socket.onclose = () => {
    out.textContent += "\n[工作階段已結束]";
  };
}
function login(edit = false) {
  if (connected && !edit) {
    modal("伺服器", `<section class="server-summary"><h3>${esc(serverName())}</h3><p class="server-address">${esc(location.origin)}</p><p class="description">已連線 · 開啟時自動連接</p></section>`, "", button("編輯連線", "edit-connection"));
    return;
  }
  modal(
    "連接伺服器",
    `<p class="server-address">${esc(location.origin)}</p><p>此網頁連接目前網址。成功連線後會記住 Token，之後自動連接。</p>${field("管理員 Token", "token", getToken(), "", "password")}`,
    "connect-form",
    submit("儲存並連線"),
  );
}
async function refresh() {
  if (polling || authenticationRequired || document.hidden || Date.now() < nextPollAt) return;
  polling = true;
  const credential = getToken();
  try {
    if (credential) {
      const next = await request("/snapshot"),
        changed = JSON.stringify(next) !== JSON.stringify(data) || !connected;
      if (getToken() !== credential) return;
      data = next;
      connected = true;
      nextPollAt = 0;
      if (changed && document.activeElement?.id !== "search") render();
      await pollJob();
    }
  } catch (e) {
    if (getToken() !== credential) return;
    connected = false;
    authenticationRequired = e.status === 401 || e.status === 403;
    nextPollAt = Date.now() + 5000;
    updateConnectionChrome();
    if ($("#job-error")) $("#job-error").textContent = e.message;
  } finally {
    polling = false;
  }
}
document.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-action]");
  if (!b) return;
  const a = b.dataset.action,
    id = b.dataset.id;
  try {
    if (a === "close-modal") $("#modal").close();
    else if (a === "close-console") {
      $("#console").close();
      jobId = null;
      closeTerminal();
    } else if (a === "connect") login();
    else if (a === "edit-connection") login(true);
    else if (a === "service") serviceDetail(id);
    else if (a === "host") hostDetail(id);
    else if (a === "operation" || a === "binding-job") operation(id);
    else if (a === "bind") bindingForm(id);
    else if (a === "edit-resource") {
      const s = (data.resources || []).find((r) => r.id === id),
        adapter = serviceAdapters(data).find((a) => a.id === s.adapter);
      modal(
        "編輯設定",
        `<input type="hidden" name="id" value="${id}"><input type="hidden" name="host" value="${s.host}"><input type="hidden" name="adapter" value="${esc(s.adapter)}">${field("名稱", "name", s.name)}<p>保留主機與安裝身份，可修改版本策略及操作命令。</p>${adapterFields({ ...adapter, fields: adapter.fields.map((f) => ({ ...f, initial: s.settings[f.name] ?? f.initial })) })}`,
        "edit-resource-form",
        submit("儲存"),
      );
    } else if (a === "plugin-create" || a === "plugin-import") {
      openPluginEditor(a === "plugin-create" ? "create" : "import", request, async () => {
        await refresh(); render(); toast("已儲存，請在插件卡片按 Install／更新插件");
      });
    } else if (a === "plugin-export") {
      b.disabled = true;
      try { downloadPlugin(await request(`/plugins/${id}/manifest`)); }
      finally { b.disabled = false; }
    } else if (a === "plugin-change") {
      const [plugin, action] = id.split(":");
      b.disabled = true;
      await request("/plugins/" + plugin, { action });
      await refresh();
      render();
    } else if (a === "job-interrupt" || a === "job-end")
      await sendJobInput(
        a === "job-interrupt" ? "\u0003" : "",
        a === "job-end",
      );
    else if (a === "job") await openJob(id);
    else if (a === "download") await downloadLog(id);
    else if (a === "filter") {
      stateFilter = id;
      render();
    } else if (a === "ssh") ssh(id);
    else if (a === "ctrl-c" || a === "ctrl-d") {
      if (socket?.readyState === 1)
        socket.send(
          JSON.stringify({
            type: "input",
            data: a === "ctrl-c" ? "\u0003" : "\u0004",
          }),
        );
    } else if (a === "add-host")
      modal(
        "新增主機",
        field("主機名稱", "name") +
          field("IP / DNS 位址", "address") +
          field("SSH Port", "port", "22", "", "number") +
          field("SSH 使用者", "username", "unified") +
          field("私鑰檔案名稱", "key", "id_ed25519") +
          '<p class="description">私鑰與 known_hosts 由伺服器掛載管理。</p>',
        "host-form",
        submit("新增主機"),
      );
    else if (a === "add-service") {
      if (!data.hosts.length) return toast("請先新增主機。");
      const adapters = serviceAdapters(data);
      if (!adapters.length) return toast("伺服器尚未提供可用的服務接入類型。");
      modal(
        "新增受管對象",
        field("對象名稱", "name") +
          `<label class="field">所在主機<select name="host">${data.hosts.map((h) => `<option value="${h.id}" ${h.id === id ? "selected" : ""}>${esc(h.name)}</option>`).join("")}</select></label>` +
          `<label class="field">接入類型<select name="adapter" id="service-adapter">${adapters.map((a) => `<option value="${esc(a.id)}">${esc(a.label)}</option>`).join("")}</select></label><div id="adapter-fields">${adapterFields(adapters[0])}</div>`,
        "service-form",
        submit("新增受管對象"),
      );
    } else if (a === "backup") {
      const apps = backupApplications(data);
      if (!apps.length) return toast("備份接入或儲存設定尚未就緒。");
      modal(
        "建立備份",
        `<label class="field">應用程式<select name="client">${apps.map((app) => `<option value="${esc(app.client)}">${esc(app.label)}</option>`).join("")}</select></label>${scenario()}<p class="description">備份應用程式設定至中央指定的儲存位置，並校驗遠端副本。</p>`,
        "backup-form",
        submit("開始備份"),
      );
    } else if (a === "restore") {
      const backup = data.backups.find((b) => b.id === id);
      if (!canRestore(backup)) return toast("還原接入或儲存設定尚未就緒。");
      modal(
        "還原 " + esc(backup.client),
        `<input type="hidden" name="backup" value="${id}"><p>${esc(backup.name)}</p><div class="danger-note">將覆蓋此應用程式設定。請先停止寫入這些設定的應用程式；上一份設定會保留供回復。</div><label class="radio-option"><input type="checkbox" name="confirm" required>確認還原此份備份</label>${scenario()}`,
        "restore-form",
        submit("開始還原"),
      );
    } else if (a === "architecture")
      modal(
        "共同能力，兩種客戶端",
        '<div class="architecture-grid"><div class="architecture-box">Web UI<small>HTML / JavaScript</small></div><div class="architecture-box">Android App<small>Kotlin / Jetpack Compose</small></div></div><div class="architecture-arrow">↓　HTTP API / WebSocket　↓</div><div class="architecture-central"><strong>nas-host · Application Layer</strong><p>服務管理 · 背景任務 · SQLite<br>SSH Gateway · WebDAV 備份還原</p></div><p class="description">兩個客戶端共用 API 與相同操作能力。任務、憑證和執行結果由中央層管理。</p>',
      );
  } catch (err) {
    toast(err.message);
  }
});
document.addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target,
    d = Object.fromEntries(new FormData(f));
  if (f.id === "job-input-form") {
    try {
      await sendJobInput(d.input + "\n");
      f.reset();
    } catch (err) {
      toast(err.message);
    }
    return;
  }
  if (f.id === "terminal-form") {
    if (socket?.readyState === 1)
      socket.send(JSON.stringify({ type: "input", data: d.command + "\n" }));
    f.reset();
    return;
  }
  const b = f.querySelector("[type=submit]");
  if (b) b.disabled = true;
  try {
    let j;
    if (f.id === "connect-form") {
      data = await connectWorkspace(d.token.trim());
      authenticationRequired = false;
      nextPollAt = 0;
      connected = true;
    } else if (f.id === "host-form")
      await request("/hosts", { ...d, port: Number(d.port) });
    else if (f.id === "service-form")
      await request("/resources", serviceBody(d));
    else if (f.id === "edit-resource-form")
      await request(`/resources/${d.id}`, serviceBody(d));
    else if (f.id === "binding-form")
      await request(`/resources/${d.resource}/bindings`, {
        parent: d.parent,
        register_command: d.register_command,
        unregister_command: d.unregister_command,
        verify_command: d.verify_command,
      });
    else if (f.id === "operation-form")
      j = await request(`/resources/${d.service}/jobs`, {
        confirm: Boolean(d.confirm),
        binding: d.binding || null,
        action: d.action,
        scenario: d.scenario || "normal",
      });
    else if (f.id === "backup-form")
      j = await request("/backups", {
        client: d.client,
        scenario: d.scenario || "normal",
      });
    else if (f.id === "restore-form")
      j = await request(`/backups/${d.backup}/restore`, {
        confirm: true,
        scenario: d.scenario || "normal",
      });
    $("#modal").close();
    await refresh();
    render();
    if (j) await openJob(j.id);
  } catch (err) {
    $("#form-error").textContent = err.message;
  } finally {
    if (b) b.disabled = false;
  }
});
document.addEventListener("input", (e) => {
  if (e.target.id === "search") {
    query = e.target.value;
    $("#service-results").innerHTML = serviceRows();
  }
});
document.addEventListener("change", (e) => {
  if (e.target.id === "service-adapter") {
    $("#adapter-fields").innerHTML = adapterFields(
      serviceAdapters(data).find((a) => a.id === e.target.value),
    );
  }
  if (e.target.id === "plugin-category" || e.target.id === "plugin-installed") {
    if (e.target.id === "plugin-category") pluginCategory = e.target.value;
    else pluginInstalled = e.target.value;
    render();
  }
  if (e.target.id === "kind-filter") {
    kindFilter = e.target.value;
    $("#service-results").innerHTML = serviceRows();
  }
  if (e.target.id === "host-filter") {
    hostFilter = e.target.value;
    $("#service-results").innerHTML = serviceRows();
  } else if (e.target.id === "stream") {
    jobStream = e.target.value;
    renderLogs();
  }
});
$("#console").addEventListener("close", () => {
  jobId = null;
  closeTerminal();
});
window.addEventListener("hashchange", () => {
  page = navs.some((n) => n[0] === location.hash.slice(1))
    ? location.hash.slice(1)
    : "services";
  render();
  window.scrollTo(0, 0);
});
page = navs.some((n) => n[0] === location.hash.slice(1))
  ? location.hash.slice(1)
  : "services";
$(".brand-sub").textContent = "SERVICE MANAGER / 0.4";
$(".profile div span").textContent = "個人工作區";
$(".small-badge").textContent = "0.4";
render();
try {
  if (!getToken()) {
    const info = await request("/info");
    if (info.mode === "demo") setToken(DEMO_TOKEN);
  }
  if (getToken()) {
    await refresh();
    if (connected) setToken(getToken()); // Migrate a verified session-only connection.
    if (authenticationRequired) login();
  } else login();
} catch {
  if (!getToken()) login();
}
setInterval(refresh, 1000);
function resumeConnection() {
  if (!document.hidden) { nextPollAt = 0; refresh(); }
}
document.addEventListener("visibilitychange", resumeConnection);
window.addEventListener("online", resumeConnection);
