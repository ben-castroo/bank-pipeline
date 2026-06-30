"""Fase 5.1 — Benchmark local del ETL por etapa.

Mide extract, transform y (opcionalmente) load N veces sobre el CSV local.
Guarda media y desviación estándar en reports/perf_local.json.

Uso:
    python scripts/benchmark_etl.py [--runs N] [--csv PATH]

Por defecto usa ml/data/bank_clean_export.csv como fuente (ya procesado)
y mide solo extract + transform (no requiere DB).
Para incluir la carga a DB, definir SUPABASE_DB_URL en el entorno.
"""
import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

# Añadir el root al path para importar etl/
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "etl"))

from etl.process_data import read_source, validate_structure, clean_data  # noqa: E402


def bench_extract(csv_path: Path, runs: int) -> dict:
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        df = read_source(csv_path)
        try:
            validate_structure(df)
        except ValueError:
            pass  # clean CSV no tiene la columna 'default' del raw — normal
        times.append(time.perf_counter() - t0)
    return {
        "mean_s":   round(statistics.mean(times), 4),
        "std_s":    round(statistics.stdev(times) if len(times) > 1 else 0.0, 4),
        "min_s":    round(min(times), 4),
        "max_s":    round(max(times), 4),
        "runs":     runs,
    }


def bench_transform(csv_path: Path, runs: int) -> dict:
    df_raw = read_source(csv_path)
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        clean_data(df_raw.copy())
        times.append(time.perf_counter() - t0)
    return {
        "mean_s":   round(statistics.mean(times), 4),
        "std_s":    round(statistics.stdev(times) if len(times) > 1 else 0.0, 4),
        "min_s":    round(min(times), 4),
        "max_s":    round(max(times), 4),
        "runs":     runs,
    }


def bench_load_db(csv_path: Path, runs: int) -> dict | None:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("  [SKIP] SUPABASE_DB_URL no definida — load a DB omitido.")
        return None

    from sqlalchemy import create_engine
    from etl.process_data import load_clean_supabase

    df_raw = read_source(csv_path)
    clean_df, *_ = clean_data(df_raw.copy())
    eng = create_engine(db_url)
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        load_clean_supabase(clean_df, eng)
        times.append(time.perf_counter() - t0)
    return {
        "mean_s":   round(statistics.mean(times), 4),
        "std_s":    round(statistics.stdev(times) if len(times) > 1 else 0.0, 4),
        "min_s":    round(min(times), 4),
        "max_s":    round(max(times), 4),
        "runs":     runs,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark local del ETL")
    parser.add_argument("--runs", type=int, default=5, help="Número de repeticiones")
    # Preferir el CSV original (input del ETL); si no existe usar el clean como fallback
    _default_csv = REPO / "data" / "bank.csv"
    if not _default_csv.exists():
        _default_csv = REPO / "data" / "bank_dirty.csv"
    if not _default_csv.exists():
        _default_csv = REPO / "ml" / "data" / "bank_clean_export.csv"
    parser.add_argument(
        "--csv",
        type=Path,
        default=_default_csv,
        help="Ruta al CSV de entrada (formato raw con columna 'default')",
    )
    args = parser.parse_args()

    csv_path = args.csv
    if not csv_path.exists():
        sys.exit(f"ERROR: no se encuentra {csv_path}")

    runs = args.runs
    print(f"Benchmark ETL local — {runs} corridas sobre {csv_path.name}")
    print()

    print(f"[1/3] Extract (read CSV + validate) ...")
    ext = bench_extract(csv_path, runs)
    print(f"      mean={ext['mean_s']}s  std={ext['std_s']}s")

    print(f"[2/3] Transform (clean_data) ...")
    trn = bench_transform(csv_path, runs)
    print(f"      mean={trn['mean_s']}s  std={trn['std_s']}s")

    print(f"[3/3] Load to DB (SUPABASE_DB_URL) ...")
    ld = bench_load_db(csv_path, 3)
    if ld:
        print(f"      mean={ld['mean_s']}s  std={ld['std_s']}s")

    total_mean = round(ext["mean_s"] + trn["mean_s"] + (ld["mean_s"] if ld else 0.0), 4)
    total_std  = round(
        (ext["std_s"] ** 2 + trn["std_s"] ** 2 + (ld["std_s"] if ld else 0.0) ** 2) ** 0.5, 4
    )

    result = {
        "source": str(csv_path.name),
        "n_rows": len(read_source(csv_path)),
        "extract":   ext,
        "transform": trn,
        "load_db":   ld,
        "total": {"mean_s": total_mean, "std_s": total_std},
    }

    out = REPO / "reports" / "perf_local.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print(f"Total estimado: {total_mean}s ± {total_std}s")
    print(f"Guardado: {out}")


if __name__ == "__main__":
    main()
