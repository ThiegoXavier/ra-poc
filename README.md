# Revenue Assurance PoC

Revenue Assurance Proof of Concept using **K3s, PostgreSQL, Python, Machine Learning and Grafana**.

The project simulates a telecom billing environment and provides:

- Customer and contract generation
- Offers and billing rules
- Billing cycles
- Invoices and invoice items
- Revenue Assurance controls
- Billing gap detection
- Revenue leakage calculation
- Machine Learning forecasts
- Anomaly detection
- Churn prediction
- NLP-based billing classification
- Grafana dashboards

The PoC is designed to run locally on **Windows + WSL2 + Ubuntu + K3s**.

---

# 1. Architecture

```text
                        Windows
                           │
                           │
                         WSL2
                           │
                    Ubuntu 26.04
                           │
                         K3s
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
     PostgreSQL        Grafana          Python
          │                                 │
          │                    ┌────────────┼────────────┐
          │                    │            │            │
          ▼                    ▼            ▼            ▼
     Billing Data        Data Generator  RA Engine     ML Engine
                                      │            │
                                      │            ├── ML v1
                                      │            └── ML v2
                                      │
                                      ▼
                               Revenue Assurance
```

---

# 2. Technology Stack

| Component | Technology |
|---|---|
| Operating System | Windows + WSL2 |
| Linux | Ubuntu 26.04 |
| Container Platform | K3s |
| Database | PostgreSQL |
| Programming Language | Python 3.14 |
| Data Generation | Faker |
| RA Engine | Python + NumPy |
| ML Engine | Scikit-learn |
| Deep Learning | PyTorch |
| Visualization | Grafana |
| Database Driver | psycopg2 |

---

# 3. Prerequisites

The PoC requires:

- Windows 10/11
- WSL2
- Ubuntu 26.04
- Internet access
- Administrator access on Windows
- At least 8 GB RAM recommended
- At least 20 GB free disk space

---

# 4. Install WSL

From **PowerShell as Administrator**:

```powershell
wsl --install
```

If a specific Ubuntu distribution is required:

```powershell
wsl --install -d Ubuntu-26.04
```

Check the installed distributions:

```powershell
wsl --list --verbose
```

Expected example:

```text
NAME            STATE           VERSION
Ubuntu-26.04    Running         2
```

Start Ubuntu:

```powershell
wsl -d Ubuntu-26.04
```

---

# 5. Configure systemd

K3s requires systemd.

Inside Ubuntu:

```bash
sudo tee /etc/wsl.conf > /dev/null <<'EOF'
[boot]
systemd=true
EOF
```

Exit WSL:

```bash
exit
```

From PowerShell:

```powershell
wsl --terminate Ubuntu-26.04
```

Start Ubuntu again:

```powershell
wsl -d Ubuntu-26.04
```

Validate systemd:

```bash
ps -p 1 -o pid,comm,args
```

Expected:

```text
PID COMMAND         COMMAND
  1 systemd         /sbin/init
```

Also check:

```bash
systemctl is-system-running
```

`degraded` can occur in WSL because of services that are not applicable to the WSL environment. For this PoC, the important requirement is that systemd is running as PID 1 and K3s is operational.

---

# 6. Install Base Packages

Update the system:

```bash
sudo apt update
```

Install the required packages:

```bash
sudo apt install -y \
    python3-venv \
    python3-pip \
    postgresql-client \
    curl \
    git
```

Verify Python:

```bash
python3 --version
```

Expected:

```text
Python 3.14.x
```

Verify Git:

```bash
git --version
```

Verify PostgreSQL client:

```bash
psql --version
```

---

# 7. Install K3s

Install the pinned K3s version used by this PoC:

```bash
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_VERSION="v1.36.4+k3s1" \
  sh -s - --write-kubeconfig-mode=644
```

The version is intentionally pinned to make the PoC environment reproducible.

Check K3s:

```bash
sudo systemctl status k3s
```

Check the node:

