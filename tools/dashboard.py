#!/usr/bin/env python3
"""Turn a dashboard into a self-contained page that tools/build.py can take.

usage: python3 tools/dashboard.py <export-folder> <csv-folder> <out-folder>

A dashboard is not one HTML file. Its page, its data sources and its filter defaults are separate
documents, and its page code expects a host that supplies the data, a `dash` object, d3 and a set of
style tokens. This script writes <out-folder>/index.html with all of that in the page:

  - <export-folder>/dash/meta.json            {"title": ...}
  - <export-folder>/dash/params.json          filter defaults (optional)
  - <export-folder>/datasets/<id>.json        {"title", "description", "source": {"kind": "file", "url": "/_blob/<hex>", "name": ...}}
  - <export-folder>/files/index.html.json     {"text": the page}
  - <csv-folder>/<hex>.csv                    the attached file behind each data source

Only attached CSV files are handled. A source that is a live query has no rows to carry and stops
the conversion: a public page cannot run it.

The page loads d3 from ../assets/d3.v7.min.js, which is where it sits once the page is built into
its own folder of the site. Fonts are open ones standing in for the dashboard's own.
"""
import glob
import html
import json
import os
import re
import sys

TOKENS = """
:root{
  color-scheme:light;
  --font-anthropic-sans:"IBM Plex Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --font-anthropic-serif:"Newsreader",ui-serif,Georgia,"Times New Roman",serif;
  --color-bg:#f9f9f7;--color-panel:#fff;--color-fg:#0b0b0b;--color-fg-muted:#6f6d68;
  --color-border-line:rgba(11,11,11,.1);--color-bad:#8e2626;--color-ok:#006300;--color-warn:#734500;
  --cds-border:rgba(11,11,11,.1);--cds-text-secondary:#52514e;--cds-surface-popover:#fff;
  --cds-shadow-popover:0 8px 24px #0000001f,0 2px 6px #00000014;
  --cds-chart-axis:#c3c2b7;--cds-chart-grid:rgba(11,11,11,.1);--cds-chart-muted:#c3c2b7;
  --cds-chart-reference:#898781;--cds-chart-status-critical:#d03b3b;
  --cds-chart-categorical-1:#2a78d6;--cds-chart-categorical-2:#eb6834;--cds-chart-categorical-3:#1baf7a;
  --cds-chart-categorical-4:#eda100;--cds-chart-categorical-5:#e87ba4;--cds-chart-categorical-6:#008300;
  --cds-chart-categorical-7:#6250d6;--cds-chart-categorical-8:#e34948;
  --cds-font-size-caption:.8125rem;--cds-font-size-body:.9375rem;--cds-font-size-heading:1rem;--cds-font-size-title:1.75rem;
  --cds-font-weight-medium:500;
  --cds-gap-xs:8px;--cds-gap-sm:12px;--cds-gap-md:16px;--cds-gap-lg:28px;--cds-gap-xl:40px;
  --cds-pad-xs:6px;--cds-pad-sm:8px;--cds-pad-md:12px;--cds-pad-lg:16px;--cds-pad-xl:24px;
  --cds-radius:8px;--cds-dur-slow:.45s;--cds-ease-out:cubic-bezier(.165,.84,.44,1);
}
@media (prefers-color-scheme:dark){:root{
  color-scheme:dark;
  --color-bg:#0b0b0b;--color-panel:#1a1a19;--color-fg:#f0efec;--color-fg-muted:#9a988f;
  --color-border-line:rgba(255,255,255,.1);--color-bad:#ec7e7e;--color-ok:#0ca30c;--color-warn:#db9300;
  --cds-border:rgba(255,255,255,.1);--cds-text-secondary:#c3c2b7;--cds-surface-popover:#20201f;
  --cds-shadow-popover:0 8px 24px #00000052,0 2px 6px #0003;
  --cds-chart-axis:#383835;--cds-chart-grid:rgba(255,255,255,.1);--cds-chart-muted:#5f5e5a;
  --cds-chart-reference:#97958d;
  --cds-chart-categorical-1:#3987e5;--cds-chart-categorical-2:#d95926;--cds-chart-categorical-3:#199e70;
  --cds-chart-categorical-4:#c98500;--cds-chart-categorical-5:#d55181;--cds-chart-categorical-6:#008300;
  --cds-chart-categorical-7:#9085e9;--cds-chart-categorical-8:#e66767;
}}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--color-bg);color:var(--color-fg);font-family:var(--font-anthropic-sans)}
#dash-root{box-sizing:border-box;max-width:1240px;margin:0 auto;padding:clamp(16px,4vw,40px);color:var(--color-fg);font-size:var(--cds-font-size-body);line-height:1.45}
#dash-root :is(b,strong){font-weight:600}
""".strip()

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=IBM+Plex+Sans:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400..600&display=swap">')

