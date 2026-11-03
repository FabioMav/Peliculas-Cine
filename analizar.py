"""
analizar.py
Lee datos/movies.csv (incluido en el repositorio, no se descarga nada), lo
valida y genera public/index.html con el informe.

Columnas obligatorias (del CSV de FiveThirtyEight / Bechdel): imdb, title,
year, budget, domgross. Las demas columnas del CSV (test, clean_test,
binary, intgross, code, budget_2013$, domgross_2013$, period code,
decade code) se conservan en el archivo pero no se usan en este informe.

Reglas de validacion, segun la consigna:
  - El encabezado debe tener las 5 columnas obligatorias.
  - Debe haber al menos un registro (fila de datos).
  - Cada fila debe tener el numero correcto de campos (ni de mas ni de menos).
  - imdb: no vacio y unico en todo el archivo.
  - title: no vacio.
  - year: entero positivo (no admite NA).
  - budget y domgross: admiten NA, "#N/A" o vacio como dato faltante (nunca
    se convierten en 0). Si estan presentes, deben ser numeros finitos no
    negativos.
      Nota: la consigna dice "admite NA o vacio"; el CSV real publicado por
      FiveThirtyEight usa literalmente "#N/A" para marcar estos mismos
      vacios (se puede comprobar con la fila de budget/domgross faltante
      mas cercana), asi que este programa trata NA, "#N/A" y la cadena
      vacia como la misma marca de dato faltante.
  - budget: ademas, si esta presente, no puede superar BUDGET_MAXIMO (un
    tope realista para atrapar errores de tipeo, p. ej. un cero de mas).
    domgross no tiene este tope.
  - budget: ademas, si esta presente, debe ser SOLO digitos (y como mucho
    un punto decimal): nada de comas de miles, simbolos de moneda, signo
    "+" ni notacion cientifica (1e7). Comas/espacios/"$"/letras ya
    quedaban afuera porque float() los rechaza; esto cierra el hueco de
    "+500" y "1e7", que float() si acepta. domgross no tiene esta regla.
  - domgross = ingresos de taquilla en Estados Unidos, en dolares nominales
    del ano de estreno. No se suma con intgross ni con columnas ajustadas
    por inflacion (budget_2013$, domgross_2013$, intgross_2013$): esas
    columnas se ignoran a proposito.
  - No se calcula "beneficio" (domgross - budget): no tiene el respaldo
    metodologico necesario y la consigna pide explicitamente no llamarlo asi.
  - Si hay cualquier dato invalido, el programa junta TODOS los errores
    encontrados (cada uno con su fila y columna), los imprime y termina con
    codigo de salida distinto de cero sin escribir un informe nuevo.
"""
import csv
import html
import os
import re
import sys
from datetime import datetime, timezone

ARCHIVO_ENTRADA = "datos/movies.csv"
DIRECTORIO_SALIDA = "public"
ARCHIVO_SALIDA = f"{DIRECTORIO_SALIDA}/index.html"

NOMBRE_ESTUDIANTE = "Fabio Mavric"
URL_FUENTE = "https://github.com/fivethirtyeight/data/tree/master/bechdel"
URL_CSV_ORIGINAL = "https://raw.githubusercontent.com/fivethirtyeight/data/master/bechdel/movies.csv"
URL_LICENCIA = "https://creativecommons.org/licenses/by/4.0/"

COLUMNAS_OBLIGATORIAS = ["imdb", "title", "year", "budget", "domgross"]
MARCAS_FALTANTE = {"", "NA", "#N/A"}

# Validacion extra: budget no puede superar un tope realista. El budget
# real mas alto del CSV original es ~425 millones de USD (una pelicula de
# gran presupuesto); 2,000 millones de USD da un margen amplio sin bloquear
# ninguna pelicula real, pero atrapa errores de tipeo como un cero de mas
# (p. ej. 20,000,000,000 en vez de 2,000,000,000).
BUDGET_MAXIMO = 2_000_000_000

