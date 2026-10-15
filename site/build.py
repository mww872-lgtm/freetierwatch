"""Free Tier Watch sitesini uretir: data/plans.json + data/manual/*.json + config/site.json -> _site/"""
import json
import os
import pathlib
import datetime
import re
from html import escape as e

import compare

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Haftalik veri (plans, manual, history, snapshots...) ozel depoda tutulur; FTW_DATA_DIR o klasoru gosterir.
DATA = pathlib.Path(os.environ["FTW_DATA_DIR"]) if os.environ.get("FTW_DATA_DIR") else ROOT / "data"
OUT = ROOT / "_site"
REPO = "https://github.com/mww872-lgtm/freetierwatch"
ICON = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%2316181D'/%3E%3Cpath d='M7 11h18M7 15h18M7 21h12' stroke='%23F5F5F2' stroke-width='2.4' fill='none'/%3E%3C/svg%3E"

# Tema: ziyaretci secer (varsayilan acik), secim bu tarayicida hatirlanir. Sayfa cizilmeden once uygulanir (titreme olmasin).
THEME_HEAD = ("(function(){var d=document.documentElement;d.className+=' js';var t=null;"
              "try{t=localStorage.getItem('ftw-theme')}catch(x){}"
              "d.setAttribute('data-theme',t==='dark'?'dark':'light')})();")
THEME_BODY = ("(function(){var d=document.documentElement,bs=document.querySelectorAll('.tgl button');"
              "function set(t,save){d.setAttribute('data-theme',t);"
              "for(var i=0;i<bs.length;i++){bs[i].setAttribute('aria-pressed',String(bs[i].getAttribute('data-t')===t))}"
              "if(save){try{localStorage.setItem('ftw-theme',t)}catch(x){}}}"
              "set(d.getAttribute('data-theme')||'light',false);"
              "for(var i=0;i<bs.length;i++){bs[i].addEventListener('click',function(){set(this.getAttribute('data-t'),true)})}})();")
LABEL = {"verified": "Verified", "partial": "Partly stated", "none": "Couldn't verify"}


def load(path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def pretty_date(iso):
    try:
        d = datetime.date.fromisoformat(iso)
        return d.strftime("%b ") + str(d.day) + d.strftime(", %Y")
    except (TypeError, ValueError):
        return "unknown"


def host(url):
    return url.split("//", 1)[-1].split("/", 1)[0].replace("www.", "")


def clean_quote(text):
    """Resmi sayfadan gelen sondaki dipnot numarasini ('Google Flow3') gosterimden siler."""
    return re.sub(r"(?<=[A-Za-z])\d{1,2}$", "", str(text or "")).strip()


NUMWORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
            "seven": "7", "eight": "8", "nine": "9", "ten": "10"}


def numbers_in(text):
    words = re.sub(r"[a-z]+", lambda m: NUMWORDS.get(m.group(0), m.group(0)), str(text).lower())
    return set(re.findall(r"\d[\d.,]*\d|\d", words))


def check_claims(services):
    """Ozet, buyuk rakam ve etiketteki her sayi, altindaki alintilarda gecmiyorsa siteyi uretme."""
    problems = []
    for s in services:
        if s["cfg"]["status"] == "none":
            continue
        quotes = " ".join(
            str(x.get("evidence", "")) + " " + str(x.get("value", ""))
            for x in s["limits"] + s["features"]
        )
        have = numbers_in(quotes)
        said = numbers_in(" ".join([s["cfg"]["summary"], s["cfg"]["big"], s["cfg"]["label"]]))
        missing = sorted(said - have)
        if missing:
            problems.append(f"{s['name']}: {', '.join(missing)} sayisi hicbir alintida gecmiyor")
    if problems:
        raise SystemExit("HATA: ozette kaynaksiz iddia var:\n  " + "\n  ".join(problems))


