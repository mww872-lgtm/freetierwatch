#!/usr/bin/env python3
"""Okuyucu: degisen (veya ilk kez gorulen) servisin resmi sayfa metnini Gemini'ye okutur.

Uc katmanli guvenlik vardir:
 1) Kapsam: sadece servisin SOHBET UYGULAMASININ UCRETSIZ plani. API/gelistirici, kurumsal ve ucretli plan
    bolumleri yok sayilir.
 2) Alinti kontrolu: model her bilgi icin sayfadan BIREBIR alinti vermek zorunda (bosluk/noktalama farki
    onemsenmez, kelimeler birebir olmali). Alinti sayfada yoksa bilgi atilir. Bilginin hangi sayfadan
    geldigini model degil, kod belirler.
 3) Baglam kontrolu: ikinci bir model cagrisi, alintinin sayfadaki CEVRESINE bakarak "bu cumle gercekten
    ucretsiz sohbet planiyla mi ilgili?" diye sorar. Model kendi hafizasini DEGIL, sadece sayfa metnini
    kullanir. Sayfa ucretsiz kullanicilari acikca gostermiyorsa bilgi atilir.
Atilan bilgiler "rejected_items" altinda nedeniyle saklanir (gozden gecirmek icin), yayina girmez.
Sayfa metni cok azsa (ornegin JavaScript ile olusan sayfa) servis hakkinda HICBIR iddia uretilmez.

Kullanim:
  python reader/read.py          -> sadece 'first' ve 'changed' servisleri okur
  python reader/read.py --all    -> hepsini okur
Anahtar GEMINI_API_KEY ortam degiskeninden gelir (GitHub Secrets). Yoksa hicbir sey yapmaz."""
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MIN_EVIDENCE_CHARS = 20
SOURCE_RE = re.compile(r"^=== SOURCE: (.+?) ===$", re.M)

PROMPT = """You extract facts about the FREE plan of the consumer chat product of an AI service, from text copied from its official web pages.

Scope: ONLY the free plan of the chat app/website that ordinary people use in a browser or phone app.
Ignore completely: the developer API or platform, enterprise/team/business/education plans, and paid plans.

Rules:
- Use ONLY the page text below. Never use outside knowledge.
- If the pages do not clearly say something, use the value "not officially stated". Never guess.
- For every limit or feature, give "evidence": a SHORT exact copy (max 200 characters) of one sentence from the page text that supports it. Copy it character for character.
- Do not include a limit or feature if you cannot support it with such a sentence.

Return JSON with exactly this shape:
{{
  "free_plan_exists": "yes" | "no" | "not officially stated",
  "free_plan_name": string or null,
  "limits": [{{"topic": string, "value": string, "evidence": string}}],
  "features": [{{"feature": string, "evidence": string}}],
  "notes": string
}}

Service: {name}
Page text (several pages, each starts with a SOURCE line):
\"\"\"
{text}
\"\"\"
"""

CONTEXT_PROMPT = """You check whether quotes taken from official web pages describe the FREE plan of the consumer chat app/website of "{name}" (the product ordinary people use in a browser or phone app).

Judge ONLY from the CONTEXT text given with each quote. Do NOT use anything you believe about the product from memory; your memory may be outdated.
Answer true only if the context itself shows that the quote applies to free users of the consumer chat product: for example it mentions free users, the free plan, no cost, or "without a plan", or it sits under a heading about the free plan, or the page is clearly about free usage.
Answer false if the context shows the quote belongs to the developer API or platform, enterprise/team/business/education plans, or a paid plan only, OR if the context gives no clear sign that it applies to free users (for example a plain list of features that does not say which plan has them).
In "reason", say in one short sentence what in the context made you decide.

Return JSON: a list of {{"id": number, "about_free_consumer_plan": true or false, "reason": short string}}

{items}
"""


def locate(evidence: str, text: str):
    """Alintiyi metinde bulur. Bosluk, satir sonu ve noktalama farklari onemsenmez; kelimeler ayni sirada
    ve birebir olmali. Bulursa (bas, son) dondurur, bulamazsa None."""
    words = re.findall(r"[a-z0-9]+", evidence.lower())
    if len(" ".join(words)) < MIN_EVIDENCE_CHARS:
        return None
    pattern = r"(?<![a-z0-9])" + r"[^a-z0-9]+".join(re.escape(w) for w in words) + r"(?![a-z0-9])"
    m = re.search(pattern, text, re.I)
    return (m.start(), m.end()) if m else None


def split_sources(text: str) -> dict:
    """'=== SOURCE: adres ===' satirlarina gore metni sayfalara boler."""
    matches = list(SOURCE_RE.finditer(text))
    sections = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[m.group(1)] = text[m.end():end].strip()
    return sections


def ask_gemini(model: str, key: str, prompt: str):
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


