import pandas as pd
import numpy as np

df = pd.read_csv("bank.csv")

# ── 1. DUPLICADOS (5 filas repetidas) ─────────────────────────────────────
df = pd.concat([df, df.iloc[:5]], ignore_index=True)

# ── 2. RANGOS INVÁLIDOS ────────────────────────────────────────────────────
df.loc[0, "age"]      = 15       # age < 18
df.loc[1, "age"]      = 120      # age > 100
df.loc[2, "day"]      = 0        # day < 1
df.loc[3, "day"]      = 35       # day > 31
df.loc[4, "duration"] = -5       # duration < 0
df.loc[5, "campaign"] = 0        # campaign < 1
df.loc[6, "previous"] = -3       # previous < 0
df.loc[7, "pdays"]    = -5       # pdays < -1

# ── 3. CATEGORÍAS INVÁLIDAS ────────────────────────────────────────────────
df.loc[10, "marital"]   = "widowed"      # no está en VALID_MARITAL
df.loc[11, "education"] = "phd"          # no está en VALID_EDUCATION
df.loc[12, "contact"]   = "email"        # no está en VALID_CONTACT
df.loc[13, "poutcome"]  = "cancelled"    # no está en VALID_POUTCOME
df.loc[14, "job"]       = "influencer"   # no está en VALID_JOBS

# ── 4. NORMALIZACIÓN DE TEXTO (mayúsculas y espacios) ─────────────────────
df.loc[20, "marital"]   = "  Married  "  # espacios + mayúscula → limpieza lo arregla
df.loc[21, "job"]       = "ADMIN."       # mayúsculas → limpieza lo arregla
df.loc[22, "education"] = "Secondary"    # capitalizada → limpieza lo arregla

# ── 5. NULOS EN COLUMNAS CRÍTICAS ─────────────────────────────────────────
df.loc[30, "age"]      = np.nan
df.loc[31, "balance"]  = np.nan
df.loc[32, "deposit"]  = np.nan
df.loc[33, "duration"] = np.nan

# ── 6. BINARIAS CON VALOR EXTRAÑO ─────────────────────────────────────────
df.loc[40, "housing"]        = "maybe"   # ni yes ni no → NaN tras map
df.loc[41, "default"]        = "true"    # no es yes/no → NaN tras map
df.loc[42, "loan"]           = "1"       # → NaN tras map (no crítica, no elimina fila)

df.to_csv("bank_dirty.csv", index=False)
print(f"bank_dirty.csv generado con {len(df)} filas ({len(df) - 5} originales + 5 duplicados + errores)")