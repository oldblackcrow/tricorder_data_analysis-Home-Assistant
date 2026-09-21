#!/usr/bin/env python3

import json
import os
import sys
from datetime import datetime, timedelta


ARCHIVE_PATH = os.environ.get(
    "TRICORDER_ARCHIVE_PATH",
    "/config/tricorder/tricorder_uploads.jsonl",
)

ARCHIVE_STATE_PATH = "/config/tricorder/archive_state.json"


SCAN_TYPES = {
    "atmosphere_scan": "tricorder_atmosphere",
    "radiation_scan": "tricorder_radiation",
    "scan_summary": "tricorder_radiation",
    "audio_scan": "tricorder_audio",
    "color_scan": "tricorder_color",
    "orientation_scan": "tricorder_orientation",
    "magnetic_scan": "tricorder_magnetic",
    "location_update": "tricorder_location",
    "thermal_scan": "tricorder_thermal",
    "distance_scan": "tricorder_distance",
    "uv_scan": "tricorder_uv",
}


def load_archived_missions():
    try:
        with open(
            ARCHIVE_STATE_PATH,
            "r",
            encoding="utf-8",
        ) as handle:
            data = json.load(handle)

        archived = data.get("archived", {})

        if isinstance(archived, dict):
            return archived

    except Exception:
        pass

    return {}


def load_records(mode=None, mission_id=""):
    """Keep only records needed by this command.

    The JSONL file must still be read, but selected-mission requests
    should not hold every unrelated scan in memory. For scans, all
    mission starts and untagged GPS fixes are retained to support the
    existing, bounded location time-window inference.
    """
    if mode in ("events", "scans", "comparison") and mission_id in (
        "", "unknown", "unavailable",
    ):
        return [], None

    records = []

    try:
        with open(
            ARCHIVE_PATH,
            "r",
            encoding="utf-8",
        ) as handle:

            for line in handle:
                line = line.strip()

                if not line or not line.startswith("{"):
                    continue

                try:
                    record = json.loads(line)
                except Exception:
                    continue

                if not isinstance(record, dict):
                    continue

                kind = record.get("record_type")
                record_mission = str(record.get("mission_file", "") or "")

                if mode in ("catalog", "archived"):
                    if kind != "mission_start":
                        continue
                elif mode == "events":
                    if record_mission != mission_id:
                        continue
                elif mode in ("scans", "comparison"):
                    if not (
                        record_mission == mission_id
                        or kind == "mission_start"
                        or (kind == "location_update" and not record_mission)
                    ):
                        continue

                records.append(record)

    except Exception as error:
        return [], str(error)

    return records, None


def result_payload(series, count):
    if series:
        results = [{"series": series}]
    else:
        results = [{}]

    return {
        "count": count,
        "results": results,
    }


def mission_catalog(records):
    # One row per mission_file, newest mission first.
    # Archived missions are hidden from this normal catalog.

    archived = load_archived_missions()

    seen = set()
    starts = []

    for record in records:

        if record.get("record_type") != "mission_start":
            continue

        mission_id = str(
            record.get("mission_file", "") or ""
        )

        if mission_id in archived:
            continue

        if not mission_id or mission_id in seen:
            continue

        seen.add(mission_id)
        starts.append(record)

    starts.sort(
        key=lambda r: str(r.get("time", "")),
        reverse=True,
    )

    columns = [
        "time",
        "elapsed_seconds",
        "mission_code",
        "mission_id",
        "mission_name",
        "status",
    ]

    values = []

    for r in starts[:100]:
        values.append([
            r.get("time"),
            r.get("elapsed_seconds", 0),
            r.get("mission_code", "unknown"),
            r.get("mission_file", ""),
            r.get("mission_name", "unnamed"),
            r.get("status", "active"),
        ])

    series = []

    if values:
        series.append({
            "name": "tricorder_mission_event",
            "columns": columns,
            "values": values,
        })

    return result_payload(series, len(values))


def archived_mission_catalog(records):
    # One row per archived mission.
    # Mission metadata comes from the original mission_start record.

    archived = load_archived_missions()

    if not archived:
        return result_payload([], 0)

    seen = set()
    starts = []

    for record in records:

        if record.get("record_type") != "mission_start":
            continue

        mission_id = str(
            record.get("mission_file", "") or ""
        )

        if not mission_id:
            continue

        if mission_id not in archived:
            continue

        if mission_id in seen:
            continue

        seen.add(mission_id)
        starts.append(record)

    starts.sort(
        key=lambda r: str(r.get("time", "")),
        reverse=True,
    )

    columns = [
        "time",
        "elapsed_seconds",
        "mission_code",
        "mission_id",
        "mission_name",
        "status",
        "archived_at",
    ]

    values = []

    for r in starts[:100]:

        mission_id = str(
            r.get("mission_file", "") or ""
        )

        values.append([
            r.get("time"),
            r.get("elapsed_seconds", 0),
            r.get("mission_code", "unknown"),
            mission_id,
            r.get("mission_name", "unnamed"),
            r.get("status", "active"),
            archived.get(mission_id, ""),
        ])

    series = []

    if values:
        series.append({
            "name": "tricorder_archived_mission",
            "columns": columns,
            "values": values,
        })

    return result_payload(series, len(values))


