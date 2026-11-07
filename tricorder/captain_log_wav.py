#!/usr/bin/env python3
"""Decode private TR-460 Captain's Log .adp files into authenticated HA Media WAV.

Matches Rev100 MaTouch playback: each 88-byte packet contains the sequence,
initial signed-16 predictor, IMA index, and 159 low-nibble-first ADPCM codes.
The 32-byte TRCAP01 container is NOT a standard WAV file.
"""
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import wave

SOURCE = Path(os.environ.get("TRICORDER_CAPTAINS_DIR", "/config/tricorder/captains"))
OUTPUT = Path(os.environ.get("TRICORDER_CAPTAINS_MEDIA_DIR", "/media/tricorder_captains"))
FILE = re.compile(r"captain_[0-9]{8}\.adp\Z")
HEADER = struct.Struct("<8sHHIIHHII")
PACKET = struct.Struct("<IhBB80s")
STEPS = (
    7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,
    55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,
    279,307,337,371,408,449,494,544,598,658,724,796,876,963,1060,
    1166,1282,1411,1552,1707,1878,2066,2272,2499,2749,3024,3327,
    3660,4026,4428,4871,5358,5894,6484,7132,7845,8630,9493,10442,
    11487,12635,13899,15289,16818,18500,20350,22385,24623,27086,
    29794,32767
)
INDEX_DELTA = (-1,-1,-1,-1,2,4,6,8)
MAX_WAV_BYTES = 32 * 1024 * 1024
SILENCE = bytes(320)

def unpack_packet(data):
    seq, pred, index, reserved, codes = PACKET.unpack(data)
    if index > 88 or reserved:
        raise ValueError("invalid ADPCM packet")
    out = bytearray(320)
    struct.pack_into("<h", out, 0, pred)
    for i in range(159):
        octet = codes[i//2]
        code = (octet >> 4) if i & 1 else octet & 15
        step = STEPS[index]
        change = (step >> 3) + (step >> 2 if code & 1 else 0)
        change += (step >> 1) if code & 2 else 0
        change += step if code & 4 else 0
        pred = max(-32768, min(32767, pred + (-change if code & 8 else change)))
        index = max(0, min(88, index + INDEX_DELTA[code & 7]))
        struct.pack_into("<h", out, (i+1)*2, pred)
    return seq, out

def convert(source_path):
    if not FILE.fullmatch(source_path.name):
        raise ValueError("invalid filename")
    dest = OUTPUT / (source_path.stem + ".wav")
    with source_path.open("rb") as source:
        header = source.read(HEADER.size)
        if len(header) != HEADER.size:
            raise ValueError("truncated Captain's Log header")
        magic, version, head_size, rate, epoch, samples, packet_size, count, duration = HEADER.unpack(header)
        if (magic != b"TRCAP01\x00" or version != 1 or head_size != 32 or rate != 8000
                or samples != 160 or packet_size != 88 or count < 1
                or source_path.stat().st_size != 32 + count * 88
                or source_path.stat().st_size > 3 * 1024 * 1024):
            raise ValueError("invalid Captain's Log header")
        if dest.is_file():
            with wave.open(str(dest), "rb") as w:
                if (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1,2,8000) and w.getnframes():
                    return "already-present"
            raise ValueError("invalid existing WAV; kept untouched")
        OUTPUT.mkdir(mode=0o750, parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".capt_", dir=str(OUTPUT))
        os.close(fd)
        try:
            frames = 0
            previous = None
            with wave.open(tmp, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(8000)
                for _ in range(count):
                    packet = source.read(PACKET.size)
                    if len(packet) != PACKET.size:
                        raise ValueError("truncated Captain's Log packet")
                    seq, pcm = unpack_packet(packet)
                    if previous is not None:
                        if seq <= previous:
                            raise ValueError("non-increasing packet sequence")
                        gap = min(seq - previous - 1, 40)
                        if gap:
                            if (frames + gap*160)*2 > MAX_WAV_BYTES:
                                raise ValueError("WAV exceeds maximum size")
                            wav.writeframesraw(SILENCE * gap)
                            frames += gap*160
                    if (frames + 160)*2 > MAX_WAV_BYTES:
                        raise ValueError("WAV exceeds maximum size")
                    wav.writeframesraw(pcm)
                    frames += 160
                    previous = seq
            os.replace(tmp, dest)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    return "converted"

def convert_all():
    if not SOURCE.is_dir():
        raise FileNotFoundError("Captain's Log archive missing: " + str(SOURCE))
    tally = {"converted":0, "already-present":0, "failed":0}
    for source in sorted(SOURCE.iterdir()):
        if not source.is_file() or not FILE.fullmatch(source.name):
            continue
        try:
            tally[convert(source)] += 1
        except (OSError, ValueError, EOFError, wave.Error) as error:
            tally["failed"] += 1
            print(f"Captain's Log {source.name}: {error}", file=sys.stderr)
    return tally

if __name__ == "__main__":
    result = convert_all()
    print(json.dumps(result))
    sys.exit(1 if result["failed"] else 0)