```bash
kubectl get nodes
```

Expected:

```text
NAME            STATUS   ROLES                  AGE   VERSION
<node-name>     Ready    control-plane,master   ...   v1.36.4+k3s1
```

---

# 8. Kubeconfig

For this PoC, K3s is configured to create the kubeconfig with mode `644`.

The kubeconfig is located at:

```text
/etc/rancher/k3s/k3s.yaml
```

Set:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
```

To make it persistent:

```bash
echo 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' >> ~/.bashrc
```

Reload:

```bash
source ~/.bashrc
```

Validate:

```bash
kubectl get nodes
```

> **Security note:** `644` is convenient for this local PoC. A production environment should use a user-owned kubeconfig with restrictive permissions.

---

# 9. Project Directory

The project directory is:

```text
~/ra_poc
```

Create it if necessary:

```bash
mkdir -p ~/ra_poc
cd ~/ra_poc
```

The `~` automatically refers to the current Linux user's home directory, so no username is hardcoded.

---

# 10. Project Structure

```text
ra_poc/
│
├── setup.sh
│
├── k8s/
│   ├── postgres.yaml
│   └── grafana.yml
│
├── database/
│   ├── schema.sql
│   ├── ml_schema.sql
│   └── ml_v2_schema.sql
│
├── data-generator/
│   ├── requirements.txt
│   └── generate.py
│
├── ra-engine/
│   ├── requirements.txt
│   └── engine.py
│
├── ra-ml/
│   ├── requirements.txt
│   ├── ml_engine.py
│   └── ml_engine_v2.py
│
└── grafana/
    │
    ├── provisioning/
    │   ├── datasources/
    │   │   └── datasource.yml
    │   │
    │   └── dashboards/
    │       └── dashboards.yml
    │
    └── dashboards/
        ├── ra-overview.json
        ├── ra-controls.json
        ├── ra-gaps.json
        ├── ra-by-offer.json
        ├── ra-projections.json
        ├── ra-customers.json
        ├── ra-ml-insights.json
        ├── ra-offers-rules.json
        └── ra-customer-contracts.json
```

---

# 11. Database

The PoC uses PostgreSQL running inside K3s.

Database configuration:

```text
Host:     localhost
Port:     30432
Database: ra_billing
User:     ra_admin
```

The PoC password is:

```text
ra_poc_2024
```

> This password is for demonstration purposes only and must not be used in production.

---

# 12. Database Schema

The database is initialized using:

```text
database/schema.sql
database/ml_schema.sql
database/ml_v2_schema.sql
```

The schemas create the required tables for:

- Customers
- Contracts
- Offers
- Billing rules
- Billing cycles
- Invoices
- Invoice items
- Revenue Assurance controls
- Revenue gaps
- ML forecasts
- ML anomalies
- ML classifications
- Other supporting entities

The validated PoC environment creates:

```text
17 tables
```

---

# 13. Data Generator

The data generator creates a realistic telecom billing dataset.

Location:

```text
data-generator/
```

Requirements:

```text
psycopg2-binary==2.9.12
faker==25.0.0
```

A Python virtual environment is created using:

```bash
python3 -m venv venv
```

Activate it:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python generate.py
```

The generator creates:

- 20 offers
- 32 billing rules
- 1,000 customers
- 1,772 contracts
- 12 billing cycles
- 11,779 invoices
- 20,853 invoice items

It also intentionally introduces billing gaps to simulate Revenue Assurance scenarios.

Validated execution:

```text
Offers:      20
Rules:       32
Customers:   1000
Contracts:   1772
Cycles:      12
Invoices:    11779
Items:       20853

Total Billed: R$ 1,577,800.80

Intentional gaps: 618
```

---

# 14. Python Virtual Environments

Each Python component uses an isolated virtual environment.

For example:

```bash
cd ~/ra_poc/data-generator
python3 -m venv venv
source venv/bin/activate
```

The virtual environment prevents project dependencies from being installed globally.

