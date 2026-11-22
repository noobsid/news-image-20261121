#!/usr/bin/env python3
"""news-image-20261121 entry program (Python 3.13, standard library only).

The entry image is entry.png beside this file: a broadsheet front page
summing up the world news of Saturday 21 November 2026, rendered by
render.py from researched, attributed stories. This program copies that
image, byte for byte, to /output/entry.png. It uses no network, reads
nothing else, and two runs always write identical bytes.

Outside the grader's container, MAKEFUN_OUTPUT_DIR stands in for /output:
    mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "entry.png"


def main() -> None:
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, out_dir / "entry.png")


if __name__ == "__main__":
    main()
