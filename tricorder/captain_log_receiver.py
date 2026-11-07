#!/usr/bin/env python3
"""Reassemble Rev098 Captain's Log ADPCM files from the existing private JSONL.

The HA File notifier must write webhook events first. The receiver automation
then calls this script on captains_log_complete. HTTP 2xx is not a disk ACK.
No web/static directory is used. Works with Python 3 standard library only.
"""
import base64
import binascii
import fcntl
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import zlib

ARCHIVE = Path(os.environ.get(
    "TRICORDER_ARCHIVE_PATH", "/config/tricorder/tricorder_uploads.jsonl"
))
DEST = Path(os.environ.get(
    "TRICORDER_CAPTAINS_DIR", "/config/tricorder/captains"
))
FILENAME = re.compile(r"captain_[0-9]{8}\.adp\Z")
TX = re.compile(r"[0-9a-f]{16}\Z")
CRC = re.compile(r"[0-9a-f]{8}\Z")
CHUNK = 4096
MAX_SIZE = 3 * 1024 * 1024
MAX_META = 4096
FORM = "<8sHHIIHHII"  # Rev093-098: magic, version, size, Hz, epoch, samples,
                         # packet bytes, packet count, duration milliseconds
HEADER_SIZE = struct.calcsize(FORM)  # 32 bytes
KINDS = {"captains_log_begin", "captains_log_chunk", "captains_log_complete"}


def messages():
    with ARCHIVE.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if not line.startswith("{"):
                continue
            try:
                value = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if isinstance(value, dict):
                yield value


def valid_manifest(row):
    if not isinstance(row, dict):
        return False
    name, tx, checksum = (row.get(k) for k in ("file", "transfer_id", "crc32"))
    count, size = row.get("chunks"), row.get("bytes")
    return (
        isinstance(name, str) and FILENAME.fullmatch(name) is not None
        and isinstance(tx, str) and TX.fullmatch(tx) is not None
        and isinstance(checksum, str) and CRC.fullmatch(checksum) is not None
        and type(size) is int and HEADER_SIZE + 88 <= size <= MAX_SIZE
        and type(count) is int
        and count == (size + CHUNK - 1) // CHUNK
    )


def same_manifest(left, right):
    return all(left.get(k) == right.get(k)
               for k in ("file", "transfer_id", "crc32", "bytes", "chunks"))


def valid_header(path, size):
    with path.open("rb") as inp:
        blob = inp.read(HEADER_SIZE)
    if len(blob) != HEADER_SIZE:
        return False
    magic, ver, head, hz, epoch, samples, packet_size, blocks, duration = (
        struct.unpack(FORM, blob)
    )
    return (magic == b"TRCAP01\x00" and ver == 1
            and head == HEADER_SIZE and hz == 8000 and samples == 160
            and packet_size == 88 and blocks > 0
            and HEADER_SIZE + blocks * packet_size == size)


def file_crc(path):
    checksum = 0
    with path.open("rb") as inp:
        while True:
            data = inp.read(65536)
            if not data:
                break
            checksum = zlib.crc32(data, checksum)
    return f"{checksum:08x}"


