-- ============================================================
-- RA-PoC: Schema EB-like (Revenue Assurance Proof of Concept)
-- Database: ra_billing @ PostgreSQL 16
-- ============================================================

-- ============================================================
-- CAMADA 1: CRM (Catalogo, Clientes, Contratos)
-- ============================================================

CREATE TABLE offer (
    offer_id        SERIAL PRIMARY KEY,
    offer_code      VARCHAR(20) UNIQUE NOT NULL,
    offer_name      VARCHAR(100) NOT NULL,
    offer_type      VARCHAR(20) NOT NULL CHECK (offer_type IN ('PLAN', 'ADDON', 'PROMO')),
    base_price      NUMERIC(10,2) NOT NULL,
    currency        VARCHAR(3) DEFAULT 'BRL',
    recurrence      VARCHAR(10) DEFAULT 'MONTHLY' CHECK (recurrence IN ('MONTHLY', 'YEARLY', 'ONCE')),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE offer_rule (
    rule_id         SERIAL PRIMARY KEY,
    offer_id        INTEGER REFERENCES offer(offer_id),
    rule_type       VARCHAR(30) NOT NULL CHECK (rule_type IN (
                        'BASE_PRICE', 'LOYALTY_DISCOUNT', 'PROMO_DISCOUNT',
                        'PRO_RATA', 'COMBO_DISCOUNT', 'PENALTY'
                    )),
    rule_value      NUMERIC(10,2) NOT NULL,
    value_type      VARCHAR(10) DEFAULT 'FIXED' CHECK (value_type IN ('FIXED', 'PERCENT')),
    min_months      INTEGER DEFAULT 0,
    max_months      INTEGER,
    description     VARCHAR(200),
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE customer (
    customer_id     SERIAL PRIMARY KEY,
    customer_code   VARCHAR(20) UNIQUE NOT NULL,
    customer_name   VARCHAR(100) NOT NULL,
    document_number VARCHAR(20),
    customer_type   VARCHAR(10) DEFAULT 'PF' CHECK (customer_type IN ('PF', 'PJ')),
    status          VARCHAR(10) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUSPENDED', 'CANCELLED')),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE contract (
    contract_id     SERIAL PRIMARY KEY,
    contract_code   VARCHAR(30) UNIQUE NOT NULL,
    customer_id     INTEGER REFERENCES customer(customer_id),
    offer_id        INTEGER REFERENCES offer(offer_id),
    status          VARCHAR(15) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUSPENDED', 'CANCELLED', 'EXPIRED')),
    start_date      DATE NOT NULL,
    end_date        DATE,
    billing_day     INTEGER DEFAULT 1 CHECK (billing_day BETWEEN 1 AND 28),
    loyalty_months  INTEGER DEFAULT 0,
    discount_pct    NUMERIC(5,2) DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- CAMADA 2: BILLING (Ciclos, Faturas, Itens)
-- ============================================================

CREATE TABLE billing_cycle (
    cycle_id        SERIAL PRIMARY KEY,
    cycle_code      VARCHAR(10) UNIQUE NOT NULL,
    cycle_year      INTEGER NOT NULL,
    cycle_month     INTEGER NOT NULL CHECK (cycle_month BETWEEN 1 AND 12),
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    status          VARCHAR(15) DEFAULT 'CLOSED' CHECK (status IN ('OPEN', 'PROCESSING', 'CLOSED')),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE invoice (
    invoice_id      SERIAL PRIMARY KEY,
    invoice_number  VARCHAR(30) UNIQUE NOT NULL,
    customer_id     INTEGER REFERENCES customer(customer_id),
    cycle_id        INTEGER REFERENCES billing_cycle(cycle_id),
    invoice_date    DATE NOT NULL,
    due_date        DATE NOT NULL,
    total_amount    NUMERIC(12,2) NOT NULL DEFAULT 0,
    status          VARCHAR(15) DEFAULT 'ISSUED' CHECK (status IN ('ISSUED', 'PAID', 'OVERDUE', 'CANCELLED')),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE invoice_item (
    item_id         SERIAL PRIMARY KEY,
    invoice_id      INTEGER REFERENCES invoice(invoice_id),
    contract_id     INTEGER REFERENCES contract(contract_id),
    offer_id        INTEGER REFERENCES offer(offer_id),
    description     VARCHAR(200),
    base_amount     NUMERIC(10,2) NOT NULL,
    discount_amount NUMERIC(10,2) DEFAULT 0,
    final_amount    NUMERIC(10,2) NOT NULL,
    charge_type     VARCHAR(20) DEFAULT 'RECURRING' CHECK (charge_type IN ('RECURRING', 'PRO_RATA', 'PENALTY', 'ADDON')),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- CAMADA 3: REVENUE ASSURANCE
-- ============================================================

CREATE TABLE ra_run (
    run_id          SERIAL PRIMARY KEY,
    run_date        TIMESTAMP DEFAULT NOW(),
    cycle_id        INTEGER REFERENCES billing_cycle(cycle_id),
    total_customers INTEGER DEFAULT 0,
    total_contracts INTEGER DEFAULT 0,
    total_invoices  INTEGER DEFAULT 0,
    gaps_found      INTEGER DEFAULT 0,
    status          VARCHAR(15) DEFAULT 'RUNNING' CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED'))
);

CREATE TABLE ra_result (
    result_id       SERIAL PRIMARY KEY,
    run_id          INTEGER REFERENCES ra_run(run_id),
    customer_id     INTEGER REFERENCES customer(customer_id),
    contract_id     INTEGER REFERENCES contract(contract_id),
    invoice_id      INTEGER REFERENCES invoice(invoice_id),
    expected_amount NUMERIC(10,2) NOT NULL,
    billed_amount   NUMERIC(10,2),
    difference      NUMERIC(10,2),
    status          VARCHAR(20) NOT NULL CHECK (status IN (
                        'MATCH', 'JUSTIFIED', 'GAP_OVERCHARGE',
                        'GAP_UNDERCHARGE', 'GAP_MISSING'
                    )),
    justification   VARCHAR(500)
);

CREATE TABLE ra_projection (
    projection_id   SERIAL PRIMARY KEY,
    run_id          INTEGER REFERENCES ra_run(run_id),
    cycle_code      VARCHAR(10) NOT NULL,
    projected_revenue NUMERIC(14,2) NOT NULL,
    active_contracts  INTEGER NOT NULL,
    avg_ticket        NUMERIC(10,2),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_contract_customer ON contract(customer_id);
CREATE INDEX idx_contract_offer ON contract(offer_id);
CREATE INDEX idx_contract_status ON contract(status);
CREATE INDEX idx_invoice_customer ON invoice(customer_id);
CREATE INDEX idx_invoice_cycle ON invoice(cycle_id);
CREATE INDEX idx_invoice_item_invoice ON invoice_item(invoice_id);
CREATE INDEX idx_invoice_item_contract ON invoice_item(contract_id);
CREATE INDEX idx_ra_result_run ON ra_result(run_id);
CREATE INDEX idx_ra_result_status ON ra_result(status);
CREATE INDEX idx_ra_result_customer ON ra_result(customer_id);

-- ============================================================