def previous_history(sid, checked):
    """Bu servisin, su anki kontrolden onceki en yeni arsiv kaydi (yoksa None)."""
    folder = DATA / "history" / sid
    best = None
    if folder.exists() and checked:
        for p in sorted(folder.glob("*.json")):
            if p.stem < checked:
                best = p
    return load(best) if best else None


def collect_services():
    plans = load(DATA / "plans.json", {"services": {}}).get("services", {})
    site = load(ROOT / "config" / "site.json")
    hide = site.get("hide", {})
    result = []
    for sid in site["order"]:
        cfg = site["services"][sid]
        manual = load(DATA / "manual" / f"{sid}.json")
        auto = plans.get(sid)
        src = manual or auto or {}
        ext = (src.get("extracted") or {}) if cfg["status"] != "none" else {}
        result.append({
            "id": sid,
            "name": src.get("name") or sid.title(),
            "cfg": cfg,
            "features": [{**f, "evidence": clean_quote(f.get("evidence"))} for f in ext.get("features", []) if f.get("feature") not in hide.get(sid, [])],
            "limits": [{**l, "evidence": clean_quote(l.get("evidence"))} for l in ext.get("limits", []) if l.get("topic") not in hide.get(sid, [])],
            "checked": src.get("last_checked"),
            "sources": src.get("sources", []),
            "manual": bool(manual),
        })
    for s in result:
        s["changes"], s["prev"] = [], None
        old = previous_history(s["id"], s["checked"])
        if old and old.get("status") != "none" and s["cfg"]["status"] != "none":
            h = hide.get(s["id"], [])
            s["changes"] = compare.compare(
                compare.items(old.get("limits"), old.get("features"), h),
                compare.items(s["limits"], s["features"], h),
            )
            s["prev"] = old.get("date")
    return result


def limit_line(l):
    return f"{l['topic']}: {l['value']}"


SVG = '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">%s</svg>'
ICON_OF = {
    "down": SVG % '<path d="M7 2v10M3 8l4 4 4-4"/>',
    "up": SVG % '<path d="M7 12V2M3 6l4-4 4 4"/>',
    "shape": SVG % '<path d="M2 5h10M9 2l3 3-3 3M12 9H2M5 12l-3-3 3-3"/>',
}
ICON_OF["mixed"] = ICON_OF["shape"]
ICON_OF["removed"] = ICON_OF["down"]
ICON_OF["added"] = ICON_OF["up"]


def reference_week(prev, cur):
    """Aralik 10 gunden kisaysa 'last week', degilse tarihi yazar (yanlis 'gecen hafta' demeyelim)."""
    try:
        gap = (datetime.date.fromisoformat(cur) - datetime.date.fromisoformat(prev)).days
    except (TypeError, ValueError):
        return "the last check"
    return "last week" if gap <= 10 else f"the {pretty_date(prev)} check"


def pill_text(kind, ref):
    return {"down": f"Less generous than {ref}", "up": f"More generous than {ref}",
            "mixed": f"Mixed changes since {ref}", "shape": f"Limit works differently than {ref}"}[kind]


def quote_span(item, date):
    link = f' <a href="{e(item["source"])}" rel="noopener">{e(host(item["source"]))}</a>' if item.get("source") else ""
    return f'<span>{e(pretty_date(date))}: <q>{e(item["quote"])}</q>{link}</span>'


def change_row(c, prev, cur):
    d, o, n = c["dir"], c["old"], c["new"]
    if d == "added":
        old_t, new_t = "not listed", (n["value"] if n["limit"] else "listed")
    elif d == "removed":
        old_t, new_t = (o["value"] if o["limit"] else "listed"), "no longer listed"
    else:
        old_t, new_t = o["value"], n["value"]
    quotes = ""
    if o:
        quotes += quote_span(o, prev)
    if n:
        quotes += quote_span(n, cur)
    return (f'<li class="{d}"><div class="cr"><b>{e(c["label"])}</b>'
            f'<span class="cv"><span class="ov">{e(str(old_t))}</span>{ICON_OF[d]}<span class="nv">{e(str(new_t))}</span></span></div>'
            f'<div class="cq">{quotes}</div></li>')


