"""
test_analizar.py
Al menos 4 pruebas con datos chicos propios, independientes del CSV real
(no se fija el numero real de peliculas ni sus cifras, porque la copia
local se modifica a proposito en los pasos 7 y 8 de la practica).

Correr con: python -m unittest discover -v
"""
import csv
import os
import shutil
import tempfile
import unittest

import analizar


FIELDNAMES_CHICO = [
    "year", "imdb", "title", "test", "clean_test", "binary",
    "budget", "domgross", "intgross", "code",
    "budget_2013$", "domgross_2013$", "intgross_2013$", "period code", "decade code",
]

OTRAS_COLUMNAS = {
    "test": "notalk", "clean_test": "notalk", "binary": "FAIL",
    "intgross": "1", "code": "X", "budget_2013$": "1", "domgross_2013$": "1",
    "intgross_2013$": "1", "period code": "1", "decade code": "1",
}


def fila(imdb, title, year, budget, domgross):
    base = {"year": year, "imdb": imdb, "title": title, "budget": budget, "domgross": domgross}
    base.update(OTRAS_COLUMNAS)
    return base


FILAS_EJEMPLO = [
    fila("tt0000001", "Pelicula Uno", "2000", "1000000", "3000000"),
    fila("tt0000002", "Pelicula Dos", "2001", "2000000", "4000000"),
    fila("tt0000003", "Pelicula Tres &amp; Cia", "2002", "NA", "NA"),
]


class TestCalculoConDatosConocidos(unittest.TestCase):
    def test_suma_y_media_conocidas(self):
        """Con cifras chicas y conocidas, la suma de domgross y la media de
        budget deben ser exactamente las esperadas."""
        peliculas = analizar.validar_filas(FIELDNAMES_CHICO, FILAS_EJEMPLO)
        stats = analizar.calcular(peliculas)

        self.assertEqual(stats["total"], 3)
        # domgross disponible: 3,000,000 + 4,000,000 (la tercera es NA)
        self.assertEqual(stats["suma_domgross"], 7_000_000)
        # budget disponible: (1,000,000 + 2,000,000) / 2
        self.assertEqual(stats["media_budget"], 1_500_000)
        self.assertEqual(stats["faltantes_domgross"], 1)


class TestValoresFaltantes(unittest.TestCase):
    def test_na_no_se_convierte_en_cero(self):
        """NA/#N/A/vacio deben quedar como None (faltante), nunca como 0."""
        peliculas = analizar.validar_filas(FIELDNAMES_CHICO, FILAS_EJEMPLO)
        tercera = next(p for p in peliculas if p["imdb"] == "tt0000003")
        self.assertIsNone(tercera["budget"])
        self.assertIsNone(tercera["domgross"])
        self.assertNotEqual(tercera["budget"], 0)
        self.assertNotEqual(tercera["domgross"], 0)

    def test_marca_numerica_opcional_acepta_na_vacio_y_hashn_a(self):
        """La consigna admite NA/vacio; el CSV real de FiveThirtyEight usa
        '#N/A', asi que las tres marcas deben tratarse igual (faltante)."""
        errores = []
        for marca in ("NA", "", "#N/A"):
            resultado = analizar._valor_numerico_opcional(marca, "domgross", 2, errores)
            self.assertIsNone(resultado)
        self.assertEqual(errores, [])


