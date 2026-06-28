"""Capa de acceso a datos (Postgres / Supabase) vía SQLAlchemy."""
import pandas as pd
from sqlalchemy import create_engine, text, bindparam

from . import config

engine = create_engine(config.DB_URL, pool_pre_ping=True)


# --- DDL: crea las tablas nuevas si no existen ------------------------------
_DDL_SCORES = f"""
CREATE TABLE IF NOT EXISTS {config.MODEL_SCORES_TABLE} (
    id            BIGSERIAL PRIMARY KEY,
    raw_id        BIGINT,
    prob_deposit  DOUBLE PRECISION NOT NULL,
    pred_deposit  BOOLEAN NOT NULL,
    threshold     DOUBLE PRECISION NOT NULL,
    model_version TEXT NOT NULL,
    scored_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_DDL_JOBS = f"""
CREATE TABLE IF NOT EXISTS {config.RETRAIN_JOBS_TABLE} (
    job_id        UUID PRIMARY KEY,
    status        TEXT NOT NULL,
    sample_size   INTEGER,
    model_version TEXT,
    metrics       JSONB,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    error         TEXT
);
"""


def init_tables() -> None:
    with engine.begin() as conn:
        conn.execute(text(_DDL_SCORES))
        conn.execute(text(_DDL_JOBS))


# --- Lectura de bank_clean --------------------------------------------------
def fetch_clean_rows(ids: list) -> pd.DataFrame:
    """Trae las filas de bank_clean cuyos identificadores estén en `ids`."""
    stmt = text(
        f"SELECT * FROM {config.BANK_CLEAN_TABLE} "
        f"WHERE {config.CLEAN_ID_COLUMN} IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    return pd.read_sql(stmt, engine, params={"ids": ids})


def fetch_retrain_source() -> pd.DataFrame:
    """Trae todo bank_clean (features + target) para muestrear y reentrenar."""
    return pd.read_sql(text(f"SELECT * FROM {config.BANK_CLEAN_TABLE}"), engine)


# --- Escritura de scores ----------------------------------------------------
def insert_scores(rows: list) -> None:
    """rows: lista de dicts con raw_id, prob, pred, thr, ver."""
    if not rows:
        return
    stmt = text(
        f"INSERT INTO {config.MODEL_SCORES_TABLE} "
        "(raw_id, prob_deposit, pred_deposit, threshold, model_version) "
        "VALUES (:raw_id, :prob, :pred, :thr, :ver)"
    )
    with engine.begin() as conn:
        conn.execute(stmt, rows)


# --- Jobs de reentrenamiento ------------------------------------------------
def running_job_exists() -> bool:
    stmt = text(
        f"SELECT 1 FROM {config.RETRAIN_JOBS_TABLE} WHERE status = 'running' LIMIT 1"
    )
    with engine.connect() as conn:
        return conn.execute(stmt).first() is not None


def create_job(job_id: str, sample_size: int) -> None:
    stmt = text(
        f"INSERT INTO {config.RETRAIN_JOBS_TABLE} (job_id, status, sample_size) "
        "VALUES (:job_id, 'running', :sample_size)"
    )
    with engine.begin() as conn:
        conn.execute(stmt, {"job_id": job_id, "sample_size": sample_size})


def finish_job(job_id: str, model_version: str, metrics: dict) -> None:
    import json
    stmt = text(
        f"UPDATE {config.RETRAIN_JOBS_TABLE} SET status='done', "
        "model_version=:ver, metrics=CAST(:metrics AS JSONB), finished_at=now() "
        "WHERE job_id=:job_id"
    )
    with engine.begin() as conn:
        conn.execute(stmt, {"job_id": job_id, "ver": model_version,
                            "metrics": json.dumps(metrics)})


def fail_job(job_id: str, error: str) -> None:
    stmt = text(
        f"UPDATE {config.RETRAIN_JOBS_TABLE} SET status='failed', "
        "error=:error, finished_at=now() WHERE job_id=:job_id"
    )
    with engine.begin() as conn:
        conn.execute(stmt, {"job_id": job_id, "error": error[:5000]})


def get_job(job_id: str) -> dict | None:
    stmt = text(f"SELECT * FROM {config.RETRAIN_JOBS_TABLE} WHERE job_id=:job_id")
    with engine.connect() as conn:
        row = conn.execute(stmt, {"job_id": job_id}).mappings().first()
        return dict(row) if row else None


def get_metrics_for_version(version: str) -> dict | None:
    stmt = text(
        f"SELECT metrics FROM {config.RETRAIN_JOBS_TABLE} "
        "WHERE model_version=:ver AND status='done' "
        "ORDER BY finished_at DESC LIMIT 1"
    )
    with engine.connect() as conn:
        row = conn.execute(stmt, {"ver": version}).first()
        return row[0] if row else None
