"""
ETL Bank Marketing: lectura → validación → limpieza → PostgreSQL (raw + clean).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

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


def get_engine():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Render usa postgresql://, SQLAlchemy necesita postgresql+psycopg2://
        url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        if "sslmode" not in url:
            url += "?sslmode=require"
        return create_engine(url)
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    host = os.environ["DB_HOST"]
    port = os.environ["DB_PORT"]
    name = os.environ["DB_NAME"]
    return create_engine(
        f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    )


def create_tables(engine) -> None:
    """Crea las tablas si no existen (Opción B: sin init.sql externo)."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bank_raw (
                id SERIAL PRIMARY KEY,
                loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                age TEXT, job TEXT, marital TEXT, education TEXT,
                default_credit TEXT, balance TEXT, housing TEXT, loan TEXT,
                contact TEXT, day TEXT, month TEXT, duration TEXT,
                campaign TEXT, pdays TEXT, previous TEXT, poutcome TEXT,
                deposit TEXT
            );
            CREATE TABLE IF NOT EXISTS bank_clean (
                id SERIAL PRIMARY KEY,
                processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                age INTEGER, job VARCHAR(50), marital VARCHAR(30),
                education VARCHAR(30), default_credit BOOLEAN, balance INTEGER,
                housing BOOLEAN, loan BOOLEAN, contact VARCHAR(30), day INTEGER,
                month VARCHAR(10), duration INTEGER, campaign INTEGER,
                pdays INTEGER, previous INTEGER, poutcome VARCHAR(30),
                deposit BOOLEAN
            );
            CREATE INDEX IF NOT EXISTS idx_bank_clean_deposit ON bank_clean (deposit);
        """))
    print("Tablas verificadas/creadas correctamente.")


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
    raw = raw.astype(str)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE bank_raw RESTART IDENTITY"))
    raw.to_sql("bank_raw", engine, if_exists="append", index=False)


def clean_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    stats: dict = {}
    stats["registros_iniciales"] = len(df)

    df = df.rename(columns={"default": "default_credit"})
    stats["duplicados_eliminados"] = int(df.duplicated().sum())
    df = df.drop_duplicates()

    for col in TEXT_COLUMNS:
        df[col] = df[col].astype(str).str.strip().str.lower()
        df[col] = df[col].replace({"nan": "unknown", "": "unknown"})

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    before_ranges = len(df)
    df = df[(df["age"] >= 18) & (df["age"] <= 100)]
    df = df[(df["day"] >= 1) & (df["day"] <= 31)]
    df = df[df["duration"] >= 0]
    df = df[df["campaign"] >= 1]
    df = df[df["previous"] >= 0]
    df = df[df["pdays"] >= -1]
    stats["filas_fuera_de_rango"] = before_ranges - len(df)

    for col in BINARY_COLUMNS:
        df[col] = df[col].map({"yes": True, "no": False})

    before_cat = len(df)
    df = df[df["marital"].isin(VALID_MARITAL)]
    df = df[df["education"].isin(VALID_EDUCATION)]
    df = df[df["contact"].isin(VALID_CONTACT)]
    df = df[df["poutcome"].isin(VALID_POUTCOME)]
    df = df[df["job"].isin(VALID_JOBS)]
    stats["filas_categoria_invalida"] = before_cat - len(df)

    null_before = len(df)
    critical = [
        "age",
        "balance",
        "day",
        "duration",
        "campaign",
        "pdays",
        "previous",
        "deposit",
    ]
    df = df.dropna(subset=critical)
    stats["filas_con_nulos_criticos"] = null_before - len(df)
    stats["registros_finales"] = len(df)
    stats["nulos_por_columna"] = df.isnull().sum().to_dict()

    return df, stats


def load_clean(df: pd.DataFrame, engine) -> None:
    out = df.copy()
    out["processed_at"] = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE bank_clean RESTART IDENTITY"))
    out.to_sql("bank_clean", engine, if_exists="append", index=False)


def write_report(stats: dict, source_file: str) -> None:
    report_dir = Path("/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": source_file,
        **stats,
    }
    path = report_dir / "quality_report.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    source = resolve_data_file()
    print(f"Leyendo: {source}")

    df = read_source(source)
    validate_structure(df)
    initial_rows = len(df)

    engine = get_engine()
    create_tables(engine)
    load_raw(df, engine)
    print(f"Cargados {initial_rows} registros en bank_raw")

    clean_df, stats = clean_data(df)
    load_clean(clean_df, engine)

    stats["archivo_origen"] = str(source.name)
    write_report(stats, str(source))

    print("ETL finalizado correctamente.")
    print(f"  Raw:   {initial_rows} filas")
    print(f"  Clean: {stats['registros_finales']} filas")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR ETL: {exc}", file=sys.stderr)
        sys.exit(1)