class TestRechazoDeDatosInvalidos(unittest.TestCase):
    def test_rechazo_de_domgross_negativo(self):
        """Un domgross negativo debe rechazar todo el archivo (no se
        descarta en silencio la fila: se detiene el programa)."""
        filas_con_negativo = [
            fila("tt0000001", "Pelicula Uno", "2000", "1000000", "-100"),
        ]
        with self.assertRaises(analizar.DatosInvalidos) as cm:
            analizar.validar_filas(FIELDNAMES_CHICO, filas_con_negativo)
        mensaje = "\n".join(cm.exception.errores)
        self.assertIn("fila 2", mensaje)
        self.assertIn("domgross", mensaje)

    def test_rechazo_de_columna_obligatoria_ausente(self):
        """Si falta una columna obligatoria (p. ej. 'domgross') en la
        cabecera, debe detenerse con un mensaje claro."""
        cabecera_incompleta = [c for c in FIELDNAMES_CHICO if c != "domgross"]
        with self.assertRaises(analizar.DatosInvalidos) as cm:
            analizar.validar_estructura(cabecera_incompleta)
        mensaje = "\n".join(cm.exception.errores)
        self.assertIn("domgross", mensaje)

    def test_rechazo_de_imdb_vacio_o_duplicado(self):
        """imdb vacio o repetido debe juntarse como error, con su fila."""
        filas = [
            fila("", "Sin id", "2000", "1000000", "2000000"),
            fila("tt0000009", "Repetida A", "2001", "1000000", "2000000"),
            fila("tt0000009", "Repetida B", "2002", "1000000", "2000000"),
        ]
        with self.assertRaises(analizar.DatosInvalidos) as cm:
            analizar.validar_filas(FIELDNAMES_CHICO, filas)
        mensaje = "\n".join(cm.exception.errores)
        self.assertIn("fila 2", mensaje)
        self.assertIn("imdb", mensaje)
        self.assertIn("duplicado", mensaje)

    def test_rechazo_de_year_no_entero_positivo(self):
        """year vacio, no numerico o <= 0 debe rechazarse con su fila."""
        filas = [fila("tt0000001", "Pelicula", "no-es-un-ano", "1000000", "2000000")]
        with self.assertRaises(analizar.DatosInvalidos) as cm:
            analizar.validar_filas(FIELDNAMES_CHICO, filas)
        self.assertIn("year", "\n".join(cm.exception.errores))

    def test_sin_registros_se_detiene(self):
        """Un CSV con solo cabecera (sin filas) tambien debe detenerse."""
        with self.assertRaises(analizar.DatosInvalidos):
            analizar.validar_filas(FIELDNAMES_CHICO, [])


class TestGeneracionDeInforme(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cwd_original = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.cwd_original)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _escribir_csv(self, filas):
        os.makedirs("datos", exist_ok=True)
        with open(analizar.ARCHIVO_ENTRADA, "w", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=FIELDNAMES_CHICO)
            escritor.writeheader()
            for fila_ in filas:
                escritor.writerow(fila_)

    def test_main_genera_informe_con_datos_validos(self):
        self._escribir_csv(FILAS_EJEMPLO)
        analizar.main()

        self.assertTrue(os.path.exists("public/index.html"))
        with open("public/index.html", encoding="utf-8") as f:
            contenido = f.read()

        self.assertIn("Fabio Mavric", contenido)
        self.assertIn("Copia educativa: contiene modificaciones simuladas", contenido)
        self.assertIn("CC BY 4.0", contenido)
        self.assertIn("local", contenido)  # GITHUB_SHA no esta seteado en el test
        # el titulo con entidad HTML debe quedar decodificado y re-escapado correctamente
        self.assertIn("Pelicula Tres &amp; Cia", contenido)
        self.assertNotIn("beneficio", contenido.lower())

    def test_main_no_escribe_informe_si_los_datos_son_invalidos(self):
        filas_invalidas = [fila("tt0000001", "Pelicula Uno", "2000", "1000000", "-100")]
        self._escribir_csv(filas_invalidas)

        with self.assertRaises(SystemExit) as cm:
            analizar.main()
        self.assertNotEqual(cm.exception.code, 0)
        self.assertFalse(os.path.exists("public/index.html"))

    def test_html_escapado_en_titulos(self):
        """Un titulo con caracteres especiales no debe romper el HTML ni
        quedar sin escapar."""
        filas = [fila("tt0000001", "5 <Test> & Cia", "2000", "1000000", "2000000")]
        self._escribir_csv(filas)
        analizar.main()
        with open("public/index.html", encoding="utf-8") as f:
            contenido = f.read()
        self.assertNotIn("<Test>", contenido)
        self.assertIn("&lt;Test&gt;", contenido)


if __name__ == "__main__":
    unittest.main()
