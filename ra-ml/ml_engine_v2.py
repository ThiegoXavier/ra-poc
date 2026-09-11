#!/usr/bin/env python3
"""
RA-PoC ML Engine v2 — Advanced Models
  - Autoencoder anomaly detection (PyTorch)
  - NLP justification classification (TF-IDF + KMeans + heuristics)
"""

import os
import sys
import time
import json
import warnings
import re
from collections import Counter
from datetime import datetime

import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor

warnings.filterwarnings("ignore")

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "30432")),
    "dbname": os.environ.get("DB_NAME", "ra_billing"),
    "user": os.environ.get("DB_USER", "ra_admin"),
    "password": os.environ.get("DB_PASSWORD", "ra_poc_2024"),
}

# Check for torch availability
try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

# Check for sklearn
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


def connect_db():
    return psycopg2.connect(**DB_CONFIG)


# ================================================================
# 1. AUTOENCODER ANOMALY DETECTION
# ================================================================

class BillingAutoencoder(nn.Module):
    """Autoencoder that learns 'normal' billing patterns.
    High reconstruction error = anomaly."""

    def __init__(self, input_dim, encoding_dim=4):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 8),
            nn.ReLU(),
            nn.Linear(8, encoding_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(encoding_dim, 8),
            nn.ReLU(),
            nn.Linear(8, 16),
            nn.ReLU(),
            nn.Linear(16, input_dim),
        )

    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded


