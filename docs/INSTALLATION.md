# Installation — Home Assistant only

## Prerequisites

- A backed-up Home Assistant instance; source system was **2026.9.3**. Other versions have **not** been verified.
- Python 3 available for HA command-line/shell-command integration, and writable `/config/tricorder/`.
- The Home Assistant **File** integration configured as a notifier named `notify.file`, writing to `/config/tricorder/tricorder_uploads.jsonl`; it is what persists each upload as JSONL. Verify the entity name **exactly** before enabling the receiver.
- The third-party **HTML/Jinja2 Template Card** (`custom:html-template-card`) and **card-mod**. Graph popups use **browser_mod**. Install these separately from their original distributors; nothing from HACS is redistributed here. The removed OTA action formerly used Mushroom, but the included cards don't require it.
- Optional compatible LCARS theme: the installed system's `LCARS Modern` theme was not redistributed. Apply your own available theme after import.

## Setup, in order

1. **Make a backup**. Copy the seven files from `packages/` into `/config/packages/`; merge `setup/configuration-snippets.yaml` into your existing `/config/configuration.yaml`. Do **not** overwrite your existing Home Assistant configuration or duplicate top-level keys such as `homeassistant:`, `command_line:` or `shell_command:`.
2. Copy all three `tricorder/*.py` files to `/config/tricorder/`. Create an empty writable `/config/tricorder/tricorder_uploads.jsonl` and, if needed, an `archive_state.json` containing `{"archived":{}}`. Keep both files private. `archive_manager.py` supports archive/restore/delete; deletion is permanent.
3. In HA's **File integration**, create a file notifier at `/config/tricorder/tricorder_uploads.jsonl` and ensure its target is `notify.file`. Test that a non-sensitive message writes one JSON record on a line. If you have a different entity, update the receiver's first action to match it.
4. Merge the three entries in `setup/tricorder_scripts.yaml` into existing `scripts.yaml`; ensure `script: !include scripts.yaml` (or an equivalent include) is configured. Reload scripts after checking YAML.
5. Copy `setup/tricorder_upload_receiver.example.yaml` into `automations.yaml` (merge the one list item, do not replace other automations). **Replace the placeholder webhook ID with a fresh private random value on your own HA instance; never commit that value.** Receiver is local-only, POST-only as extracted. Do not expose the webhook or assume webhook IDs alone provide robust access control. Keep uploads on trusted network paths and add external access protection if you choose remote use.
6. Check configuration and restart/reload the applicable Home Assistant components. Confirm `sensor.tricorder_mission_catalog`, `sensor.tricorder_mission_scans`, `sensor.tricorder_mission_events`, `sensor.tricorder_comparison_mission_scans`, and `sensor.tricorder_radiation_analysis` exist. The archived missions sensor is defined by the `command_line` snippet, not the seven packages.
7. Create a **new dashboard** and paste the contents of `dashboard/tricorder-dashboard.yaml` into its Raw Configuration Editor. The `dashboard/cards/` directory has individual cards if you'd rather merge these views into your existing dashboard. Avoid overwriting your other LCARS views.
8. Ensure the sender posts JSON records matching the existing TR-460 payload format to your new private local webhook. The physical sender/firmware is **not included**. Use `examples/tricorder_uploads.example.jsonl` as fictional test records: copy the *lines*, not the example file itself, into a **test** archive if desired.
9. Verify selecting a mission refreshes all the relevant dashboard cards. In particular, the Radiation, Color, Orientation and Magnetic cards are the revised mission-aware versions from the backed-up HA dashboard.

## Scope caveats

- `setup/tricorder_upload_receiver.example.yaml` deliberately drops **12 retired InfluxDB-writing actions**; it still writes to `notify.file` and updates helpers. The deprecated `packages/tricorder_influxdb.yaml` is not shipped.
- OTA firmware, its `/config/www/tricorder_ota/` subtree, and the `tricorder_build_manifest` service are omitted. The standalone dashboard excludes the GENERATE REVISION DIRECTIVE button.
- Only two Tricorder views are provided, not your household's full `dashboard_command` dashboard. Other user custom views and the privately installed theme are omitted.
- Your backup had no files in the separate `share.tar.gz`; the persistent Tricorder JSONL was under `/config/tricorder/`, and was intentionally omitted.
- Existing `notify.file` configuration is maintained by HA's UI (File integration); it is **not** exported from HA's private `.storage/core.config_entries`.

## Troubleshooting

If the archive cards show no data: confirm the File notifier writes *one JSON object per line* to the correct path and that `/config/tricorder/tricorder_archive_reader.py catalog` produces JSON. If the selected mission does not refresh, check `input_text.tric_archive_mission_id` and the two mission scan/event sensors. For popup failures, confirm `browser_mod` is installed/loaded in the browser. If helpers appear as unexpected IDs after install, compare IDs referenced in dashboard card YAML and packages.
