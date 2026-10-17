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
CONTACT = "freetierwatch@gmail.com"
SITE = "https://freetierwatch.com"  # sitenin gercek adresi: canonical, paylasim onizlemesi ve sitemap bundan uretilir
OG_IMAGE = "og.png"
ICON = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%2316181D'/%3E%3Cpath d='M7 11h18M7 15h18M7 21h12' stroke='%23F5F5F2' stroke-width='2.4' fill='none'/%3E%3C/svg%3E"


VENDOR = {"chatgpt": "OpenAI", "claude": "Anthropic", "gemini": "Google", "grok": "xAI",
          "copilot": "Microsoft", "perplexity": "Perplexity", "deepseek": "DeepSeek"}

# Tema: varsayilan KOYU; ziyaretci Light secerse bu tarayicida hatirlanir. Sayfa cizilmeden once uygulanir (titreme olmasin).
THEME_HEAD = ("(function(){var d=document.documentElement;d.className+=' js';var t=null;"
              "try{t=localStorage.getItem('ftw-theme')}catch(x){}"
              "d.setAttribute('data-theme',t==='light'?'light':'dark')})();")
THEME_BODY = ("(function(){var d=document.documentElement,b=document.getElementById('theme');"
              "function set(t,save){d.setAttribute('data-theme',t);if(b){b.textContent=t==='dark'?'Light':'Dark';b.setAttribute('aria-pressed',String(t==='dark'))}"
              "if(save){try{localStorage.setItem('ftw-theme',t)}catch(x){}}}"
              "set(d.getAttribute('data-theme')||'dark',false);"
              "if(b){b.addEventListener('click',function(){set(d.getAttribute('data-theme')==='dark'?'light':'dark',true)})}"
              "var ds=document.querySelectorAll('dialog');"
              "document.addEventListener('click',function(ev){var o=ev.target.closest('[data-open]');"
              "if(o){var m=document.getElementById('d-'+o.getAttribute('data-open'));if(m){if(m.showModal){m.showModal()}else{m.setAttribute('open','')}}return}"
              "var c=ev.target.closest('[data-close]');if(c){var p=c.closest('dialog');if(p){p.close()}return}"
              "if(ev.target.tagName==='DIALOG'){ev.target.close()}})})();")
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


