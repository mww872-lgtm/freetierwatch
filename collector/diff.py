#!/usr/bin/env python3
"""Fark bulucu: her servisin son kaydini bir oncekiyle karsilastirir,
sonucu data/changes.json dosyasina yazar.
Durumlar: first (ilk kayit), unchanged, changed, error."""
import difflib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MAX_LINES = 200


def main():
    log = json.loads((DATA / "collect_log.json").read_text(encoding="utf-8"))
    today = log["date"]
    out = {"date": today, "services": {}}

    for sid, res in log["results"].items():
        if not res["ok"]:
            out["services"][sid] = {"status": "error", "error": res["error"], "added": [], "removed": []}
            continue
        files = sorted(p for p in (DATA / "snapshots" / sid).glob("*.txt") if p.stem <= today)
        if len(files) < 2:
            out["services"][sid] = {"status": "first", "thin": res["thin"], "added": [], "removed": []}
            continue
        old = files[-2].read_text(encoding="utf-8").splitlines()
        new = files[-1].read_text(encoding="utf-8").splitlines()
        if old == new:
            out["services"][sid] = {"status": "unchanged", "thin": res["thin"], "added": [], "removed": []}
            continue
        added, removed = [], []
        for line in difflib.unified_diff(old, new, n=0, lineterm=""):
            if line.startswith("+") and not line.startswith("+++"):
                added.append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                removed.append(line[1:])
        out["services"][sid] = {
            "status": "changed", "thin": res["thin"],
            "compared_with": files[-2].stem,
            "added": added[:MAX_LINES], "removed": removed[:MAX_LINES],
        }

    (DATA / "changes.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    for sid, s in out["services"].items():
        print(f"{sid}: {s['status']}")


if __name__ == "__main__":
    main()
