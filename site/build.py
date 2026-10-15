"""Free Tier Watch sitesini uretir: data/plans.json + data/manual/*.json + config/site.json -> _site/"""
import json
import pathlib
import datetime
import re
from html import escape as e

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
REPO = "https://github.com/mww872-lgtm/freetierwatch"
ICON = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%230a1114'/%3E%3Ccircle cx='16' cy='16' r='7' fill='%233ddbb0'/%3E%3C/svg%3E"
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


def collect_services():
    plans = load(ROOT / "data" / "plans.json", {"services": {}}).get("services", {})
    site = load(ROOT / "config" / "site.json")
    hide = site.get("hide", {})
    result = []
    for sid in site["order"]:
        cfg = site["services"][sid]
        manual = load(ROOT / "data" / "manual" / f"{sid}.json")
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
    return result


def limit_line(l):
    return f"{l['topic']}: {l['value']}"


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
        f'<div class="m"><p class="sum">{e(cfg["summary"])}</p>{note}'
        f'{"<ul class=feat>" + bullets + "</ul>" if bullets else ""}{details}</div>'
        f'<div class="r"><span class="st {cfg["status"]}">{LABEL[cfg["status"]]}</span>'
        f'<div class="when">Checked {checked}</div></div></article>'
    )


CSS = """
:root{--p:#0a1114;--sf:#111c21;--sf2:#16252b;--ln:#223239;--ink:#e5f0ed;--mu:#8ea6a4;--ac:#3ddbb0;--wa:#ffb84d;--no:#ff7a7a;color-scheme:dark}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--p);color:var(--ink);font:16px/1.55 "Bricolage Grotesque",system-ui,sans-serif;
 padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.in{max-width:1000px;margin:0 auto}
a{color:var(--ac)}
header.top{display:flex;flex-wrap:wrap;gap:12px 24px;justify-content:space-between;align-items:center;padding:20px 0}
.logo{font-weight:700;font-size:19px;display:flex;gap:10px;align-items:center;color:var(--ink);text-decoration:none}
.logo::before{content:"";width:12px;height:12px;border-radius:50%;background:var(--ac);box-shadow:0 0 0 4px rgba(61,219,176,.18)}
nav{display:flex;gap:18px;flex-wrap:wrap;font-size:15px}
nav a{color:var(--mu);text-decoration:none}nav a:hover{color:var(--ink)}
h1{font-size:clamp(32px,5.6vw,56px);line-height:1.04;letter-spacing:-.03em;margin:30px 0 12px;font-weight:700;max-width:16ch;text-wrap:balance}
.sub{color:var(--mu);max-width:56ch;margin:0 0 22px;font-size:18px}
.pulse{display:flex;gap:10px 22px;flex-wrap:wrap;font:13px "DM Mono",monospace;color:var(--mu);margin-bottom:20px}
.pulse b{color:var(--ac);font-weight:500}
.tbl{background:var(--sf);border:1px solid var(--ln);border-radius:12px;overflow:hidden}
.row{display:grid;grid-template-columns:200px minmax(0,1fr) 150px;gap:10px 28px;padding:22px 24px;border-top:1px solid var(--ln)}
.row:first-child{border-top:0}
.l,.m,.r{min-width:0}
.r{display:flex;flex-direction:column;align-items:flex-end;gap:8px}
@media(max-width:720px){.row{grid-template-columns:1fr;padding:18px}.r{flex-direction:row;align-items:center;justify-content:space-between}}
.nm{font-weight:700;font-size:22px;margin:0 0 8px}
.st{font:11px "DM Mono",monospace;padding:3px 8px;border-radius:99px;border:1px solid currentColor;white-space:nowrap}
.st.verified{color:var(--ac)}.st.partial{color:var(--wa)}.st.none{color:var(--no)}
.num{font-size:34px;line-height:1;font-weight:700;letter-spacing:-.03em;margin-top:6px}
.num small{display:block;font:12px "DM Mono",monospace;letter-spacing:0;color:var(--mu);margin-top:6px;font-weight:400}
.sum{margin:0 0 6px;color:var(--ink);font-size:15px}
.cnote{margin:0 0 6px;color:var(--wa);font-size:13px}
ul.feat{list-style:none;margin:12px 0 0;padding:12px 0 0;border-top:1px dashed var(--ln);display:grid;gap:4px;font-size:14px;color:var(--mu)}
ul.feat li::before{content:"+ ";color:var(--ac);font-family:"DM Mono",monospace}
details{margin-top:12px;font-size:14px}
summary{cursor:pointer;color:var(--ac);font:13px "DM Mono",monospace}
summary:focus-visible,a:focus-visible{outline:2px solid var(--ac);outline-offset:3px}
ul.src{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:12px}
ul.src b{display:block;font-weight:600}
ul.src q{display:block;color:var(--mu);font-size:13px;margin:2px 0;quotes:"\\201C" "\\201D"}
ul.src a{font:12px "DM Mono",monospace}
.how{color:var(--mu);font-size:13px;margin:10px 0 0}
.when{font:11px "DM Mono",monospace;color:var(--mu)}
section{margin-top:44px}
h2{font-size:26px;letter-spacing:-.02em;margin:0 0 12px}
.panel{background:var(--sf2);border:1px solid var(--ln);border-radius:12px;padding:20px;max-width:70ch}
.panel p{margin:0 0 8px}.panel p:last-child{margin:0}
footer{margin:56px 0 40px;padding-top:20px;border-top:1px solid var(--ln);color:var(--mu);font-size:14px;max-width:70ch}
.page h1{font-size:clamp(30px,5vw,44px);max-width:22ch}
.page h2{margin-top:34px}
.page p,.page li{max-width:66ch;color:var(--ink)}
.page li{margin:6px 0}
.kind{display:grid;gap:10px;margin:14px 0}
.kind div{background:var(--sf);border:1px solid var(--ln);border-radius:10px;padding:12px 14px}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" '
         'href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=DM+Mono:wght@400;500&display=swap">')


def shell(title, desc, body, page=False):
    err = f"{REPO}/issues/new?title=Error%20report%3A%20&body=Which%20service%3F%0AWhat%20is%20wrong%3F%0ALink%20to%20the%20official%20page%3A%20"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        f"<title>{e(title)}</title><meta name=\"description\" content=\"{e(desc)}\">"
        f'<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:type" content="website"><meta name="twitter:card" content="summary">'
        f'<link rel="icon" href="{ICON}">{FONTS}<style>{CSS}</style></head>'
        f'<body><div class="in{" page" if page else ""}"><header class="top"><a class="logo" href="index.html">Free Tier Watch</a>'
        f'<nav><a href="index.html#services">Services</a><a href="index.html#this-week">This week</a>'
        f'<a href="how-we-check.html">How we check</a><a href="{err}" rel="noopener">Report an error</a></nav></header>'
        f"{body}"
        '<footer>Free Tier Watch is independent. We are not affiliated with any company listed here and we run no ads or sponsors. '
        "Plans change often and mistakes can happen, so always confirm on the official page before you rely on a limit. "
        f'Found something wrong? <a href="{err}" rel="noopener">Tell us</a>.</footer></div></body></html>'
    )


def this_week(services):
    changes = load(ROOT / "data" / "changes.json", {}) or {}
    items = changes.get("services", changes)
    changed = [k for k, v in items.items() if isinstance(v, dict) and v.get("status") == "changed"] if isinstance(items, dict) else []
    names = {s["id"]: s["name"] for s in services}
    if changed:
        lst = ", ".join(names.get(c, c.title()) for c in changed)
        txt = f"Pages changed since the last check: {lst}. We compare the new text with the old one and update the cards above after review."
    else:
        txt = "This is our first full check. From next Monday this section lists what changed on the free plans."
    return f'<section id="this-week"><h2>This week</h2><div class="panel"><p>{e(txt)}</p></div></section>'


def index(services):
    counts = {k: sum(1 for s in services if s["cfg"]["status"] == k) for k in LABEL}
    dates = [s["checked"] for s in services if s["checked"]]
    last = pretty_date(max(dates)) if dates else "not yet"
    body = (
        '<h1>The free plans, checked weekly.</h1>'
        '<p class="sub">What each AI chat app gives you for $0, with the source and the exact quote behind every line.</p>'
        f'<div class="pulse"><span><b>{len(services)}</b> services</span><span><b>{counts["verified"]}</b> verified</span>'
        f'<span><b>{counts["partial"]}</b> partly stated</span><span><b>{counts["none"]}</b> unverified</span><span>Last check: {last}</span></div>'
        f'<section id="services" style="margin-top:0"><div class="tbl">{"".join(card(s) for s in services)}</div></section>'
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
<p>The data and the code of this site are public: <a href="%s" rel="noopener">%s</a></p>
""" % (REPO, REPO.replace("https://", ""))
    return shell("How we check - Free Tier Watch", "How Free Tier Watch collects and verifies free plan information.", body, page=True)


def main():
    services = collect_services()
    check_claims(services)
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(index(services), encoding="utf-8")
    (OUT / "how-we-check.html").write_text(method(), encoding="utf-8")
    public = [{"id": s["id"], "name": s["name"], "status": s["cfg"]["status"], "checked": s["checked"],
               "limits": s["limits"], "features": s["features"]} for s in services]
    (OUT / "data.json").write_text(json.dumps(public, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok:", [p.name for p in OUT.iterdir()])


if __name__ == "__main__":
    main()
