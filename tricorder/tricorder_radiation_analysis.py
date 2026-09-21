#!/usr/bin/env python3
import json
import math
import os

ARCHIVE_PATH = os.environ.get(
    "TRICORDER_ARCHIVE_PATH",
    "/config/tricorder/tricorder_uploads.jsonl",
)

RECENT_LIMIT = 8


def load_records():
    records = []
    try:
        with open(ARCHIVE_PATH, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                # Analysis only consumes radiation_scan/scan_summary;
                # don't retain unrelated telemetry for every poll.
                if (
                    isinstance(record, dict)
                    and record.get("record_type")
                    in ("radiation_scan", "scan_summary")
                ):
                    records.append(record)
    except Exception as error:
        return [], str(error)
    return records, None


def normalize_scan(record):
    rt = record.get("record_type", "")
    if rt not in ("radiation_scan", "scan_summary"):
        return None

    try:
        cpm = float(record.get("cpm", 0))
        dose = float(record.get("dose_usvh", 0))
        pulses = int(record.get("pulses", 0))
        duration = float(record.get("duration_seconds", 0))
    except Exception:
        return None

    rid = record.get("radiation_record_id", record.get("id"))
    return {
        "time": str(record.get("time", "")),
        "record_id": rid,
        "cpm": cpm,
        "dose_usvh": dose,
        "pulses": pulses,
        "duration_seconds": duration,
        "mission_file": str(record.get("mission_file", "") or ""),
        "mission_code": str(record.get("mission_code", record.get("mission", "")) or ""),
        "mission_name": str(record.get("mission_name", "") or ""),
        "mission_elapsed": record.get("elapsed_seconds"),
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
        "_raw": record,
    }


def unique_scans(records):
    # The same physical scan can be uploaded twice:
    # once as scan_summary and once as the mission-linked radiation_scan.
    # Deduplicate them and prefer the mission-linked copy.
    grouped = {}

    for record in records:
        scan = normalize_scan(record)
        if scan is None or not scan["time"]:
            continue

        rid = scan["record_id"]
        key = (
            scan["time"],
            str(rid) if rid is not None else "",
            round(scan["cpm"], 4),
            scan["pulses"],
        )

        old = grouped.get(key)
        if old is None:
            grouped[key] = scan
            continue

        if scan["mission_file"] and not old["mission_file"]:
            grouped[key] = scan

    scans = list(grouped.values())
    scans.sort(key=lambda s: s["time"])
    return scans


def precision_label(pulses):
    if pulses <= 0:
        return "NO COUNTS"
    if pulses < 4:
        return "VERY LOW"
    if pulses < 10:
        return "LOW"
    if pulses < 25:
        return "FAIR"
    if pulses < 100:
        return "MODERATE"
    return "HIGH"


def pct_change(current, previous):
    if previous is None or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100.0


def round_or_none(value, digits):
    if value is None:
        return None
    return round(value, digits)


def build_payload(records):
    scans = unique_scans(records)

    if not scans:
        return {
            "state": 0,
            "available": False,
            "recent": [],
        }

    cur = scans[-1]
    prev = scans[-2] if len(scans) >= 2 else None

    pulses = cur["pulses"]
    duration = cur["duration_seconds"]
    cpm = cur["cpm"]
    dose = cur["dose_usvh"]

    sigma_cpm = None
    relative_sigma_pct = None

    if pulses > 0 and duration > 0:
        sigma_cpm = math.sqrt(pulses) * 60.0 / duration
        relative_sigma_pct = 100.0 / math.sqrt(pulses)

    cpm_low = max(0.0, cpm - sigma_cpm) if sigma_cpm is not None else None
    cpm_high = cpm + sigma_cpm if sigma_cpm is not None else None

    integrated_dose = None
    if duration > 0:
        integrated_dose = dose * duration / 3600.0

    previous_cpm = prev["cpm"] if prev else None
    previous_dose = prev["dose_usvh"] if prev else None

    recent = []
    for scan in scans[-RECENT_LIMIT:]:
        recent.append({
            "time": scan["time"],
            "cpm": round(scan["cpm"], 3),
            "dose_usvh": round(scan["dose_usvh"], 4),
            "pulses": scan["pulses"],
            "duration_seconds": round(scan["duration_seconds"], 2),
        })

    in_mission = bool(cur["mission_file"])

    return {
        "state": round(cpm, 3),
        "available": True,
        "scan_time": cur["time"],
        "record_id": cur["record_id"],
        "cpm": round(cpm, 3),
        "dose_usvh": round(dose, 4),
        "pulses": pulses,
        "duration_seconds": round(duration, 2),

        "previous_time": prev["time"] if prev else "",
        "previous_cpm": round_or_none(previous_cpm, 3),
        "previous_dose_usvh": round_or_none(previous_dose, 4),
        "delta_cpm": round_or_none(
            cpm - previous_cpm if previous_cpm is not None else None, 3
        ),
        "delta_cpm_pct": round_or_none(
            pct_change(cpm, previous_cpm), 1
        ),
        "delta_dose_usvh": round_or_none(
            dose - previous_dose if previous_dose is not None else None, 4
        ),
        "delta_dose_pct": round_or_none(
            pct_change(dose, previous_dose), 1
        ),

        "sigma_cpm": round_or_none(sigma_cpm, 3),
        "relative_sigma_pct": round_or_none(relative_sigma_pct, 1),
        "cpm_low_1sigma": round_or_none(cpm_low, 3),
        "cpm_high_1sigma": round_or_none(cpm_high, 3),
        "count_precision": precision_label(pulses),
        "integrated_dose_usv": round_or_none(integrated_dose, 7),

        "scope": "MISSION" if in_mission else "STANDALONE",
        "mission_code": cur["mission_code"] if in_mission else "",
        "mission_name": cur["mission_name"] if in_mission else "",
        "mission_elapsed": cur["mission_elapsed"] if in_mission else None,
        "latitude": cur["latitude"],
        "longitude": cur["longitude"],

        "recent": recent,
    }


def main():
    records, error = load_records()
    if error:
        payload = {
            "state": 0,
            "available": False,
            "error": error,
            "recent": [],
        }
    else:
        payload = build_payload(records)

    print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))


if __name__ == "__main__":
    main()
