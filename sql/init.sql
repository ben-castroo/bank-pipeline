-- Capa RAW: todo como TEXT (sin transformar)
CREATE TABLE IF NOT EXISTS bank_raw (
    id SERIAL PRIMARY KEY,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    age TEXT,
    job TEXT,
    marital TEXT,
    education TEXT,
    default_credit TEXT,
    balance TEXT,
    housing TEXT,
    loan TEXT,
    contact TEXT,
    day TEXT,
    month TEXT,
    duration TEXT,
    campaign TEXT,
    pdays TEXT,
    previous TEXT,
    poutcome TEXT,
    deposit TEXT
);

-- Capa CLEAN: tipos listos para análisis / ML posterior
CREATE TABLE IF NOT EXISTS bank_clean (
    id SERIAL PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    age INTEGER,
    job VARCHAR(50),
    marital VARCHAR(30),
    education VARCHAR(30),
    default_credit BOOLEAN,
    balance INTEGER,
    housing BOOLEAN,
    loan BOOLEAN,
    contact VARCHAR(30),
    day INTEGER,
    month VARCHAR(10),
    duration INTEGER,
    campaign INTEGER,
    pdays INTEGER,
    previous INTEGER,
    poutcome VARCHAR(30),
    deposit BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_bank_clean_deposit ON bank_clean (deposit);
