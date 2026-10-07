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
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transform as T  # noqa: E402

BASE = "https://resultadoelectoral.onpe.gob.pe"
PAGINA_INICIO = f"{BASE}/main/alcance-electoral"
API = "/presentacion-backend"
RUTA_UBIGEOS = "/assets/ubig/v1.json"  # verificado: archivo estático en la raíz del sitio
ID_REGIONAL, ID_MUNICIPAL, ID_DISTRITAL = 1, 3, 4  # 3 = alcalde provincial; 4 = alcalde distrital (verificado con --descubrir)
LOTE = 40
RITMO = {"conc": 2, "min": 500, "max": 1100}  # pedidos en paralelo y pausa (ms); ajustable con --hilos/--pausa-ms
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
  let parar = false;
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
    while (i < urls.length && !parar) {
      const url = urls[i++];
      out[url] = await uno(url);
      if (out[url].status === 401 || out[url].status === 403) parar = true;
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

    def _lote(self, lote: list[str]) -> dict[str, dict]:
        """Si la web de ONPE navega/recarga a mitad del lote, espera la carga y reintenta (hasta 4 veces)."""
        for intento in range(5):
            try:
                return self.page.evaluate(
                    JS_POOL, {"urls": lote, "conc": RITMO["conc"], "minMs": RITMO["min"], "maxMs": RITMO["max"]})
            except Exception as e:
                if intento == 4 or not any(k in str(e) for k in ("Execution context", "navigation", "Target closed")):
                    raise
                print(f"  (la página se recargó; reintento {intento + 1}/4)", file=sys.stderr, flush=True)
                try:
                    self.page.wait_for_load_state("networkidle", timeout=30_000)
                except Exception:
                    pass
                time.sleep(3)
                if not self.page.url.startswith(BASE) or "alcance-electoral" not in self.page.url:
                    self.page.goto(PAGINA_INICIO, wait_until="networkidle", timeout=60_000)

    def __call__(self, urls: list[str]) -> dict[str, dict]:
        resultado: dict[str, dict] = {}
        for i in range(0, len(urls), LOTE):
            lote = urls[i:i + LOTE]
            resultado.update(self._lote(lote))
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


def consultar_unidades(fetch, id_eleccion: int, nivel: str, unidades: list[dict], vacio_ok: bool = False) -> list[dict]:
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
        if vacio_ok and not tot and not par:
            # distrito sin elección distrital propia (p. ej. capital de provincia): no es un error
            registros.append({"ubigeo": u["ubigeo"], "nombre": u["nombre"], "dep": u["dep"], "prov": u["prov"],
                              "totales": None, "participantes": None, "qc": [], "sin_eleccion": True})
            continue
        registros.append({
            "ubigeo": u["ubigeo"], "nombre": u["nombre"], "dep": u["dep"], "prov": u["prov"],
            "totales": tot, "participantes": par, "qc": T.qc_unidad(tot, par) if tot else ["sin_totales"],
        })
    return registros


def consultar_capitales(fetch, sin_eleccion: list[dict], catalogo: list[dict]) -> list[dict]:
    """Elección provincial (id 3) a nivel de distrito para los distritos sin elección distrital."""
    por_ub = {d["ubigeo"]: d for d in catalogo}
    unidades = [por_ub[r["ubigeo"]] for r in sin_eleccion if r["ubigeo"] in por_ub]
    print(f"Capitales de provincia (voto provincial en el distrito): {len(unidades)}", file=sys.stderr, flush=True)
    regs = []
    t0 = time.time()
    for i in range(0, len(unidades), 20):
        regs += consultar_unidades(fetch, ID_MUNICIPAL, "dist", unidades[i:i + 20])
        print(f"  capitales {min(i + 20, len(unidades))}/{len(unidades)} ({time.time() - t0:.0f} s)",
              file=sys.stderr, flush=True)
    return regs


ID_PROV_LIMA = "140100"


def consultar_lima(fetch, catalogo: list[dict]) -> list[dict]:
    """Alcaldía de Lima Metropolitana (elección provincial) a nivel de cada uno de sus distritos.

    Sirve para proyectar lo que falta contar por distrito (modelo MAG aplicado a Lima)."""
    unidades = [d for d in catalogo if d.get("prov") == ID_PROV_LIMA]
    print(f"Lima Metropolitana: voto metropolitano en {len(unidades)} distritos", file=sys.stderr, flush=True)
    return consultar_unidades(fetch, ID_MUNICIPAL, "dist", unidades) if unidades else []


def _leer(ruta: Path) -> list[dict]:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _guardar_cache(path: Path | None, modo: str, regs: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"modo": modo, "regs": regs}, ensure_ascii=False,
                               separators=(",", ":")), encoding="utf-8")


