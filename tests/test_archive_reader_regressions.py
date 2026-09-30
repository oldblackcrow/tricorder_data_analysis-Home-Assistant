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

def test_unlinked_radiation_record_is_assigned_by_mission_time_window(tmp_path):
    archive = tmp_path / "uploads.jsonl"
    records = [
        {"record_type": "mission_start", "mission_code": "GS-001",
         "time": "2026-09-29T17:51:42"},
        {"record_type": "radiation_scan", "mission_code": "GS-001",
         "time": "2026-09-29T17:55:51", "elapsed_seconds": 250.1,
         "radiation_record_id": 75, "cpm": 4.0, "dose_usvh": 0.0753,
         "pulses": 1, "duration_seconds": 15.02,
         "pulse_bins": [0, 0, 0, 0, 1]},
        {"record_type": "mission_end", "mission_code": "GS-001",
         "time": "2026-09-29T17:56:10"},
        {"record_type": "mission_start", "mission_code": "GS-001",
         "time": "2026-09-29T18:00:00"},
        {"record_type": "radiation_scan", "mission_code": "GS-001",
         "time": "2026-09-29T18:00:05", "radiation_record_id": 76,
         "pulse_bins": [1]},
        {"record_type": "mission_end", "mission_code": "GS-001",
         "time": "2026-09-29T18:00:10"},
    ]
    archive.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    mission_a = "mission_20260929_175142_GS-001.jsonl"
    scans = run_reader(tmp_path, "scans", mission_a)

    summary = series_rows(scans, "tricorder_radiation")
    pulse_rows = series_rows(scans, "tricorder_radiation_series")
    assert len(summary) == 1
    assert summary[0]["record_id"] == 75
    assert [row["pulse_1s"] for row in pulse_rows] == [0, 0, 0, 0, 1]

