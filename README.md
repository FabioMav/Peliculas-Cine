# cine-cicd

Informe automatizado sobre peliculas (conjunto **Bechdel** de FiveThirtyEight),
con validacion y publicacion continua usando **GitHub Actions** y **GitHub Pages**.

Practica de CI/CD — Fabio Mavric (UNIVALLE Cochabamba, Ingenieria en Ciencia
de Datos e Inteligencia de Negocios).

## Que hace este proyecto

`analizar.py` lee `datos/movies.csv` (ya incluido en el repositorio: **no se
descarga nada** en ningun momento) y genera `public/index.html`, un informe
con: total de peliculas, suma de `domgross` disponible, media de `budget`
disponible, conteo de ingresos faltantes, un grafico de barras con las diez
peliculas de mayor `domgross` y una tabla con las primeras diez filas en el
orden original del CSV.

Cada `push` a `main` dispara el workflow `.github/workflows/cine.yml`:

- **`verificar` (CI):** instala Python 3.12, corre `python -m unittest
  discover -v`, valida `datos/movies.csv` y genera el sitio con `python
  analizar.py`. Si el CSV tiene algun dato invalido, `analizar.py` termina
  con codigo de salida distinto de cero **y no genera un informe nuevo** —
  el job falla y no se sube nada a Pages.
- **`publicar` (CD):** solo corre si `verificar` termino bien (`needs:
  verificar`), y publica `public/` en GitHub Pages.

No hay descarga automatica ni ejecucion programada (`schedule`): cada
publicacion usa exactamente el CSV que viaja en ese commit.

## Datos y licencia

- Datos: conjunto Bechdel de FiveThirtyEight —
  https://github.com/fivethirtyeight/data/tree/master/bechdel
- CSV original: https://raw.githubusercontent.com/fivethirtyeight/data/master/bechdel/movies.csv
- Licencia de los datos: **CC BY 4.0** — https://creativecommons.org/licenses/by/4.0/
- Son datos **historicos** de taquilla (no cifras actuales ni un catalogo
  completo del cine).

**Copia educativa: contiene modificaciones simuladas.** Los cambios hechos
en esta practica (pasos 7 y 8) son simulaciones para demostrar un flujo de
CI/CD; no representan correcciones de la investigacion original de
FiveThirtyEight. Este aviso tambien aparece en la pagina generada.

## Estructura del proyecto

```
datos/movies.csv              # CSV fuente, SI va al repositorio (no esta en .gitignore)
analizar.py                   # validacion + calculo + generacion de public/index.html
test_analizar.py              # pruebas unittest, con datos propios (no el CSV real)
.github/workflows/cine.yml    # workflow de CI (verificar) y CD (publicar)
.gitignore                    # public/, __pycache__/, .venv/
public/index.html             # se genera al ejecutar analizar.py (no se versiona)
```

## Columnas obligatorias y validacion

De `datos/movies.csv` se usan: `imdb`, `title`, `year`, `budget`, `domgross`.
Las demas columnas (`test`, `clean_test`, `binary`, `intgross`, `code`,
`budget_2013$`, `domgross_2013$`, `intgross_2013$`, `period code`, `decade
code`) se conservan en el archivo pero no se usan en el informe.

Reglas:

- La cabecera debe tener las 5 columnas obligatorias, y debe haber al menos
  una fila de datos.
- Cada fila debe tener el numero correcto de campos.
- `imdb`: no vacio y unico.
- `title`: no vacio.
- `year`: entero positivo.
- `budget` y `domgross`: admiten `NA`, vacio o `#N/A` como dato faltante
  (**nunca se convierten en 0**). El CSV real de FiveThirtyEight usa
  literalmente `#N/A` para estos faltantes — se puede comprobar por
  ejemplo en la fila de *The Frozen Ground* (`tt2005374`), que no tiene
  `domgross` (hay 17 peliculas asi en el archivo original). Si el valor
  esta presente, debe ser un numero finito no negativo.
- `budget`, ademas, no puede superar **2,000 millones de USD** (el
  presupuesto real mas alto del CSV original es ~425 millones; el tope da
  margen amplio pero atrapa errores de tipeo, como un cero de mas).
  `domgross` no tiene este tope.
- `budget`, ademas, debe ser **solo digitos** (y como mucho un punto
  decimal): nada de comas de miles, simbolos de moneda, texto, espacios,
  signo `+` ni notacion cientifica (`1e7`). Comas, espacios, `$` y letras
  ya quedaban afuera de por si (no son numeros validos), pero esta regla
  cierra casos como `+13000000` o `1.3e7`, que son numeros validos para
  Python pero no "solo digitos". `domgross` no tiene esta regla.
- `domgross` son ingresos de taquilla en Estados Unidos, en dolares
  nominales del ano de estreno. No se suma con `intgross` ni se mezcla con
  columnas ajustadas por inflacion. El informe tampoco calcula "beneficio"
  (`domgross - budget`).

