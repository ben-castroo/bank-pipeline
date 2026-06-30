# TAREA (agente) — Servir el notebook como HTML en `/bi/notebook`

**Repo:** `bank-pipeline` · **Rama:** `feat/form-prediccion`.
**Objetivo:** mostrar el análisis completo (`ml/analisis_eda_modelo.ipynb`) como una página
web en la **misma URL del servicio**, sin abrir Jupyter. Se convierte el notebook a **HTML
autocontenido** (con figuras embebidas), se sirve en `/bi/notebook` y se enlaza desde el
dashboard.

## Enfoque (y por qué)

- `nbconvert --to html` **NO ejecuta** el notebook: solo renderiza los outputs ya guardados.
  → no necesita datos, ni sklearn, ni credenciales; es seguro y rápido.
- El HTML se **genera localmente y se commitea** (no se agrega Jupyter a la imagen de
  producción). El servidor solo sirve un archivo estático.
- Se monta en la app de BI que ya existe (`bi_api`), accesible en `/bi/notebook`.

## Guardrails

1. **No agregar `jupyter`/`nbconvert` a `requirements.txt` ni al Dockerfile.** La conversión
   es un paso local; al repo va el HTML resultante.
2. Antes de convertir, el notebook debe tener sus **outputs guardados** (correr
   "Restart & Run All"); si no, el HTML saldría sin figuras.
3. **Revisar que ninguna celda tenga secretos** antes de commitear el HTML (ya se verificó
   que lee de CSV, sin credenciales; confirmarlo de nuevo porque el HTML expone todo el código).
4. La página es **pública** (es análisis, sin PII). No tocar el ETL ni el modelo.
5. La ruta debe responder con un 404 amable si el HTML aún no se generó.

## Archivos a crear / editar

```
scripts/build_notebook_html.py     ← NUEVO: genera el HTML
bi_api/static/notebook.html        ← NUEVO (generado y commiteado)
bi_api/app.py                      ← EDITAR: ruta /notebook
etl/templates/dashboard.html       ← EDITAR: botón "Ver análisis (notebook)"
```

---

## Tarea 1 — Script de build
```python
# scripts/build_notebook_html.py
"""Convierte el notebook canónico a HTML autocontenido para servirlo en /bi/notebook.
Uso:  pip install nbconvert  &&  python scripts/build_notebook_html.py
No ejecuta el notebook: solo renderiza los outputs ya guardados.
"""
import pathlib, subprocess, sys

NB = "ml/analisis_eda_modelo.ipynb"
OUT_DIR = pathlib.Path("bi_api/static")
OUT_DIR.mkdir(parents=True, exist_ok=True)

subprocess.run(
    [sys.executable, "-m", "nbconvert", "--to", "html", "--embed-images",
     NB, "--output", "notebook", "--output-dir", str(OUT_DIR)],
    check=True,
)
print("Generado:", OUT_DIR / "notebook.html")
```
**Aceptación:** `pip install nbconvert && python scripts/build_notebook_html.py` deja
`bi_api/static/notebook.html` con código, texto y **figuras embebidas**.

## Tarea 2 — Ruta en `bi_api/app.py`
```python
import os
from flask import send_file

NOTEBOOK_HTML = os.path.join(os.path.dirname(__file__), "static", "notebook.html")

@app.get("/notebook")
def notebook():
    if not os.path.exists(NOTEBOOK_HTML):
        return ("<p>El HTML del notebook no está generado todavía. "
                "Corre <code>python scripts/build_notebook_html.py</code>.</p>", 404)
    return send_file(NOTEBOOK_HTML)
```
(Montado en `/bi` → queda accesible en **`/bi/notebook`**.)
**Aceptación:** `GET /bi/notebook` devuelve el HTML del análisis; si falta el archivo,
devuelve el 404 con instrucciones.

## Tarea 3 — Enlace desde el dashboard
En `etl/templates/dashboard.html`, agregar (cerca del encabezado/nav, con el estilo
existente) un enlace que abra el análisis en otra pestaña:
```html
<a href="/bi/notebook" target="_blank" rel="noopener"
   class="px-3 py-1 rounded-full bg-slate-200 hover:bg-slate-300 text-sm">
  Ver análisis (notebook)
</a>
```
(Opcional: agregar el mismo enlace en `bi_api/templates/bi.html`.)
**Aceptación:** desde el dashboard hay un botón visible que abre `/bi/notebook` en pestaña nueva.

---

## Criterio de aceptación GLOBAL

- `https://TU-APP.onrender.com/bi/notebook` muestra el notebook (EDA + modelo + métricas)
  con sus figuras, en la misma URL del servicio.
- El HTML está **commiteado** (`bi_api/static/notebook.html`); el servidor no ejecuta nada.
- `requirements.txt` y el Dockerfile **no** incluyen Jupyter.
- El dashboard principal tiene el enlace "Ver análisis (notebook)".
- Si el HTML no existe, `/bi/notebook` responde 404 con la instrucción para generarlo.

## Cómo probar

1. `pip install nbconvert` (solo local).
2. Abrir el notebook y "Restart & Run All" para asegurar outputs guardados.
3. `python scripts/build_notebook_html.py` → confirmar `bi_api/static/notebook.html`.
4. `python wsgi.py` → abrir `http://localhost:8000/bi/notebook` y el botón en `/`.
5. Commitear el HTML; en Render (rama desplegada) abrir `.../bi/notebook`.

## Mantenimiento

Cada vez que cambie el notebook: re-correr el build y commitear el HTML actualizado.
(Alternativa al repo: como el repo es público, también puedes linkear directo al `.ipynb`
en GitHub, que lo renderiza nativamente; pero servirlo desde la app deja todo en una URL.)

## Qué desbloquea

- Anexo del informe (apartado k) accesible online y material de demo: muestras el análisis
  completo sin abrir Jupyter, en la misma URL del proyecto.
