#!/usr/bin/env python3
"""Render docs/bedienungsanleitung.md to a print-ready PDF.

Pipeline: pandoc (markdown -> HTML fragment) -> a styled standalone HTML ->
headless Chromium (-> PDF). Needs `pandoc` and a Chromium/Chrome on PATH; both
are dev-machine tools (the Pi does not need them). Run: `make manual` or
`python tools/build_manual_pdf.py`.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "bedienungsanleitung.md"
PDF = ROOT / "docs" / "bedienungsanleitung.pdf"
TMP_HTML = ROOT / "docs" / "_manual.html"  # under $HOME so snap Chromium can read it

CSS = """
@page { size: A4; margin: 19mm 16mm 16mm; }
* { box-sizing: border-box; }
body { font-family: "DejaVu Sans","Liberation Sans",Arial,sans-serif;
       font-size: 10.5pt; line-height: 1.5; color: #1b1b1b; }
h1 { font-size: 23pt; color: #7a1628; margin: 0 0 4pt; letter-spacing: .2pt; }
h2 { font-size: 14pt; color: #7a1628; border-bottom: 1.4pt solid #e3ccd0;
     padding-bottom: 3pt; margin: 17pt 0 8pt; page-break-after: avoid; }
h3 { font-size: 11.5pt; color: #333; margin: 12pt 0 4pt; page-break-after: avoid; }
p { margin: 0 0 6pt; }
ul, ol { margin: 0 0 7pt; padding-left: 17pt; }
li { margin: 2.5pt 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 11pt;
        font-size: 9.7pt; page-break-inside: auto; }
th, td { border: .6pt solid #cdb9bd; padding: 4pt 6pt; text-align: left; vertical-align: top; }
th { background: #7a1628; color: #fff; font-weight: 600; }
tr:nth-child(even) td { background: #faf5f6; }
tr { page-break-inside: avoid; }
code { font-family: "DejaVu Sans Mono","Liberation Mono",monospace; font-size: 8.8pt;
       background: #f1ecee; padding: .5pt 3pt; border-radius: 2pt; }
blockquote { border-left: 2.5pt solid #d4bcc1; margin: 6pt 0; padding: 1pt 0 1pt 10pt;
             color: #444; font-style: italic; }
strong { color: #111; }
a { color: #7a1628; text-decoration: none; }
hr { border: none; border-top: .6pt solid #ddd; margin: 12pt 0; }
"""

CHROMIUM_NAMES = ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome"]


def _find(names: list[str]) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def main() -> int:
    pandoc = shutil.which("pandoc")
    chromium = _find(CHROMIUM_NAMES)
    if pandoc is None:
        print("Fehler: 'pandoc' nicht gefunden (bitte installieren).", file=sys.stderr)
        return 1
    if chromium is None:
        print(
            "Fehler: kein Chromium/Chrome gefunden (chromium, google-chrome, …).",
            file=sys.stderr,
        )
        return 1
    if not SRC.exists():
        print(f"Fehler: {SRC} fehlt.", file=sys.stderr)
        return 1

    body = subprocess.run(
        [pandoc, str(SRC), "-t", "html5"], capture_output=True, text=True, check=True
    ).stdout
    TMP_HTML.write_text(
        "<!doctype html><html lang='de'><head><meta charset='utf-8'>"
        f"<style>{CSS}</style></head><body>{body}</body></html>",
        encoding="utf-8",
    )
    try:
        subprocess.run(
            [
                chromium,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={PDF}",
                TMP_HTML.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
    finally:
        TMP_HTML.unlink(missing_ok=True)
    print(f"PDF erstellt: {PDF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
