# Security and privacy checklist

**This bundle is a working draft, not a substitute for checking your own deployment or a dedicated security review.**

## Deliberately omitted

- Full backup archive, `/config/secrets.yaml`, `.storage/`, `.cloud/`, TLS/private-key material, HA database and add-on data.
- Original live `tricorder_uploads.jsonl`, `archive_state.json`, personal mission logs, and true latitude/longitude records.
- Actual webhook ID, original File integration `.storage` configuration, old InfluxDB URL/token and legacy writer package.
- Physical tricorder firmware and OTA manifests; unrelated household configuration and media.

## Before publishing / installing

1. Replace the receiver's `REPLACE_WITH_PRIVATE_RANDOM_WEBHOOK_ID` in your **local working HA**, not in this repo. Keep real webhook endpoints private. The example is configured `local_only: true`.
2. Keep JSONL mission records outside Git. Raw records can include GPS coordinates, timestamps, labels and household-specific metadata.
3. Do not commit `secrets.yaml`, HA backups, `.storage/`, `.cloud/`, `.db`, real webhooks or screenshots with real location/sensitive data. The `.gitignore` helps but **does not sanitize files or Git history**.
4. The extraction was deliberately limited to seven packages, three Python files, a redacted automation, setup snippets and two dashboard views. Inspect later local customizations before committing them.
5. The original archive/restore/delete shell commands pass selected mission IDs to a shell. Keep this dashboard/service limited to trusted users and do not accept arbitrary untrusted mission IDs without additional validation/quoting. Deletion is destructive; back up your JSONL.
6. Installing a local-only POST webhook is not equivalent to comprehensive authentication for remote/public access. Never publish the live URL or endpoint ID.
7. Review third-party licensing for the optional LCARS theme, Star Trek audio/images, icons, fonts and HACS code. **None are bundled.**
8. If a secret was ever committed, removing it from the current file isn't enough: revoke/rotate it and clean the public Git history.

This repository contains a **fictional** demo file only; its date is 2000 and it does not describe a real person's location.
