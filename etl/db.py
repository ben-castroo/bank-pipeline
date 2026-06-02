"""
Configuración de logger, zona horaria y utilidades de base de datos.
Importado tanto por process_data.py como por app.py.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Logger con zona horaria configurable (por defecto UTC)
# ---------------------------------------------------------------------------
TZ_NAME = os.getenv("TZ", "UTC")
_tz = ZoneInfo(TZ_NAME)


class _TZFormatter(logging.Formatter):
    """Formateador que incluye la zona horaria en cada mensaje."""

    def formatTime(self, record, datefmt=None):  # noqa: N802
        dt = datetime.fromtimestamp(record.created, tz=_tz)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%dT%H:%M:%S %Z%z")


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(
    _TZFormatter(fmt="%(asctime)s [%(levelname)s] %(message)s")
)
log = logging.getLogger("etl")
log.setLevel(logging.INFO)
log.addHandler(_handler)
log.propagate = False


# ---------------------------------------------------------------------------
# Conexiones a base de datos
# ---------------------------------------------------------------------------
def get_engine():
    """Engine hacia Render PostgreSQL (DATABASE_URL o variables individuales)."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
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


def get_supabase_engine():
    """Engine hacia Supabase usando SUPABASE_URL. Retorna None si no está definida.

    Usar el URL del connection pooler (puerto 6543) para evitar problemas de IPv6.
    """
    url = os.getenv("SUPABASE_URL")
    if not url:
        return None
    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if "sslmode" not in url:
        url += "?sslmode=require"
    return create_engine(url)


# ---------------------------------------------------------------------------
# DDL: creación de tablas
# ---------------------------------------------------------------------------
def create_tables(engine) -> None:
    """Crea las tablas de metadatos en Render PostgreSQL si no existen."""
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
            CREATE TABLE IF NOT EXISTS etl_reports (
                id SERIAL PRIMARY KEY,
                generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                source_file TEXT,
                registros_iniciales INTEGER,
                duplicados_eliminados INTEGER,
                filas_fuera_de_rango INTEGER,
                filas_categoria_invalida INTEGER,
                filas_con_nulos_criticos INTEGER,
                registros_finales INTEGER,
                payload JSONB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS etl_rejected (
                id SERIAL PRIMARY KEY,
                run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                row_index INTEGER,
                raw_id INTEGER,
                reason VARCHAR(60),
                original_data JSONB
            );
            CREATE TABLE IF NOT EXISTS etl_row_logs (
                id SERIAL PRIMARY KEY,
                run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                row_index INTEGER,
                raw_id INTEGER,
                event VARCHAR(40),
                detail TEXT,
                snapshot JSONB
            );
        """))
        # Migración: añadir raw_id a tablas existentes si aún no tienen la columna
        conn.execute(text("ALTER TABLE etl_rejected ADD COLUMN IF NOT EXISTS raw_id INTEGER"))
        conn.execute(text("ALTER TABLE etl_row_logs ADD COLUMN IF NOT EXISTS raw_id INTEGER"))
    log.info("Tablas verificadas/creadas en Render PostgreSQL.")


def create_tables_supabase(engine) -> None:
    """Crea bank_clean en Supabase si no existe."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bank_clean (
                id SERIAL PRIMARY KEY,
                processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                raw_id INTEGER,
                age INTEGER, job VARCHAR(50), marital VARCHAR(30),
                education VARCHAR(30), default_credit BOOLEAN, balance INTEGER,
                housing BOOLEAN, loan BOOLEAN, contact VARCHAR(30), day INTEGER,
                month VARCHAR(10), duration INTEGER, campaign INTEGER,
                pdays INTEGER, previous INTEGER, poutcome VARCHAR(30),
                deposit BOOLEAN
            );
            CREATE INDEX IF NOT EXISTS idx_bank_clean_deposit ON bank_clean (deposit);
        """))
        # Migración: añadir raw_id a tabla existente si aún no tiene la columna
        conn.execute(text("ALTER TABLE bank_clean ADD COLUMN IF NOT EXISTS raw_id INTEGER"))
    log.info("Tabla bank_clean verificada/creada en Supabase.")
