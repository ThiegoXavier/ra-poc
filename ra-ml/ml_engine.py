#!/usr/bin/env python3
"""
RA-PoC ML Engine
Machine Learning module for Revenue Assurance:
  - Revenue forecasting (Prophet-style decomposition via scikit-learn)
  - Anomaly detection (Z-score + Isolation Forest)
  - Dynamic churn prediction (Logistic Regression features)
"""

import os
import sys
import time
import json
import warnings
from datetime import datetime
from decimal import Decimal

import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor

# Suppress sklearn warnings
warnings.filterwarnings("ignore")

try:
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.ensemble import IsolationForest, GradientBoostingRegressor
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler
    from sklearn.metrics import mean_absolute_percentage_error
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    print("WARNING: scikit-learn not installed. Using fallback methods.")

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "30432")),
    "dbname": os.environ.get("DB_NAME", "ra_billing"),
    "user": os.environ.get("DB_USER", "ra_admin"),
    "password": os.environ.get("DB_PASSWORD", "ra_poc_2024"),
}


def connect_db():
    return psycopg2.connect(**DB_CONFIG)


# ================================================================
# 1. REVENUE FORECASTING
# ================================================================

def forecast_revenue(conn):
    """
    Time series forecasting using Gradient Boosting with polynomial features.
    Trains on historical billing data and predicts 6 months ahead.
    """
    print("\n" + "─" * 60)
    print("  📈 ML Revenue Forecasting")
    print("─" * 60)

    start = time.time()

    # Load historical revenue
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT bc.cycle_code, bc.cycle_month, bc.cycle_year,
                   SUM(i.total_amount) AS revenue,
                   COUNT(DISTINCT i.customer_id) AS customers,
                   COUNT(DISTINCT ii.contract_id) AS contracts
            FROM billing_cycle bc
            JOIN invoice i ON i.cycle_id = bc.cycle_id
            JOIN invoice_item ii ON ii.invoice_id = i.invoice_id
            GROUP BY bc.cycle_code, bc.cycle_month, bc.cycle_year
            ORDER BY bc.cycle_code
        """)
        data = cur.fetchall()

    if len(data) < 6:
        print("  ⚠ Not enough data for forecasting (need >= 6 cycles)")
        return

    # Prepare features
    revenues = np.array([float(d["revenue"]) for d in data])
    months = np.arange(1, len(data) + 1).reshape(-1, 1)
    customers = np.array([d["customers"] for d in data]).reshape(-1, 1)
    contracts = np.array([d["contracts"] for d in data]).reshape(-1, 1)

    # Feature matrix: month, month^2, customers, contracts
    X = np.hstack([months, months ** 2, customers, contracts])

    if HAS_SKLEARN:
        # Gradient Boosting for non-linear patterns
        model = GradientBoostingRegressor(
            n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42
        )
        model.fit(X, revenues)
        fitted = model.predict(X)
        mape = mean_absolute_percentage_error(revenues, fitted) * 100
    else:
        # Fallback: simple linear trend
        slope = (revenues[-1] - revenues[0]) / (len(revenues) - 1)
        intercept = revenues[0] - slope
        fitted = np.array([intercept + slope * m for m in range(1, len(data) + 1)])
        mape = np.mean(np.abs((revenues - fitted) / revenues)) * 100

    print(f"  Training MAPE: {mape:.2f}%")
    print(f"  Model: {'GradientBoosting' if HAS_SKLEARN else 'LinearFallback'}")

    # Clear old forecasts
    with conn.cursor() as cur:
        cur.execute("TRUNCATE ml_revenue_forecast")

    # Save fitted values (historical)
    with conn.cursor() as cur:
        for i, d in enumerate(data):
            residual = revenues[i] - fitted[i]
            std = np.std(revenues - fitted)
            cur.execute("""
                INSERT INTO ml_revenue_forecast
                (cycle_code, actual_revenue, predicted_revenue, lower_bound, upper_bound,
                 model_type, mape, is_future)
                VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE)
            """, (
                d["cycle_code"],
                float(revenues[i]),
                float(fitted[i]),
                float(fitted[i] - 1.96 * std),
                float(fitted[i] + 1.96 * std),
                "gradient_boosting" if HAS_SKLEARN else "linear",
                float(mape),
            ))

    # Predict 6 months ahead
    last_month = len(data)
    last_customers = customers[-1][0]
    last_contracts = contracts[-1][0]
    churn_rate = 0.02

    print(f"\n  Future projections (6 months):")
    with conn.cursor() as cur:
        for i in range(1, 7):
            future_month = last_month + i
            future_customers = int(last_customers * (1 - churn_rate) ** i)
            future_contracts = int(last_contracts * (1 - churn_rate) ** i)

            X_future = np.array([[future_month, future_month ** 2,
                                  future_customers, future_contracts]])

            if HAS_SKLEARN:
                pred = model.predict(X_future)[0]
            else:
                pred = intercept + slope * future_month

            std = np.std(revenues - fitted)
            lower = pred - 1.96 * std
            upper = pred + 1.96 * std

            # Cycle code
            proj_month = data[-1]["cycle_month"] + i
            proj_year = data[-1]["cycle_year"]
            if proj_month > 12:
                proj_month -= 12
                proj_year += 1
            cycle_code = f"{proj_year}-{proj_month:02d}"

            cur.execute("""
                INSERT INTO ml_revenue_forecast
                (cycle_code, predicted_revenue, lower_bound, upper_bound,
                 model_type, mape, is_future)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            """, (cycle_code, float(pred), float(lower), float(upper),
                  "gradient_boosting" if HAS_SKLEARN else "linear", float(mape)))

            print(f"    {cycle_code}: ${pred:>12,.2f}  "
                  f"[${lower:>12,.2f} — ${upper:>12,.2f}]")

    conn.commit()
    elapsed = int((time.time() - start) * 1000)
    print(f"\n  ✓ Forecasting complete ({elapsed}ms)")
    return mape, elapsed


# ================================================================
# 2. ANOMALY DETECTION
# ================================================================

def detect_anomalies(conn):
    """
    Detect anomalies in billing metrics using Z-score and Isolation Forest.
    Monitors: revenue per cycle, gap rate, avg ticket, customer count.
    """
    print("\n" + "─" * 60)
    print("  🔍 ML Anomaly Detection")
    print("─" * 60)

    start = time.time()

    # Load cycle-level metrics
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT bc.cycle_code,
                   SUM(i.total_amount) AS revenue,
                   COUNT(DISTINCT i.customer_id) AS customers,
                   AVG(i.total_amount) AS avg_ticket,
                   COALESCE(SUM(CASE WHEN r.status LIKE 'GAP_%%' THEN 1 ELSE 0 END), 0) AS gap_count,
                   COALESCE(COUNT(r.*), 1) AS total_checks,
                   COALESCE(SUM(ABS(COALESCE(r.difference, 0))), 0) AS gap_value
            FROM billing_cycle bc
            JOIN invoice i ON i.cycle_id = bc.cycle_id
            LEFT JOIN ra_run rr ON rr.cycle_id = bc.cycle_id
            LEFT JOIN ra_result r ON r.run_id = rr.run_id
            GROUP BY bc.cycle_code
            ORDER BY bc.cycle_code
        """)
        data = cur.fetchall()

    if len(data) < 3:
        print("  ⚠ Not enough data for anomaly detection")
        return

    # Clear old anomalies
    with conn.cursor() as cur:
        cur.execute("TRUNCATE ml_anomaly")

    # Metrics to monitor
    metrics = {
        "revenue": [float(d["revenue"]) for d in data],
        "gap_rate": [float(d["gap_count"]) / max(float(d["total_checks"]), 1) * 100 for d in data],
        "avg_ticket": [float(d["avg_ticket"]) for d in data],
        "gap_value": [float(d["gap_value"]) for d in data],
        "customer_count": [float(d["customers"]) for d in data],
    }

    total_anomalies = 0

    if HAS_SKLEARN:
        # Isolation Forest on multi-dimensional data
        X_all = np.array([[metrics[m][i] for m in metrics] for i in range(len(data))])
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_all)

        iso_forest = IsolationForest(contamination=0.1, random_state=42)
        iso_labels = iso_forest.fit_predict(X_scaled)  # -1 = anomaly

    with conn.cursor() as cur:
        for metric_name, values in metrics.items():
            arr = np.array(values)
            mean = np.mean(arr)
            std = np.std(arr) if np.std(arr) > 0 else 1

            for i, d in enumerate(data):
                z = (values[i] - mean) / std
                is_anomaly_z = abs(z) > 2.0

                if HAS_SKLEARN:
                    is_anomaly_iso = iso_labels[i] == -1
                    is_anomaly = is_anomaly_z or is_anomaly_iso
                else:
                    is_anomaly = is_anomaly_z

                if abs(z) > 3:
                    severity = "CRITICAL"
                elif abs(z) > 2.5:
                    severity = "HIGH"
                elif abs(z) > 2:
                    severity = "MEDIUM"
                else:
                    severity = "LOW"

                if is_anomaly:
                    total_anomalies += 1
                    direction = "above" if z > 0 else "below"
                    desc = (f"{metric_name} is {abs(z):.1f} std devs {direction} mean "
                            f"(value={values[i]:.2f}, mean={mean:.2f})")
                else:
                    desc = None

                cur.execute("""
                    INSERT INTO ml_anomaly
                    (cycle_code, metric_name, metric_value, expected_value,
                     z_score, is_anomaly, severity, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    d["cycle_code"], metric_name, float(values[i]), float(mean),
                    float(z), bool(is_anomaly), severity if bool(is_anomaly) else "LOW",
                    str(desc) if desc else None,
                ))

    conn.commit()
    elapsed = int((time.time() - start) * 1000)
    print(f"  Metrics monitored: {len(metrics)}")
    print(f"  Cycles analyzed: {len(data)}")
    print(f"  Anomalies found: {total_anomalies}")
    method = "Isolation Forest + Z-score" if HAS_SKLEARN else "Z-score"
    print(f"  Method: {method}")
    print(f"  ✓ Anomaly detection complete ({elapsed}ms)")
    return total_anomalies, elapsed


# ================================================================
# 3. CHURN PREDICTION
# ================================================================

def predict_churn(conn):
    """
    Predict churn rate dynamically based on historical patterns.
    Uses contract lifecycle features to estimate future cancellations.
    """
    print("\n" + "─" * 60)
    print("  📉 ML Churn Prediction")
    print("─" * 60)

    start = time.time()

    # Historical churn data by month
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT bc.cycle_code, bc.cycle_month,
                   COUNT(DISTINCT CASE WHEN c.status IN ('CANCELLED','EXPIRED')
                         AND c.end_date BETWEEN bc.start_date AND bc.end_date
                         THEN c.contract_id END) AS cancellations,
                   COUNT(DISTINCT CASE WHEN c.start_date <= bc.end_date
                         AND (c.end_date IS NULL OR c.end_date >= bc.start_date)
                         AND c.status IN ('ACTIVE','SUSPENDED')
                         THEN c.contract_id END) AS active_contracts
            FROM billing_cycle bc
            CROSS JOIN contract c
            GROUP BY bc.cycle_code, bc.cycle_month, bc.start_date, bc.end_date
            ORDER BY bc.cycle_code
        """)
        data = cur.fetchall()

    if len(data) < 6:
        print("  ⚠ Not enough data for churn prediction")
        return

    # Calculate actual churn rates
    churn_rates = []
    for d in data:
        active = max(d["active_contracts"], 1)
        rate = d["cancellations"] / active
        churn_rates.append(rate)

    churn_arr = np.array(churn_rates)
    months = np.arange(1, len(data) + 1).reshape(-1, 1)

    if HAS_SKLEARN:
        # Polynomial regression for churn trend
        poly = PolynomialFeatures(degree=2)
        X_poly = poly.fit_transform(months)
        model = LinearRegression()
        model.fit(X_poly, churn_arr)
        fitted = model.predict(X_poly)
    else:
        mean_churn = np.mean(churn_arr)
        fitted = np.full_like(churn_arr, mean_churn)

    # Clear old predictions
    with conn.cursor() as cur:
        cur.execute("TRUNCATE ml_churn_prediction")

    # Save historical + predictions
    with conn.cursor() as cur:
        # Historical
        for i, d in enumerate(data):
            active = max(d["active_contracts"], 1)
            cur.execute("""
                INSERT INTO ml_churn_prediction
                (cycle_code, actual_churn_rate, predicted_churn_rate,
                 active_contracts, predicted_cancellations, risk_revenue,
                 model_type, is_future)
                VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE)
            """, (
                d["cycle_code"],
                float(churn_rates[i]),
                float(fitted[i]),
                active,
                int(fitted[i] * active),
                None,  # Will calculate for future
                "polynomial_regression" if HAS_SKLEARN else "mean",
            ))

        # Future 6 months
        last_active = data[-1]["active_contracts"]
        avg_ticket_row = None
        with conn.cursor(cursor_factory=RealDictCursor) as cur2:
            cur2.execute("SELECT AVG(total_amount) AS avg FROM invoice")
            avg_ticket_row = cur2.fetchone()
        avg_ticket = float(avg_ticket_row["avg"]) if avg_ticket_row else 100

        print(f"\n  Future churn predictions (6 months):")
        for i in range(1, 7):
            future_month = len(data) + i
            if HAS_SKLEARN:
                X_f = poly.transform([[future_month]])
                pred_rate = max(0, min(model.predict(X_f)[0], 0.15))
            else:
                pred_rate = np.mean(churn_arr)

            proj_active = int(last_active * (1 - pred_rate) ** i)
            pred_cancel = int(proj_active * pred_rate)
            risk = pred_cancel * avg_ticket

            proj_month = data[-1]["cycle_month"] + i
            proj_year = 2025
            if proj_month > 12:
                proj_month -= 12
                proj_year += 1
            cycle_code = f"{proj_year}-{proj_month:02d}"

            cur.execute("""
                INSERT INTO ml_churn_prediction
                (cycle_code, predicted_churn_rate, active_contracts,
                 predicted_cancellations, risk_revenue, model_type, is_future)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            """, (
                cycle_code, float(pred_rate), proj_active,
                pred_cancel, float(risk),
                "polynomial_regression" if HAS_SKLEARN else "mean",
            ))

            print(f"    {cycle_code}: churn={pred_rate*100:.2f}%  "
                  f"cancel=~{pred_cancel}  risk=${risk:,.0f}")

    conn.commit()
    elapsed = int((time.time() - start) * 1000)
    print(f"\n  ✓ Churn prediction complete ({elapsed}ms)")
    return float(np.mean(churn_arr)), elapsed


