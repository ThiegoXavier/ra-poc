#!/bin/bash
# ============================================================
# RA-PoC — Full From-Scratch Setup (host-based pipeline)
# Assumes: K3s running, kubectl working, Python 3.12, psql client
# Run from ~/ra-poc:  ./setup.sh
# ============================================================
set -e

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
cd "$(dirname "$0")"
PGHOST=localhost; PGPORT=30432; PGDB=ra_billing; PGUSER=ra_admin
export PGPASSWORD=ra_poc_2024
PSQL="psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDB"

echo "============================================"
echo "  RA-PoC — Full Setup"
echo "============================================"

echo ""
echo "============================================"
echo "[6/6] Deploying PostgreSQL..."
echo "============================================"

echo ""
echo "[1/6] Namespace + PostgreSQL..."
kubectl get namespace ra-poc >/dev/null 2>&1 || kubectl create namespace ra-poc
kubectl apply -f k8s/postgres.yaml
kubectl rollout status deployment/postgres -n ra-poc --timeout=180s

echo ""
echo "[2/6] Waiting for PostgreSQL to accept connections..."
for i in $(seq 1 30); do
  if $PSQL -c "SELECT 1" >/dev/null 2>&1; then echo "  ✓ DB ready"; break; fi
  sleep 3
done

echo ""
echo "[3/6] Creating schema (17 tables)..."
$PSQL -f database/schema.sql
$PSQL -f database/ml_schema.sql
$PSQL -f database/ml_v2_schema.sql
TABLES=$($PSQL -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';" | tr -d ' ')
echo "  ✓ Tables created: $TABLES (expected 17)"

echo ""
echo "[4/6] Generating data..."
cd data-generator
python3 -m venv venv && source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
python generate.py
deactivate
cd ..

echo ""
echo "[5/6] Running RA Engine..."
cd ra-engine
source ../data-generator/venv/bin/activate
pip install -q -r requirements.txt
python engine.py
deactivate
cd ..

echo ""
echo "[6/6] Running ML (v1 + v2)..."
cd ra-ml
source ../data-generator/venv/bin/activate
pip install -q -r requirements.txt
pip install -q torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
python ml_engine.py
python ml_engine_v2.py
deactivate
cd ..

echo ""
echo "============================================"
echo "[7/7] Deploying Grafana..."
echo "============================================"

echo ""
echo "[1/4] Creating ConfigMaps..."

# Datasource
kubectl create configmap grafana-datasources \
  --from-file=datasource.yml=grafana/provisioning/datasources/datasource.yml \
  -n ra-poc --dry-run=client -o yaml | kubectl apply -f -

# Dashboard provider
kubectl create configmap grafana-dashboard-providers \
  --from-file=dashboards.yml=grafana/provisioning/dashboards/dashboards.yml \
  -n ra-poc --dry-run=client -o yaml | kubectl apply -f -

# Dashboard JSONs (all 6 in one configmap)
kubectl create configmap grafana-dashboards \
  --from-file=grafana/dashboards/ \
  -n ra-poc --dry-run=client -o yaml | kubectl apply -f -

echo "✓ ConfigMaps created"

echo ""
echo "[2/4] Applying Grafana manifests..."
kubectl apply -f k8s/grafana.yml
echo "✓ PVC, Deployment, Service applied"

echo ""
echo "[3/4] Waiting for Grafana to be ready..."
kubectl rollout status deployment/grafana -n ra-poc --timeout=120s
kubectl port-forward -n ra-poc svc/grafana 30300:3000 &
echo "✓ Grafana is running"

echo ""
echo "[4/4] Status..."
kubectl get pods -n ra-poc -l app=grafana
kubectl get svc grafana -n ra-poc

echo ""
echo "============================================"
echo "  ✅ Setup Complete!"
echo "============================================"
echo ""
echo "  Validation:"
echo "    Invoices:  $($PSQL -t -c 'SELECT COUNT(*) FROM invoice;' | tr -d ' ')"
echo "    RA checks: $($PSQL -t -c 'SELECT COUNT(*) FROM ra_result;' | tr -d ' ')"
echo "    Forecasts: $($PSQL -t -c 'SELECT COUNT(*) FROM ml_revenue_forecast;' | tr -d ' ')"
echo ""
echo "  URL:      http://localhost:30300"
echo "  User:     admin"
echo "  Password: ra_poc_2024"
echo ""
echo "  Dashboards:"
echo "    🏠 Overview          /d/ra-overview"
echo "    🔍 RA Controls       /d/ra-controls"
echo "    ⚠️ Gaps              /d/ra-gaps"
echo "    📦 By Offer          /d/ra-by-offer"
echo "    📈 Projections       /d/ra-projections"
echo "    👤 Customers         /d/ra-customers"
echo "    🤖 ML Insights       /d/ra-ml-insights"
echo "    🗂️ Offers & Rules    /d/ra-offers-rules"
echo "    🗂️ Contracts & Rules /d/ra-customer-contracts"
echo "============================================"

