#!/usr/bin/env python3

import json
import os
import sys
from datetime import datetime, timezone


STATE_FILE = "/config/tricorder/archive_state.json"

ARCHIVE_FILE = os.environ.get(
    "TRICORDER_ARCHIVE_PATH",
    "/config/tricorder/tricorder_uploads.jsonl",
)


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        if not isinstance(data, dict):
            data = {}

    except Exception:
        data = {}

    data.setdefault("archived", {})

    if not isinstance(data["archived"], dict):
        data["archived"] = {}

    return data


def save_state(data):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

    temp_file = STATE_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)

    os.replace(temp_file, STATE_FILE)


def delete_mission_records(mission_id):
    if not os.path.exists(ARCHIVE_FILE):
        raise RuntimeError(
            f"Mission archive file does not exist: {ARCHIVE_FILE}"
        )

    temp_file = ARCHIVE_FILE + ".tmp"

    removed = 0

    try:
        with open(
            ARCHIVE_FILE,
            "r",
            encoding="utf-8",
        ) as source, open(
            temp_file,
            "w",
            encoding="utf-8",
        ) as destination:

            for raw_line in source:

                line = raw_line.strip()

                remove_line = False

                if line.startswith("{"):
                    try:
                        record = json.loads(line)

                        if isinstance(record, dict):
                            record_mission_id = str(
                                record.get("mission_file", "") or ""
                            )

                            if record_mission_id == mission_id:
                                remove_line = True

                    except Exception:
                        pass

                if remove_line:
                    removed += 1
                else:
                    destination.write(raw_line)

        os.replace(temp_file, ARCHIVE_FILE)

    except Exception:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception:
            pass

        raise

    return removed


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: archive_manager.py "
            "archive|restore|delete MISSION_ID",
            file=sys.stderr,
        )
        sys.exit(2)

    action = sys.argv[1].strip().lower()
    mission_id = sys.argv[2].strip()

    if not mission_id:
        print("Mission ID is empty.", file=sys.stderr)
        sys.exit(2)

    data = load_state()
    archived = data["archived"]

    if action == "archive":

        archived[mission_id] = datetime.now(
            timezone.utc
        ).isoformat()

        save_state(data)

        print(
            json.dumps({
                "result": "archived",
                "mission_id": mission_id,
            })
        )

    elif action == "restore":

        archived.pop(mission_id, None)

        save_state(data)

        print(
            json.dumps({
                "result": "restored",
                "mission_id": mission_id,
            })
        )

    elif action == "delete":

        # Safety interlock:
        # only an already-archived mission may be permanently deleted.
        if mission_id not in archived:
            print(
                "REFUSED: mission must be archived before deletion.",
                file=sys.stderr,
            )
            sys.exit(3)

        removed = delete_mission_records(mission_id)

        archived.pop(mission_id, None)

        save_state(data)

        print(
            json.dumps({
                "result": "deleted",
                "mission_id": mission_id,
                "records_removed": removed,
            })
        )

    else:
        print(
            f"Unknown action: {action}",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()