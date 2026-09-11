#!/usr/bin/env python3
"""
RA-PoC Data Generator
Generates synthetic billing data for 12 months to simulate a generic telecom billing environment.
- ~20 offers with rules
- ~1000 customers
- 1-3 contracts per customer
- 12 billing cycles (Jan-Dec 2025)
- ~5% intentional gaps for RA detection
"""

import os
import random
import string
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import psycopg2
from faker import Faker

# Config
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "30432")),
    "dbname": os.environ.get("DB_NAME", "ra_billing"),
    "user": os.environ.get("DB_USER", "ra_admin"),
    "password": os.environ.get("DB_PASSWORD", "ra_poc_2024")
}

NUM_CUSTOMERS = 1000
GAP_PERCENTAGE = 0.05  # 5% of invoices will have intentional gaps
BILLING_YEAR = 2025

fake = Faker("pt_BR")
random.seed(42)

# ============================================================
# OFFERS CATALOG
# ============================================================

OFFERS = [
    # PLANS
    {"code": "PLAN-BASIC-50", "name": "Basic Plan 50GB", "type": "PLAN", "price": 49.90},
    {"code": "PLAN-BASIC-100", "name": "Basic Plan 100GB", "type": "PLAN", "price": 69.90},
    {"code": "PLAN-PLUS-150", "name": "Plus Plan 150GB", "type": "PLAN", "price": 99.90},
    {"code": "PLAN-PLUS-200", "name": "Plus Plan 200GB", "type": "PLAN", "price": 119.90},
    {"code": "PLAN-PREMIUM-UNL", "name": "Premium Unlimited Plan", "type": "PLAN", "price": 149.90},
    {"code": "PLAN-FAMILIA-4", "name": "Family Plan 4 Lines", "type": "PLAN", "price": 199.90},
    {"code": "PLAN-FAMILIA-6", "name": "Family Plan 6 Lines", "type": "PLAN", "price": 279.90},
    {"code": "PLAN-EMP-BASIC", "name": "Business Plan Basic", "type": "PLAN", "price": 89.90},
    {"code": "PLAN-EMP-PLUS", "name": "Business Plan Plus", "type": "PLAN", "price": 149.90},
    {"code": "PLAN-EMP-PREMIUM", "name": "Business Plan Premium", "type": "PLAN", "price": 249.90},
    {"code": "PLAN-CTRL-30", "name": "Control Plan 30GB", "type": "PLAN", "price": 39.90},
    {"code": "PLAN-CTRL-50", "name": "Control Plan 50GB", "type": "PLAN", "price": 54.90},
    # ADDONS
    {"code": "ADD-STREAMING", "name": "Streaming Plus Addon", "type": "ADDON", "price": 29.90},
    {"code": "ADD-CLOUD-100", "name": "Cloud Storage 100GB Addon", "type": "ADDON", "price": 19.90},
    {"code": "ADD-SEGURO", "name": "Device Insurance Addon", "type": "ADDON", "price": 14.90},
    {"code": "ADD-ROAMING", "name": "Americas Roaming Addon", "type": "ADDON", "price": 49.90},
    {"code": "ADD-MUSIC", "name": "Premium Music Addon", "type": "ADDON", "price": 9.90},
    # PROMOS (temporary discounts)
    {"code": "PROMO-WELCOME-50", "name": "Welcome 50% Promo", "type": "PROMO", "price": 0.00},
    {"code": "PROMO-FIDELIDADE-20", "name": "Loyalty 20% Promo", "type": "PROMO", "price": 0.00},
    {"code": "PROMO-BLACKFRI", "name": "Black Friday 30% Promo", "type": "PROMO", "price": 0.00},
]