If the project directory is moved or renamed, an existing virtual environment can become invalid because Python virtual environments contain references to the original path.

For example, moving:

```text
~/ra_poc
```

to:

```text
~/ra-poc
```

can result in:

```text
bad interpreter: No such file or directory
```

In that situation, recreate the environment:

```bash
cd ~/ra_poc/data-generator

rm -rf venv

python3 -m venv venv

source venv/bin/activate

pip install --upgrade pip

pip install -r requirements.txt
```

---

# 15. Revenue Assurance Engine

The Revenue Assurance engine is located at:

```text
ra-engine/
```

Requirements:

```text
psycopg2-binary==2.9.12
numpy==2.5.3
```

Run:

```bash
cd ~/ra_poc/ra-engine

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

python engine.py
```

The engine validates billing against expected revenue and billing rules.

It identifies:

```text
GAP_OVERCHARGE
GAP_UNDERCHARGE
GAP_MISSING
```

---

# 16. Revenue Assurance Results

Validated PoC execution:

```text
Total checks:       20,848
Total MATCH:        20,230
Total JUSTIFIED:         0
Total GAPS:            618

Expected Revenue: R$   1,576,503.40
Billed Revenue:   R$   1,577,800.80
Total Gap Value:  R$      61,344.67

Revenue Leakage:       3.89%
```

Control distribution:

```text
MATCH:       20,230
GAPS:           618
```

This demonstrates the basic Revenue Assurance workflow:

```text
Expected Billing
       │
       ▼
Actual Billing
       │
       ▼
Comparison
       │
       ├── MATCH
       │
       └── GAP
             │
             ├── OVERCHARGE
             ├── UNDERCHARGE
             └── MISSING
```

---

# 17. Machine Learning Engine

The ML implementation is located at:

```text
ra-ml/
```

Requirements:

```text
psycopg2-binary==2.9.12
numpy==2.5.3
scikit-learn==1.9.0
```

The PoC contains two ML implementations.

---

# 18. ML Engine V1

The first ML engine uses:

- Scikit-learn
- Gradient Boosting
- Isolation Forest
- Z-score analysis
- Revenue forecasting
- Churn prediction

Run:

```bash
cd ~/ra_poc/ra-ml

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

PyTorch can be installed separately if required:

```bash
pip install -q torch==2.14.0 \
  --index-url https://download.pytorch.org/whl/cpu
```

Run:

```bash
python ml_engine.py
```

Validated results:

```text
scikit-learn: 1.9.0

Training MAPE: 0.00%

Model:
GradientBoosting

Cycles analyzed:
12

Anomalies found:
10
```

---

# 19. Revenue Forecast

The ML engine generates future revenue projections.

Example:

```text
2026-01: $241,307.21
2026-02: $241,307.21
2026-03: $241,307.21
2026-04: $241,307.21
2026-05: $241,307.21
2026-06: $241,307.21
```

The model also generates prediction intervals.

Example:

```text
$241,307.21
[$241,305.86 — $241,308.56]
```

---

# 20. Churn Prediction

The ML engine also estimates customer churn.

Example output:

```text
2026-01:
Churn:   0.19%
Cancel:  ~3
Risk:    $402

2026-02:
Churn:   0.20%
Cancel:  ~3

2026-03:
Churn:   0.21%
Cancel:  ~3

2026-04:
Churn:   0.22%
Cancel:  ~3

2026-05:
Churn:   0.24%
Cancel:  ~4

2026-06:
Churn:   0.26%
Cancel:  ~4
Risk:    $536
```

---

# 21. ML Engine V2

The second ML implementation adds Deep Learning and NLP.

It uses:

- PyTorch
- Autoencoder
- TF-IDF
- KMeans
- Anomaly detection
- Billing classification

Run:

```bash
cd ~/ra_poc/ra-ml

source venv/bin/activate