Si hay cualquier dato invalido, `analizar.py` junta **todos** los errores
encontrados (cada uno con su fila y su columna), los imprime por `stderr` y
termina con `sys.exit(1)` sin escribir `public/index.html`.

## Valores de referencia (CSV original, sin editar)

Con el `datos/movies.csv` tal como viene del repositorio de FiveThirtyEight:

- Total de peliculas: **1794**
- Primera fila (`tt1711425`, *21 & Over*): `domgross` = **25682380**
- Suma total de `domgross` disponible: **122,847,649,792**
- Peliculas sin `domgross` (`#N/A`): **17**

Vas a usar estos numeros en el paso 4 y para comparar despues de editar el
CSV en el paso 7.

## Como correrlo en tu computadora

Terminal de VS Code, en la raiz del proyecto:

```bash
python -m unittest discover -v
python analizar.py
```

(Si tu sistema usa otro comando, cambia `python` por `python3` o `py`.)

Despues abre `public/index.html` en el navegador y revisa que el total
inicial sea **1794 peliculas**.

## Pasos para publicarlo (resumen de la practica)

1. Crea en GitHub un repositorio **publico** llamado `cine-cicd`, con README
   y rama `main`. Clonalo con GitHub Desktop y abrelo en VS Code.
2. Copia estos archivos dentro del repositorio clonado (reemplazando el
   README por defecto si hace falta) — este zip ya trae exactamente la
   estructura que pide la consigna, con `datos/movies.csv` ya descargado y
   verificado (es CSV real, no una pagina HTML).
3. En GitHub → **Settings → Pages → Build and deployment → Source →
   GitHub Actions**.
4. En GitHub Desktop: deberian aparecer como cambios `datos/movies.csv`,
   `analizar.py`, `test_analizar.py`, `.gitignore`, `README.md` y
   `.github/workflows/cine.yml`. Commit **"Primera version del informe"**
   y Push origin.
5. En GitHub → **Actions**, abre "Cine - CI y CD" y espera que `verificar`
   y `publicar` terminen en verde. En Settings → Pages, abre "Visit site"
   (normalmente `https://TU-USUARIO.github.io/cine-cicd/`).

### Paso 7 — actualizacion valida

Edita en `datos/movies.csv` la fila de `tt1711425` (*21 & Over*): suma
**1000000** a su `domgross` (sin simbolos de moneda ni separadores de
miles; valor original **25682380** → nuevo **26682380**). No toques
`budget`, otras columnas, la cabecera ni la cantidad de campos.

```bash
python -m unittest discover -v
python analizar.py
```

La tabla debe mostrar el nuevo ingreso y la suma total de `domgross` debe
subir exactamente en USD 1,000,000 (confirmado localmente: de
122,847,649,792 a 122,848,649,792). El total de peliculas y la media del
presupuesto no cambian.

Commit **"Simular aumento de taquilla de USD 1000000"** y Push origin.
Espera que ambos jobs terminen en verde y confirma en GitHub Pages el
nuevo ingreso, el aumento exacto y el identificador del commit.

- Ejecucion del cambio valido: `<pega aqui el link a esa ejecucion de Actions>`

### Paso 8 — dato invalido bloquea CD

Cambia temporalmente ese mismo `domgross` a **-100**. En local, `python
analizar.py` debe fallar (confirmado: termina con codigo de salida 1 y el
mensaje indica `fila 2, columna 'domgross'`, sin generar un informe
nuevo). Aun asi, haz commit **"Prueba controlada: taquilla invalida"** y
Push origin para demostrar el control remoto.

En Actions, `verificar` debe fallar al validar el CSV y `publicar` debe
quedar omitido. GitHub Pages conserva el informe valido del paso anterior.

- Ejecucion del dato invalido: `<pega aqui el link a esa ejecucion de Actions>`

Restaura `domgross` al valor valido del paso 7 (**26682380**), vuelve a
correr los comandos localmente, y haz commit **"Corregir taquilla
invalida"** y Push origin. Confirma que ambos jobs vuelvan a estar en
verde.

- Ejecucion de la correccion: `<pega aqui el link a esa ejecucion de Actions>`

## Enlaces de entrega

- Sitio en GitHub Pages: `<pega aqui la URL de Pages>`
- Repositorio publico: `<pega aqui la URL del repositorio>`

## Si el cambio no aparece

- Comprueba primero que el nuevo valor este en `datos/movies.csv` dentro
  de GitHub, en `main` (que no haya quedado sin `commit` o sin `push`).
- Revisa la ejecucion de Actions asociada al ultimo commit: `publicar`
  tambien debe haber terminado bien. Abre la URL del despliegue y recarga
  sin cache.
- No edites `public/index.html` directamente: Actions lo vuelve a generar
  en cada ejecucion. No descargues otra copia del CSV: el proyecto siempre
  lee `datos/movies.csv` del repositorio.
