# Release review · 0.6.0

## Delivered behavior

Web and Android create independent service, package, extension and tool plugins through Compose, npm or administrator-authored command methods. Each document has its own identity/version and goes through server validation, preview, catalog save and explicit Install. npm runtime paths, install scope, package identity and software version are separate from plugin metadata.

Copy preserves the complete available manifest and requires a fresh ID. Both preview and save use create_only=true; Application checks local, remote and installed catalogs under its lifecycle guard. Ordinary JSON import retains the deliberate override workflow.

Compose adapters bind installed manifest descriptors and enforce supported operations, service kind and compose_dir fields. Normalized host/directory locks apply across plugin IDs. Real Compose operations use the central interactive job session, including diagnostic input. Existing installed manifests, records and persistent mount paths are preserved.

## Validation and publication gates

- Backend fixture coverage includes independent Compose installation/restart, defaults, operation enforcement, cross-ID target locking, real-mode interactive session routing with mocked transports, npm extension installation, remote ID collisions and preview/save races.
- Web checks cover generated documents, method/kind constraints and lossless copying. Browser acceptance uses isolated demo containers to create Compose/npm definitions and copy an existing Compose package; saved packages remain uninstalled.
- Native JVM/Compose tests exercise creation, method changes, copying, source-ID rejection, create-only request intent and explicit saving. Shared-device acceptance uses an isolated test application and synthetic state, including Compose creation, connection recovery, adaptive state and crash-log recovery. It does not modify the daily application or connect to managed hosts.
- Docker entrypoint and OMV fixtures verify startup and persistent plugin data. Existing Compose/env layouts remain valid.
- Before publication, review the complete staged diff, exported tree, reachable history, APK payload/strings/signer and every image layer/config/history. Gitleaks and HIGH/CRITICAL vulnerability gates run locally and again in the publishing workflow. Exact reviewed commit/image identifiers belong in the release receipt and workflow summary.

## Upgrade

Pull both 0.6.0 images (or latest after publication), then Up. Install Android 0.6.0, versionCode 17. Personal Compose IDs and create-only requests require the 0.6.0 Application. Existing plugins remain at their installed versions until explicitly updated. Upgrading image/client binaries does not install remote software.

Real host commands and physical fold transitions require separate acceptance on explicitly authorized targets. Demo and mocked-transport success only establish application behavior.
