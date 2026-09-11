-- ============================================================
-- RA-PoC: ML v2 Extension Tables (Autoencoder + NLP)
-- ============================================================

-- Autoencoder anomaly detection (deep learning)
CREATE TABLE IF NOT EXISTS ml_autoencoder_anomaly (
    id              SERIAL PRIMARY KEY,
    run_date        TIMESTAMP DEFAULT NOW(),
    cycle_code      VARCHAR(10) NOT NULL,
    reconstruction_error NUMERIC(12,6) NOT NULL,
    threshold       NUMERIC(12,6) NOT NULL,
    is_anomaly      BOOLEAN DEFAULT FALSE,
    error_ratio     NUMERIC(8,4),
    features_used   TEXT,
    description     VARCHAR(500),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- NLP justification classification
CREATE TABLE IF NOT EXISTS ml_nlp_classification (
    id              SERIAL PRIMARY KEY,
    run_date        TIMESTAMP DEFAULT NOW(),
    result_id       INTEGER REFERENCES ra_result(result_id),
    original_text   TEXT NOT NULL,
    category        VARCHAR(50) NOT NULL,
    subcategory     VARCHAR(50),
    confidence      NUMERIC(5,4),
    embedding_cluster INTEGER,
    suggested_action VARCHAR(200),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- NLP category summary
CREATE TABLE IF NOT EXISTS ml_nlp_category_summary (
    id              SERIAL PRIMARY KEY,
    run_date        TIMESTAMP DEFAULT NOW(),
    category        VARCHAR(50) NOT NULL,
    total_count     INTEGER NOT NULL,
    total_value     NUMERIC(14,2),
    avg_confidence  NUMERIC(5,4),
    top_offers      TEXT,
    suggested_action VARCHAR(200),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ml_ae_cycle ON ml_autoencoder_anomaly(cycle_code);
CREATE INDEX IF NOT EXISTS idx_ml_nlp_category ON ml_nlp_classification(category);
CREATE INDEX IF NOT EXISTS idx_ml_nlp_result ON ml_nlp_classification(result_id);
