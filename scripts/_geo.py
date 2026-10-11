import json, unicodedata
from pathlib import Path
S = Path(__file__).resolve().parent.parent / "site"
ALIAS = {"ANTONIO RAYMONDI": "ANTONIO RAIMONDI"}
def norm(s): return "".join(c for c in unicodedata.normalize("NFD", str(s).upper()) if unicodedata.category(c) != "Mn").strip()
def mapa_provincias():
    """(id geometría INEI de 4 dígitos) -> ubigeo provincial ONPE de 6 dígitos, por nombre de departamento + provincia."""
    md = json.loads((S / "api" / "municipal-data.json").read_text(encoding="utf-8"))["records"]
    por = {(norm(r["department"]), norm(r["province"])): r["ubigeo"] for r in md if r["level"] == "provincial"}
    fp = json.loads((S / "map-geography.json").read_text(encoding="utf-8"))["provincial"]["features"]
    out, falta = {}, []
    for f in fp:
        p = f["properties"]; k = (norm(p["department"]), norm(p["province"]))
        k = (k[0], ALIAS.get(k[1], k[1]))
        if k in por: out[p["id"]] = por[k]
        else: falta.append(k)
    return out, falta, fp
