"""Funciones puras del pipeline ERM 2026: ubigeos, control de calidad, ranking y CSV.

No hacen red ni escriben archivos, para poder probarlas sin conexión.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone

LIMA_TZ = timezone(timedelta(hours=-5))  # Perú: UTC-5, sin horario de verano
PARTICULAS = {"De", "Del", "La", "Las", "Los", "Y", "El"}
MAX_DEP_PERU = 25  # departamentos 01-25; códigos mayores se asumen exterior [VERIFICAR]

CSV_COLUMNAS = [
    "region", "puesto", "organizacion", "candidato", "votos",
    "porcentaje_validos", "actas_contabilizadas", "actualizacion_onpe",
    "fuente_candidatura",
]


# --------------------------------------------------------------------------- ubigeos
def clasificar_ubigeo(codigo: str | None) -> str | None:
    """Devuelve 'nacion', 'dep', 'prov', 'dist' o None según el código de 6 dígitos."""
    if not codigo or not re.fullmatch(r"\d{6}", codigo):
        return None
    if codigo == "000000":
        return "nacion"
    if codigo[2:] == "0000":
        return "dep"
    if codigo[4:] == "00":
        return "prov"
    return "dist"


def parse_ubigeos(filas: list[dict]) -> dict[str, list[dict]]:
    """Agrupa assets/ubig/v1.json en dep/prov/dist (solo territorio nacional)."""
    salida: dict[str, list[dict]] = {"dep": [], "prov": [], "dist": []}
    for fila in filas:
        codigo = fila.get("c_ubigeo")
        nivel = clasificar_ubigeo(codigo)
        if nivel not in salida:
            continue
        if int(codigo[:2]) > MAX_DEP_PERU:
            continue
        salida[nivel].append({
            "ubigeo": codigo,
            "nombre": fila.get("c_nombre", ""),
            "dep": codigo[:2] + "0000",
            "prov": codigo[:4] + "00",
        })
    for lista in salida.values():
        lista.sort(key=lambda u: u["ubigeo"])
    return salida


# --------------------------------------------------------------------------- control de calidad
def qc_unidad(totales: dict | None, participantes: list | None) -> list[str]:
    """Lista de problemas de una unidad territorial (vacía = correcta)."""
    problemas: list[str] = []
    if not totales:
        return ["sin_totales"]
    pct = totales.get("actasContabilizadas")
    if pct is None or not (0 <= pct <= 100):
        problemas.append("pct_actas_fuera_de_rango")
    cont, total = totales.get("contabilizadas"), totales.get("totalActas")
    if cont is not None and total is not None and cont > total:
        problemas.append("contabilizadas_mayor_que_total")
    if participantes is None:
        problemas.append("sin_participantes")
        return problemas
    suma = sum(p.get("totalVotosValidos", 0) for p in participantes)
    validos = totales.get("totalVotosValidos", 0)
    if abs(suma - validos) > 1:  # tolerancia de ±1 voto por redondeo
        problemas.append(f"suma_votos_{suma}_distinta_de_validos_{validos}")
    return problemas


# --------------------------------------------------------------------------- incremental
def firma_totales(totales: dict | None) -> tuple | None:
    """Huella barata de una unidad: si no cambia, no hace falta bajar sus distritos."""
    if not totales:
        return None
    return (
        totales.get("contabilizadas"), totales.get("enviadasJee"),
        totales.get("pendientesJee"), totales.get("totalVotosValidos"),
    )


def planificar_distritos(prev_prov: list[dict], nuevo_prov: list[dict],
                         prev_dist: list[dict], distritos: list[dict],
                         completo: bool) -> tuple[list[dict], list[dict]]:
    """Separa distritos a consultar de distritos que se copian del corte anterior."""
    if completo or not prev_dist:
        return list(distritos), []
    firmas_prev = {r["ubigeo"]: firma_totales(r.get("totales")) for r in prev_prov}
    cambiadas = {
        r["ubigeo"] for r in nuevo_prov
        if firmas_prev.get(r["ubigeo"]) != firma_totales(r.get("totales"))
    }
    previos = {r["ubigeo"]: r for r in prev_dist}
    consultar, copiar = [], []
    for d in distritos:
        if d["prov"] in cambiadas or d["ubigeo"] not in previos:
            consultar.append(d)
        else:
            copiar.append(previos[d["ubigeo"]])
    return consultar, copiar


# --------------------------------------------------------------------------- CSV del dashboard
def titulo_es(texto: str) -> str:
    """'MADRE DE DIOS' -> 'Madre de Dios' (partículas en minúscula)."""
    palabras = texto.strip().lower().title().split(" ")
    return " ".join(
        p.lower() if (i > 0 and p in PARTICULAS) else p for i, p in enumerate(palabras)
    )


def nombre_region(nombre_dep: str, ubigeo: str) -> str:
    # En el dashboard actual el departamento Lima (sin Lima Metropolitana) es "Lima región"
    if ubigeo == "150000":
        return "Lima región"
    return titulo_es(nombre_dep)


def slug_cartilla(nombre_dep: str, ubigeo: str) -> str:
    if ubigeo == "150000":
        return "lima-provincias"
    sin_tildes = unicodedata.normalize("NFD", nombre_dep.lower())
    sin_tildes = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", sin_tildes).strip("-")


def formato_hora_onpe(fecha_iso: str) -> str:
    """'2026-10-06T16:16:01.569Z' -> '06/10/2026 · 11:16:01 a. m.' (hora de Lima)."""
    dt = datetime.fromisoformat(fecha_iso.replace("Z", "+00:00")).astimezone(LIMA_TZ)
    sufijo = "a. m." if dt.hour < 12 else "p. m."
    hora12 = dt.hour % 12 or 12
    return f"{dt:%d/%m/%Y} · {hora12:02d}:{dt:%M:%S} {sufijo}"


def top2_regional(registros_dep: list[dict]) -> list[dict]:
    """Primer y segundo puesto por departamento (elección regional), orden estable."""
    filas = []
    for r in registros_dep:
        participantes = r.get("participantes") or []
        totales = r.get("totales") or {}
        if not participantes:
            continue
        orden = sorted(participantes, key=lambda p: p["totalVotosValidos"], reverse=True)[:2]
        for puesto, p in enumerate(orden, start=1):
            filas.append({
                "region": nombre_region(r["nombre"], r["ubigeo"]),
                "puesto": puesto,
                "organizacion": p["nombreAgrupacionPolitica"],
                "candidato": titulo_es(p.get("nombreCandidato") or ""),
                "votos": p["totalVotosValidos"],
                "porcentaje_validos": f'{p["porcentajeVotosValidos"]:.3f}',
                "actas_contabilizadas": f'{totales.get("actasContabilizadas", 0):.3f}',
                "actualizacion_onpe": formato_hora_onpe(totales["fechaActualizacion"]),
                "fuente_candidatura": (
                    "https://votoinformado.jne.gob.pe/pdf/cartillas/"
                    f'cartilla-erm-{slug_cartilla(r["nombre"], r["ubigeo"])}.pdf'
                ),
            })
    return filas


def a_csv(filas: list[dict]) -> str:
    """CSV con BOM y comillas, mismo formato que /api/results.csv del dashboard actual."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNAS, quoting=csv.QUOTE_ALL, lineterminator="\n")
    w.writeheader()
    w.writerows(filas)
    return "﻿" + buf.getvalue()


# --------------------------------------------------------------------------- huella de datos
def huella(payloads: dict[str, object]) -> str:
    """SHA-256 estable de los datos publicados; si no cambia, no se hace commit."""
    h = hashlib.sha256()
    for clave in sorted(payloads):
        h.update(clave.encode())
        h.update(json.dumps(payloads[clave], sort_keys=True, ensure_ascii=False,
                            separators=(",", ":")).encode())
    return h.hexdigest()
