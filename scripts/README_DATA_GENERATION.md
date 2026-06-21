# Tunisian Banking Data Generation Tool

This script (`scripts/generate_tunisian_banking_data.py`) generates a relationally consistent, deterministic dataset representing Tunisian banking activities. The data is targeted specifically at analytical dashboards, risk calculations (NPL ratios, provision coverage), and compliance audits.

## Target Tables Populated
The script populates **54 tables** including:
- **Core Tables**: `customers`, `accounts`, `transactions`, `branches`, `products`, `risk_flags`.
- **Loan Domain**: `loan_products`, `loan_contracts`, `loan_installments`, `loan_repayments`, `loan_delinquency_events`, `loan_restructuring`, `collateral`, `guarantees`, `provisions`, `non_performing_loans`.
- **KYC & AML Domains**: `kyc_cases`, `kyc_documents`, `kyc_reviews`, `kyc_verifications`, `kyc_expirations`, `pep_screening`, `sanctions_screening`, `aml_alerts`, `suspicious_activity_reports`, `compliance_cases`, `compliance_reviews`, `audit_findings`.
- **Finance & GL Domains**: `general_ledger`, `ledger_entries`, `fee_income`, `interest_income`, `operating_expenses`, `profitability_metrics`, `balance_sheet_snapshots`, `income_statement_snapshots`.
- **Organization & Extensions**: `regions`, `departments`, `business_units`, `employees`, `relationship_managers`, `customer_profiles`, `customer_addresses`, `customer_contacts`, `customer_preferences`, `customer_status_history`, `account_types`, `account_balances`, `account_status_history`, `joint_accounts`, `account_signatories`.

## Design Assumptions
1. **Determinism**: Use `--seed 42` (default) to guarantee identical outputs on every run.
2. **Tunisia-Native**: Uses TND currency, Tunisian cities (Tunis, Sfax, Sousse, etc.), and governorate mappings. Governorates are grouped into 5 regional divisions (Grand Tunis, Nord, Sahel, Sfax, Sud).
3. **Geographical Weights**: Population and customer distribution weights reflect actual Tunisian demographics (Grand Tunis ~40%, Sfax ~15%, Sousse ~10%).
4. **Relational Consistency**: Foreign keys are strictly maintained. Every loan belongs to a real customer and is backed by a real account. Transactions link to valid accounts.

## Usage

Generate the default seed dataset:
```bash
./scripts/generate_tunisian_banking_data.py --customers 2000 --accounts 5000 --transactions 50000 --loans 1500 --months 24 --seed 42 --output init/09-tunisian-banking-data-seed.sql
```

### CLI Options:
- `--customers`: Number of customers (default: 2000)
- `--accounts`: Number of accounts (default: 5000)
- `--loans`: Number of loan contracts (default: 1500)
- `--transactions`: Number of transactions (default: 50000)
- `--months`: Months of historical snapshots/time-series (default: 24)
- `--seed`: Random seed (default: 42)
- `--output`: File path to output SQL INSERT statements (default: `init/09-tunisian-banking-data-seed.sql`)

## Running the Migration Seed
Once the SQL file is generated, it will be automatically applied when the postgres-main container boots (if mounted). Alternatively, you can apply it manually to a running database:
```bash
psql -h localhost -U banking_user -d banking_dev -f init/09-tunisian-banking-data-seed.sql
```
