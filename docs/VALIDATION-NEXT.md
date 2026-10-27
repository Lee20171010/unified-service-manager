# 下一版设计预览验证 · 2026-10-27

范围：`prototype/next/` 互动 HTML 与 `DESIGN-NEXT.md` 设计草案。现有 production Web、backend、Android 和原版 `prototype/` 根页面没有功能变更。

## 自动检查

- `node --check prototype/next/app.mjs`：通过。
- `node --check prototype/next/model.mjs`：通过。
- `node --check prototype/next/resources.mjs`：通过。
- `node --test tests/prototype-next.test.mjs tests/prototype-resources.test.mjs`：26 项通过。
- 设计相关 8 个 Markdown 文件的本地链接检查通过。
- tailnet 入口 `https://manager.example.com/next/`：HTTP 200，浏览器可打开。

Mock 模型覆盖：catalog 存在而安装状态为空、显式安装、交互升级等待／继续／退出后返回 shell、终态任务与会话分离、关闭会话后拒绝输入、失效 generation 拒绝、同目标锁、活动任务阻止插件停用、应用与存储双插件门槛、失败还原、页面重载中断且不重跑、新工具参数化任务、单 worker 等待输入时其他目标排队。

这些测试验证 UI 模型状态转换，不证明真实 SSH 程序控制、套件安装或备份完整性。

## 浏览器操作验证

在 tailnet HTTPS 页面通过真实表单和按钮操作：

1. 首次打开零插件，catalog 显示 12 个设计用包（包含本次新增的三个套件管理包）。
2. 手动安装 OpenCode；新增 Mock 主机与服务，五项标准操作出现在详情。
3. 升级等待 y/n；模拟断线后输入关闭；重连后向同一任务输入 y，最终成功并返回 shell，支持直接排错。
4. 安装通用插件；新增 android-test-env 一次性工具，填入参数并执行成功。
5. 未装备份插件时提示依赖；分别安装 Magpie 和 WebDAV，配置示范目的地，备份在 Console 收起后完成。
6. 还原需要确认；模拟校验失败显示 stderr 及未修改原设置。
7. 390 × 844 窄屏检查底部导航、服务列表与 Console；切换浅色，PTY 模式标示合并输出。
8. 收起并重开同一 PTY 升级任务，Ctrl+C 后任务标为中断并回到 shell，仍可输入排错。
9. 停用 OpenCode 后服务记录仍在，托管操作关闭并显示插件修复入口。

截图：`preview/next-interactive-upgrade.png`、`preview/next-mobile-services.png`、`preview/next-mobile-console.png`、`preview/next-plugin-catalog.png`。

## 尚未交付的执行能力

本次没有构建或部署新的 backend／Web production 映像或 APK，没有连接真实受管主机、修改真实应用设置或调用 WebDAV。没有 Android 设备验收。前台升级提示模拟 y/n；升级退出后模拟 shell 支持 pwd、ls、cd、whoami、hostname、echo、ps、status、journalctl、clear、exit，其他输入只显示模拟说明。敏感输入、真正的 stdin／PTY、控制权、协议去重、版本更新／回退和数据库迁移仍需按设计实施并测试。

浏览器间 Mock 数据不共享；页面重载会中断模拟执行器。正式设计由中央持有任务和程序，客户端重载可重新接入仍存活的任务。

## Shell 交互修正验证

新增模型测试验证：前台升级不把输入误当 shell 指令、成功／失败／中断后返回 shell、排错不修改任务终态和日志、exit 后拒绝输入、页面重载不恢复旧会话、临时 shell 内容不写入浏览器持久存储。

浏览器实测：前台输入 ls 得到升级程序响应；输入 y 后成功并回到提示符；同一 Console 执行 pwd、ls、whoami、cd 后保留当前目录；模拟断线重连；向上键恢复本次 shell 指令；exit 后输入关闭。390 × 844 手机布局验证 Ctrl+C 后直接执行 status，原任务仍为中断。截图：`preview/next-shell-debug.png`、`preview/next-shell-mobile.png`。

正式 Shell／PTY、认证与主机权限仍为待实现设计，本次没有开启实际 shell 连接或更改现有生产服务。

## 套件与应用插件验证

本次加入 npm-packages、billion-context、oc-codex-multi-auth 三个可手动安装的管理插件，以及常驻服务、套件／CLI、应用插件、一次性工具四种对象视图。

新增 13 项模型测试覆盖：管理插件安装与远端套件安装分离、通用 scoped npm 包、跨管理插件的安装身份去重、输入及固定版本校验、同主机同帐号宿主关联、专用插件兼容性、已安装与已载入版本分离、解除接入及卸载门槛、相关宿主锁定与提交时版本固定、失败／中断保留版本、停用保留对象、共享套件按宿主分别载入、活动接入任务阻止宿主管理插件停用。

浏览器实际操作：

1. 手动安装三个管理插件，以表单建立 bili、通用 `@example/cli` 和 oc-codex-multi-auth Mock 对象。
2. 将 bili 关联 OpenCode，执行接入任务，再明确重启 OpenCode，显示已载入 `1.0.0-mock`。
3. 通过交互 Console 升级 bili 并输入 y；完成后已安装版本为 `2.0.0-mock`，OpenCode 仍载入 `1.0.0-mock`，页面提示需要重启。
4. 通用 npm 对象由未安装执行安装任务；套件详情只显示适用操作。
5. auth 插件使用宿主管理范围，关联 OpenCode 后仍显示未接入，等待独立接入任务。
6. 390 × 844 检查类型筛选、安装范围、版本和宿主关系详情。

截图：`preview/next-managed-resources.png`、`preview/next-package-mobile.png`。执行器和版本均为 Mock；未运行 npm、bili 或 auth 安装器，也没有读取 OAuth 凭据或真实应用配置。正式 API、持久化迁移和 Android 同等功能仍按 `MANAGED-RESOURCES.md` 接续实现。
