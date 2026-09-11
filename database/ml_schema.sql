-- ============================================================
-- RA-PoC: ML Extension Tables
-- ============================================================

-- Revenue forecast (time series predictions)
CREATE TABLE IF NOT EXISTS ml_revenue_forecast (
    forecast_id     SERIAL PRIMARY KEY,
    run_date        TIMESTAMP DEFAULT NOW(),
    cycle_code      VARCHAR(10) NOT NULL,
    actual_revenue  NUMERIC(14,2),
    predicted_revenue NUMERIC(14,2) NOT NULL,
    lower_bound     NUMERIC(14,2),
    upper_bound     NUMERIC(14,2),
    model_type      VARCHAR(30) DEFAULT 'prophet',
    mape            NUMERIC(8,4),
    is_future       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Anomaly detection results
CREATE TABLE IF NOT EXISTS ml_anomaly (
    anomaly_id      SERIAL PRIMARY KEY,
    run_date        TIMESTAMP DEFAULT NOW(),
    cycle_code      VARCHAR(10) NOT NULL,
    metric_name     VARCHAR(50) NOT NULL,
    metric_value    NUMERIC(14,2) NOT NULL,
    expected_value  NUMERIC(14,2),
    z_score         NUMERIC(8,4),
    is_anomaly      BOOLEAN DEFAULT FALSE,
    severity        VARCHAR(10) CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    description     VARCHAR(500),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Dynamic churn prediction
CREATE TABLE IF NOT EXISTS ml_churn_prediction (
    prediction_id   SERIAL PRIMARY KEY,
    run_date        TIMESTAMP DEFAULT NOW(),
    cycle_code      VARCHAR(10) NOT NULL,
    actual_churn_rate NUMERIC(8,4),
    predicted_churn_rate NUMERIC(8,4) NOT NULL,
    active_contracts INTEGER,
    predicted_cancellations INTEGER,
    risk_revenue    NUMERIC(14,2),
    model_type      VARCHAR(30) DEFAULT 'logistic_regression',
    is_future       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ML model metadata
CREATE TABLE IF NOT EXISTS ml_model_run (
    model_run_id    SERIAL PRIMARY KEY,
    run_date        TIMESTAMP DEFAULT NOW(),
    model_name      VARCHAR(50) NOT NULL,
    model_version   VARCHAR(20) DEFAULT '1.0',
    training_cycles INTEGER,
    metrics         JSONB,
    status          VARCHAR(15) DEFAULT 'COMPLETED' CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED')),
    duration_ms     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_ml_forecast_cycle ON ml_revenue_forecast(cycle_code);
CREATE INDEX IF NOT EXISTS idx_ml_anomaly_cycle ON ml_anomaly(cycle_code);
CREATE INDEX IF NOT EXISTS idx_ml_churn_cycle ON ml_churn_prediction(cycle_code);
