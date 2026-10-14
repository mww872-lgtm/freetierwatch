#!/usr/bin/env python3
"""Toplayici: her servisin ucretsiz plan sayfasini indirir, duz metne cevirir,
tarihli olarak data/snapshots/<servis>/<tarih>.txt dosyasina kaydeder.
Sadece Python'un kendi kutuphanelerini kullanir (kurulum gerekmez)."""
import datetime
import json
import pathlib
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
USER_AGENT = "FreeTierWatchBot/0.1 (+https://freetierwatch.com; weekly public pricing-page check)"


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
        sid, url = svc["id"], svc["url"]
        try:
            text = html_to_text(fetch(url))
            folder = DATA / "snapshots" / sid
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{today}.txt").write_text(text, encoding="utf-8")
            thin = len(text) < settings["min_page_chars"]
            results[sid] = {"ok": True, "chars": len(text), "thin": thin, "url": url, "error": None}
            print(f"{svc['name']}: {len(text)} karakter" + ("  [UYARI: cok az metin, sayfa JavaScript ile olusuyor olabilir]" if thin else ""))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            results[sid] = {"ok": False, "chars": 0, "thin": False, "url": url, "error": str(exc)}
            print(f"{svc['name']}: HATA - {exc}")

    DATA.mkdir(exist_ok=True)
    (DATA / "collect_log.json").write_text(
        json.dumps({"date": today, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