def decode_metadata(raw, filename):
    if not isinstance(raw, str) or not raw:
        return None
    if len(raw) > ((MAX_META + 2) // 3) * 4 + 4:
        raise ValueError("metadata too large")
    try:
        data = base64.b64decode(raw, validate=True)
        meta = json.loads(data)
    except (binascii.Error, ValueError, UnicodeError) as error:
        raise ValueError("invalid metadata") from error
    if (len(data) > MAX_META or not isinstance(meta, dict)
            or meta.get("record_type") != "captains_log"
            or meta.get("file") != filename):
        raise ValueError("metadata does not match recording")
    return data


def atomic_write(path, content):
    fd, temp = tempfile.mkstemp(prefix=".capt_meta_", dir=str(DEST))
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        if path.exists():
            if path.read_bytes() != content:
                raise ValueError("existing metadata differs; kept untouched")
        else:
            os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def restore(completion):
    tx, filename = completion["transfer_id"], completion["file"]
    size, total = completion["bytes"], completion["chunks"]
    target = DEST / filename
    if target.exists():
        if (target.stat().st_size == size
                and file_crc(target) == completion["crc32"]
                and valid_header(target, size)):
            return "already-present"
        raise ValueError(f"{filename}: existing file differs; kept untouched")

    # Look up the begin separately. HA may persist closely spaced webhook
    # automation events out of order if an older installation is not queued.
    begin = None
    for row in messages():
        if (row.get("transfer_id") == tx
                and row.get("record_type") == "captains_log_begin"):
            if begin is not None or not valid_manifest(row) or not same_manifest(row, completion):
                raise ValueError("conflicting or invalid begin record")
            begin = row
    if begin is None:
        raise ValueError("missing begin event")
    meta = decode_metadata(begin.get("metadata_b64"), filename)

    fd, temp = tempfile.mkstemp(prefix=".capt_data_", dir=str(DEST))
    seen = set()
    complete_seen = False
    try:
        with os.fdopen(fd, "wb") as out:
            for row in messages():
                if row.get("transfer_id") != tx:
                    continue
                kind = row.get("record_type")
                if kind == "captains_log_complete":
                    if not same_manifest(row, completion):
                        raise ValueError("completion does not match begin")
                    complete_seen = True
                elif kind == "captains_log_chunk":
                    if row.get("file") != filename or type(row.get("index")) is not int:
                        raise ValueError("invalid chunk metadata")
                    index = row["index"]
                    if index < 0 or index >= total or index in seen:
                        raise ValueError("out-of-range or duplicate chunk")
                    value = row.get("data")
                    if not isinstance(value, str) or len(value) > 5472:
                        raise ValueError("invalid Base64 chunk size")
                    try:
                        binary = base64.b64decode(value, validate=True)
                    except binascii.Error as error:
                        raise ValueError("invalid Base64 chunk") from error
                    expected = min(CHUNK, size - index * CHUNK)
                    if len(binary) != expected:
                        raise ValueError("incorrect chunk length")
                    out.seek(index * CHUNK)
                    out.write(binary)
                    seen.add(index)
            out.flush()
            os.fsync(out.fileno())

        if not complete_seen or len(seen) != total:
            raise ValueError("incomplete Captain's Log transfer")
        staged = Path(temp)
        if (staged.stat().st_size != size or
                file_crc(staged) != completion["crc32"] or
                not valid_header(staged, size)):
            raise ValueError("binary size, CRC32, or header mismatch")
        if target.exists():
            raise ValueError("destination appeared during transfer")
        os.replace(temp, target)
        temp = None
        if meta is not None:
            atomic_write(DEST / filename.replace(".adp", ".json"), meta)
        return "restored"
    finally:
        if temp is not None and os.path.exists(temp):
            os.unlink(temp)

def run():
    if not ARCHIVE.is_file():
        raise FileNotFoundError(f"archive missing: {ARCHIVE}")
    DEST.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(DEST, 0o700)
    # Prevent two simultaneous HA automation calls from corrupting output.
    with (DEST / ".receiver.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        completed = {}
        for item in messages():
            if item.get("record_type") == "captains_log_complete" and valid_manifest(item):
                completed[item["transfer_id"]] = item
        stats = {"restored": 0, "already-present": 0, "failed": 0}
        for item in completed.values():
            try:
                outcome = restore(item)
                stats[outcome] += 1
                if outcome == "restored":
                    print(f"Captain's Log restored: {item['file']}")
            except (OSError, ValueError, UnicodeError) as error:
                stats["failed"] += 1
                print(f"Captain's Log {item['file']} failed: {error}", file=sys.stderr)
        # Also materialize browser-playable WAVs in HA's protected Media Browser.
        # Old uploads are converted on the next receiver run as well.
        from captain_log_wav import convert_all
        wav_stats = convert_all()
        print(json.dumps({"transfers": stats, "wav": wav_stats}))
        return 1 if stats["failed"] or wav_stats["failed"] else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (OSError, ValueError) as error:
        print(f"Captain's Log receiver: {error}", file=sys.stderr)
        sys.exit(1)
