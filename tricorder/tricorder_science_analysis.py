#!/usr/bin/env python3
"""Compare saved Tricorder mission scans with a selected reference mission.

This is exploratory STEM analysis, not a calibrated alarm or safety monitor.
No scans are created, edited, or deleted. Measurements are saved snapshots,
not a continuous telemetry stream.
"""

import json
import math
import os
import statistics
import sys

ARCHIVE_PATH = os.environ.get(
    "TRICORDER_ARCHIVE_PATH", "/config/tricorder/tricorder_uploads.jsonl"
)

# Floors are deliberately conservative teaching heuristics, NOT instrument
# accuracy specifications, validated safety limits, or universal norms.
# Schema: record type, archive field, presentation name, unit, conversion,
# minimum difference that may be called outside the reference band.
CHANNELS = (
    ("atmosphere_scan", "temperature_c", "Temperature", "°C", 1.0, 1.5),
    ("atmosphere_scan", "humidity_percent", "Humidity", "%RH", 1.0, 10.0),
    ("atmosphere_scan", "pressure_pa", "Pressure", "hPa", 0.01, 3.0),
    ("atmosphere_scan", "eco2_ppm", "eCO₂ estimate", "ppm", 1.0, 300.0),
    ("atmosphere_scan", "tvoc_ppb", "TVOC estimate", "ppb", 1.0, 100.0),
    ("atmosphere_scan", "lux", "Illuminance", "lux", 1.0, 100.0),
    ("magnetic_scan", "magnetic_field_ut", "Magnetic field", "µT", 1.0, 10.0),
    ("uv_scan", "uv_index", "UV index", "index", 1.0, 1.0),
    ("audio_scan", "relative_db", "Relative acoustic level", "relative dB", 1.0, 6.0),
    ("thermal_scan", "center_c", "Thermal center", "°C", 1.0, 2.0),
    ("distance_scan", "distance_m", "Distance", "m", 1.0, 0.2),
)

INVALID_IDS = ("", "unknown", "unavailable", "none", "null")
RAD_TYPES = ("scan_summary", "radiation_scan")


