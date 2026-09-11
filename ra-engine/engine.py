#!/usr/bin/env python3
"""
RA-PoC Revenue Assurance Engine
Performs CRM x Billing reconciliation, identifies gaps, and projects revenue.
"""

import os
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import psycopg2
from psycopg2.extras import RealDictCursor

# Config
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "30432")),
    "dbname": os.environ.get("DB_NAME", "ra_billing"),
    "user": os.environ.get("DB_USER", "ra_admin"),
    "password": os.environ.get("DB_PASSWORD", "ra_poc_2024")
}


def connect_db():
    return psycopg2.connect(**DB_CONFIG)


def get_offer_rules(conn):
    """Load all offer rules into memory for fast lookup"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT o.offer_id, o.offer_code, o.base_price,
                   r.rule_type, r.rule_value, r.value_type, r.min_months, r.max_months
            FROM offer o
            LEFT JOIN offer_rule r ON r.offer_id = o.offer_id AND r.is_active = TRUE
            WHERE o.is_active = TRUE
            ORDER BY o.offer_id
        """)
        rows = cur.fetchall()

    rules_by_offer = {}
    for row in rows:
        oid = row["offer_id"]
        if oid not in rules_by_offer:
            rules_by_offer[oid] = {
                "offer_code": row["offer_code"],
                "base_price": row["base_price"],
                "rules": []
            }
        if row["rule_type"]:
            rules_by_offer[oid]["rules"].append({
                "type": row["rule_type"],
                "value": row["rule_value"],
                "value_type": row["value_type"],
                "min_months": row["min_months"] or 0,
                "max_months": row["max_months"]
            })
    return rules_by_offer


def get_active_contracts(conn, cycle_start, cycle_end):
    """Get all contracts active during the billing cycle"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT c.contract_id, c.contract_code, c.customer_id, c.offer_id,
                   c.start_date, c.end_date, c.loyalty_months, c.discount_pct,
                   cu.customer_code, cu.customer_name
            FROM contract c
            JOIN customer cu ON cu.customer_id = c.customer_id
            WHERE c.start_date <= %s
              AND (c.end_date IS NULL OR c.end_date >= %s)
              AND c.status IN ('ACTIVE', 'SUSPENDED')
            ORDER BY c.customer_id, c.contract_id
        """, (cycle_end, cycle_start))
        return cur.fetchall()


def get_invoices_for_cycle(conn, cycle_id):
    """Get all invoice items for a billing cycle"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT i.invoice_id, i.customer_id, i.total_amount,
                   ii.item_id, ii.contract_id, ii.offer_id,
                   ii.base_amount, ii.discount_amount, ii.final_amount,
                   ii.description
            FROM invoice i
            JOIN invoice_item ii ON ii.invoice_id = i.invoice_id
            WHERE i.cycle_id = %s
            ORDER BY i.customer_id, ii.contract_id
        """, (cycle_id,))
        return cur.fetchall()


