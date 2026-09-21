"""Periodic radiation analysis should not retain unrelated Tricorder telemetry."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tricorder" / "tricorder_radiation_analysis.py"


def test_radiation_loader_keeps_only_radiation_rows(tmp_path, monkeypatch):
    module_spec = importlib.util.spec_from_file_location("tric_radiation_analysis", SCRIPT)
    reader = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(reader)

    archive = tmp_path / "uploads.jsonl"
    archive.write_text(
        "\n".join(json.dumps(record) for record in [
            {"record_type": "mission_start", "time": "2000-01-01T12:00:00Z"},
            {"record_type": "color_scan", "time": "2000-01-01T12:00:01Z", "red": 7},
            {"record_type": "scan_summary", "time": "2000-01-01T12:00:02Z",
             "cpm": 8, "dose_usvh": 0.15, "pulses": 2, "duration_seconds": 15},
            {"record_type": "radiation_scan", "time": "2000-01-01T12:00:02Z",
             "cpm": 8, "dose_usvh": 0.15, "pulses": 2, "duration_seconds": 15,
             "mission_file": "mission_20000101_120000_TEST.jsonl"},
        ]) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(reader, "ARCHIVE_PATH", str(archive))
    records, error = reader.load_records()
    assert error is None
    assert [r["record_type"] for r in records] == ["scan_summary", "radiation_scan"]
    assert len(reader.unique_scans(records)) == 1
    assert reader.unique_scans(records)[0]["mission_file"].endswith("TEST.jsonl")
