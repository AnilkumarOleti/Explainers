#!/usr/bin/env python3
"""Build the Explainers site for GitHub Pages.

usage: python3 tools/build.py [saved-pages-folder]

tools/catalog.json lists every page on the site: its section, address (slug), title and the
one-line blurb shown on the home page.

With a folder argument, each page found in that folder is rebuilt. The folder holds one
sub-folder per page, each with the page saved as index.html. A page is matched to its catalog
entry by the sub-folder name (the entry's "artifact" id) or, failing that, by its <title>.
Pages that are not supplied are kept as they are in the repository.

Without an argument, only the home page and 404 page are rebuilt from the catalog.

What a page gets, and nothing else:
  - a normal document head: language, charset, title, description, link-preview tags, icon;
  - one link at the foot, back to the home page.

A catalog entry may carry "css": a small style fix applied to that page only, for a layout fault
in the saved page (a chart that pushes a phone screen sideways, say). The saved page is not edited.

Run tools/shots.py afterwards to make the preview pictures for new or changed pages.
"""
import glob
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIVATE = re.compile(r"https://claude\.ai/(?:code/)?artifact/[A-Za-z0-9-]+")
LEAD = re.compile(r"\s*(<title>.*?</title>|<link\b[^>]*>|<meta\b[^>]*>|<style\b[^>]*>.*?</style>|<!--.*?-->)", re.S)
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,200..800&display=swap">')
BACK = ('<div style="clear:both;flex-basis:100%;grid-column:1/-1;box-sizing:border-box;width:100%;text-align:center;'
        'padding:48px 16px 40px;margin:0;position:relative;z-index:1">'
        '<a href="../" style="display:inline-block;padding:10px 20px;border-radius:999px;'
        'background:#101828;color:#fff;border:1px solid rgba(255,255,255,.3);text-decoration:none;'
        'font:600 15px/1.2 system-ui,-apple-system,\'Segoe UI\',sans-serif;letter-spacing:0">'
        '<span aria-hidden="true">&larr;&nbsp;</span>All explainers</a></div>\n')


def e(t):
    return html.escape(t, quote=True)


def read(path):
    with open(path, encoding="utf8") as f:
        return f.read()


def write(rel, text):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf8") as f:
        f.write(text)


def split(path):
    """Return (base style, page title, head tags the page brought, body attributes, body).

    Two shapes are accepted: a page saved from a published artifact, whose own <title>, fonts and
    styles sit at the top of <body> under a small wrapper head; and an ordinary full document.
    """
    s = read(path)
    m = re.search(r"<body([^>]*)>", s)
    if not m:
        raise SystemExit(f"{path}: no <body>")
    head, attrs, body = s[:m.start()], m.group(1), s[m.end():]
    body = body[:body.rindex("</body>")]
    title, lead, base = None, [], ""
    if "<title" in head:  # a full document: keep what its head loads, replace what describes it
        inner = re.search(r"<head[^>]*>(.*)</head>", head, re.S).group(1)
        title = html.unescape(re.sub(r"<[^>]+>", "", re.search(r"<title>.*?</title>", inner, re.S).group(0))).strip()
        inner = re.sub(r"<title>.*?</title>", "", inner, flags=re.S)
        inner = re.sub(r"<meta\b[^>]*(?:charset|viewport|description|og:|twitter:)[^>]*>", "", inner)
        inner = re.sub(r"<link\b[^>]*rel=[\"']?(?:canonical|icon)[^>]*>", "", inner)
        lead.append(re.sub(r"\n\s*\n+", "\n", inner).strip())
    else:
        w = re.search(r"<style>.*?</style>", head, re.S)
        base = w.group(0) if w else ""
        pos = 0
        while True:
            m = LEAD.match(body, pos)
            if not m:
                break
            tag, pos = m.group(1), m.end()
            if tag.startswith("<title"):
                title = html.unescape(re.sub(r"<[^>]+>", "", tag)).strip()
            elif tag.startswith("<meta") and re.search(r"charset|viewport", tag):
                pass
            else:
                lead.append(tag)
        body = body[pos:]
    if title is None:
        raise SystemExit(f"{path}: no <title> found")
    return base, title, "\n".join(lead), attrs, body.strip() + "\n"