# Validacion extra: budget debe ser SOLO digitos (y, como mucho, un punto
# decimal) - nada de comas de miles, simbolos de moneda, espacios, signo
# "+", notacion cientifica (1e7) ni ningun otro caracter. Las comas,
# espacios, "$" y letras ya quedaban afuera porque float() los rechaza; lo
# que este patron cierra es la notacion cientifica y el signo "+", que
# float() si acepta sin problema (float("1e7") y float("+500") funcionan).
PATRON_BUDGET_SOLO_DIGITOS = re.compile(r"\d+(\.\d+)?")


class DatosInvalidos(Exception):
    """Junta uno o mas errores de validacion (cada uno con fila y columna)."""

    def __init__(self, errores):
        self.errores = list(errores)
        super().__init__("\n".join(self.errores))


def leer_filas(ruta_csv):
    """Devuelve (fieldnames, filas_crudas) leyendo el CSV con DictReader.

    No valida contenido todavia; solo deja ver la cabecera y las filas tal
    cual estan en el archivo (incluyendo filas con numero de campos
    incorrecto, que DictReader marca con None o con la clave de sobra)."""
    try:
        with open(ruta_csv, newline="", encoding="utf-8") as f:
            lector = csv.DictReader(f, restkey="__campos_de_mas__")
            fieldnames = lector.fieldnames or []
            filas = list(lector)
    except FileNotFoundError as exc:
        raise DatosInvalidos(
            [f"No se encontro {ruta_csv}. Debe estar en el repositorio (no se descarga)."]
        ) from exc
    return fieldnames, filas


def validar_estructura(fieldnames):
    """Valida la cabecera: deben estar las 5 columnas obligatorias."""
    faltantes = [c for c in COLUMNAS_OBLIGATORIAS if c not in fieldnames]
    if faltantes:
        raise DatosInvalidos(
            [f"cabecera, columna '{c}': falta la columna obligatoria" for c in faltantes]
        )


def _valor_numerico_opcional(valor, columna, numero_fila, errores, maximo=None, solo_digitos=False):
    """Para budget/domgross: NA/#N/A/vacio -> None (faltante, nunca 0).
    Si hay valor, debe ser un numero finito no negativo; si no, se agrega
    un error con fila y columna y se devuelve None para esa fila.
    Si se pasa 'maximo', un valor por encima de ese tope tambien se
    rechaza (se usa para budget, ver BUDGET_MAXIMO).
    Si se pasa 'solo_digitos=True', el texto debe ser SOLO digitos (y como
    mucho un punto decimal): rechaza comas, simbolos, signo "+" y notacion
    cientifica aunque float() los aceptaria (se usa para budget)."""
    texto = "" if valor is None else str(valor).strip()
    if texto in MARCAS_FALTANTE:
        return None
    if solo_digitos and not PATRON_BUDGET_SOLO_DIGITOS.fullmatch(texto):
        errores.append(
            f"fila {numero_fila}, columna '{columna}': formato invalido, debe "
            f"contener solo digitos (y opcionalmente un punto decimal), sin "
            f"comas, simbolos ni letras (se encontro {texto!r})"
        )
        return None
    try:
        numero = float(texto)
    except ValueError:
        errores.append(
            f"fila {numero_fila}, columna '{columna}': valor no numerico ({texto!r})"
        )
        return None
    import math

    if not math.isfinite(numero) or numero < 0:
        errores.append(
            f"fila {numero_fila}, columna '{columna}': debe ser un numero finito no "
            f"negativo (se encontro {texto!r})"
        )
        return None
    if maximo is not None and numero > maximo:
        errores.append(
            f"fila {numero_fila}, columna '{columna}': supera el tope realista "
            f"de {maximo:,.0f} (se encontro {texto!r})"
        )
        return None
    return numero


