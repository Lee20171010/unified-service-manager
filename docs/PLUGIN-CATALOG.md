# 插件目录与默认操作

目录提供 11 个具体管理插件。用户仍需在插件页按 Install，再新增受管对象并选择主机。创建自己的插件时选择「服务」或「工具」即可；这两个类型不需要另装一个通用插件。

| 插件 | 安装后提供的管理能力 | 环境与需要填写的参数 |
| --- | --- | --- |
| Docker Compose | 状态、启动、停止、重启、拉取镜像并更新 | 已有 Compose 项目；主机、项目目录及服务名 |
| OpenCode | 状态、版本、启停、重启、升级、环境检查 | Linux、Python 3、已有 systemd 服务及 opencode CLI |
| OpenChamber | 状态、版本、启停、重启、升级、环境检查 | Linux、Python 3、systemd 服务、npm 全局安装的 @openchamber/web |
| Hermes | Gateway 状态、版本、启停、重启、升级、环境检查 | Linux、Python 3、systemd Gateway、支持 --no-gateway-restart 的 Hermes |
| ChatGPT | 状态、DEB 版本、启停、重启、APT 升级、环境检查 | Linux DEB 包 chatgpt、已有 systemd 单元；升级需要包来源与包管理权限 |
| npm 套件／CLI | 安装、查版本、升级、卸载、Node 检查 | npm 管理的用户前缀或项目目录、Node/npm 路径、包名称和版本 |
| billion-context | 上述 npm 操作，固定包名；可关联 OpenCode/Hermes | 安装位置、Node/npm 路径及版本；应用注册/移除/已加载版本探针需配置对应安装方式的命令 |
| oc-codex-multi-auth | 上述 npm 操作，固定包名；可关联 OpenCode | 安装位置、Node/npm 路径及版本；应用注册/移除/探针需配置命令，OAuth 账号不在此管理 |
| Magpie | 配置快照备份、还原 | Application 可读取的 Magpie 配置源目录、WebDAV 目的地 |
| Flutter ServerBox | 配置快照备份、还原 | Application 可读取的配置导出目录、WebDAV 目的地 |
| WebDAV | 提供远端快照存储 | WebDAV URL、凭据和远端目录 |

备份插件处理挂载到 Application 的配置文件，不能直接读取手机应用的私有数据。npm 的环境检查验证所选 Node 和包的观察结果，不等同于检查宿主应用已加载插件。

## 服务默认操作

OpenCode、OpenChamber、Hermes、ChatGPT 的插件版本为 1.1.0。填写远端工作目录、实例识别名称、程序路径、systemd 范围及一个准确的服务单元名称，便可使用六项默认操作。程序路径可填绝对路径；使用名称时会先查 PATH，再查常见用户安装位置。多个候选路径会要求明确选择。

这些插件管理已经安装的软件和服务单元。默认范围为 user，默认单元分别为 opencode.service、openchamber.service、hermes-gateway.service、app-chatgpt@autostart.service；应改成目标主机实际使用的名称。通过 system scope 操作系统服务时，SSH 账号必须已有相应授权。ChatGPT 是 Linux 桌面应用，需要对应用户图形会话；普通 NAS 通常不满足这个环境。

- OpenCode 调用 `opencode upgrade`。
- OpenChamber 确认选中程序属于 npm 全局安装，解析 latest 或指定版本为精确版本，再更新该前缀中的 @openchamber/web。避免调用会处理全部实例的更新器。
- Hermes 检查更新器支持延后 Gateway 重启，再运行 `hermes update --no-gateway-restart`。
- ChatGPT 调用 `apt-get install --only-upgrade chatgpt`。非 root 使用 `sudo -n`，需预先授权；APT 使用主机现有包索引，版本是否可更新取决于配置的来源。没有来源时不会自动下载未知安装包。

升级成功后，仅对原先运行中的所选服务执行 restart；原先停止的服务保持停止。更新器失败不会接着重启。多个服务共享同一安装目录时，新代码会影响共用该目录的实例；需要逐一检查，默认命令不会重启其他单元。系统包自己的安装脚本仍按其上游行为执行。

Job Console 显示执行输出，支持升级程序的交互输入。环境检查和状态查询用有限时间的只读命令。缺少单元、程序或不支持的安装方式会明确失败，不能把成功的命令退出码当成运行状态。

「进阶：自订操作命令」可覆盖单个受管对象的操作；非空的实例命令优先于插件默认命令。留空使用该插件提供的默认值。已有自订命令在更新插件后继续有效。作者声明为必填的命令字段仍直接显示。

## 自己新增服务和工具

两者都通过同一个「建立命令插件」入口创建：

- 服务：持续运行，通常提供状态、启停和重启，例如自己的 halogen 服务。
- 工具：按需执行，完成后退出，例如一次检查或构建任务；不必伪造常驻运行状态。

类型决定操作和状态表达，插件负责实际命令与参数。仓库 `examples/plugin-authoring/` 提供作者参考，不放在新安装的可安装目录。已经安装的旧通用插件及用户导入的同名插件继续保留。

## 更新已经部署的目录

本次默认操作与表单调整由 Application／Web／Android 0.4.5 提供。先通过 OMV Compose Pull → Up 更新核心，再导入新版 JSON；安装 APK 本身不会更新 NAS。

OMV 的 plugin-catalog 是持久化卷，更新镜像不会覆盖里面已有的定义。升级到 0.4.5 或更新的兼容版本后，可在插件页「导入插件」选择新版 `plugin.json`，校验并保存，再按 Update（尚未安装则按 Install）。导入和启用是两个步骤，资源设置保留。后续同接口的插件更新只需重复导入/Update，不用重建镜像。

导出的目录 ZIP 是分发包：解压后逐个导入 JSON，UI 不直接导入 ZIP。已安装文件以独立版本和校验和保存，可以回退。billion-context 的显示名称统一为包名；插件 ID 未变，现有对象和关联不变。

## 开发与验证

服务配方源码在 `plugin-sources/linux-service.py`；运行 `python3 scripts/build-plugin-catalog.py` 生成四个独立、自包含的 JSON。目标主机需要 Python 3；无需把此源码复制到容器或 SSH 主机。每个插件仍能单独导出、导入和升级。

运行 `python3 scripts/build-plugin-catalog.py --check` 检查源码和发行 JSON 一致。`backend/tests/test_catalog_recipes.py` 用隔离的命令桩验证六项操作、指定目标、空格路径、版本、升级失败、停止状态保持、默认值和覆盖优先级；这些是 fixture 结果，不是用户主机的运行验收。Web/Android 表单均验证进阶命令折叠时仍保留原值。

上游依据：[OpenCode CLI](https://opencode.ai/docs/cli/)、[OpenChamber](https://github.com/openchamber/openchamber)、[Hermes CLI](https://hermes-agent.nousresearch.com/docs/reference/cli-commands)。具体插件目录的 README 说明所支持安装方式。
