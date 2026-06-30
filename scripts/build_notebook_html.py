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