python ml_engine_v2.py
```

Validated execution:

```text
PyTorch: 2.14.0
scikit-learn: available
```

---

# 22. Autoencoder

The Autoencoder architecture is:

```text
9 → 16 → 8 → 4 → 8 → 16 → 9
```

Training:

```text
Epochs:       200
Final loss:   0.031043
Threshold:    0.078528
```

Anomaly result:

```text
Anomalies:
1 / 12 cycles
```

The Autoencoder is used to detect unusual billing-cycle behavior.

---

# 23. NLP Billing Classification

The ML V2 engine analyzes billing descriptions using TF-IDF and clustering.

Validated execution:

```text
Texts to classify: 20,848
TF-IDF features:       100
KMeans clusters:         7
```

Classification results:

| Classification | Items | Value |
|---|---:|---:|
| BILLING_MATCH | 20,230 | $1,504,676.04 |
| OVERCHARGE | 168 | $4,231.68 |
| DUPLICATE | 153 | $18,059.57 |
| UNDERCHARGE | 149 | $4,286.99 |
| MISSING_CHARGE | 148 | $16,706.86 |

Total:

```text
Classified: 20,848 / 20,848
Coverage:   100%
```

---

# 24. Grafana

Grafana runs inside K3s.

Service:

```text
NodePort: 30300
```

Access:

```text
http://localhost:30300
```

Default PoC credentials:

```text
User:     admin
Password: ra_poc_2024
```

> Change the credentials before using this configuration outside the PoC environment.

---

# 25. Grafana Dashboards

The PoC provides nine dashboards.

| Dashboard | Path | Description |
|---|---|---|
| Overview | `/d/ra-overview` | Overall Revenue Assurance KPIs and billing performance |
| RA Controls | `/d/ra-controls` | Revenue Assurance control results |
| Gaps | `/d/ra-gaps` | Billing gaps and revenue leakage analysis |
| By Offer | `/d/ra-by-offer` | Revenue Assurance analysis by offer |
| Projections | `/d/ra-projections` | Revenue projections and future trends |
| Customers | `/d/ra-customers` | Customer-level Revenue Assurance information |
| ML Insights | `/d/ra-ml-insights` | Machine Learning forecasts, anomalies and churn insights |
| Offers & Rules | `/d/ra-offers-rules` | Offers and associated billing rules |
| Contracts & Rules | `/d/ra-customer-contracts` | Customer contracts and applicable rules |

Direct URLs:

```text
http://localhost:30300/d/ra-overview
http://localhost:30300/d/ra-controls
http://localhost:30300/d/ra-gaps
http://localhost:30300/d/ra-by-offer
http://localhost:30300/d/ra-projections
http://localhost:30300/d/ra-customers
http://localhost:30300/d/ra-ml-insights
http://localhost:30300/d/ra-offers-rules
http://localhost:30300/d/ra-customer-contracts
```

---

# 26. Grafana Provisioning

Grafana provisioning is configured under:

```text
grafana/provisioning/
```

Datasource:

```text
grafana/provisioning/datasources/datasource.yml
```

Dashboard provider:

```text
grafana/provisioning/dashboards/dashboards.yml
```

Dashboard JSON files:

```text
grafana/dashboards/
```

The dashboards are automatically provisioned when Grafana starts.

---

# 27. Complete Setup

The complete PoC can be deployed using:

```bash
cd ~/ra_poc

chmod +x setup.sh

./setup.sh
```

The setup script performs the complete process:

```text
1. Deploy PostgreSQL
2. Wait for PostgreSQL
3. Create database schema
4. Generate billing data
5. Run Revenue Assurance engine
6. Run Machine Learning engines
7. Deploy Grafana
```

---

# 28. Setup Validation

After execution, validate Kubernetes:

```bash
kubectl get pods -n ra-poc
```

Expected components include:

```text
postgres
grafana
```

Check services:

```bash
kubectl get svc -n ra-poc
```

Check deployments:

```bash
kubectl get deployments -n ra-poc
```

Check PostgreSQL:

```bash
kubectl get pods -n ra-poc
```

---

# 29. Database Validation

Connect to PostgreSQL:

```bash
PGPASSWORD=ra_poc_2024 \
psql \
  -h localhost \
  -p 30432 \
  -U ra_admin \
  -d ra_billing
