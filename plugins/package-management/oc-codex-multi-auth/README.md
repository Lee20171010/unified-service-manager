# oc-codex-multi-auth

This integration manages an explicitly selected npm-owned CLI installation and its OpenCode relation. It does not adopt or rewrite OpenCode's existing private cache automatically. Current upstream requires Node 22.19+.

Install the Unified package from Plugin, register the scope and executables, and separately run Install. Configure host registration/unregistration for the actual OpenCode version. Upstream's CLI installer (`scripts/install-oc-codex-multi-auth.js` within the installed package) supports `--plugin-only`, `--v2` and `--dry-run`; its `update` command refreshes its managed cache without changing configuration. That cache and the CLI prefix are different installations. Do not substitute CLI version for an observed OpenCode-loaded version.

Removal from host configuration is manual upstream; a saved administrator unregister recipe must preserve unrelated configuration. This release intentionally requires explicit binding recipes rather than silently editing unknown JSON/JSONC files. Package uninstall is blocked while a host relation is registered or its loaded state is not confirmed as `none`.

Account pools, OAuth credentials and account diagnostics are not read by this integration. The environment-check action checks Node/package observations only.

Reference: https://github.com/ndycode/oc-codex-multi-auth (checked 2026-10-27).
