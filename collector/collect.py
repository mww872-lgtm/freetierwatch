#!/usr/bin/env python3
"""Toplayici: her servisin RESMI sayfalarini (birden fazla olabilir) indirir, duz metne cevirir,
tek bir dosyada birlestirip data/snapshots/<servis>/<tarih>.txt olarak kaydeder.
Her sayfanin basina "=== SOURCE: <adres> ===" satiri konur ki bilginin hangi sayfadan geldigi bilinsin.
Sadece Python'un kendi kutuphanelerini kullanir (kurulum gerekmez)."""
import datetime
import http.client
import json
import pathlib
import re
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
USER_AGENT = "FreeTierWatchBot/0.1 (+https://freetierwatch.com; weekly public pricing-page check)"
PAUSE_SECONDS = 2  # sitelere nazik davran: istekler arasi bekleme


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
             "section", "article", "ul", "ol", "table", "header", "footer"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    lines = []
    for raw in "".join(parser.parts).splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return "\n".join(lines)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def main():
    services = json.loads((ROOT / "config" / "services.json").read_text(encoding="utf-8"))["services"]
    settings = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    today = datetime.date.today().isoformat()
    results = {}

    for svc in services:
        sid = svc["id"]
        sections, details = [], []
        for url in svc["urls"]:
            try:
                text = html_to_text(fetch(url))
                sections.append(f"=== SOURCE: {url} ===\n{text}")
                details.append({"url": url, "ok": True, "chars": len(text), "error": None})
                print(f"{svc['name']} | {url}: {len(text)} karakter")
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, http.client.HTTPException) as exc:
                details.append({"url": url, "ok": False, "chars": 0, "error": str(exc)})
                print(f"{svc['name']} | {url}: HATA - {exc}")
            time.sleep(PAUSE_SECONDS)

        ok = bool(sections)
        total = sum(d["chars"] for d in details)
        thin = ok and total < settings["min_page_chars"]
        failed = [d["url"] for d in details if not d["ok"]]
        if ok:
            folder = DATA / "snapshots" / sid
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{today}.txt").write_text("\n\n".join(sections), encoding="utf-8")
        results[sid] = {
            "ok": ok, "chars": total, "thin": thin,
            "partial": ok and bool(failed), "failed_sources": failed,
            "sources": details,
            "error": None if ok else "; ".join(f"{d['url']} -> {d['error']}" for d in details),
        }
        if thin:
            print(f"  [UYARI] {svc['name']}: toplam cok az metin ({total}); bu servis hakkinda iddia uretilmeyecek.")

    DATA.mkdir(exist_ok=True)
    (DATA / "collect_log.json").write_text(
        json.dumps({"date": today, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