def mission_events(records, mission_id):

    if not mission_id or mission_id in (
        "unknown",
        "unavailable",
    ):
        return result_payload([], 0)

    selected = [
        r
        for r in records
        if str(r.get("mission_file", "") or "")
        == mission_id
    ]

    selected.sort(
        key=lambda r: str(r.get("time", ""))
    )

    columns = [
        "time",
        "elapsed_seconds",
        "event",
        "mission_code",
        "mission_id",
        "mission_name",
        "status",
    ]

    values = []

    for r in selected:

        event = r.get(
            "record_type",
            "unknown",
        )

        if event == "scan_summary":
            event = "radiation_scan"

        status = r.get(
            "status",
            r.get(
                "scan_status",
                "none",
            ),
        )

        values.append([
            r.get("time"),
            r.get("elapsed_seconds", -1),
            event,
            r.get("mission_code", "unknown"),
            mission_id,
            r.get("mission_name", "unnamed"),
            status,
        ])

    series = []

    if values:
        series.append({
            "name": "tricorder_mission_event",
            "columns": columns,
            "values": values,
        })

    return result_payload(series, len(values))


def common_tags(r, mission_id):
    return {
        "mission_id": mission_id,
        "mission_code": r.get(
            "mission_code",
            "unknown",
        ),
        "mission_name": r.get(
            "mission_name",
            "unnamed",
        ),
        "scope": "mission",
    }


def normalize_scan(r, mission_id):

    rt = r.get("record_type", "")

    measurement = SCAN_TYPES.get(rt)

    if not measurement:
        return None, None

    row = {
        "time": r.get("time"),
    }

    row.update(
        common_tags(
            r,
            mission_id,
        )
    )

    row["elapsed_seconds"] = r.get(
        "elapsed_seconds",
        -1,
    )

    if measurement == "tricorder_radiation":

        row.update({
            "cpm": r.get("cpm", 0),
            "dose_usvh": r.get(
                "dose_usvh",
                0,
            ),
            "pulses": r.get(
                "pulses",
                0,
            ),
            "duration_seconds": r.get(
                "duration_seconds",
                0,
            ),
            "record_id": r.get(
                "radiation_record_id",
                r.get("id", 0),
            ),
            "status": r.get(
                "status",
                r.get(
                    "scan_status",
                    "none",
                ),
            ),
        })

    elif measurement == "tricorder_atmosphere":

        tc = r.get("temperature_c")
        pa = r.get("pressure_pa")

        row.update({
            "temperature_f":
                (float(tc) * 1.8 + 32)
                if tc is not None
                else None,
            "humidity_percent":
                r.get("humidity_percent"),
            "pressure_hpa":
                (float(pa) / 100.0)
                if pa is not None
                else None,
            "altitude_m":
                r.get("altitude_m"),
            "lux":
                r.get("lux"),
            "proximity":
                r.get("proximity"),
            "eco2_ppm":
                r.get("eco2_ppm"),
            "tvoc_ppb":
                r.get("tvoc_ppb"),
        })

    elif measurement == "tricorder_orientation":

        row.update({
            "heading_deg":
                r.get("heading_deg"),
            "magnetic_field_ut":
                r.get("magnetic_field_ut"),
            "accel_x":
                r.get("accel_x"),
            "accel_y":
                r.get("accel_y"),
            "accel_z":
                r.get("accel_z"),
        })

    elif measurement == "tricorder_audio":

        row.update({
            "relative_db":
                r.get("relative_db"),
            "peak_db":
                r.get("peak_db"),
        })

    elif measurement == "tricorder_magnetic":

        row.update({
            "magnetic_field_ut":
                r.get("magnetic_field_ut"),
            "heading_deg":
                r.get("heading_deg"),
            "mag_x_ut":
                r.get("mag_x_ut"),
            "mag_y_ut":
                r.get("mag_y_ut"),
            "mag_z_ut":
                r.get("mag_z_ut"),
        })

    elif measurement == "tricorder_color":

        row.update({
            "red":
                r.get("red"),
            "green":
                r.get("green"),
            "blue":
                r.get("blue"),
            "clear":
                r.get("clear"),
            "lux":
                r.get("lux"),
            "proximity":
                r.get("proximity"),
        })

    elif measurement == "tricorder_location":

        row.update({
            "latitude":
                r.get("latitude"),
            "longitude":
                r.get("longitude"),
            "location_source": r.get(
                "_location_source",
                "location_update",
            ),
        })

    elif measurement == "tricorder_thermal":

        center = r.get(
            "center_c",
            r.get("thermal_center_c"),
        )

        min_c = r.get(
            "min_c",
            r.get("thermal_min_c"),
        )

        max_c = r.get(
            "max_c",
            r.get("thermal_max_c"),
        )

        explicit = r.get(
            "available",
            r.get("thermal_available"),
        )

        available = (
            bool(explicit)
            if explicit is not None
            else center is not None
        )

        row["available"] = available
        row["center_c"] = center
        row["center_f"] = (
            float(center) * 1.8 + 32
            if center is not None
            else None
        )

        row["min_c"] = min_c
        row["min_f"] = (
            float(min_c) * 1.8 + 32
            if min_c is not None
            else None
        )

        row["max_c"] = max_c
        row["max_f"] = (
            float(max_c) * 1.8 + 32
            if max_c is not None
            else None
        )

    elif measurement == "tricorder_distance":

        distance = r.get(
            "distance_m",
            r.get("lidar_distance_m"),
        )

        explicit = r.get(
            "available",
            r.get("distance_available"),
        )

        available = (
            bool(explicit)
            if explicit is not None
            else distance is not None
        )

        row.update({
            "available":
                available,
            "distance_m":
                distance,
        })

    elif measurement == "tricorder_uv":

        uv_raw = r.get("uv_raw")
        uv_index = r.get("uv_index")

        explicit = r.get(
            "available",
            r.get("uv_available"),
        )

        available = (
            bool(explicit)
            if explicit is not None
            else (
                uv_raw is not None
                or uv_index is not None
            )
        )

        row.update({
            "available":
                available,
            "uv_raw":
                uv_raw,
            "uv_index":
                uv_index,
        })

    return measurement, row


