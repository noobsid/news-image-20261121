#!/usr/bin/env python3
"""Deliver the entry image for make.fun's news-image-20261121.

The picture itself, entry.png, sits next to this file: a one-page
broadsheet that sums up Saturday 21 November 2026 (Iran's Bahrain
strikes, the Kryvyi Rih missile, Wall Street's AI correction, and
33 more stories). render.py drew it ahead of time; this program's
whole job is to place a byte-identical copy where the grader looks,
at $MAKEFUN_OUTPUT_DIR/entry.png, or /output/entry.png when the
variable is unset. Standard library only, no network, and the same
bytes come out on every run.
"""

import os
from pathlib import Path

IMAGE_BYTES = (Path(__file__).resolve().parent / "entry.png").read_bytes()


def deliver() -> Path:
    target_dir = Path(os.getenv("MAKEFUN_OUTPUT_DIR", "/output"))
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "entry.png"
    target.write_bytes(IMAGE_BYTES)
    return target


if __name__ == "__main__":
    deliver()
