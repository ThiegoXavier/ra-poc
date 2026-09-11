# RA-PoC — Revenue Assurance Proof of Concept

A **Revenue Assurance (RA) Proof of Concept** running on **WSL2 + Ubuntu 26.04 + K3s + PostgreSQL + Python + Machine Learning + Grafana**.

The project simulates a telecommunications billing environment with customers, contracts, offers, billing cycles and invoices. It executes Revenue Assurance controls, identifies billing gaps and applies Machine Learning models for revenue forecasting, anomaly detection, churn prediction and NLP-based classification.

---

## 1. Architecture

```text
Windows
  │
  └── WSL2
       │
       └── Ubuntu 26.04
            │
            ├── K3s
            │    │
            │    ├── PostgreSQL
            │    │
            │    └── Grafana
            │
            └── Python
                 │
                 ├── Data Generator
                 ├── RA Engine
                 ├── ML Engine v1
                 └── ML Engine v2
```

### Components

| Component | Technology |
|---|---|
| Operating System | Ubuntu 26.04 |
| Runtime | WSL2 |
| Kubernetes | K3s |
| Database | PostgreSQL |
| Data Generator | Python |
| RA Engine | Python |
| ML Engine v1 | scikit-learn |
| ML Engine v2 | PyTorch + scikit-learn |
| Dashboard | Grafana |
| Database Client | PostgreSQL `psql` |

---

# 2. Prerequisites

The following components are required:

- Windows with WSL2 support
- WSL2
- Ubuntu 26.04
- Internet access
- A Linux user created during Ubuntu installation

The Linux username is intentionally **not hardcoded** in this documentation.

---

# 3. Create the WSL Distribution

From **Windows PowerShell**:

```powershell
wsl --install -d Ubuntu-26.04
```

After installation, start the distribution:

```powershell
wsl -d Ubuntu-26.04
```

During the first startup, Ubuntu will ask you to create a Linux username and password.

Use the username you want for your environment.

---

# 4. Configure systemd

K3s requires systemd for service management.

Inside Ubuntu:

```bash
sudo tee /etc/wsl.conf > /dev/null <<'EOF'
[boot]
systemd=true
EOF
```

> The Linux username is not specified in `/etc/wsl.conf`, making the configuration independent of the username created during Ubuntu installation.

Exit WSL:

```bash
exit
```

Restart the distribution from PowerShell:

```powershell
wsl --terminate Ubuntu-26.04
wsl -d Ubuntu-26.04
```

Validate systemd:

```bash
ps -p 1 -o pid,comm,args
```

PID 1 should be `systemd`.

You can also check:

```bash
systemctl is-system-running
```

A `degraded` state can occur in WSL because of services that are not applicable to the virtualized environment. This does not necessarily prevent K3s from working.

---

# 5. Install Required Packages

Inside Ubuntu:

```bash
sudo apt update && sudo apt install -y \
  python3-venv \
  python3-pip \
  postgresql-client \
  curl \
  git
```

Validate the environment:

```bash
python3 --version
pip3 --version
git --version
curl --version
```

---

# 6. Install K3s

The PoC uses K3s as a single-node Kubernetes environment.

The validated K3s version used for this PoC is:

```text
v1.36.4+k3s1
```

Install K3s:

```bash
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_VERSION="v1.36.4+k3s1" \
  sh -s - --write-kubeconfig-mode=644
```

The `--write-kubeconfig-mode=644` option allows the current Linux user to access the K3s kubeconfig.

---

# 7. Validate K3s

Check the K3s service:

```bash
sudo systemctl status k3s --no-pager
```

Check whether the service is active:

```bash
sudo systemctl is-active k3s
```

Check the Kubernetes node:

```bash
kubectl get nodes
```

Check all pods:

```bash
kubectl get pods -A
```

The node should report:

```text
STATUS
Ready
```

---

# 8. Project Structure

The project is expected to be located at:

```text
~/ra-poc
```

Directory structure:

```text
ra-poc/
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
    ├── provisioning/
    │   ├── datasources/
    │   │   └── datasource.yml
    │   └── dashboards/
    │       └── dashboards.yml
    │
    └── dashboards/
        ├── ra-overview.json
        ├── ra-controls.json
        ├── ra-gaps.json
        ├── ra-by-offer.json
        ├── ra-projections.json
        └── ra-customers.json
```

---

# 9. Run the Setup

Change to the project directory:

```bash
cd ~/ra-poc
```

Make the setup script executable:

```bash
chmod +x setup.sh
```

Run the complete setup:

```bash
./setup.sh
```