def _radiation_sample_time(end_time, duration, elapsed):
    if not end_time:
        return end_time

    try:
        raw = str(end_time)
        parse_value = (
            raw[:-1] + "+00:00"
            if raw.endswith("Z")
            else raw
        )
        end_dt = datetime.fromisoformat(parse_value)
        sample_dt = (
            end_dt
            - timedelta(seconds=float(duration))
            + timedelta(seconds=float(elapsed))
        )
        result = sample_dt.isoformat()

        if raw.endswith("Z") and result.endswith("+00:00"):
            result = result[:-6] + "Z"

        return result
    except Exception:
        return end_time


def _radiation_series_rows(r, mission_id):
    bins = r.get("pulse_bins", [])

    if not isinstance(bins, list) or not bins:
        return []

    try:
        interval = float(r.get("pulse_bin_seconds", 1) or 1)
    except Exception:
        interval = 1.0

    try:
        duration = float(r.get("duration_seconds", 0) or 0)
    except Exception:
        duration = 0.0

    record_id = r.get(
        "radiation_record_id",
        r.get("id", 0),
    )

    rows = []
    cumulative = 0

    for index, pulse_value in enumerate(bins, start=1):
        try:
            pulse_1s = int(pulse_value or 0)
        except Exception:
            pulse_1s = 0

        cumulative += pulse_1s
        elapsed = index * interval

        cpm = (
            cumulative * 60.0 / elapsed
            if elapsed > 0
            else 0.0
        )
        dose = cpm / 53.032

        row = {
            "time": _radiation_sample_time(
                r.get("time"),
                duration,
                elapsed,
            ),
            "elapsed_seconds": elapsed,
            "pulse_1s": pulse_1s,
            "cumulative_pulses": cumulative,
            "cpm": cpm,
            "dose_usvh": dose,
            "record_id": record_id,
            "scan_id": record_id,
        }

        row.update(common_tags(r, mission_id))
        rows.append(row)

    return rows