def _cargar_cache(path: Path | None, modo: str) -> dict:
    """Reutiliza el avance guardado si es reciente (completo: 3 h; incremental: 20 min).
    Ya no depende de que los totales provinciales sigan idénticos: ONPE los actualiza sin parar."""
    if path is None:
        return {}
    try:
        c = json.loads(path.read_text(encoding="utf-8"))
        edad = time.time() - path.stat().st_mtime
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if c.get("modo") not in (None, modo):
        return {}
    return c.get("regs", {}) if edad < (3 * 3600 if modo == "full" else 20 * 60) else {}


def recolectar(fetch, out: Path, modo: str, ahora: datetime | None = None,
               cache_path: Path | None = None) -> dict:
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
                                               completo=True)  # los totales provinciales ya no sirven de proxy: la elección distrital es otra
    # Avance guardado: si ONPE corta (403) a mitad de camino, la siguiente corrida retoma desde aquí.
    clave = modo + "_distrital"
    avance = _cargar_cache(cache_path, clave)
    if avance:
        print(f"Se reutiliza avance guardado: {len(avance)} distritos", file=sys.stderr, flush=True)
    pendientes = [d for d in consultar if d["ubigeo"] not in avance]
    t0 = time.time()
    total = len(consultar)
    print(f"Distritos por consultar: {len(pendientes)} (ya guardados: {total - len(pendientes)} de {total})", file=sys.stderr, flush=True)
    try:
        for i in range(0, len(pendientes), 100):
            for r in consultar_unidades(fetch, ID_DISTRITAL, "dist", pendientes[i:i + 100], vacio_ok=True):
                avance[r["ubigeo"]] = r
            _guardar_cache(cache_path, clave, avance)
            hechos = min(i + 100, len(pendientes))
            seg = time.time() - t0
            falta = seg / hechos * (len(pendientes) - hechos) if hechos else 0
            print(f"Avance: {total - len(pendientes) + hechos}/{total} distritos "
                  f"({(total - len(pendientes) + hechos) / total:.0%}) · transcurrido {int(seg // 60)} min · "
                  f"faltan unos {int(falta // 60)} min", file=sys.stderr, flush=True)
    except Bloqueado:
        _guardar_cache(cache_path, clave, avance)
        raise
    print("Descarga terminada; validando y armando archivos…", file=sys.stderr, flush=True)
    dists = [avance[d["ubigeo"]] for d in consultar] + copiar
    dists.sort(key=lambda r: r["ubigeo"])

    # Distritos capitales de provincia: no tienen alcalde distrital (ONPE responde 204), pero su votación
    # (elección provincial dentro del distrito) sí existe y se muestra de forma individualizada.
    capitales = consultar_capitales(fetch, [d for d in dists if d.get("sin_eleccion")], ub["dist"])
    lima = consultar_lima(fetch, ub["dist"])
    problemas = {r["ubigeo"]: r["qc"] for r in deps + provs + dists + capitales + lima if r.get("qc")}
    archivos = {
        "regional_departamentos.json": deps,
        "municipal_provincias.json": provs,
        "municipal_distritos.json": dists,
        "municipal_capitales.json": capitales,
        "municipal_lima.json": lima,
    }
    h = T.huella(archivos)
    csv_top2 = T.a_csv(T.top2_regional(deps))
    meta = {
        "generado_utc": ahora.isoformat(timespec="seconds"),
        "modo": modo,
        "fuente": "ONPE – Resultados Electorales ERM 2026 (https://resultadoelectoral.onpe.gob.pe)",
        "huella": h,
        "id_distrital": ID_DISTRITAL,
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


# --------------------------------------------------------------------------- diagnóstico
def descubrir_elecciones(fetch) -> None:
    """Para idEleccion 1..12 muestra totales/participantes a nivel nación, provincia y distrito de prueba."""
    prueba_prov = {"dep": "010000", "prov": "010100", "ubigeo": "010100"}
    prueba_dist = {"dep": "010000", "prov": "010100", "ubigeo": "010102"}  # Asunción (Chachapoyas, Amazonas)
    for ide in range(1, 13):
        for etiqueta, nivel, u in (("nación", "nacion", None), ("provincia Chachapoyas", "prov", prueba_prov),
                                   ("distrito Asunción", "dist", prueba_dist)):
            try:
                tot = _datos(fetch([url_resumen("totales", ide, nivel, u)]).get(url_resumen("totales", ide, nivel, u)))
                par = _datos(fetch([url_resumen("participantes", ide, nivel, u)]).get(url_resumen("participantes", ide, nivel, u)))
            except Bloqueado as e:
                print(f"idEleccion={ide:2d} {etiqueta}: BLOQUEO {e}", flush=True)
                return
            if not tot and not par:
                print(f"idEleccion={ide:2d} {etiqueta}: sin datos", flush=True)
                continue
            nombres = ", ".join(f"{(p.get('nombreAgrupacionPolitica') or '')[:22]}={p.get('totalVotosValidos')}"
                                for p in sorted(par or [], key=lambda p: -(p.get('totalVotosValidos') or 0))[:3])
            print(f"idEleccion={ide:2d} {etiqueta}: válidos={(tot or {}).get('totalVotosValidos')} "
                  f"actas={(tot or {}).get('totalActas')} partic={len(par or [])} | {nombres}", flush=True)


def solo_capitales(fetch, out: Path) -> bool:
    dists = _leer(out / "municipal_distritos.json")
    if not dists:
        print("No hay data/municipal_distritos.json; corre primero la descarga completa.", file=sys.stderr)
        return False
    print(f"Leyendo catálogo de ubigeos… ({len(dists)} distritos en data/)", file=sys.stderr, flush=True)
    crudo = _datos(fetch([RUTA_UBIGEOS])[RUTA_UBIGEOS])
    ub = T.parse_ubigeos(crudo)
    caps = consultar_capitales(fetch, [d for d in dists if d.get("sin_eleccion")], ub["dist"])
    malos = {r["ubigeo"]: r["qc"] for r in caps if r.get("qc")}
    if malos:
        print(f"QC: {len(malos)} capitales con problemas: {list(malos.items())[:5]}", file=sys.stderr)
        return False
    (out / "municipal_capitales.json").write_text(json.dumps(caps, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Capitales guardadas: {len(caps)}")
    return True


def verificar_distritos(fetch, ubigeos: list[str]) -> None:
    """Muestra lo que ONPE devuelve ahora mismo para cada distrito (elección provincial=3 y distrital=4)."""
    for ub in ubigeos:
        u = {"dep": ub[:2] + "0000", "prov": ub[:4] + "00", "ubigeo": ub}
        for ide, nombre in ((ID_DISTRITAL, "ALCALDE DISTRITAL"), (ID_MUNICIPAL, "alcalde provincial en el distrito")):
            ut, up = url_resumen("totales", ide, "dist", u), url_resumen("participantes", ide, "dist", u)
            r = fetch([ut, up])
            tot, par = _datos(r.get(ut)), _datos(r.get(up))
            if not tot and not par:
                print(f"{ub} · {nombre}: ONPE no devuelve datos (estado {r.get(ut, {}).get('status')})", flush=True)
                continue
            print(f"{ub} · {nombre}: actas {tot.get('contabilizadas')}/{tot.get('totalActas')} "
                  f"({tot.get('actasContabilizadas')} %), JEE {tot.get('enviadasJee')}, pendientes {tot.get('pendientesJee')}, "
                  f"válidos {tot.get('totalVotosValidos')}, emitidos {tot.get('totalVotosEmitidos')}, "
                  f"corte {tot.get('fechaActualizacion')}", flush=True)
            for q in sorted(par or [], key=lambda q: -(q.get('totalVotosValidos') or 0))[:4]:
                print(f"     {q.get('nombreAgrupacionPolitica')}: {q.get('totalVotosValidos')} ({q.get('porcentajeVotosValidos')} %)", flush=True)


def descubrir_campos(page) -> None:
    """Muestra el JSON crudo de un distrito (elección 4) y las URLs de API que usa la propia web de ONPE."""
    u = {"dep": "010000", "prov": "010100", "ubigeo": "010102"}
    fetch = FetcherNavegador(page)
    for kind in ("totales", "participantes"):
        url = url_resumen(kind, ID_DISTRITAL, "dist", u)
        r = fetch([url]).get(url)
        print(f"\n== {kind} (distrito Asunción, idEleccion={ID_DISTRITAL}) ==", flush=True)
        print(json.dumps((r or {}).get("body"), ensure_ascii=False)[:1800], flush=True)
    vistas: dict[str, str] = {}

    def al_responder(resp):
        if "/presentacion-backend/" in resp.url and resp.url not in vistas:
            try:
                vistas[resp.url] = resp.text()[:300]
            except Exception:
                vistas[resp.url] = "(sin cuerpo)"
    page.on("response", al_responder)
    for ruta in ("/main/elecciones-municipales", "/main/resumen-general-municipal"):
        try:
            page.goto(BASE + ruta, wait_until="networkidle", timeout=45_000)
            page.wait_for_timeout(4000)
        except Exception as e:
            print(f"(no cargó {ruta}: {e})", flush=True)
    print("\n== URLs de API que usa la web ==", flush=True)
    for url, cuerpo in vistas.items():
        print(url.replace(BASE, ""), "\n   ", cuerpo[:200].replace("\n", " "), flush=True)


# --------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--full", action="store_true")
    g.add_argument("--smoke", action="store_true")
    ap.add_argument("--headed", action="store_true", help="navegador con ventana (no headless)")
    ap.add_argument("--chrome", action="store_true", help="usar Google Chrome instalado en vez de Chromium")
    ap.add_argument("--hilos", type=int, default=2, help="pedidos en paralelo (por defecto 2; más hilos aumentan el riesgo de 403)")
    ap.add_argument("--pausa-ms", type=int, default=500, help="pausa mínima entre pedidos de cada hilo (ms)")
    ap.add_argument("--dry-run", action="store_true", help="no escribe archivos")
    ap.add_argument("--solo-capitales", action="store_true",
                    help="rápido (~5 min): descarga solo el voto provincial de los distritos capitales y lo guarda en data/")
    ap.add_argument("--verificar", nargs="+", metavar="UBIGEO",
                    help="consulta en vivo estos distritos (p. ej. 010601 150411) y muestra lo que ONPE devuelve")
    ap.add_argument("--descubrir", action="store_true",
                    help="diagnóstico: muestra qué idEleccion de ONPE corresponde a cada elección (no escribe nada)")
    args = ap.parse_args(argv)
    RITMO.update(conc=max(1, min(args.hilos, 6)), min=args.pausa_ms, max=int(args.pausa_ms * 2.2))
    modo = "smoke" if args.smoke else "full" if args.full else "incremental"
    out = Path(args.out)

    from playwright.sync_api import sync_playwright  # import tardío: los tests no lo requieren

    try:
        with sync_playwright() as pw:
            opciones = {"headless": not args.headed}
            if args.chrome:
                opciones["channel"] = "chrome"
            print("Abriendo navegador…", file=sys.stderr, flush=True)
            browser = pw.chromium.launch(**opciones)
            print("Cargando página de ONPE (hasta 60 s)…", file=sys.stderr, flush=True)
            ctx = browser.new_context(locale="es-PE", timezone_id="America/Lima")
            page = ctx.new_page()
            resp = page.goto(PAGINA_INICIO, wait_until="networkidle", timeout=60_000)
            if resp is None or resp.status >= 400:
                print(f"BLOQUEO: la página de inicio respondió {getattr(resp, 'status', None)}", file=sys.stderr)
                return EXIT_BLOQUEO
            if args.solo_capitales:
                ok = solo_capitales(FetcherNavegador(page), out)
                browser.close()
                return 0 if ok else EXIT_QC
            if args.verificar:
                verificar_distritos(FetcherNavegador(page), args.verificar)
                browser.close()
                return 0
            if args.descubrir:
                descubrir_elecciones(FetcherNavegador(page))
                descubrir_campos(page)
                browser.close()
                return 0
            resultado = recolectar(FetcherNavegador(page), out, modo,
                                   cache_path=Path(".cache") / "avance_distritos_d4.json")
            print("Cerrando navegador…", file=sys.stderr, flush=True)
            try:
                browser.close()
            except Exception:
                pass
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
