"""Propuesta B (tablero de 25 carreras). Genera dist/propuesta-b.html autocontenido."""
import base64, json, re
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
S = RAIZ / "site"
LIVE = "https://peru-regionales-onpe-carlos-mucching.netlify.app"

DATA = json.loads((S / "api" / "results.json").read_text(encoding="utf-8"))["regiones"]

def b64(p, mime): return f"data:{mime};base64," + base64.b64encode((S / p).read_bytes()).decode()
sym = {}
for r in DATA:
    for ref in {r["simbolo"], *[t["simbolo"] for t in r["top"]]}:
        if ref in sym or ref.startswith("http"): continue
        sym[ref] = b64(ref, "image/png")

geo = json.loads((S / "map-geography.json").read_text(encoding="utf-8"))["regional"]
def rd(c): return [round(c[0], 2), round(c[1], 2)] if isinstance(c[0], (int, float)) else [rd(x) for x in c]
paths = {f["properties"]["id"]: rd(f["geometry"]["coordinates"]) for f in geo["features"] if not f["properties"].get("excluded")}
gtype = {f["properties"]["id"]: f["geometry"]["type"] for f in geo["features"]}

html = (RAIZ / "scripts" / "propuesta_b.tpl.html").read_text(encoding="utf-8")
html = (html.replace("__DATA__", json.dumps(DATA, ensure_ascii=False))
            .replace("__SYM__", json.dumps(sym))
            .replace("__GEO__", json.dumps({"p": paths, "t": gtype}, separators=(",", ":")))
            .replace("__BANNER__", b64("banner-marca-personal.jpg", "image/jpeg"))
            .replace("__LIVE__", LIVE))
out = RAIZ / "dist" / "propuesta-b.html"; out.parent.mkdir(exist_ok=True)
out.write_text(html, encoding="utf-8"); print(out, f"{out.stat().st_size/1e6:.2f} MB")

# versión para el sitio (rutas relativas, banner externo)
SITE_OUT = S / "index.html"
site = html.replace(b64("banner-marca-personal.jpg", "image/jpeg"), "/banner-marca-personal.jpg").replace(LIVE, "")
site = site.replace(' · <a href="">tablero en vivo</a>', "").replace("Datos de ejemplo congelados al corte indicado", "Datos al corte indicado")
SITE_OUT.write_text(site, encoding="utf-8"); print(SITE_OUT, f"{SITE_OUT.stat().st_size/1e6:.2f} MB")
