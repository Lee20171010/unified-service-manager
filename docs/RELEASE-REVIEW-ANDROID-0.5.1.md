# Android 0.5.1 release review

This native-only release adapts navigation, host/resource details and catalog/list columns to the current window. It preserves selected IDs, page and scroll positions across resizing, and keeps unsent connection/form/console drafts in ViewModel-owned memory through Activity recreation. Explicit close or a successful workspace change clears the relevant drafts. Process death discards them.

Application/Web remain 0.5.0 with API/schema v1. No container image, Compose, environment variable or server storage migration is required. The APK keeps the existing application ID and signing identity, versionCode 16, minSdk 26 and targetSdk 35.

## Validation

- Android assembly and 54 local JVM/Compose tests pass. Coverage includes single/two-pane switching, saveable navigation, fresh snapshots, retained form input, unsaved connection edits during automatic recovery, request-free resizing, catalog control separation and existing managed operations.
- Eight deterministic fixture screenshots cover compact, unfolded light/dark, tablet landscape and catalog layouts. These were visually reviewed; they are review captures rather than approved golden-image comparisons.
- Isolated Android emulator acceptance covers connection editing, HTTPS interruption/recovery, plugin catalog actions, MainActivity recreation with an unsaved credential draft, and diagnostics after a system-induced crash. Exact local reports remain outside public source.
- Physical folding/hinge behavior, Samsung multi-window, keyboard behavior and Tailnet connectivity remain handset acceptance tasks.

## Publication scope

Review the complete staged change and every introduced commit before publishing source. Scan the exact source tree and APK contents for credentials/private information, and verify package/version/signature before distribution. Record the reviewed commit and APK checksum in the release evidence. Only the native APK/source are published for this release; existing server images are retained.

## Toolchain

AGP 9.1.1 with built-in Kotlin, Compose compiler plugin 2.2.10, Gradle 9.3.1, SDK platform 37.0 and build tools 36.0.0. The wrapper distribution checksum is pinned. Compose BOM 2026.09.00, Material 3 Adaptive 1.3.0 and Navigation 3 1.2.0 supply the layout and navigation APIs. Existing JUnit4 Compose test APIs are retained; their v2 migration is separate maintenance work.
