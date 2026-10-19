#!/usr/bin/env python3
"""Render archived TR-460 thermal snapshots into browsable PNG files.

A 32x24 deci-Celsius temperature grid is preserved in the private JSONL
archive; this script only generates 320x205 presentation images. Stdlib only.
Called after Home Assistant's File notifier has appended a thermal_snapshot.
"""
import json
import os
import re
import struct
import sys
import tempfile
import zlib

ARCHIVE = os.environ.get(
    "TRICORDER_ARCHIVE_PATH", "/config/tricorder/tricorder_uploads.jsonl"
)
OUT = os.environ.get(
    "TRICORDER_THERMAL_IMAGE_DIR", "/config/www/tricorder_thermal"
)
W, H = 320, 205
VALID_NAME = re.compile(r"^thermal_distance_[0-9]{8}\.jsonl$")

# Tiny 5x7 font for overlay text, removing the need for Pillow dependencies.
FONT = {
    " ": ["00000"] * 7,
    "0": ["01110","10001","10011","10101","11001","10001","01110"],
    "1": ["00100","01100","00100","00100","00100","00100","01110"],
    "2": ["01110","10001","00001","00010","00100","01000","11111"],
    "3": ["11110","00001","00001","01110","00001","00001","11110"],
    "4": ["00010","00110","01010","10010","11111","00010","00010"],
    "5": ["11111","10000","10000","11110","00001","00001","11110"],
    "6": ["00110","01000","10000","11110","10001","10001","01110"],
    "7": ["11111","00001","00010","00100","01000","01000","01000"],
    "8": ["01110","10001","10001","01110","10001","10001","01110"],
    "9": ["01110","10001","10001","01111","00001","00010","01100"],
    "A": ["01110","10001","10001","11111","10001","10001","10001"],
    "B": ["11110","10001","10001","11110","10001","10001","11110"],
    "C": ["01111","10000","10000","10000","10000","10000","01111"],
    "D": ["11110","10001","10001","10001","10001","10001","11110"],
    "E": ["11111","10000","10000","11110","10000","10000","11111"],
    "F": ["11111","10000","10000","11110","10000","10000","10000"],
    "G": ["01111","10000","10000","10111","10001","10001","01111"],
    "H": ["10001","10001","10001","11111","10001","10001","10001"],
    "I": ["01110","00100","00100","00100","00100","00100","01110"],
    "L": ["10000","10000","10000","10000","10000","10000","11111"],
    "M": ["10001","11011","10101","10101","10001","10001","10001"],
    "N": ["10001","11001","10101","10011","10001","10001","10001"],
    "O": ["01110","10001","10001","10001","10001","10001","01110"],
    "P": ["11110","10001","10001","11110","10000","10000","10000"],
    "R": ["11110","10001","10001","11110","10100","10010","10001"],
    "S": ["01111","10000","10000","01110","00001","00001","11110"],
    "T": ["11111","00100","00100","00100","00100","00100","00100"],
    "U": ["10001","10001","10001","10001","10001","10001","01110"],
    "V": ["10001","10001","10001","10001","10001","01010","00100"],
    "W": ["10001","10001","10001","10101","10101","10101","01010"],
    "X": ["10001","10001","01010","00100","01010","10001","10001"],
    "Y": ["10001","10001","01010","00100","00100","00100","00100"],
    "-": ["00000","00000","00000","11111","00000","00000","00000"],
    ".": ["00000","00000","00000","00000","00000","00110","00110"],
    ":": ["00000","00100","00100","00000","00100","00100","00000"],
    "/": ["00001","00001","00010","00100","01000","10000","10000"],
}
def rgb_for(level):
    v = max(0, min(255, level))
    if v < 64:
        r, g, b = 0, 2*v, 90+2*v
    elif v < 128:
        d = v-64
        r, g, b = 0, 128+2*d, 218-d
    elif v < 192:
        d = v-128
        r, g, b = 4*d, 255, 154-2*d
    else:
        d = v-192
        r, g, b = 255, 255-4*d, 26-d//3
    return tuple(max(0, min(255, c)) for c in (r, g, b))

