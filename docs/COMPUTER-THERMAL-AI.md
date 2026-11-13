# Computer: TR-460 mission-aware thermal image analysis

**Status:** GitHub implementation; **not yet installed or validated on the live
Home Assistant instance.** There are no changes to tricorder firmware, mission
records, existing archive reader, or dashboard cards.

## What this does

- Uses the mission selected by the Tricorder dashboard's
  `input_text.tric_archive_mission_id`; never guesses the mission.
- Reads every valid 32x24 `thermal_snapshot` for that mission directly from
  `/config/tricorder/tricorder_uploads.jsonl`. The source is **0.1°C per pixel**.
- Calculates the **pixel-weighted mission mean**, actual lowest valid pixel,
  highest valid pixel, average valid center pixel, and per-image statistics.
  These are not estimates from false-color PNGs.
- Supplies rendered images from the selected mission for qualitative AI vision.
  The script sends up to **16 PNG images per request** to limit voice latency and
  API cost. **All** valid raw frames contribute to numeric averages, including
  images not attached. The spoken report must disclose any such limit.
- With optional `compare_to` input, compares a second mission by its
  code/name/ID, or `all` other missions numerically. In a specific two-mission
  comparison, images from both missions can be attached within the same limit.
  `all` comparisons do **not** upload all other archived pictures.
- Keeps the source JSONL and rendered PNGs unchanged. Working copies are placed
  in authenticated Home Assistant media under `/media/tricorder_ai/`.
  The PNGs originally under `/config/www/` retain their existing permissions.

## Install (after making a Home Assistant backup)

1. Copy
   [`tricorder/tricorder_thermal_ai_prepare.py`](../tricorder/tricorder_thermal_ai_prepare.py)
   to `/config/tricorder/tricorder_thermal_ai_prepare.py`.
2. **Merge** the one `tricorder_prepare_thermal_ai` command from
   [`setup/tricorder_thermal_ai_shell_command.yaml`](../setup/tricorder_thermal_ai_shell_command.yaml)
   into the **existing** `shell_command:` section of `configuration.yaml`.
   Do not replace the other commands or create a second top-level section.
   Reload `shell_command` from Developer Tools > YAML (or restart HA).
3. In Scripts, edit the already-created **Analyze Tricorder Thermal Image**
   script, replace the original hardcoded-PNG YAML with
   [`setup/tricorder_thermal_ai_script.yaml`](../setup/tricorder_thermal_ai_script.yaml).
   Save; do not create a duplicate script.
4. Select a mission on the Tricorder dashboard. Run the script manually first
   and inspect its response/trace. If successful, expose that one script to
   **Assist** under Script settings > Voice assistants.
5. Ask Computer to analyze the selected mission's thermal scans. For comparisons,
   ask it to compare against mission code/name or all missions. Check Assist
   Debug to confirm it invoked the exposed script.

**Prerequisites:** OpenAI AI Task configured for images (already confirmed in the
earlier manual test); OpenAI Conversation with AI tools = Device control; current
archive and PNG renderer operating. Home Assistant Python 3 and `/media`
write access are needed.

**If no images appear:** The helper returns the original numeric temperature
summary without visual findings. If there is no thermal data in the selected
mission, it returns an explicit error.

**Safety:** This is exploratory thermal interpretation of a 32×24 image.
The false-color palette is independently normalized for each image; colors are
not absolute temperatures. This is not a calibrated safety, electrical,
fire, or medical diagnostic tool.

**Testing:** Offline test cases in
[`tests/test_thermal_ai_prepare.py`](../tests/test_thermal_ai_prepare.py)
exercise averages, comparisons, missing media, rejected filenames and YAML
parsing. The repository's GitHub Actions test workflow is presently reporting
failures on both previous and current commits; no live Home Assistant
end-to-end validation has been claimed.
