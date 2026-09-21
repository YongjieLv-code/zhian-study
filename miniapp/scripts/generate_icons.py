"""Generate native tab-bar PNGs using only Python's standard library."""
import binascii
import math
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1] / "src" / "static" / "tabs"

def segments(points):
    return list(zip(points, points[1:]))

shapes = {
    "today": (segments([(12, 6), (9, 4), (3, 4), (3, 19), (9, 19), (12, 21), (15, 19), (21, 19), (21, 4), (15, 4), (12, 6), (12, 21)]), []),
    "plans": (segments([(5, 5), (20, 5), (20, 21), (4, 21), (4, 5), (5, 5)]) + segments([(8, 3), (8, 7)]) + segments([(16, 3), (16, 7)]) + segments([(4, 10), (20, 10)]) + segments([(8, 15), (11, 18), (16, 13)]), []),
    "reviews": (segments([(19, 9), (21, 9), (21, 3)]) + segments([(5, 15), (3, 15), (3, 21)]), [(12, 12, 8, 190, 330), (12, 12, 8, 10, 150)]),
    "stats": (segments([(4, 3), (4, 21), (22, 21)]) + segments([(9, 16), (9, 11)]) + segments([(14, 16), (14, 5)]) + segments([(19, 16), (19, 8)]), []),
    "mine": (segments([(4, 21), (4, 19), (6, 16), (10, 15), (14, 15), (18, 16), (20, 19), (20, 21)]), [(12, 7, 4, 0, 360)]),
}

def distance_to_line(x, y, segment):
    (ax, ay), (bx, by) = segment
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / length)) if length else 0
    return math.hypot(x - ax - t * dx, y - ay - t * dy)

def inside(x, y, lines, circles):
    if any(distance_to_line(x, y, line) < .85 for line in lines):
        return True
    for cx, cy, radius, start, end in circles:
        angle = math.degrees(math.atan2(y - cy, x - cx)) % 360
        if start <= angle <= end and abs(math.hypot(x - cx, y - cy) - radius) < .85:
            return True
    return False

def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xffffffff)

def generate():
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, (lines, circles) in shapes.items():
        for suffix, color in [("", (135, 145, 128)), ("-active", (69, 99, 76))]:
            raw = bytearray()
            for py in range(72):
                raw.append(0)
                for px in range(72):
                    coverage = sum(inside((px + dx) / 3, (py + dy) / 3, lines, circles) for dx in (.25, .75) for dy in (.25, .75))
                    raw.extend((*color, round(255 * coverage / 4)))
            data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 72, 72, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b"")
            (ROOT / f"{name}{suffix}.png").write_bytes(data)
    print("Generated 10 tab-bar icons")

if __name__ == "__main__":
    generate()
