# Client release 0.3.2 · 2026-10-27

Web and native Android use the user-selected first generated design: circular nodes joined into a U. The master is `assets/branding/unified-network-icon-v1.png`; `selection.json` records the choice. Generated PNGs are resized copies, with no redesign of the master. The Android monochrome vector preserves the same silhouette; launcher padding keeps nodes inside circular masks.

## Built and checked

- Android 0.3.2 / versionCode 7: assembleDebug and all **22 Android unit/Compose tests** passed. APK signing certificate matches 0.3.0/0.3.1 for an in-place upgrade.
- APK SHA-256: `873c8d1c35d4b8a711d16fd31dbdc80b78d515af5c04f683224a6b55b5f86f45`.
- **8 Web integration/theme tests** passed. OMV Compose validates with supplied environment values.
- AAPT confirms the native launcher references packaged adaptive resources. The color artwork and monochrome silhouette were rendered under rounded-square/circular masks and visually inspected (`preview/android-launcher-0.3.2.png`).
- Actual Tailnet Web page inspected at desktop size and 390×844. Both header images load, the favicon points to the new PNG, and the mobile page has no horizontal overflow. Screenshots: `preview/web-brand-0.3.2-desktop.png` and `preview/web-brand-0.3.2-mobile.png`.
- A separate demo fixture registered two hosts with the same Compose directory and stopped one resource while starting the other. Both jobs completed and retained independent states. This verifies application behavior, not connectivity to two real machines.
- Downloaded APK, Web-only image archive and complete image archive match local SHA-256 values. Live Web icon bytes match the packaged source assets.

## Deployment

local review Web was updated to `unified-web:0.3.2-omv1`; Application remains 0.3.0 in demo mode. Previous Web image is retained as `unified-web:before-network-brand`. No Application restart or database migration was needed.

NAS users import `unified-web-0.3.2-omv1-amd64.tar.gz`, then change only Web's image tag in OMV Compose and select Up. Application `unified-application:0.3.0-omv1`, env and persistent paths stay compatible. For a new deployment, the combined image archive and manual Compose/env are also published.

## Acceptance boundaries

Android physical-device launcher/header appearance has not been observed by the agent; local mask renders and Robolectric tests are separate evidence. The APK is debug signed. nas-host was not deployed remotely by the agent. Multi-host SSH access requires each host's configured account/key/known_hosts; the one central worker processes jobs sequentially. WebDAV backups still read centrally mounted configuration directories.