# Rules per offer
OFFER_RULES = {
    # Plans - base price + loyalty discounts
    "PLAN-BASIC-50": [
        {"type": "BASE_PRICE", "value": 49.90, "vtype": "FIXED", "desc": "Monthly plan base price"},
        {"type": "LOYALTY_DISCOUNT", "value": 10.00, "vtype": "PERCENT", "min_m": 12, "desc": "Loyalty discount after 12 months"},
    ],
    "PLAN-BASIC-100": [
        {"type": "BASE_PRICE", "value": 69.90, "vtype": "FIXED", "desc": "Monthly plan base price"},
        {"type": "LOYALTY_DISCOUNT", "value": 10.00, "vtype": "PERCENT", "min_m": 12, "desc": "Loyalty discount after 12 months"},
    ],
    "PLAN-PLUS-150": [
        {"type": "BASE_PRICE", "value": 99.90, "vtype": "FIXED", "desc": "Monthly plan base price"},
        {"type": "LOYALTY_DISCOUNT", "value": 15.00, "vtype": "PERCENT", "min_m": 12, "desc": "Loyalty discount after 12 months"},
        {"type": "COMBO_DISCOUNT", "value": 10.00, "vtype": "FIXED", "min_m": 0, "desc": "Combo discount with addon"},
    ],
    "PLAN-PLUS-200": [
        {"type": "BASE_PRICE", "value": 119.90, "vtype": "FIXED", "desc": "Monthly plan base price"},
        {"type": "LOYALTY_DISCOUNT", "value": 15.00, "vtype": "PERCENT", "min_m": 12, "desc": "Loyalty discount after 12 months"},
    ],
    "PLAN-PREMIUM-UNL": [
        {"type": "BASE_PRICE", "value": 149.90, "vtype": "FIXED", "desc": "Monthly plan base price"},
        {"type": "LOYALTY_DISCOUNT", "value": 20.00, "vtype": "PERCENT", "min_m": 12, "desc": "Loyalty discount after 12 months"},
    ],
    "PLAN-FAMILIA-4": [
        {"type": "BASE_PRICE", "value": 199.90, "vtype": "FIXED", "desc": "Monthly plan base price"},
        {"type": "LOYALTY_DISCOUNT", "value": 10.00, "vtype": "PERCENT", "min_m": 12, "desc": "Loyalty discount"},
    ],
    "PLAN-FAMILIA-6": [
        {"type": "BASE_PRICE", "value": 279.90, "vtype": "FIXED", "desc": "Monthly plan base price"},
        {"type": "LOYALTY_DISCOUNT", "value": 15.00, "vtype": "PERCENT", "min_m": 12, "desc": "Loyalty discount"},
    ],
    "PLAN-EMP-BASIC": [
        {"type": "BASE_PRICE", "value": 89.90, "vtype": "FIXED", "desc": "Monthly plan base price"},
        {"type": "LOYALTY_DISCOUNT", "value": 10.00, "vtype": "PERCENT", "min_m": 6, "desc": "Loyalty discount after 6 months"},
    ],
    "PLAN-EMP-PLUS": [
        {"type": "BASE_PRICE", "value": 149.90, "vtype": "FIXED", "desc": "Monthly plan base price"},
        {"type": "LOYALTY_DISCOUNT", "value": 15.00, "vtype": "PERCENT", "min_m": 6, "desc": "Loyalty discount after 6 months"},
    ],
    "PLAN-EMP-PREMIUM": [
        {"type": "BASE_PRICE", "value": 249.90, "vtype": "FIXED", "desc": "Monthly plan base price"},
        {"type": "LOYALTY_DISCOUNT", "value": 20.00, "vtype": "PERCENT", "min_m": 6, "desc": "Loyalty discount after 6 months"},
    ],
    "PLAN-CTRL-30": [
        {"type": "BASE_PRICE", "value": 39.90, "vtype": "FIXED", "desc": "Monthly plan base price"},
    ],
    "PLAN-CTRL-50": [
        {"type": "BASE_PRICE", "value": 54.90, "vtype": "FIXED", "desc": "Monthly plan base price"},
        {"type": "LOYALTY_DISCOUNT", "value": 5.00, "vtype": "PERCENT", "min_m": 12, "desc": "Loyalty discount"},
    ],
    # Addons
    "ADD-STREAMING": [
        {"type": "BASE_PRICE", "value": 29.90, "vtype": "FIXED", "desc": "Monthly streaming addon"},
    ],
    "ADD-CLOUD-100": [
        {"type": "BASE_PRICE", "value": 19.90, "vtype": "FIXED", "desc": "Monthly cloud storage addon"},
    ],
    "ADD-SEGURO": [
        {"type": "BASE_PRICE", "value": 14.90, "vtype": "FIXED", "desc": "Monthly device insurance"},
    ],
    "ADD-ROAMING": [
        {"type": "BASE_PRICE", "value": 49.90, "vtype": "FIXED", "desc": "Monthly Americas roaming addon"},
    ],
    "ADD-MUSIC": [
        {"type": "BASE_PRICE", "value": 9.90, "vtype": "FIXED", "desc": "Monthly premium music addon"},
    ],
    # Promos
    "PROMO-WELCOME-50": [
        {"type": "PROMO_DISCOUNT", "value": 50.00, "vtype": "PERCENT", "max_m": 3, "desc": "50% off for first 3 months"},
    ],
    "PROMO-FIDELIDADE-20": [
        {"type": "PROMO_DISCOUNT", "value": 20.00, "vtype": "PERCENT", "min_m": 12, "desc": "20% off after 12 months"},
    ],
    "PROMO-BLACKFRI": [
        {"type": "PROMO_DISCOUNT", "value": 30.00, "vtype": "PERCENT", "max_m": 6, "desc": "30% off for 6 months (Black Friday)"},
    ],
}