def run_autoencoder(conn):
    """Train autoencoder on billing metrics and detect anomalies."""
    print("\n" + "-" * 60)
    print("  🧠 Autoencoder Anomaly Detection")
    print("-" * 60)

    start = time.time()

    if not HAS_TORCH:
        print("  ⚠ PyTorch not available. Using fallback (MSE-based).")

    # Load features per cycle
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT bc.cycle_code,
                   SUM(i.total_amount) AS revenue,
                   COUNT(DISTINCT i.customer_id) AS customers,
                   AVG(i.total_amount) AS avg_ticket,
                   STDDEV(i.total_amount) AS std_ticket,
                   COUNT(i.*) AS invoice_count,
                   SUM(ii.discount_amount) AS total_discounts,
                   SUM(ii.base_amount) AS total_base,
                   COALESCE(SUM(CASE WHEN r.status LIKE 'GAP_%%' THEN 1 ELSE 0 END), 0) AS gap_count,
                   COALESCE(SUM(ABS(COALESCE(r.difference, 0))), 0) AS gap_value
            FROM billing_cycle bc
            JOIN invoice i ON i.cycle_id = bc.cycle_id
            JOIN invoice_item ii ON ii.invoice_id = i.invoice_id
            LEFT JOIN ra_run rr ON rr.cycle_id = bc.cycle_id
            LEFT JOIN ra_result r ON r.run_id = rr.run_id
            GROUP BY bc.cycle_code
            ORDER BY bc.cycle_code
        """)
        data = cur.fetchall()

    if len(data) < 6:
        print("  ⚠ Not enough cycles for autoencoder training")
        return 0, 0

    # Build feature matrix
    feature_names = ["revenue", "customers", "avg_ticket", "std_ticket",
                     "invoice_count", "total_discounts", "total_base",
                     "gap_count", "gap_value"]
    X_raw = []
    for d in data:
        row = [float(d[f] or 0) for f in feature_names]
        X_raw.append(row)
    X_raw = np.array(X_raw, dtype=np.float32)

    # Normalize
    scaler = StandardScaler() if HAS_SKLEARN else None
    if scaler:
        X_norm = scaler.fit_transform(X_raw).astype(np.float32)
    else:
        mean = X_raw.mean(axis=0)
        std = X_raw.std(axis=0) + 1e-8
        X_norm = ((X_raw - mean) / std).astype(np.float32)

    input_dim = X_norm.shape[1]

    if HAS_TORCH:
        # Train autoencoder
        model = BillingAutoencoder(input_dim, encoding_dim=4)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        criterion = nn.MSELoss(reduction='none')

        X_tensor = torch.FloatTensor(X_norm)

        # Training loop
        model.train()
        for epoch in range(200):
            optimizer.zero_grad()
            reconstructed = model(X_tensor)
            loss = criterion(reconstructed, X_tensor).mean()
            loss.backward()
            optimizer.step()

        # Compute reconstruction errors
        model.eval()
        with torch.no_grad():
            reconstructed = model(X_tensor)
            errors = criterion(reconstructed, X_tensor).mean(dim=1).numpy()

        model_type = "autoencoder_pytorch"
        print(f"  Model: PyTorch Autoencoder ({input_dim}→16→8→4→8→16→{input_dim})")
        print(f"  Training epochs: 200")
        print(f"  Final loss: {loss.item():.6f}")
    else:
        # Fallback: compute MSE from mean pattern
        mean_pattern = X_norm.mean(axis=0)
        errors = np.mean((X_norm - mean_pattern) ** 2, axis=1)
        model_type = "mse_fallback"
        print(f"  Model: MSE Fallback (no PyTorch)")

    # Threshold: mean + 2*std of errors
    threshold = float(errors.mean() + 2 * errors.std())
    anomalies_found = 0

    # Clear old results
    with conn.cursor() as cur:
        cur.execute("TRUNCATE ml_autoencoder_anomaly")

    # Save results
    with conn.cursor() as cur:
        for i, d in enumerate(data):
            err = float(errors[i])
            is_anom = err > threshold
            ratio = err / threshold if threshold > 0 else 0

            if is_anom:
                anomalies_found += 1
                # Find which features contributed most
                if HAS_TORCH:
                    with torch.no_grad():
                        per_feature = criterion(
                            model(X_tensor[i:i+1]),
                            X_tensor[i:i+1]
                        ).squeeze().numpy()
                    top_feat_idx = np.argsort(per_feature)[-3:][::-1]
                else:
                    per_feature = (X_norm[i] - X_norm.mean(axis=0)) ** 2
                    top_feat_idx = np.argsort(per_feature)[-3:][::-1]

                top_feats = [feature_names[j] for j in top_feat_idx]
                desc = f"Anomaly: top deviating features: {', '.join(top_feats)} (error={err:.4f}, threshold={threshold:.4f})"
            else:
                desc = None

            cur.execute("""
                INSERT INTO ml_autoencoder_anomaly
                (cycle_code, reconstruction_error, threshold, is_anomaly,
                 error_ratio, features_used, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                d["cycle_code"], err, threshold, bool(is_anom),
                float(ratio), ", ".join(feature_names),
                desc,
            ))

    conn.commit()
    elapsed = int((time.time() - start) * 1000)

    print(f"  Features: {input_dim} ({', '.join(feature_names[:5])}...)")
    print(f"  Threshold: {threshold:.6f}")
    print(f"  Anomalies: {anomalies_found} / {len(data)} cycles")
    print(f"  ✓ Autoencoder complete ({elapsed}ms)")

    return anomalies_found, elapsed


# ================================================================
# 2. NLP JUSTIFICATION CLASSIFICATION
# ================================================================

# Category rules (pattern-based + embedding clustering)
CATEGORY_PATTERNS = {
    "OVERCHARGE": [
        r"overcharged",
        r"overcharge",
        r"charged.*more",
        r"above",
    ],
    "UNDERCHARGE": [
        r"undercharged",
        r"undercharge",
        r"charged.*less",
        r"below",
    ],
    "MISSING_CHARGE": [
        r"not billed",
        r"active contract not",
        r"missing",
        r"no charge",
    ],
    "DUPLICATE": [
        r"duplicate charge",
        r"duplicate",
        r"\bdup\b",
        r"\[dup\]",
    ],
    "ROUNDING": [
        r"rounding",
        r"rounding difference",
    ],
    "BILLING_MATCH": [
        r"values match",
        r"^match$",
        r"correct",
        r"no discounts",
    ],
}

