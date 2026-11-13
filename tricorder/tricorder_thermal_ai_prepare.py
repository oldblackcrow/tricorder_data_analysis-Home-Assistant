#!/usr/bin/env python3
"""Prepare mission-specific TR-460 thermal data for Home Assistant AI Task.

Reads only the existing private JSONL archive and renderer output. Calculates
temperature statistics from original 32x24 deci-Celsius samples, not PNG colors.
Copies valid rendered PNGs to authenticated HA Media for AI Task attachments.
Standard library only; never modifies source archives or images.
"""
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ARCHIVE = Path(os.environ.get(
    "TRICORDER_ARCHIVE_PATH", "/config/tricorder/tricorder_uploads.jsonl"))
RENDER_DIR = Path(os.environ.get(
    "TRICORDER_THERMAL_IMAGE_DIR", "/config/www/tricorder_thermal"))
MEDIA_DIR = Path(os.environ.get(
    "TRICORDER_AI_MEDIA_DIR", "/media/tricorder_ai"))
ARCHIVE_NAME = re.compile(r"thermal_distance_[0-9]{8}\.jsonl\Z")
MAX_ATTACHMENTS = 16


def emit(data):
    print(json.dumps(data, ensure_ascii=True, separators=(",", ":")))
    return 0


def snapshots():
    """Index valid thermal snapshots by their actual mission_file."""
    missions = {}
    with ARCHIVE.open(encoding="utf-8") as archive:
        for line in archive:
            # Avoid parsing large unrelated base64 WAV-transfer records.
            if '"thermal_snapshot"' not in line and '"mission_start"' not in line:
                continue
            if not line.lstrip().startswith("{"):
                continue
            try:
                record = json.loads(line)
            except (TypeError, ValueError):
                continue
            if not isinstance(record, dict):
                continue
            mission_id = record.get("mission_file")
            if not isinstance(mission_id, str) or not mission_id:
                continue
            mission = missions.setdefault(mission_id, {
                "mission_id": mission_id, "mission_code": "",
                "mission_name": "", "snapshots": {},
            })
            if record.get("record_type") == "mission_start":
                mission["mission_code"] = str(record.get("mission_code") or "")
                mission["mission_name"] = str(record.get("mission_name") or "")
            if record.get("record_type") != "thermal_snapshot":
                continue
            archive_file = record.get("archive_file")
            pixels = record.get("pixels")
            if (not isinstance(archive_file, str)
                    or not ARCHIVE_NAME.fullmatch(archive_file)
                    or record.get("width") != 32
                    or record.get("height") != 24
                    or record.get("unit") != "deci_c"
                    or not isinstance(pixels, list)
                    or len(pixels) != 768
                    or any(type(v) is not int or v < -32768 or v > 32767
                           for v in pixels)):
                continue
            valid = [v for v in pixels if v != -32768]
            if not valid:
                continue
            center = pixels[12 * 32 + 16]
            filename = archive_file[:-6] + ".png"
            mission["snapshots"][archive_file] = {
                "file": filename, "time": str(record.get("time") or ""),
                "minimum_deci_c": min(valid), "maximum_deci_c": max(valid),
                "sum_deci_c": sum(valid), "pixel_count": len(valid),
                "center_deci_c": center if center != -32768 else None,
            }
            if not mission["mission_code"]:
                mission["mission_code"] = str(record.get("mission_code") or "")
            if not mission["mission_name"]:
                mission["mission_name"] = str(record.get("mission_name") or "")
    return {name: mission for name, mission in missions.items()
            if mission["snapshots"]}


def summarize(mission):
    images = sorted(mission["snapshots"].values(),
                    key=lambda item: (item["time"], item["file"]))
    pixels = sum(image["pixel_count"] for image in images)
    centers = [image["center_deci_c"] for image in images
               if image["center_deci_c"] is not None]
    summary = {
        "mission_id": mission["mission_id"],
        "mission_code": mission["mission_code"],
        "mission_name": mission["mission_name"],
        "image_count": len(images),
        "valid_pixel_count": pixels,
        "mean_c": round(sum(im["sum_deci_c"] for im in images) / pixels / 10, 2),
        "minimum_c": round(min(im["minimum_deci_c"] for im in images) / 10, 2),
        "maximum_c": round(max(im["maximum_deci_c"] for im in images) / 10, 2),
        "mean_center_c": round(sum(centers) / len(centers) / 10, 2)
        if centers else None,
        "images": [],
    }
    for item in images:
        summary["images"].append({
            "file": item["file"], "time": item["time"],
            "mean_c": round(item["sum_deci_c"] / item["pixel_count"] / 10, 2),
            "minimum_c": round(item["minimum_deci_c"] / 10, 2),
            "maximum_c": round(item["maximum_deci_c"] / 10, 2),
            "center_c": round(item["center_deci_c"] / 10, 2)
            if item["center_deci_c"] is not None else None,
        })
    return summary


