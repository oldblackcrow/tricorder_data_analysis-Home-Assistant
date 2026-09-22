"""Offline STEM checks: fictional missions; never require a running HA instance."""
import importlib.util
import json
import math
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tricorder" / "tricorder_science_analysis.py"
SPEC = importlib.util.spec_from_file_location("tric_science_analysis", SCRIPT)
science = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(science)

BASE = "mission_20000101_000000_REFERENCE.jsonl"
CURRENT = "mission_20000102_000000_TEST.jsonl"
OTHER = "mission_20000103_000000_OTHER.jsonl"


def archive(tmp_path, *rows):
    path = tmp_path / "uploads.jsonl"
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\nnot json\n",
        encoding="utf-8",
    )
    return str(path)


def scan(mission, kind, **fields):
    return dict(record_type=kind, mission_file=mission, **fields)


def find(result, name):
    return next(r for r in result["rows"] if r["measurement"] == name)


def test_reference_band_needs_three_scans_and_ignores_unrelated_missions(tmp_path):
    path = archive(
        tmp_path,
        scan(BASE, "atmosphere_scan", temperature_c=20),
        scan(CURRENT, "atmosphere_scan", temperature_c=30),
        scan(OTHER, "atmosphere_scan", temperature_c=10000),
    )
    result = science.analyze(CURRENT, BASE, path)
    row = find(result, "Temperature")
    assert result["status"] == "ready"
    assert (row["baseline"], row["current"], row["delta"]) == (20, 30, 10)
    assert row["baseline_n"] == 1
    assert row["flag"] == "limited_reference"


def test_flagged_baseline_deviation_and_nonflagged_readings(tmp_path):
    rows = [
        scan(BASE, "atmosphere_scan", temperature_c=temp, humidity_percent=45)
        for temp in (20.0, 20.2, 20.4)
    ]
    rows += [
        scan(CURRENT, "atmosphere_scan", temperature_c=27, humidity_percent=46)
    ]
    result = science.analyze(CURRENT, BASE, archive(tmp_path, *rows))
    assert find(result, "Temperature")["flag"] == "outside_reference"
    assert find(result, "Humidity")["flag"] == "within_reference"
    assert find(result, "Temperature")["baseline_n"] == 3
    assert "saved" in result["note"].lower()


def test_radiation_uses_integration_time_and_deduplicates_scan_summary(tmp_path):
    rows = [
        scan(BASE, "scan_summary", time="2000-01-01T00:00:20",
             id=7, pulses=120, duration_seconds=600),
        scan(BASE, "radiation_scan", time="2000-01-01T00:00:20",
             id=7, pulses=120, duration_seconds=600),
        scan(CURRENT, "radiation_scan", time="2000-01-02T00:00:20",
             id=8, pulses=300, duration_seconds=600),
    ]
    result = science.analyze(CURRENT, BASE, archive(tmp_path, *rows))
    r = find(result, "Radiation count rate")
    assert r["baseline_n"] == 1
    assert r["baseline_pulses"] == 120
    assert (r["baseline"], r["current"]) == (12, 30)
    assert r["flag"] == "count_difference"


def test_radiation_low_counts_are_not_called_an_anomaly(tmp_path):
    result = science.analyze(
        CURRENT, BASE,
        archive(tmp_path,
                scan(BASE, "radiation_scan", pulses=1, duration_seconds=10),
                scan(CURRENT, "radiation_scan", pulses=3, duration_seconds=10)),
    )
    assert find(result, "Radiation count rate")["flag"] == "low_counts"


def test_no_baseline_no_mission_or_same_mission_requires_no_file():
    missing_file = "/nonexistent/tricorder-archive-for-test.jsonl"
    assert science.analyze(CURRENT, "", missing_file)["status"] == "select_baseline"
    assert science.analyze("", BASE, missing_file)["status"] == "select_mission"
    assert science.analyze(BASE, BASE, missing_file)["status"] == "same_mission"