def calculate_expected(contract, offer_rules, cycle_month, cycle_year):
    """Calculate expected charge for a contract based on offer rules"""
    offer_data = offer_rules.get(contract["offer_id"])
    if not offer_data:
        return Decimal("0"), Decimal("0"), "Offer not found"

    base_price = Decimal(str(offer_data["base_price"]))
    if base_price == 0:
        return Decimal("0"), Decimal("0"), "Promo offer (zero base)"

    # Calculate months since contract start
    cycle_date = date(cycle_year, cycle_month, 1)
    contract_months = (cycle_date - contract["start_date"]).days // 30

    total_discount = Decimal("0")
    discount_reasons = []

    for rule in offer_data["rules"]:
        if rule["type"] == "BASE_PRICE":
            continue  # Already have base_price

        elif rule["type"] == "LOYALTY_DISCOUNT":
            if (contract_months >= rule["min_months"] and
                contract["loyalty_months"] >= rule["min_months"]):
                if rule["value_type"] == "PERCENT":
                    disc = base_price * Decimal(str(rule["value"])) / 100
                else:
                    disc = Decimal(str(rule["value"]))
                total_discount += disc
                discount_reasons.append(f"Loyalty discount: -${disc:.2f}")

        elif rule["type"] == "PROMO_DISCOUNT":
            max_m = rule["max_months"] or 999
            if rule["min_months"] <= contract_months <= max_m:
                if rule["value_type"] == "PERCENT":
                    disc = base_price * Decimal(str(rule["value"])) / 100
                else:
                    disc = Decimal(str(rule["value"]))
                total_discount += disc
                discount_reasons.append(f"Promo discount: -${disc:.2f}")

        elif rule["type"] == "COMBO_DISCOUNT":
            if rule["value_type"] == "FIXED":
                disc = Decimal(str(rule["value"]))
                total_discount += disc
                discount_reasons.append(f"Combo discount: -${disc:.2f}")

    # Individual contract discount
    if contract["discount_pct"] and contract["discount_pct"] > 0:
        disc = base_price * Decimal(str(contract["discount_pct"])) / 100
        total_discount += disc
        discount_reasons.append(f"Negotiated discount: -${disc:.2f}")

    expected = (base_price - total_discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    expected = max(expected, Decimal("0"))

    reason = "; ".join(discount_reasons) if discount_reasons else "No discounts"
    return expected, total_discount, reason


def classify_gap(expected, billed, discount_reason):
    """Classify the difference between expected and billed amounts"""
    if billed is None:
        return "GAP_MISSING", "Active contract not billed in this cycle"

    diff = billed - expected
    tolerance = Decimal("0.05")  # R$0.05 tolerance for rounding

    if abs(diff) <= tolerance:
        return "MATCH", "Values match"

    # Check if difference can be justified
    pct_diff = abs(diff) / expected * 100 if expected > 0 else Decimal("100")

    if pct_diff <= Decimal("1"):
        return "JUSTIFIED", f"Rounding difference: ${diff:.2f}"

    if diff > 0:
        return "GAP_OVERCHARGE", f"Overcharged ${diff:.2f} ({pct_diff:.1f}%)"
    else:
        return "GAP_UNDERCHARGE", f"Undercharged ${abs(diff):.2f} ({pct_diff:.1f}%)"


def run_ra_for_cycle(conn, cycle_id, cycle_code, cycle_month, cycle_year):
    """Execute RA process for a single billing cycle"""
    print(f"\n{'─'*60}")
    print(f"  Processing cycle: {cycle_code}")
    print(f"{'─'*60}")

    cycle_start = date(cycle_year, cycle_month, 1)
    if cycle_month == 12:
        cycle_end = date(cycle_year, 12, 31)
    else:
        cycle_end = date(cycle_year, cycle_month + 1, 1) - timedelta(days=1)

    # Load data
    offer_rules = get_offer_rules(conn)
    contracts = get_active_contracts(conn, cycle_start, cycle_end)
    invoice_items = get_invoices_for_cycle(conn, cycle_id)

    # Index billed items by contract_id
    billed_by_contract = {}
    for item in invoice_items:
        cid = item["contract_id"]
        if cid not in billed_by_contract:
            billed_by_contract[cid] = []
        billed_by_contract[cid].append(item)

    # Create RA run record
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO ra_run (cycle_id, total_customers, total_contracts, total_invoices, status)
            VALUES (%s, %s, %s, %s, 'RUNNING')
            RETURNING run_id
        """, (cycle_id,
              len(set(c["customer_id"] for c in contracts)),
              len(contracts),
              len(set(i["invoice_id"] for i in invoice_items))))
        run_id = cur.fetchone()[0]

    # Process each contract
    results = {"MATCH": 0, "JUSTIFIED": 0, "GAP_OVERCHARGE": 0,
               "GAP_UNDERCHARGE": 0, "GAP_MISSING": 0}
    total_expected = Decimal("0")
    total_billed = Decimal("0")
    total_gap_value = Decimal("0")

    with conn.cursor() as cur:
        for contract in contracts:
            expected, discount, reason = calculate_expected(
                contract, offer_rules, cycle_month, cycle_year)

            if expected == 0:
                continue  # Skip promo-only offers

            total_expected += expected

            # Find billed amount for this contract
            billed_items = billed_by_contract.get(contract["contract_id"], [])

            if not billed_items:
                # GAP: contract not billed
                status, justification = "GAP_MISSING", "Active contract not billed in this cycle"
                billed_amount = None
                diff = None
                total_gap_value += expected
            else:
                # Sum all charges for this contract (handles duplicates)
                billed_amount = sum(Decimal(str(item["final_amount"])) for item in billed_items)
                total_billed += billed_amount
                diff = billed_amount - expected
                status, justification = classify_gap(expected, billed_amount, reason)

                if status in ("GAP_OVERCHARGE", "GAP_UNDERCHARGE"):
                    total_gap_value += abs(diff)

                # Check for duplicate charges
                if len(billed_items) > 1:
                    descs = [i["description"] for i in billed_items]
                    dups = [d for d in descs if "[DUP]" in str(d)]
                    if dups:
                        status = "GAP_OVERCHARGE"
                        justification = f"Duplicate charge detected ({len(billed_items)} items)"
                        total_gap_value += abs(diff) if diff else expected

            results[status] += 1

            # Insert RA result
            invoice_id = billed_items[0]["invoice_id"] if billed_items else None
            cur.execute("""
                INSERT INTO ra_result (run_id, customer_id, contract_id, invoice_id,
                                      expected_amount, billed_amount, difference, status, justification)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (run_id, contract["customer_id"], contract["contract_id"], invoice_id,
                  float(expected), float(billed_amount) if billed_amount else None,
                  float(diff) if diff else None, status, justification))

        # Update RA run with gap count
        total_gaps = results["GAP_OVERCHARGE"] + results["GAP_UNDERCHARGE"] + results["GAP_MISSING"]
        cur.execute("""
            UPDATE ra_run SET gaps_found = %s, status = 'COMPLETED' WHERE run_id = %s
        """, (total_gaps, run_id))

    conn.commit()

    # Print cycle summary
    total_checks = sum(results.values())
    print(f"  Contracts checked: {total_checks}")
    print(f"  ├── MATCH:          {results['MATCH']:>5} ({results['MATCH']*100/total_checks:.1f}%)")
    print(f"  ├── JUSTIFIED:      {results['JUSTIFIED']:>5} ({results['JUSTIFIED']*100/total_checks:.1f}%)")
    print(f"  ├── GAP_OVERCHARGE: {results['GAP_OVERCHARGE']:>5} ({results['GAP_OVERCHARGE']*100/total_checks:.1f}%)")
    print(f"  ├── GAP_UNDERCHARGE:{results['GAP_UNDERCHARGE']:>5} ({results['GAP_UNDERCHARGE']*100/total_checks:.1f}%)")
    print(f"  └── GAP_MISSING:    {results['GAP_MISSING']:>5} ({results['GAP_MISSING']*100/total_checks:.1f}%)")
    print(f"  Expected:  R$ {total_expected:>12,.2f}")
    print(f"  Billed:    R$ {total_billed:>12,.2f}")
    print(f"  Gap Value: R$ {total_gap_value:>12,.2f}")

    return run_id, results, total_expected, total_billed, total_gap_value


