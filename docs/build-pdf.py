#!/usr/bin/env python3
"""Render docs/indicator-reference.html to a self-contained PDF.

Persian text needs a font that actually ships the glyphs, and a PDF that
depends on whatever is installed on the reader's machine is not portable.
So the Vazirmatn TTFs are inlined as base64 @font-face rules before the page
is handed to headless Chromium.

    python3 docs/build-pdf.py --font-dir /path/to/vazirmatn/ttf

Chromium comes from Playwright. On this container it lives under
/opt/pw-browsers; elsewhere Playwright's own lookup is used.
"""

from __future__ import annotations

import argparse
import base64
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_HTML = os.path.join(HERE, "indicator-reference.html")
DEFAULT_PDF = os.path.join(HERE, "M_Plus-Indicator-Reference.pdf")

# Chromium builds Playwright may have unpacked, newest first.
CHROMIUM_GLOBS = [
    "/opt/pw-browsers/chromium-*/chrome-linux/chrome",
    "/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell",
]


def find_chromium() -> str | None:
    for pattern in CHROMIUM_GLOBS:
        hits = sorted(glob.glob(pattern), reverse=True)
        if hits:
            return hits[0]
    return None


def font_face_css(font_dir: str) -> str:
    """Build @font-face rules with the TTFs inlined as data URIs."""
    wanted = {"Vazirmatn-Regular.ttf": 400, "Vazirmatn-Bold.ttf": 700}
    rules = []

    for name, weight in wanted.items():
        matches = glob.glob(os.path.join(font_dir, "**", name), recursive=True)
        if not matches:
            print(f"  ! {name} not found under {font_dir}", file=sys.stderr)
            continue
        with open(matches[0], "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        rules.append(
            "@font-face{font-family:'Vazirmatn';"
            f"src:url(data:font/ttf;base64,{b64}) format('truetype');"
            f"font-weight:{weight};font-style:normal;font-display:block;}}"
        )
        print(f"  + embedded {name} ({len(b64) // 1024} KB base64)")

    return "<style>" + "".join(rules) + "</style>"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default=DEFAULT_HTML)
    ap.add_argument("--out", default=DEFAULT_PDF)
    ap.add_argument("--font-dir", default="", help="directory holding Vazirmatn TTFs")
    args = ap.parse_args()

    with open(args.html, encoding="utf-8") as fh:
        html = fh.read()

    if args.font_dir:
        css = font_face_css(args.font_dir)
        if "</head>" not in html:
            print("! no </head> in the HTML, cannot inject fonts", file=sys.stderr)
            return 1
        html = html.replace("</head>", css + "</head>")
    else:
        print("  no --font-dir given, relying on system fonts")

    from playwright.sync_api import sync_playwright

    launch_kwargs = {}
    chromium = find_chromium()
    if chromium:
        launch_kwargs["executable_path"] = chromium
        print(f"  chromium: {chromium}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_kwargs)
        page = browser.new_page()
        page.set_content(html, wait_until="load")
        page.emulate_media(media="print")
        page.pdf(
            path=args.out,
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template="<div></div>",
            footer_template=(
                "<div style='width:100%;font-size:7pt;color:#8894a0;"
                "padding:0 14mm;font-family:sans-serif;text-align:center'>"
                "M+ FVG Engulf — Indicator Reference &nbsp;·&nbsp; "
                "<span class='pageNumber'></span> / <span class='totalPages'></span>"
                "</div>"
            ),
            margin={"top": "14mm", "bottom": "16mm", "left": "12mm", "right": "12mm"},
        )
        browser.close()

    print(f"  wrote {args.out} ({os.path.getsize(args.out) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
