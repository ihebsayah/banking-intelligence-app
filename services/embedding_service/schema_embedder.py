"""
services/embedding_service/schema_embedder.py

Pre-computes and stores embeddings for all banking schema entities
(domains, tables, semantic entities) into postgres-embeddings.
"""
from __future__ import annotations

import json
import logging
from typing import List, Tuple

import asyncpg

from embedding_computer import EmbeddingComputer

logger = logging.getLogger(__name__)

# ── Static schema catalogue ───────────────────────────────────────────────────

DOMAINS: List[Tuple[str, str]] = [
    ("customer_analysis",    "Analysis of customer data, segments, demographics, and profiles"),
    ("risk_analysis",        "Analysis of fraud, defaults, AML/KYC compliance violations and alerts"),
    ("revenue_analysis",     "Analysis of income, fees, commissions, and overall profitability"),
    ("operational_analysis", "Analysis of transaction volume, throughput, and processing efficiency"),
    ("geographic_analysis",  "Analysis by branch, region, city, state, or territory"),
    ("product_analysis",     "Analysis of banking products, account types, and service performance"),
    ("compliance_analysis",  "Analysis of regulatory compliance, audit findings, and policy adherence"),
    ("transaction_analysis", "Analysis of payments, wire transfers, ACH flows, and settlements"),
]

TABLES: List[Tuple[str, str]] = [
    # Customer
    ("customers",              "Customer master data — identifiers, demographics, KYC status"),
    ("customer_segments",      "Customer segment classification — premium, gold, standard, retail"),
    # Account
    ("accounts",               "Customer accounts — balance, type, status, open date"),
    ("account_types",          "Account type definitions — checking, savings, investment, credit"),
    # Transaction
    ("transactions",           "Financial transactions — amount, date, type, status, channel"),
    ("transaction_details",    "Detailed transaction line items and metadata"),
    # Risk
    ("risk_flags",             "Risk flags and alert records — severity, category, resolution"),
    ("aml_flags",              "AML and KYC violation records"),
    ("fraud_detection",        "Fraud detection alerts and case management"),
    ("credit_risk_scores",     "Credit risk scores — PD, LGD, EAD per customer or account"),
    # Revenue
    ("fees",                   "Fee revenue — service charges, late fees, overdraft fees"),
    ("commissions",            "Commission income from referrals and product sales"),
    ("interest_income",        "Interest income earned on loans and credit products"),
    ("products",               "Banking product catalogue — loans, deposits, insurance"),
    # Branch / Geography
    ("branches",               "Branch master data — name, code, location, manager"),
    ("branch_locations",       "Branch physical addresses and geo-coordinates"),
    ("branch_performance",     "Branch performance metrics — revenue, headcount, customer count"),
    # Compliance
    ("kyc_status",             "KYC verification status per customer"),
    ("audit_logs",             "Immutable audit trail of system actions"),
    ("regulatory_reports",     "Regulatory compliance submissions and findings"),
    # Geographic
    ("regions",                "Geographic region definitions and hierarchy"),
]

SEMANTIC_ENTITIES: List[Tuple[str, str]] = [
    ("customer",    "Unique customer identifier and associated personal data"),
    ("account",     "Customer account and balance information"),
    ("transaction", "Individual financial transaction record"),
    ("branch",      "Physical branch location and performance data"),
    ("product",     "Banking product or financial service offering"),
    ("risk",        "Risk indicators, flags, and credit scores"),
    ("compliance",  "Regulatory compliance status and audit records"),
]


class SchemaEmbedder:
    """
    Computes and persists embeddings for all schema entities into postgres-embeddings.
    Designed to run once at startup; idempotent via DELETE + INSERT.
    """

    def __init__(self, db_url: str, embedder: EmbeddingComputer) -> None:
        self.db_url = db_url
        self.embedder = embedder
        self.pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        self.pool = await asyncpg.create_pool(self.db_url, min_size=2, max_size=5)
        logger.info("asyncpg pool created → postgres-embeddings")

    async def precompute_all_embeddings(self) -> int:
        """
        Compute and store embeddings for all domains, tables, and entities.
        Returns total rows inserted.
        """
        if not self.pool:
            raise RuntimeError("Call initialize() first")

        logger.info("Computing domain embeddings (%d)…", len(DOMAINS))
        domain_texts = [f"{name}: {desc}" for name, desc in DOMAINS]
        domain_vecs  = self.embedder.compute_embeddings_batch(domain_texts)

        logger.info("Computing table embeddings (%d)…", len(TABLES))
        table_texts = [f"{name}: {desc}" for name, desc in TABLES]
        table_vecs  = self.embedder.compute_embeddings_batch(table_texts)

        logger.info("Computing semantic entity embeddings (%d)…", len(SEMANTIC_ENTITIES))
        entity_texts = [f"{name}: {desc}" for name, desc in SEMANTIC_ENTITIES]
        entity_vecs  = self.embedder.compute_embeddings_batch(entity_texts)

        total = 0
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Wipe and reload (idempotent)
                await conn.execute("DELETE FROM schema_embeddings")
                await conn.execute("DELETE FROM domain_categories")

                # Domain categories
                for i, (name, desc) in enumerate(DOMAINS):
                    await conn.execute(
                        """
                        INSERT INTO domain_categories (domain_name, description, embedding)
                        VALUES ($1, $2, $3)
                        """,
                        name, desc, json.dumps(domain_vecs[i]),
                    )
                    total += 1

                # Tables
                for i, (name, desc) in enumerate(TABLES):
                    await conn.execute(
                        """
                        INSERT INTO schema_embeddings (entity_type, entity_name, embedding, metadata)
                        VALUES ($1, $2, $3, $4)
                        """,
                        "table", name, json.dumps(table_vecs[i]),
                        json.dumps({"description": desc}),
                    )
                    total += 1

                # Semantic entities
                for i, (name, desc) in enumerate(SEMANTIC_ENTITIES):
                    await conn.execute(
                        """
                        INSERT INTO schema_embeddings (entity_type, entity_name, embedding, metadata)
                        VALUES ($1, $2, $3, $4)
                        """,
                        "semantic_entity", name, json.dumps(entity_vecs[i]),
                        json.dumps({"description": desc}),
                    )
                    total += 1

        logger.info("Schema embeddings stored: %d rows total", total)
        return total

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