def change_block(s):
    ch = s.get("changes") or []
    if not ch:
        return ""
    kind = compare.overall(ch)
    ref = reference_week(s["prev"], s["checked"])
    rows = "".join(change_row(c, s["prev"], s["checked"]) for c in ch)
    return (f'<details class="chg"><summary class="pill {kind}">{ICON_OF[kind]}<span>{e(pill_text(kind, ref))}</span></summary>'
            f'<div class="chgbox"><div class="chgh">What changed · {e(pretty_date(s["prev"]))} to {e(pretty_date(s["checked"]))}</div>'
            f'<ul class="chgl">{rows}</ul>'
            '<p class="how">Only items that changed are listed, each with the official quote from both checks.</p></div></details>')


def card(s):
    cfg = s["cfg"]
    lines = []
    for l in s["limits"]:
        if str(l.get("value", "")).lower().startswith("not officially"):
            continue
        lines.append(limit_line(l))
    lines += [f["feature"] for f in s["features"]]
    shown, more = lines[:3], lines[3:]
    bullets = "".join(f"<li>{e(x)}</li>" for x in shown)
    detail_rows = ""
    for l in s["limits"]:
        if str(l.get("value", "")).lower().startswith("not officially"):
            continue
        detail_rows += f'<li><b>{e(limit_line(l))}</b><q>{e(l["evidence"])}</q><a href="{e(l["source"])}" rel="noopener">{e(host(l["source"]))}</a></li>'
    for f in s["features"]:
        detail_rows += f'<li><b>{e(f["feature"])}</b><q>{e(f["evidence"])}</q><a href="{e(f["source"])}" rel="noopener">{e(host(f["source"]))}</a></li>'
    note = f'<p class="cnote">{e(cfg["note"])}</p>' if cfg.get("note") else ""
    how = "Read by hand from the official page." if s["manual"] else "Read automatically, quotes checked against the page."
    details = ""
    if detail_rows:
        extra = f" (+{len(more)} more)" if more else ""
        details = f'<details><summary>Sources and quotes{extra}</summary><ul class="src">{detail_rows}</ul><p class="how">{how}</p></details>'
    elif s["id"] == "deepseek":
        details = '<details><summary>Why no data?</summary><p class="how">The only official page we found has too little information about a free plan. We do not guess.</p></details>'
    checked = pretty_date(s["checked"]) if s["checked"] else "not checked"
    return (
        f'<article class="row" id="{e(s["id"])}">'
        f'<div class="l"><h3 class="nm">{e(s["name"])}</h3>'
        f'<div class="num">{e(cfg["big"])}<small>{e(cfg["label"])}</small></div></div>'
        f'<div class="m"><p class="sum">{e(cfg["summary"])}</p>{note}{change_block(s)}'
        f'{"<ul class=feat>" + bullets + "</ul>" if bullets else ""}{details}</div>'
        f'<div class="r"><span class="st {cfg["status"]}">{LABEL[cfg["status"]]}</span>'
        f'<div class="when">Checked {checked}</div></div></article>'
    )


