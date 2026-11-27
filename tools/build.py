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
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIVATE = re.compile(r"https://claude\.ai/(?:code/)?artifact/[A-Za-z0-9-]+")
LEAD = re.compile(r"\s*(<title>.*?</title>|<link\b[^>]*>|<meta\b[^>]*>|<style\b[^>]*>.*?</style>|<!--.*?-->)", re.S)
BACK = ('<div style="clear:both;flex-basis:100%;grid-column:1/-1;box-sizing:border-box;width:100%;text-align:center;'
        'padding:48px 16px 40px;margin:0;position:relative;z-index:1">'
        '<a href="../" style="display:inline-block;padding:10px 20px;border-radius:999px;'
        'background:#101828;color:#fff;border:1px solid rgba(255,255,255,.3);text-decoration:none;'
        'font:600 15px/1.2 system-ui,-apple-system,\'Segoe UI\',sans-serif;letter-spacing:0">'
        '<span aria-hidden="true">&larr;&nbsp;</span>All explainers</a></div>\n')


def next_html(page):
    """An optional "what to read next" card at the foot of a page: the catalog entry's "next" (slug, title, question)."""
    n = page.get("next")
    if not n:
        return ""
    return ("<div data-next style=\"clear:both;flex-basis:100%;grid-column:1/-1;box-sizing:border-box;width:100%;padding:40px 16px 0;margin:0;"
            "position:relative;z-index:1\"><a href=\"../" + e(n["slug"]) + "/\" style=\"display:block;max-width:620px;margin:0 auto;padding:20px 24px 22px;"
            "border-radius:18px;background:#101828;color:#fff;text-decoration:none;border:1px solid rgba(255,255,255,.3);"
            "font:400 16px/1.45 system-ui,-apple-system,'Segoe UI',sans-serif;text-align:left\">"
            "<span style=\"display:block;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#FFD873\">Next question</span>"
            "<span style=\"display:block;margin-top:8px;font-size:20px;line-height:1.3;font-weight:600\">" + e(n["question"]) + "</span>"
            "<span style=\"display:block;margin-top:12px;font-weight:600;color:#FFD873\">" + e(n["title"]) + " <span aria-hidden=\"true\">&rarr;</span></span>"
            "</a></div>\n")


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
            f"{base}\n{lead}\n{fix}</head>\n<body{attrs}>\n{body}{next_html(page)}{BACK}</body>\n</html>\n")


# ---- Star Atlas home page -------------------------------------------------------------------
ATLAS_FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
               '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
               '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
               'family=Fraunces:ital,opsz,wght@0,9..144,400..700;1,9..144,400..700'
               '&family=Inter:wght@400;500;600&display=swap">')

# Short names for the sky labels; a section not listed here uses its full name.
SHORT = {"data": "Data & analytics", "ai": "AI & tech", "body": "Body & health", "brain": "Brain & mind",
         "ideas": "Big ideas", "world": "World & history", "screen": "Screen & sport"}
# Where each constellation sits on the sky, in percent of its width and height, in catalog order.
CENTRES = [(15, 36), (38, 22), (62, 30), (86, 30), (22, 76), (51, 72), (80, 76)]

