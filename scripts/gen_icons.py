"""Generate the PWA PNG icons (solid brand square with a white 'r') without any
image library — writes minimal true-color PNGs by hand."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

BRAND = (16, 185, 129)  # #10b981
WHITE = (255, 255, 255)

# 4x7 bitmap of a chunky lowercase-style "r"
GLYPH = [
    "1110",
    "1001",
    "1001",
    "1110",
    "1010",
    "1001",
    "1001",
]


def make_png(size: int, path: Path) -> None:
    pixels = [[BRAND for _ in range(size)] for _ in range(size)]
    scale = size // 12
    gw, gh = 4 * scale, 7 * scale
    ox, oy = (size - gw) // 2, (size - gh) // 2
    for gy, row in enumerate(GLYPH):
        for gx, bit in enumerate(row):
            if bit == "1":
                for yy in range(scale):
                    for xx in range(scale):
                        pixels[oy + gy * scale + yy][ox + gx * scale + xx] = WHITE

    raw = b"".join(b"\x00" + b"".join(bytes(c) for c in row) for row in pixels)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    print(f"wrote {path} ({len(png)} bytes)")


if __name__ == "__main__":
    public = Path(__file__).resolve().parents[1] / "frontend" / "public"
    make_png(192, public / "icon-192.png")
    make_png(512, public / "icon-512.png")