def validar_filas(fieldnames, filas):
    """Valida cada fila y devuelve la lista de peliculas validas (dicts con
    imdb, title, year, budget, domgross ya tipados). Si encuentra cualquier
    error junta TODOS los que pueda (no se detiene en el primero) y al
    final lanza DatosInvalidos con la lista completa."""
    errores = []
    peliculas = []
    vistos = {}  # imdb -> primera fila donde aparecio

    if not filas:
        raise DatosInvalidos(["no hay ningun registro de datos (el CSV solo tiene cabecera)"])

    n_columnas_esperadas = len(fieldnames)

    for indice, fila in enumerate(filas):
        numero_fila = indice + 2  # fila 1 es la cabecera

        # numero correcto de campos
        if "__campos_de_mas__" in fila:
            errores.append(
                f"fila {numero_fila}, estructura: tiene mas campos de los "
                f"{n_columnas_esperadas} esperados segun la cabecera"
            )
            continue
        if any(fila.get(c) is None for c in fieldnames):
            errores.append(
                f"fila {numero_fila}, estructura: tiene menos campos de los "
                f"{n_columnas_esperadas} esperados segun la cabecera"
            )
            continue

        imdb = (fila.get("imdb") or "").strip()
        title_crudo = (fila.get("title") or "").strip()
        year_texto = (fila.get("year") or "").strip()

        if not imdb:
            errores.append(f"fila {numero_fila}, columna 'imdb': identificador vacio")
        elif imdb in vistos:
            errores.append(
                f"fila {numero_fila}, columna 'imdb': identificador duplicado "
                f"{imdb!r} (ya aparece en la fila {vistos[imdb]})"
            )
        else:
            vistos[imdb] = numero_fila

        if not title_crudo:
            errores.append(f"fila {numero_fila}, columna 'title': titulo vacio")

        year = None
        if not year_texto:
            errores.append(f"fila {numero_fila}, columna 'year': ano vacio")
        else:
            try:
                year = int(year_texto)
                if year <= 0:
                    errores.append(
                        f"fila {numero_fila}, columna 'year': debe ser un entero "
                        f"positivo (se encontro {year_texto!r})"
                    )
                    year = None
            except ValueError:
                errores.append(
                    f"fila {numero_fila}, columna 'year': no es un entero valido "
                    f"(se encontro {year_texto!r})"
                )

        budget = _valor_numerico_opcional(
            fila.get("budget"), "budget", numero_fila, errores,
            maximo=BUDGET_MAXIMO, solo_digitos=True,
        )
        domgross = _valor_numerico_opcional(fila.get("domgross"), "domgross", numero_fila, errores)

        # Solo construimos la pelicula si imdb/title/year son utilizables;
        # si alguno fallo, la fila ya quedo registrada en errores y mas
        # abajo se detiene todo el programa de cualquier forma.
        if imdb and title_crudo and year is not None:
            peliculas.append({
                "imdb": imdb,
                "title": html.unescape(title_crudo),
                "year": year,
                "budget": budget,
                "domgross": domgross,
                "orden_original": indice,
            })

    if errores:
        raise DatosInvalidos(errores)

    return peliculas


def calcular(peliculas):
    """Separado de la validacion: solo calcula, sobre datos ya validos."""
    total = len(peliculas)

    con_domgross = [p for p in peliculas if p["domgross"] is not None]
    con_budget = [p for p in peliculas if p["budget"] is not None]

    suma_domgross = sum(p["domgross"] for p in con_domgross)
    media_budget = (sum(p["budget"] for p in con_budget) / len(con_budget)) if con_budget else None
    faltantes_domgross = total - len(con_domgross)

    top10_domgross = sorted(con_domgross, key=lambda p: p["domgross"], reverse=True)[:10]
    primeras10_original = sorted(peliculas, key=lambda p: p["orden_original"])[:10]

    return {
        "total": total,
        "suma_domgross": suma_domgross,
        "media_budget": media_budget,
        "faltantes_domgross": faltantes_domgross,
        "top10_domgross": top10_domgross,
        "primeras10_original": primeras10_original,
    }