def page_html(site, page, base, lead, attrs, body):
    url = site["url"] + page["slug"] + "/"
    title, desc = page["title"], page["blurb"]
    fix = f"<style>{page['css']}</style>\n" if page.get("css") else ""
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
            f"<title>{e(title)} | {e(site['title'])}</title>\n"
            f"<meta name=\"description\" content=\"{e(desc)}\">\n"
            f"<link rel=\"canonical\" href=\"{e(url)}\">\n"
            "<link rel=\"icon\" href=\"../favicon.svg\" type=\"image/svg+xml\">\n"
            "<meta property=\"og:type\" content=\"article\">\n"
            f"<meta property=\"og:site_name\" content=\"{e(site['title'])}\">\n"
            f"<meta property=\"og:title\" content=\"{e(title)}\">\n"
            f"<meta property=\"og:description\" content=\"{e(desc)}\">\n"
            f"<meta property=\"og:url\" content=\"{e(url)}\">\n"
            f"<meta property=\"og:image\" content=\"{e(url)}card.jpg\">\n"
            "<meta property=\"og:image:width\" content=\"1200\">\n"
            "<meta property=\"og:image:height\" content=\"630\">\n"
            "<meta name=\"twitter:card\" content=\"summary_large_image\">\n"
            f"{base}\n{lead}\n{fix}</head>\n<body{attrs}>\n{body}{BACK}</body>\n</html>\n")


CSS = """
:root{--ground:#EEF0F3;--surface:#fff;--ink:#101828;--muted:#536079;--line:#C9D0DB;--accent:#1F3FD6;--on-accent:#fff;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--ground:#0E1220;--surface:#171C2C;--ink:#E8ECF4;--muted:#9AA6BD;--line:#2B3349;--accent:#A9B8FF;--on-accent:#0E1220;color-scheme:dark}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--ground);color:var(--ink);font-family:"Bricolage Grotesque",system-ui,-apple-system,"Segoe UI",sans-serif;font-size:17px;line-height:1.5;font-optical-sizing:auto;-webkit-font-smoothing:antialiased}
a{color:inherit}
:focus-visible{outline:3px solid var(--accent);outline-offset:3px;border-radius:4px}
.wrap{max-width:1240px;margin:0 auto;padding-inline:clamp(16px,4vw,48px)}
.top{display:flex;align-items:baseline;justify-content:space-between;gap:8px 32px;flex-wrap:wrap;padding-block:22px 0}
.mark{margin:0;font-size:1.5rem;font-weight:800;font-stretch:75%;letter-spacing:-.01em;line-height:1}
.mark a{text-decoration:none}
.top nav{display:flex;flex-wrap:wrap;gap:0 22px;font-size:.94rem}
.top nav a{color:var(--muted);text-decoration:none;padding-block:8px}
.top nav a:hover{color:var(--ink);text-decoration:underline;text-underline-offset:4px}
.hero{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:clamp(24px,4vw,64px);align-items:center;padding-block:clamp(32px,6vw,80px) clamp(40px,6vw,80px);border-bottom:1px solid var(--line)}
.ask{margin:0;font-size:clamp(2.5rem,6.1vw,5.25rem);line-height:.98;font-weight:800;font-stretch:75%;letter-spacing:-.02em;text-wrap:balance;min-height:2.94em;display:flex;align-items:flex-end}
.ask a{text-decoration:none}
.ask a:hover{text-decoration:underline;text-decoration-thickness:.06em;text-underline-offset:.1em}
.acts{display:flex;flex-wrap:wrap;gap:12px;margin-top:clamp(20px,3vw,32px)}
.btn{font:inherit;font-size:1rem;font-weight:600;line-height:1.2;padding:13px 22px;border-radius:999px;border:1.5px solid var(--ink);background:transparent;color:var(--ink);cursor:pointer;text-decoration:none;display:inline-block}
.btn.go{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}
.btn:hover{background:var(--ink);border-color:var(--ink);color:var(--ground)}
.intro{margin:clamp(20px,3vw,32px) 0 0;color:var(--muted);max-width:38ch;font-size:1.06rem}
.pic{display:block;text-decoration:none}
.pic img{display:block;width:100%;height:auto;aspect-ratio:1200/630;border:1px solid var(--line);border-radius:12px;background:var(--surface)}
.pic span{display:block;margin-top:10px;color:var(--muted);font-size:.94rem}
.pic:hover img{border-color:var(--ink)}
.sec{padding-top:clamp(40px,5vw,72px);scroll-margin-top:8px}
.sec h2{margin:0 0 22px;font-size:clamp(1.7rem,3.2vw,2.4rem);line-height:1.05;font-weight:800;font-stretch:75%;letter-spacing:-.01em}
.sec h2 small{font-size:.48em;font-weight:500;font-stretch:100%;letter-spacing:0;color:var(--muted);margin-left:.6em}
.grid{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,280px),1fr));gap:36px 28px}
.card{display:block;text-decoration:none}
.card img{display:block;width:100%;height:auto;aspect-ratio:640/336;border:1px solid var(--line);border-radius:8px;background:var(--surface)}
.card b{display:block;margin-top:14px;font-size:1.2rem;line-height:1.2;font-weight:700;text-wrap:balance}
.card span{display:block;margin-top:6px;color:var(--muted);font-size:.97rem;line-height:1.45}
.card i{display:inline-block;margin-top:9px;font-style:normal;font-size:.82rem;font-weight:600;border:1px solid var(--line);border-radius:999px;padding:2px 10px}
.card:hover img{border-color:var(--ink)}
.card:hover b{text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:3px}
.foot{margin-top:clamp(56px,8vw,104px);padding-block:28px 56px;border-top:1px solid var(--line);color:var(--muted);font-size:.97rem}
.foot p{margin:0 0 8px;max-width:68ch}
.foot a{color:var(--ink);text-underline-offset:3px}
@media (max-width:820px){
  .hero{grid-template-columns:1fr}
  .ask{min-height:0}
  .top nav{gap:0 18px}
}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
""".strip()