ATLAS_CSS = """
:root{--night:#090D20;--sky:#0E1431;--panel:#121A40;--line:#262F5C;--ink:#E8E6F5;--soft:#B9BDD6;--muted:#9EA3C6;--gold:#FFD873;--gold-hi:#FFF1C4;--dim:#4A5385;color-scheme:dark}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--night);color:var(--ink);font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;font-size:16px;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:var(--gold)}a:hover{color:var(--gold-hi)}
:focus-visible{outline:3px solid var(--gold);outline-offset:3px;border-radius:6px}
.wrap{max-width:1280px;margin:0 auto;padding-inline:clamp(16px,4vw,40px)}
.serif{font-family:Fraunces,Georgia,serif}
.top{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px 24px;padding-block:24px}
.mark{margin:0;display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.mark a{font-family:Fraunces,Georgia,serif;font-style:italic;font-weight:600;font-size:1.75rem;color:#fff;text-decoration:none}
.mark small{font-size:.8rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.top nav{display:flex;gap:6px 22px;flex-wrap:wrap;font-size:.95rem}
.top nav a{text-decoration:none;padding-block:8px}
.hero{display:flex;flex-wrap:wrap;gap:20px 64px;align-items:flex-end;justify-content:space-between;padding-block:clamp(24px,5vw,56px) clamp(20px,3vw,32px)}
.hero h1{margin:0;font-family:Fraunces,Georgia,serif;font-weight:500;font-size:clamp(2.4rem,6vw,4.4rem);line-height:1.02;letter-spacing:-.02em;max-width:15ch;color:#fff;text-wrap:balance}
.hero h1 em{color:var(--gold)}
.hero p{margin:0;max-width:36ch;font-size:1.06rem;color:var(--soft)}
.stage{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:20px;align-items:stretch}
.scroll{overflow-x:auto;border-radius:28px;border:1px solid var(--line);background:var(--sky);scrollbar-color:var(--line) transparent}
.sky{position:relative;min-width:880px;height:620px;overflow:hidden}
.dust{position:absolute;width:2px;height:2px;border-radius:50%;background:#fff;animation:tw 3.4s ease-in-out infinite}
@keyframes tw{0%,100%{opacity:.2}50%{opacity:.8}}
.sky svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.sky line{stroke:rgba(255,216,115,.42);stroke-width:.14;transition:stroke .3s}
.sky line.off{stroke:rgba(120,130,190,.16)}
.label{position:absolute;transform:translate(-50%,-50%);background:none;border:0;cursor:pointer;font-family:Fraunces,Georgia,serif;font-style:italic;font-size:17px;color:var(--gold-hi);white-space:nowrap;padding:8px 10px;transition:color .3s}
.label span{font-family:Inter,sans-serif;font-style:normal;font-size:12px;opacity:.7;margin-left:4px}
.label.off{color:#6A72A6}
.star{position:absolute;transform:translate(-50%,-50%);width:30px;height:30px;padding:0;border:0;background:none;cursor:pointer;display:grid;place-items:center;border-radius:50%}
.star i{display:block;width:var(--s);height:var(--s);border-radius:50%;background:var(--gold);box-shadow:0 0 12px rgba(255,216,115,.75);transition:transform .25s,background .3s,box-shadow .3s}
.star:hover i,.star:focus-visible i{transform:scale(1.7)}
.star.off i{background:var(--dim);box-shadow:none}
.star.seen i{background:#fff;box-shadow:0 0 0 3px rgba(255,216,115,.35),0 0 16px var(--gold)}
.star.sel i{width:18px;height:18px;background:#fff;box-shadow:0 0 0 7px rgba(255,216,115,.25),0 0 30px var(--gold)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:22px;overflow:hidden;display:flex;flex-direction:column}
.card img{display:block;width:100%;height:auto;aspect-ratio:640/336;object-fit:cover;object-position:top;background:#1B2350}
.card .in{padding:18px 20px 22px;display:flex;flex-direction:column;flex:1}
.kicker{font-size:.75rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.card h2{margin:6px 0 0;font-family:Fraunces,Georgia,serif;font-weight:500;font-size:1.6rem;line-height:1.12;color:#fff}
.card p{margin:10px 0 18px;color:#CDD0E6;font-size:.98rem}
.card .go{margin-top:auto}
.pill{display:inline-block;font:inherit;font-size:.95rem;font-weight:600;line-height:1.2;padding:12px 20px;border-radius:999px;border:0;background:var(--gold);color:#14183A;text-decoration:none;cursor:pointer}
.pill:hover{background:var(--gold-hi);color:#14183A}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:18px}
.chip{font:inherit;font-size:.9rem;padding:9px 15px;border-radius:999px;cursor:pointer;border:1px solid var(--line);background:transparent;color:var(--ink)}
.chip[aria-pressed=true]{background:var(--gold);border-color:var(--gold);color:#14183A}
.find{flex:1 1 220px;display:flex;justify-content:flex-end;gap:10px;flex-wrap:wrap;align-items:center}
.find input{font:inherit;font-size:.95rem;width:min(100%,240px);padding:11px 16px;border-radius:999px;border:1px solid var(--line);background:var(--sky);color:var(--ink)}
.find input::placeholder{color:var(--muted)}
.swipe{display:none;margin:10px 0 0;color:var(--muted);font-size:.9rem}
.tally{margin:14px 0 0;color:var(--muted);font-size:.92rem}
.tally b{color:var(--gold);font-weight:600}
.cons{padding-top:clamp(56px,8vw,96px);scroll-margin-top:12px}
.cons>h2{margin:0;font-family:Fraunces,Georgia,serif;font-weight:500;font-size:clamp(1.9rem,4vw,2.6rem);color:#fff}
.cons>p{margin:6px 0 28px;color:var(--muted)}
.groups{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr));gap:20px;align-items:start}
.group{background:#0F1538;border:1px solid var(--line);border-radius:20px;padding:22px 22px 14px;scroll-margin-top:12px}
.group h3{margin:0;display:flex;justify-content:space-between;align-items:baseline;gap:12px;font-family:Fraunces,Georgia,serif;font-style:italic;font-weight:500;font-size:1.45rem;color:#fff}
.group h3 small{font-family:Inter,sans-serif;font-style:normal;font-size:.8rem;color:var(--muted);white-space:nowrap}
.group ul{list-style:none;margin:14px 0 0;padding:0}
.group li a{display:flex;gap:12px;align-items:baseline;padding:9px 0;border-top:1px solid #1D2551;text-decoration:none;color:#DADCEE}
.group li a:hover b{color:var(--gold-hi);text-decoration:underline;text-underline-offset:3px}
.group li a::before{content:"";flex:none;width:7px;height:7px;border-radius:50%;background:var(--dim);transform:translateY(-1px)}
.group li a.seen::before{background:var(--gold);box-shadow:0 0 8px var(--gold)}
.group b{font-weight:500}
.group i{display:block;font-style:normal;font-size:.86rem;color:var(--muted);margin-top:2px}
.suggest{margin-top:clamp(56px,8vw,96px);scroll-margin-top:12px;background:var(--panel);border:1px solid var(--line);border-radius:24px;padding:clamp(24px,4vw,40px);display:flex;flex-wrap:wrap;gap:20px 48px;align-items:center;justify-content:space-between}
.suggest h2{margin:0;font-family:Fraunces,Georgia,serif;font-weight:500;font-size:clamp(1.6rem,3.4vw,2.2rem);line-height:1.1;color:#fff}
.suggest p{margin:8px 0 0;color:var(--soft);max-width:46ch}
.suggest .acts{display:flex;flex-wrap:wrap;gap:12px;align-items:center}
.ghost{display:inline-block;font:inherit;font-size:.95rem;font-weight:600;line-height:1.2;padding:11px 19px;border-radius:999px;border:1.5px solid var(--gold);color:var(--gold);text-decoration:none}
.ghost:hover{background:var(--gold);color:#14183A}
[hidden]{display:none!important}
.start{padding-bottom:clamp(20px,3vw,32px)}
.start-top{display:flex;flex-wrap:wrap;gap:12px 28px;align-items:center;justify-content:space-between}
.start h2{margin:0;font-family:Fraunces,Georgia,serif;font-weight:500;font-size:clamp(1.35rem,3vw,1.75rem);color:#fff}
.search{flex:1 1 260px;display:flex;justify-content:flex-end}
.search input{font:inherit;font-size:1rem;width:min(100%,380px);padding:13px 18px;border-radius:999px;border:1px solid var(--line);background:var(--sky);color:var(--ink)}
.search input::placeholder{color:var(--muted)}
.hits{list-style:none;margin:14px 0 0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,270px),1fr));gap:8px 16px}
.hits a{display:flex;justify-content:space-between;gap:12px;align-items:baseline;padding:12px 16px;min-height:46px;border:1px solid var(--line);border-radius:14px;background:var(--panel);color:var(--ink);text-decoration:none}
.hits a:hover{border-color:var(--gold)}
.hits a.seen b::after{content:" \2022";color:var(--gold)}
.hits small{color:var(--muted);white-space:nowrap}
.hits .more{color:var(--muted);padding:12px 4px;font-size:.95rem}
.nomatch{margin:14px 0 0;color:var(--soft)}
.starters{list-style:none;margin:16px 0 0;padding:0;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.scard{display:flex;gap:14px;align-items:center;height:100%;padding:10px;border:1px solid var(--line);border-radius:18px;background:var(--panel);color:var(--ink);text-decoration:none}
.scard:hover{border-color:var(--gold)}
.scard img{flex:none;width:112px;height:auto;aspect-ratio:640/336;object-fit:cover;object-position:top;border-radius:10px;background:#1B2350}
.scard b{display:block;font-family:Fraunces,Georgia,serif;font-weight:500;font-size:1.12rem;line-height:1.15;color:#fff}
.scard i{display:block;margin-top:4px;font-style:normal;font-size:.88rem;line-height:1.4;color:var(--soft)}
.foot{margin-top:clamp(56px,8vw,104px);padding-block:28px 56px;border-top:1px solid var(--line);color:var(--muted);font-size:.94rem}
.foot p{margin:0 0 8px;max-width:72ch}
.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media (max-width:960px){.starters{grid-template-columns:1fr}.stage{grid-template-columns:1fr}.card{flex-direction:row}.card img{width:42%;aspect-ratio:auto}}
@media (max-width:600px){.search{justify-content:stretch}.search input{width:100%}.card{flex-direction:column}.card img{width:100%;aspect-ratio:640/336}.sky{height:540px;min-width:780px}.swipe{display:block}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}.dust{animation:none;opacity:.5}.star i,.label,.sky line{transition:none}}
""".strip()

