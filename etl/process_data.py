"""
ETL Bank Marketing: lectura → validación → limpieza → PostgreSQL (raw) + Supabase (clean).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from db import TZ_NAME, _tz, log, get_engine, get_supabase_engine, create_tables, create_tables_supabase

EXPECTED_COLUMNS = [
    "age",
    "job",
    "marital",
    "education",
    "default",
    "balance",
    "housing",
    "loan",
    "contact",
    "day",
    "month",
    "duration",
    "campaign",
    "pdays",
    "previous",
    "poutcome",
    "deposit",
]

TEXT_COLUMNS = [
    "job",
    "marital",
    "education",
    "default_credit",
    "housing",
    "loan",
    "contact",
    "month",
    "poutcome",
    "deposit",
]

NUMERIC_COLUMNS = [
    "age",
    "balance",
    "day",
    "duration",
    "campaign",
    "pdays",
    "previous",
]

BINARY_COLUMNS = ["default_credit", "housing", "loan", "deposit"]

VALID_MARITAL = {"married", "single", "divorced"}
VALID_EDUCATION = {"primary", "secondary", "tertiary", "unknown"}
VALID_CONTACT = {"cellular", "telephone", "unknown"}
VALID_POUTCOME = {"success", "failure", "other", "unknown"}
VALID_JOBS = {
    "admin.",
    "unknown",
    "unemployed",
    "management",
    "housemaid",
    "entrepreneur",
    "student",
    "blue-collar",
    "self-employed",
    "retired",
    "technician",
    "services",
}


def resolve_data_file() -> Path:
    explicit = os.getenv("DATA_FILE")
    if explicit:
        path = Path(explicit)
        if path.exists():
            return path
    data_dir = Path("/data")
    for name in ("bank.csv", "bank.xlsx", "bank.xls"):
        candidate = data_dir / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "No se encontró bank.csv ni bank.xlsx en /data. "
        "Coloca el archivo en bank-pipeline/data/"
    )


def read_source(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def validate_structure(df: pd.DataFrame) -> None:
    missing = set(EXPECTED_COLUMNS) - set(df.columns)
    extra = set(df.columns) - set(EXPECTED_COLUMNS)
    if missing:
        raise ValueError(f"Faltan columnas: {sorted(missing)}")
    if extra:
        raise ValueError(f"Columnas no esperadas: {sorted(extra)}")


def load_raw(df: pd.DataFrame, engine) -> None:
    raw = df.copy()
    raw = raw.rename(columns={"default": "default_credit"})
    raw["loaded_at"] = datetime.now(_tz).isoformat()
    raw = raw.astype(str)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE bank_raw RESTART IDENTITY"))
    raw.to_sql("bank_raw", engine, if_exists="append", index=False)


def _row_to_dict(row) -> dict:
    """Convierte una fila de DataFrame a dict serializable en JSON."""
    result = {}
    for k, v in row.items():
        try:
            if pd.isna(v):
                result[k] = None
                continue
        except (TypeError, ValueError):
            pass
        result[k] = v.item() if hasattr(v, "item") else v
    return result


def clean_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list, list]:
    rejected: list[dict] = []
    row_logs: list[dict] = []
    stats: dict = {}
    stats["registros_iniciales"] = len(df)

    df = df.rename(columns={"default": "default_credit"})

    # ── Duplicados ───────────────────────────────────────────────────────────
    dup_mask = df.duplicated()
    for i, row in df[dup_mask].iterrows():
        rejected.append({"row_index": int(i), "reason": "duplicado", "data": _row_to_dict(row)})
    stats["duplicados_eliminados"] = int(dup_mask.sum())
    df = df.drop_duplicates()

    # ── Normalización de texto ──────────────────────────────────────────────────
    # Capturar valores ANTES de normalizar para comparar luego
    existing_text_cols = [c for c in TEXT_COLUMNS if c in df.columns]
    df_pre_norm = df[existing_text_cols].astype(str).copy()

    for col in existing_text_cols:
        df[col] = df[col].astype(str).str.strip().str.lower()
        df[col] = df[col].replace({"nan": "unknown", "": "unknown"})

    # Registrar filas donde algo cambió
    for idx in df.index:
        changes = {}
        for col in existing_text_cols:
            before = df_pre_norm.at[idx, col]
            after = df.at[idx, col]
            if before != after:
                changes[col] = {"antes": before, "despues": after}
        if changes:
            row_logs.append({
                "row_index": int(idx),
                "event": "normalizado",
                "detail": "; ".join(f"{c}: '{v['antes']}'→'{v['despues']}'" for c, v in changes.items()),
                "data": _row_to_dict(df.loc[idx]),
            })

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── Fuera de rango ───────────────────────────────────────────────────────
    range_mask = (
        (df["age"] >= 18) & (df["age"] <= 100)
        & (df["day"] >= 1) & (df["day"] <= 31)
        & (df["duration"] >= 0)
        & (df["campaign"] >= 1)
        & (df["previous"] >= 0)
        & (df["pdays"] >= -1)
    )
    for i, row in df[~range_mask].iterrows():
        rejected.append({"row_index": int(i), "reason": "fuera_de_rango", "data": _row_to_dict(row)})
    before_ranges = len(df)
    df = df[range_mask]
    stats["filas_fuera_de_rango"] = before_ranges - len(df)

    # ── Binarias ───────────────────────────────────────────────────────────────
    for col in BINARY_COLUMNS:
        original_vals = df[col].copy()
        df[col] = df[col].map({"yes": True, "no": False})
        # Detectar valores que no eran yes/no y no eran ya nulos
        invalid_bin = df[col].isna() & original_vals.notna()
        for idx in df[invalid_bin].index:
            row_logs.append({
                "row_index": int(idx),
                "event": "binario_invalido",
                "detail": f"{col}: valor '{original_vals.at[idx]}' no es yes/no → NULL",
                "data": _row_to_dict(df.loc[idx]),
            })

    # ── Categoría inválida ───────────────────────────────────────────────────
    cat_mask = (
        df["marital"].isin(VALID_MARITAL)
        & df["education"].isin(VALID_EDUCATION)
        & df["contact"].isin(VALID_CONTACT)
        & df["poutcome"].isin(VALID_POUTCOME)
        & df["job"].isin(VALID_JOBS)
    )
    for i, row in df[~cat_mask].iterrows():
        rejected.append({"row_index": int(i), "reason": "categoria_invalida", "data": _row_to_dict(row)})
    before_cat = len(df)
    df = df[cat_mask]
    stats["filas_categoria_invalida"] = before_cat - len(df)

    # ── Nulos críticos ───────────────────────────────────────────────────────
    critical = [
        "age", "balance", "day", "duration",
        "campaign", "pdays", "previous", "deposit",
    ]
    null_mask = df[critical].isna().any(axis=1)
    for i, row in df[null_mask].iterrows():
        rejected.append({"row_index": int(i), "reason": "nulo_critico", "data": _row_to_dict(row)})
    null_before = len(df)
    df = df.dropna(subset=critical)
    stats["filas_con_nulos_criticos"] = null_before - len(df)
    stats["registros_finales"] = len(df)
    stats["nulos_por_columna"] = df.isnull().sum().to_dict()

    # ── Registro final por fila: aceptado o rechazado ───────────────────────────
    for i, row in df.iterrows():
        row_logs.append({
            "row_index": int(i),
            "event": "aceptado",
            "detail": "fila procesada y cargada",
            "data": _row_to_dict(row),
        })
    for r in rejected:
        row_logs.append({
            "row_index": r["row_index"],
            "event": "rechazado",
            "detail": r["reason"],
            "data": r["data"],
        })

    return df, stats, rejected, row_logs


def load_clean_supabase(df: pd.DataFrame, engine) -> None:
    """Carga datos limpios en Supabase (reemplaza todo en cada ejecución)."""
    out = df.copy()
    out["processed_at"] = datetime.now(_tz)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE bank_clean RESTART IDENTITY"))
    out.to_sql("bank_clean", engine, if_exists="append", index=False)


def load_rejected(rejected: list, engine) -> None:
    """Guarda las filas rechazadas en etl_rejected (reemplaza en cada ejecución)."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE etl_rejected RESTART IDENTITY"))
        for r in rejected:
            conn.execute(
                text("""
                    INSERT INTO etl_rejected (run_at, row_index, reason, original_data)
                    VALUES (:run_at, :row_index, :reason, CAST(:original_data AS jsonb))
                """),
                {
                    "run_at": datetime.now(_tz),
                    "row_index": r["row_index"],
                    "reason": r["reason"],
                    "original_data": json.dumps(r["data"], ensure_ascii=False, default=str),
                },
            )


