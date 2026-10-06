"""Descarga los resultados ERM 2026 desde la API pública de ONPE usando un navegador real.

Uso:
    python scraper/onpe_scraper.py --out data            # incremental
    python scraper/onpe_scraper.py --out data --full     # todos los distritos
    python scraper/onpe_scraper.py --out data --smoke    # prueba mínima (pocas unidades)

Códigos de salida: 0 ok · 2 falló el control de calidad · 3 bloqueo/desafío de ONPE · 4 error de red.
Reglas: ritmo bajo, sin saltar CAPTCHAs ni defensas anti-bot. Si ONPE devuelve un desafío, se
detiene y se conservan los últimos datos buenos.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transform as T  # noqa: E402

BASE = "https://resultadoelectoral.onpe.gob.pe"
PAGINA_INICIO = f"{BASE}/main/alcance-electoral"
API = "/presentacion-backend"
RUTA_UBIGEOS = "/assets/ubig/v1.json"  # verificado: archivo estático en la raíz del sitio
ID_REGIONAL, ID_MUNICIPAL = 1, 3
LOTE = 150
SMOKE_N = 3

NIVEL_FILTRO = {"dep": "ubigeo_nivel_01", "prov": "ubigeo_nivel_02", "dist": "ubigeo_nivel_03"}

EXIT_QC, EXIT_BLOQUEO, EXIT_RED = 2, 3, 4


class Bloqueado(Exception):
    pass


# --------------------------------------------------------------------------- URLs
def url_resumen(kind: str, id_eleccion: int, nivel: str, u: dict | None = None) -> str:
    q: dict = {"idEleccion": id_eleccion}
    if nivel == "nacion":
        q["tipoFiltro"] = "eleccion"
    else:
        q["tipoFiltro"] = NIVEL_FILTRO[nivel]
        q["idAmbitoGeografico"] = 1
        q["idUbigeoDepartamento"] = u["dep"]
        if nivel in ("prov", "dist"):
            q["idUbigeoProvincia"] = u["prov"]
        if nivel == "dist":
            q["idUbigeoDistrito"] = u["ubigeo"]
    return f"{API}/resumen-general/{kind}?" + urlencode(q)


# --------------------------------------------------------------------------- navegador
JS_POOL = """
async ({urls, conc, minMs, maxMs}) => {
  const out = {};
  let i = 0;
  const dormir = ms => new Promise(r => setTimeout(r, ms));
  async function uno(url) {
    for (let intento = 0; intento < 4; intento++) {
      try {
        const r = await fetch(url, {headers: {'Accept': 'application/json'}});
        if (r.status === 204) return {status: 204, body: null};
        if (r.status === 403 || r.status === 401) return {status: r.status, body: null};
        if (r.status === 429 || r.status >= 500) { await dormir(1500 * (intento + 1)); continue; }
        const ct = r.headers.get('content-type') || '';
        if (!ct.includes('json')) return {status: r.status, body: null, html: true};
        return {status: r.status, body: await r.json()};
      } catch (e) { await dormir(1000 * (intento + 1)); }
    }
    return {status: 0, body: null};
  }
  async function worker() {
    while (i < urls.length) {
      const url = urls[i++];
      out[url] = await uno(url);
      await dormir(minMs + Math.random() * (maxMs - minMs));
    }
  }
  await Promise.all(Array.from({length: conc}, worker));
  return out;
}
"""


class FetcherNavegador:
    """Ejecuta GET dentro de la página de ONPE (mismo origen, sesión de navegador real)."""

    def __init__(self, page):
        self.page = page

    def __call__(self, urls: list[str]) -> dict[str, dict]:
        resultado: dict[str, dict] = {}
        for i in range(0, len(urls), LOTE):
            lote = urls[i:i + LOTE]
            resultado.update(self.page.evaluate(
                JS_POOL, {"urls": lote, "conc": 4, "minMs": 120, "maxMs": 350}))
            malas = [(u, r) for u, r in resultado.items()
                     if r["status"] in (401, 403) or (r.get("html") and r["status"] == 200)]
            if malas:
                u, r = malas[0]
                raise Bloqueado(f"ONPE devolvió estado {r['status']}{' (HTML en vez de JSON)' if r.get('html') else ''} en {u}")
        return resultado


# --------------------------------------------------------------------------- recolección
def _datos(resp: dict | None):
    if not resp or resp.get("status") != 200 or resp.get("body") is None:
        return None
    body = resp["body"]
    return body.get("data") if isinstance(body, dict) and "data" in body else body


def consultar_unidades(fetch, id_eleccion: int, nivel: str, unidades: list[dict]) -> list[dict]:
    """Totales + participantes de cada unidad. Devuelve registros con 'qc' (lista de problemas)."""
    urls = []
    for u in unidades:
        urls.append(url_resumen("totales", id_eleccion, nivel, u))
        urls.append(url_resumen("participantes", id_eleccion, nivel, u))
    respuestas = fetch(urls) if urls else {}
    registros = []
    for u in unidades:
        tot = _datos(respuestas.get(url_resumen("totales", id_eleccion, nivel, u)))
        par = _datos(respuestas.get(url_resumen("participantes", id_eleccion, nivel, u)))
        registros.append({
            "ubigeo": u["ubigeo"], "nombre": u["nombre"], "dep": u["dep"], "prov": u["prov"],
            "totales": tot, "participantes": par, "qc": T.qc_unidad(tot, par) if tot else ["sin_totales"],
        })
    return registros


def _leer(ruta: Path) -> list[dict]:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def recolectar(fetch, out: Path, modo: str, ahora: datetime | None = None) -> dict:
    """Lógica completa (sin Playwright): devuelve {archivo: contenido} y un resumen."""
    ahora = ahora or datetime.now(timezone.utc)
    crudo = _datos(fetch([RUTA_UBIGEOS])[RUTA_UBIGEOS])
    if not crudo:
        raise RuntimeError("No se pudo obtener el catálogo de ubigeos")
    ub = T.parse_ubigeos(crudo)
    smoke = modo == "smoke"
    if smoke:
        ub = {k: v[:SMOKE_N] for k, v in ub.items()}

    deps = consultar_unidades(fetch, ID_REGIONAL, "dep", ub["dep"])
    provs = consultar_unidades(fetch, ID_MUNICIPAL, "prov", ub["prov"])

    prev_prov = _leer(out / "municipal_provincias.json")
    prev_dist = _leer(out / "municipal_distritos.json")
    consultar, copiar = T.planificar_distritos(prev_prov, provs, prev_dist, ub["dist"],
                                               completo=(modo != "incremental"))
    dists = consultar_unidades(fetch, ID_MUNICIPAL, "dist", consultar) + copiar
    dists.sort(key=lambda r: r["ubigeo"])

    problemas = {r["ubigeo"]: r["qc"] for r in deps + provs + dists if r.get("qc")}
    archivos = {
        "regional_departamentos.json": deps,
        "municipal_provincias.json": provs,
        "municipal_distritos.json": dists,
    }
    h = T.huella(archivos)
    csv_top2 = T.a_csv(T.top2_regional(deps))
    meta = {
        "generado_utc": ahora.isoformat(timespec="seconds"),
        "modo": modo,
        "fuente": "ONPE – Resultados Electorales ERM 2026 (https://resultadoelectoral.onpe.gob.pe)",
        "huella": h,
        "conteo": {"departamentos": len(deps), "provincias": len(provs), "distritos": len(dists),
                   "distritos_consultados": len(consultar), "distritos_copiados": len(copiar)},
        "problemas_qc": problemas,
    }
    return {"archivos": archivos, "csv": csv_top2, "meta": meta}


def escribir(out: Path, resultado: dict) -> bool:
    """Escribe solo si cambió la huella. Devuelve True si hubo cambios."""
    out.mkdir(parents=True, exist_ok=True)
    meta_prev = {}
    try:
        meta_prev = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    if meta_prev.get("huella") == resultado["meta"]["huella"] and meta_prev.get("modo") == resultado["meta"]["modo"]:
        return False
    for nombre, contenido in resultado["archivos"].items():
        (out / nombre).write_text(json.dumps(contenido, ensure_ascii=False, separators=(",", ":")),
                                  encoding="utf-8")
    (out / "results.csv").write_text(resultado["csv"], encoding="utf-8")
    (out / "meta.json").write_text(json.dumps(resultado["meta"], ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    return True


# --------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--full", action="store_true")
    g.add_argument("--smoke", action="store_true")
    ap.add_argument("--headed", action="store_true", help="navegador con ventana (no headless)")
    ap.add_argument("--chrome", action="store_true", help="usar Google Chrome instalado en vez de Chromium")
    ap.add_argument("--dry-run", action="store_true", help="no escribe archivos")
    args = ap.parse_args(argv)
    modo = "smoke" if args.smoke else "full" if args.full else "incremental"
    out = Path(args.out)

    from playwright.sync_api import sync_playwright  # import tardío: los tests no lo requieren

    try:
        with sync_playwright() as pw:
            opciones = {"headless": not args.headed}
            if args.chrome:
                opciones["channel"] = "chrome"
            browser = pw.chromium.launch(**opciones)
            ctx = browser.new_context(locale="es-PE", timezone_id="America/Lima")
            page = ctx.new_page()
            resp = page.goto(PAGINA_INICIO, wait_until="networkidle", timeout=60_000)
            if resp is None or resp.status >= 400:
                print(f"BLOQUEO: la página de inicio respondió {getattr(resp, 'status', None)}", file=sys.stderr)
                return EXIT_BLOQUEO
            resultado = recolectar(FetcherNavegador(page), out, modo)
            browser.close()
    except Bloqueado as e:
        print(f"BLOQUEO: {e}. No se evade; se conservan los datos anteriores.", file=sys.stderr)
        return EXIT_BLOQUEO
    except Exception as e:  # red, timeouts, etc.
        print(f"ERROR de red/ejecución: {e}", file=sys.stderr)
        return EXIT_RED

    meta = resultado["meta"]
    print(json.dumps({k: meta[k] for k in ("modo", "conteo")}, ensure_ascii=False))
    if meta["problemas_qc"]:
        print(f"QC: {len(meta['problemas_qc'])} unidades con problemas", file=sys.stderr)
        for k, v in list(meta["problemas_qc"].items())[:20]:
            print(f"  {k}: {v}", file=sys.stderr)
        return EXIT_QC  # no se publica nada si falla el QC
    if args.dry_run:
        return 0
    print("cambios" if escribir(out, resultado) else "sin cambios")
    return 0


if __name__ == "__main__":
    sys.exit(main())