ATLAS_JS = """
(function(){
  var D=JSON.parse(document.getElementById('atlas-data').textContent);
  var KEY='explainers-lit',seen={};
  try{(JSON.parse(localStorage.getItem(KEY))||[]).forEach(function(s){seen[s]=1;});}catch(e){}
  function save(){try{localStorage.setItem(KEY,JSON.stringify(Object.keys(seen)));}catch(e){}}
  var stars=[].slice.call(document.querySelectorAll('.star')),lines=[].slice.call(document.querySelectorAll('.sky line')),
      labels=[].slice.call(document.querySelectorAll('.label')),chips=[].slice.call(document.querySelectorAll('.chip')),
      links=[].slice.call(document.querySelectorAll('a[data-slug]')),q=document.getElementById('find'),
      card={img:document.getElementById('c-img'),sec:document.getElementById('c-sec'),title:document.getElementById('c-title'),
            ask:document.getElementById('c-ask'),go:document.getElementById('c-go')},
      tally=document.getElementById('tally'),sec='',sel=-1;
  function norm(s){return s.toLowerCase().replace(/[\u2018\u2019']/g,'').replace(/[^a-z0-9]+/g,' ').trim();}
  D.forEach(function(p){p.hay=' '+norm(p.title+' '+p.ask+' '+p.blurb);});
  function words(){return norm(q.value).split(' ').filter(Boolean);}
  function match(i){
    var p=D[i],w=words();
    if(w.length)return w.every(function(x){return p.hay.indexOf(' '+x)>=0;});
    return !sec||p.sec===sec;
  }
  var ul=document.getElementById('hits'),no=document.getElementById('nomatch'),cnt=document.getElementById('hitcount'),
      startList=document.querySelector('.starters');
  function hits(){var h=[];for(var i=0;i<D.length;i++){if(match(i))h.push(i);}return h;}
  function renderHits(){
    var w=words();ul.textContent='';
    if(!w.length){ul.hidden=true;no.hidden=true;startList.hidden=false;cnt.textContent='';return;}
    startList.hidden=true;var h=hits();
    if(!h.length){ul.hidden=true;no.hidden=false;no.textContent='No pages match \u201c'+q.value.trim()+'\u201d. Try one word, or pick a constellation below.';cnt.textContent='No pages match';return;}
    no.hidden=true;ul.hidden=false;
    h.slice(0,8).forEach(function(i){
      var li=document.createElement('li'),a=document.createElement('a'),b=document.createElement('b'),s=document.createElement('small');
      a.href=D[i].slug+'/';a.setAttribute('data-slug',D[i].slug);if(seen[D[i].slug])a.className='seen';
      b.textContent=D[i].title;s.textContent=D[i].secName;a.appendChild(b);a.appendChild(s);li.appendChild(a);ul.appendChild(li);});
    if(h.length>8){var m=document.createElement('li');m.className='more';m.textContent='and '+(h.length-8)+' more, lit up in the sky below';ul.appendChild(m);}
    cnt.textContent=h.length+(h.length===1?' page matches':' pages match');
  }
  function paint(){
    stars.forEach(function(b,i){
      b.classList.toggle('off',!match(i));b.classList.toggle('seen',!!seen[D[i].slug]);b.classList.toggle('sel',i===sel);
      b.setAttribute('aria-pressed',i===sel?'true':'false');
    });
    lines.forEach(function(l){l.classList.toggle('off',!!sec&&l.getAttribute('data-sec')!==sec);});
    labels.forEach(function(l){l.classList.toggle('off',!!sec&&l.getAttribute('data-sec')!==sec);});
    chips.forEach(function(c){c.setAttribute('aria-pressed',!words().length&&c.getAttribute('data-sec')===sec?'true':'false');});
    renderHits();
    links.forEach(function(a){a.classList.toggle('seen',!!seen[a.getAttribute('data-slug')]);});
    var n=Object.keys(seen).filter(function(s){return D.some(function(p){return p.slug===s;});}).length;
    tally.innerHTML=n?'You have lit <b>'+n+'</b> of '+D.length+' stars. Each page you open stays lit in your sky.'
                     :'Each page you open stays lit in your sky, on this device.';
  }
  function pick(i){
    sel=i;var p=D[i];
    card.img.src=p.slug+'/thumb.webp';card.sec.textContent=p.secName;card.title.textContent=p.title;
    card.ask.textContent=p.ask;card.go.href=p.slug+'/';paint();
    var sc=document.querySelector('.scroll'),b=stars[i];
    if(sc.scrollWidth>sc.clientWidth){var x=b.offsetLeft-sc.clientWidth/2;sc.scrollTo({left:Math.max(0,x),behavior:'smooth'});}
  }
  stars.forEach(function(b,i){b.addEventListener('click',function(){pick(i);});});
  function setSec(s){sec=s;paint();}
  chips.forEach(function(c){c.addEventListener('click',function(){setSec(c.getAttribute('data-sec'));});});
  labels.forEach(function(l){l.addEventListener('click',function(){setSec(sec===l.getAttribute('data-sec')?'':l.getAttribute('data-sec'));});});
  [].forEach.call(document.querySelectorAll('[data-light]'),function(b){b.addEventListener('click',function(){
    setSec(b.getAttribute('data-light'));document.getElementById('atlas').scrollIntoView();});});
  q.addEventListener('input',paint);
  q.addEventListener('keydown',function(ev){if(ev.key==='Enter'){var h=hits();if(h.length){pick(h[0]);document.getElementById('atlas').scrollIntoView({block:'start'});}}});
  document.getElementById('shoot').addEventListener('click',function(){
    var pool=[];for(var i=0;i<D.length;i++){if(match(i)&&i!==sel)pool.push(i);}
    if(!pool.length)for(i=0;i<D.length;i++)if(i!==sel)pool.push(i);
    pick(pool[Math.floor(Math.random()*pool.length)]);
  });
  document.addEventListener('click',function(ev){
    var a=ev.target.closest&&ev.target.closest('a[data-slug],#c-go');if(!a)return;
    var s=a.id==='c-go'?D[sel].slug:a.getAttribute('data-slug');seen[s]=1;save();
  });
  window.addEventListener('pageshow',function(){
    try{seen={};(JSON.parse(localStorage.getItem(KEY))||[]).forEach(function(s){seen[s]=1;});}catch(e){}paint();});
  var asks=[];D.forEach(function(p,i){if(p.hasAsk)asks.push(i);});
  pick(asks.length?asks[Math.floor(Math.random()*asks.length)]:0);
})();
""".strip()


