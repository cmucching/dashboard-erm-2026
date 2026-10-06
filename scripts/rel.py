"""Convierte rutas absolutas del sitio (/api/x, /board.css, /provincial) a relativas con extensión,
para que funcione igual en Netlify, GitHub Pages (subruta) o abierto como archivos."""
import re
from pathlib import Path

PAGES = ("provincial", "distrital", "lima-metropolitana", "base-municipal")


def relativizar(t: str) -> str:
    t = re.sub(r"""(fetch\(\s*['"`])/api/([a-z-]+)(['"`])""", r"\1api/\2.json\3", t)
    t = re.sub(r"""(href=["'])/api/([a-z-]+)(["'])""", r"\1api/\2.json\3", t)
    t = re.sub(r"""(fetch\(\s*['"`])/(?!/)""", r"\1", t)
    t = re.sub(r"""((?:src|href)=["'])/api/""", r"\1api/", t)
    for p in PAGES:
        t = re.sub(rf"""((?:href|src)=["'])/{p}(["'])""", rf"\1{p}.html\2", t)
    t = re.sub(r"""((?:src|href)=["'])/(?!/)(?=[A-Za-z])""", r"\1", t)
    t = re.sub(r"""((?:src|href)=["'])/(["'])""", r"\1index.html\2", t)
    return t


if __name__ == "__main__":
    for f in sorted((Path(__file__).resolve().parent.parent / "site").glob("*")):
        if f.suffix in (".html", ".js") and f.name not in ("shell.js",):
            a = f.read_text(encoding="utf-8")
            b = relativizar(a)
            if a != b:
                f.write_text(b, encoding="utf-8")
                print("relativizado", f.name)