def construir_svg_barras(top10):
    """Barras con las 10 peliculas de mayor domgross (SVG inline, sin
    dependencias externas)."""
    if not top10:
        return "<p>No hay suficientes datos de domgross para el grafico.</p>"
    maximo = max(p["domgross"] for p in top10)
    ancho_barra = 68
    espacio = 20
    alto_grafico = 220
    margen_inferior = 70
    ancho_svg = len(top10) * (ancho_barra + espacio) + espacio
    alto_svg = alto_grafico + margen_inferior

    def abreviar(valor):
        if valor >= 1_000_000_000:
            return f"${valor / 1_000_000_000:.2f}B"
        if valor >= 1_000_000:
            return f"${valor / 1_000_000:.1f}M"
        if valor >= 1_000:
            return f"${valor / 1_000:.0f}K"
        return f"${valor:.0f}"

    barras = []
    for i, p in enumerate(top10):
        alto_barra = (p["domgross"] / maximo) * (alto_grafico - 24) if maximo else 0
        x = espacio + i * (ancho_barra + espacio)
        y = alto_grafico - alto_barra
        etiqueta_valor = abreviar(p["domgross"])
        titulo_corto = p["title"] if len(p["title"]) <= 13 else p["title"][:12] + "…"
        barras.append(
            f'<rect x="{x}" y="{y:.1f}" width="{ancho_barra}" height="{alto_barra:.1f}" '
            f'fill="#2a78d6" rx="3"><title>{html.escape(p["title"])}: ${p["domgross"]:,.0f}</title></rect>'
            f'<text x="{x + ancho_barra / 2}" y="{y - 6:.1f}" font-size="11" '
            f'text-anchor="middle" fill="#0b0b0b">{html.escape(etiqueta_valor)}</text>'
            f'<text x="{x + ancho_barra / 2}" y="{alto_grafico + 16}" font-size="10" '
            f'text-anchor="middle" fill="#52514e">{html.escape(titulo_corto)}</text>'
            f'<text x="{x + ancho_barra / 2}" y="{alto_grafico + 30}" font-size="10" '
            f'text-anchor="middle" fill="#52514e">{p["year"]}</text>'
        )
    return (
        f'<svg viewBox="0 0 {ancho_svg} {alto_svg}" width="100%" '
        f'style="max-width:{ancho_svg}px; height:auto;" role="img" '
        f'aria-label="Diez peliculas con mayor domgross">' + "".join(barras) + "</svg>"
    )


