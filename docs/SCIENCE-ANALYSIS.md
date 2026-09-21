# Science Analysis: mission baseline + exploratory deviations

**Optional draft add-on for existing HA mission archives.** It reads saved
JSONL scans and never modifies the archive or physical instrument. The initial
release compares Mission A with a *different*, manually chosen reference
mission. It is not continuous recording or automated hazard monitoring.

## Existing installation: what to add

1. Back up your HA configuration. Copy
   `tricorder/tricorder_science_analysis.py` to
   `/config/tricorder/tricorder_science_analysis.py`.
2. Copy `packages/tricorder_science_analysis.yaml` to
   `/config/packages/tricorder_science_analysis.yaml`. Existing installations
   with `packages: !include_dir_named packages` pick it up after an HA restart.
   **Do not replace** `packages/tricorder_archive.yaml`, existing helpers,
   scripts, webhook automation, or firmware.
3. Check HA configuration and restart. Confirm the entities
   `input_text.tric_science_baseline_mission_id` and
   `sensor.tricorder_science_analysis` appear.
4. Add `dashboard/cards/science-baseline.yaml` as an individual card in a new
   SCIENCE view, *or* adapt the standalone `dashboard/science-analysis-view.yaml`.
   That standalone file starts with `views:`; merge **only the new view** into
   your existing dashboard's `views:` list. Do not replace the whole dashboard.
   It includes a copy of Mission Selector using the existing Mission A helper.
5. Select a saved reference mission as Mission A and press **USE MISSION A AS
   REFERENCE**. Then select a *different* Mission A. Results update when
   either helper changes. Prefer a completed mission with multiple repeats as
   the reference; if data is limited, the card says so.
6. Compare a second mission, verify the displayed values against known scans,
   switch reference missions, and check that existing eight Tricorder cards
   still refresh normally. No Pynt/CLUE firmware change is required.

## Interpretation and scientific limitations

- Results are **saved snapshots only**. Neither the reference nor Mission A is
  sampled continuously; selecting a mission as a baseline does not capture a
  new baseline scan. For comparison, repeat the same measurement procedure
  with comparable sensor placement and environmental conditions.
- Numeric channels use each mission's **median**. The provisional deviation
  band is the larger of an illustrative per-channel floor and
  `3 × 1.4826 × median absolute deviation` of the reference readings.
  At least **three reference snapshots per channel** are required before a
  deviation is flagged. Floors are classroom heuristics in
  `tricorder_science_analysis.py`'s `CHANNELS`, **not sensor accuracy
  specifications or validated safety thresholds**.
- The radiation comparison pools pulses and actual scan durations after
  deduplicating companion `scan_summary` / `radiation_scan` uploads. An
  approximate independent-Poisson **3-sigma** count-rate check is shown only
  when both missions have at least ten pulses. Low counts are marked limited
  evidence. These results are not radiological safety decisions.
- eCO₂ and TVOC are sensor estimates, relative dB is not a calibrated sound
  level, and magnetic results depend on location/orientation. No claim is made
  that an anomalous reading identifies a material or hazardous condition.
- Missing/nonfinite channels are omitted rather than shown as measured zero.
  Missions with no shared scan types show a no-data message. The optional
  sensor reads the archive on mission/reference selection, not every 30 seconds.

## For contributors

Offline coverage: `python -m pip install pytest PyYAML` then
`python -m pytest -q tests`. GitHub Actions runs these checks on the PR.
A passing offline check does **not** establish compatibility with every HA
release or the actual third-party HTML Template Card renderer.

Example `TRICORDER_ARCHIVE_PATH=/path/to/test.jsonl python3
tricorder/tricorder_science_analysis.py MISSION_A.jsonl REFERENCE.jsonl`.

Do not commit live mission archives, locations, webhook IDs, or HA secrets.
