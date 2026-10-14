#!/usr/bin/env python3
"""Okuyucu: degisen (veya ilk kez gorulen) sayfayi Gemini'ye okutur ve tabloya cevirir.
Guvenlik: modelden her bilgi icin sayfadan BIREBIR alinti ister; alinti sayfada
gercekten yoksa o bilgi "dogrulanamadi" diye isaretlenir (uydurmayi yakalamak icin).

Kullanim:
  python reader/read.py          -> sadece 'first' ve 'changed' servisleri okur
  python reader/read.py --all    -> hepsini okur
Anahtar GEMINI_API_KEY ortam degiskeninden gelir (GitHub Secrets). Yoksa hicbir sey yapmaz."""
import datetime
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
NOT_STATED = "not officially stated"

PROMPT = """You extract facts about the FREE plan of an AI service from the text of its official pricing page.

Rules:
- Use ONLY the page text below. Never use outside knowledge.
- If the page does not clearly say something, use the value "not officially stated". Never guess.
- For every limit or feature, give "evidence": a SHORT exact copy (max 200 characters) of the sentence from the page text that supports it.
- Ignore paid plans, except to note in "notes" if the free plan is not mentioned at all.

Return JSON with exactly this shape:
{{
  "free_plan_exists": "yes" | "no" | "not officially stated",
  "free_plan_name": string or null,
  "limits": [{{"topic": string, "value": string, "evidence": string}}],
  "features": [{{"feature": string, "evidence": string}}],
  "notes": string
}}

Service: {name}
Page text:
\"\"\"
{text}
\"\"\"
"""


def norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def ask_gemini(model: str, key: str, prompt: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return json.loads(data["candidates"][0]["content"]["parts"][0]["text"])


def check_evidence(extracted: dict, page_text: str) -> int:
    """Her alintinin sayfada gercekten gecip gecmedigine bakar. Gecmeyenleri isaretler."""
    haystack = norm(page_text)
    bad = 0
    for group in ("limits", "features"):
        for item in extracted.get(group, []) or []:
            ev = norm(item.get("evidence", ""))
            item["verified"] = bool(ev) and ev in haystack
            if not item["verified"]:
                bad += 1
    return bad


def main():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("GEMINI_API_KEY yok; okuyucu atlandi (bu hata degil).")
        return
    settings = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    services = {s["id"]: s for s in json.loads(
        (ROOT / "config" / "services.json").read_text(encoding="utf-8"))["services"]}
    changes = json.loads((DATA / "changes.json").read_text(encoding="utf-8"))
    read_all = "--all" in sys.argv

    plans_path = DATA / "plans.json"
    plans = json.loads(plans_path.read_text(encoding="utf-8")) if plans_path.exists() else {"services": {}}

    for sid, ch in changes["services"].items():
        if ch["status"] not in ("first", "changed") and not (read_all and ch["status"] != "error"):
            continue
        svc = services[sid]
        page_text = (DATA / "snapshots" / sid / f"{changes['date']}.txt").read_text(encoding="utf-8")
        prompt = PROMPT.format(name=svc["name"], text=page_text[: settings["max_page_chars"]])
        try:
            extracted = ask_gemini(settings["gemini_model"], key, prompt)
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError, OSError) as exc:
            print(f"{svc['name']}: okunamadi - {exc}")
            continue
        bad = check_evidence(extracted, page_text)
        plans["services"][sid] = {
            "name": svc["name"],
            "source_url": svc["url"],
            "last_checked": changes["date"],
            "page_was_thin": ch.get("thin", False),
            "unverified_items": bad,
            "needs_human_review": bool(bad or ch.get("thin")),
            "extracted": extracted,
        }
        print(f"{svc['name']}: okundu, dogrulanamayan madde: {bad}")

    plans["updated"] = changes["date"]
    plans_path.write_text(json.dumps(plans, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