def sky(cat):
    """Positions for every star, the lines between them and the constellation labels."""
    import hashlib
    import math
    stars, lines, labels = [], [], []
    for k, s in enumerate(cat["sections"]):
        cx, cy = CENTRES[k % len(CENTRES)]
        pts = []
        for i, p in enumerate(s["pages"]):
            h = hashlib.md5(p["slug"].encode()).digest()
            jx, jy = (h[0] / 255 - .5) * 1.2, (h[1] / 255 - .5) * 1.6
            a, r = i * 2.39996, 2.2 * math.sqrt(i + .6)
            x, y = cx + r * math.cos(a) * .62 + jx, cy + r * math.sin(a) + jy
            x, y = round(min(max(x, 3), 97), 2), round(min(max(y, 5), 95), 2)
            pts.append((x, y))
            stars.append(dict(p=p, sec=s, x=x, y=y, size=7 + h[2] % 3 * 2))
        for i in range(1, len(pts)):
            j = min(range(i), key=lambda m: (pts[m][0] - pts[i][0]) ** 2 * 6 + (pts[m][1] - pts[i][1]) ** 2)
            lines.append((s["id"], pts[j], pts[i]))
        top = min(y for _, y in pts) if pts else cy
        labels.append(dict(sec=s, x=cx, y=round(max(top - 5, 4), 2)))
    return stars, lines, labels


