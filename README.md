# Revenue Assurance PoC

This repository contains a **Revenue Assurance Proof of Concept (PoC)** for a telecom billing environment.

The PoC provides an end-to-end environment including:

* PostgreSQL database
* Telecom billing data generation
* Revenue Assurance controls
* Billing gap detection
* Revenue leakage calculation
* Machine Learning analysis
* Revenue forecasting
* Anomaly detection
* Churn prediction
* Grafana dashboards

The environment is designed to run locally using:

* Windows
* WSL2
* Ubuntu 26.04
* K3s
* PostgreSQL
* Python
* Grafana

---

# 1. Prerequisites

Before installing the PoC, make sure the following are available:

* Windows 10/11
* WSL2
* Ubuntu 26.04
* Internet connection
* Administrator privileges on Windows
* At least 8 GB RAM recommended
* At least 20 GB free disk space

---

# 2. Install WSL2 and Ubuntu

Open **PowerShell as Administrator**.

Install WSL:

```powershell
wsl --install
```

Install Ubuntu 26.04:

```powershell
wsl --install -d Ubuntu-26.04
```

Check the installed distributions:

```powershell
wsl --list --verbose
```

Expected:

```text
NAME            STATE           VERSION
Ubuntu-26.04    Running         2
```

Start Ubuntu:

```powershell
wsl -d Ubuntu-26.04
```

During the first startup, Ubuntu will ask you to create a Linux user and password.

The username is not fixed by this PoC.

---

# 3. Configure systemd

K3s requires systemd.

Inside Ubuntu, create `/etc/wsl.conf`:

```bash
sudo tee /etc/wsl.conf > /dev/null <<'EOF'
[boot]
systemd=true
EOF
```

Exit Ubuntu:

```bash
exit
```

From PowerShell, restart the distribution:

```powershell
wsl --terminate Ubuntu-26.04
```

Start it again:

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
1   systemd         /sbin/init
```

Check the system:

```bash
systemctl is-system-running
```

`degraded` may be reported in WSL because some services are not applicable to the WSL environment. This does not necessarily prevent the PoC from running.

---

# 4. Install Required Packages

Update Ubuntu:

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

Verify Git:

```bash
git --version
```

Verify PostgreSQL client:

```bash
psql --version
```

---

# 5. Install K3s

Install the K3s version used by the PoC:

```bash
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_VERSION="v1.36.4+k3s1" \
  sh -s - --write-kubeconfig-mode=644
```

Check K3s:

```bash
sudo systemctl status k3s
```

Check the Kubernetes node:

```bash
kubectl get nodes
```

The node should be in `Ready` state.

Example:

```text
NAME       STATUS   ROLES                  AGE   VERSION
<node>     Ready    control-plane,master   ...   v1.36.4+k3s1
```

---

# 6. Configure kubectl

For this PoC, the K3s kubeconfig is created with permissions that allow the local user to access it.

Set:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
```

To make this persistent:

```bash
echo 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' >> ~/.bashrc
```

Reload the shell configuration:

```bash
source ~/.bashrc
```

Validate:

```bash
kubectl get nodes
```

> For a production environment, use a user-owned kubeconfig with restrictive permissions instead of `644`.

---

# 7. Get the PoC Source Code

The PoC directory is:

```text
~/ra-poc
```

Clone the repository according to your Git environment.

Example:

```bash
cd ~
git clone <REPOSITORY_URL> ra-poc
```

Enter the project directory:

```bash
cd ~/ra-poc
```

Verify the project:

```bash
ls
```

Expected structure:

```text
setup.sh
k8s/
database/
data-generator/
ra-engine/
ra-ml/
grafana/
```

Make the setup script executable:

```bash
chmod +x setup.sh
```

---

# 8. Run the PoC Installation

From the project root:

```bash
cd ~/ra-poc
```

Run:

```bash
./setup.sh
```

The setup script performs the complete PoC deployment.

The installation sequence is:

```text
1. Deploy PostgreSQL
2. Wait for PostgreSQL
3. Create database schemas
4. Generate telecom billing data
5. Run Revenue Assurance engine
6. Run Machine Learning engines
7. Deploy Grafana
```

No manual execution of the individual Python components is required when using `setup.sh`.

---

# 9. Python Virtual Environments

