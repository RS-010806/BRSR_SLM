"""Builds the list of ordinary English words used to tell a word from a company name.

A word the linker does not recognise may be a company that is not covered ("zyxcorp emissions"), or it may just be
an ordinary word ("smaller peers"). The list lets the parser tell the two apart without guessing.

Run once on a machine that has /usr/share/dict/words; the output is committed with the other artifacts.
"""
from __future__ import annotations

import gzip
import re
from pathlib import Path

SRC = Path("/usr/share/dict/words")
OUT = Path(__file__).resolve().parents[1] / "server" / "pramana" / "nlu" / "artifacts" / "english.txt.gz"


def main():
    words = sorted({w.strip().lower() for w in SRC.read_text().splitlines() if re.fullmatch(r"[A-Za-z]{3,12}", w.strip())})
    with gzip.GzipFile(OUT, "wb", compresslevel=9, mtime=0) as f:        # mtime=0 keeps the file byte-identical between runs
        f.write("\n".join(words).encode())
    print(f"{len(words)} words -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
