"""Configuración central del servicio de predicción.

Todo se lee desde variables de entorno. No hay credenciales en el código.
"""
import os

# --- Conexión a base de datos (Postgres / Supabase) -------------------------
# Reutiliza la misma cadena del ETL. Acepta SUPABASE_DB_URL o, si no existe,
# SUPABASE_URL (la que ya usa el pipeline actual).
DB_URL = os.getenv("SUPABASE_DB_URL") or os.getenv("SUPABASE_URL")

# --- Supabase Storage (artefacto del modelo) --------------------------------
# OJO: esta NO es la cadena de Postgres. Es la URL del proyecto Supabase.
SUPABASE_PROJECT_URL = os.getenv("SUPABASE_PROJECT_URL")   # https://xxxx.supabase.co
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")   # service_role key
MODEL_BUCKET = os.getenv("MODEL_BUCKET", "models")
MODEL_PREFIX = os.getenv("MODEL_PREFIX", "deposit")        # "carpeta" lógica dentro del bucket

# --- Autenticación del API --------------------------------------------------
API_KEY = os.getenv("API_KEY")            # obligatorio en producción
API_KEY_HEADER = "X-API-Key"

# --- Predicción -------------------------------------------------------------
DEFAULT_THRESHOLD = float(os.getenv("DEFAULT_THRESHOLD", "0.5"))
RANDOM_STATE = 42

# --- Reentrenamiento --------------------------------------------------------
DEFAULT_SAMPLE_SIZE = int(os.getenv("RETRAIN_SAMPLE_SIZE", "5000"))
MIN_SAMPLE_SIZE = 500

# --- Tablas -----------------------------------------------------------------
BANK_CLEAN_TABLE = "bank_clean"
MODEL_SCORES_TABLE = "model_scores"
RETRAIN_JOBS_TABLE = "retrain_jobs"

# Columna identificadora en bank_clean usada para buscar registros.
# ⚠️ CONFIRMAR contra el esquema real. Normalmente es 'id' (PK de bank_clean).
# El request del API la llama 'raw_id' por convención de negocio.
CLEAN_ID_COLUMN = os.getenv("CLEAN_ID_COLUMN", "id")

# --- Artefacto base horneado en la imagen (fallback de arranque en frío) ----
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
BASE_MODEL_PATH = os.path.join(ARTIFACTS_DIR, "base_model.joblib")
BASE_CARD_PATH = os.path.join(ARTIFACTS_DIR, "model_card.json")