def number(value):
    """Return a finite numerical observation, excluding booleans/NaN."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _payload(status, selected="", baseline="", rows=None, note="", error=""):
    return {
        "state": len(rows or []),
        "status": status,
        "current_mission": selected,
        "baseline_mission": baseline,
        "rows": rows or [],
        "note": note,
        "error": error,
    }


def _radiation_key(record, line_number):
    rid = record.get("radiation_record_id", record.get("id"))
    if rid not in (None, "", 0, "0"):
        return ("id", str(rid))
    when = str(record.get("time") or "").strip()
    if when:
        return ("time", when, str(record.get("duration_seconds", "")))
    return ("line", line_number)


def _read_selected(path, selected, baseline):
    """One archive pass, retaining only numeric fields of two missions."""
    targets = {selected, baseline}
    samples = {mission: {} for mission in targets}
    radiation = {mission: {} for mission in targets}
    kinds = {}
    for kind, field, name, unit, scale, floor in CHANNELS:
        kinds.setdefault(kind, []).append((field, name, scale))

    with open(path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.lstrip().startswith("{"):
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue

            mission = str(record.get("mission_file") or "")
            if mission not in targets:
                continue
            kind = record.get("record_type")

            for field, name, scale in kinds.get(kind, ()):
                value = number(record.get(field))
                if value is None:
                    # The older thermal payload can use thermal_center_c.
                    if kind == "thermal_scan" and field == "center_c":
                        value = number(record.get("thermal_center_c"))
                if value is not None:
                    samples[mission].setdefault(name, []).append(value * scale)

            if kind in RAD_TYPES:
                pulses = number(record.get("pulses"))
                duration = number(record.get("duration_seconds"))
                if (pulses is None or pulses < 0 or
                        duration is None or duration <= 0):
                    continue
                key = _radiation_key(record, line_number)
                previous = radiation[mission].get(key)
                # Prefer the full radiation_scan if its companion summary
                # refers to the same scan; do not count one scan twice.
                if previous is None or kind == "radiation_scan":
                    radiation[mission][key] = (pulses, duration)

    return samples, radiation


def _numeric_rows(samples, selected, baseline):
    rows = []
    for _, _, name, unit, _, floor in CHANNELS:
        before = samples[baseline].get(name, [])
        after = samples[selected].get(name, [])
        if not before or not after:
            continue

        ref = statistics.median(before)
        now = statistics.median(after)
        delta = now - ref
        mad = statistics.median(abs(value - ref) for value in before)
        band = max(floor, 3.0 * 1.4826 * mad)
        enough = len(before) >= 3
        flag = "outside_reference" if enough and abs(delta) > band else (
            "within_reference" if enough else "limited_reference"
        )
        rows.append({
            "measurement": name, "unit": unit,
            "baseline": round(ref, 4), "current": round(now, 4),
            "delta": round(delta, 4), "band": round(band, 4),
            "baseline_n": len(before), "current_n": len(after),
            "flag": flag,
            "note": (
                "Heuristic deviation; repeat under comparable conditions."
                if flag == "outside_reference" else
                "Fewer than 3 reference snapshots; no deviation flag."
                if not enough else
                "No deviation beyond this reference band."
            ),
        })
    return rows


def _radiation_row(radiation, selected, baseline):
    before = list(radiation[baseline].values())
    after = list(radiation[selected].values())
    if not before or not after:
        return None

    b_pulses = sum(item[0] for item in before)
    a_pulses = sum(item[0] for item in after)
    b_seconds = sum(item[1] for item in before)
    a_seconds = sum(item[1] for item in after)
    b_cpm = b_pulses * 60.0 / b_seconds
    a_cpm = a_pulses * 60.0 / a_seconds
    delta = a_cpm - b_cpm
    # Independent Poisson count uncertainty, accounting for unequal
    # cumulative integration times (counts per minute = 60 * counts / sec).
    sigma = 60.0 * math.sqrt(
        b_pulses / (b_seconds * b_seconds) +
        a_pulses / (a_seconds * a_seconds)
    )
    z = abs(delta) / sigma if sigma > 0 else None
    enough = b_pulses >= 10 and a_pulses >= 10
    flag = (
        "count_difference" if enough and z is not None and z >= 3 else
        "within_count_uncertainty" if enough else "low_counts"
    )
    return {
        "measurement": "Radiation count rate", "unit": "CPM",
        "baseline": round(b_cpm, 4), "current": round(a_cpm, 4),
        "delta": round(delta, 4),
        "band": round(3 * sigma, 4),
        "baseline_n": len(before), "current_n": len(after),
        "baseline_pulses": b_pulses, "current_pulses": a_pulses,
        "baseline_seconds": round(b_seconds, 3),
        "current_seconds": round(a_seconds, 3),
        "flag": flag,
        "note": (
            "Count-rate difference meets a 3-sigma exploratory check; repeat measurement."
            if flag == "count_difference" else
            "Low pulse counts; insufficient data for this approximate comparison."
            if flag == "low_counts" else
            "No count-rate difference beyond this approximate 3-sigma check."
        ),
    }


def analyze(selected, baseline, path=None):
    selected = str(selected or "").strip()
    baseline = str(baseline or "").strip()
    if selected.lower() in INVALID_IDS:
        return _payload("select_mission", note="Select Mission A on the Tricorder page.")
    if baseline.lower() in INVALID_IDS:
        return _payload(
            "select_baseline", selected=selected,
            note="Save a different mission as the baseline."
        )
    if selected == baseline:
        return _payload(
            "same_mission", selected, baseline,
            note="Select a different Mission A to compare against this reference."
        )
    try:
        samples, radiation = _read_selected(path or ARCHIVE_PATH, selected, baseline)
    except OSError as exc:
        return _payload("error", selected, baseline, error=str(exc))

    rows = _numeric_rows(samples, selected, baseline)
    rad = _radiation_row(radiation, selected, baseline)
    if rad:
        rows.append(rad)
    return _payload(
        "ready" if rows else "no_shared_scans",
        selected, baseline, rows,
        "Saved mission snapshots only. Exploratory reference comparisons; not safety alerts."
        if rows else "These missions have no comparable saved measurements.",
    )


def main():
    selected = sys.argv[1] if len(sys.argv) > 1 else ""
    baseline = sys.argv[2] if len(sys.argv) > 2 else ""
    print(json.dumps(analyze(selected, baseline), ensure_ascii=True,
                     separators=(",", ":")))


if __name__ == "__main__":
    main()
