"""Writes placeholder PWA icons: a quest-giver "!" on the ground colour, 16x16 pixel art
scaled with nearest-neighbour. Stdlib only. Replace with Aseprite art in Phase 7."""

import struct
import zlib
from pathlib import Path

GROUND = (0x1B, 0x1A, 0x2E)
PANEL = (0x2A, 0x27, 0x40)
BORDER = (0x5A, 0x55, 0x80)
GOLD = (0xE6, 0xB8, 0x4A)
SHADOW = (0x8A, 0x6A, 0x2A)

# 16x16: . ground, p panel, b border, g gold, s shadow
ART = [
    "................",
    "................",
    "..bbbbbbbbbbbb..",
    "..bppppppppppb..",
    "..bpppppggpppb..",
    "..bpppppggsppb..",
    "..bpppppggsppb..",
    "..bpppppggsppb..",
    "..bpppppggsppb..",
    "..bppppppssppb..",
    "..bpppppggpppb..",
    "..bpppppggsppb..",
    "..bppppppssppb..",
    "..bbbbbbbbbbbb..",
    "................",
    "................",
]
COLORS = {".": GROUND, "p": PANEL, "b": BORDER, "g": GOLD, "s": SHADOW}


def png(size: int) -> bytes:
    scale = size // 16
    rows = []
    for y in range(size):
        line = ART[min(y // scale, 15)]
        pixels = b"".join(bytes(COLORS[line[min(x // scale, 15)]]) for x in range(size))
        rows.append(b"\x00" + pixels)
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


out = Path(__file__).resolve().parent.parent / "public" / "icons"
out.mkdir(parents=True, exist_ok=True)
for name, size in {"icon-192.png": 192, "icon-512.png": 512, "apple-touch-icon.png": 176}.items():
    (out / name).write_bytes(png(size))