def find_comparison(missions, selected_id, query):
    if not query:
        return [], None
    candidates = [item for name, item in missions.items()
                  if name != selected_id]
    if query.casefold() == "all":
        return sorted(candidates, key=lambda m: m["mission_id"]), None
    match = [m for m in candidates if query.casefold() in {
        m["mission_id"].casefold(), m["mission_code"].casefold(),
        m["mission_name"].casefold()}]
    if not match:
        match = [m for m in candidates if query.casefold() in
                 (m["mission_code"] + " " + m["mission_name"]).casefold()]
    if len(match) != 1:
        return [], ("No matching comparison mission." if not match else
                    "Multiple missions match; specify the mission code: " +
                    ", ".join(m["mission_code"] for m in match[:8]))
    return match, None


def put_in_media(filename):
    """Copy only renderer-named images, atomically, to HA's private media."""
    if not re.fullmatch(r"thermal_distance_[0-9]{8}\.png", filename):
        return False
    source = RENDER_DIR / filename
    if not source.is_file():
        return False
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    target = MEDIA_DIR / filename
    if (target.is_file() and target.stat().st_size == source.stat().st_size
            and target.stat().st_mtime_ns == source.stat().st_mtime_ns):
        return True
    fd, tmp = tempfile.mkstemp(prefix=".thermal_ai_", dir=MEDIA_DIR)
    try:
        with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
            shutil.copyfileobj(inp, out)
        shutil.copystat(source, tmp)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return True


def prepare(selected_id, compare_to=""):
    if not selected_id or selected_id in {"unknown", "unavailable"}:
        return {"ok": False, "error": "Select a mission on the Tricorder dashboard first."}
    if not ARCHIVE.is_file():
        return {"ok": False, "error": "Tricorder JSONL archive is missing."}
    all_missions = snapshots()
    selected = all_missions.get(selected_id)
    if selected is None:
        return {"ok": False, "error": "Selected mission has no valid thermal snapshots."}
    comparisons, error = find_comparison(all_missions, selected_id, compare_to)
    if error:
        return {"ok": False, "error": error}
    selected_stats = summarize(selected)
    compare_stats = [summarize(m) for m in comparisons]
    # For 'all', compare the numeric data across every mission without
    # sending every archived PNG to an external AI.
    wants_images = comparisons if compare_to.casefold() != "all" else []
    groups = [("selected", selected_stats)] + [
        ("comparison", summarize(m)) for m in wants_images]
    attachments = []
    attachment_index = []
    for role, group in groups:
        for item in group["images"]:
            if len(attachments) >= MAX_ATTACHMENTS:
                break
            if put_in_media(item["file"]):
                attachments.append({
                    "media_content_id": "media-source://media_source/local/tricorder_ai/" +
                    item["file"],
                    "media_content_type": "image/png",
                })
                attachment_index.append({
                    "position": len(attachments), "role": role,
                    "mission_code": group["mission_code"],
                    "file": item["file"], "time": item["time"],
                })
    image_total = selected_stats["image_count"] + sum(
        stat["image_count"] for stat in
        ([summarize(m) for m in wants_images]))
    return {
        "ok": True, "selected": selected_stats, "comparisons": compare_stats,
        "comparison_request": compare_to, "attachments": attachments,
        "attachment_index": attachment_index,
        "visible_images": len(attachments),
        "available_images": image_total,
        "unattached_images": image_total - len(attachments),
        "note": ("Only attached images receive visual interpretation. "
                 "Numeric statistics use every valid archived thermal frame."),
    }


def main():
    if len(sys.argv) not in (2, 3):
        return emit({"ok": False, "error": "Expected selected mission ID and optional comparison."})
    try:
        return emit(prepare(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else ""))
    except (OSError, ValueError, UnicodeError) as exc:
        return emit({"ok": False, "error": "Thermal archive or media access failed: " +
                     str(exc)})


if __name__ == "__main__":
    sys.exit(main())
