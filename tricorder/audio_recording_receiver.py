#!/usr/bin/env python3
"""Restore Rev100 audio-scan PCM WAV transfers to authenticated HA Media.

The existing JSONL notifier receives audio_recording_{begin,chunk,complete}.
An HA automation runs this script after a complete event is recorded.
Outputs WAVs only in /media/tricorder_audio (HA's authenticated Media Browser).
Metadata JSON sidecars remain private under /config/tricorder/recordings.
No third-party packages or publicly served /config/www audio files.
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
    "TRICORDER_AUDIO_MEDIA_DIR", "/media/tricorder_audio"
))
METADATA = Path(os.environ.get(
    "TRICORDER_AUDIO_METADATA_DIR", "/config/tricorder/recordings"
))
FILENAME = re.compile(r"audio_[0-9]{8}\\.wav\\Z")
TX = re.compile(r"[0-9a-f]{16}\\Z")
CRC = re.compile(r"[0-9a-f]{8}\\Z")
CHUNK = 4096
MAX_SIZE = 1024 * 1024
MAX_META = 4096
WAV_FORMAT = "<4sI4s4sIHHIIHH4sI"
WAV_HEADER_SIZE = struct.calcsize(WAV_FORMAT)


def records():
    with ARCHIVE.open(encoding="utf-8", errors="replace") as source:
        for line in source:
            if not line.startswith("{"):
                continue
            try:
                row = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if isinstance(row, dict):
                yield row


def manifest_ok(row):
    name = row.get("file")
    tx = row.get("transfer_id")
    crc = row.get("crc32")
    size = row.get("bytes")
    count = row.get("chunks")
    return (isinstance(name, str) and FILENAME.fullmatch(name) is not None
            and isinstance(tx, str) and TX.fullmatch(tx) is not None
            and isinstance(crc, str) and CRC.fullmatch(crc) is not None
            and type(size) is int and WAV_HEADER_SIZE < size <= MAX_SIZE
            and type(count) is int and count == (size + CHUNK - 1) // CHUNK)


def same_manifest(a, b):
    return all(a.get(k) == b.get(k)
               for k in ("file", "transfer_id", "crc32", "bytes", "chunks"))


def wav_ok(path, size):
    if size <= WAV_HEADER_SIZE:
        return False
    with path.open("rb") as source:
        blob = source.read(WAV_HEADER_SIZE)
    if len(blob) != WAV_HEADER_SIZE:
        return False
    (riff, length, wave, fmt, fmt_size, encoding, channels,
     rate, byte_rate, align, bits, data, data_bytes) = struct.unpack(
         WAV_FORMAT, blob
     )
    return (riff == b"RIFF" and wave == b"WAVE" and fmt == b"fmt "
            and data == b"data" and fmt_size == 16 and encoding == 1
            and channels == 1 and rate == 8000 and byte_rate == 16000
            and align == 2 and bits == 16
            and length == size - 8 and data_bytes == size - WAV_HEADER_SIZE
            and data_bytes % 2 == 0)


def crc32_file(path):
    crc = 0
    with path.open("rb") as source:
        while True:
            buf = source.read(65536)
            if not buf:
                break
            crc = zlib.crc32(buf, crc)
    return f"{crc:08x}"


def metadata_bytes(value, filename):
    if not isinstance(value, str) or not value:
        raise ValueError("recording metadata missing")
    if len(value) > ((MAX_META + 2) // 3) * 4 + 4:
        raise ValueError("oversized metadata")
    try:
        raw = base64.b64decode(value, validate=True)
        meta = json.loads(raw)
    except (ValueError, UnicodeError, binascii.Error) as error:
        raise ValueError("invalid recording metadata") from error
    if (len(raw) > MAX_META or not isinstance(meta, dict)
            or meta.get("record_type") != "audio_recording"
            or meta.get("file") != filename):
        raise ValueError("recording metadata/file mismatch")
    return raw


def save_metadata(path, raw):
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("existing metadata differs; left unchanged")
        return
    fd, tmp = tempfile.mkstemp(prefix=".audio_meta_", dir=str(METADATA))
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        if path.exists():
            raise ValueError("metadata path appeared during transfer")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def restore(done):
    name, tx = done["file"], done["transfer_id"]
    size, count = done["bytes"], done["chunks"]
    target = DEST / name

    begin = None
    for row in records():
        if row.get("transfer_id") == tx and row.get("record_type") == "audio_recording_begin":
            if begin is not None or not manifest_ok(row) or not same_manifest(row, done):
                raise ValueError("duplicate or invalid begin")
            begin = row
    if begin is None:
        raise ValueError("missing begin")
    meta = metadata_bytes(begin.get("metadata_b64"), name)

    if target.exists():
        if not (target.stat().st_size == size and
                crc32_file(target) == done["crc32"] and wav_ok(target, size)):
            raise ValueError("existing WAV differs; left unchanged")
        save_metadata(METADATA / name.replace(".wav", ".json"), meta)
        return "already-present"

    fd, tmp = tempfile.mkstemp(prefix=".audio_data_", dir=str(DEST))
    seen = set()
    complete = False
    try:
        with os.fdopen(fd, "wb") as out:
            for row in records():
                if row.get("transfer_id") != tx:
                    continue
                kind = row.get("record_type")
                if kind == "audio_recording_complete":
                    if not same_manifest(row, done):
                        raise ValueError("completion does not match begin")
                    complete = True
                elif kind == "audio_recording_chunk":
                    index = row.get("index")
                    if (row.get("file") != name or type(index) is not int
                            or index < 0 or index >= count or index in seen):
                        raise ValueError("invalid or duplicate chunk index")
                    encoded = row.get("data")
                    if not isinstance(encoded, str) or len(encoded) > 5472:
                        raise ValueError("invalid Base64 chunk size")
                    try:
                        binary = base64.b64decode(encoded, validate=True)
                    except binascii.Error as error:
                        raise ValueError("invalid Base64 data") from error
                    expected = min(CHUNK, size - index * CHUNK)
                    if len(binary) != expected:
                        raise ValueError("incorrect chunk size")
                    out.seek(index * CHUNK)
                    out.write(binary)
                    seen.add(index)
            out.flush()
            os.fsync(out.fileno())
        if not complete or len(seen) != count:
            raise ValueError("incomplete audio recording")
        staged = Path(tmp)
        if (staged.stat().st_size != size or
                crc32_file(staged) != done["crc32"] or not wav_ok(staged, size)):
            raise ValueError("WAV length, header, or CRC mismatch")
        if target.exists():
            raise ValueError("destination appeared during transfer")
        os.replace(tmp, target)
        tmp = None
        save_metadata(METADATA / name.replace(".wav", ".json"), meta)
        return "restored"
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)


def run():
    if not ARCHIVE.is_file():
        raise FileNotFoundError(f"missing upload archive: {ARCHIVE}")
    DEST.mkdir(mode=0o750, parents=True, exist_ok=True)
    METADATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (METADATA / ".receiver.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        completed = {}
        for row in records():
            if (row.get("record_type") == "audio_recording_complete"
                    and manifest_ok(row)):
                completed[row["transfer_id"]] = row
        totals = {"restored": 0, "already-present": 0, "failed": 0}
        for row in completed.values():
            try:
                state = restore(row)
                totals[state] += 1
                if state == "restored":
                    print(f"Audio recording restored: {row['file']}")
            except (OSError, ValueError, UnicodeError) as error:
                totals["failed"] += 1
                print(f"Audio {row['file']}: {error}", file=sys.stderr)
        print(json.dumps(totals))
        return 1 if totals["failed"] else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (OSError, ValueError) as error:
        print(f"Audio recording receiver: {error}", file=sys.stderr)
        sys.exit(1)
