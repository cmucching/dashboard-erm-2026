"""Genera site/api/search-index.json: índice liviano para el buscador global (nombre, ubicación, líder, avance)."""
import json
from pathlib import Path
S = Path(__file__).resolve().parent.parent / "site"
def main():
    md = json.loads((S / "api" / "municipal-data.json").read_text(encoding="utf-8"))["records"]
    out = []
    for r in md:
        o = sorted(r.get("organizations") or [], key=lambda q: -q["votes"])
        prov = r["level"] == "provincial"
        out.append({"u": r["ubigeo"], "l": "p" if prov else "d", "n": r["province"] if prov else r["district"], "p": r["province"], "d": r["department"],
                    "v": r.get("valid_votes") or 0, "a": r.get("counted_pct"), "w": o[0]["organization"] if o else None,
                    "lp": o[0]["pct_valid"] if o else None, "m": round(o[0]["pct_valid"] - (o[1]["pct_valid"] if len(o) > 1 else 0), 2) if o else None})
    dest = S / "api" / "search-index.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(len(out), f"{dest.stat().st_size/1e3:.0f} KB")
if __name__ == "__main__": main()
