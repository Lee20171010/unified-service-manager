# OMV deployment revision omv2 validation

## Scope

Application image `unified-application:0.4.0-omv2`; Web image `unified-web:0.4.2-omv1`; APK stays 0.4.2. Only OMV deployment initialization changes. API/schema and client behavior remain compatible.

## Reproduction and unit gate

- Before the fix, an absent host directory created by Docker was UID 0; the existing non-root Application image raised PermissionError when writing a fixture file there.
- `bash scripts/test.sh`: **71 backend tests passed**, including five new initialization boundary tests; **14 Web tests passed** and JavaScript syntax checks passed.
- Boundary tests cover fresh empty root-owned directories, repeat invocation, populated directories and their symlink targets, other owners, and rejection of directory symlinks/files.

## Isolated Compose acceptance

Run `python3 scripts/test-omv.py` after building the release image. The script copies the shipped Compose to an empty temporary project, uses a generated fixture Token and random loopback port, starts real-mode Application with no hosts, and tears down its containers/volumes/directories afterwards. No remote operation is submitted.

Acceptance covers Docker creating the three bind directories; initialization to UID/GID 10001 and 0700; Application running as UID 10001; authenticated API access; unauthenticated request rejected; zero plugins activated; a fixture plugin document persisting after full container recreation; and a populated SSH directory retaining a root-owned 0600 fixture file and contents.

Result: **PASS** on the review host using the shipped Compose with fresh temporary directories and subsequent full container recreation. All fixture containers, named volumes and directories were removed.

## Limits and rollback

No nas-host deployment, physical Android testing, or real SSH/WebDAV operation was performed for this change. Populated directories are deliberately preserved, so existing incorrect permissions require administrator review. Existing installations must keep the same mount paths and Compose project identity.

The API/data schema is unchanged. Retain the previous Application image and configuration for rollback, and remove storage-init dependencies if using the prior image. No Android rebuild is required.