def start_html(cat, total):
    starters = [p for s in cat["sections"] for p in s["pages"] if p.get("starter")]
    cards = "".join(
        f"<li><a class=\"scard\" href=\"{e(p['slug'])}/\" data-slug=\"{e(p['slug'])}\">"
        f"<img src=\"{e(p['slug'])}/thumb.webp\" width=\"640\" height=\"336\" alt=\"\" loading=\"lazy\" decoding=\"async\">"
        f"<span><b>{e(p['title'])}</b><i>{e(p['starter'])}</i></span></a></li>" for p in starters)
    return ("<section class=\"start\" aria-labelledby=\"h-start\">\n<div class=\"start-top\"><h2 id=\"h-start\">Not sure where to start?</h2>"
            f"<div class=\"search\"><label class=\"vh\" for=\"find\">Search all {total} pages</label>"
            f"<input id=\"find\" type=\"search\" placeholder=\"Search all {total} pages\u2026\" autocomplete=\"off\"></div></div>\n"
            "<p class=\"vh\" id=\"hitcount\" role=\"status\" aria-live=\"polite\"></p>\n"
            "<ul class=\"hits\" id=\"hits\" hidden></ul>\n<p class=\"nomatch\" id=\"nomatch\" hidden></p>\n"
            f"<ul class=\"starters\">{cards}</ul>\n</section>\n")


