"""Her servisin o anki (gosterilen) verisini data/history/<servis>/<tarih>.json olarak saklar.
Ayni tarihli dosya varsa dokunmaz; yani istedigin kadar calistirilabilir.
Haftalik robot, yeni veriyi yazmadan ONCE bunu calistirir; boylece gecen haftanin verisi kaybolmaz."""
import json
import pathlib

import build

HIST = build.DATA / "history"


def main():
    wrote = 0
    for s in build.collect_services():
        if not s["checked"]:
            continue
        path = HIST / s["id"] / f"{s['checked']}.json"
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "date": s["checked"],
            "status": s["cfg"]["status"],
            "manual": s["manual"],
            "limits": [{k: l.get(k) for k in ("topic", "value", "evidence", "source")} for l in s["limits"]],
            "features": [{k: f.get(k) for k in ("feature", "evidence", "source")} for f in s["features"]],
        }
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        wrote += 1
        print("arsivlendi:", s["id"], s["checked"])
    if not wrote:
        print("yeni arsiv yok")


if __name__ == "__main__":
    main()