def build_prompt_text(sections: dict, max_chars: int) -> str:
    per_source = max_chars // max(1, len(sections))
    return "\n\n".join(f"=== SOURCE: {u} ===\n{t[:per_source]}" for u, t in sections.items())


def verify_and_filter(extracted: dict, sections: dict, model: str, key: str, name: str):
    """Alinti kontrolu + baglam kontrolu. Kabul edilenler `extracted` icinde kalir, digerleri atilir.
    Doner: (atilanlar, inceleme_nedenleri)"""
    rejected, reasons = [], []
    candidates = []  # (group, item, baglam)

    for group in ("limits", "features"):
        kept = []
        for item in extracted.get(group) or []:
            found = None
            for url, text in sections.items():
                span = locate(item.get("evidence", ""), text)
                if span:
                    found = (url, text, span)
                    break
            if found is None:
                rejected.append({"group": group, "item": item, "reason": "quote not found on the source pages"})
                continue
            url, text, (s, e) = found
            item["source"] = url
            kept.append(item)
            context = re.sub(r"\s+", " ", text[max(0, s - 700): e + 300]).strip()
            candidates.append((group, item, context))
        extracted[group] = kept

    if candidates:
        items_txt = "\n".join(
            f"[{i}] QUOTE: {it['evidence']}\nCONTEXT: {ctx}\n" for i, (_, it, ctx) in enumerate(candidates))
        try:
            answer = ask_gemini(model, key, CONTEXT_PROMPT.format(name=name, items=items_txt))
            if isinstance(answer, dict):
                answer = answer.get("results") or answer.get("items") or []
            verdict = {int(a["id"]): a for a in answer}
            for i, (group, item, _) in enumerate(candidates):
                v = verdict.get(i)
                if v is None or v.get("about_free_consumer_plan") is not True:
                    extracted[group].remove(item)
                    why = (v or {}).get("reason", "no context verdict returned")
                    rejected.append({"group": group, "item": item, "reason": "context check: " + str(why)})
                else:
                    item["context_note"] = v.get("reason", "")
        except (urllib.error.URLError, KeyError, ValueError, TypeError, TimeoutError, OSError) as exc:
            reasons.append(f"context check failed ({exc}); items kept but NOT context-checked")

    if rejected:
        reasons.append(f"{len(rejected)} item(s) rejected automatically")
    return rejected, reasons


def main():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("GEMINI_API_KEY yok; okuyucu atlandi (bu hata degil).")
        return
    settings = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    services = {s["id"]: s for s in json.loads(
        (ROOT / "config" / "services.json").read_text(encoding="utf-8"))["services"]}
    changes = json.loads((DATA / "changes.json").read_text(encoding="utf-8"))
    log = json.loads((DATA / "collect_log.json").read_text(encoding="utf-8"))["results"]
    read_all = "--all" in sys.argv

    plans_path = DATA / "plans.json"
    plans = json.loads(plans_path.read_text(encoding="utf-8")) if plans_path.exists() else {"services": {}}

    for sid, ch in changes["services"].items():
        if ch["status"] not in ("first", "changed") and not (read_all and ch["status"] != "error"):
            continue
        svc = services[sid]
        res = log.get(sid, {})
        page_text = (DATA / "snapshots" / sid / f"{changes['date']}.txt").read_text(encoding="utf-8")
        sections = split_sources(page_text)
        base = {
            "name": svc["name"],
            "sources": list(sections.keys()),
            "failed_sources": res.get("failed_sources", []),
            "last_checked": changes["date"],
        }

        if res.get("thin"):
            plans["services"][sid] = {**base, "status": "source_too_thin", "needs_human_review": True,
                "review_reasons": ["Source pages returned too little text. No claim is made about this service."],
                "extracted": None, "rejected_items": []}
            print(f"{svc['name']}: kaynak metni cok az, iddia uretilmedi")
            continue

        prompt = PROMPT.format(name=svc["name"], text=build_prompt_text(sections, settings["max_page_chars"]))
        try:
            extracted = ask_gemini(settings["gemini_model"], key, prompt)
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError, OSError) as exc:
            print(f"{svc['name']}: okunamadi - {exc}")
            continue

        rejected, reasons = verify_and_filter(extracted, sections, settings["gemini_model"], key, svc["name"])
        if res.get("partial"):
            reasons.append("some source pages could not be fetched: " + ", ".join(res.get("failed_sources", [])))
        plans["services"][sid] = {**base, "status": "ok", "needs_human_review": bool(reasons),
            "review_reasons": reasons, "extracted": extracted, "rejected_items": rejected}
        print(f"{svc['name']}: okundu, kabul: {len(extracted.get('limits', [])) + len(extracted.get('features', []))}, "
              f"reddedilen: {len(rejected)}")

    plans["updated"] = changes["date"]
    plans_path.write_text(json.dumps(plans, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
