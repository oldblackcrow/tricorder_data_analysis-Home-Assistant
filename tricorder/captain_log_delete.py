#!/usr/bin/env python3
"""Delete one TR-460 Captain's Log from Home Assistant, not the handheld.

Keep a tombstone alongside the original archive so the existing webhook
receiver does not reconstruct a deliberately deleted file from historical
JSONL upload records. Original JSONL remains untouched.
"""
import json
import os
from pathlib import Path
import re
import sys

SOURCE = Path(os.environ.get("TRICORDER_CAPTAINS_DIR", "/config/tricorder/captains"))
MEDIA = Path(os.environ.get("TRICORDER_CAPTAINS_MEDIA_DIR", "/media/tricorder_captains"))
NUMBER = re.compile(r"[0-9]{1,8}\Z")


def delete(log_number):
    if not NUMBER.fullmatch(log_number) or int(log_number) < 1:
        raise ValueError("invalid Captain's Log number")
    name = f"captain_{int(log_number):08d}"
    if not SOURCE.is_dir():
        raise FileNotFoundError("Captain's Log directory missing")
    original = SOURCE / (name + ".adp")
    metadata = SOURCE / (name + ".json")
    wav = MEDIA / (name + ".wav")
    tombstone = SOURCE / (name + ".deleted")

    if not tombstone.is_file() and not any(
        path.is_file() for path in (original, metadata, wav)
    ):
        raise FileNotFoundError(f"Captain's Log {name} not found")

    # Mark *before* removing anything so queued receiver jobs cannot restore
    # this file if HA restarts or the delete is interrupted.
    if not tombstone.exists():
        with tombstone.open("x", encoding="ascii") as handle:
            handle.write("Deleted from Home Assistant; keep this marker to block historical reimport.\n")
            handle.flush()
            os.fsync(handle.fileno())
    removed = []
    for path in (original, metadata, wav):
        if path.exists():
            path.unlink()
            removed.append(path.name)
    return {"log": name, "removed": removed, "reimport_blocked": True}


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("usage: captain_log_delete.py NUMBER")
        print(json.dumps(delete(sys.argv[1])))
    except (OSError, ValueError) as error:
        print(f"Captain's Log deletion failed: {error}", file=sys.stderr)
        sys.exit(1)
