# 插件开发与 UI 发布 · 0.4

Web 与 Android 均在「插件」页面提供创建、导入和导出。Application、Web、APK 首次升级至 0.4.0 后，支持范围内的后续插件发布无需重建镜像或客户端。导入内容保存在现有 data 持久化目录，不需要进入 Docker 或增加挂载。

## 创建命令插件

点击「建立命令插件」，填写稳定 ID、显示名称、独立版本、作者、说明、对象类型及远端工作目录。为需要的操作填写命令；留空的操作不会加入插件。可增加自定义参数：字段名、标签、默认值、必填以及逗号分隔的选项。`directory`、`identity` 是基础字段，不要重复定义；最多 22 个自定义参数。

例如字段 `mode`、选项 `check,repair`，执行命令可填写 `./my-tool --mode "$UNIFIED_MODE"`。参数以环境变量传给远端，命令中应加引号。工作目录属于被管理主机，程序或脚本也应已在那台主机准备好。状态命令可输出 `active`、`stopped` 或 `{"status":"online","version":"1.2.3"}`。

点击「校验与预览」，检查完整参数、命令、将替换的可用版本及当前已安装版本，再「保存到可安装」。最后在卡片按 Install；建立资源并选择主机后才能执行命令。

## 导入与分享

开发者可在自己的电脑编写 `plugin.json`，参考 [interface v1 示例](RUNTIME-0.3.md#package-authoring-without-a-core-rebuild) 或仓库 `plugins/`。每个插件建议独立文件夹并附 README，说明支持的环境、远端安装方式、权限、参数、命令副作用和测试方法。

在任一客户端选择「导入插件」，选择 JSON 文件或粘贴内容。服务器校验后预览，再保存到可安装。文件及服务器规范化 JSON 均限制为 128 KiB。JSON 的字段与类型须符合接口；ZIP、任意核心代码、自动依赖安装不属于此接口。

点击卡片「导出 JSON」，Web 下载文件，Android 选择系统保存位置。导出的是卡片对应的可用版本，包含命令定义和字段默认值。请勿把密码、私钥等凭据写入这些定义。主机账号、资源实例设置及安装状态不随插件导出。

## 更新和存储

- ID 保持不变；修改内容必须增加版本，如 `1.0.0` → `1.1.0`。
- 导入已存在 ID 的新版本会替换可安装目录项，预览会说明替换关系。安装版本及运行中任务保持原状，需在卡片手动 Update。
- 同一版本的内容不可覆盖。导入重复且相同的内容可安全重复保存。
- 更新安装版本前须等相关任务结束；已有回退、禁用、移除操作仍然适用。
- UI 文件：`/data/plugins/catalog/<id>/plugin.json`，按 ID 独立目录，分类来自 manifest 的 `category`。UI 文件优先于只读 `/plugin-catalog` 中同 ID 的包。
- 已安装且带校验和的副本：`/data/plugins/packages/<id>/<version>/plugin.json`。可安装与已安装目录分离。
- 备份整个 data 目录会同时包含导入文件和安装记录。回退到 0.3 前保留 0.4 数据备份；0.3 不发现 UI 导入目录，但已安装 interface v1 副本格式兼容。

## 开发边界与测试

`commands` 和 `npm` 是可复用执行驱动。UI 创建表单覆盖命令插件；其他现有驱动使用 JSON 导入。Compose、Magpie、ServerBox、WebDAV 原语绑定现有 ID，全新执行协议或备份格式需要扩展核心。命令使用所选 SSH 账号权限，插件不构成隔离沙箱。

先在 demo 验证表单、安装、资源创建和输出交互。demo 不执行真实命令；实际命令要在专用测试主机/目录验证成功、失败、参数引用和状态返回，不能把 demo 成功当成真实运行证明。中央回归测试 `bash scripts/test.sh`；Android `android/gradlew -p android :app:assembleDebug :app:testDebugUnitTest --max-workers=1`。
