"""Iki kontrol arasindaki farki bulur: hangi limit/ozellik kisilmis, hangisi artirilmis.

Kural: sadece her iki kontrolde de alintisi olan maddeler karsilastirilir.
Sayilar ancak ayni birimde ve tek sayi iceriyorsa 'yukari/asagi' sayilir; aksi halde 'shape' (limitin sekli degisti)."""
import re

STORAGE = {"kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12}
PERIOD = {"day": "day", "daily": "day", "week": "week", "weekly": "week", "month": "month", "monthly": "month",
          "hour": "hour", "hours": "hour", "hr": "hour", "hrs": "hour", "minute": "minute", "minutes": "minute",
          "min": "minute", "year": "year"}


def parse_value(value):
    """('inf', None) | (sayi, donem) | None (karsilastirilamaz)."""
    v = str(value or "").lower()
    if "unlimited" in v or "no limit" in v:
        return ("inf", None)
    nums = re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(k\b)?\s*(kb|mb|gb|tb)?", v)
    if len(nums) != 1:
        return None
    raw, k, unit = nums[0]
    try:
        qty = float(raw.replace(",", ""))
    except ValueError:
        return None
    if k:
        qty *= 1000
    if unit:
        qty *= STORAGE[unit]
    period = None
    for w in re.findall(r"[a-z]+", v):
        if w in PERIOD:
            period = PERIOD[w]
            break
    return (qty, period)


def direction(old_value, new_value):
    """'up' | 'down' | 'shape' | None (degisiklik yok / sadece ifade farki)."""
    a, b = parse_value(old_value), parse_value(new_value)
    if a is None or b is None:
        # Iki taraf da sayisiz serbest metinse (sadece ifade degisti) alarm uretme.
        if not (re.search(r"\d|unlimited", str(old_value).lower()) or re.search(r"\d|unlimited", str(new_value).lower())):
            return None
        same = " ".join(str(old_value).lower().split()) == " ".join(str(new_value).lower().split())
        return None if same else "shape"
    if a[0] == "inf" and b[0] == "inf":
        return None
    if a[0] == "inf":
        return "down"
    if b[0] == "inf":
        return "up"
    if a[1] != b[1]:
        return "shape"
    if a[0] == b[0]:
        return None
    return "up" if b[0] > a[0] else "down"


def items(limits, features, hide=()):
    out = {}
    for l in limits or []:
        if l.get("topic") in hide or str(l.get("value", "")).lower().startswith("not officially"):
            continue
        out["limit:" + l["topic"]] = {"label": l["topic"], "value": l.get("value", ""),
                                      "quote": l.get("evidence", ""), "source": l.get("source", ""), "limit": True}
    for f in features or []:
        if f.get("feature") in hide:
            continue
        out["feature:" + f["feature"]] = {"label": f["feature"], "value": None,
                                          "quote": f.get("evidence", ""), "source": f.get("source", ""), "limit": False}
    return out


def compare(old, new):
    """old, new: items() cikti sozlukleri. Degisiklik listesi doner."""
    changes = []
    for k, n in new.items():
        o = old.get(k)
        if o is None:
            changes.append({"label": n["label"], "dir": "added", "old": None, "new": n})
        elif n["limit"]:
            d = direction(o["value"], n["value"])
            if d:
                changes.append({"label": n["label"], "dir": d, "old": o, "new": n})
    for k, o in old.items():
        if k not in new:
            changes.append({"label": o["label"], "dir": "removed", "old": o, "new": None})
    return changes


def norm_text(text):
    """Karsilastirma icin metni sadelestirir: kucuk harf, sadece harf ve rakam, tek bosluk."""
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip() + " "


def on_page(quote, page):
    """Alinti, sayfa metninde (bosluk/noktalama farkina bakmadan) geciyor mu?"""
    q = str(quote or "").strip()
    if not q:
        return False
    loose = re.sub(r"(?<=[A-Za-z])\d{1,2}$", "", q)  # sondaki dipnot numarasi
    return any(c.strip() and c in page for c in {norm_text(q), norm_text(loose)})


def confirm(changes, old_page, new_page):
    """Sadece resmi sayfada gercekten degisen maddeleri tutar.

    Okuyucu ayni maddeye her calismada farkli baslik verebilir ya da sayfada zaten olan bir satiri
    bu sefer cikarabilir; bunlar sahte 'kisildi/artti' oku uretmesin. Kural: eklenen maddenin alintisi
    ESKI sayfada, kalkan maddenin alintisi YENI sayfada zaten varsa degisiklik sayilmaz.
    Sayfa metni yoksa (elle okunan servisler) bir sey elenmez."""
    if old_page is None or new_page is None:
        return changes, []
    kept, dropped = [], []
    for c in changes:
        if c["dir"] == "removed":
            real = not on_page(c["old"]["quote"], new_page)
        else:  # added, up, down, shape: yeni alinti eski sayfada yoksa gercek
            real = not on_page(c["new"]["quote"], old_page)
        (kept if real else dropped).append(c)
    return kept, dropped


def overall(changes):
    """'down' | 'up' | 'mixed' | 'shape' | None"""
    if not changes:
        return None
    dirs = {"down" if c["dir"] in ("down", "removed") else "up" if c["dir"] in ("up", "added") else "shape" for c in changes}
    if dirs == {"down"}:
        return "down"
    if dirs == {"up"}:
        return "up"
    if dirs == {"shape"}:
        return "shape"
    return "mixed"