def connect_db():
    return psycopg2.connect(**DB_CONFIG)


def truncate_tables(conn):
    """Clear all data for re-generation"""
    with conn.cursor() as cur:
        cur.execute("""
            TRUNCATE TABLE ra_projection, ra_result, ra_run,
                          invoice_item, invoice, billing_cycle,
                          contract, customer, offer_rule, offer
            CASCADE
        """)
    conn.commit()
    print("✓ Tables truncated")


def create_offers(conn):
    """Insert offers and their rules"""
    with conn.cursor() as cur:
        for offer in OFFERS:
            cur.execute("""
                INSERT INTO offer (offer_code, offer_name, offer_type, base_price)
                VALUES (%s, %s, %s, %s)
                RETURNING offer_id
            """, (offer["code"], offer["name"], offer["type"], offer["price"]))
            offer_id = cur.fetchone()[0]
            offer["id"] = offer_id

            # Insert rules
            rules = OFFER_RULES.get(offer["code"], [])
            for rule in rules:
                cur.execute("""
                    INSERT INTO offer_rule (offer_id, rule_type, rule_value, value_type,
                                          min_months, max_months, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    offer_id, rule["type"], rule["value"], rule["vtype"],
                    rule.get("min_m", 0), rule.get("max_m"), rule["desc"]
                ))
    conn.commit()
    print(f"✓ {len(OFFERS)} offers created with rules")
    return {o["code"]: o for o in OFFERS}


def create_customers(conn):
    """Generate fake customers"""
    customers = []
    with conn.cursor() as cur:
        for i in range(1, NUM_CUSTOMERS + 1):
            ctype = random.choice(["PF"] * 8 + ["PJ"] * 2)  # 80% PF, 20% PJ
            name = fake.company() if ctype == "PJ" else fake.name()
            doc = fake.cnpj() if ctype == "PJ" else fake.cpf()
            code = f"CLI-{i:05d}"

            cur.execute("""
                INSERT INTO customer (customer_code, customer_name, document_number, customer_type)
                VALUES (%s, %s, %s, %s)
                RETURNING customer_id
            """, (code, name, doc, ctype))
            cid = cur.fetchone()[0]
            customers.append({"id": cid, "code": code, "type": ctype})
    conn.commit()
    print(f"✓ {len(customers)} customers created")
    return customers


def create_contracts(conn, customers, offers):
    """Create 1-3 contracts per customer"""
    contracts = []
    plan_codes = [o["code"] for o in OFFERS if o["type"] == "PLAN"]
    addon_codes = [o["code"] for o in OFFERS if o["type"] == "ADDON"]

    with conn.cursor() as cur:
        for cust in customers:
            # Each customer gets 1 plan + 0-2 addons
            plan_code = random.choice(plan_codes)
            plan_offer = offers[plan_code]

            # Random start date (some before 2025, some during 2025)
            months_active = random.randint(1, 24)
            start_date = date(2025, 1, 1) - timedelta(days=months_active * 30)
            loyalty = random.choice([0, 0, 0, 6, 12, 12, 24])
            discount = random.choice([0, 0, 0, 0, 5, 10, 15])
            billing_day = random.randint(1, 28)

            # Status: most active, some suspended/cancelled during the year
            status = "ACTIVE"
            end_date = None
            rand_status = random.random()
            if rand_status < 0.03:
                status = "CANCELLED"
                end_date = date(2025, random.randint(1, 12), random.randint(1, 28))
            elif rand_status < 0.05:
                status = "SUSPENDED"
                end_date = date(2025, random.randint(6, 12), random.randint(1, 28))

            contract_code = f"CTR-{cust['code']}-01"
            cur.execute("""
                INSERT INTO contract (contract_code, customer_id, offer_id, status,
                                    start_date, end_date, billing_day, loyalty_months, discount_pct)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING contract_id
            """, (contract_code, cust["id"], plan_offer["id"], status,
                  start_date, end_date, billing_day, loyalty, discount))
            ctr_id = cur.fetchone()[0]
            contracts.append({
                "id": ctr_id, "customer_id": cust["id"],
                "offer_code": plan_code, "offer_id": plan_offer["id"],
                "start_date": start_date, "end_date": end_date,
                "status": status, "loyalty": loyalty,
                "discount_pct": discount, "billing_day": billing_day
            })

            # Add 0-2 addons
            num_addons = random.choices([0, 1, 2], weights=[40, 40, 20])[0]
            if num_addons > 0:
                chosen_addons = random.sample(addon_codes, min(num_addons, len(addon_codes)))
                for idx, addon_code in enumerate(chosen_addons, 2):
                    addon_offer = offers[addon_code]
                    addon_start = start_date + timedelta(days=random.randint(0, 90))
                    addon_contract_code = f"CTR-{cust['code']}-{idx:02d}"

                    cur.execute("""
                        INSERT INTO contract (contract_code, customer_id, offer_id, status,
                                            start_date, end_date, billing_day, loyalty_months, discount_pct)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING contract_id
                    """, (addon_contract_code, cust["id"], addon_offer["id"],
                          status, addon_start, end_date, billing_day, 0, 0))
                    addon_ctr_id = cur.fetchone()[0]
                    contracts.append({
                        "id": addon_ctr_id, "customer_id": cust["id"],
                        "offer_code": addon_code, "offer_id": addon_offer["id"],
                        "start_date": addon_start, "end_date": end_date,
                        "status": status, "loyalty": 0,
                        "discount_pct": 0, "billing_day": billing_day
                    })
    conn.commit()
    print(f"✓ {len(contracts)} contracts created")
    return contracts


def create_billing_cycles(conn):
    """Create 12 monthly billing cycles for 2025"""
    cycles = []
    with conn.cursor() as cur:
        for month in range(1, 13):
            code = f"{BILLING_YEAR}-{month:02d}"
            start = date(BILLING_YEAR, month, 1)
            if month == 12:
                end = date(BILLING_YEAR, 12, 31)
            else:
                end = date(BILLING_YEAR, month + 1, 1) - timedelta(days=1)

            cur.execute("""
                INSERT INTO billing_cycle (cycle_code, cycle_year, cycle_month, start_date, end_date, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING cycle_id
            """, (code, BILLING_YEAR, month, start, end, "CLOSED"))
            cid = cur.fetchone()[0]
            cycles.append({"id": cid, "code": code, "month": month, "start": start, "end": end})
    conn.commit()
    print(f"✓ {len(cycles)} billing cycles created")
    return cycles


def calculate_expected_amount(contract, offers_dict, cycle_month):
    """Calculate what SHOULD be charged based on offer rules"""
    offer_code = contract["offer_code"]
    base_price = Decimal(str(offers_dict[offer_code]["price"]))
    rules = OFFER_RULES.get(offer_code, [])

    # Calculate months since contract start
    contract_months = (date(BILLING_YEAR, cycle_month, 1) - contract["start_date"]).days // 30

    total_discount = Decimal("0")
    for rule in rules:
        if rule["type"] == "LOYALTY_DISCOUNT":
            if contract_months >= rule.get("min_m", 0) and contract["loyalty"] >= rule.get("min_m", 0):
                if rule["vtype"] == "PERCENT":
                    total_discount += base_price * Decimal(str(rule["value"])) / 100
                else:
                    total_discount += Decimal(str(rule["value"]))

        elif rule["type"] == "PROMO_DISCOUNT":
            max_m = rule.get("max_m", 999)
            min_m = rule.get("min_m", 0)
            if min_m <= contract_months <= max_m:
                if rule["vtype"] == "PERCENT":
                    total_discount += base_price * Decimal(str(rule["value"])) / 100
                else:
                    total_discount += Decimal(str(rule["value"]))

        elif rule["type"] == "COMBO_DISCOUNT":
            # Apply if customer has addons (simplified)
            if rule["vtype"] == "FIXED":
                total_discount += Decimal(str(rule["value"]))

    # Individual contract discount
    if contract["discount_pct"] > 0:
        total_discount += base_price * Decimal(str(contract["discount_pct"])) / 100

    final = (base_price - total_discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return max(final, Decimal("0")), base_price, total_discount


def generate_invoices(conn, contracts, cycles, offers_dict):
    """Generate invoices for each cycle, introducing ~5% gaps"""
    invoice_count = 0
    item_count = 0
    gap_count = 0

    # Group contracts by customer
    customer_contracts = {}
    for ctr in contracts:
        cid = ctr["customer_id"]
        if cid not in customer_contracts:
            customer_contracts[cid] = []
        customer_contracts[cid].append(ctr)

    with conn.cursor() as cur:
        for cycle in cycles:
            for customer_id, cust_contracts in customer_contracts.items():
                # Filter active contracts for this cycle
                active_contracts = []
                for ctr in cust_contracts:
                    if ctr["start_date"] <= cycle["end"]:
                        if ctr["end_date"] is None or ctr["end_date"] >= cycle["start"]:
                            if ctr["status"] in ("ACTIVE", "SUSPENDED"):
                                active_contracts.append(ctr)

                if not active_contracts:
                    continue

                # Decide if this invoice has a gap (5% chance)
                has_gap = random.random() < GAP_PERCENTAGE
                gap_type = None
                if has_gap:
                    gap_type = random.choice([
                        "MISSING_ITEM",      # contract not billed
                        "OVERCHARGE",        # billed more than expected
                        "UNDERCHARGE",       # billed less than expected
                        "DOUBLE_CHARGE",     # billed twice
                    ])
                    gap_count += 1

                # Create invoice
                inv_number = f"INV-{cycle['code']}-{customer_id:05d}"
                inv_date = date(BILLING_YEAR, cycle["month"], min(active_contracts[0]["billing_day"], 28))
                due_date = inv_date + timedelta(days=10)

                cur.execute("""
                    INSERT INTO invoice (invoice_number, customer_id, cycle_id, invoice_date, due_date, total_amount, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING invoice_id
                """, (inv_number, customer_id, cycle["id"], inv_date, due_date, 0,
                      random.choices(["PAID", "ISSUED", "OVERDUE"], weights=[75, 15, 10])[0]))
                invoice_id = cur.fetchone()[0]
                invoice_count += 1

                total_amount = Decimal("0")

                for idx, ctr in enumerate(active_contracts):
                    # GAP: skip one contract (MISSING_ITEM)
                    if has_gap and gap_type == "MISSING_ITEM" and idx == 0:
                        continue

                    expected, base, discount = calculate_expected_amount(ctr, offers_dict, cycle["month"])

                    # Apply gap modifications
                    billed = expected
                    if has_gap and idx == 0:
                        if gap_type == "OVERCHARGE":
                            # Charge 10-30% more
                            extra = expected * Decimal(str(random.uniform(0.10, 0.30)))
                            billed = (expected + extra).quantize(Decimal("0.01"))
                        elif gap_type == "UNDERCHARGE":
                            # Charge 10-40% less
                            less = expected * Decimal(str(random.uniform(0.10, 0.40)))
                            billed = (expected - less).quantize(Decimal("0.01"))

                    desc = f"{offers_dict[ctr['offer_code']]['name']} - {cycle['code']}"
                    cur.execute("""
                        INSERT INTO invoice_item (invoice_id, contract_id, offer_id, description,
                                                base_amount, discount_amount, final_amount, charge_type)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (invoice_id, ctr["id"], ctr["offer_id"], desc,
                          float(base), float(discount), float(billed), "RECURRING"))
                    item_count += 1
                    total_amount += billed

                    # GAP: duplicate charge
                    if has_gap and gap_type == "DOUBLE_CHARGE" and idx == 0:
                        cur.execute("""
                            INSERT INTO invoice_item (invoice_id, contract_id, offer_id, description,
                                                    base_amount, discount_amount, final_amount, charge_type)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (invoice_id, ctr["id"], ctr["offer_id"], f"[DUP] {desc}",
                              float(base), float(discount), float(billed), "RECURRING"))
                        item_count += 1
                        total_amount += billed

                # Update invoice total
                cur.execute("UPDATE invoice SET total_amount = %s WHERE invoice_id = %s",
                           (float(total_amount), invoice_id))

        conn.commit()
    print(f"✓ {invoice_count} invoices created with {item_count} items")
    print(f"  → {gap_count} intentional gaps introduced (~{gap_count*100/invoice_count:.1f}%)")


def main():
    print("=" * 60)
    print("RA-PoC Data Generator")
    print("=" * 60)

    conn = connect_db()
    try:
        print("\n[1/5] Cleaning existing data...")
        truncate_tables(conn)

        print("\n[2/5] Creating offers catalog...")
        offers_dict = create_offers(conn)

        print("\n[3/5] Creating customers...")
        customers = create_customers(conn)

        print("\n[4/5] Creating contracts...")
        contracts = create_contracts(conn, customers, offers_dict)

        print("\n[5/5] Generating 12 months of billing...")
        cycles = create_billing_cycles(conn)
        generate_invoices(conn, contracts, cycles, offers_dict)

        # Final stats
        with conn.cursor() as cur:
            print("\n" + "="*60)
            print("SUMMARY")
            print("="*60)
            cur.execute("SELECT COUNT(*) FROM offer")
            print(f"  Offers:    {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM offer_rule")
            print(f"  Rules:     {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM customer")
            print(f"  Customers: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM contract")
            print(f"  Contracts: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM billing_cycle")
            print(f"  Cycles:    {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM invoice")
            print(f"  Invoices:  {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM invoice_item")
            print(f"  Items:     {cur.fetchone()[0]}")
            cur.execute("SELECT SUM(total_amount) FROM invoice")
            total = cur.fetchone()[0]
            print(f"  Total Billed: R$ {total:,.2f}")
            print("="*60)

    finally:
        conn.close()
    print("\n✓ Data generation complete!")


if __name__ == "__main__":
    main()