def load_row_logs(row_logs: list, engine) -> None:
    """Guarda los logs granulares por fila (normaliz. y binarios inválidos)."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE etl_row_logs RESTART IDENTITY"))
        if not row_logs:
            return
        conn.execute(
            text("""
                INSERT INTO etl_row_logs (run_at, row_index, event, detail, snapshot)
                VALUES (:run_at, :row_index, :event, :detail, CAST(:snapshot AS jsonb))
            """),
            [
                {
                    "run_at": datetime.now(_tz),
                    "row_index": r["row_index"],
                    "event": r["event"],
                    "detail": r["detail"],
                    "snapshot": json.dumps(r["data"], ensure_ascii=False, default=str),
                }
                for r in row_logs
            ],
        )


def write_report(stats: dict, source_file: str, engine) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": source_file,
        **stats,
    }
    # Intentar escribir en /reports (local/dev); en Render es efímero pero no falla
    try:
        report_dir = Path("/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "quality_report.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass
    # Persistir siempre en PostgreSQL
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO etl_reports
                    (generated_at, source_file, registros_iniciales,
                     duplicados_eliminados, filas_fuera_de_rango,
                     filas_categoria_invalida, filas_con_nulos_criticos,
                     registros_finales, payload)
                VALUES
                    (NOW(), :source_file, :registros_iniciales,
                     :duplicados_eliminados, :filas_fuera_de_rango,
                     :filas_categoria_invalida, :filas_con_nulos_criticos,
                     :registros_finales, CAST(:payload AS jsonb))
            """),
            {
                "source_file": source_file,
                "registros_iniciales": stats.get("registros_iniciales"),
                "duplicados_eliminados": stats.get("duplicados_eliminados"),
                "filas_fuera_de_rango": stats.get("filas_fuera_de_rango"),
                "filas_categoria_invalida": stats.get("filas_categoria_invalida"),
                "filas_con_nulos_criticos": stats.get("filas_con_nulos_criticos"),
                "registros_finales": stats.get("registros_finales"),
                "payload": json.dumps(payload, ensure_ascii=False),
            },
        )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    log.info("=== ETL Bank Marketing iniciado ===")
    log.info("Zona horaria activa: %s", TZ_NAME)

    source = resolve_data_file()
    log.info("Archivo fuente: %s", source)

    df = read_source(source)
    validate_structure(df)
    initial_rows = len(df)
    log.info("Registros leídos: %d", initial_rows)

    engine = get_engine()
    create_tables(engine)
    load_raw(df, engine)
    log.info("[Render PG] bank_raw cargado: %d filas (loaded_at en %s)", initial_rows, TZ_NAME)

    clean_df, stats, rejected, row_logs = clean_data(df)
    log.info("Limpieza completada: %d → %d filas", initial_rows, stats["registros_finales"])
    log.info("  duplicados eliminados   : %d", stats["duplicados_eliminados"])
    log.info("  filas fuera de rango    : %d", stats["filas_fuera_de_rango"])
    log.info("  filas categoría inválida: %d", stats["filas_categoria_invalida"])
    log.info("  filas nulos críticos    : %d", stats["filas_con_nulos_criticos"])

    load_rejected(rejected, engine)
    log.info("[Render PG] etl_rejected: %d filas rechazadas registradas", len(rejected))

    load_row_logs(row_logs, engine)
    log.info("[Render PG] etl_row_logs: %d eventos granulares registrados", len(row_logs))

    # --- Supabase: destino de datos limpios ---
    supabase_engine = get_supabase_engine()
    if supabase_engine:
        create_tables_supabase(supabase_engine)
        load_clean_supabase(clean_df, supabase_engine)
        log.info("[Supabase] bank_clean cargado: %d filas", stats["registros_finales"])
    else:
        log.info("[Supabase] SUPABASE_URL no configurada, omitiendo carga.")

    stats["archivo_origen"] = str(source.name)
    write_report(stats, str(source), engine)

    log.info("=== ETL finalizado correctamente ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log.exception("ERROR ETL: %s", exc)
        sys.exit(1)
