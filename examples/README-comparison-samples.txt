TRICORDER HOME ASSISTANT — SYNTHETIC COMPARISON DATA

Three fictional mission archives in the same JSONL record format used by the TR-460 upload receiver and archive reader. No real measurements or location data. Do not use them for scientific conclusions.

The three mission_*.jsonl files are individually readable examples. Home Assistant does NOT automatically load them just because they are stored in the examples folder.

To test the Comparison card, use the included tricorder_uploads.comparison_demo.jsonl as a ready-made combined archive on a TEST Home Assistant installation. Back up any existing /config/tricorder/tricorder_uploads.jsonl first; never overwrite or concatenate into your live archive without making a backup.

On a test system, replace the EMPTY /config/tricorder/tricorder_uploads.jsonl with the CONTENTS of the combined file (the archive reader expects one JSON object per line in that single file). Refresh the mission catalog and mission scans entities or wait for their next update. Choose DEMO-002 for Mission A and DEMO-003 or DEMO-004 for Mission B.

DEMO-002 (classroom baseline), DEMO-003 (sunlit-window scenario), DEMO-004 (workbench equipment scenario) differ deliberately across environment, radiation, thermal, distance, and UV for comparison graphs. Each has two radiation results with per-second pulse bins and three readings for each other sensor type.

These files are for local archive-reader testing, not a replay protocol: the HA webhook receives ONE JSON object per POST, not an entire JSONL file in one POST.