JS = """
(function(){
  var asks=JSON.parse(document.getElementById('asks').textContent);
  var q=document.getElementById('ask-q'),go=document.getElementById('ask-go'),pic=document.getElementById('ask-pic'),
      img=pic.querySelector('img'),cap=pic.querySelector('span'),next=document.getElementById('ask-next');
  var i=Math.floor(Math.random()*asks.length);
  function show(){
    var a=asks[i],href=a.slug+'/';
    q.textContent=a.ask;q.href=href;go.href=href;pic.href=href;
    img.src=a.slug+'/card.jpg';cap.textContent=a.title;
  }
  show();
  next.addEventListener('click',function(){
    i=(i+1+Math.floor(Math.random()*(asks.length-1)))%asks.length;show();
  });
})();
""".strip()


def index_html(cat):
    site = cat["site"]
    pages = [p for s in cat["sections"] for p in s["pages"]]
    asks = [p for p in pages if p.get("ask")]
    first = asks[0]
    names = [x["name"][0].lower() + x["name"][1:] if not x["name"].startswith("AI") else x["name"] for x in cat["sections"]]
    desc = f"{site['intro']} {len(pages)} pages on {', '.join(names[:-1])}, and {names[-1]}."
    nav = "".join(f'<a href="#{e(s["id"])}">{e(s["name"])}</a>' for s in cat["sections"])
    out = ["<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
           f"<title>{e(site['title'])}</title>\n"
           f"<meta name=\"description\" content=\"{e(desc)}\">\n"
           f"<link rel=\"canonical\" href=\"{e(site['url'])}\">\n"
           "<link rel=\"icon\" href=\"favicon.svg\" type=\"image/svg+xml\">\n"
           "<meta property=\"og:type\" content=\"website\">\n"
           f"<meta property=\"og:title\" content=\"{e(site['title'])}\">\n"
           f"<meta property=\"og:description\" content=\"{e(desc)}\">\n"
           f"<meta property=\"og:url\" content=\"{e(site['url'])}\">\n"
           f"<meta property=\"og:image\" content=\"{e(site['url'])}card.jpg\">\n"
           "<meta property=\"og:image:width\" content=\"1200\">\n"
           "<meta property=\"og:image:height\" content=\"630\">\n"
           "<meta name=\"twitter:card\" content=\"summary_large_image\">\n"
           f"{FONTS}\n<style>\n{CSS}\n</style>\n</head>\n<body>\n"
           "<div class=\"wrap\">\n"
           f"<header class=\"top\">\n<h1 class=\"mark\"><a href=\"./\">{e(site['title'])}</a></h1>\n"
           f"<nav aria-label=\"Sections\">{nav}</nav>\n</header>\n"
           "<main>\n<section class=\"hero\" aria-label=\"A question to start with\">\n<div>\n"
           f"<p class=\"ask\" aria-live=\"polite\"><a id=\"ask-q\" href=\"{e(first['slug'])}/\">{e(first['ask'])}</a></p>\n"
           f"<div class=\"acts\"><a class=\"btn go\" id=\"ask-go\" href=\"{e(first['slug'])}/\">Read the answer</a>"
           "<button class=\"btn\" id=\"ask-next\" type=\"button\">Ask another</button></div>\n"
           f"<p class=\"intro\">{e(site['intro'])} {len(pages)} so far.</p>\n</div>\n"
           f"<a class=\"pic\" id=\"ask-pic\" href=\"{e(first['slug'])}/\" tabindex=\"-1\">"
           f"<img src=\"{e(first['slug'])}/card.jpg\" width=\"1200\" height=\"630\" alt=\"\">"
           f"<span>{e(first['title'])}</span></a>\n</section>\n"]
    data = json.dumps([{"ask": p["ask"], "slug": p["slug"], "title": p["title"]} for p in asks],
                      ensure_ascii=False).replace("</", "<\\/")
    out.append(f"<script type=\"application/json\" id=\"asks\">{data}</script>\n<script>\n{JS}\n</script>\n")
    for s in cat["sections"]:
        out.append(f"<section class=\"sec\" id=\"{e(s['id'])}\" aria-labelledby=\"h-{e(s['id'])}\">\n"
                   f"<h2 id=\"h-{e(s['id'])}\">{e(s['name'])}<small>{len(s['pages'])} pages</small></h2>\n<ul class=\"grid\">\n")
        for p in s["pages"]:
            note = f"<i>{e(p['note'])}</i>" if p.get("note") else ""
            out.append(f"<li><a class=\"card\" href=\"{e(p['slug'])}/\">"
                       f"<img src=\"{e(p['slug'])}/thumb.webp\" width=\"640\" height=\"336\" loading=\"lazy\" decoding=\"async\" alt=\"\">"
                       f"<b>{e(p['title'])}</b><span>{e(p['blurb'])}</span>{note}</a></li>\n")
        out.append("</ul>\n</section>\n")
    out.append("</main>\n<footer class=\"foot\">\n"
               f"<p>A collection by <a href=\"{e(site['github'])}\">{e(site['author'])}</a>.</p>\n"
               f"<p>For data science and machine learning, there is also the <a href=\"{e(site['handbook'])}\">DS/ML Learning Handbook</a>.</p>\n"
               "<p>These pages are for understanding. The health pages are not medical advice.</p>\n"
               "</footer>\n</div>\n</body>\n</html>\n")
    return "".join(out)


