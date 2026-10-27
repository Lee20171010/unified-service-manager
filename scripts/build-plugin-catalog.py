#!/usr/bin/env python3
"""Compile self-contained, portable interface-v1 service recipes into their JSON packages."""
import argparse
import json
from pathlib import Path
import shlex

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "plugin-sources/linux-service.py").read_text()
OPERATIONS = ["refresh", "start", "stop", "restart", "upgrade", "doctor"]
LABELS = {"refresh": "狀態", "start": "啟動", "stop": "停止", "restart": "重啟", "upgrade": "升級", "doctor": "環境檢查"}
UNITS = {"opencode": "opencode.service", "openchamber": "openchamber.service", "hermes": "hermes-gateway.service", "chatgpt": "app-chatgpt@autostart.service"}
DESCRIPTIONS = {
    "opencode": "Linux systemd 服務管理、版本查詢與 opencode upgrade；填寫現有服務單元與 CLI 路徑即可使用。",
    "openchamber": "Linux systemd 啟停與版本查詢；升級指定 npm 全域安裝，僅重啟所選服務。",
    "hermes": "Linux systemd Gateway 啟停、版本查詢與 Hermes 原生升級；延後上游重啟，只重啟所選服務。",
    "chatgpt": "Linux DEB 桌面應用的 systemd 單元管理、版本查詢與 APT 升級；需已有服務單元及套件來源。",
}

def build(check=False):
    for name in UNITS:
        path = ROOT / "plugins/service-management" / name / "plugin.json"
        manifest = json.loads(path.read_text())
        manifest.update(version="1.1.0", description=DESCRIPTIONS[name], operations=OPERATIONS,
            commands={action: "python3 -c " + shlex.quote(SOURCE) + " " + name + " " + action for action in OPERATIONS})
        def field(name, label, initial="", required=True, choices=()):
            return dict(name=name, label=label, initial=initial, required=required, choices=list(choices))
        manifest["fields"] = [
            field("directory", "遠端工作目錄", "/"),
            field("identity", "實例識別名稱", name),
            field("binary", "程式名稱或絕對路徑", name),
            field("service_scope", "systemd 範圍", "user", choices=["user", "system"]),
            field("unit", "現有 systemd 服務單元", UNITS[name]),
        ]
        if name == "openchamber":
            manifest["fields"].append(field("version", "升級版本（latest 或完整版本號）", "latest"))
        manifest["fields"] += [field("cmd_" + action, LABELS[action] + "自訂命令（留空使用插件預設）", required=False) for action in OPERATIONS]
        rendered = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        if check:
            if path.read_text() != rendered:
                raise SystemExit(f"Regenerate {path.relative_to(ROOT)}")
        else:
            path.write_text(rendered)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    build(check=parser.parse_args().check)
