"""Offline tests for thermal AI preparation (no HA or API calls)."""
import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tricorder_thermal_ai_prepare",
    ROOT / "tricorder" / "tricorder_thermal_ai_prepare.py")
thermal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(thermal)


def test_selected_mission_uses_all_raw_grid_pixels(tmp_path, monkeypatch):
    archive = tmp_path / "tricorder_uploads.jsonl"
    render = tmp_path / "render"
    media = tmp_path / "media"
    render.mkdir()
    records = [
        {"record_type": "mission_start", "mission_file": "m1",
         "mission_code": "A", "mission_name": "First"},
        {"record_type": "thermal_snapshot", "mission_file": "m1",
         "time": "2026-11-01T00:00:00", "width": 32, "height": 24,
         "unit": "deci_c", "archive_file": "thermal_distance_00000001.jsonl",
         "pixels": [200] * 768},
        {"record_type": "thermal_snapshot", "mission_file": "m1",
         "time": "2026-11-01T00:00:01", "width": 32, "height": 24,
         "unit": "deci_c", "archive_file": "thermal_distance_00000002.jsonl",
         "pixels": [300] * 768},
        {"record_type": "mission_start", "mission_file": "m2",
         "mission_code": "B", "mission_name": "Second"},
        {"record_type": "thermal_snapshot", "mission_file": "m2",
         "time": "2026-11-02T00:00:00", "width": 32, "height": 24,
         "unit": "deci_c", "archive_file": "thermal_distance_00000003.jsonl",
         "pixels": [400] * 768},
    ]
    archive.write_text("\n".join(json.dumps(record) for record in records))
    for n in range(1, 4):
        (render / ("thermal_distance_%08d.png" % n)).write_bytes(b"png-test")
    monkeypatch.setattr(thermal, "ARCHIVE", archive)
    monkeypatch.setattr(thermal, "RENDER_DIR", render)
    monkeypatch.setattr(thermal, "MEDIA_DIR", media)

    selected = thermal.prepare("m1")
    assert selected["ok"]
    assert selected["selected"]["image_count"] == 2
    assert selected["selected"]["mean_c"] == 25.0
    assert selected["selected"]["minimum_c"] == 20.0
    assert selected["selected"]["maximum_c"] == 30.0
    assert selected["selected"]["valid_pixel_count"] == 1536
    assert len(selected["attachments"]) == 2
    assert selected["comparisons"] == []
    assert (media / "thermal_distance_00000001.png").is_file()
    assert not (media / "thermal_distance_00000003.png").exists()

    compared = thermal.prepare("m1", "B")
    assert compared["comparisons"][0]["mean_c"] == 40.0
    assert len(compared["attachments"]) == 3

    everyone = thermal.prepare("m1", "all")
    assert everyone["comparisons"][0]["mission_code"] == "B"
    assert len(everyone["attachments"]) == 2

    assert not thermal.prepare("missing")["ok"]


def test_bad_frames_and_missing_png_are_reported(tmp_path, monkeypatch):
    archive = tmp_path / "archive.jsonl"
    archive.write_text("\n".join([
        json.dumps({"record_type": "thermal_snapshot", "mission_file": "m1",
                    "width": 32, "height": 24, "unit": "deci_c",
                    "archive_file": "thermal_distance_00000001.jsonl",
                    "pixels": [235] * 768}),
        json.dumps({"record_type": "thermal_snapshot", "mission_file": "m1",
                    "width": 32, "height": 24, "unit": "deci_c",
                    "archive_file": "../../something.jsonl",
                    "pixels": [600] * 768}),
    ]))
    monkeypatch.setattr(thermal, "ARCHIVE", archive)
    monkeypatch.setattr(thermal, "RENDER_DIR", tmp_path / "empty")
    monkeypatch.setattr(thermal, "MEDIA_DIR", tmp_path / "media")
    report = thermal.prepare("m1")
    assert report["ok"]
    assert report["selected"]["mean_c"] == 23.5
    assert report["selected"]["image_count"] == 1
    assert report["attachments"] == []
    assert report["unattached_images"] == 1


def test_home_assistant_yaml_is_parseable():
    for path in (
        "setup/tricorder_thermal_ai_shell_command.yaml",
        "setup/tricorder_thermal_ai_script.yaml",
    ):
        loaded = yaml.safe_load((ROOT / path).read_text())
        assert isinstance(loaded, dict)