def put(img, x, y, color):
    if 0 <= x < W and 0 <= y < H:
        at = (y*W+x)*3
        img[at:at+3] = bytes(color)

def text(img, x, y, text_value, color=(185, 225, 205)):
    for ch in text_value.upper():
        glyph = FONT.get(ch, FONT[" "])
        for dy, row in enumerate(glyph):
            for dx, pixel in enumerate(row):
                if pixel == "1":
                    put(img, x+dx, y+dy, color)
        x += 6

def png_bytes(rgb):
    # RGB8 PNG, filter=0; no image library needed on HA.
    raw = b"".join(b"\0"+rgb[y*W*3:(y+1)*W*3] for y in range(H))
    def chunk(name, data):
        return (struct.pack(">I", len(data))+name+data+
                struct.pack(">I", zlib.crc32(name+data)&0xffffffff))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", W,H,8,2,0,0,0)) +
            chunk(b"IDAT", zlib.compress(raw, 6)) +
            chunk(b"IEND", b""))

def render(record):
    pixels = record.get("pixels")
    if (record.get("record_type") != "thermal_snapshot" or
        record.get("width") != 32 or record.get("height") != 24 or
        record.get("unit") != "deci_c" or not isinstance(pixels, list) or
        len(pixels) != 768 or any(type(p) is not int or p < -32768 or p > 32767
                                 for p in pixels)):
        return None
    archive_file = record.get("archive_file", "")
    if not isinstance(archive_file, str) or not VALID_NAME.fullmatch(archive_file):
        return None

    img = bytearray(W*H*3)
    values = [p for p in pixels if p != -32768]
    if not values:
        return None
    low, high = min(values), max(values)
    span = max(20, high-low)
    base = low - (span-(high-low))//2
    for iy in range(24):
        for ix in range(32):
            value = pixels[iy*32+ix]
            color = (96,96,96) if value == -32768 else rgb_for(
                ((value-base)*255)//span
            )
            for y in range(39+iy*5, 39+iy*5+5):
                off = (y*W+32+ix*8)*3
                img[off:off+24] = bytes(color)*8
    # The MaTouch's centered thermal-image crosshair.
    for x in range(155, 165):
        put(img, x, 99, (242,242,242))
    for y in range(95,104):
        put(img, 159, y, (242,242,242))

    text(img, 12, 16, "THERMAL IMAGE", (180,221,204))
    center = record.get("center_c")
    if not isinstance(center,(int,float)):center = pixels[12*32+16]/10.0
    readout = "MIN %.1fC  CENTER %.1fC  MAX %.1fC" % (
        low/10.0, float(center), high/10.0
    )
    text(img, 12, 168, readout[:49], (180,221,204))
    distance = record.get("range_m")
    text(img, 12, 189,
         "RANGE %.2fM" % float(distance) if isinstance(distance,(int,float))
         else "RANGE --", (180,221,204))
    return archive_file.replace(".jsonl",".png"), png_bytes(img)

def atomic_write(path, data):
    fd,tmp = tempfile.mkstemp(prefix=".tric_",dir=os.path.dirname(path))
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main():
    os.makedirs(OUT, exist_ok=True)
    index = {}
    newest = None
    try:
        with open(ARCHIVE,encoding="utf-8") as source:
            for line in source:
                if '"thermal_snapshot"' not in line:
                    continue
                try:record = json.loads(line)
                except (ValueError,TypeError):continue
                result = render(record)
                if result is None:continue
                name, data = result
                target=os.path.join(OUT,name)
                if not os.path.exists(target):
                    atomic_write(target,data)
                newest=(record,name,data)
                index[record["archive_file"]]={
                    "time":record.get("time",""),
                    "mission_file":record.get("mission_file",""),
                    "image":"/local/tricorder_thermal/"+name,
                }
    except FileNotFoundError:
        return 0
    if newest is None:
        return 0
    record,name,data=newest
    atomic_write(os.path.join(OUT,"latest.png"),data)
    atomic_write(os.path.join(OUT,"index.json"),
                 json.dumps({"latest":index[record["archive_file"]],
                             "snapshots":index},separators=(",",":")).encode())
    return 0

if __name__ == "__main__":
    sys.exit(main())
