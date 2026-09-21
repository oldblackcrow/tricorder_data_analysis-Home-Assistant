"""Regression guard: mission selection refreshes sensors only through HA automation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_mission_selector_does_not_double_refresh():
    for path in (
        "dashboard/cards/mission-select.yaml",
        "dashboard/tricorder-view.yaml",
        "dashboard/tricorder-dashboard.yaml",
    ):
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "input_text.tric_archive_mission_id" in text
        assert '"homeassistant",\n' not in text or '"update_entity"' not in text

    automation = (ROOT / "packages/tricorder_archive.yaml").read_text(encoding="utf-8")
    assert "tricorder_archive_refresh_selected_mission" in automation
    assert "sensor.tricorder_mission_events" in automation
    assert "sensor.tricorder_mission_scans" in automation
