# Security and publication

Unified is a single-administrator management service. An authenticated administrator can install command plugins and run SSH commands with the configured remote account's authority. Protect the administrator token and the HTTPS entrypoint accordingly. SSH host-key verification and TLS certificate validation remain enabled.

## Publication requirements

Every commit must be reviewed before it is created and before it is pushed. Review all commits/content being introduced, not only the final tree. Before publishing an image, inspect build inputs, all image layers, history and metadata. Deleting a secret in a later commit/layer does not remove the earlier exposure.

Local .env files, SSH keys, runtime directories, screenshots, device details, real-host plans and generated distribution artifacts are excluded from Git and Docker build input. Images use explicit COPY instructions and an allowlisted build context. First-run Android connection settings are empty; examples use documentation addresses. The fixed demo token is intentionally public and is rejected by real mode.

The publication workflow is manual. It checks out the exact reviewed commit, scans the full ancestry of that reviewed commit, builds the two images, scans them, and publishes versioned tags. It promotes both latest aliases only after both immutable images are pushed. Only repository read and package write permissions are granted to the workflow. Existing version tags must not be overwritten. Source/revision OCI labels tie packages to the repository and commit.

## Verification

- Astra max reviews application security and the staged release, with focused regression tests for confirmed findings.
- Gitleaks scans the complete public tree and all commits, with redacted reports.
- `scripts/check-release-inputs.py` checks staged/history trees for private network references, key material and sensitive paths.
- Image review covers final contents, all layers and metadata; Trivy checks dependency vulnerabilities. Scanner results are evidence, not a guarantee of absence of defects.
- Backend/Web fixtures and Android JVM tests run locally; isolated Docker checks exercise initialization, actual server privileges, persistence and shutdown. Real-host/device acceptance is separate.

## Reporting

Report vulnerabilities privately to the repository maintainer using GitHub's private vulnerability reporting when available. Do not post tokens, private keys, personal host details or exploit output containing user data in public issues.