def test_missing_archive_is_explicit_error():
    result = science.analyze(CURRENT, BASE, "/nonexistent/tricorder-archive-for-test.jsonl")
    assert result["status"] == "error" and result["error"]


def test_nonfinite_values_and_unmatched_types_not_fabricated(tmp_path):
    result = science.analyze(
        CURRENT, BASE,
        archive(tmp_path,
                scan(BASE, "magnetic_scan", magnetic_field_ut="NaN"),
                scan(CURRENT, "magnetic_scan", magnetic_field_ut=55),
                scan(BASE, "color_scan", red=100),
                scan(CURRENT, "color_scan", red=200)),
    )
    assert result["status"] == "no_shared_scans"
    assert result["rows"] == []


def test_reference_is_median_not_last_scan(tmp_path):
    records = [
        scan(BASE, "magnetic_scan", magnetic_field_ut=v)
        for v in (40, 40, 1000)
    ]
    records.append(scan(CURRENT, "magnetic_scan", magnetic_field_ut=70))
    result = science.analyze(CURRENT, BASE, archive(tmp_path, *records))
    assert find(result, "Magnetic field")["baseline"] == 40
    assert find(result, "Magnetic field")["flag"] == "outside_reference"


def test_science_yaml_package_card_view_are_structurally_valid():
    import yaml

    root = SCRIPT.parents[1]
    package = yaml.safe_load((root / "packages/tricorder_science_analysis.yaml").read_text())
    card = yaml.safe_load((root / "dashboard/cards/science-baseline.yaml").read_text())
    view = yaml.safe_load((root / "dashboard/science-analysis-view.yaml").read_text())
    assert "tric_science_baseline_mission_id" in package["input_text"]
    assert "sensor.tricorder_science_analysis" in card["entities"]
    assert len(view["views"][0]["sections"][0]["cards"]) == 2
    assert "input_text.tric_archive_mission_id" in view["views"][0]["sections"][0]["cards"][0]["entities"]


def test_unmeasured_gases_do_not_create_false_eco2_anomaly(tmp_path):
    baseline = [scan(BASE, "atmosphere_scan",
                     eco2_ppm=0, tvoc_ppb=0, temperature_c=22)
                for _ in range(3)]
    current = [scan(CURRENT, "atmosphere_scan",
                    eco2_ppm=400, tvoc_ppb=0, temperature_c=23)
               for _ in range(3)]
    result = science.analyze(CURRENT, BASE, archive(tmp_path, *(baseline + current)))
    assert find(result, "Temperature")["baseline_n"] == 3
    assert all(r["measurement"] not in ("eCO₂ estimate", "TVOC estimate")
               for r in result["rows"])


def test_measured_zero_tvoc_is_valid_but_zero_eco2_is_not(tmp_path):
    baseline = [scan(BASE, "atmosphere_scan",
                     eco2_ppm=400, tvoc_ppb=0, handheld_linked=True)
                for _ in range(3)]
    current = [scan(CURRENT, "atmosphere_scan",
                    eco2_ppm=550, tvoc_ppb=0, handheld_linked=True)
               for _ in range(3)]
    result = science.analyze(CURRENT, BASE, archive(tmp_path, *(baseline + current)))
    assert find(result, "eCO₂ estimate")["baseline"] == 400
    assert find(result, "TVOC estimate")["baseline"] == 0
    assert find(result, "TVOC estimate")["current"] == 0


def test_unlinked_gases_are_ignored_even_if_nonzero(tmp_path):
    baseline = [scan(BASE, "atmosphere_scan",
                     eco2_ppm=400, tvoc_ppb=0, handheld_linked=False)
                for _ in range(3)]
    current = [scan(CURRENT, "atmosphere_scan",
                    eco2_ppm=650, tvoc_ppb=10, handheld_linked=True)
               for _ in range(3)]
    result = science.analyze(CURRENT, BASE, archive(tmp_path, *(baseline + current)))
    assert result["status"] == "no_shared_scans"