The setup script executes the complete pipeline:

```text
[1/7] Deploy PostgreSQL
[2/7] Wait for PostgreSQL
[3/7] Create database schema
[4/7] Generate billing data
[5/7] Run Revenue Assurance Engine
[6/7] Run Machine Learning pipelines
[7/7] Deploy Grafana
```

---

# 10. PostgreSQL

PostgreSQL runs inside K3s.

The setup creates the following Kubernetes resources:

```text
Namespace
PersistentVolumeClaim
Deployment
Service
```

Namespace:

```text
ra-poc
```

The database is exposed to the host through the configured PostgreSQL service port used by the setup script.

---

# 11. Database Schema

The setup executes:

```bash
psql -f database/schema.sql
psql -f database/ml_schema.sql
psql -f database/ml_v2_schema.sql
```

The validated environment created:

```text
17 tables
```

---

# 12. Data Generator

The Data Generator creates synthetic telecommunications billing data.

Validated result:

| Entity | Quantity |
|---|---:|
| Offers | 20 |
| Rules | 32 |
| Customers | 1,000 |
| Contracts | 1,772 |
| Billing Cycles | 12 |
| Invoices | 11,779 |
| Invoice Items | 20,853 |

The generator intentionally introduced:

```text
618 billing gaps
```

approximately:

```text
5.2%
```

of the generated billing population.

### Total billed amount

```text
R$ 1,577,800.80
```

---

# 13. Revenue Assurance Engine

The RA Engine processed:

```text
12 billing cycles
```

and:

```text
20,848 checks
```

### Results

| Result | Quantity | Percentage |
|---|---:|---:|
| MATCH | 20,230 | 97.0% |
| JUSTIFIED | 0 | 0.0% |
| GAPS | 618 | 3.0% |

### Revenue

```text
Expected Revenue: R$ 1,576,503.40
Billed Revenue:   R$ 1,577,800.80
```

### Revenue Gap

```text
Total Gap Value: R$ 61,344.67
```

### Revenue Leakage

```text
3.89%
```

---

# 14. Revenue Assurance Gap Types

The RA Engine identifies:

```text
GAP_OVERCHARGE
GAP_UNDERCHARGE
GAP_MISSING
```

Conceptually:

```text
Expected Revenue
       │
       ▼
   RA Engine
       │
       ▼
Billed Revenue
       │
       ▼
   Gap Analysis
```

---

# 15. Machine Learning — Engine v1

The first ML pipeline uses:

```text
scikit-learn
GradientBoosting
Isolation Forest
Z-score
```

Validated version:

```text
scikit-learn 1.9.0
```

## Revenue Forecasting

The model generates six-month revenue projections.

Example:

```text
2026-01: R$ 241,307.21
2026-02: R$ 241,307.21
2026-03: R$ 241,307.21
2026-04: R$ 241,307.21
2026-05: R$ 241,307.21
2026-06: R$ 241,307.21
```

Training MAPE:

```text
0.00%
```

## Anomaly Detection

```text
Metrics monitored: 5
Cycles analyzed: 12
Anomalies found: 10
```

Method:

```text
Isolation Forest + Z-score
```

## Churn Prediction

The model also generates six-month churn predictions.

Validated average churn:

```text
0.13%
```

---

# 16. Machine Learning — Engine v2

The second ML pipeline uses more advanced models:

```text
PyTorch
scikit-learn
TF-IDF
KMeans
Autoencoder
```

Validated PyTorch version:

```text
2.14.0+cu130
```

## Autoencoder

Architecture:

```text
9 → 16 → 8 → 4 → 8 → 16 → 9
```

Results:

```text
Training epochs: 200
Final loss:      0.031043
Threshold:       0.078528
Anomalies:       1 / 12 cycles
```

## NLP Classification

The pipeline analyzed:

```text
20,848 texts
```

using:

```text
TF-IDF features: 100
KMeans clusters: 7
```

Final categories:

```text
BILLING_MATCH
OVERCHARGE
DUPLICATE
UNDERCHARGE
MISSING_CHARGE
```

Results:

| Category | Quantity | Value |
|---|---:|---:|
| BILLING_MATCH | 20,230 | R$ 1,504,676.04 |
| OVERCHARGE | 168 | R$ 4,231.68 |
| DUPLICATE | 153 | R$ 18,059.57 |
| UNDERCHARGE | 149 | R$ 4,286.99 |
| MISSING_CHARGE | 148 | R$ 16,706.86 |

Classification coverage:

```text
20,848 / 20,848
100%
```

---

# 17. Grafana

Grafana runs inside K3s.