```

Example:

```sql
SELECT COUNT(*) FROM invoices;
```

Expected:

```text
11779
```

RA controls:

```sql
SELECT COUNT(*) FROM ra_checks;
```

Expected:

```text
20848
```

Forecasts:

```sql
SELECT COUNT(*) FROM ml_forecasts;
```

Expected:

```text
18
```

Exit:

```sql
\q
```

---

# 30. Useful Kubernetes Commands

List namespaces:

```bash
kubectl get namespaces
```

List PoC resources:

```bash
kubectl get all -n ra-poc
```

List pods:

```bash
kubectl get pods -n ra-poc
```

Detailed pod information:

```bash
kubectl describe pod <pod-name> -n ra-poc
```

View PostgreSQL logs:

```bash
kubectl logs deployment/postgres -n ra-poc
```

View Grafana logs:

```bash
kubectl logs deployment/grafana -n ra-poc
```

Restart PostgreSQL:

```bash
kubectl rollout restart deployment/postgres -n ra-poc
```

Restart Grafana:

```bash
kubectl rollout restart deployment/grafana -n ra-poc
```

---

# 31. Useful K3s Commands

Check K3s:

```bash
sudo systemctl status k3s
```

Restart K3s:

```bash
sudo systemctl restart k3s
```

Check K3s logs:

```bash
sudo journalctl -u k3s -f
```

Check node:

```bash
kubectl get nodes
```

---

# 32. Recreating the Environment

If the PoC needs to be recreated from scratch:

```bash
cd ~/ra_poc
```

Remove the namespace:

```bash
kubectl delete namespace ra-poc
```

Wait until it is removed:

```bash
kubectl get namespaces
```

Then execute:

```bash
./setup.sh
```

If Python virtual environments are invalid because the project directory was moved:

```bash
rm -rf data-generator/venv
rm -rf ra-engine/venv
rm -rf ra-ml/venv
```

The setup process can recreate them.

---

# 33. Git

Initialize the repository:

```bash
cd ~/ra_poc

git init
```

Check status:

```bash
git status
```

Add files:

```bash
git add .
```

Commit:

```bash
git commit -m "Initial Revenue Assurance PoC"
```

Check branches:

```bash
git branch
```

Check remote:

```bash
git remote -v
```

---

# 34. Recommended `.gitignore`

Create:

```bash
nano .gitignore
```

Suggested content:

```text
# Python
__pycache__/
*.py[cod]
*.pyo

# Virtual environments
venv/
.venv/

# Environment files
.env

# Python cache
.pytest_cache/
.mypy_cache/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# Temporary files
*.tmp

