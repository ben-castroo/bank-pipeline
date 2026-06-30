"""Fase 3.1 — Carga reports/model_metrics.json a tres tablas de Supabase.

Uso:
    python ml/load_metrics_to_db.py

Requiere variable de entorno SUPABASE_DB_URL (cadena postgres).
"""
import json
import os
import datetime as dt
from pathlib import Path
from sqlalchemy import create_engine, text

METRICS_PATH = Path("reports/model_metrics.json")


def load_metrics(db_url: str) -> str:
    m = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    run_id = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    eng = create_engine(db_url)

    with eng.begin() as cx:
        cx.execute(text("""
            CREATE TABLE IF NOT EXISTS model_metrics (
                run_id           text PRIMARY KEY,
                created_at       timestamptz DEFAULT now(),
                model_name       text,
                duration_excluded bool,
                accuracy         numeric,
                precision        numeric,
                recall           numeric,
                f1               numeric,
                roc_auc          numeric,
                gini             numeric,
                n_train          int,
                n_test           int,
                si_pct           numeric
            )
        """))

        cx.execute(text("""
            CREATE TABLE IF NOT EXISTS model_confusion (
                run_id    text,
                actual    text,
                predicted text,
                n         int
            )
        """))

        cx.execute(text("""
            CREATE TABLE IF NOT EXISTS model_comparison (
                run_id     text,
                model_name text,
                f1         numeric,
                roc_auc    numeric
            )
        """))

        me = m["metrics"]
        cm = m["confusion_matrix"]

        cx.execute(text("""
            INSERT INTO model_metrics
                VALUES (:r, now(), :mn, :de, :acc, :pre, :rec, :f1, :auc, :gini, :ntr, :nte, :sp)
            ON CONFLICT (run_id) DO NOTHING
        """), dict(
            r=run_id,
            mn=m["model"]["name"],
            de=m["model"]["duration_excluded"],
            acc=me["accuracy"], pre=me["precision"], rec=me["recall"],
            f1=me["f1"], auc=me["roc_auc"], gini=me["gini"],
            ntr=m["split"]["n_train"], nte=m["split"]["n_test"],
            sp=m["dataset"]["balance"]["si_pct"],
        ))

        for actual, predicted, n in [
            ("no", "no", cm["tn"]),
            ("no", "si", cm["fp"]),
            ("si", "no", cm["fn"]),
            ("si", "si", cm["tp"]),
        ]:
            cx.execute(
                text("INSERT INTO model_confusion VALUES (:r, :a, :p, :n)"),
                dict(r=run_id, a=actual, p=predicted, n=n),
            )

        for comp in m["model_comparison"]:
            cx.execute(
                text("INSERT INTO model_comparison VALUES (:r, :mn, :f1, :auc)"),
                dict(r=run_id, mn=comp["model"], f1=comp["f1"], auc=comp["roc_auc"]),
            )

    return run_id


if __name__ == "__main__":
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise SystemExit("ERROR: SUPABASE_DB_URL no definida en el entorno.")
    if not METRICS_PATH.exists():
        raise SystemExit(f"ERROR: {METRICS_PATH} no existe. Ejecuta primero el notebook de Fase 2.")

    run_id = load_metrics(db_url)
    print("Cargado run_id:", run_id)
    print("Verificar con: SELECT * FROM model_metrics WHERE run_id =", f"'{run_id}';")