def index_html(cat):
    site = cat["site"]
    pages = [p for s in cat["sections"] for p in s["pages"]]
    names = [x["name"][0].lower() + x["name"][1:] if not x["name"].startswith("AI") else x["name"] for x in cat["sections"]]
    desc = f"{site['intro']} {len(pages)} pages on {', '.join(names[:-1])}, and {names[-1]}."
    stars, lines, labels = sky(cat)
    rng = __import__("random").Random(7)
    out = ["<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
           f"<title>{e(site['title'])}</title>\n"
           f"<meta name=\"description\" content=\"{e(desc)}\">\n"
           f"<link rel=\"canonical\" href=\"{e(site['url'])}\">\n"
           "<link rel=\"icon\" href=\"favicon.svg\" type=\"image/svg+xml\">\n"
           "<meta name=\"theme-color\" content=\"#090D20\">\n"
           f"<meta name=\"author\" content=\"{e(site['author'])}\">\n"
           "<meta property=\"og:type\" content=\"website\">\n"
           f"<meta property=\"og:title\" content=\"{e(site['title'])}\">\n"
           f"<meta property=\"og:description\" content=\"{e(desc)}\">\n"
           f"<meta property=\"og:url\" content=\"{e(site['url'])}\">\n"
           f"<meta property=\"og:image\" content=\"{e(site['url'])}card.jpg\">\n"
           "<meta property=\"og:image:width\" content=\"1200\">\n"
           "<meta property=\"og:image:height\" content=\"630\">\n"
           "<meta name=\"twitter:card\" content=\"summary_large_image\">\n"
           f"{ATLAS_FONTS}\n<style>\n{ATLAS_CSS}\n</style>\n</head>\n<body>\n<div class=\"wrap\">\n"
           f"<header class=\"top\">\n<h1 class=\"mark\"><a href=\"./\">{e(site['title'])}</a>"
           f"<small>A star atlas of {len(pages)} ideas · curated by {e(site['author'])}</small></h1>\n"
           "<nav aria-label=\"Site\"><a href=\"#atlas\">The sky</a><a href=\"#constellations\">Every page</a>"
           f"<a href=\"{e(site['handbook'])}\">DS/ML Handbook</a>"
           f"<a href=\"{e(site['linkedin'])}\" rel=\"me noopener\">LinkedIn</a>"
           "<a href=\"#suggest\">Suggest an idea</a></nav>\n</header>\n<main>\n"
           "<section class=\"hero\">\n<h2 class=\"vh\">Start here</h2>\n"
           "<p class=\"serif\" style=\"margin:0;font-weight:500;font-size:clamp(2.4rem,6vw,4.4rem);line-height:1.02;"
           "letter-spacing:-.02em;max-width:15ch;color:#fff;text-wrap:balance\">Every star is an idea you can <em>play with.</em></p>\n"
           f"<p>{e(site['intro'])} Pick a star to see its question. Each one you open stays lit, so your sky slowly fills in.</p>\n"
           "</section>\n"
           + start_html(cat, len(pages)) + "<section id=\"atlas\" aria-label=\"The star atlas\" style=\"scroll-margin-top:12px\">\n<div class=\"stage\">\n"
           "<div class=\"scroll\"><div class=\"sky\">\n"]
    for _ in range(110):
        out.append(f"<span class=\"dust\" aria-hidden=\"true\" style=\"left:{rng.uniform(.5, 99.5):.2f}%;top:{rng.uniform(.5, 99.5):.2f}%;"
                   f"animation-delay:-{rng.uniform(0, 3.4):.2f}s\"></span>")
    out.append("\n<svg viewBox=\"0 0 100 100\" preserveAspectRatio=\"none\" aria-hidden=\"true\">")
    for sid, a, b in lines:
        out.append(f"<line data-sec=\"{e(sid)}\" x1=\"{a[0]}\" y1=\"{a[1]}\" x2=\"{b[0]}\" y2=\"{b[1]}\"></line>")
    out.append("</svg>\n")
    for lb in labels:
        s = lb["sec"]
        out.append(f"<button type=\"button\" class=\"label\" data-sec=\"{e(s['id'])}\" style=\"left:{lb['x']}%;top:{lb['y']}%\">"
                   f"{e(SHORT.get(s['id'], s['name']))}<span>{len(s['pages'])}</span></button>\n")
    for st in stars:
        p = st["p"]
        out.append(f"<button type=\"button\" class=\"star\" aria-label=\"{e(p['title'])}\" aria-pressed=\"false\" "
                   f"style=\"left:{st['x']}%;top:{st['y']}%;--s:{st['size']}px\"><i></i></button>\n")
    first = pages[0]
    out.append("</div></div>\n"
               "<p class=\"swipe\" aria-hidden=\"true\">Swipe the sky sideways to see every constellation →</p>\n"
               "<article class=\"card\" aria-live=\"polite\">\n"
               f"<img id=\"c-img\" src=\"{e(first['slug'])}/thumb.webp\" width=\"640\" height=\"336\" alt=\"\">\n"
               f"<div class=\"in\"><div class=\"kicker\" id=\"c-sec\">{e(SHORT.get(cat['sections'][0]['id'], cat['sections'][0]['name']))}</div>\n"
               f"<h2 id=\"c-title\">{e(first['title'])}</h2>\n"
               f"<p id=\"c-ask\">{e(first.get('ask') or first['blurb'])}</p>\n"
               f"<div class=\"go\"><a class=\"pill\" id=\"c-go\" href=\"{e(first['slug'])}/\">Visit this star</a></div></div>\n"
               "</article>\n</div>\n"
               "<div class=\"bar\" role=\"group\" aria-label=\"Light up a constellation\">\n"
               "<button type=\"button\" class=\"chip\" data-sec=\"\" aria-pressed=\"true\">Whole sky</button>\n")
    for s in cat["sections"]:
        out.append(f"<button type=\"button\" class=\"chip\" data-sec=\"{e(s['id'])}\" aria-pressed=\"false\">{e(SHORT.get(s['id'], s['name']))}</button>\n")
    out.append("<div class=\"find\">"
               "<button type=\"button\" class=\"pill\" id=\"shoot\">Catch a shooting star</button></div>\n</div>\n"
               "<p class=\"tally\" id=\"tally\">Each page you open stays lit in your sky, on this device.</p>\n</section>\n"
               "<section class=\"cons\" id=\"constellations\">\n<h2>Every page, by constellation</h2>\n"
               "<p>The same sky as a plain list. Gold dots are the pages you have already opened.</p>\n<div class=\"groups\">\n")
    for s in cat["sections"]:
        out.append(f"<section class=\"group\" id=\"{e(s['id'])}\" aria-labelledby=\"h-{e(s['id'])}\">\n"
                   f"<h3 id=\"h-{e(s['id'])}\">{e(s['name'])}<small>{len(s['pages'])} stars</small></h3>\n<ul>\n")
        for p in s["pages"]:
            note = f" · {e(p['note'])}" if p.get("note") else ""
            out.append(f"<li><a href=\"{e(p['slug'])}/\" data-slug=\"{e(p['slug'])}\"><span><b>{e(p['title'])}</b>"
                       f"<i>{e(p['blurb'])}{note}</i></span></a></li>\n")
        out.append(f"</ul>\n<p style=\"margin:8px 0 0\"><button type=\"button\" class=\"chip\" style=\"border:0;padding-inline:0;color:var(--gold)\" "
                   f"data-light=\"{e(s['id'])}\">Light up this constellation ↑</button></p>\n</section>\n")
    data = json.dumps([dict(slug=st["p"]["slug"], title=st["p"]["title"], ask=st["p"].get("ask") or st["p"]["blurb"],
                            hasAsk=bool(st["p"].get("ask")), blurb=st["p"]["blurb"], sec=st["sec"]["id"],
                            secName=SHORT.get(st["sec"]["id"], st["sec"]["name"])) for st in stars],
                      ensure_ascii=False).replace("</", "<\\/")
    ask_body = "What idea or question would you like explained?\n\n\n\nWhy does it matter to you? (optional)\n"
    issue = f"{site['repo']}/issues/new?" + urllib.parse.urlencode({"title": "Idea: ", "body": ask_body}, quote_via=urllib.parse.quote)
    mail = f"mailto:{site['email']}?" + urllib.parse.urlencode({"subject": "An idea for Explainers", "body": ask_body}, quote_via=urllib.parse.quote)
    out.append("</div>\n</section>\n"
               "<section class=\"suggest\" id=\"suggest\" aria-labelledby=\"h-suggest\">\n<div>\n"
               "<h2 id=\"h-suggest\">Is there an idea you wish someone would explain?</h2>\n"
               "<p>Tell me what you are curious about. The best ones become a new star.</p>\n</div>\n"
               f"<div class=\"acts\"><a class=\"pill\" href=\"{e(issue)}\" rel=\"noopener\">Suggest on GitHub</a>"
               f"<a class=\"ghost\" href=\"{e(mail)}\">Or send an email</a></div>\n</section>\n</main>\n<footer class=\"foot\">\n"
               f"<p>Curated by {e(site['author'])}, one idea at a time. "
               f"<a href=\"{e(site['linkedin'])}\" rel=\"me noopener\">LinkedIn</a> · <a href=\"{e(site['github'])}\">GitHub</a>.</p>\n"
               f"<p>For data science and machine learning, there is also the <a href=\"{e(site['handbook'])}\">DS/ML Learning Handbook</a>.</p>\n"
               "<p>These pages are for understanding. The health pages are not medical advice.</p>\n"
               "</footer>\n</div>\n"
               f"<script type=\"application/json\" id=\"atlas-data\">{data}</script>\n<script>\n{ATLAS_JS}\n</script>\n"
               "</body>\n</html>\n")
    return "".join(out)


def notfound_html(site):
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
            f"<title>Page not found | {e(site['title'])}</title>\n<meta name=\"robots\" content=\"noindex\">\n"
            f"{ATLAS_FONTS}\n<style>\n{ATLAS_CSS}\n.lost{{padding-block:18vh}}.lost p{{color:var(--soft)}}\n</style>\n</head>\n<body>\n"
            "<div class=\"wrap lost\">\n<p class=\"serif\" style=\"margin:0;font-size:clamp(2.2rem,6vw,4rem);line-height:1.05;color:#fff\">"
            "This star has drifted <em style=\"color:var(--gold)\">out of the sky.</em></p>\n"
            "<p style=\"margin:20px 0 28px\">The address may have changed, or the page was never published.</p>\n"
            f"<a class=\"pill\" href=\"{e(site['url'])}\">Back to the star atlas</a>\n</div>\n</body>\n</html>\n")


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
