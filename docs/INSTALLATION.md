# Installation — Home Assistant only

## Prerequisites

- A backed-up Home Assistant instance; source system was **2026.9.3**. Other versions have **not** been verified.
- Python 3 available for HA command-line/shell-command integration, with writable `/config/tricorder/` and `/config/scripts/`.
- The Home Assistant **File** integration configured as a notifier named `notify.file`, writing to `/config/tricorder/tricorder_uploads.jsonl`; it is what persists each upload as JSONL. Verify the entity name **exactly** before enabling the receiver.
- The third-party **HTML/Jinja2 Template Card** (`custom:html-template-card`) and **card-mod**. Graph popups use **browser_mod**. Install these separately from their original distributors; nothing from HACS is redistributed here. The removed OTA action formerly used Mushroom, but the included cards don't require it.
- Optional compatible LCARS theme: the installed system's `LCARS Modern` theme was not redistributed. Apply your own available theme after import.

## Setup, in order

1. **Make a backup**. Copy the seven files from `packages/` into `/config/packages/`; merge `setup/configuration-snippets.yaml` into your existing `/config/configuration.yaml`. Do **not** overwrite your existing Home Assistant configuration or duplicate top-level keys such as `homeassistant:`, `command_line:` or `shell_command:`.
2. Copy all three `tricorder/*.py` files to `/config/tricorder/`. Copy `scripts/tricorder_science_analysis.py` to `/config/scripts/tricorder_science_analysis.py`. Create an empty writable `/config/tricorder/tricorder_uploads.jsonl` and, if needed, an `archive_state.json` containing `{"archived":{}}`. Keep both files private. `archive_manager.py` supports archive/restore/delete; deletion is permanent.
3. In HA's **File integration**, create a file notifier at `/config/tricorder/tricorder_uploads.jsonl` and ensure its target is `notify.file`. Test that a non-sensitive message writes one JSON record on a line. If you have a different entity, update the receiver's first action to match it.
4. Merge the three entries in `setup/tricorder_scripts.yaml` into existing `scripts.yaml`; ensure `script: !include scripts.yaml` (or an equivalent include) is configured. Reload scripts after checking YAML.
5. Copy `setup/tricorder_upload_receiver.example.yaml` into `automations.yaml` (merge the one list item, do not replace other automations). **Replace the placeholder webhook ID with a fresh private random value on your own HA instance; never commit that value.** Receiver is local-only, POST-only as extracted. Do not expose the webhook or assume webhook IDs alone provide robust access control. Keep uploads on trusted network paths and add external access protection if you choose remote use.
6. Check configuration and restart/reload the applicable Home Assistant components. Confirm `sensor.tricorder_mission_catalog`, `sensor.tricorder_mission_scans`, `sensor.tricorder_mission_events`, `sensor.tricorder_comparison_mission_scans`, and `sensor.tricorder_radiation_analysis` exist. The archived missions sensor is defined by the `command_line` snippet, not the seven packages.
7. Create a **new dashboard** and paste the contents of `dashboard/tricorder-dashboard.yaml` into its Raw Configuration Editor. The `dashboard/cards/` directory has individual cards if you'd rather merge these views into your existing dashboard. Avoid overwriting your other LCARS views.
8. Ensure the sender posts JSON records matching the existing TR-460 payload format to your new private local webhook. The physical sender/firmware is **not included**. Use `examples/tricorder_uploads.example.jsonl` as fictional test records: copy the *lines*, not the example file itself, into a **test** archive if desired.
9. Verify selecting a mission refreshes all the relevant dashboard cards. The mission selector changes `input_text.tric_archive_mission_id`; the automation in `packages/tricorder_archive.yaml` refreshes the events and scans sensors. Avoid adding a second refresh in dashboard JavaScript, which rereads the archive unnecessarily. In particular, the Radiation, Color, Orientation and Magnetic cards are the revised mission-aware versions from the backed-up HA dashboard.

## MaTouch Rev078: Thermal Images and Subspace Uplink