def generate_projections(conn, run_id, cycle_code, active_contracts, offer_rules, cycle_year):
    """Project revenue for next 6 months based on current portfolio"""
    # Calculate current average ticket
    total_monthly = Decimal("0")
    for contract in active_contracts:
        expected, _, _ = calculate_expected(contract, offer_rules, 12, cycle_year)
        total_monthly += expected

    avg_ticket = total_monthly / len(active_contracts) if active_contracts else Decimal("0")

    # Project assuming 2% monthly churn and stable pricing
    churn_rate = Decimal("0.02")
    current_contracts = len(active_contracts)

    with conn.cursor() as cur:
        for i in range(1, 7):
            proj_month = int(cycle_code.split("-")[1]) + i
            proj_year = cycle_year
            if proj_month > 12:
                proj_month -= 12
                proj_year += 1

            projected_contracts = int(current_contracts * (1 - churn_rate) ** i)
            projected_revenue = avg_ticket * projected_contracts

            proj_code = f"{proj_year}-{proj_month:02d}"
            cur.execute("""
                INSERT INTO ra_projection (run_id, cycle_code, projected_revenue, active_contracts, avg_ticket)
                VALUES (%s, %s, %s, %s, %s)
            """, (run_id, proj_code, float(projected_revenue), projected_contracts, float(avg_ticket)))

    conn.commit()
    print(f"\n  Projections generated for next 6 months (avg ticket: R$ {avg_ticket:.2f})")