def generar_html(peliculas, stats, hora_generacion_utc, commit_sha):
    total = stats["total"]
    suma_domgross = stats["suma_domgross"]
    media_budget = stats["media_budget"]
    faltantes_domgross = stats["faltantes_domgross"]
    top10 = stats["top10_domgross"]
    primeras10 = stats["primeras10_original"]

    svg_grafico = construir_svg_barras(top10)

    def celda_numero(valor):
        return f"${valor:,.0f}" if valor is not None else "NA"

    filas_tabla = "\n".join(
        f"<tr><td>{html.escape(p['imdb'])}</td><td>{html.escape(p['title'])}</td>"
        f"<td>{p['year']}</td><td>{celda_numero(p['budget'])}</td>"
        f"<td>{celda_numero(p['domgross'])}</td></tr>"
        for p in primeras10
    )

    media_budget_texto = f"${media_budget:,.2f}" if media_budget is not None else "NA"

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe de peliculas (Bechdel / FiveThirtyEight)</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem;
          line-height: 1.5; color: #0b0b0b; background: #fcfcfb; }}
  @media (prefers-color-scheme: dark) {{
    body {{ color: #f0efec; background: #1a1a19; }}
    td, th {{ border-color: #3a3a38 !important; }}
    .aviso {{ background: rgba(230,160,40,0.14) !important; }}
  }}
  h1 {{ margin-bottom: 0.2rem; }}
  .subtitulo {{ color: #52514e; margin-top: 0; }}
  .aviso {{ background: rgba(230,160,40,0.12); border-left: 4px solid #d98c1a; border-radius: 6px;
            padding: 0.8rem 1rem; margin: 1rem 0; font-size: 0.92rem; }}
  .indicadores {{ display: flex; gap: 1.5rem; flex-wrap: wrap; margin: 1.5rem 0; }}
  .indicador {{ background: rgba(42,120,214,0.08); border-radius: 10px; padding: 0.8rem 1.2rem; min-width: 190px; }}
  .indicador .valor {{ font-size: 1.5rem; font-weight: 700; }}
  .indicador .etiqueta {{ font-size: 0.85rem; color: #52514e; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #d8d6d0; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; }}
  th {{ background: rgba(42,120,214,0.08); }}
  footer {{ margin-top: 2rem; font-size: 0.85rem; color: #52514e; }}
  a {{ color: #2a78d6; }}
  code {{ font-size: 0.85em; }}
</style>
</head>
<body>
  <h1>Informe de peliculas (conjunto Bechdel, FiveThirtyEight)</h1>
  <p class="subtitulo">{html.escape(NOMBRE_ESTUDIANTE)} &middot;
    Fuente y atribucion: <a href="{URL_FUENTE}">FiveThirtyEight &ndash; Bechdel Test</a>
    (CSV original: <a href="{URL_CSV_ORIGINAL}">movies.csv</a>) &middot;
    Licencia de los datos: <a href="{URL_LICENCIA}">CC BY 4.0</a></p>

  <p class="aviso"><strong>Copia educativa: contiene modificaciones simuladas.</strong>
    Son datos historicos de taquilla, no cifras actuales ni un catalogo completo del cine.
    Los cambios realizados en esta practica son simulaciones para demostrar un flujo de
    CI/CD; no representan correcciones de la investigacion original de FiveThirtyEight.</p>

  <p>Generado: <strong>{hora_generacion_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC</strong><br>
     Commit: <code>{html.escape(commit_sha)}</code></p>

  <div class="indicadores">
    <div class="indicador"><div class="valor">{total}</div><div class="etiqueta">Peliculas totales</div></div>
    <div class="indicador"><div class="valor">${suma_domgross:,.0f}</div>
      <div class="etiqueta">Suma de domgross disponible (USD nominales de esta muestra historica, sin ajustar por inflacion)</div></div>
    <div class="indicador"><div class="valor">{media_budget_texto}</div><div class="etiqueta">Media del presupuesto disponible</div></div>
    <div class="indicador"><div class="valor">{faltantes_domgross}</div><div class="etiqueta">Peliculas sin dato de domgross (NA)</div></div>
  </div>

  <h2>Diez peliculas con mayor domgross</h2>
  {svg_grafico}

  <h2>Primeras diez filas (orden original del CSV)</h2>
  <p>Se muestran en el orden del archivo, no por domgross, para poder verificar un cambio
    aunque la pelicula modificada no entre en el grafico de arriba.</p>
  <table>
    <thead><tr><th>imdb</th><th>title</th><th>year</th><th>budget</th><th>domgross</th></tr></thead>
    <tbody>
    {filas_tabla}
    </tbody>
  </table>

  <footer>
    <p>domgross: ingresos de taquilla en Estados Unidos, en dolares nominales del ano de
      estreno de cada pelicula. No se suma con intgross ni con columnas ajustadas por
      inflacion (budget_2013$, domgross_2013$, intgross_2013$).</p>
    <p>Datos: <a href="{URL_FUENTE}">FiveThirtyEight &ndash; Bechdel Test</a>,
      licencia <a href="{URL_LICENCIA}">CC BY 4.0</a>.
      Generado automaticamente por GitHub Actions a partir de datos/movies.csv del repositorio.</p>
  </footer>
</body>
</html>
"""


def main():
    try:
        fieldnames, filas = leer_filas(ARCHIVO_ENTRADA)
        validar_estructura(fieldnames)
        peliculas = validar_filas(fieldnames, filas)
    except DatosInvalidos as exc:
        print("ERROR: se encontraron datos invalidos en "
              f"{ARCHIVO_ENTRADA}; no se genera un informe nuevo.", file=sys.stderr)
        for mensaje in exc.errores:
            print(f"  - {mensaje}", file=sys.stderr)
        sys.exit(1)

    stats = calcular(peliculas)
    os.makedirs(DIRECTORIO_SALIDA, exist_ok=True)

    hora_generacion_utc = datetime.now(timezone.utc)
    commit_sha = os.environ.get("GITHUB_SHA") or "local"
    contenido = generar_html(peliculas, stats, hora_generacion_utc, commit_sha)
    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
        f.write(contenido)

    print(f"OK: {ARCHIVO_SALIDA} generado con {stats['total']} peliculas validas.")


if __name__ == "__main__":
    main()
