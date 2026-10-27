# bili / billion-context

Install this Unified management package from Plugin. Register an npm-owned user prefix or project installation; then submit a separate package install/upgrade job. Node 20+ is required by the current upstream package. An installed CLI is distinct from code already loaded by OpenCode/Hermes.

For a user-prefix installation, an administrator can configure a binding recipe using the selected Node path and `$UNIFIED_DIRECTORY/lib/node_modules/billion-context/dist/index.js`. Upstream native integration verbs are `plugin install opencode`, `plugin remove opencode`, `plugin install hermes`, and `plugin remove hermes`. Use the actual absolute Node path in the recipe; project installations use `node_modules/` directly. Registration affects the SSH account's actual host application configuration. Review the upstream instructions for that installed version before saving recipes.

The package update job pins and installs the requested npm version. It does not automatically invoke bili's own autonomous updater, restart hosts, or infer loaded versions. Configure a probe against the particular running instance. The upstream `/__bili/status` response exposes `version` and `diskVersion`; a probe must select the intended local instance and emit only its loaded version. If that cannot be proven, leave the observation unknown.

Reference: https://github.com/ranxianglei/billion-context (checked 2026-10-27).