def page_text(sid, date):
    """O gun kaydedilen resmi sayfa metni (yoksa None), karsilastirma icin sadelestirilmis."""
    if not date:
        return None
    try:
        return compare.norm_text((DATA / "snapshots" / sid / f"{date}.txt").read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return None


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
        s["changes"], s["dropped"], s["prev"] = [], [], None
        old = previous_history(s["id"], s["checked"])
        if old and old.get("status") != "none" and s["cfg"]["status"] != "none":
            h = hide.get(s["id"], [])
            found = compare.compare(
                compare.items(old.get("limits"), old.get("features"), h),
                compare.items(s["limits"], s["features"], h),
            )
            s["changes"], s["dropped"] = compare.confirm(
                found, page_text(s["id"], old.get("date")), page_text(s["id"], s["checked"]))
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


CHG_TEXT = {"down": ("▼", "tighter"), "up": ("▲", "more generous"),
            "mixed": ("◆", "mixed"), "shape": ("⇄", "works differently")}


def shown_items(s):
    """Kartta ve pencerede gosterilen satirlar: (baslik, deger, alinti, kaynak)."""
    out = []
    for l in s["limits"]:
        if str(l.get("value", "")).lower().startswith("not officially"):
            continue
        out.append((l["topic"], l.get("value", ""), l["evidence"], l["source"]))
    for f in s["features"]:
        out.append((f["feature"], "", f["evidence"], f["source"]))
    return out


def dialog(s):
    cfg = s["cfg"]
    items = shown_items(s)
    ch = s.get("changes") or []
    parts = [f'<div class="dhead"><h2>{e(s["name"])}</h2><button class="x" type="button" data-close aria-label="Close">×</button></div>',
             f'<p class="meta">{e(VENDOR.get(s["id"], ""))} · {LABEL[cfg["status"]]} · checked {e(pretty_date(s["checked"]) if s["checked"] else "not checked")}</p>']
    if ch:
        kind = compare.overall(ch)
        ref = reference_week(s["prev"], s["checked"])
        rows = "".join(change_row(c, s["prev"], s["checked"]) for c in ch)
        parts.append(f'<div class="chgbox"><div class="chgh">{e(pill_text(kind, ref))} · {e(pretty_date(s["prev"]))} to {e(pretty_date(s["checked"]))}</div>'
                     f'<ul class="chgl">{rows}</ul><p class="how">Only items that changed are listed, each with the official quote from both checks.</p></div>')
    if items:
        for title, value, quote, src in items:
            v = f' <span>· {e(str(value))}</span>' if value else ""
            parts.append(f'<div class="it"><h4>{e(title)}{v}</h4><blockquote>“{e(quote)}”</blockquote>'
                         f'<a href="{e(src)}" rel="noopener">{e(host(src))}</a></div>')
        how = "Read by hand from the official page." if s["manual"] else "Read automatically, quotes checked against the page."
        parts.append(f'<p class="how">{how}</p>')
    else:
        parts.append('<p>The only official page we found has too little information about a free plan. We do not guess.</p>')
    return f'<dialog id="d-{e(s["id"])}" aria-label="{e(s["name"])} sources"><div class="dbody">{"".join(parts)}</div></dialog>'


def card(s):
    cfg = s["cfg"]
    items = shown_items(s)
    ch = s.get("changes") or []
    if ch:
        kind = compare.overall(ch)
        sym, word = CHG_TEXT[kind]
        label = pill_text(kind, reference_week(s["prev"], s["checked"]))
        chg = (f'<button class="chg {kind}" type="button" data-open="{e(s["id"])}" aria-label="{e(label)}. Show what changed">'
               f'<i>{sym}</i>{word}</button>')
    else:
        chg = '<div class="chg"><i>–</i>no change</div>' if s.get("prev") else '<div class="chg"><i>–</i>first check</div>'
    note = f'<p class="note">{e(cfg["note"])}</p>' if cfg.get("note") else ""
    n = len(items)
    btn = (f'<span class="full">Quotes and sources ({n})</span><span class="short">Quotes ({n})</span>' if n else "Why no data?")
    checked = pretty_date(s["checked"]).rsplit(",", 1)[0] if s["checked"] else "not checked"
    return (
        f'<article class="card" id="{e(s["id"])}" style="--acc:var(--v-{e(s["id"])})">'
        f'<div class="card-head"><div><h2 class="name"><span class="dot"></span>{e(s["name"])}</h2>'
        f'<p class="vendor">{e(VENDOR.get(s["id"], ""))}</p></div><span class="chip {cfg["status"]}">{LABEL[cfg["status"]]}</span></div>'
        f'<div class="fig{" none" if cfg["status"] == "none" else ""}"><div class="fig-t"><b>{e(cfg["big"])}</b><em>{e(cfg["label"])}</em></div>{chg}</div>'
        f'<p class="sum">{e(cfg["summary"])}</p>{note}'
        f'<div class="srcrow"><button type="button" data-open="{e(s["id"])}">{btn}</button><span>Checked {e(checked)}</span></div></article>'
    )


def guide():
    rows = [("var(--ok)", "Verified", "Official page states the limits clearly."),
            ("var(--part)", "Partly stated", "Some limits are published, others are not."),
            ("var(--bad)", "Couldn't verify", "Not enough on the official page, so we make no claims."),
            ("var(--faint)", "▲ ▼ –", "Change since last week. Colors describe what it means for readers, not what a company intended.")]
    lis = "".join(f'<li><span class="sw" style="background:{c}"></span><b>{e(t)}</b> {e(d)}</li>' for c, t, d in rows)
    return f'<aside class="card guide"><h3>How to read this</h3><ul>{lis}</ul></aside>'


CSS = r"""
:root{--bg:#edf0f6;--surface:#fff;--surface2:#f5f7fb;--ink:#0e1a30;--mute:#586784;--faint:#8b97ae;--line:#d6dce9;--accent:#2a4bff;--ok:#0c8f63;--part:#a86a0a;--bad:#cc3b3b;--up:#0c8f63;--down:#cc3b3b;
--v-chatgpt:#2f7bff;--v-claude:#e0782a;--v-gemini:#8a63e8;--v-grok:#14a89a;--v-copilot:#d6478f;--v-perplexity:#1f9bb0;--v-deepseek:#6b7aa6;
--f-display:"Bricolage Grotesque","DM Sans",system-ui,sans-serif;--f-body:"DM Sans",system-ui,sans-serif;--f-mono:"JetBrains Mono",ui-monospace,Menlo,monospace;color-scheme:light}
:root[data-theme="dark"]{--bg:#0a1120;--surface:#121b2e;--surface2:#0e1627;--ink:#e6edfd;--mute:#96a4c0;--faint:#667693;--line:#243250;--accent:#86a2ff;--ok:#5fe0b0;--part:#f0bd5a;--bad:#ff8c86;--up:#5fe0b0;--down:#ff8c86;
--v-chatgpt:#6aa2ff;--v-claude:#f0a35e;--v-gemini:#b79af2;--v-grok:#4fd6c8;--v-copilot:#f08cbd;--v-perplexity:#5fd0e3;--v-deepseek:#97a6cf;color-scheme:dark}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 var(--f-body)}
a{color:inherit}:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.app{min-height:100%;display:grid;grid-template-rows:auto auto minmax(0,1fr) auto;gap:14px;padding:14px max(20px,env(safe-area-inset-right,0px)) 14px max(20px,env(safe-area-inset-left,0px));max-width:1480px;margin:0 auto}
.top{display:flex;align-items:center;gap:12px;flex-wrap:wrap;min-width:0}
.brand{display:flex;align-items:center;gap:9px;text-decoration:none;font:700 18px var(--f-display);letter-spacing:-.01em}
.logo{width:22px;height:22px;color:var(--accent)}
.tag{color:var(--mute);font-size:13px}
.pill{appearance:none;background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:3px 12px;font:500 12px var(--f-body);color:var(--mute);cursor:pointer;text-decoration:none}
.pill:hover{color:var(--ink);border-color:var(--mute)}
.right{margin-left:auto;display:flex;align-items:center;gap:10px}
.stamp{font:12px var(--f-mono);color:var(--mute);white-space:nowrap}
.hero{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap}
h1{margin:0;font:700 clamp(26px,3.4vw,44px)/1.02 var(--f-display);letter-spacing:-.03em;text-wrap:balance;max-width:20ch}
.hero-side{display:flex;flex-direction:column;align-items:flex-end;gap:7px;max-width:100%}
.counts{display:flex;gap:8px;flex-wrap:wrap}
.count{display:flex;align-items:baseline;gap:8px;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:6px 12px}
.count b{font:600 19px var(--f-mono);font-variant-numeric:tabular-nums}.count span{font-size:12px;color:var(--mute)}
.count.ok b{color:var(--ok)}.count.part b{color:var(--part)}.count.bad b{color:var(--bad)}
.week{margin:0;font-size:12.5px;color:var(--mute);text-align:right}.week b{color:var(--ink);font-weight:600}.week a{color:var(--accent);text-underline-offset:3px}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));grid-auto-rows:1fr;gap:12px;min-height:0}
.card{container-type:inline-size;--acc:var(--accent);background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px 15px 11px;display:flex;flex-direction:column;min-width:0}
.card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.name{display:flex;align-items:center;gap:9px;margin:0;font:700 clamp(19px,1.8vw,24px)/1 var(--f-display);letter-spacing:-.02em}
.dot{width:11px;height:11px;border-radius:50%;background:var(--acc);flex:none}
.vendor{margin:4px 0 0 20px;font:12px var(--f-mono);color:var(--mute)}
.chip{font:600 11px var(--f-mono);padding:3px 9px;border:1px solid currentColor;border-radius:999px;white-space:nowrap}
.chip.verified{color:var(--ok)}.chip.partial{color:var(--part)}.chip.none{color:var(--bad)}
.fig{margin:11px 0 8px;padding:9px 12px;background:var(--surface2);border-radius:10px;display:flex;align-items:center;justify-content:space-between;gap:10px}
.fig-t{min-width:0}
.fig b{display:block;font:600 clamp(24px,2.5vw,34px)/1 var(--f-mono);letter-spacing:-.04em;color:var(--acc);font-variant-numeric:tabular-nums}
.fig em{display:block;font-style:normal;font-size:12px;color:var(--mute);margin-top:5px}
.fig.none b{color:var(--faint)}
.chg{flex:none;text-align:center;font:600 11px var(--f-mono);color:var(--faint);line-height:1.2;background:none;border:0;padding:0}
.chg i{display:block;font:600 22px/1 var(--f-mono);font-style:normal;margin-bottom:2px}
button.chg{cursor:pointer;border-radius:8px;padding:4px 6px}button.chg:hover{background:var(--surface)}
.chg.up{color:var(--up)}.chg.down{color:var(--down)}.chg.mixed,.chg.shape{color:var(--mute)}
.sum{margin:0;font-size:13px;color:var(--ink);flex:1}
.note{margin:6px 0 0;font-size:11.5px;color:var(--mute);font-style:italic}
.srcrow{display:flex;justify-content:space-between;align-items:center;gap:8px;border-top:1px solid var(--line);padding-top:8px;margin-top:9px;font:11.5px var(--f-mono);color:var(--mute)}
.srcrow button{appearance:none;background:none;border:0;padding:0;font:inherit;color:var(--accent);cursor:pointer;text-underline-offset:3px}
.srcrow button:hover{text-decoration:underline}
.srcrow button,.srcrow span{white-space:nowrap}.srcrow .short{display:none}
@container (max-width:300px){.name{font-size:18px}.chip{font-size:10px;padding:2px 7px}.fig{padding:8px 10px}.fig b{font-size:25px}.fig em{font-size:11px}.chg{font-size:10px}.chg i{font-size:18px}.sum{font-size:12.5px}.srcrow{font-size:10.5px}.srcrow .full{display:none}.srcrow .short{display:inline}}
.card.guide{background:transparent;border-style:dashed}
.guide h3{margin:0 0 8px;font:600 11px var(--f-mono);letter-spacing:.07em;text-transform:uppercase;color:var(--accent)}
.guide ul{margin:0;padding:0;list-style:none;display:grid;gap:8px;font-size:12.5px;color:var(--mute)}
.guide li b{color:var(--ink)}
.guide .sw{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
footer{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px 28px;border-top:1px solid var(--line);padding-top:12px;font-size:11.5px;color:var(--mute)}
footer h5{margin:0 0 4px;font:600 10.5px var(--f-mono);letter-spacing:.07em;text-transform:uppercase;color:var(--faint)}
footer p{margin:0}footer a{color:var(--ink);text-underline-offset:3px}
dialog{padding:0;border:1px solid var(--line);border-radius:16px;background:var(--surface);color:var(--ink);width:min(820px,calc(100% - 32px));max-height:90vh;overflow:hidden;box-shadow:0 24px 60px rgba(0,0,0,.28)}
dialog::backdrop{background:rgba(6,12,24,.55);backdrop-filter:blur(3px)}
.dbody{padding:22px 14px 24px 24px;max-height:90vh;overflow-y:auto;scrollbar-width:thin;scrollbar-color:var(--line) transparent;scrollbar-gutter:stable;--acc:var(--accent)}
.dbody::-webkit-scrollbar{width:8px}.dbody::-webkit-scrollbar-track{background:transparent;margin:14px 0}.dbody::-webkit-scrollbar-thumb{background:var(--line);border-radius:8px}.dbody::-webkit-scrollbar-thumb:hover{background:var(--faint)}
.dhead{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:6px}
.dhead h2{margin:0;font:700 24px/1.1 var(--f-display);letter-spacing:-.02em}
.x{appearance:none;border:1px solid var(--line);background:var(--surface2);color:var(--ink);width:32px;height:32px;border-radius:8px;font:500 18px/1 var(--f-body);cursor:pointer;flex:none}
.meta{font:12px var(--f-mono);color:var(--mute);margin:0 0 14px}
.it{border-top:1px solid var(--line);padding:11px 0}
.it h4{margin:0 0 3px;font:600 14px var(--f-body)}.it h4 span{font-weight:400;color:var(--mute)}
.it blockquote{margin:6px 0 4px;padding:6px 10px;border-left:3px solid var(--accent);background:var(--surface2);border-radius:0 8px 8px 0;font-size:13px}
.it a{font:11.5px var(--f-mono);color:var(--accent);text-underline-offset:3px;overflow-wrap:anywhere}
.how{color:var(--mute);font-size:12.5px;margin:10px 0 0}
.chgbox{margin:0 0 10px;padding:14px 16px;background:var(--surface2);border:1px solid var(--line);border-radius:12px}
.chgh{font:12px var(--f-mono);letter-spacing:.04em;text-transform:uppercase;color:var(--mute);margin-bottom:6px}
ul.chgl{list-style:none;margin:0;padding:0}
ul.chgl>li{padding:10px 0;border-top:1px solid var(--line)}ul.chgl>li:first-child{border-top:0}
.cr{display:flex;flex-wrap:wrap;gap:6px 16px;justify-content:space-between;align-items:baseline}
.cr b{font-weight:600}
.cv{display:inline-flex;align-items:center;gap:10px;flex-wrap:wrap;font:13px var(--f-mono)}
.cv .ov{color:var(--mute)}
li.down .nv,li.removed .nv{color:var(--down)}li.up .nv,li.added .nv{color:var(--up)}
li.down svg,li.removed svg{color:var(--down)}li.up svg,li.added svg{color:var(--up)}
.cq{display:grid;gap:4px;margin-top:6px;font-size:12.5px;color:var(--mute)}
.cq q{font-style:italic}.cq a{font:12px var(--f-mono);color:var(--accent)}
.page main{max-width:760px;width:100%;margin:0 auto;padding:10px 0 20px}
.page h1{font-size:clamp(28px,4.4vw,42px);max-width:22ch;margin:26px 0 14px}
.page h2{font:700 21px/1.2 var(--f-display);letter-spacing:-.01em;margin:30px 0 10px}
.page p,.page li{max-width:66ch;font-size:15px;line-height:1.65}
.page li{margin:6px 0}.page ul{padding-left:20px}
.page a{color:var(--accent);text-underline-offset:3px}
.kind{display:grid;gap:10px;margin:14px 0}
.kind div{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.kind p{margin:8px 0 0}
.st{font:500 11px var(--f-mono);padding:3px 9px;border-radius:99px;border:1px solid currentColor;white-space:nowrap}
.st.verified{color:var(--ok)}.st.partial{color:var(--part)}.st.none{color:var(--bad)}
@media (max-width:1100px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:900px){footer{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:640px){.grid{grid-template-columns:1fr}.tag{display:none}.hero-side{align-items:flex-start}.week{text-align:left}}
@media (max-width:520px){footer{grid-template-columns:1fr}}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=DM+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;600&display=swap">')

LOGO = ('<svg class="logo" viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="2" width="12" height="20" rx="1.5" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<path d="M9 8h6M9 12h6M9 16h3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>')


def shell(title, desc, body, path="", issue="", page=False, dialogs=""):
    err = f"mailto:{CONTACT}?subject=Error%20report%3A%20&body=Which%20service%3F%0AWhat%20is%20wrong%3F%0ALink%20to%20the%20official%20page%3A%20"
    url = SITE + "/" + path
    img = f"{SITE}/{OG_IMAGE}"
    meta = (
        f'<link rel="canonical" href="{e(url)}">'
        f'<meta property="og:site_name" content="Free Tier Watch"><meta property="og:type" content="website">'
        f'<meta property="og:url" content="{e(url)}"><meta property="og:title" content="{e(title)}">'
        f'<meta property="og:description" content="{e(desc)}"><meta property="og:image" content="{img}">'
        f'<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
        f'<meta property="og:image:alt" content="Free Tier Watch: what free AI plans really include">'
        f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(title)}">'
        f'<meta name="twitter:description" content="{e(desc)}"><meta name="twitter:image" content="{img}">'
    )
    stamp = f'<span class="stamp">{e(issue)}</span>' if issue else ""
    how_link = '<a class="pill" href="how-we-check.html">How we check</a>'
    foot = (
        '<footer>'
        '<div><h5>Independent</h5><p>Free Tier Watch is independent. We are not affiliated with any company listed here and we run no ads or sponsors.</p></div>'
        '<div><h5>Check before you rely</h5><p>Plans change often and mistakes can happen, so always confirm on the official page before you rely on a limit.</p></div>'
        '<div><h5>Reuse</h5><p>Our summaries and data may be quoted with credit to Free Tier Watch (freetierwatch.com, CC BY 4.0).</p></div>'
        f'<div><h5>Found a mistake?</h5><p><a href="{err}">Tell us</a> or write to {CONTACT}.</p></div>'
        '</footer>'
    )
    return (
        '<!doctype html><html lang="en" data-theme="dark"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        f"<title>{e(title)}</title><meta name=\"description\" content=\"{e(desc)}\">{meta}"
        '<link rel="icon" href="favicon.ico" sizes="48x48"><link rel="icon" type="image/png" href="favicon-192.png" sizes="192x192">'
        '<link rel="apple-touch-icon" href="apple-touch-icon.png">'
        f'{FONTS}<script>{THEME_HEAD}</script><style>{CSS}</style></head>'
        f'<body class="{"page" if page else ""}"><div class="app">'
        f'<header class="top"><a class="brand" href="./">{LOGO}<span>Free Tier Watch</span></a>'
        f'<span class="tag">Free AI plan limits, checked weekly</span>{how_link}'
        f'<div class="right">{stamp}<button class="pill" id="theme" type="button" aria-pressed="true">Light</button></div></header>'
        f'{body}{foot}</div>{dialogs}<script>{THEME_BODY}</script></body></html>'
    )


def issue_label(services):
    """'Issue No. 3 · Oct 26': haftalik sayi, son kontrol tarihinden hesaplanir (uydurma yok)."""
    dates = [s["checked"] for s in services if s["checked"]]
    site = load(ROOT / "config" / "site.json", {}) or {}
    try:
        last = datetime.date.fromisoformat(max(dates))
        first = datetime.date.fromisoformat(site["first_issue_week"])
    except (ValueError, KeyError):
        return ""
    monday = last - datetime.timedelta(days=last.weekday())
    n = (monday - first).days // 7 + 1
    if n < 1:
        return ""
    return f"Issue No. {n} \u00b7 {last.strftime('%b')} {last.day}"


def human_list(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def this_week(services):
    """Tek satirlik 'This week' ozeti. Sadece gercek (dogrulanmis) degisiklikler sayilir."""
    moved = [s for s in services if s.get("changes")]
    if moved:
        links = ", ".join(
            f'<a href="#{e(s["id"])}">{e(s["name"])}</a> ({e(pill_text(compare.overall(s["changes"]), reference_week(s["prev"], s["checked"])).split(" than ")[0].split(" since ")[0].lower())})'
            for s in moved)
        return f'<p class="week"><b>This week:</b> changes in the free plans: {links}.</p>'
    if any(s.get("prev") for s in services):
        return '<p class="week"><b>This week:</b> No changes in the free plans since the last check.</p>'
    return '<p class="week"><b>This week:</b> This is our first full check. From next Monday this line lists what changed on the free plans.</p>'


def index(services, issue=""):
    counts = {k: sum(1 for s in services if s["cfg"]["status"] == k) for k in LABEL}
    cnt = "".join(f'<div class="count {c}"><b>{counts[k]}</b><span>{LABEL[k]}</span></div>'
                  for c, k in (("ok", "verified"), ("part", "partial"), ("bad", "none")))
    body = (
        '<section class="hero"><h1>What free AI plans actually give you.</h1>'
        f'<div class="hero-side"><div class="counts" aria-label="Status summary">{cnt}</div>{this_week(services)}</div></section>'
        f'<main class="grid">{"".join(card(s) for s in services)}{guide()}</main>'
    )
    covered = [s["name"] for s in services if s["cfg"]["status"] != "none"]
    desc = (f"What free AI plans really include: limits and features for {human_list(covered)}, "
            "with the official source and exact quote for each line.") if covered else \
        "What free AI plans really include, checked against official pages every week."
    return shell("Free AI plan limits, checked weekly | Free Tier Watch", desc, body, path="", issue=issue,
                 dialogs="".join(dialog(s) for s in services))


def method(issue=""):
    body = """<main>
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
<ul><li>What the companies say and what we tried ourselves are always shown separately.</li>
<li>Mistakes can happen. If you spot one, write to %s and we will look at it.</li></ul>
<p>The code of this site is public: <a href="%s" rel="noopener">%s</a>. The limits shown on each page are also available on this site as <a href="data.json">data.json</a>. Our summaries and compiled data are free to quote under <a href="https://creativecommons.org/licenses/by/4.0/" rel="noopener">CC BY 4.0</a>; please credit Free Tier Watch (freetierwatch.com). Text quoted from official pages belongs to its owners.</p>
</main>
""" % (CONTACT, REPO, REPO.replace("https://", ""))
    return shell("How we check free AI plan limits | Free Tier Watch",
                 "How Free Tier Watch collects free plan limits from official pages, checks every quote and shows what it could not verify.",
                 body, path="how-we-check.html", issue=issue, page=True)


def sitemap(services):
    """Sadece gercek sayfalar. Ana sayfanin lastmod'u en son gercek kontrol tarihidir; yontem sayfasinda
    veriye bagli tarih olmadigi icin lastmod yazilmaz (uydurma tarih yok)."""
    dates = [s["checked"] for s in services if s["checked"]]
    last = f"<lastmod>{max(dates)}</lastmod>" if dates else ""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"<url><loc>{SITE}/</loc>{last}</url>\n"
            f"<url><loc>{SITE}/how-we-check.html</loc></url>\n</urlset>\n")


def main():
    services = collect_services()
    check_claims(services)
    for s in services:
        for c in s["changes"]:
            print(f"DEGISIKLIK [{s['id']}] {c['dir']}: {c['label']}: "
                  f"{(c['old'] or {}).get('value')} -> {(c['new'] or {}).get('value')}")
        for c in s["dropped"]:
            print(f"ELENDI (resmi sayfada ayni, sahte degisiklik) [{s['id']}] {c['dir']}: {c['label']}")
    issue = issue_label(services)
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(index(services, issue), encoding="utf-8")
    (OUT / "how-we-check.html").write_text(method(issue), encoding="utf-8")
    public = [{"id": s["id"], "name": s["name"], "status": s["cfg"]["status"], "checked": s["checked"],
               "limits": s["limits"], "features": s["features"]} for s in services]
    (OUT / "data.json").write_text(json.dumps(public, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "sitemap.xml").write_text(sitemap(services), encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")
    (OUT / "CNAME").write_text("freetierwatch.com\n", encoding="utf-8")
    for f in (ROOT / "site" / "static").glob("*"):  # paylasim gorseli ve site simgeleri
        (OUT / f.name).write_bytes(f.read_bytes())
    print("ok:", sorted(p.name for p in OUT.iterdir()), "|", issue or "no issue label")


if __name__ == "__main__":
    main()
