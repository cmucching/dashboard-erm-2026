"""Genera dist/erm2026-regionales.html: una sola página autocontenida (sin servidor)."""
import base64, json, re, sys, urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SITE = RAIZ / "site"
LIVE = "https://peru-regionales-onpe-carlos-mucching.netlify.app"
OUT = RAIZ / "dist" / "erm2026-regionales.html"


def b64(data, mime):
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def js_seguro(txt):
    return re.sub(r"</(script)", r"<\\/\1", txt, flags=re.I)


def main():
    h = (SITE / "index.html").read_text(encoding="utf-8")
    # quitar script HUD de Netlify
    h = re.sub(r"<script async src=\"/\.netlify/scripts/hud[^>]*></script>", "", h)
    # CSS locales en línea
    def css(m):
        return "<style>" + (SITE / m.group(1)).read_text(encoding="utf-8") + "</style>"
    h = re.sub(r'<link rel="stylesheet" href="((?!https?:)[^"]+\.css)">', css, h)
    # símbolos: una sola vez en un mapa SYM
    sym = {}
    def regsym(m):
        ref = m.group(1)
        if ref.startswith("http"):
            try:
                req = urllib.request.Request(ref, headers={"User-Agent": "Mozilla/5.0"})
                data = urllib.request.urlopen(req, timeout=20).read()
            except Exception:
                return m.group(0)
        else:
            data = (SITE / ref).read_bytes()
        sym[ref] = b64(data, "image/png")
        return '"simbolo":SYM[' + json.dumps(ref) + "]"
    h = re.sub(r'"simbolo":"([^"]+)"', regsym, h)
    # banner
    h = h.replace("banner-marca-personal.jpg", b64((SITE / "banner-marca-personal.jpg").read_bytes(), "image/jpeg"))
    h = h.replace('href="favicon.svg"', 'href="' + b64((SITE / "favicon.svg").read_bytes(), "image/svg+xml") + '"')
    # enlaces del menú y descargas -> sitio en vivo
    h = re.sub(r'href="(/(?:provincial|distrital|lima-metropolitana|base-municipal|moderacion|api/results\.csv)?)"',
               lambda m: f'href="{LIVE}{m.group(1)}"', h)
    h = h.replace('href="mapa-regional-peru-onpe-2026.png"', f'href="{LIVE}/mapa-regional-peru-onpe-2026.png"')
    # aviso de actualidad estático
    corte = re.search(r'"hora_onpe":"([^"]+)"', h)
    aviso = ('<aside class="freshness" id="freshness" role="status"><strong>Copia para ver sin conexión</strong>'
             f'<p>Generada el {datetime.now():%d/%m/%Y %H:%M}. Corte ONPE de la última región: {corte.group(1).rstrip(".") if corte else "—"}. '
             f'Para cifras al día abre <a href="{LIVE}">el tablero en vivo</a>.</p></aside>')
    h = re.sub(r'<aside class="freshness" id="freshness".*?</aside>', aviso, h, flags=re.S)
    # geografía embebida + fetch simulado
    geo = json.loads((SITE / "map-geography.json").read_text(encoding="utf-8"))
    geo = {k: geo[k] for k in ("source", "crs", "regional") if k in geo}
    pre = ("<script>const SYM=" + json.dumps(sym) + ";window.__GEO=" + json.dumps(geo, separators=(",", ":")) + ";"
           "const __f=window.fetch.bind(window);window.fetch=function(u,o){const s=String(u);"
           "if(s.indexOf('map-geography.json')>-1)return Promise.resolve(new Response(JSON.stringify(window.__GEO),{status:200,headers:{'Content-Type':'application/json'}}));"
           "if(s.charAt(0)==='/'&&s.indexOf('//')!==0)return Promise.reject(new Error('sin servidor'));return __f(u,o);};</script>")
    # SYM debe existir antes del script que define DATA
    h = h.replace("</head>", pre + "</head>", 1)
    # scripts locales en línea (excepto freshness)
    h = h.replace('<script src="freshness.js"></script>', "")
    def scr(m):
        return "<script>" + js_seguro((SITE / m.group(1)).read_text(encoding="utf-8")) + "</script>"
    h = re.sub(r'<script src="((?!https?:)[^"]+\.js)"></script>', scr, h)
    # ocultar comentarios (requieren servidor)
    h = h.replace("</head>", "<style>#comentarios{display:none!important}</style></head>", 1)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(h, encoding="utf-8")
    print(OUT, f"{OUT.stat().st_size/1e6:.1f} MB", len(sym), "símbolos")


if __name__ == "__main__":
    sys.exit(main())
