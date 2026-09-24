"""Draws placeholder persona art until the Aseprite sheets land (Phase 7). Stdlib only.

personas/<slug>/assets/sprite.png   160x32: five 32x32 frames idle, talk, happy, concerned, sleep
personas/<slug>/assets/portrait.png 16x16 head crop of the idle frame
"""

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "personas"
STATES = ["idle", "talk", "happy", "concerned", "sleep"]
INK = (0x1B, 0x1A, 0x2E, 255)
SKIN = (0xE8, 0xB9, 0x8F, 255)
WHITE = (0xED, 0xE9, 0xDC, 255)
CLEAR = (0, 0, 0, 0)

PERSONAS = {
    "coach": {"accent": "#e0623a", "hair": (0x5A, 0x3A, 0x22, 255), "hat": "headband"},
    "teacher": {"accent": "#4a8fd6", "hair": (0x3A, 0x2A, 0x1A, 255), "hat": "glasses"},
    "mom": {"accent": "#e6b84a", "hair": (0x8A, 0x4A, 0x2A, 255), "hat": "bun"},
    "quartermaster": {"accent": "#7fa08a", "hair": (0x4A, 0x4A, 0x4A, 255), "hat": "beret"},
}


def rgba(hex_: str) -> tuple[int, int, int, int]:
    return (int(hex_[1:3], 16), int(hex_[3:5], 16), int(hex_[5:7], 16), 255)


def shade(c, f):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f), 255)


class Canvas:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.px = [[CLEAR] * w for _ in range(h)]

    def rect(self, x0, y0, x1, y1, c):  # inclusive
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            for x in range(max(0, x0), min(self.w, x1 + 1)):
                self.px[y][x] = c

    def dot(self, x, y, c):
        self.rect(x, y, x, y, c)

    def outline(self):
        solid = [[p[3] > 0 for p in row] for row in self.px]
        for y in range(self.h):
            for x in range(self.w):
                if solid[y][x]:
                    continue
                near = any(
                    0 <= y + dy < self.h and 0 <= x + dx < self.w and solid[y + dy][x + dx]
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                )
                if near:
                    self.px[y][x] = INK

    def png(self) -> bytes:
        raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in self.px)

        def chunk(tag, data):
            return (
                struct.pack(">I", len(data))
                + tag
                + data
                + struct.pack(">I", zlib.crc32(tag + data))
            )

        ihdr = struct.pack(">IIBBBBB", self.w, self.h, 8, 6, 0, 0, 0)
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b"")
        )


def frame(p: dict, state: str) -> Canvas:
    c = Canvas(32, 32)
    accent = rgba(p["accent"])
    bob = 1 if state == "sleep" else 0
    # body + arms
    c.rect(9, 21 + bob, 22, 30, accent)
    c.rect(9, 27, 22, 30, shade(accent, 0.75))
    c.rect(7, 22 + bob, 8, 27, accent)
    c.rect(23, 22 + bob, 24, 27, accent)
    if state == "happy":  # arms up
        c.rect(7, 16, 8, 22, accent)
        c.rect(23, 16, 24, 22, accent)
    # head + hair
    y = 7 + bob
    c.rect(10, y, 21, y + 12, SKIN)
    c.rect(10, y, 21, y + 2, p["hair"])
    c.rect(10, y + 3, 10, y + 6, p["hair"])
    c.rect(21, y + 3, 21, y + 6, p["hair"])
    # eyes
    ey = y + 6
    if state == "sleep":
        c.rect(12, ey + 1, 14, ey + 1, INK)
        c.rect(17, ey + 1, 19, ey + 1, INK)
        c.rect(25, 2, 28, 2, WHITE), c.dot(27, 3, WHITE), c.dot(26, 4, WHITE)
        c.rect(25, 5, 28, 5, WHITE)
    elif state == "happy":
        c.dot(12, ey + 1, INK), c.dot(13, ey, INK), c.dot(14, ey + 1, INK)
        c.dot(17, ey + 1, INK), c.dot(18, ey, INK), c.dot(19, ey + 1, INK)
    else:
        c.rect(13, ey, 14, ey + 1, INK)
        c.rect(17, ey, 18, ey + 1, INK)
    if state == "concerned":
        # brows raised in the middle = worried, not angry
        c.dot(12, ey - 1, INK), c.dot(13, ey - 2, INK)
        c.dot(19, ey - 1, INK), c.dot(18, ey - 2, INK)
    # mouth
    my = y + 10
    if state == "talk":
        c.rect(15, my - 1, 16, my, INK)
    elif state == "happy":
        c.rect(14, my - 1, 17, my - 1, INK), c.dot(13, my - 2, INK), c.dot(18, my - 2, INK)
    elif state == "concerned":
        c.rect(14, my, 17, my, INK), c.dot(13, my + 1, INK), c.dot(18, my + 1, INK)
    elif state == "idle":
        c.rect(14, my, 17, my, INK)
    # persona mark
    hat = p["hat"]
    if hat == "headband":
        c.rect(10, y + 3, 21, y + 3, accent)
        c.rect(14, 22 + bob, 17, 22 + bob, WHITE)  # whistle cord
    elif hat == "glasses":  # half-rim readers: lower rims, bridge, temples
        c.rect(12, ey + 2, 14, ey + 2, INK), c.rect(17, ey + 2, 19, ey + 2, INK)
        c.rect(15, ey, 16, ey, INK)
        c.dot(11, ey, INK), c.dot(20, ey, INK)
    elif hat == "bun":
        c.rect(13, y - 3, 18, y - 1, p["hair"])
    elif hat == "beret":
        c.rect(9, y - 2, 20, y, accent)
        c.dot(19, y - 3, accent)
    c.outline()
    return c


def main() -> None:
    for slug, p in PERSONAS.items():
        sheet = Canvas(32 * len(STATES), 32)
        for i, state in enumerate(STATES):
            f = frame(p, state)
            for y in range(32):
                sheet.px[y][i * 32 : (i + 1) * 32] = f.px[y]
        idle = frame(p, "idle")
        portrait = Canvas(16, 16)
        portrait.px = [row[8:24] for row in idle.px[3:19]]
        out = ROOT / slug / "assets"
        out.mkdir(parents=True, exist_ok=True)
        (out / "sprite.png").write_bytes(sheet.png())
        (out / "portrait.png").write_bytes(portrait.png())


if __name__ == "__main__":
    main()
