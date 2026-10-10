#!/usr/bin/env python3
"""Make the preview pictures: <slug>/card.jpg (1200x630, used by link previews and the home page's
opening picture) and <slug>/thumb.webp (640x336, used by the home page grid), plus card.jpg for the
home page itself.

usage: python3 tools/shots.py [--all] [--fonts DIR] [slug ...]

With no slugs, pictures are made for pages that have none; --all remakes every one.

Needs Python with playwright and Pillow, and a Chromium that playwright can find.
The pages load their typefaces from Google Fonts. Where that is not reachable, pass
--fonts DIR with DIR being node_modules/@fontsource after `npm i @fontsource/<family> ...`,
and the pictures are made with those local copies; without it they fall back to system fonts.
"""
import glob
import io
import json
import os
import re
import sys
import urllib.parse

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RANGES = {
    "latin": "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
    "latin-ext": "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF",
    "greek": "U+0370-0377,U+037A-037F,U+0384-038A,U+038C,U+038E-03A1,U+03A3-03FF",
}
SKIP = ("cyrillic", "cyrillic-ext", "greek-ext", "vietnamese")


def font_css(fonts_dir, query):
    """Stand-in for the Google Fonts stylesheet, built from local @fontsource packages.

    A family's variable package (@fontsource-variable/<family>) is used when present, so width and
    optical-size settings behave as they do with the real stylesheet.
    """
    out = []
    for fam in urllib.parse.parse_qs(query).get("family", []):
        name = fam.split(":")[0]
        pkg = name.lower().replace(" ", "-")
        var = os.path.join(os.path.dirname(fonts_dir), "@fontsource-variable", pkg, "files")
        found = []  # (subset, weight or None for variable, style, url)
        for kind in ("full", "standard", "wght"):
            for f in sorted(glob.glob(os.path.join(var, f"{pkg}-*-{kind}-*.woff2"))):
                m = re.match(rf"{re.escape(pkg)}-(.+)-{kind}-(normal|italic)\.woff2$", os.path.basename(f))
                if m:
                    found.append((m.group(1), None, m.group(2), f"https://fonts.local/v/{pkg}/{os.path.basename(f)}"))
            if found:
                break
        if not found:
            for f in sorted(glob.glob(os.path.join(fonts_dir, pkg, "files", "*.woff2"))):
                m = re.match(rf"{re.escape(pkg)}-(.+)-(\d+)-(normal|italic)\.woff2$", os.path.basename(f))
                if m:
                    found.append((m.group(1), m.group(2), m.group(3), f"https://fonts.local/s/{pkg}/{os.path.basename(f)}"))
        faces = []
        for sub, weight, style, url in found:
            if sub in SKIP:
                continue
            span = f"font-weight:{weight};" if weight else "font-weight:1 1000;font-stretch:25% 151%;"
            rng = f"unicode-range:{RANGES[sub]};" if sub in RANGES else ""
            order = {"latin": 2, "latin-ext": 1}.get(sub, 0)
            faces.append((order, f'@font-face{{font-family:"{name}";font-style:{style};{span}{rng}src:url({url}) format("woff2")}}'))
        out += [css for _, css in sorted(faces, key=lambda t: t[0])]
    return "\n".join(out)


def main():
    args = sys.argv[1:]
    fonts_dir = None
    if "--fonts" in args:
        i = args.index("--fonts")
        fonts_dir = os.path.abspath(args[i + 1])
        del args[i:i + 2]
    every = "--all" in args
    wanted = [a for a in args if not a.startswith("--")]
    cat = json.load(open(os.path.join(ROOT, "tools", "catalog.json"), encoding="utf8"))
    slugs = [p["slug"] for s in cat["sections"] for p in s["pages"]]
    todo = wanted or [s for s in slugs if every or not os.path.exists(os.path.join(ROOT, s, "thumb.webp"))]
    unknown = [s for s in todo if s not in slugs]
    if unknown:
        raise SystemExit(f"not in the catalog: {unknown}")

    def route_fonts(route):
        url = urllib.parse.urlsplit(route.request.url)
        if url.netloc == "fonts.googleapis.com" and fonts_dir:
            route.fulfill(status=200, content_type="text/css", body=font_css(fonts_dir, url.query))
        elif url.netloc == "fonts.local":
            kind, pkg, name = url.path.strip("/").split("/")
            base = fonts_dir if kind == "s" else os.path.join(os.path.dirname(fonts_dir), "@fontsource-variable")
            route.fulfill(status=200, content_type="font/woff2", body=open(os.path.join(base, pkg, "files", name), "rb").read())
        else:
            route.abort()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1200, "height": 630}, color_scheme="light", reduced_motion="reduce")
        ctx.route(re.compile(r"^https?://"), route_fonts)
        page = ctx.new_page()
        for slug in todo + ([""] if not wanted or every else []):
            page.goto("file://" + os.path.join(ROOT, slug, "index.html"))
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(900)
            shot = Image.open(io.BytesIO(page.screenshot(type="png"))).convert("RGB")
            shot.save(os.path.join(ROOT, slug, "card.jpg"), quality=84, optimize=True, progressive=True)
            if slug:
                shot.resize((640, 336), Image.LANCZOS).save(os.path.join(ROOT, slug, "thumb.webp"), quality=80, method=6)
            print("made", slug or "(home)")
        browser.close()


if __name__ == "__main__":
    main()