SUGGESTED_ACTIONS = {
    "DISCOUNT_NOT_APPLIED": "Review pricing rules engine — ensure loyalty/promo discounts trigger correctly",
    "OVERCHARGE": "Issue credit note and investigate billing rule configuration",
    "UNDERCHARGE": "Review if promotional period expired — adjust next cycle",
    "MISSING_CHARGE": "Check contract activation status and billing trigger conditions",
    "DUPLICATE": "Remove duplicate charge and add dedup validation to billing pipeline",
    "ROUNDING": "No action needed — within tolerance",
    "BILLING_MATCH": "No action needed — billing correct",
    "UNCATEGORIZED": "Manual review required — pattern not recognized",
}


def classify_text(text):
    """Classify justification text using regex patterns."""
    if not text:
        return "UNCATEGORIZED", None, 0.0

    text_lower = text.lower()

    scores = {}
    for category, patterns in CATEGORY_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, text_lower):
                score += 1
        if score > 0:
            scores[category] = score

    if scores:
        best = max(scores, key=scores.get)
        confidence = min(scores[best] / len(CATEGORY_PATTERNS[best]), 1.0)
        return best, SUGGESTED_ACTIONS.get(best), confidence

    return "UNCATEGORIZED", SUGGESTED_ACTIONS["UNCATEGORIZED"], 0.0


