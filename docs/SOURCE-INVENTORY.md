# Source inventory and extraction decisions

| Original backup location | What this repo does |
|---|---|
| `/config/packages/tricorder*.yaml` | Copies seven HA-only packages. Omits the deprecated `tricorder_influxdb.yaml` with a token reference. |
| `/config/tricorder/*.py` | Copies three Python source files. |
| `/config/tricorder/tricorder_uploads.jsonl` | **Never copied**; includes personal scans/locations. |
| `/config/tricorder/archive_state.json` | **Never copied**; includes personal mission identifiers. |
| `/config/automations.yaml` | Extracts only “Tricorder Upload Receiver”; removes the private webhook ID and twelve defunct InfluxDB actions. |
| `/config/scripts.yaml` | Extracts only three Tricorder archive scripts. |
| `/config/configuration.yaml` | Creates a minimal setup snippet: homeassistant packages/allowlist, shell commands, and archived-missions command-line sensor. Other household configuration is excluded. |
| `/config/.storage/lovelace.dashboard_command` | Extracts only TRICORDER and ANALYSIS views; extracts their 13 HTML cards as standalone YAML, excludes other views/HA storage metadata. |
| `/config/www/tricorder_ota/` | Excluded: physical PSP firmware, manifests and OTA support are not HA-only. |
| `/config/www/tric-icons.js`, LCARS theme and HACS resources | Excluded: not used by these two included views or separately distributable dependencies. |
| `share.tar.gz` | Was empty in the supplied backup; no Tricorder share content was found there. |

**Source environment:** one September 2026 HA backup, version 2026.9.3. **No claims of compatibility for earlier/later HA versions or hardware without testing.**