CSS = """
:root{--p:#F5F5F2;--ink:#16181D;--mu:#5B6068;--soft:#3A3F47;--ln:#C9CBCF;--dot:#9A9DA3;--sf:#FFFFFF;--lk:#1F3A5F;--ok:#067647;--okbg:#ECFDF3;--no:#B42318;--nobg:#FEF3F2;--wa:#8A5300;--fl:#475467;--flbg:#F2F4F7;color-scheme:light}
:root[data-theme="dark"]{--p:#14161A;--ink:#ECEDEF;--mu:#A0A5AE;--soft:#C4C8CF;--ln:#3A3E46;--dot:#5A5F69;--sf:#1C1F25;--lk:#8FB0E8;--ok:#5FE39A;--okbg:#123222;--no:#FF9C94;--nobg:#3A1A1A;--wa:#FFB84D;--fl:#B5BAC3;--flbg:#272A31;color-scheme:dark}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--p);color:var(--ink);font:16px/1.55 "IBM Plex Sans",system-ui,sans-serif;
 padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.in{max-width:1120px;margin:0 auto}
a{color:var(--lk)}
a:focus-visible,button:focus-visible,summary:focus-visible{outline:2px solid var(--lk);outline-offset:3px}
.mast{padding:12px 0 20px;text-align:center;border-bottom:3px double var(--ink)}
.tgl{display:none;justify-content:flex-end;align-items:center;gap:2px;padding-bottom:10px;font:500 12px "IBM Plex Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--dot)}
html.js .tgl{display:flex}
.tgl button{background:none;border:0;padding:13px 8px;font:inherit;letter-spacing:inherit;text-transform:inherit;color:var(--mu);cursor:pointer}
.tgl button[aria-pressed="true"]{color:var(--ink);text-decoration:underline;text-underline-offset:5px}
.kick{font:12px "IBM Plex Mono",monospace;letter-spacing:.16em;text-transform:uppercase;color:var(--mu)}
.logo{display:block;margin-top:10px;font:700 clamp(40px,9vw,72px)/1 Fraunces,Georgia,serif;letter-spacing:-.02em;color:var(--ink);text-decoration:none}
nav{display:flex;flex-wrap:wrap;justify-content:center;gap:4px 28px;padding:6px 0;border-bottom:1px solid var(--ink);font-size:15px;font-weight:500}
nav a{color:var(--lk);text-decoration:none;padding:8px 2px}nav a:hover{text-decoration:underline}
.hero{display:flex;flex-wrap:wrap;gap:36px 56px;padding:52px 0 48px;align-items:flex-start}
.hero>div:first-child{flex:1 1 480px;min-width:0}
h1{font:500 clamp(32px,5.5vw,48px)/1.1 Fraunces,Georgia,serif;letter-spacing:-.01em;margin:0;text-wrap:balance}
.sub{color:var(--soft);max-width:56ch;margin:20px 0 0;font-size:18px;line-height:1.6}
.last{margin:18px 0 0;font:13px "IBM Plex Mono",monospace;color:var(--mu)}
.stats{flex:1 1 280px;min-width:0}
.stat{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:12px 0;border-top:1px solid var(--ink)}
.stat:last-child{border-bottom:1px solid var(--ink)}
.stat span{font-size:15px;color:var(--mu)}
.stat b{font:700 34px/1 Fraunces,Georgia,serif}
section{margin-top:0;padding-bottom:48px}
.sh{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:6px 16px;border-bottom:3px double var(--ink);padding-bottom:10px}
.sh h2{font:700 32px/1.2 Fraunces,Georgia,serif;margin:0}
.sh span{font:13px "IBM Plex Mono",monospace;color:var(--mu)}
.row{display:grid;grid-template-columns:200px minmax(0,1fr) 160px;gap:14px 28px;padding:24px 0;border-bottom:1px solid var(--ln)}
.l,.m,.r{min-width:0}
.r{display:flex;flex-direction:column;align-items:flex-end;gap:8px}
@media(max-width:720px){.row{grid-template-columns:1fr;padding:20px 0}.r{flex-direction:row;align-items:center;justify-content:space-between}.sh h2{font-size:28px}}
.nm{font:700 28px/1.1 Fraunces,Georgia,serif;margin:0}
.st{font:500 11px "IBM Plex Mono",monospace;padding:3px 9px;border-radius:99px;border:1px solid currentColor;white-space:nowrap}
.st.verified{color:var(--ok)}.st.partial{color:var(--wa)}.st.none{color:var(--no)}
.num{font:600 22px/1 "IBM Plex Mono",monospace;letter-spacing:-.02em;margin-top:14px;padding-top:14px;border-top:1px dotted var(--dot);color:var(--ink)}
.num small{display:block;font:12px/1.4 "IBM Plex Mono",monospace;letter-spacing:0;color:var(--mu);margin-top:8px;font-weight:400}
.sum{margin:0 0 6px;color:var(--ink);font-size:16px}
.cnote{margin:0 0 6px;color:var(--wa);font-size:14px}
ul.feat{list-style:none;margin:12px 0 0;padding:0;font-size:15px;color:var(--mu)}
ul.feat li{padding:6px 0;border-bottom:1px dotted var(--dot)}
ul.feat li:last-child{border-bottom:0}
details{margin-top:12px;font-size:14px}
summary{cursor:pointer;color:var(--lk);font:13px "IBM Plex Mono",monospace}
ul.src{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:14px}
ul.src b{display:block;font-weight:600}
ul.src q{display:block;color:var(--mu);font-size:13px;margin:2px 0;font-style:italic;quotes:"\\201C" "\\201D"}
ul.src a{font:12px "IBM Plex Mono",monospace}
.how{color:var(--mu);font-size:13px;margin:10px 0 0}
.when{font:11px "IBM Plex Mono",monospace;color:var(--mu)}
h2{font:700 26px/1.2 Fraunces,Georgia,serif;letter-spacing:-.01em;margin:0 0 12px}
.panel{background:var(--sf);border:1px solid var(--ink);padding:24px 28px}
.sh+.panel{margin-top:18px}
.panel p{margin:0 0 8px}.panel p:last-child{margin:0}
.panel ul{margin:8px 0 0;padding-left:20px}
footer{margin:16px 0 40px;padding-top:20px;padding-right:max(0px,calc(100% - 70ch));border-top:3px double var(--ink);color:var(--mu);font-size:14px}
.page h1{font-size:clamp(30px,5vw,44px);max-width:22ch;margin:44px 0 14px}
.page h2{margin-top:34px}
.page p,.page li{max-width:66ch;color:var(--ink)}
.page li{margin:6px 0}
.kind{display:grid;gap:10px;margin:14px 0}
.kind div{background:var(--sf);border:1px solid var(--ln);padding:12px 14px}
.chg{margin-top:12px}
.chg>summary{list-style:none;display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:99px;font:600 13px "IBM Plex Sans",sans-serif}
.chg>summary::-webkit-details-marker{display:none}
.chg>summary svg{flex:none}
.pill.down{color:var(--no);background:var(--nobg)}
.pill.up{color:var(--ok);background:var(--okbg)}
.pill.mixed,.pill.shape{color:var(--fl);background:var(--flbg)}
.chgbox{margin-top:12px;padding:16px 20px;background:var(--sf);border:1px solid var(--ink)}
.chgh{font:12px "IBM Plex Mono",monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--mu);margin-bottom:6px}
ul.chgl{list-style:none;margin:0;padding:0}
ul.chgl>li{padding:12px 0;border-top:1px solid var(--ln)}
.cr{display:flex;flex-wrap:wrap;gap:6px 16px;justify-content:space-between;align-items:baseline}
.cr b{font-weight:600}
.cv{display:inline-flex;align-items:center;gap:10px;flex-wrap:wrap;font:14px "IBM Plex Mono",monospace}
.cv .ov{color:var(--mu)}
li.down .nv,li.removed .nv{color:var(--no)}
li.up .nv,li.added .nv{color:var(--ok)}
li.down svg,li.removed svg{color:var(--no)}
li.up svg,li.added svg{color:var(--ok)}
li.shape svg{color:var(--fl)}
.cq{display:grid;gap:4px;margin-top:6px;font-size:13px;color:var(--mu)}
.cq q{font-style:italic;quotes:"\\201C" "\\201D"}
.cq a{font:12px "IBM Plex Mono",monospace}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" '
         'href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">')


def shell(title, desc, body, page=False):
    err = f"{REPO}/issues/new?title=Error%20report%3A%20&body=Which%20service%3F%0AWhat%20is%20wrong%3F%0ALink%20to%20the%20official%20page%3A%20"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        f"<title>{e(title)}</title><meta name=\"description\" content=\"{e(desc)}\">"
        f'<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:type" content="website"><meta name="twitter:card" content="summary">'
        f'<link rel="icon" href="{ICON}">{FONTS}<script>{THEME_HEAD}</script><style>{CSS}</style></head>'
        f'<body><div class="in{" page" if page else ""}"><header><div class="mast">'
        '<div class="tgl" role="group" aria-label="Color theme"><button type="button" data-t="light" aria-pressed="true">Light</button>'
        '<span aria-hidden="true">/</span><button type="button" data-t="dark" aria-pressed="false">Dark</button></div>'
        '<div class="kick">Independent · Weekly · Sourced</div><a class="logo" href="index.html">Free Tier Watch</a></div>'
        f'<nav aria-label="Main"><a href="index.html#services">The ledger</a><a href="index.html#this-week">This week</a>'
        f'<a href="how-we-check.html">How we check</a><a href="{err}" rel="noopener">Report an error</a></nav></header>'
        f"{body}"
        '<footer>Free Tier Watch is independent. We are not affiliated with any company listed here and we run no ads or sponsors. '
        "Plans change often and mistakes can happen, so always confirm on the official page before you rely on a limit. "
        'Our summaries and data may be quoted with credit to Free Tier Watch (CC BY 4.0). '
        f'Found something wrong? <a href="{err}" rel="noopener">Tell us</a>.</footer></div><script>{THEME_BODY}</script></body></html>'
    )


def this_week(services):
    changes = load(DATA / "changes.json", {}) or {}
    items = changes.get("services", changes)
    changed = [k for k, v in items.items() if isinstance(v, dict) and v.get("status") == "changed"] if isinstance(items, dict) else []
    names = {s["id"]: s["name"] for s in services}
    if changed:
        lst = ", ".join(names.get(c, c.title()) for c in changed)
        txt = f"Pages changed since the last check: {lst}. We compare the new text with the old one and update the cards above after review."
    elif any(s.get("changes") for s in services):
        txt = ""
    elif any(s.get("prev") for s in services):
        txt = "No changes in the free plans since the last check."
    else:
        txt = "This is our first full check. From next Monday this section lists what changed on the free plans."
    moved = [s for s in services if s.get("changes")]
    lst = ""
    if moved:
        items_html = "".join(
            f'<li><a href="#{e(s["id"])}">{e(s["name"])}</a>: '
            f'{e(pill_text(compare.overall(s["changes"]), reference_week(s["prev"], s["checked"])))}</li>'
            for s in moved
        )
        lst = f'<p>Changes in the free plans since the last check:</p><ul>{items_html}</ul>'
    dates = [s["checked"] for s in services if s["checked"]]
    stamp = f'Week of {pretty_date(max(dates))}' if dates else ""
    return (f'<section id="this-week"><div class="sh"><h2>This week</h2><span>{e(stamp)}</span></div>'
            f'<div class="panel">{"<p>" + e(txt) + "</p>" if txt else ""}{lst}</div></section>')


def index(services):
    counts = {k: sum(1 for s in services if s["cfg"]["status"] == k) for k in LABEL}
    dates = [s["checked"] for s in services if s["checked"]]
    last = pretty_date(max(dates)) if dates else "not yet"
    body = (
        '<div class="hero"><div><h1>What does each free AI plan really give you this week?</h1>'
        '<p class="sub">What each AI chat app gives you for $0, with the source and the exact quote behind every line.</p>'
        f'<p class="last">Last check: {e(last)}</p></div>'
        f'<div class="stats"><div class="stat"><span>Services followed</span><b>{len(services)}</b></div>'
        f'<div class="stat"><span>Verified</span><b>{counts["verified"]}</b></div>'
        f'<div class="stat"><span>Partly stated</span><b>{counts["partial"]}</b></div>'
        f'<div class="stat"><span>Couldn\'t verify</span><b>{counts["none"]}</b></div></div></div>'
        f'<section id="services"><div class="sh"><h2>The ledger</h2><span>Free chat plans only</span></div>'
        f'{"".join(card(s) for s in services)}</section>'
        f"{this_week(services)}"
    )
    return shell("Free Tier Watch", "What the free plans of AI chat apps really include, checked against official pages every week.", body)


def method():
    body = """
