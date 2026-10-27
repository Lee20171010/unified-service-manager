# OpenChamber · 插件 1.1.0

提供状态、版本、启动、停止、重启、升级和环境检查。支持 Linux、Python 3 及已存在的 systemd 单元，默认 user 范围 `openchamber.service`。请填写目标主机实际的程序路径、单元和范围；默认命令不负责创建服务单元。

升级：更新所选 npm 全局前缀中的 @openchamber/web，先解析精确版本。只有原先运行中的所选单元在更新成功后重启；停止状态保持。详见 [目录与支持范围](../../../docs/PLUGIN-CATALOG.md)，其中说明包来源、权限及共享安装的限制。

在插件页导入 JSON 并 Install/Update，再创建受管对象。一般参数无需编写命令；进阶命令可覆盖单个对象的默认操作，现有自定义命令优先保留。SSH 账号需要实际操作权限。

源码：`plugin-sources/linux-service.py`；生成：`python3 scripts/build-plugin-catalog.py`。生成的 JSON 自包含，可独立分享；修改内容须递增版本。验证见 `backend/tests/test_catalog_recipes.py`，隔离命令桩不代表真实主机验收。