# What the page's own script expects from its host: its data, filters and redraws.
SHIM = r"""
window.dash = (function () {
  var sets = {}, calcs = {}, subs = [], defaults = __PARAMS__, params = Object.assign({}, defaults);
  document.querySelectorAll('script[type="text/csv"][data-id]').forEach(function (s) {
    sets[s.getAttribute('data-id')] = d3.csvParse(s.textContent.replace(/^\s+|\s+$/g, ''));
  });
  function answer(status, data, columns) {
    return { status: status, data: data, rows: Array.isArray(data) ? data : [], columns: columns || [], value: data, message: '', refreshing: false, meta: [] };
  }
  function data(id) {
    if (sets[id]) return answer('ok', sets[id], sets[id].columns);
    var c = calcs[id];
    if (c) {
      if (!c.done) { c.value = c.fn.apply(null, (c.inputs || []).map(function (i) { return data(i).data; })); c.done = true; }
      var v = c.value;
      return answer('ok', v, Array.isArray(v) && v[0] && typeof v[0] === 'object' ? Object.keys(v[0]) : []);
    }
    return answer('missing', []);
  }
  var queued = false;
  function redraw() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(function () { queued = false; subs.forEach(function (fn) { fn(); }); });
  }
  var root = document.getElementById('dash-root'), width = root.clientWidth;
  if (window.ResizeObserver) new ResizeObserver(function () {
    if (root.clientWidth !== width) { width = root.clientWidth; redraw(); }
  }).observe(root);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(redraw);
  return {
    data: data,
    onData: function (fn) { subs.push(fn); fn(); },
    calc: function (id, spec) { calcs[id] = { inputs: spec.inputs, fn: spec.fn }; },
    loader: function () {},
    colors: [1, 2, 3, 4, 5, 6, 7, 8].map(function (i) { return 'var(--cds-chart-categorical-' + i + ')'; }),
    params: function () { return Object.assign({}, params); },
    setParams: function (next) {
      Object.keys(next || {}).forEach(function (k) { if (next[k] == null) delete params[k]; else params[k] = next[k]; });
      redraw();
    },
    resetParams: function () { params = Object.assign({}, defaults); redraw(); },
    refresh: function () {},
    setLink: function (name) { try { history.replaceState(history.state, '', '#' + name); } catch (e) {} }
  };
})();
""".strip()


def load(path):
    with open(path, encoding="utf8") as f:
        d = json.load(f)
    return d.get("data", d) if isinstance(d.get("data"), dict) else d


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    src, csvs, out = sys.argv[1:]
    title = load(os.path.join(src, "dash", "meta.json"))["title"]
    params_path = os.path.join(src, "dash", "params.json")
    params = load(params_path) if os.path.exists(params_path) else {}
    page = load(os.path.join(src, "files", "index.html.json"))["text"]
    if len(glob.glob(os.path.join(src, "files", "*.json"))) != 1:
        raise SystemExit("the page is split over several files; only a single index.html is handled")

    data = []
    for f in sorted(glob.glob(os.path.join(src, "datasets", "*.json"))):
        ds, ident = load(f), os.path.basename(f)[:-5]
        source = ds["source"]
        if source.get("kind") != "file":
            raise SystemExit(f"{ident}: a live query, which a public page cannot run")
        m = re.fullmatch(r"/_blob/([0-9a-f]{32})", source["url"])
        if not m or not source["name"].lower().endswith(".csv"):
            raise SystemExit(f"{ident}: only attached CSV files are handled")
        with open(os.path.join(csvs, m.group(1) + ".csv"), encoding="utf8") as c:
            text = c.read().lstrip("﻿").strip()
        if "</script" in text.lower():
            raise SystemExit(f"{ident}: the file cannot be placed in a page safely")
        data.append(f'<script type="text/csv" data-id="{html.escape(ident, quote=True)}">\n{text}\n</script>')

    cut = page.find("<script")
    if cut < 0:
        raise SystemExit("the page has no script")
    host = ("\n".join(data) + '\n<script src="../assets/d3.v7.min.js"></script>\n<script>\n'
            + SHIM.replace("__PARAMS__", json.dumps(params).replace("</", "<\\/")) + "\n</script>\n")
    doc = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
           f"<title>{html.escape(title)}</title>\n{FONTS}\n<style>\n{TOKENS}\n</style>\n</head>\n<body>\n"
           f"<main id=\"dash-root\">\n{page[:cut].strip()}\n</main>\n{host}{page[cut:].strip()}\n</body>\n</html>\n")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "index.html"), "w", encoding="utf8") as f:
        f.write(doc)
    print(f"{title}: {len(data)} data sources, {len(doc):,} characters -> {os.path.join(out, 'index.html')}")


if __name__ == "__main__":
    main()