def notfound_html(site):
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
            f"<title>Page not found | {e(site['title'])}</title>\n<meta name=\"robots\" content=\"noindex\">\n"
            f"{FONTS}\n<style>\n{CSS}\n.lost{{padding-block:18vh}}.lost p{{margin:0 0 24px;color:var(--muted)}}\n</style>\n</head>\n<body>\n"
            "<div class=\"wrap lost\">\n<p class=\"ask\" style=\"min-height:0\">That page isn't here.</p>\n"
            "<p style=\"margin-top:20px\">The address may have changed, or the page was never published.</p>\n"
            f"<a class=\"btn go\" href=\"{e(site['url'])}\">See all explainers</a>\n</div>\n</body>\n</html>\n")


def main():
    args = sys.argv[1:]
    if len(args) > 1 or (args and args[0] in ("-h", "--help")):
        raise SystemExit(__doc__)
    cat = json.loads(read(os.path.join(ROOT, "tools", "catalog.json")))
    site = cat["site"]
    pages = [p for s in cat["sections"] for p in s["pages"]]
    slugs = [p["slug"] for p in pages]
    dup = sorted({s for s in slugs if slugs.count(s) > 1})
    if dup:
        raise SystemExit(f"catalog repeats a slug: {dup}")

    by_id, by_title = {}, {}
    if args:
        for f in sorted(glob.glob(os.path.join(args[0], "*", "index.html"))):
            if "artifact-type/" in read(f):
                continue  # not a self-contained page
            by_id[os.path.basename(os.path.dirname(f))] = f
            by_title.setdefault(split(f)[1], []).append(f)

    built, kept, missing = [], [], []
    for p in pages:
        src = by_id.get(p.get("artifact", ""))
        if not src:
            hits = by_title.get(p.get("source_title", p["title"]), [])
            if len(hits) > 1:
                raise SystemExit(f"{p['title']}: {len(hits)} saved pages share this title; set \"artifact\" in the catalog")
            src = hits[0] if hits else None
        if src:
            base, _, lead, attrs, body = split(src)
            if PRIVATE.search(body):
                raise SystemExit(f"{p['title']}: links to a private page")
            write(f"{p['slug']}/index.html", page_html(site, p, base, lead, attrs, body))
            built.append(p["slug"])
        elif os.path.exists(os.path.join(ROOT, p["slug"], "index.html")):
            kept.append(p["slug"])
        else:
            missing.append(p["title"])
    if missing:
        raise SystemExit(f"in the catalog but not supplied and not in the repository: {missing}")

    write("index.html", index_html(cat))
    write("404.html", notfound_html(site))
    print(f"home page: {len(pages)} pages in {len(cat['sections'])} sections")
    print(f"pages rebuilt: {len(built)}; kept as they were: {len(kept)}")
    no_pic = [s for s in slugs if not os.path.exists(os.path.join(ROOT, s, "thumb.webp"))]
    if no_pic:
        print(f"no preview picture yet (run tools/shots.py): {', '.join(no_pic)}")


if __name__ == "__main__":
    main()
