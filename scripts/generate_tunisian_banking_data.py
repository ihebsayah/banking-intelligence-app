#!/usr/bin/env python3
"""
scripts/generate_tunisian_banking_data.py
Deterministic Tunisian synthetic data generator for Phase 6A.
Generates relationally consistent, high-quality data spanning 24 months.
Produces a SQL seed file with INSERT statements.
"""
import argparse
import random
import sys
import os
from datetime import datetime, timedelta

def escape_sql(s: str) -> str:
    """Escape a string value for safe embedding inside PostgreSQL single-quoted literals."""
    return s.replace("'", "''")


def main():
    parser = argparse.ArgumentParser(description="Tunisian Banking Synthetic Data Generator")
    parser.add_argument("--customers", type=int, default=2000, help="Number of customers to generate")
    parser.add_argument("--accounts", type=int, default=5000, help="Number of accounts to generate")
    parser.add_argument("--transactions", type=int, default=50000, help="Number of transactions to generate")
    parser.add_argument("--loans", type=int, default=1500, help="Number of loans to generate")
    parser.add_argument("--months", type=int, default=24, help="Time-series depth in months")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for determinism")
    parser.add_argument("--output", type=str, default="init/09-tunisian-banking-data-seed.sql", help="Output SQL file path")
    args = parser.parse_args()

    random.seed(args.seed)
    
    print(f"Generating synthetic Tunisian banking data with seed={args.seed}...")
    print(f"Target: {args.customers} customers, {args.accounts} accounts, {args.loans} loans, {args.transactions} transactions over {args.months} months.")

    # 1. Names and lists
    first_names_m = ["Mohamed", "Ahmed", "Youssef", "Hamza", "Ali", "Omar", "Khalil", "Slim", "Khaled", "Anis", "Hassen", "Walid", "Sami", "Karim", "Zied", "Firas", "Amine", "Ramzi", "Tarek", "Mahdi"]
    first_names_f = ["Faten", "Amel", "Ines", "Meriam", "Yasmine", "Sarah", "Olfa", "Rania", "Sonia", "Jihene", "Salma", "Leila", "Mouna", "Nour", "Hela", "Chaima", "Mariem", "Sirine", "Rym", "Eya"]
    last_names = ["Trabelsi", "Chaabane", "Gharbi", "Dridi", "Ayari", "Ellouze", "Rekik", "Fakhfakh", "Abid", "Bouazizi", "Selmi", "Mansouri", "Hammami", "Riahi", "Ben Amara", "Jemli", "Oueslati", "Saidi", "Guesmi", "Masmoudi", "Mejri", "Jlassi", "Ben Ali", "Haddad", "Mathlouthi"]
    
    tunisian_cities = [
        # (city, governorate, weight)
        ("Tunis", "Tunis", 0.20),
        ("Ariana", "Ariana", 0.08),
        ("Ben Arous", "Ben Arous", 0.07),
        ("Manouba", "Manouba", 0.05),
        ("Sfax", "Sfax", 0.15),
        ("Sousse", "Sousse", 0.10),
        ("Nabeul", "Nabeul", 0.08),
        ("Bizerte", "Bizerte", 0.07),
        ("Gabès", "Gabès", 0.05),
        ("Monastir", "Monastir", 0.05),
        ("Kairouan", "Kairouan", 0.05),
        ("Gafsa", "Gafsa", 0.03),
        ("Béja", "Béja", 0.02)
    ]
    
    cities_flat = []
    cities_weights = []
    for c, g, w in tunisian_cities:
        cities_flat.append((c, g))
        cities_weights.append(w)

    def get_random_city():
        return random.choices(cities_flat, weights=cities_weights, k=1)[0]

    # Predefined lists
    segments = [
        ("PART_MASS", "Particulier Standard", 0.70, 0.00, 0.00),
        ("PART_PREM", "Particulier Premium", 0.20, 10000.00, 36000.00),
        ("CORP_SME", "PME / Professionnel", 0.08, 20000.00, 80000.00),
        ("CORP_LARGE", "Grande Entreprise", 0.02, 100000.00, 500000.00)
    ]
    
    # 2. Start SQL Output
    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
        
    sql_file = open(args.output, "w", encoding="utf-8")
    sql_file.write("-- =============================================================================\n")
    sql_file.write(f"-- Tunisian Banking Synthetic Seed Data (Deterministic, Seed={args.seed})\n")
    sql_file.write(f"-- Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    sql_file.write("-- =============================================================================\n\n")
    sql_file.write("BEGIN;\n\n")

    # Disable constraints temporarily for clean insert
    sql_file.write("SET CONSTRAINTS ALL DEFERRED;\n\n")

    # Clean existing data to avoid PK clashes on rerun
    sql_file.write("TRUNCATE TABLE non_performing_loans CASCADE;\n")
    sql_file.write("TRUNCATE TABLE provisions CASCADE;\n")
    sql_file.write("TRUNCATE TABLE collateral CASCADE;\n")
    sql_file.write("TRUNCATE TABLE guarantees CASCADE;\n")
    sql_file.write("TRUNCATE TABLE loan_repayments CASCADE;\n")
    sql_file.write("TRUNCATE TABLE loan_installments CASCADE;\n")
    sql_file.write("TRUNCATE TABLE loan_contracts CASCADE;\n")
    sql_file.write("TRUNCATE TABLE loan_products CASCADE;\n")
    sql_file.write("TRUNCATE TABLE aml_alerts CASCADE;\n")
    sql_file.write("TRUNCATE TABLE suspicious_activity_reports CASCADE;\n")
    sql_file.write("TRUNCATE TABLE kyc_cases CASCADE;\n")
    sql_file.write("TRUNCATE TABLE kyc_documents CASCADE;\n")
    sql_file.write("TRUNCATE TABLE kyc_reviews CASCADE;\n")
    sql_file.write("TRUNCATE TABLE kyc_verifications CASCADE;\n")
    sql_file.write("TRUNCATE TABLE kyc_expirations CASCADE;\n")
    sql_file.write("TRUNCATE TABLE pep_screening CASCADE;\n")
    sql_file.write("TRUNCATE TABLE sanctions_screening CASCADE;\n")
    sql_file.write("TRUNCATE TABLE compliance_cases CASCADE;\n")
    sql_file.write("TRUNCATE TABLE compliance_reviews CASCADE;\n")
    sql_file.write("TRUNCATE TABLE audit_findings CASCADE;\n")
    sql_file.write("TRUNCATE TABLE ledger_entries CASCADE;\n")
    sql_file.write("TRUNCATE TABLE fee_income CASCADE;\n")
    sql_file.write("TRUNCATE TABLE interest_income CASCADE;\n")
    sql_file.write("TRUNCATE TABLE operating_expenses CASCADE;\n")
    sql_file.write("TRUNCATE TABLE profitability_metrics CASCADE;\n")
    sql_file.write("TRUNCATE TABLE balance_sheet_snapshots CASCADE;\n")
    sql_file.write("TRUNCATE TABLE income_statement_snapshots CASCADE;\n")
    sql_file.write("TRUNCATE TABLE general_ledger CASCADE;\n")
    sql_file.write("TRUNCATE TABLE relationship_managers CASCADE;\n")
    sql_file.write("TRUNCATE TABLE employees CASCADE;\n")
    sql_file.write("TRUNCATE TABLE departments CASCADE;\n")
    sql_file.write("TRUNCATE TABLE business_units CASCADE;\n")
    sql_file.write("TRUNCATE TABLE customer_profiles CASCADE;\n")
    sql_file.write("TRUNCATE TABLE customer_segments CASCADE;\n")
    sql_file.write("TRUNCATE TABLE customer_addresses CASCADE;\n")
    sql_file.write("TRUNCATE TABLE customer_contacts CASCADE;\n")
    sql_file.write("TRUNCATE TABLE customer_risk_scores CASCADE;\n")
    sql_file.write("TRUNCATE TABLE customer_relationships CASCADE;\n")
    sql_file.write("TRUNCATE TABLE customer_documents CASCADE;\n")
    sql_file.write("TRUNCATE TABLE customer_preferences CASCADE;\n")
    sql_file.write("TRUNCATE TABLE customer_status_history CASCADE;\n")
    sql_file.write("TRUNCATE TABLE account_balances CASCADE;\n")
    sql_file.write("TRUNCATE TABLE account_status_history CASCADE;\n")
    sql_file.write("TRUNCATE TABLE joint_accounts CASCADE;\n")
    sql_file.write("TRUNCATE TABLE account_signatories CASCADE;\n")
    sql_file.write("TRUNCATE TABLE account_types CASCADE;\n")
    sql_file.write("TRUNCATE TABLE regions CASCADE;\n")
    # Clean standard tables too, ensuring full clean state
    sql_file.write("TRUNCATE TABLE transactions CASCADE;\n")
    sql_file.write("TRUNCATE TABLE risk_flags CASCADE;\n")
    sql_file.write("TRUNCATE TABLE accounts CASCADE;\n")
    sql_file.write("TRUNCATE TABLE customers CASCADE;\n")
    sql_file.write("TRUNCATE TABLE branches CASCADE;\n")
    sql_file.write("TRUNCATE TABLE products CASCADE;\n\n")

    # 3. Regions Seed
    regions = [
        ("REG_TUNIS", "Grand Tunis", ["Tunis", "Ariana", "Ben Arous", "Manouba"], 2800000, 35.5),
        ("REG_NORD", "Nord-Est & Ouest", ["Bizerte", "Béja", "Jendouba", "Kef", "Siliana", "Zaghouan"], 1500000, 12.0),
        ("REG_SAHEL", "Sahel & Centre", ["Sousse", "Monastir", "Mahdia", "Kairouan"], 2200000, 22.5),
        ("REG_SFAX", "Région Sfax", ["Sfax"], 1000000, 15.0),
        ("REG_SUD", "Sud Tunisien", ["Gabès", "Medenine", "Tataouine", "Tozeur", "Kebili", "Gafsa"], 1200000, 15.0)
    ]
    for rid, name, gov_list, pop, gdp in regions:
        govs_str = "ARRAY[" + ",".join([f"'{g}'" for g in gov_list]) + "]"
        sql_file.write(f"INSERT INTO regions (region_id, region_name_fr, governorates, population, gdp_contribution) VALUES ('{rid}', '{name}', {govs_str}, {pop}, {gdp}) ON CONFLICT DO NOTHING;\n")
    sql_file.write("\n")

    # 4. Branches Seed (30 branches across regions)
    branch_ids = []
    branch_regions = {}
    for i in range(1, 31):
        bid = f"BR_{i:03d}"
        branch_ids.append(bid)
        name = f"Agence {random.choice(['La Fayette', 'Ennasr', 'Lac 2', 'El Ghazala', 'Sfax Medina', 'Sousse Corniche', 'Bizerte Port', 'Gabès Centre', 'Kairouan Centre', 'Djerba Houmt Souk', 'Menezel Temime', 'Ariana Centre', 'Ben Arous Ville', 'Béja Ville'])} {i}"
        city_data = get_random_city()
        city, gov = city_data
        
        # Match region
        matched_rid = "REG_TUNIS"
        for rid, _, gov_list, _, _ in regions:
            if gov in gov_list:
                matched_rid = rid
                break
        branch_regions[bid] = matched_rid
        
        sql_file.write(f"INSERT INTO branches (branch_id, name, state, city, manager_id, region_id) VALUES ('{bid}', '{name}', '{gov}', '{city}', 'MGR_{i:03d}', '{matched_rid}') ON CONFLICT DO NOTHING;\n")
    sql_file.write("\n")

    # 5. Products Seed
    prods = [
        ("PROD_CHQ", "Compte Chèque Retail", "compte"),
        ("PROD_SAV", "Compte Épargne Classique", "épargne"),
        ("PROD_CARTE_GOLD", "Carte Gold Visa", "carte"),
        ("PROD_CARTE_PREM", "Carte Platinum Premium", "carte"),
        ("PROD_ASSUR_VIE", "Assurance Vie El Amana", "assurance")
    ]
    for pid, name, cat in prods:
        sql_file.write(f"INSERT INTO products (product_id, name, category, description) VALUES ('{pid}', '{escape_sql(name)}', '{escape_sql(cat)}', 'Produit standard {escape_sql(name)}') ON CONFLICT DO NOTHING;\n")
    sql_file.write("\n")

    # 6. Customer Segments
    for sid, name, _, min_b, min_inc in segments:
        sql_file.write(f"INSERT INTO customer_segments (segment_id, segment_name, segment_label_fr, min_balance, min_annual_income) VALUES ('{sid}', '{name}', '{name}', {min_b or 0.00}, {min_inc or 0.00});\n")
    sql_file.write("\n")

    # 7. Account Types
    acc_types = [
        ("checking", "Compte Courant", "Checking Account", 0.0000, 0.00, 10000000.00),
        ("savings", "Compte d'Épargne", "Savings Account", 0.0425, 10.00, 5000000.00),
        ("deposit", "Dépôt à Terme (DAT)", "Term Deposit", 0.0550, 5000.00, 20000000.00)
    ]
    for code, fr, en, rate, min_b, max_b in acc_types:
        sql_file.write(f"INSERT INTO account_types (type_code, type_name_fr, type_name_en, interest_rate, min_balance, max_balance) VALUES ('{code}', '{escape_sql(fr)}', '{escape_sql(en)}', {rate}, {min_b}, {max_b});\n")
    sql_file.write("\n")

    # 8. Departments & Business Units
    depts = [("DEP_RISK", "Risque", "Risk"), ("DEP_COMP", "Conformité", "Compliance"), ("DEP_COMM", "Commercial", "Commercial"), ("DEP_OPS", "Opérations", "Operations"), ("DEP_IT", "Informatique", "IT")]
    for did, fr, en in depts:
        sql_file.write(f"INSERT INTO departments (department_id, name_fr, name_en) VALUES ('{did}', '{fr}', '{en}');\n")
    sql_file.write("\n")

    bus = [("BU_RETAIL", "Retail Banking", "Retail Banking"), ("BU_CORP", "Corporate Banking", "Corporate Banking"), ("BU_WEALTH", "Wealth Management", "Wealth Management")]
    for bu_id, fr, en in bus:
        sql_file.write(f"INSERT INTO business_units (unit_id, name_fr, name_en) VALUES ('{bu_id}', '{fr}', '{en}');\n")
    sql_file.write("\n")

    # 9. Employees (Relationship Managers, Analysts, etc. - 100 employees)
    employee_ids = []
    rm_ids = []
    for i in range(1, 101):
        emp_id = f"EMP_{i:03d}"
        employee_ids.append(emp_id)
        
        is_rm = i <= 60 # 60 RMs
        role = "relationship_manager" if is_rm else random.choice(["analyst", "manager", "compliance"])
        dept = "DEP_COMM" if is_rm else ("DEP_RISK" if role == "analyst" else ("DEP_COMP" if role == "compliance" else "DEP_OPS"))
        title = "Chargé de Clientèle" if is_rm else f"Analyste {dept[4:]}"
        
        fname = random.choice(first_names_m) if i % 2 == 0 else random.choice(first_names_f)
        lname = random.choice(last_names)
        bid = random.choice(branch_ids)
        email = f"{fname.lower()}.{lname.lower()}{i}@reportingbank.com.tn"
        hire_date = (datetime.now() - timedelta(days=random.randint(365, 365*5))).strftime("%Y-%m-%d")
        
        sql_file.write(f"INSERT INTO employees (employee_id, branch_id, department_id, first_name, last_name, title, role, hire_date, email) VALUES ('{emp_id}', '{bid}', '{dept}', '{fname}', '{lname}', '{title}', '{role}', '{hire_date}', '{email}');\n")
        
        if is_rm:
            rm_ids.append(emp_id)
    sql_file.write("\n")

    # 10. Loan Products
    loan_prods = [
        ("LP_IMMO", "Crédit Immobilier", "Financement de biens immobiliers résidentiels", 10000.00, 500000.00, 0.0825, 0.1150, 60, 300),
        ("LP_CONSO", "Crédit à la Consommation", "Prêts personnels à court terme", 1000.00, 30000.00, 0.1050, 0.1450, 12, 60),
        ("LP_AUTO", "Crédit Automobile", "Financement d'achat de véhicules", 5000.00, 80000.00, 0.0950, 0.1250, 12, 84),
        ("LP_PRO", "Crédit Professionnel", "Financement d'investissements professionnels", 5000.00, 1000000.00, 0.0750, 0.1050, 12, 120)
    ]
    for lpid, name, desc, min_a, max_a, min_r, max_r, min_t, max_t in loan_prods:
        sql_file.write(f"INSERT INTO loan_products (loan_product_id, name, description, min_amount, max_amount, min_interest_rate, max_interest_rate, min_term_months, max_term_months) VALUES ('{lpid}', '{escape_sql(name)}', '{escape_sql(desc)}', {min_a}, {max_a}, {min_r}, {max_r}, {min_t}, {max_t});\n")
    sql_file.write("\n")

    # 11. General Ledger
    gl_accounts = [
        ("1000", "Actifs de Caisse", "actif"),
        ("1100", "Placements Interbancaires", "actif"),
        ("1200", "Portefeuille Crédits Clients", "actif"),
        ("1290", "Provisions pour Pertes sur Crédits", "actif"), # contra-asset (asset reduction)
        ("2000", "Dépôts de la Clientèle", "passif"),
        ("2100", "Emprunts Interbancaires", "passif"),
        ("3000", "Capitaux Propres", "passif"),
        ("4000", "Intérêts perçus sur Crédits", "produit"),
        ("4100", "Commissions sur Services", "produit"),
        ("5000", "Charges d'Intérêts payées", "charge"),
        ("5100", "Charges de Personnel", "charge"),
        ("5200", "Charges Locatives et Matériel", "charge")
    ]
    for code, fr, atype in gl_accounts:
        sql_file.write(f"INSERT INTO general_ledger (account_code, account_name_fr, account_type) VALUES ('{code}', '{escape_sql(fr)}', '{atype}');\n")
    sql_file.write("\n")

    # 12. Customers & Extensions
    print("Generating customers...")
    customer_ids = []
    segment_dist = random.choices([s[0] for s in segments], weights=[s[2] for s in segments], k=args.customers)
    
    for idx in range(1, args.customers + 1):
        cust_id = f"CUST_{idx:05d}"
        customer_ids.append(cust_id)
        
        seg = segment_dist[idx-1]
        is_m = idx % 2 == 0
        fname = random.choice(first_names_m) if is_m else random.choice(first_names_f)
        lname = random.choice(last_names)
        name = f"{fname} {lname}"
        
        email = f"{fname.lower()}.{lname.lower()}{idx}@mail.tn"
        phone = f"216{random.choice([9, 5, 2, 7])}{random.randint(1000000, 9999999)}"
        
        kyc = random.choices([True, False], weights=[0.85, 0.15], k=1)[0]
        # PEP is very rare
        pep = random.choices([True, False], weights=[0.015, 0.985], k=1)[0]
        
        risk = round(random.uniform(0.05, 0.90) if not pep else random.uniform(0.65, 0.98), 2)
        
        # Write customers table row
        sql_file.write(f"INSERT INTO customers (customer_id, name, email, phone, kyc_verified, risk_score, segment) VALUES ('{cust_id}', '{name}', '{email}', '{phone}', {str(kyc).lower()}, {risk}, '{seg}');\n")
        
        # Write customer_profiles table row
        dob = (datetime.now() - timedelta(days=random.randint(18*365, 75*365))).strftime("%Y-%m-%d")
        gender = 'M' if is_m else 'F'
        cin = f"{random.randint(0, 1)}{random.randint(1000000, 9999999):07d}"
        income = round(random.uniform(8000, 35000) if seg == "PART_MASS" else (random.uniform(35000, 120000) if seg == "PART_PREM" else random.uniform(80000, 800000)), 2)
        net_worth = "<50K" if income < 20000 else ("50K-200K" if income < 70000 else ("200K-1M" if income < 250000 else ">1M"))
        employer = random.choice(["Tunisie Telecom", "STEG", "SONEDE", "Société Privée", "Cabinet Médical", "Enseignant", "Tunisair", "Banque Centrale", "Ministère Éducation", "Auto-entrepreneur"])
        
        pep_details = "NULL" if not pep else "'Membre de l''administration publique'"
        sql_file.write(f"INSERT INTO customer_profiles (customer_id, date_of_birth, gender, national_id, employment_status, employer_name, annual_income, net_worth_band, politically_exposed, pep_details) VALUES ('{cust_id}', '{dob}', '{gender}', '{cin}', 'actif', '{employer}', {income}, '{net_worth}', {str(pep).lower()}, {pep_details});\n")
        
        # Write customer_addresses table row
        city_data = get_random_city()
        city, gov = city_data
        postal = f"{random.randint(10, 99):02d}{random.randint(0, 99):02d}"
        sql_file.write(f"INSERT INTO customer_addresses (customer_id, address_type, address_line1, city, governorate, postal_code, is_primary) VALUES ('{cust_id}', 'domicile', 'Rue de la Liberté', '{city}', '{gov}', '{postal}', true);\n")
        
        # Write customer_contacts table row
        sql_file.write(f"INSERT INTO customer_contacts (customer_id, contact_type, contact_value, is_primary, verified) VALUES ('{cust_id}', 'mobile', '{phone}', true, true);\n")
        
        # Write customer_preferences table row
        sql_file.write(f"INSERT INTO customer_preferences (customer_id, language, contact_channel) VALUES ('{cust_id}', 'fr', 'email');\n")
        
        # RM assignment
        rm = random.choice(rm_ids)
        sql_file.write(f"INSERT INTO relationship_managers (employee_id, customer_id, portfolio_type) VALUES ('{rm}', '{cust_id}', '{seg.replace('PART_','').replace('CORP_','')}') ON CONFLICT (customer_id) DO NOTHING;\n")

    sql_file.write("\n")

    # 13. Accounts & Extensions
    print("Generating accounts...")
    account_ids = []
    account_customer_map = {}
    account_branch_map = {}
    account_balance_map = {}
    
    # Generate accounts for each customer
    acc_idx = 1
    for cust_id in customer_ids:
        # At least 2 accounts, up to 4 accounts (guarantees ~5000+ across 2000 customers)
        num_accs = random.randint(2, 4)
        for _ in range(num_accs):
            if acc_idx > args.accounts and len(account_ids) >= args.customers:
                break # satisfy the count
                
            acc_id = f"ACC_{acc_idx:05d}"
            account_ids.append(acc_id)
            account_customer_map[acc_id] = cust_id
            
            atype = "checking" if len(account_ids) == acc_idx else random.choice(["checking", "savings", "deposit"])
            status = random.choices(["active", "dormant", "closed"], weights=[0.92, 0.06, 0.02], k=1)[0]
            
            balance = round(random.uniform(50, 5000) if atype == "checking" else (random.uniform(500, 25000) if atype == "savings" else random.uniform(10000, 150000)), 2)
            if status == "closed":
                balance = 0.00
                
            avail_balance = balance if balance >= 0 else 0.00
            bid = random.choice(branch_ids)
            account_branch_map[acc_id] = bid
            account_balance_map[acc_id] = balance
            
            created_at = (datetime.now() - timedelta(days=random.randint(180, 720))).strftime("%Y-%m-%d %H:%M:%S")
            
            sql_file.write(f"INSERT INTO accounts (account_id, customer_id, account_type, status, balance, available_balance, currency, branch_id, created_at) VALUES ('{acc_id}', '{cust_id}', '{atype}', '{status}', {balance}, {avail_balance}, 'TND', '{bid}', '{created_at}');\n")
            acc_idx += 1
            
    # Also generate joint accounts (5% of accounts)
    for i in range(1, int(len(account_ids)*0.05) + 1):
        acc = random.choice(account_ids)
        cust = random.choice(customer_ids)
        if account_customer_map[acc] != cust:
            sql_file.write(f"INSERT INTO joint_accounts (account_id, customer_id, relationship) VALUES ('{acc}', '{cust}', 'conjoint') ON CONFLICT DO NOTHING;\n")

    sql_file.write("\n")

    # 14. Loans Domain
    print("Generating loans...")
    loan_ids = []
    for l_idx in range(1, args.loans + 1):
        loan_id = f"LOAN_{l_idx:05d}"
        loan_ids.append(loan_id)
        
        cust_id = random.choice(customer_ids)
        # Find their checking account to link to
        linked_acc = None
        for acc_id, cid in account_customer_map.items():
            if cid == cust_id:
                linked_acc = acc_id
                break
        if not linked_acc:
            linked_acc = random.choice(account_ids)
            
        lp = random.choice(loan_prods)
        lpid = lp[0]
        ltype = lp[0].replace("LP_", "").lower()
        min_a, max_a, min_r, max_r, min_t, max_t = lp[3], lp[4], lp[5], lp[6], lp[7], lp[8]
        
        principal = round(random.uniform(min_a, max_a), 2)
        rate = round(random.uniform(min_r, max_r), 4)
        term = random.randint(min_t, max_t)
        
        # Installment simple calculation
        installment = round((principal * (1 + rate)) / term, 2)
        
        disb_date_dt = datetime.now() - timedelta(days=random.randint(90, 720))
        disb_date = disb_date_dt.strftime("%Y-%m-%d")
        mat_date = (disb_date_dt + timedelta(days=term * 30)).strftime("%Y-%m-%d")
        
        status = random.choices(["actif", "remboursé", "en_retard", "contentieux", "restructuré"], weights=[0.80, 0.10, 0.05, 0.03, 0.02], k=1)[0]
        
        days_past_due = 0
        if status == "en_retard":
            days_past_due = random.randint(5, 89)
        elif status == "contentieux":
            days_past_due = random.randint(90, 360)
            
        outstanding = principal if status != "remboursé" else 0.00
        if status in ["actif", "en_retard", "contentieux", "restructuré"] and status != "remboursé":
            # Paid some amount
            paid_ratio = random.uniform(0.05, 0.60)
            outstanding = round(principal * (1 - paid_ratio), 2)
            
        bid = account_branch_map[linked_acc]
        
        sql_file.write(f"INSERT INTO loan_contracts (loan_id, customer_id, account_id, branch_id, loan_product_id, loan_type, principal_amount, currency, interest_rate, term_months, installment_amount, disbursement_date, maturity_date, status, outstanding_balance, days_past_due) VALUES ")
        sql_file.write(f"('{loan_id}', '{cust_id}', '{linked_acc}', '{bid}', '{lpid}', '{ltype}', {principal}, 'TND', {rate}, {term}, {installment}, '{disb_date}', '{mat_date}', '{status}', {outstanding}, {days_past_due});\n")

        # Loan Installments & Repayments (generate a few installments to seed tables)
        num_installments = min(5, term)
        for inst_num in range(1, num_installments + 1):
            inst_due = (disb_date_dt + timedelta(days=inst_num * 30)).strftime("%Y-%m-%d")
            inst_status = "paid" if inst_due < datetime.now().strftime("%Y-%m-%d") and status != "contentieux" else "unpaid"
            inst_paid_amt = installment if inst_status == "paid" else 0.00
            inst_paid_date = inst_due if inst_status == "paid" else "NULL"
            
            p_part = round(installment * 0.8, 2)
            i_part = round(installment * 0.2, 2)
            
            inst_uuid = f"inst_uuid_{l_idx}_{inst_num}"
            # Let's insert installments
            sql_file.write(f"INSERT INTO loan_installments (loan_id, installment_number, due_date, principal_amount, interest_amount, total_amount, status, paid_amount, paid_date) VALUES ('{loan_id}', {inst_num}, '{inst_due}', {p_part}, {i_part}, {installment}, '{inst_status}', {inst_paid_amt}, {'NULL' if inst_status == 'unpaid' else f'\'{inst_paid_date}\''});\n")
            
            if inst_status == "paid":
                sql_file.write(f"INSERT INTO loan_repayments (loan_id, amount, repayment_date, payment_method) VALUES ('{loan_id}', {installment}, '{inst_due}', 'prélèvement');\n")

        # Collateral (for professional or immo loans)
        if ltype in ["immobilier", "professionnel"] or random.random() < 0.3:
            col_id = f"COL_{l_idx:05d}"
            col_val = round(principal * random.uniform(1.1, 1.8), 2)
            col_type = "hypothèque" if ltype == "immobilier" else "nantissement"
            sql_file.write(f"INSERT INTO collateral (collateral_id, loan_id, collateral_type, description, estimated_value, valuation_date, status) VALUES ('{col_id}', '{loan_id}', '{col_type}', 'Garantie réelle pour prêt {loan_id}', {col_val}, '{disb_date}', 'actif');\n")

        # Guarantees (20% of loans)
        if random.random() < 0.20:
            gua_id = f"GUA_{l_idx:05d}"
            g_amt = round(principal * 0.5, 2)
            sql_file.write(f"INSERT INTO guarantees (guarantee_id, loan_id, guarantor_name, guarantee_amount, guarantee_type) VALUES ('{gua_id}', '{loan_id}', 'Société Tunisienne de Garantie', {g_amt}, 'caution_solidaire');\n")

        # Provisions (for late or contentieux loans)
        if status in ["en_retard", "contentieux"]:
            prov_amt = round(outstanding * (0.20 if status == "en_retard" else 0.70), 2)
            sql_file.write(f"INSERT INTO provisions (loan_id, provision_date, provision_amount, calculation_model) VALUES ('{loan_id}', CURRENT_DATE, {prov_amt}, 'BCT_standard');\n")

        # NPL table entry (contentieux / defaulted)
        if status == "contentieux":
            classif = "compromis" if days_past_due > 180 else "douteux"
            sql_file.write(f"INSERT INTO non_performing_loans (loan_id, npl_amount, npl_date, classification) VALUES ('{loan_id}', {outstanding}, '{disb_date}', '{classif}');\n")

    sql_file.write("\n")

    # 15. Transactions (Large Time Series)
    print("Generating transactions...")
    # Generate transactions spread over the last 24 months
    # Target: 50,000 transactions
    # To avoid writing 50,000 separate insert lines in python which might slow down compilation,
    # let's construct bulk INSERTs.
    tx_types = ["virement", "retrait DAB", "versement", "paiement TPE", "frais compte"]
    tx_weights = [0.40, 0.20, 0.15, 0.20, 0.05]
    
    start_date = datetime.now() - timedelta(days=args.months * 30)
    
    # We will generate blocks of inserts
    txn_values = []
    for t_idx in range(1, args.transactions + 1):
        txn_id = f"TXN_{t_idx:06d}"
        
        acc_id = random.choice(account_ids)
        cust_id = account_customer_map[acc_id]
        
        tx_type = random.choices(tx_types, weights=tx_weights, k=1)[0]
        
        # Debits are negative, credits are positive
        if tx_type in ["retrait DAB", "paiement TPE", "frais compte"] or (tx_type == "virement" and random.random() < 0.7):
            amount = -round(random.uniform(5, 500), 2)
        else:
            amount = round(random.uniform(50, 3000), 2)
            
        desc = f"Transaction {tx_type} tunisienne"
        # Spreading date
        tx_time = start_date + timedelta(seconds=random.randint(0, args.months * 30 * 24 * 3600))
        tx_date_str = tx_time.strftime("%Y-%m-%d %H:%M:%S")
        status = "complété"
        
        txn_values.append(f"('{txn_id}', '{acc_id}', '{cust_id}', {amount}, '{tx_type}', '{status}', '{desc}', '{tx_date_str}')")
        
        # Write in bulks of 1000 to keep SQL format clean and fast
        if len(txn_values) >= 1000:
            sql_file.write("INSERT INTO transactions (transaction_id, account_id, customer_id, amount, transaction_type, status, description, transaction_date) VALUES\n")
            sql_file.write(",\n".join(txn_values))
            sql_file.write(";\n")
            txn_values = []
            
    if txn_values:
        sql_file.write("INSERT INTO transactions (transaction_id, account_id, customer_id, amount, transaction_type, status, description, transaction_date) VALUES\n")
        sql_file.write(",\n".join(txn_values))
        sql_file.write(";\n")
        
    sql_file.write("\n")

    # 16. KYC / AML Domains
    print("Generating KYC/AML cases...")
    for idx, cust_id in enumerate(customer_ids):
        # 30% of customers have KYC case history
        if random.random() < 0.30:
            case_id = f"KYC_{idx:05d}"
            risk_band = "standard" if idx % 10 != 0 else ("pep" if idx % 50 == 0 else "élevé")
            status = random.choices(["approuvé", "en_cours", "ouvert", "rejeté"], weights=[0.80, 0.10, 0.05, 0.05], k=1)[0]
            ctype = "periodic_review" if idx % 3 == 0 else "initial_kyc"
            
            opened = (datetime.now() - timedelta(days=random.randint(10, 180))).strftime("%Y-%m-%d %H:%M:%S")
            closed = "NULL" if status in ["en_cours", "ouvert"] else f"'{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}'"
            
            sql_file.write(f"INSERT INTO kyc_cases (kyc_case_id, customer_id, case_type, status, risk_level, assigned_to, opened_at, closed_at) VALUES ")
            sql_file.write(f"('{case_id}', '{cust_id}', '{ctype}', '{status}', '{risk_band}', 'EMP_062', '{opened}', {closed});\n")
            
            # KYC document
            sql_file.write(f"INSERT INTO kyc_documents (kyc_case_id, document_type, document_number, verified) VALUES ('{case_id}', 'CIN', '{random.randint(0,1)}{random.randint(1000000,9999999):07d}', true);\n")
            
            # Screening
            if risk_band == "pep":
                sql_file.write(f"INSERT INTO pep_screening (customer_id, matched_name, risk_level, status) VALUES ('{cust_id}', 'Matching PEP Name', 'élevé', 'confirmé');\n")
            if idx % 15 == 0:
                sql_file.write(f"INSERT INTO sanctions_screening (customer_id, matched_name, sanctions_list, match_score, status) VALUES ('{cust_id}', 'Sanction Name Match', 'OFAC', 95.5, 'faux_positif');\n")

    # AML Alerts (generate 500 alerts)
    print("Generating AML alerts...")
    for idx in range(1, 501):
        alert_id = f"AML_{idx:04d}"
        cust_id = random.choice(customer_ids)
        # Find an account
        linked_acc = None
        for acc_id, cid in account_customer_map.items():
            if cid == cust_id:
                linked_acc = acc_id
                break
        if not linked_acc:
            linked_acc = random.choice(account_ids)
            
        atype = random.choice(["transaction_inhabituelle", "seuil_dépassé", "structuring"])
        label = f"Suspicion AML: {atype.replace('_', ' ').capitalize()}"
        severity = random.choices(["faible", "moyen", "élevé", "critique"], weights=[0.50, 0.30, 0.15, 0.05], k=1)[0]
        status = random.choices(["clôturé", "ouvert", "en_cours", "faux_positif"], weights=[0.40, 0.30, 0.20, 0.10], k=1)[0]
        score = round(random.uniform(50, 99), 2)
        
        sql_file.write(f"INSERT INTO aml_alerts (alert_id, customer_id, account_id, alert_type, alert_label_fr, severity, status, score) VALUES ")
        sql_file.write(f"('{alert_id}', '{cust_id}', '{linked_acc}', '{atype}', '{label}', '{severity}', '{status}', {score});\n")
        
        # Suspicious Activity Report (for 5% of alerts)
        if idx % 20 == 0:
            sar_id = f"SAR_{idx:04d}"
            sql_file.write(f"INSERT INTO suspicious_activity_reports (sar_id, alert_id, customer_id, report_date, status, description) VALUES ")
            sql_file.write(f"('{sar_id}', '{alert_id}', '{cust_id}', CURRENT_DATE, 'approuvé', 'Déclaration de soupçon relative à des transactions structurées répétées.');\n")

    sql_file.write("\n")

    # 17. Finance snapshoting
    print("Generating finance snapshots...")
    # Generate snaps for last 24 months
    for month_idx in range(args.months, 0, -1):
        snap_time = datetime.now() - timedelta(days=month_idx * 30)
        period = snap_time.strftime("%Y-%m")
        snap_date = snap_time.strftime("%Y-%m-%d")
        
        # General scale of banking sheet
        assets = 1500000000.00 + month_idx * 5000000.00
        liab = 1350000000.00 + month_idx * 4000000.00
        eq = assets - liab
        
        hqla = 300000000.00
        outflows = 150000000.00
        
        asf = 800000000.00
        rsf = 700000000.00
        
        # Balance Sheet snapshot
        sql_file.write(f"INSERT INTO balance_sheet_snapshots (period, total_assets, total_liabilities, total_equity, hqla, net_outflows_30d, available_stable_funding, required_stable_funding, snapshot_date) VALUES ")
        sql_file.write(f"('{period}', {assets}, {liab}, {eq}, {hqla}, {outflows}, {asf}, {rsf}, '{snap_date}');\n")
        
        # Income Statement
        interest_inc = 12000000.00 + random.uniform(-500000, 500000)
        interest_exp = 4000000.00 + random.uniform(-200000, 200000)
        fee_inc = 3000000.00 + random.uniform(-100000, 100000)
        net_b_inc = interest_inc + fee_inc - interest_exp
        ops_exp = 5000000.00 + random.uniform(-100000, 100000)
        net_inc = net_b_inc - ops_exp
        
        sql_file.write(f"INSERT INTO income_statement_snapshots (period, interest_income, interest_expense, fee_income, net_banking_income, operating_expenses, pnb, net_income, snapshot_date) VALUES ")
        sql_file.write(f"('{period}', {interest_inc}, {interest_exp}, {fee_inc}, {net_b_inc}, {ops_exp}, {net_b_inc}, {net_inc}, '{snap_date}');\n")

    sql_file.write("\n")

    # 18. Profitability Metrics & GL Ledger entries
    print("Generating profitability metrics...")
    for idx, bid in enumerate(branch_ids):
        pnb = round(random.uniform(50000, 500000), 2)
        expenses = round(pnb * random.uniform(0.40, 0.70), 2)
        net = pnb - expenses
        cir = round((expenses / pnb) * 100, 2)
        sql_file.write(f"INSERT INTO profitability_metrics (branch_id, pnb, net_income, cost_to_income_ratio, calculation_date) VALUES ('{bid}', {pnb}, {net}, {cir}, CURRENT_DATE);\n")

    # Audit findings (generate a few)
    sql_file.write("INSERT INTO audit_findings (finding_id, title, description, source, severity, status, target_resolution_date) VALUES\n")
    sql_file.write("('AUD_001', 'Sécurité de la caisse agence Tunis', 'Insuffisance de caméra de surveillance en caisse', 'audit_interne', 'moyen', 'ouvert', CURRENT_DATE + INTERVAL '60 days'),\n")
    sql_file.write("('AUD_002', 'Diligence KYC entreprises manquante', 'Absence de registre bénéficiaires effectifs sur 5 dossiers', 'audit_externe', 'élevé', 'en_attente', CURRENT_DATE + INTERVAL '30 days'),\n")
    sql_file.write("('AUD_003', 'Contrôles d''accès IT', 'Comptes génériques non désactivés sur le core banking', 'régulateur', 'critique', 'ouvert', CURRENT_DATE + INTERVAL '15 days');\n")

    # Commit transactions
    sql_file.write("\nCOMMIT;\n")
    sql_file.close()
    
    print(f"Data generation complete! Written successfully to: {args.output}")

if __name__ == "__main__":
    main()