Service type:

```text
NodePort
```

Port:

```text
30300
```

Access:

```text
http://localhost:30300
```

PoC credentials:

```text
Username: admin
Password: ra_poc_2024
```

> These credentials are intended only for the PoC environment and must not be used in production.

---

## 18. Dashboards


The PoC includes the following Grafana dashboards:


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


The dashboards are available after the setup completes:


```text
http://localhost:30300
```


### Dashboard URLs


```text
/d/ra-overview
/d/ra-controls
/d/ra-gaps
/d/ra-by-offer
/d/ra-projections
/d/ra-customers
/d/ra-ml-insights
/d/ra-offers-rules
/d/ra-customer-contracts
```


---


# 19. Validated Execution Result


The complete PoC pipeline was successfully executed.


```text
============================================
RA-PoC Execution Result
============================================


Customers:          1,000
Contracts:           1,772
Billing Cycles:         12
Invoices:            11,779
Invoice Items:       20,853


RA Checks:           20,848
MATCH:               20,230
GAPS:                   618


Expected Revenue:    R$ 1,576,503.40
Billed Revenue:      R$ 1,577,800.80
Gap Value:           R$    61,344.67


Revenue Leakage:            3.89%


ML Forecasts:              18
ML Anomalies v1:            10
ML Anomalies v2:             1


NLP Classification:       100%


Grafana:
http://localhost:30300
============================================
```

---

# 20. Validation Commands

Check all pods:

```bash
kubectl get pods -n ra-poc
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
kubectl get pods -n ra-poc -l app=postgres
```

Check Grafana:

```bash
kubectl get pods -n ra-poc -l app=grafana
```

---

# 21. Re-run the PoC

To execute the pipeline again:

```bash
cd ~/ra-poc
./setup.sh
```

The Data Generator clears existing generated data before creating a new dataset.

The RA Engine also clears previous RA results before processing the billing cycles again.

---

# 22. Main PoC Capabilities

The PoC demonstrates a Revenue Assurance platform capable of:

- Simulating telecommunications customers and contracts
- Simulating offers and billing rules
- Generating billing cycles
- Generating invoices and invoice items
- Introducing intentional billing gaps
- Comparing expected versus billed revenue
- Detecting overcharges
- Detecting undercharges
- Detecting missing charges
- Detecting anomalies
- Forecasting future revenue
- Predicting churn
- Classifying billing justifications using NLP
- Visualizing KPIs using Grafana
- Running the complete pipeline on Kubernetes/K3s

---

# 23. Environment

```text
OS:             Ubuntu 26.04
Runtime:        WSL2
Kubernetes:     K3s v1.36.4+k3s1
Python:         Python 3.14
scikit-learn:   1.9.0
PyTorch:        2.14.0+cu130
PostgreSQL:     Kubernetes Deployment
Grafana:        Kubernetes Deployment
```

---

# 24. Production Considerations

This project is a **Proof of Concept** and uses synthetic data.

For production environments, additional capabilities should be implemented, including:

- Secure secret management
- Proper authentication and authorization
- TLS
- High availability
- Database backup and recovery
- Kubernetes resource management
- Monitoring and observability
- Model versioning
- CI/CD
- Certificate management
- Network policies
- Production-grade credentials
- Persistent storage strategy

---

# 25. Quick Start

From Windows PowerShell:

```powershell
wsl --install -d Ubuntu-26.04
```

Start Ubuntu:

```powershell
wsl -d Ubuntu-26.04
```

Configure systemd:

```bash
sudo tee /etc/wsl.conf > /dev/null <<'EOF'
[boot]
systemd=true
EOF
```

Exit and restart WSL:

```bash
exit
```

```powershell
wsl --terminate Ubuntu-26.04
wsl -d Ubuntu-26.04
```

Install dependencies:

```bash
sudo apt update && sudo apt install -y \
  python3-venv \
  python3-pip \
  postgresql-client \
  curl \
  git
```

Install K3s:

```bash
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_VERSION="v1.36.4+k3s1" \
  sh -s - --write-kubeconfig-mode=644
```

Clone or copy the project:

```bash
cd ~
git clone <REPOSITORY_URL> ra-poc
cd ra-poc
```

Run the setup:

```bash
chmod +x setup.sh
./setup.sh
```

Open Grafana:

```text
http://localhost:30300
```

---

# 26. Status

The PoC has been successfully validated end-to-end.

```text
K3s        ✓
PostgreSQL ✓
Data       ✓
RA Engine  ✓
ML v1      ✓
ML v2      ✓
Grafana    ✓
```