# Local Kubernetes data
*.local.yaml
```

Do not commit passwords or production credentials.

---

# 35. Production Considerations

This project is a **Proof of Concept** and should not be considered production-ready.

Before production deployment, consider:

## Security

- Use Kubernetes Secrets
- Remove hardcoded passwords
- Use TLS
- Use RBAC
- Restrict network access
- Use secure kubeconfig permissions
- Rotate credentials
- Use external secret management

## Database

- PostgreSQL High Availability
- Persistent storage
- Backup strategy
- Point-in-time recovery
- Connection pooling
- Monitoring

## Kubernetes

- Multiple nodes
- Resource limits
- Resource requests
- Pod disruption budgets
- Network policies
- Ingress
- TLS certificates

## Observability

- Prometheus
- Grafana
- Centralized logging
- Alerting
- Distributed tracing

## Machine Learning

- Model registry
- Feature engineering pipeline
- Model versioning
- Model monitoring
- Data drift detection
- Model drift detection
- Automated retraining

---

# 36. End-to-End Data Flow

The complete PoC follows this flow:

```text
                    ┌──────────────────┐
                    │  Data Generator  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   PostgreSQL     │
                    │                  │
                    │ Customers        │
                    │ Contracts        │
                    │ Offers           │
                    │ Rules            │
                    │ Invoices         │
                    │ Invoice Items    │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   RA Engine      │
                    └────────┬─────────┘
                             │
                    ┌────────┴─────────┐
                    │                  │
                    ▼                  ▼
                 MATCH                GAP
                                       │
                       ┌───────────────┼───────────────┐
                       │               │               │
                       ▼               ▼               ▼
                   OVERCHARGE     UNDERCHARGE      MISSING
                       │               │               │
                       └───────────────┼───────────────┘
                                       │
                                       ▼
                              Revenue Leakage
                                       │
                                       ▼
                            ┌──────────────────┐
                            │   ML Engine      │
                            │                  │
                            │ Forecasting      │
                            │ Anomaly Detection│
                            │ Churn Prediction │
                            │ NLP              │
                            └────────┬─────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │     Grafana      │
                            │                  │
                            │ KPIs             │
                            │ Gaps             │
                            │ Forecasts        │
                            │ Customers        │
                            │ ML Insights      │
                            └──────────────────┘
```

---

# 37. Validated PoC Results

The complete environment was successfully validated with:

```text
Customers:              1,000
Contracts:              1,772
Offers:                    20
Rules:                     32
Billing Cycles:            12
Invoices:              11,779
Invoice Items:         20,853

RA Checks:             20,848
Matches:               20,230
Gaps:                     618

Expected Revenue:  R$ 1,576,503.40
Billed Revenue:    R$ 1,577,800.80
Gap Value:         R$    61,344.67

Revenue Leakage:          3.89%

ML Forecasts:              18
ML Anomalies:                1 / 12 cycles
NLP Classification:       20,848 / 20,848
```

Grafana:

```text
URL:
http://localhost:30300

Dashboards:
9
```

---

# 38. Quick Start

For an already configured WSL/K3s environment:

```bash
cd ~/ra_poc

chmod +x setup.sh

./setup.sh
```

Then open:

```text
http://localhost:30300
```

Login:

```text
User:     admin
Password: ra_poc_2024
```

Main dashboard:

```text
http://localhost:30300/d/ra-overview
```

---

# 39. Quick Troubleshooting

## K3s is not running

```bash
sudo systemctl status k3s
```

If necessary:

```bash
sudo systemctl restart k3s
```

---

## kubectl cannot connect

Check:

```bash
echo $KUBECONFIG
```

Expected:

```text
/etc/rancher/k3s/k3s.yaml
```

Then:

```bash
kubectl get nodes
```

---

## Kubeconfig permission denied

For the PoC:

```bash
sudo chmod 644 /etc/rancher/k3s/k3s.yaml
```

Then:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
```

---

## Python virtual environment error

If you see:

```text
bad interpreter: No such file or directory
```

recreate the virtual environment:

```bash
cd ~/ra_poc/data-generator

rm -rf venv

python3 -m venv venv

source venv/bin/activate

pip install -r requirements.txt
```

---

## PostgreSQL is not ready

Check:

```bash
kubectl get pods -n ra-poc
```

Check logs:

```bash
kubectl logs deployment/postgres -n ra-poc
```

---

## Grafana is not available

Check:

```bash
kubectl get pods -n ra-poc
```

Then:

```bash
kubectl get svc -n ra-poc
```

Check logs:

```bash
kubectl logs deployment/grafana -n ra-poc
```

---

# 40. Project Status

Current PoC status:

```text
WSL2                  ✓
Ubuntu 26.04          ✓
systemd               ✓
K3s                   ✓
PostgreSQL            ✓
Database Schema       ✓
Data Generator        ✓
Revenue Assurance     ✓
ML Engine V1          ✓
ML Engine V2          ✓
Grafana               ✓
Dashboards            ✓
End-to-End Validation ✓
```

The environment is ready for further development of the Revenue Assurance PoC.
