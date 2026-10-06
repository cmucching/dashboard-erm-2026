import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scraper"))
import onpe_scraper as S  # noqa: E402
import transform as T  # noqa: E402

FIX = RAIZ / "tests" / "fixtures"


def fx(nombre):
    return json.loads((FIX / nombre).read_text(encoding="utf-8"))["data"]


class TestUbigeos(unittest.TestCase):
    def test_clasificar(self):
        self.assertEqual(T.clasificar_ubigeo("000000"), "nacion")
        self.assertEqual(T.clasificar_ubigeo("010000"), "dep")
        self.assertEqual(T.clasificar_ubigeo("010100"), "prov")
        self.assertEqual(T.clasificar_ubigeo("010101"), "dist")
        self.assertIsNone(T.clasificar_ubigeo("1"))

    def test_parse_excluye_exterior(self):
        filas = [{"c_ubigeo": "010000", "c_nombre": "AMAZONAS"},
                 {"c_ubigeo": "010101", "c_nombre": "CHACHAPOYAS"},
                 {"c_ubigeo": "900000", "c_nombre": "EXTERIOR"}]
        r = T.parse_ubigeos(filas)
        self.assertEqual(len(r["dep"]), 1)
        self.assertEqual(r["dist"][0]["prov"], "010100")


class TestQC(unittest.TestCase):
    def test_fixtures_correctos(self):
        self.assertEqual(T.qc_unidad(fx("e1_dep_amazonas_totales.json"),
                                     fx("e1_dep_amazonas_participantes.json")), [])
        self.assertEqual(T.qc_unidad(fx("e3_prov_chachapoyas_totales.json"),
                                     fx("e3_prov_chachapoyas_participantes.json")), [])

    def test_suma_distinta(self):
        par = fx("e1_dep_amazonas_participantes.json")
        par[0]["totalVotosValidos"] += 50
        self.assertTrue(any(p.startswith("suma_votos") for p in
                            T.qc_unidad(fx("e1_dep_amazonas_totales.json"), par)))

    def test_sin_totales(self):
        self.assertEqual(T.qc_unidad(None, []), ["sin_totales"])


class TestFormato(unittest.TestCase):
    def test_hora(self):
        self.assertEqual(T.formato_hora_onpe("2026-10-06T16:16:01.569Z"), "06/10/2026 · 11:16:01 a. m.")

    def test_nombres(self):
        self.assertEqual(T.titulo_es("MADRE DE DIOS"), "Madre de Dios")
        self.assertEqual(T.nombre_region("LIMA", "150000"), "Lima región")
        self.assertEqual(T.slug_cartilla("SAN MARTÍN", "220000"), "san-martin")

    def test_top2_y_csv(self):
        reg = [{"ubigeo": "010000", "nombre": "AMAZONAS",
                "totales": fx("e1_dep_amazonas_totales.json"),
                "participantes": fx("e1_dep_amazonas_participantes.json")}]
        filas = T.top2_regional(reg)
        self.assertEqual([f["puesto"] for f in filas], [1, 2])
        self.assertEqual(filas[0]["candidato"], "Amilcar Diaz Mendoza")
        self.assertEqual(filas[0]["votos"], 51974)
        csv_txt = T.a_csv(filas)
        self.assertTrue(csv_txt.startswith("﻿"))
        self.assertIn('"Amazonas"', csv_txt)


class TestIncremental(unittest.TestCase):
    def test_solo_provincias_cambiadas(self):
        t1 = {"contabilizadas": 1, "enviadasJee": 0, "pendientesJee": 0, "totalVotosValidos": 10}
        t2 = dict(t1, contabilizadas=2)
        dists = [{"ubigeo": "010101", "prov": "010100"}, {"ubigeo": "020101", "prov": "020100"}]
        prev_prov = [{"ubigeo": "010100", "totales": t1}, {"ubigeo": "020100", "totales": t1}]
        nuevo = [{"ubigeo": "010100", "totales": t2}, {"ubigeo": "020100", "totales": t1}]
        prev_dist = [{"ubigeo": "010101"}, {"ubigeo": "020101"}]
        cons, cop = T.planificar_distritos(prev_prov, nuevo, prev_dist, dists, completo=False)
        self.assertEqual([d["ubigeo"] for d in cons], ["010101"])
        self.assertEqual([d["ubigeo"] for d in cop], ["020101"])
        cons, cop = T.planificar_distritos(prev_prov, nuevo, prev_dist, dists, completo=True)
        self.assertEqual(len(cons), 2)


class TestScraperConFetcherFalso(unittest.TestCase):
    def fetcher(self):
        ub = [{"c_ubigeo": "010000", "c_nombre": "AMAZONAS"},
              {"c_ubigeo": "010100", "c_nombre": "CHACHAPOYAS"},
              {"c_ubigeo": "010101", "c_nombre": "CHACHAPOYAS"}]
        reg_t, reg_p = fx("e1_dep_amazonas_totales.json"), fx("e1_dep_amazonas_participantes.json")
        mun_t, mun_p = fx("e3_prov_chachapoyas_totales.json"), fx("e3_prov_chachapoyas_participantes.json")

        def f(urls):
            out = {}
            for u in urls:
                if u == S.RUTA_UBIGEOS:
                    out[u] = {"status": 200, "body": ub}
                    continue
                reg = "idEleccion=1" in u
                kind = "totales" if "/totales?" in u else "participantes"
                dato = (reg_t if kind == "totales" else reg_p) if reg else (mun_t if kind == "totales" else mun_p)
                out[u] = {"status": 200, "body": {"data": dato}}
            return out
        return f

    def test_url(self):
        u = S.url_resumen("totales", 3, "dist", {"ubigeo": "010101", "prov": "010100", "dep": "010000"})
        self.assertIn("tipoFiltro=ubigeo_nivel_03", u)
        self.assertIn("idUbigeoDistrito=010101", u)

    def test_recolectar_y_escribir(self):
        ahora = datetime(2026, 10, 6, 17, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            r = S.recolectar(self.fetcher(), out, "full", ahora)
            self.assertEqual(r["meta"]["conteo"], {"departamentos": 1, "provincias": 1, "distritos": 1,
                                                   "distritos_consultados": 1, "distritos_copiados": 0})
            # los fixtures de provincia se reutilizan como distrito: pasan el QC igualmente
            self.assertEqual(r["meta"]["problemas_qc"], {})
            self.assertTrue(S.escribir(out, r))
            self.assertFalse(S.escribir(out, S.recolectar(self.fetcher(), out, "full", ahora)))
            self.assertTrue((out / "results.csv").read_text(encoding="utf-8").startswith("﻿"))


class TestReanudacion(TestScraperConFetcherFalso):
    def test_retoma_tras_bloqueo(self):
        base = self.fetcher()
        llamadas = {"n": 0, "bloquear": True}

        def f(urls):
            llamadas["n"] += 1
            if llamadas["bloquear"] and any("ubigeo_nivel_03" in u for u in urls):
                raise S.Bloqueado("403 simulado")
            return base(urls)

        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "avance.json"
            with self.assertRaises(S.Bloqueado):
                S.recolectar(f, Path(d), "full", cache_path=cache)
            llamadas["bloquear"] = False
            r = S.recolectar(f, Path(d), "full", cache_path=cache)
            self.assertEqual(r["meta"]["conteo"]["distritos"], 1)


if __name__ == "__main__":
    unittest.main()
