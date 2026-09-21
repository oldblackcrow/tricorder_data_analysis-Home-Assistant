"""Archive reader regression tests with deliberately fictional GPS and scan data."""
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
READER = ROOT / "tricorder" / "tricorder_archive_reader.py"
A = "mission_20000101_120000_TEST-A.jsonl"
B = "mission_20000101_120040_TEST-B.jsonl"


def run_reader(tmp_path, mode, mission_id=None):
    archive = tmp_path / "uploads.jsonl"
    env = dict(os.environ, TRICORDER_ARCHIVE_PATH=str(archive))
    command = [sys.executable, str(READER), mode]
    if mission_id is not None:
        command.append(mission_id)
    return json.loads(subprocess.check_output(command, env=env, text=True))


def series_rows(payload, name):
    for entry in payload["results"][0].get("series", []):
        if entry["name"] == name:
            return [dict(zip(entry["columns"], values)) for values in entry["values"]]
    return []


def test_selected_mission_excludes_other_scans_but_keeps_bounded_legacy_gps(tmp_path):
    archive = tmp_path / "uploads.jsonl"
    records = [
        {"record_type": "mission_start", "mission_file": A, "time": "2000-01-01T12:00:00Z"},
        {"record_type": "color_scan", "mission_file": A, "time": "2000-01-01T12:00:05Z", "red": 11},
        {"record_type": "location_update", "time": "2000-01-01T12:00:10Z", "latitude": 40, "longitude": -73},
        {"record_type": "color_scan", "mission_file": B, "time": "2000-01-01T12:00:20Z", "red": 99},
        {"record_type": "mission_end", "mission_file": A, "time": "2000-01-01T12:00:30Z"},
        {"record_type": "location_update", "time": "2000-01-01T12:00:31Z", "latitude": 41, "longitude": -74},
        {"record_type": "mission_start", "mission_file": B, "time": "2000-01-01T12:00:40Z"},
        {"record_type": "location_update", "time": "2000-01-01T12:00:41Z", "latitude": 42, "longitude": -75},
    ]
    archive.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    scans = run_reader(tmp_path, "scans", A)
    assert [r["red"] for r in series_rows(scans, "tricorder_color")] == [11]
    assert [(r["latitude"], r["longitude"]) for r in series_rows(scans, "tricorder_location")] == [(40, -73)]
    events = run_reader(tmp_path, "events", A)
    assert events["count"] == 3
    assert run_reader(tmp_path, "catalog")["count"] == 2


def test_missing_radiation_ids_do_not_collapse_distinct_scans(tmp_path):
    archive = tmp_path / "uploads.jsonl"
    records = [
        {"record_type": "radiation_scan", "mission_file": A,
         "time": "2000-01-01T12:00:05Z", "duration_seconds": 2,
         "pulse_bins": [1, 0]},
        {"record_type": "radiation_scan", "mission_file": A,
         "time": "2000-01-01T12:00:10Z", "duration_seconds": 2,
         "pulse_bins": [0, 1]},
    ]
    archive.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    scans = run_reader(tmp_path, "scans", A)
    assert len(series_rows(scans, "tricorder_radiation_series")) == 4


def test_unselected_mission_does_not_need_existing_archive(tmp_path):
    result = run_reader(tmp_path, "scans", "unavailable")
    assert result["count"] == 0
    assert "error" not in result
