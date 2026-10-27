#!/usr/bin/env bash
set -euo pipefail
audit_tools=${1:?Usage: install-audit-tools.sh /absolute/tool-directory}
mkdir -p "$audit_tools"
cd "$audit_tools"
curl -fsSL https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz -o gitleaks.tar.gz
printf '%s\n' '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb  gitleaks.tar.gz' | sha256sum -c -
tar -xzf gitleaks.tar.gz gitleaks
curl -fsSL https://github.com/aquasecurity/trivy/releases/download/v0.76.1/trivy_0.76.1_Linux-64bit.tar.gz -o trivy.tar.gz
printf '%s\n' 'c7cbe3137fb8a48a17574bede3dd6beb16742d1e9772929940fc90082c39d9c0  trivy.tar.gz' | sha256sum -c -
tar -xzf trivy.tar.gz trivy