<h1>How we check</h1>
<p>Free Tier Watch exists to answer one question: what do you actually get on the free plan of an AI chat app? We try to be the referee, so the rules below are strict on purpose.</p>
<h2>What we cover</h2>
<p>Only the free plan of the consumer chat app. API, developer, business and paid plans are ignored, even when they share a page with the free plan.</p>
<h2>Where the information comes from</h2>
<ul><li>Official pages of each company: help centers, pricing pages and documentation.</li>
<li>Every line shows the page it came from, the exact sentence we found there and the date we last checked.</li>
<li>If a page does not say it, we do not say it. Missing information is shown as "not officially stated".</li></ul>
<h2>How a check works</h2>
<ul><li>Every Monday a program downloads the official pages and compares them with last week.</li>
<li>A language model reads the text and proposes facts. A line only stays if its quote exists word for word on the page, and a second check confirms the quote is about the free chat plan.</li>
<li>Where a company blocks automated access, a person reads the page by hand. If that is not possible either, the service is marked as not checked that week. We never try to get around a block.</li>
<li>Everything is published as it was found. Items we dropped are kept with the reason.</li></ul>
<h2>What the labels mean</h2>
<div class="kind"><div><span class="st verified">Verified</span><p>The main limits and features are stated on official pages and the quotes were checked.</p></div>
<div><span class="st partial">Partly stated</span><p>Some information is missing or two official pages disagree. We show only what is clear.</p></div>
<div><span class="st none">Couldn't verify</span><p>We found no reliable official source, so we make no claims.</p></div></div>
<h2>Our promises</h2>
<ul><li>No ads or sponsors for now. If that ever changes, it will be said here first.</li>
<li>What the companies say and what we tried ourselves are always shown separately.</li>
<li>Mistakes can happen. Use "Report an error" at the top and we will look at it.</li></ul>
<p>The code of this site is public: <a href="%s" rel="noopener">%s</a>. The data shown on each page is published with it (see <a href="data.json">data.json</a>). Our summaries and compiled data are free to quote under <a href="https://creativecommons.org/licenses/by/4.0/" rel="noopener">CC BY 4.0</a>; please credit Free Tier Watch. Text quoted from official pages belongs to its owners.</p>
""" % (REPO, REPO.replace("https://", ""))
    return shell("How we check - Free Tier Watch", "How Free Tier Watch collects and verifies free plan information.", body, page=True)


def main():
    services = collect_services()
    check_claims(services)
    for s in services:
        for c in s["changes"]:
            print(f"DEGISIKLIK [{s['id']}] {c['dir']}: {c['label']}: "
                  f"{(c['old'] or {}).get('value')} -> {(c['new'] or {}).get('value')}")
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(index(services), encoding="utf-8")
    (OUT / "how-we-check.html").write_text(method(), encoding="utf-8")
    public = [{"id": s["id"], "name": s["name"], "status": s["cfg"]["status"], "checked": s["checked"],
               "limits": s["limits"], "features": s["features"]} for s in services]
    (OUT / "data.json").write_text(json.dumps(public, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok:", [p.name for p in OUT.iterdir()])


if __name__ == "__main__":
    main()