# ================================================================
# MAIN
# ================================================================

def main():
    print("=" * 60)
    print("  🤖 RA-PoC ML Engine")
    print("=" * 60)

    if HAS_SKLEARN:
        import sklearn
        print(f"  scikit-learn: {sklearn.__version__}")
    else:
        print("  scikit-learn: NOT AVAILABLE (using fallbacks)")

    conn = connect_db()
    total_start = time.time()

    try:
        # 1. Revenue Forecasting
        forecast_result = forecast_revenue(conn)

        # 2. Anomaly Detection
        anomaly_result = detect_anomalies(conn)

        # 3. Churn Prediction
        churn_result = predict_churn(conn)

        # Save model run metadata
        total_elapsed = int((time.time() - total_start) * 1000)
        metrics = {
            "forecast_mape": forecast_result[0] if forecast_result else None,
            "anomalies_found": anomaly_result[0] if anomaly_result else None,
            "avg_churn_rate": churn_result[0] if churn_result else None,
        }

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ml_model_run (model_name, model_version, training_cycles, metrics, duration_ms)
                VALUES (%s, %s, %s, %s, %s)
            """, ("ra_ml_pipeline", "1.0", 12,
                  json.dumps(metrics), total_elapsed))
        conn.commit()

        print(f"\n{'=' * 60}")
        print(f"  ✅ ML Pipeline Complete")
        print(f"{'=' * 60}")
        print(f"  Total time: {total_elapsed}ms")
        print(f"  Forecast MAPE: {metrics['forecast_mape']:.2f}%" if metrics['forecast_mape'] else "")
        print(f"  Anomalies: {metrics['anomalies_found']}")
        print(f"  Avg Churn: {metrics['avg_churn_rate']*100:.2f}%" if metrics['avg_churn_rate'] else "")
        print(f"{'=' * 60}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
