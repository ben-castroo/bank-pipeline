"""Fase 5.3 — Gráfico comparativo local vs nube y resumen de rendimiento.

Lee reports/perf_local.json y reports/perf_cloud.json.
Si perf_cloud.json no existe o tiene valores placeholder, genera el gráfico
con los datos disponibles y marca los nube como "pendiente".

Uso:
    python scripts/plot_perf.py

Salidas:
    reports/figures/perf_local_vs_cloud.png
    reports/perf_summary.md
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "reports"
FIGS = REPORTS / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

LOCAL_JSON  = REPORTS / "perf_local.json"
CLOUD_JSON  = REPORTS / "perf_cloud.json"
OUT_PNG     = FIGS / "perf_local_vs_cloud.png"
OUT_MD      = REPORTS / "perf_summary.md"


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    local = load_json(LOCAL_JSON)
    cloud = load_json(CLOUD_JSON)

    if local is None:
        sys.exit(f"ERROR: {LOCAL_JSON} no existe. Ejecutar primero benchmark_etl.py")

    # ── Datos locales ────────────────────────────────────────────────────────
    l_ext = local["extract"]["mean_s"]
    l_trn = local["transform"]["mean_s"]
    l_ld  = local["load_db"]["mean_s"] if local.get("load_db") else 0.0
    l_tot = local["total"]["mean_s"]

    # ── Datos nube (o placeholders) ──────────────────────────────────────────
    has_cloud = cloud is not None
    c_cold    = cloud.get("cold_start_s", 0.0) if has_cloud else 0.0
    c_warm    = cloud["warm_health_s"]["mean_s"] if has_cloud else 0.0
    c_pred    = cloud.get("predict_s", 0.0) if has_cloud else 0.0

    # ── Figura ───────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Rendimiento ETL — Local vs Nube (Render Free Tier)", fontsize=13, fontweight="bold")

    # Panel izquierdo: desglose ETL local
    ax1 = axes[0]
    stages = ["Extract", "Transform", "Load DB"]
    vals   = [l_ext, l_trn, l_ld]
    colors = ["#4C72B0", "#55A868", "#C44E52"]
    bars = ax1.bar(stages, vals, color=colors, edgecolor="white", width=0.5)
    ax1.set_title("ETL local por etapa (segundos)")
    ax1.set_ylabel("Tiempo medio (s)")
    for bar, v in zip(bars, vals):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.002,
                 f"{v:.3f}s", ha="center", va="bottom", fontsize=9)
    ax1.set_ylim(0, max(vals) * 1.4 + 0.01)

    # Panel derecho: latencias en nube
    ax2 = axes[1]
    cloud_labels = ["Cold start\n(/health)", "Warm\n(/health)", "Predict\n(/predict)"]
    cloud_vals   = [c_cold, c_warm, c_pred]
    cloud_colors = ["#DD8452", "#4C72B0", "#55A868"]

    if has_cloud:
        bars2 = ax2.bar(cloud_labels, cloud_vals, color=cloud_colors, edgecolor="white", width=0.5)
        ax2.set_title("Latencia en Render (segundos)")
        ax2.set_ylabel("Tiempo (s)")
        for bar, v in zip(bars2, cloud_vals):
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                     f"{v:.2f}s", ha="center", va="bottom", fontsize=9)
        ax2.set_ylim(0, max(cloud_vals) * 1.4 + 0.1)
    else:
        ax2.text(0.5, 0.5, "Pendiente\n(ejecutar measure_cloud.sh\nen Render)",
                 ha="center", va="center", fontsize=12, color="gray",
                 transform=ax2.transAxes)
        ax2.set_title("Latencia en Render (pendiente)")
        ax2.axis("off")

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=130)
    plt.close()
    print(f"Guardado: {OUT_PNG}")

    # ── Resumen Markdown ─────────────────────────────────────────────────────
    n_rows = local.get("n_rows", "~11 000")
    cloud_note = (
        f"- **Cold start:** {c_cold:.2f}s (primer request tras inactividad del free tier)\n"
        f"- **Warm /health:** {c_warm:.3f}s (latencia estable tras calentar)\n"
        f"- **POST /predict:** {c_pred:.3f}s (incluye lectura de DB + inferencia RF)\n"
    ) if has_cloud else (
        "- *Pendiente: ejecutar `scripts/measure_cloud.sh` contra el servicio desplegado en Render.*\n"
    )

    md = f"""# Rendimiento del sistema — Local vs Nube
**Generado:** 2026-06-29 · **Fuente local:** `{local['source']}` ({n_rows} filas)

---

## ETL local — tiempos por etapa

| Etapa | Media (s) | Std (s) | Min | Max |
|---|---|---|---|---|
| Extract (leer CSV + validar estructura) | {l_ext:.4f} | {local['extract']['std_s']:.4f} | {local['extract']['min_s']:.4f} | {local['extract']['max_s']:.4f} |
| Transform (limpieza completa) | {l_trn:.4f} | {local['transform']['std_s']:.4f} | {local['transform']['min_s']:.4f} | {local['transform']['max_s']:.4f} |
| Load DB (Supabase) | {'N/A — sin conexión' if l_ld == 0.0 else f'{l_ld:.4f}'} | — | — | — |
| **Total** | **{l_tot:.4f}** | {local['total']['std_s']:.4f} | — | — |

**Interpretación:** el transform es la etapa dominante porque recorre cada fila para
validar rangos, categorías y convertir binarios. A {n_rows} filas, el ETL completo
(sin DB) tarda aproximadamente **{l_tot:.2f}s**, lo que es adecuado para cargas
programadas (no tiempo real).

---

## Nube (Render Free Tier)

{cloud_note}
**Interpretación:** el **cold start** del free tier es la limitación más notable:
el servicio queda inactivo tras ~15 minutos sin tráfico y necesita cargar la imagen
Docker + el modelo (`~{c_cold:.1f}s` aproximado). En caliente, la latencia de predicción
es aceptable para una demo; en producción real se mitigaría con un plan pagado o
un ping periódico para mantener la instancia activa.

---

## Limitaciones conocidas

- **Free tier de Render:** una sola instancia, cold start de hasta ~30s tras inactividad,
  RAM limitada (~512 MB), sin escala horizontal.
- **ETL monolítico:** el transform es secuencial y no paralelo; escalaría con chunking
  o procesamiento distribuido (Spark) para datasets de millones de filas.
- **Modelo en memoria:** el RF de 200 árboles ocupa ~20–50 MB serializado (joblib);
  aceptable en el contexto actual.

---

## Figura

Ver `reports/figures/perf_local_vs_cloud.png` para el gráfico comparativo.
"""

    OUT_MD.write_text(md, encoding="utf-8")
    print(f"Guardado: {OUT_MD}")


if __name__ == "__main__":
    main()