The setup process creates Python virtual environments for the PoC components.

The environments are located under the corresponding directories:

```text
data-generator/venv/
ra-engine/venv/
ra-ml/venv/
```

They are intentionally not committed to Git.

If a virtual environment becomes invalid after moving or renaming the project directory, remove and recreate it.

Example:

```bash
cd ~/ra-poc/data-generator

rm -rf venv

python3 -m venv venv
```

The setup script can recreate the required environments.

---

# 10. Kubernetes Resources Created

After the installation, check the PoC namespace:

```bash
kubectl get all -n ra-poc
```

The PoC creates the namespace:

```text
ra-poc
```

Main Kubernetes components:

```text
PostgreSQL
Grafana
```

Check pods:

```bash
kubectl get pods -n ra-poc
```

Expected components should show `Running` or `Completed` according to their function.

Check services:

```bash
kubectl get svc -n ra-poc
```

---

# 11. PostgreSQL

PostgreSQL runs inside K3s.

Connection information:

```text
Host:     localhost
Port:     30432
Database: ra_billing
User:     ra_admin
Password: ra_poc_2024
```

> These credentials are for the PoC only and must be changed for production use.

## Connect using psql

```bash
PGPASSWORD=ra_poc_2024 \
psql \
  -h localhost \
  -p 30432 \
  -U ra_admin \
  -d ra_billing
```

After connecting:

```sql
\dt
```

This lists the database tables.

Exit:

```sql
\q
```

---

# 12. Validate the Database

The PoC creates **17 tables**.

Check the number of tables:

```sql
SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema = 'public';
```

Expected:

```text
17
```

Check invoices:

```sql
SELECT COUNT(*) FROM invoices;
```

Expected:

```text
11779
```

Check Revenue Assurance controls:

```sql
SELECT COUNT(*) FROM ra_checks;
```

Expected:

```text
20848
```

Check ML forecasts:

```sql
SELECT COUNT(*) FROM ml_forecasts;
```

Expected:

```text
18
```

---

# 13. Data Generated

The PoC generates a simulated telecom billing environment.

The validated installation creates:

| Entity         | Quantity |
| -------------- | -------: |
| Customers      |    1,000 |
| Contracts      |    1,772 |
| Offers         |       20 |
| Billing Rules  |       32 |
| Billing Cycles |       12 |
| Invoices       |   11,779 |
| Invoice Items  |   20,853 |

Total billed amount:

```text
R$ 1,577,800.80
```

The generator intentionally introduces billing gaps to simulate Revenue Assurance scenarios.

---

# 14. Revenue Assurance Results

The Revenue Assurance engine validates the generated billing data.

Validated results:

```text
Total checks:       20,848
MATCH:              20,230
GAPS:                   618

Expected Revenue:  R$ 1,576,503.40
Billed Revenue:    R$ 1,577,800.80
Total Gap Value:   R$    61,344.67

Revenue Leakage:          3.89%
```

The identified gap types include:

```text
GAP_OVERCHARGE
GAP_UNDERCHARGE
GAP_MISSING
```

---

# 15. Machine Learning Results

The PoC contains two ML implementations.

The validated environment includes:

```text
Scikit-learn: 1.9.0
PyTorch:      2.14.0
```

ML capabilities include:

* Revenue forecasting
* Anomaly detection
* Churn prediction
* Billing classification
* NLP analysis

Validated ML V2 results:

```text
Autoencoder:
9 → 16 → 8 → 4 → 8 → 16 → 9

Training epochs: 200
Final loss:      0.031043
Anomalies:       1 / 12 cycles
```

NLP processing:

```text
Texts analyzed: 20,848
TF-IDF features: 100
KMeans clusters: 7
Classification coverage: 100%
```

---

# 16. Access Grafana

Grafana is exposed through a Kubernetes NodePort.

Open:

```text
http://localhost:30300
```

Login:

```text
User:     admin
Password: ra_poc_2024
```

> These are PoC credentials only.

---

# 17. Grafana Dashboards

The PoC provides the following dashboards:

