#!/usr/bin/env python3
"""Reset the alert-driven operational workbench and inject fresh demo data.

- banking_integration: clears the entire alert pipeline (alerts, investigations,
  compliance_cases, information_requests, and all linked aggregations) in FK-safe
  order, then inserts a fresh set of alerts linked to new customers.
- banking_dev: upserts a set of brand-new customer records (the real Customer 360
  source) so that the injected alerts resolve to legitimate customers.

Idempotent: safe to re-run. Delete step removes whatever is there; customer upsert
uses ON CONFLICT; alert insert is unconditional (previous alerts are deleted first).

DSNs override:
  INTEGRATION_DATABASE_URL, MAIN_DATABASE_URL
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

import asyncpg

IG_DSN = os.environ.get(
    "INTEGRATION_DATABASE_URL",
    "postgresql://integration_user:integrationpass123@localhost:5435/banking_integration",
)
MAIN_DSN = os.environ.get(
    "MAIN_DATABASE_URL",
    "postgresql://banking_user:securepass123@localhost:5432/banking_dev",
)

# Delete child-first. Order is critical for FK integrity.
DELETE_ORDER = [
    "investigation_attachments",
    "investigation_report_submissions",
    "investigation_review_decisions",
    "decisions",
    "approval_decisions",
    "information_requests",
    "compliance_reviews",
    "compliance_cases",
    "investigations",
    "alerts",
    # Polymorphic aggregations (only alert-workflow entity types exist here)
    "activity_timeline",
    "comments",
    "notifications",
    "approval_requests",
    "assignment_history",
    "audit_outbox",
]

# New customers -> (customer_id, name, email, phone, kyc_verified, risk_score, segment)
NEW_CUSTOMERS = [
    ("CUST_10001", "Amel Belhadj",     "amel.belhadj10001@mail.tn",  "21620110001", True,  0.72, "PART_PREM"),
    ("CUST_10002", "Tarek Bahri",       "tarek.bahri10002@mail.tn",   "21620210002", True,  0.61, "PART_MASS"),
    ("CUST_10003", "Nour Jebali",       "nour.jebali10003@mail.tn",   "21620310003", False, 0.55, "CORP_SME"),
    ("CUST_10004", "Sami Ben Romdhane", "sami.benromdhane10004@mail.tn", "21620410004", True, 0.81, "CORP_LARGE"),
    ("CUST_10005", "Rim Bouzid",        "rim.bouzid10005@mail.tn",    "21620510005", True,  0.38, "PART_MASS"),
    ("CUST_10006", "Hela Mansour",      "hela.mansour10006@mail.tn",  "21620610006", True,  0.66, "PART_PREM"),
    ("CUST_10007", "Mohamed Karoui",    "mohamed.karoui10007@mail.tn","21620710007", False, 0.74, "CORP_SME"),
    ("CUST_10008", "Ines Sassi",        "ines.sassi10008@mail.tn",    "21620810008", True,  0.29, "PART_MASS"),
    ("CUST_10009", "Walid Ben Youssef", "walid.benyoussef10009@mail.tn", "21620910009", True, 0.48, "PART_MASS"),
    ("CUST_10010", "Yosra Hamdi",       "yosra.hamdi10010@mail.tn",   "21621010010", True,  0.85, "PART_PREM"),
]

# (alert_type, severity, title, related_customer_idx, status, assigned_to)
NEW_ALERTS = [
    ("transaction_anomaly", "critical", "Unusual large cash deposit followed by rapid transfer", 0, "assigned", "analyst_001"),
    ("risk_threshold",      "high",     "Repeated same-day transfers exceeding risk threshold",   0, "assigned", "analyst_001"),
    ("pattern_match",       "medium",   "Structurring pattern: deposits just below reporting limit", 1, "acknowledged", "analyst"),
    ("kpi_breach",          "low",      "KPI breach: dormant to active account velocity",         1, "new", None),
    ("transaction_anomaly", "high",     "Rapid round-trip transfer between linked accounts",      2, "assigned", "analyst_001"),
    ("system_rule",         "medium",   "System rule: beneficiary matches watchlist fragment",    2, "acknowledged", "analyst"),
    ("risk_threshold",      "critical", "Entity concentration: multiple accounts, one beneficiary", 3, "assigned", "analyst_001"),
    ("pattern_match",       "high",     "Circular flow across three accounts within 48h",          3, "acknowledged", "analyst"),
    ("transaction_anomaly", "low",      "Minor anomaly: weekend high-value transfer",              4, "new", None),
    ("kpi_breach",          "medium",   "KPI breach: transaction count above band",                4, "assigned", "analyst_001"),
    ("risk_threshold",      "high",     "High-risk jurisdiction: inbound transfer flagged",        5, "acknowledged", "analyst"),
    ("transaction_anomaly", "critical", "Immediate flag: same-day ATM + online withdrawal spike",  5, "assigned", "analyst_001"),
    ("system_rule",         "medium",   "System rule: duplicate counterparty concentration",       6, "new", None),
    ("pattern_match",       "low",      "Threshold rounding pattern across 5 deposits",            6, "acknowledged", "analyst"),
    ("transaction_anomaly", "high",     "Overnight transfer loop to offshore entity",              7, "assigned", "analyst_001"),
    ("risk_threshold",      "medium",   "Customer risk score re-evaluation triggered alert",       7, "new", None),
    ("kpi_breach",          "low",      "KPI breach: loan drawdown velocity",                      8, "acknowledged", "analyst"),
    ("pattern_match",       "critical", "Shell-company purchase pattern matched",                  8, "assigned", "analyst_001"),
    ("transaction_anomaly", "high",     "Unusual high-value cross-border wire",                    9, "acknowledged", "analyst"),
    ("risk_threshold",      "medium",   "Adverse media + transaction spike correlation",           9, "assigned", "analyst_001"),
]


async def delete_workflow(ig: asyncpg.Connection) -> None:
    for table in DELETE_ORDER:
        row = await ig.fetchval(f"SELECT count(*) FROM {table}")
        if row:
            await ig.execute(f"DELETE FROM {table}")
            print(f"  cleared {table} ({row} rows)")
        else:
            print(f"  {table} already empty")


async def inject_customers(main: asyncpg.Connection) -> None:
    for cid, name, email, phone, kyc, risk, seg in NEW_CUSTOMERS:
        await main.execute(
            """
            INSERT INTO customers (customer_id, name, email, phone, kyc_verified, risk_score, segment)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (customer_id) DO UPDATE SET
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                phone = EXCLUDED.phone,
                kyc_verified = EXCLUDED.kyc_verified,
                risk_score = EXCLUDED.risk_score,
                segment = EXCLUDED.segment
            """,
            cid, name, email, phone, kyc, risk, seg,
        )
    print(f"  upserted {len(NEW_CUSTOMERS)} customers into banking_dev.customers")


async def inject_alerts(ig: asyncpg.Connection) -> None:
    for alert_type, severity, title, cidx, status, assigned_to in NEW_ALERTS:
        customer_id = NEW_CUSTOMERS[cidx][0]
        await ig.execute(
            """
            INSERT INTO alerts
              (alert_id, alert_type, severity, title, status,
               related_entity_type, related_entity_id, assigned_to,
               source_rule_type, source_rule_id, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, 'customer', $6, $7, 'workbench_demo', NULL, NOW(), NOW())
            """,
            uuid.uuid4(), alert_type, severity, title, status, customer_id, assigned_to,
        )
    print(f"  inserted {len(NEW_ALERTS)} alerts into banking_integration.alerts")


async def main() -> None:
    ig = await asyncpg.connect(IG_DSN)
    main = await asyncpg.connect(MAIN_DSN)
    try:
        print("STEP 1: clearing alert workflow (integration)")
        async with ig.transaction():
            await delete_workflow(ig)

        print("STEP 2: upserting new customers (banking_dev)")
        async with main.transaction():
            await inject_customers(main)

        print("STEP 3: injecting new alerts (integration)")
        async with ig.transaction():
            await inject_alerts(ig)

        print("DONE")
    finally:
        await ig.close()
        await main.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