def run_nlp_classification(conn):
    """Classify RA justification texts using TF-IDF + KMeans + pattern matching."""
    print("\n" + "-" * 60)
    print("  📝 NLP Justification Classification")
    print("-" * 60)

    start = time.time()

    # Load all RA results with justifications
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT r.result_id, r.status, r.justification,
                   r.expected_amount, r.billed_amount, r.difference,
                   o.offer_name
            FROM ra_result r
            JOIN contract ct ON ct.contract_id = r.contract_id
            JOIN offer o ON o.offer_id = ct.offer_id
            WHERE r.justification IS NOT NULL AND r.justification != ''
        """)
        results = cur.fetchall()

    if not results:
        print("  ⚠ No justifications to classify")
        return 0, 0

    print(f"  Texts to classify: {len(results)}")

    # Phase 1: Pattern-based classification
    classifications = []
    texts = []
    for r in results:
        cat, action, conf = classify_text(r["justification"])
        classifications.append({
            "result_id": r["result_id"],
            "text": r["justification"],
            "category": cat,
            "confidence": conf,
            "action": action,
            "offer": r["offer_name"],
        })
        texts.append(r["justification"])

    # Phase 2: TF-IDF + KMeans clustering to discover hidden patterns
    cluster_labels = None
    n_clusters = min(7, len(set(texts)))

    if HAS_SKLEARN and len(texts) >= n_clusters:
        try:
            vectorizer = TfidfVectorizer(
                max_features=100,
                stop_words="english",
                ngram_range=(1, 2),
            )
            X_tfidf = vectorizer.fit_transform(texts)

            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(X_tfidf)

            print(f"  TF-IDF features: {X_tfidf.shape[1]}")
            print(f"  KMeans clusters: {n_clusters}")

            # Top terms per cluster
            feature_names = vectorizer.get_feature_names_out()
            for ci in range(n_clusters):
                center = kmeans.cluster_centers_[ci]
                top_idx = center.argsort()[-5:][::-1]
                top_terms = [feature_names[j] for j in top_idx]
                cluster_count = sum(1 for l in cluster_labels if l == ci)
                print(f"    Cluster {ci} ({cluster_count} items): {', '.join(top_terms)}")
        except Exception as e:
            print(f"  ⚠ KMeans failed: {e}")
            cluster_labels = None

    # Clear old results
    with conn.cursor() as cur:
        cur.execute("TRUNCATE ml_nlp_classification, ml_nlp_category_summary")

    # Save classifications
    with conn.cursor() as cur:
        for i, c in enumerate(classifications):
            cluster = int(cluster_labels[i]) if cluster_labels is not None else None
            cur.execute("""
                INSERT INTO ml_nlp_classification
                (result_id, original_text, category, confidence,
                 embedding_cluster, suggested_action)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                c["result_id"], c["text"], c["category"],
                float(c["confidence"]), cluster, c["action"],
            ))

    # Generate category summary
    category_counts = Counter(c["category"] for c in classifications)
    category_values = {}
    category_offers = {}

    for c, r in zip(classifications, results):
        cat = c["category"]
        val = abs(float(r["difference"] or r["expected_amount"] or 0))
        if cat not in category_values:
            category_values[cat] = 0
            category_offers[cat] = Counter()
        category_values[cat] += val
        category_offers[cat][c["offer"]] += 1

    with conn.cursor() as cur:
        for cat, count in category_counts.most_common():
            confidences = [c["confidence"] for c in classifications if c["category"] == cat]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            top_offers = ", ".join(
                f"{o} ({c})" for o, c in category_offers.get(cat, Counter()).most_common(3)
            )
            cur.execute("""
                INSERT INTO ml_nlp_category_summary
                (category, total_count, total_value, avg_confidence,
                 top_offers, suggested_action)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                cat, count, float(category_values.get(cat, 0)),
                float(avg_conf), top_offers,
                SUGGESTED_ACTIONS.get(cat, "Manual review"),
            ))

    conn.commit()
    elapsed = int((time.time() - start) * 1000)

    print(f"\n  Classification results:")
    for cat, count in category_counts.most_common():
        val = category_values.get(cat, 0)
        print(f"    {cat:30s}  {count:>5} items  ${val:>12,.2f}")

    total_classified = sum(1 for c in classifications if c["category"] != "UNCATEGORIZED")
    total = len(classifications)
    print(f"\n  Classified: {total_classified}/{total} ({total_classified*100/total:.1f}%)")
    print(f"  ✓ NLP classification complete ({elapsed}ms)")

    return len(category_counts), elapsed


# ================================================================
# MAIN
# ================================================================

def main():
    print("=" * 60)
    print("  🤖 RA-PoC ML Engine v2 — Advanced Models")
    print("=" * 60)
    print(f"  PyTorch: {'✓ ' + torch.__version__ if HAS_TORCH else '✗ (using MSE fallback)'}")
    print(f"  scikit-learn: {'✓' if HAS_SKLEARN else '✗ (limited NLP)'}")

    conn = connect_db()
    total_start = time.time()

    try:
        # 1. Autoencoder
        ae_anomalies, ae_time = run_autoencoder(conn)

        # 2. NLP Classification
        nlp_categories, nlp_time = run_nlp_classification(conn)

        # Save run metadata
        total_elapsed = int((time.time() - total_start) * 1000)
        metrics = {
            "autoencoder_anomalies": ae_anomalies,
            "autoencoder_time_ms": ae_time,
            "nlp_categories": nlp_categories,
            "nlp_time_ms": nlp_time,
            "has_torch": HAS_TORCH,
        }

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ml_model_run
                (model_name, model_version, training_cycles, metrics, duration_ms)
                VALUES (%s, %s, %s, %s, %s)
            """, ("ra_ml_v2_advanced", "2.0", 12,
                  json.dumps(metrics), total_elapsed))
        conn.commit()

        print(f"\n{'=' * 60}")
        print(f"  ✅ ML v2 Pipeline Complete")
        print(f"{'=' * 60}")
        print(f"  Autoencoder anomalies: {ae_anomalies}")
        print(f"  NLP categories: {nlp_categories}")
        print(f"  Total time: {total_elapsed}ms")
        print(f"{'=' * 60}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