def _record_timestamp(value):
    """Return a comparable timestamp, or None for an unavailable RTC."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        value = value.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(value).timestamp()
    except (ValueError, OverflowError, OSError):
        return None


def _mission_location_row(record, mission_id, source):
    """Build a location row from mission metadata or a GPS update.

    Do not manufacture a position when latitude or longitude is absent.
    """
    try:
        lat = float(record["latitude"])
        lon = float(record["longitude"])
    except (KeyError, ValueError, TypeError):
        return None

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None

    if _record_timestamp(record.get("time")) is None:
        return None

    item = dict(record)
    item["record_type"] = "location_update"
    item["_location_source"] = source
    item["latitude"] = lat
    item["longitude"] = lon
    _, row = normalize_scan(item, mission_id)
    return row


def _selected_mission_window(records, mission_id):
    """Return a bounded start/end interval for untagged GPS updates.

    A nearby fix *after* mission_end is not known to belong to that
    mission. An open-ended mission is not used for time inference.
    """
    starts = []
    ends = []
    all_starts = []
    for record in records:
        kind = record.get("record_type")
        if kind not in ("mission_start", "mission_end"):
            continue
        when = _record_timestamp(record.get("time"))
        if when is None:
            continue
        if kind == "mission_start":
            all_starts.append(when)
            if record.get("mission_file") == mission_id:
                starts.append(when)
        elif kind == "mission_end" and record.get("mission_file") == mission_id:
            ends.append(when)

    if not starts:
        return None
    start = min(starts)
    later_ends = [t for t in ends if t >= start]
    if not later_ends:
        return None
    end = min(later_ends)
    next_starts = [t for t in all_starts if t > start]
    if next_starts:
        end = min(end, min(next_starts))
    return (start, end)


def mission_scans(records, mission_id):

    if not mission_id or mission_id in (
        "unknown",
        "unavailable",
    ):
        return result_payload([], 0)

    grouped = {}
    radiation_series_seen = set()

    for r in records:

        if str(
            r.get("mission_file", "") or ""
        ) != mission_id:
            continue

        # Mission start/end records contain coordinates even when no
        # location_update carries a mission_file identifier.
        if r.get("record_type") in ("mission_start", "mission_end"):
            location = _mission_location_row(
                r, mission_id, r["record_type"],
            )
            if location is not None:
                grouped.setdefault("tricorder_location", []).append(location)
            continue

        measurement, row = normalize_scan(
            r,
            mission_id,
        )

        if measurement is None:
            continue

        grouped.setdefault(
            measurement,
            [],
        ).append(row)

        if measurement == "tricorder_radiation":
            record_id = r.get(
                "radiation_record_id",
                r.get("id", 0),
            )

            # Older scans may omit an ID. Don't collapse every
            # no-ID scan onto the same default record_id=0.
            series_key = (
                ("record", str(record_id))
                if record_id not in (None, "", 0, "0")
                else ("time", str(r.get("time", "")))
            )

            if series_key not in radiation_series_seen:
                radiation_rows = _radiation_series_rows(
                    r,
                    mission_id,
                )

                if radiation_rows:
                    grouped.setdefault(
                        "tricorder_radiation_series",
                        [],
                    ).extend(radiation_rows)

                    radiation_series_seen.add(
                        series_key
                    )

    # Older GPS updates may have no mission_file. Associate only those
    # timestamped *inside* a completed mission, not nearby orphaned fixes.
    window = _selected_mission_window(records, mission_id)
    if window is not None:
        start, end = window
        for r in records:
            if r.get("record_type") != "location_update":
                continue
            if r.get("mission_file"):
                continue
            when = _record_timestamp(r.get("time"))
            if when is None or not (start <= when <= end):
                continue
            location = _mission_location_row(
                r, mission_id, "time_window",
            )
            if location is not None:
                grouped.setdefault("tricorder_location", []).append(location)

    series = []
    total = 0

    for measurement in sorted(grouped):

        rows = grouped[measurement]

        rows.sort(
            key=lambda row:
                str(row.get("time", ""))
        )

        columns = ["time"]

        for row in rows:

            for key in row:

                if (
                    key != "time"
                    and key not in columns
                ):
                    columns.append(key)

        values = [
            [
                row.get(col)
                for col in columns
            ]
            for row in rows
        ]

        total += len(values)

        series.append({
            "name": measurement,
            "columns": columns,
            "values": values,
        })

    return result_payload(
        series,
        total,
    )


def main():

    mode = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "catalog"
    )

    mission_id = (
        sys.argv[2]
        if len(sys.argv) > 2
        else ""
    )

    records, error = load_records(mode, mission_id)

    if error:

        payload = {
            "count": 0,
            "results": [{}],
            "error": error,
        }

    elif mode == "catalog":

        payload = mission_catalog(
            records
        )

    elif mode == "archived":

        payload = archived_mission_catalog(
            records
        )

    elif mode == "events":

        payload = mission_events(
            records,
            mission_id,
        )

    elif mode in (
        "scans",
        "comparison",
    ):

        payload = mission_scans(
            records,
            mission_id,
        )

    else:

        payload = {
            "count": 0,
            "results": [{}],
            "error": "unknown mode",
        }

    print(
        json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