| Dashboard         | URL                                              |
| ----------------- | ------------------------------------------------ |
| Overview          | `http://localhost:30300/d/ra-overview`           |
| RA Controls       | `http://localhost:30300/d/ra-controls`           |
| Gaps              | `http://localhost:30300/d/ra-gaps`               |
| By Offer          | `http://localhost:30300/d/ra-by-offer`           |
| Projections       | `http://localhost:30300/d/ra-projections`        |
| Customers         | `http://localhost:30300/d/ra-customers`          |
| ML Insights       | `http://localhost:30300/d/ra-ml-insights`        |
| Offers & Rules    | `http://localhost:30300/d/ra-offers-rules`       |
| Contracts & Rules | `http://localhost:30300/d/ra-customer-contracts` |

Main dashboard:

```text
http://localhost:30300/d/ra-overview
```

---

# 18. Grafana Kubernetes Validation

Check the Grafana pod:

```bash
kubectl get pods -n ra-poc
```

Check the Grafana deployment:

```bash
kubectl get deployment grafana -n ra-poc
```

Check the service:

```bash
kubectl get svc grafana -n ra-poc
```

Expected NodePort:

```text
3000:30300
```

If Grafana is not accessible, check the logs:

```bash
kubectl logs deployment/grafana -n ra-poc
```

---

# 19. Useful Validation Commands

## Check all PoC resources

```bash
kubectl get all -n ra-poc
```

## Check pods

```bash
kubectl get pods -n ra-poc
```

## Check services

```bash
kubectl get svc -n ra-poc
```

## Check deployments

```bash
kubectl get deployments -n ra-poc
```

## Check PostgreSQL logs

```bash
kubectl logs deployment/postgres -n ra-poc
```

## Check Grafana logs

```bash
kubectl logs deployment/grafana -n ra-poc
```

## Check K3s

```bash
sudo systemctl status k3s
```

## Check Kubernetes node

```bash
kubectl get nodes
```

---

# 20. Project Structure

After installation, the project contains:

```text
ra-poc/
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
        ├── ra-customers.json
        ├── ra-ml-insights.json
        ├── ra-offers-rules.json
        └── ra-customer-contracts.json
```

---

# 21. Installation Summary

After a successful installation, the environment should contain:

```text
WSL2
  └── Ubuntu 26.04
        └── systemd
              └── K3s
                    └── ra-poc namespace
                          ├── PostgreSQL
                          │     └── ra_billing
                          │
                          └── Grafana
                                └── 9 dashboards
```

The main access points are:

### Grafana

```text
http://localhost:30300
```

### PostgreSQL

```text
localhost:30432
```

### Kubernetes

```bash
kubectl get all -n ra-poc
```

---

# 22. Quick Start

For a new environment:

```powershell
wsl --install -d Ubuntu-26.04
```

Inside Ubuntu:

```bash
sudo tee /etc/wsl.conf > /dev/null <<'EOF'
[boot]
systemd=true
EOF
```

Restart WSL:

```powershell
wsl --terminate Ubuntu-26.04
wsl -d Ubuntu-26.04
```

Install dependencies:

```bash
sudo apt update

sudo apt install -y \
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

Configure kubectl:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
```

Get the PoC:

```bash
cd ~
git clone <REPOSITORY_URL> ra-poc
```

Run the installation:

```bash
cd ~/ra-poc

chmod +x setup.sh

./setup.sh
```

After completion:

```text
Grafana:
http://localhost:30300
```

Database:

```text
localhost:30432
```

---

# 23. Troubleshooting

## K3s is not running

```bash
sudo systemctl status k3s
```

Restart:

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

## Permission denied on kubeconfig

For this PoC:

```bash
sudo chmod 644 /etc/rancher/k3s/k3s.yaml
```

Then:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
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

## Grafana is not accessible

Check:

```bash
kubectl get pods -n ra-poc
```

Check service:

```bash
kubectl get svc -n ra-poc
```

Check logs:

```bash
kubectl logs deployment/grafana -n ra-poc
```

---

## Python virtual environment is invalid

If you see:

```text
bad interpreter: No such file or directory
```

recreate the environment:

```bash
cd ~/ra-poc/data-generator

rm -rf venv

python3 -m venv venv
```

Then rerun:

```bash
cd ~/ra-poc
./setup.sh
```

---

# 24. PoC Status

Validated end-to-end environment:

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
9 Dashboards          ✓
End-to-End Validation ✓
```

The PoC is ready for demonstration and further development.