The MaTouch `matouch-geiger-014` branch now includes on-device HA receiver
configuration: on the instrument, manually connect Wi-Fi, open
**ARCHIVE > FILE TRANSFER**, start its local server, and browse to
`http://tricorder.local/`. Under **SUBSPACE UPLINK SETTINGS**, enter the
local HA server address (default `http://192.168.87.73:8123`) and the
**private webhook ID** from the active Tricorder Upload Receiver automation.
Select **SAVE UPLINK SETTINGS** and **TEST RECEIVER**. The ID remains in
MaTouch NVS and is not published on GitHub. The receiver test sends a small
`uplink_test` JSON record; verify it appears in your private JSONL archive.
An HTTP success indicates acceptance, not proof that every HA display updated.

For **thermal snapshots**, add the following once on your live HA installation:

1. Copy `tricorder/thermal_snapshot_render.py` from this repo to
   `/config/tricorder/thermal_snapshot_render.py`.
2. Merge `shell_command.tricorder_render_thermal` from
   `setup/configuration-snippets.yaml` into your existing
   `configuration.yaml`, **without overwriting other shell commands**.
3. Add the new conditional **thermal_snapshot** `if/then` action immediately
   after the `notify.file` action in your existing
   **Tricorder Upload Receiver** automation. The updated public example
   in `setup/tricorder_upload_receiver.example.yaml` shows the exact
   block. **Keep your actual webhook ID**; do not replace your full
   installed automation with the sample.
4. Check HA configuration and reload/restart the applicable services.
   On the MaTouch, save a 10/15/30-second THERMAL scan; it captures one
   *complete 32×24 thermal frame* starting at the scan midpoint.
   After the scan ends, connect Wi-Fi and run SUBSPACE UPLINK.
5. The renderer stores an image per scan at
   `/config/www/tricorder_thermal/thermal_distance_XXXXXXXX.png`,
   plus `latest.png` and `index.json`. The raw grid (0.1°C per value)
   stays in the **private** `tricorder_uploads.jsonl` archive,
   correlated with `archive_file` and `mission_file`.

To view the most recent image, add a Home Assistant **Picture** card with
the URL `/local/tricorder_thermal/latest.png`. Browsers may cache
`latest.png`; a refresh or a cache-busting image URL updates it. For
individual mission images, use the dated scan-specific URLs in
`/local/tricorder_thermal/index.json`.

**AI interpretation:** These PNGs can be supplied to an image-capable
Computer/voice-assistant model, and the private JSONL archive preserves raw
temperatures for structured analysis. This repo does **not** automatically
configure a vision model or authorize one to browse HA files; that
integration still requires an image-capable model/tool with access to the
specific snapshot. Object guesses from 32×24 thermal images are tentative.

**Privacy:** Files beneath `/config/www` are accessible by their static
`/local` URL; do not place sensitive photos or names there if your HA is
reachable from untrusted networks. Keep the webhook ID and JSONL archive
private. The media-transfer server is operator-enabled only and remains
off on boot.

## Scope caveats

- `setup/tricorder_upload_receiver.example.yaml` deliberately drops **12 retired InfluxDB-writing actions**; it still writes to `notify.file` and updates helpers. The deprecated `packages/tricorder_influxdb.yaml` is not shipped.
- OTA firmware, its `/config/www/tricorder_ota/` subtree, and the `tricorder_build_manifest` service are omitted. The standalone dashboard excludes the GENERATE REVISION DIRECTIVE button.
- Only two Tricorder views are provided, not your household's full `dashboard_command` dashboard. Other user custom views and the privately installed theme are omitted.
- Your backup had no files in the separate `share.tar.gz`; the persistent Tricorder JSONL was under `/config/tricorder/`, and was intentionally omitted.
- Existing `notify.file` configuration is maintained by HA's UI (File integration); it is **not** exported from HA's private `.storage/core.config_entries`.

## Troubleshooting

If the archive cards show no data: confirm the File notifier writes *one JSON object per line* to the correct path and that `/config/tricorder/tricorder_archive_reader.py catalog` produces JSON. If the selected mission does not refresh, check `input_text.tric_archive_mission_id` and the two mission scan/event sensors. For popup failures, confirm `browser_mod` is installed/loaded in the browser. If helpers appear as unexpected IDs after install, compare IDs referenced in dashboard card YAML and packages.