def main():
    print("=" * 60)
    print("  RA-PoC Revenue Assurance Engine")
    print("=" * 60)

    cycle_filter = None
    if len(sys.argv) > 1:
        cycle_filter = sys.argv[1]  # e.g., "2025-06" to process single cycle
        print(f"  Filter: cycle {cycle_filter}")

    conn = connect_db()
    try:
        # Clear previous RA results
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE ra_projection, ra_result, ra_run CASCADE")
        conn.commit()
        print("  Previous RA results cleared")

        # Get billing cycles
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if cycle_filter:
                cur.execute("SELECT * FROM billing_cycle WHERE cycle_code = %s", (cycle_filter,))
            else:
                cur.execute("SELECT * FROM billing_cycle ORDER BY cycle_year, cycle_month")
            cycles = cur.fetchall()

        if not cycles:
            print("  ERROR: No billing cycles found!")
            return

        print(f"  Cycles to process: {len(cycles)}")

        # Aggregate totals
        grand_expected = Decimal("0")
        grand_billed = Decimal("0")
        grand_gaps = Decimal("0")
        all_results = {"MATCH": 0, "JUSTIFIED": 0, "GAP_OVERCHARGE": 0,
                       "GAP_UNDERCHARGE": 0, "GAP_MISSING": 0}

        last_run_id = None
        for cycle in cycles:
            run_id, results, expected, billed, gaps = run_ra_for_cycle(
                conn, cycle["cycle_id"], cycle["cycle_code"],
                cycle["cycle_month"], cycle["cycle_year"])

            grand_expected += expected
            grand_billed += billed
            grand_gaps += gaps
            for k in all_results:
                all_results[k] += results[k]
            last_run_id = run_id

        # Generate projections based on last cycle
        if last_run_id:
            last_cycle = cycles[-1]
            cycle_start = last_cycle["start_date"]
            cycle_end = last_cycle["end_date"]
            offer_rules = get_offer_rules(conn)
            active_contracts = get_active_contracts(conn, cycle_start, cycle_end)
            generate_projections(conn, last_run_id, last_cycle["cycle_code"],
                               active_contracts, offer_rules, last_cycle["cycle_year"])

        # Grand summary
        total_checks = sum(all_results.values())
        total_gaps = all_results["GAP_OVERCHARGE"] + all_results["GAP_UNDERCHARGE"] + all_results["GAP_MISSING"]

        print(f"\n{'='*60}")
        print(f"  GRAND SUMMARY ({len(cycles)} cycles)")
        print(f"{'='*60}")
        print(f"  Total checks:     {total_checks:>8,}")
        print(f"  Total MATCH:      {all_results['MATCH']:>8,} ({all_results['MATCH']*100/total_checks:.1f}%)")
        print(f"  Total JUSTIFIED:  {all_results['JUSTIFIED']:>8,} ({all_results['JUSTIFIED']*100/total_checks:.1f}%)")
        print(f"  Total GAPS:       {total_gaps:>8,} ({total_gaps*100/total_checks:.1f}%)")
        print(f"  {'─'*40}")
        print(f"  Expected Revenue: R$ {grand_expected:>14,.2f}")
        print(f"  Billed Revenue:   R$ {grand_billed:>14,.2f}")
        print(f"  Total Gap Value:  R$ {grand_gaps:>14,.2f}")
        print(f"  Revenue Leakage:  {grand_gaps*100/grand_expected:.2f}%" if grand_expected > 0 else "")
        print(f"{'='*60}")
        print(f"\n  RA Engine complete!")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
