"""Generate realistic French insurance data as CSV, then load PostgreSQL."""

from __future__ import annotations

import argparse
import math
import os
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import psycopg
from faker import Faker

from retainflow.logging import get_logger

ROOT = Path(__file__).resolve().parents[3]


logger = get_logger(__name__)
SCHEMA_PATH = ROOT / "sql" / "postgres" / "00_schema.sql"
PG_DSN = os.getenv(
    "RETAINFLOW_POSTGRES_DSN",
    "postgresql://retainflow:retainflow@localhost:55432/retainflow",
)

HISTORY_START = date(2020, 1, 1)
HISTORY_END = date(2026, 6, 30)
PREDICTION_HORIZON_DAYS = 90
LABEL_CHURN_INTERCEPT = -3.05
LABEL_SYNTHETIC_CHURN_MULTIPLIER = 0.65
LABEL_MIN_CHURN_RATE_BY_SPLIT = 0.10
LABEL_TARGET_CHURN_RATE_RANGE_BY_SPLIT = (0.105, 0.14)
SNAPSHOT_DATES = (
    (date(2021, 12, 31), "train"),
    (date(2022, 12, 31), "train"),
    (date(2023, 12, 31), "train"),
    (date(2024, 12, 31), "validation"),
    (date(2025, 12, 31), "test"),
    (date(2026, 6, 30), "backtest"),
)


GEOGRAPHIES: tuple[tuple[Any, ...], ...] = (
    ("GEO_IDF_PARIS_75015", "FR", "Ile-de-France", "Paris", "Paris", "75015", "URBAN", 1.38, 1.05, 1.32),
    ("GEO_IDF_BOULOGNE_92100", "FR", "Ile-de-France", "Hauts-de-Seine", "Boulogne-Billancourt", "92100", "URBAN", 1.42, 0.98, 1.30),
    ("GEO_IDF_SAINT_DENIS_93200", "FR", "Ile-de-France", "Seine-Saint-Denis", "Saint-Denis", "93200", "URBAN", 0.88, 1.18, 1.14),
    ("GEO_ARA_LYON_69003", "FR", "Auvergne-Rhone-Alpes", "Rhone", "Lyon", "69003", "URBAN", 1.16, 1.00, 1.22),
    ("GEO_ARA_GRENOBLE_38000", "FR", "Auvergne-Rhone-Alpes", "Isere", "Grenoble", "38000", "URBAN", 1.07, 1.08, 1.18),
    ("GEO_PACA_MARSEILLE_13008", "FR", "Provence-Alpes-Cote dAzur", "Bouches-du-Rhone", "Marseille", "13008", "URBAN", 1.03, 1.20, 1.12),
    ("GEO_PACA_NICE_06000", "FR", "Provence-Alpes-Cote dAzur", "Alpes-Maritimes", "Nice", "06000", "URBAN", 1.12, 1.14, 1.16),
    ("GEO_OCC_TOULOUSE_31000", "FR", "Occitanie", "Haute-Garonne", "Toulouse", "31000", "URBAN", 1.08, 0.96, 1.20),
    ("GEO_OCC_MONTPELLIER_34000", "FR", "Occitanie", "Herault", "Montpellier", "34000", "URBAN", 1.02, 1.03, 1.18),
    ("GEO_NAQ_BORDEAUX_33000", "FR", "Nouvelle-Aquitaine", "Gironde", "Bordeaux", "33000", "URBAN", 1.10, 0.94, 1.17),
    ("GEO_NAQ_LIMOGES_87000", "FR", "Nouvelle-Aquitaine", "Haute-Vienne", "Limoges", "87000", "SUBURBAN", 0.88, 0.91, 0.96),
    ("GEO_HDF_LILLE_59000", "FR", "Hauts-de-France", "Nord", "Lille", "59000", "URBAN", 0.97, 1.08, 1.15),
    ("GEO_HDF_AMIENS_80000", "FR", "Hauts-de-France", "Somme", "Amiens", "80000", "SUBURBAN", 0.86, 1.02, 0.95),
    ("GEO_BRE_RENNES_35000", "FR", "Bretagne", "Ille-et-Vilaine", "Rennes", "35000", "URBAN", 1.04, 0.88, 1.16),
    ("GEO_BRE_BREST_29200", "FR", "Bretagne", "Finistere", "Brest", "29200", "SUBURBAN", 0.93, 0.95, 1.02),
    ("GEO_PDL_NANTES_44000", "FR", "Pays de la Loire", "Loire-Atlantique", "Nantes", "44000", "URBAN", 1.06, 0.90, 1.17),
    ("GEO_GE_STRASBOURG_67000", "FR", "Grand Est", "Bas-Rhin", "Strasbourg", "67000", "URBAN", 1.03, 0.97, 1.13),
    ("GEO_GE_REIMS_51100", "FR", "Grand Est", "Marne", "Reims", "51100", "SUBURBAN", 0.94, 1.01, 0.99),
    ("GEO_NOR_ROUEN_76000", "FR", "Normandie", "Seine-Maritime", "Rouen", "76000", "URBAN", 0.95, 1.06, 1.02),
    ("GEO_CVL_TOURS_37000", "FR", "Centre-Val de Loire", "Indre-et-Loire", "Tours", "37000", "SUBURBAN", 0.96, 0.92, 1.01),
    ("GEO_BFC_DIJON_21000", "FR", "Bourgogne-Franche-Comte", "Cote-dOr", "Dijon", "21000", "SUBURBAN", 0.98, 0.91, 1.00),
    ("GEO_COR_AJACCIO_20000", "FR", "Corse", "Corse-du-Sud", "Ajaccio", "20000", "SUBURBAN", 0.92, 1.22, 0.91),
    ("GEO_RURAL_CREUSE_23000", "FR", "Nouvelle-Aquitaine", "Creuse", "Gueret", "23000", "RURAL", 0.76, 0.86, 0.72),
    ("GEO_RURAL_CANTAL_15000", "FR", "Auvergne-Rhone-Alpes", "Cantal", "Aurillac", "15000", "RURAL", 0.79, 0.89, 0.74),
)

CHANNELS = (
    ("CH_WEB", "WEB", "Site web", "DIGITAL", True, True),
    ("CH_MOBILE", "MOBILE", "Application mobile", "DIGITAL", True, True),
    ("CH_BRANCH", "BRANCH", "Agence", "HUMAN", False, True),
    ("CH_CALL_CENTER", "CALL_CENTER", "Centre d'appels", "HUMAN", False, True),
    ("CH_BROKER", "BROKER", "Courtier", "PARTNER", False, True),
    ("CH_PARTNER", "PARTNER", "Partenaire commercial", "PARTNER", False, True),
    ("CH_EMAIL", "EMAIL", "Email", "OUTBOUND", True, False),
    ("CH_SMS", "SMS", "SMS", "OUTBOUND", True, False),
    ("CH_RETENTION_OUTBOUND", "RETENTION_OUTBOUND", "Equipe retention", "OUTBOUND", False, False),
)

PRODUCTS = (
    ("PROD_AUTO_BASIC", "AUTO", "Auto Essentiel", "BASIC", 520, 600, "MEDIUM", "MONTHLY"),
    ("PROD_AUTO_STANDARD", "AUTO", "Auto Confort", "STANDARD", 760, 350, "MEDIUM", "MONTHLY"),
    ("PROD_AUTO_PREMIUM", "AUTO", "Auto Premium", "PREMIUM", 1120, 150, "HIGH", "MONTHLY"),
    ("PROD_HOME_BASIC", "HOME", "Habitation Essentiel", "BASIC", 310, 500, "LOW", "MONTHLY"),
    ("PROD_HOME_STANDARD", "HOME", "Habitation Confort", "STANDARD", 480, 300, "MEDIUM", "MONTHLY"),
    ("PROD_HOME_PREMIUM", "HOME", "Habitation Premium", "PREMIUM", 760, 100, "MEDIUM", "MONTHLY"),
    ("PROD_HEALTH_BASIC", "HEALTH", "Sante Essentiel", "BASIC", 680, 250, "MEDIUM", "MONTHLY"),
    ("PROD_HEALTH_STANDARD", "HEALTH", "Sante Confort", "STANDARD", 980, 100, "HIGH", "MONTHLY"),
    ("PROD_HEALTH_PREMIUM", "HEALTH", "Sante Premium", "PREMIUM", 1480, 0, "HIGH", "MONTHLY"),
    ("PROD_LIFE_BASIC", "LIFE", "Prevoyance Essentiel", "BASIC", 240, 0, "LOW", "ANNUAL"),
    ("PROD_LIFE_STANDARD", "LIFE", "Prevoyance Confort", "STANDARD", 420, 0, "MEDIUM", "ANNUAL"),
    ("PROD_LIFE_PREMIUM", "LIFE", "Prevoyance Premium", "PREMIUM", 850, 0, "HIGH", "ANNUAL"),
    ("PROD_TRAVEL_STANDARD", "TRAVEL", "Voyage Confort", "STANDARD", 145, 75, "LOW", "ANNUAL"),
    ("PROD_PET_STANDARD", "PET", "Animal Confort", "STANDARD", 340, 60, "MEDIUM", "MONTHLY"),
    ("PROD_ACCIDENT_STANDARD", "PERSONAL_ACCIDENT", "Accident Confort", "STANDARD", 230, 50, "MEDIUM", "ANNUAL"),
)


@dataclass(frozen=True)
class Customer:
    customer_id: str
    geography_id: str
    agency_id: str
    birth_date: date
    acquisition_date: date
    segment: str
    income_band: str
    digital_profile: str
    price_sensitivity: float
    service_sensitivity: float
    digital_engagement: float
    loyalty: float
    claim_propensity: float
    preferred_channel_id: str
    consent_email: bool


@dataclass(frozen=True)
class Policy:
    policy_id: str
    customer_id: str
    product_id: str
    product_family: str
    agency_id: str
    agent_id: str | None
    start_date: date
    end_date: date
    status: str
    annual_premium: float
    premium_increase_pct: float
    cancellation_date: date | None


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-value))


def weighted_choice(rng: random.Random, items: list[Any], weights: list[float]) -> Any:
    return rng.choices(items, weights=weights, k=1)[0]


def random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, max(0, (end - start).days)))


def add_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(month=2, day=28, year=day.year + years)


def date_key(day: date) -> int:
    return int(day.strftime("%Y%m%d"))


def execute_many(conn: psycopg.Connection, sql: str, rows: list[tuple[Any, ...]], batch_size: int = 5000) -> None:
    if not rows:
        return
    with conn.cursor() as cur:
        for start in range(0, len(rows), batch_size):
            cur.executemany(sql, rows[start : start + batch_size])


def reset_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS retainflow CASCADE")
        cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def seed_reference_data(conn: psycopg.Connection, rng: random.Random) -> dict[str, list[dict[str, Any]]]:
    date_rows = []
    day = HISTORY_START
    while day <= HISTORY_END + timedelta(days=PREDICTION_HORIZON_DAYS):
        date_rows.append(
            (
                date_key(day),
                day,
                day.year,
                (day.month - 1) // 3 + 1,
                day.month,
                day.strftime("%B"),
                day.day,
                day.isoweekday(),
                int(day.strftime("%V")),
                day.weekday() >= 5,
                (day + timedelta(days=1)).day == 1,
                day.month in (3, 6, 9, 12) and (day + timedelta(days=1)).day == 1,
                day.month == 12 and day.day == 31,
            )
        )
        day += timedelta(days=1)

    execute_many(
        conn,
        """
        INSERT INTO retainflow.dim_date VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        date_rows,
    )
    execute_many(
        conn,
        """
        INSERT INTO retainflow.dim_geography
        (geography_id,country,region,department,city,postal_code,urbanicity,income_index,claim_risk_index,digital_adoption_index)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        list(GEOGRAPHIES),
    )
    execute_many(
        conn,
        """
        INSERT INTO retainflow.dim_channel
        (channel_id,channel_code,channel_name,channel_family,is_digital,is_inbound)
        VALUES (%s,%s,%s,%s,%s,%s)
        """,
        list(CHANNELS),
    )
    execute_many(
        conn,
        """
        INSERT INTO retainflow.dim_product
        (product_id,product_family,product_name,coverage_tier,base_annual_premium,deductible_amount,risk_level,default_payment_frequency)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        list(PRODUCTS),
    )

    agencies = []
    agency_rows = []
    for idx, geo in enumerate(GEOGRAPHIES, start=1):
        city = geo[4]
        agency_type = "BRANCH" if geo[6] != "RURAL" else "BROKER_HUB"
        if city in {"Lille", "Lyon", "Nantes", "Paris"}:
            agency_type = "RETENTION_CENTER" if city == "Lyon" else "CALL_CENTER"
        agency = {
            "agency_id": f"AGY_{idx:03d}",
            "agency_code": f"FR{idx:03d}",
            "agency_name": f"Agence RetainFlow {city}",
            "geography_id": geo[0],
            "city": city,
            "type": agency_type,
        }
        agencies.append(agency)
        agency_rows.append(
            (
                agency["agency_id"],
                agency["agency_code"],
                agency["agency_name"],
                agency["geography_id"],
                agency_type,
                random_date(rng, date(1998, 1, 1), date(2019, 12, 31)),
                rng.randint(8, 55),
            )
        )
    execute_many(
        conn,
        """
        INSERT INTO retainflow.dim_agency
        (agency_id,agency_code,agency_name,geography_id,agency_type,opened_date,employee_count)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        """,
        agency_rows,
    )

    agent_rows = []
    agents = []
    roles = [
        ("SALES", "CH_BRANCH", "Equipe commerciale"),
        ("SERVICE", "CH_CALL_CENTER", "Equipe service"),
        ("CLAIMS", "CH_CALL_CENTER", "Equipe sinistres"),
        ("RETENTION", "CH_RETENTION_OUTBOUND", "Equipe retention"),
        ("HYBRID", "CH_BROKER", "Equipe courtage"),
    ]
    counter = 1
    for agency in agencies:
        for role, channel_id, team in roles:
            role_count = 2 if role in {"SALES", "SERVICE"} else 1
            for _ in range(role_count):
                agent_id = f"AGT_{counter:05d}"
                name = Faker("fr_FR").name()
                agents.append(
                    {
                        "agent_id": agent_id,
                        "role": role,
                        "channel_id": channel_id,
                        "agency_id": agency["agency_id"],
                    }
                )
                agent_rows.append(
                    (
                        agent_id,
                        f"SRC_{agent_id}",
                        name,
                        role,
                        channel_id,
                        agency["agency_id"],
                        f"{team} {agency['city']}",
                        random_date(rng, date(2012, 1, 1), date(2023, 12, 31)),
                    )
                )
                counter += 1
    execute_many(
        conn,
        """
        INSERT INTO retainflow.dim_agent
        (agent_id,source_agent_id,agent_name,agent_role,channel_id,agency_id,team_name,hire_date)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        agent_rows,
    )
    return {"agencies": agencies, "agents": agents}


def generate_customers(conn: psycopg.Connection, n_customers: int, rng: random.Random) -> list[Customer]:
    fake = Faker("fr_FR")
    Faker.seed(rng.randint(1, 10_000_000))
    geo_weights = [1.6 if row[6] == "URBAN" else 0.95 if row[6] == "SUBURBAN" else 0.45 for row in GEOGRAPHIES]
    geos = list(GEOGRAPHIES)

    with conn.cursor() as cur:
        cur.execute("SELECT agency_id, geography_id FROM retainflow.dim_agency")
        agency_by_geo = {geo: agency for agency, geo in cur.fetchall()}

    rows: list[tuple[Any, ...]] = []
    customers: list[Customer] = []
    for i in range(1, n_customers + 1):
        geo = weighted_choice(rng, geos, geo_weights)
        income_index = float(geo[7])
        digital_index = float(geo[9])
        age = int(clamp(rng.normalvariate(47, 15), 18, 86))
        gender = weighted_choice(rng, ["F", "M", "OTHER"], [0.505, 0.485, 0.01])
        first_name = fake.first_name_female() if gender == "F" else fake.first_name_male()
        last_name = fake.last_name()
        acquisition_date = random_date(rng, HISTORY_START, min(date(2025, 12, 31), HISTORY_END))
        income_band = weighted_choice(
            rng,
            ["LOW", "LOWER_MID", "MID", "UPPER_MID", "HIGH"],
            [0.18 / income_index, 0.25, 0.31, 0.18 * income_index, 0.08 * income_index],
        )
        digital_raw = digital_index + rng.random() + (0.25 if age < 35 else -0.2 if age > 66 else 0)
        digital_profile = "HIGH" if digital_raw > 1.75 else "MEDIUM" if digital_raw > 1.1 else "LOW"
        price = clamp(rng.betavariate(2.4, 2.2) + (0.12 if income_band in {"LOW", "LOWER_MID"} else -0.06))
        service = clamp(rng.betavariate(2.0, 2.5) + (0.1 if age > 62 else 0))
        digital = clamp(rng.betavariate(2.2, 2.0) + (0.15 if digital_profile == "HIGH" else -0.12 if digital_profile == "LOW" else 0))
        loyalty = clamp(rng.betavariate(2.5, 2.0) + (0.1 if age > 45 else 0) - (0.12 if price > 0.75 else 0))
        claim_propensity = clamp(rng.betavariate(2.0, 3.2) + (float(geo[8]) - 1.0) * 0.3)
        household_size = weighted_choice(rng, [1, 2, 3, 4, 5], [0.22, 0.33, 0.24, 0.15, 0.06])
        employment = weighted_choice(
            rng,
            ["STUDENT", "EMPLOYED", "SELF_EMPLOYED", "RETIRED", "UNEMPLOYED"],
            [0.04, 0.62, 0.12, 0.14, 0.08],
        )
        if price >= 0.72:
            segment = "PRICE_SENSITIVE"
        elif digital >= 0.72:
            segment = "DIGITAL_FIRST"
        elif household_size >= 3 and 30 <= age <= 58:
            segment = "FAMILY_PROTECTOR"
        elif income_band in {"UPPER_MID", "HIGH"} and loyalty >= 0.55:
            segment = "HIGH_VALUE"
        else:
            segment = "LOW_ENGAGEMENT"
        acquisition_channel_id = weighted_choice(
            rng,
            ["CH_WEB", "CH_MOBILE", "CH_BRANCH", "CH_CALL_CENTER", "CH_BROKER", "CH_PARTNER"],
            [0.24, 0.15, 0.22, 0.16, 0.16, 0.07],
        )
        preferred_channel_id = (
            "CH_MOBILE"
            if digital_profile == "HIGH"
            else "CH_EMAIL"
            if digital_profile == "MEDIUM"
            else "CH_CALL_CENTER"
            if age > 65
            else acquisition_channel_id
        )
        customer_id = f"CUST_{i:08d}"
        birth_date = add_years(date(2026, rng.randint(1, 12), rng.randint(1, 28)), -age)
        customer = Customer(
            customer_id=customer_id,
            geography_id=geo[0],
            agency_id=agency_by_geo[geo[0]],
            birth_date=birth_date,
            acquisition_date=acquisition_date,
            segment=segment,
            income_band=income_band,
            digital_profile=digital_profile,
            price_sensitivity=price,
            service_sensitivity=service,
            digital_engagement=digital,
            loyalty=loyalty,
            claim_propensity=claim_propensity,
            preferred_channel_id=preferred_channel_id,
            consent_email=rng.random() < (0.9 if digital_profile == "HIGH" else 0.7),
        )
        customers.append(customer)
        rows.append(
            (
                customer_id,
                f"SRC_{customer_id}",
                first_name,
                last_name,
                birth_date,
                gender,
                f"{first_name.lower()}.{last_name.lower()}.{i}@example.retainflow",
                None if i % 29 == 0 else f"+33{rng.randint(600000000, 799999999)}",
                geo[0],
                customer.agency_id,
                acquisition_date,
                acquisition_channel_id,
                preferred_channel_id,
                employment,
                household_size,
                income_band,
                digital_profile,
                customer.consent_email,
                rng.random() < (0.66 if digital_profile == "HIGH" else 0.42),
                rng.random() < 0.68,
                segment,
                round(rng.betavariate(2.0, 2.2), 4),
                round(price, 4),
                round(service, 4),
                round(digital, 4),
                round(loyalty, 4),
                round(claim_propensity, 4),
            )
        )
    execute_many(
        conn,
        """
        INSERT INTO retainflow.dim_customer
        (customer_id,source_customer_id,first_name,last_name,birth_date,gender,email,phone,geography_id,home_agency_id,acquisition_date,
         acquisition_channel_id,preferred_channel_id,employment_status,household_size,estimated_income_band,digital_profile,consent_email,
         consent_sms,consent_phone,customer_segment,risk_affinity_score,price_sensitivity_score,service_sensitivity_score,
         digital_engagement_score,loyalty_score,claim_propensity_score)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        rows,
    )
    return customers


def generate_business_facts(
    conn: psycopg.Connection,
    customers: list[Customer],
    rng: random.Random,
) -> tuple[list[Policy], dict[str, dict[str, Any]]]:
    products = list(PRODUCTS)
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(float))
    policies: list[Policy] = []
    policy_rows = []
    event_rows = []
    payment_rows = []
    claim_rows = []
    interaction_rows = []
    service_rows = []
    campaign_rows = []
    quote_rows = []
    retention_rows = []

    with conn.cursor() as cur:
        cur.execute("SELECT agent_id, agent_role, agency_id FROM retainflow.dim_agent")
        agents = [{"agent_id": a, "role": r, "agency_id": ag} for a, r, ag in cur.fetchall()]
    sales_agents_by_agency: dict[str, list[str]] = defaultdict(list)
    service_agents_by_agency: dict[str, list[str]] = defaultdict(list)
    retention_agents_by_agency: dict[str, list[str]] = defaultdict(list)
    for agent in agents:
        target = (
            sales_agents_by_agency
            if agent["role"] in {"SALES", "HYBRID"}
            else retention_agents_by_agency
            if agent["role"] == "RETENTION"
            else service_agents_by_agency
        )
        target[agent["agency_id"]].append(agent["agent_id"])

    counters = defaultdict(int)
    for customer in customers:
        nb_policies = weighted_choice(rng, [1, 2, 3, 4], [0.58, 0.29, 0.10, 0.03])
        product_pool = products.copy()
        rng.shuffle(product_pool)
        customer_policies: list[Policy] = []
        for product in product_pool[:nb_policies]:
            counters["policy"] += 1
            start = max(customer.acquisition_date, random_date(rng, HISTORY_START, date(2025, 12, 31)))
            years = max(1, rng.randint(1, 6))
            end = add_years(start, years)
            churn_base = -2.1 + customer.price_sensitivity * 1.25 - customer.loyalty * 1.15 + customer.service_sensitivity * 0.35
            churn_prob = clamp(sigmoid(churn_base), 0.03, 0.55)
            cancelled = rng.random() < churn_prob and start < date(2026, 3, 31)
            cancellation_date = random_date(rng, start + timedelta(days=120), min(HISTORY_END, end)) if cancelled else None
            status = "CANCELLED" if cancelled else "ACTIVE" if end >= HISTORY_END else "EXPIRED"
            increase = clamp(rng.normalvariate(0.035, 0.045), -0.04, 0.22)
            premium_factor = 1 + (customer.price_sensitivity - 0.5) * 0.12 + rng.normalvariate(0, 0.08)
            annual_premium = max(60, round(float(product[4]) * premium_factor * (1 + increase), 2))
            discount = clamp(rng.betavariate(1.2, 8.0) * 0.25, 0, 0.35)
            agent_id = rng.choice(sales_agents_by_agency[customer.agency_id]) if sales_agents_by_agency[customer.agency_id] else None
            policy_id = f"POL_{counters['policy']:09d}"
            policy = Policy(
                policy_id,
                customer.customer_id,
                product[0],
                product[1],
                customer.agency_id,
                agent_id,
                start,
                end,
                status,
                annual_premium,
                increase,
                cancellation_date,
            )
            policies.append(policy)
            customer_policies.append(policy)
            policy_rows.append(
                (
                    policy_id,
                    f"SRC_{policy_id}",
                    customer.customer_id,
                    product[0],
                    weighted_choice(rng, ["CH_WEB", "CH_MOBILE", "CH_BRANCH", "CH_CALL_CENTER", "CH_BROKER"], [0.22, 0.14, 0.29, 0.16, 0.19]),
                    agent_id,
                    customer.agency_id,
                    start,
                    end,
                    None if status != "ACTIVE" else add_years(start, max(1, 2026 - start.year)),
                    status,
                    product[7],
                    annual_premium,
                    round(discount, 4),
                    round(increase, 4),
                    cancellation_date,
                    weighted_choice(rng, ["PRICE", "COMPETITOR", "SERVICE", "MOVED", "COVERAGE", None], [0.34, 0.22, 0.18, 0.1, 0.1, 0.06]) if cancelled else None,
                )
            )
            event_rows.append(
                (
                    f"PEV_{len(event_rows)+1:010d}",
                    policy_id,
                    customer.customer_id,
                    product[0],
                    start,
                    datetime.combine(start, datetime.min.time(), UTC) + timedelta(hours=rng.randint(8, 19)),
                    "SUBSCRIPTION",
                    "NEW_BUSINESS",
                    None,
                    "ACTIVE",
                    None,
                    annual_premium,
                    None,
                    "core_policy",
                )
            )
            if cancellation_date:
                event_rows.append(
                    (
                        f"PEV_{len(event_rows)+1:010d}",
                        policy_id,
                        customer.customer_id,
                        product[0],
                        cancellation_date,
                        datetime.combine(cancellation_date, datetime.min.time(), UTC) + timedelta(hours=rng.randint(8, 19)),
                        "CANCELLATION",
                        "CUSTOMER_REQUEST",
                        "ACTIVE",
                        "CANCELLED",
                        annual_premium,
                        annual_premium,
                        0,
                        "core_policy",
                    )
                )

            frequency_months = 1 if product[7] == "MONTHLY" else 3 if product[7] == "QUARTERLY" else 12
            payment_amount = round(annual_premium * frequency_months / 12, 2)
            due = start
            while due <= min(end, HISTORY_END):
                if cancellation_date and due > cancellation_date:
                    break
                counters["payment"] += 1
                incident_prob = 0.025 + customer.price_sensitivity * 0.055 + (0.02 if customer.income_band in {"LOW", "LOWER_MID"} else 0)
                late = rng.random() < incident_prob
                rejected = late and rng.random() < 0.18
                days_late = rng.randint(3, 45) if late else 0
                payment_status = "REJECTED" if rejected else "LATE" if late else "PAID"
                payment_rows.append(
                    (
                        f"PAY_{counters['payment']:011d}",
                        policy_id,
                        customer.customer_id,
                        due,
                        None if rejected else due + timedelta(days=days_late),
                        due.year,
                        payment_amount,
                        payment_status,
                        weighted_choice(rng, ["CARD", "DIRECT_DEBIT", "BANK_TRANSFER", "CHECK", "CASH", "WALLET"], [0.21, 0.56, 0.15, 0.03, 0.02, 0.03]),
                        days_late,
                        weighted_choice(rng, ["INSUFFICIENT_FUNDS", "EXPIRED_CARD", "MANDATE_CANCELLED"], [0.58, 0.24, 0.18]) if rejected else None,
                    )
                )
                due = due + timedelta(days=30 * frequency_months)

            claim_lambda = 0.12 + customer.claim_propensity * 0.55 + (0.18 if product[1] in {"AUTO", "HEALTH"} else 0)
            for _ in range(np.random.default_rng(rng.randint(1, 10_000_000)).poisson(claim_lambda)):
                counters["claim"] += 1
                claim_date = random_date(rng, start, min(HISTORY_END, cancellation_date or end))
                amount = round(max(80, rng.lognormvariate(6.0, 0.75)), 2)
                paid = round(max(0, amount - float(product[5])) * rng.uniform(0.65, 1.0), 2)
                handling_days = rng.randint(3, 95)
                status = weighted_choice(rng, ["CLOSED", "APPROVED", "REJECTED", "UNDER_REVIEW"], [0.72, 0.12, 0.08, 0.08])
                satisfaction = clamp(rng.normalvariate(3.8, 0.9) - (0.7 if handling_days > 45 else 0), 1, 5)
                claim_rows.append(
                    (
                        f"CLM_{counters['claim']:010d}",
                        f"SRC_CLM_{counters['claim']:010d}",
                        policy_id,
                        customer.customer_id,
                        product[0],
                        claim_date,
                        claim_date + timedelta(days=rng.randint(0, 5)),
                        claim_date + timedelta(days=handling_days) if status == "CLOSED" else None,
                        weighted_choice(rng, ["ACCIDENT", "WATER_DAMAGE", "THEFT", "HEALTHCARE", "GLASS_BREAKAGE", "LEGAL"], [0.25, 0.17, 0.12, 0.25, 0.13, 0.08]),
                        status,
                        amount,
                        paid,
                        product[5],
                        handling_days,
                        rng.random() < 0.025,
                        round(satisfaction, 2),
                    )
                )

        interaction_count = int(max(1, rng.normalvariate(5 + customer.digital_engagement * 7 + customer.service_sensitivity * 4, 2.5)))
        for _ in range(interaction_count):
            counters["interaction"] += 1
            policy = rng.choice(customer_policies)
            interaction_day = random_date(rng, max(customer.acquisition_date, HISTORY_START), HISTORY_END)
            reason = weighted_choice(rng, ["QUOTE", "CLAIM", "BILLING", "COMPLAINT", "RENEWAL", "RETENTION", "GENERAL_SERVICE"], [0.15, 0.12, 0.18, 0.08, 0.16, 0.09, 0.22])
            channel = weighted_choice(rng, ["CH_MOBILE", "CH_WEB", "CH_CALL_CENTER", "CH_BRANCH", "CH_EMAIL", "CH_SMS"], [0.25, 0.23, 0.19, 0.12, 0.15, 0.06])
            agent_id = None if channel in {"CH_MOBILE", "CH_WEB", "CH_EMAIL", "CH_SMS"} else rng.choice(service_agents_by_agency[customer.agency_id])
            sentiment = clamp(rng.normalvariate(0.12, 0.45) - (0.35 if reason == "COMPLAINT" else 0), -1, 1)
            interaction_id = f"INT_{counters['interaction']:011d}"
            interaction_rows.append(
                (
                    interaction_id,
                    customer.customer_id,
                    policy.policy_id,
                    channel,
                    agent_id,
                    datetime.combine(interaction_day, datetime.min.time(), UTC) + timedelta(hours=rng.randint(8, 20), minutes=rng.randint(0, 59)),
                    interaction_day.year,
                    weighted_choice(rng, ["CALL", "EMAIL", "WEB_VISIT", "MOBILE_SESSION", "BRANCH_MEETING", "CHAT", "SMS"], [0.18, 0.17, 0.20, 0.22, 0.08, 0.10, 0.05]),
                    reason,
                    "INBOUND" if reason not in {"RETENTION", "RENEWAL"} else weighted_choice(rng, ["INBOUND", "OUTBOUND"], [0.35, 0.65]),
                    rng.randint(45, 1800),
                    round(sentiment, 3),
                    rng.random() < (0.88 if sentiment > -0.2 else 0.58),
                )
            )
            if reason in {"COMPLAINT", "BILLING", "CLAIM"} and rng.random() < 0.45:
                counters["case"] += 1
                opened = interaction_day
                sla_breached = rng.random() < (0.18 + customer.service_sensitivity * 0.2)
                sat = clamp(rng.normalvariate(3.6, 0.9) - (0.9 if sla_breached else 0), 1, 5)
                service_rows.append(
                    (
                        f"CAS_{counters['case']:010d}",
                        customer.customer_id,
                        policy.policy_id,
                        interaction_id,
                        datetime.combine(opened, datetime.min.time(), UTC) + timedelta(hours=rng.randint(8, 18)),
                        datetime.combine(opened + timedelta(days=rng.randint(1, 25)), datetime.min.time(), UTC),
                        "COMPLAINT" if reason == "COMPLAINT" else "BILLING" if reason == "BILLING" else "CLAIM_SUPPORT",
                        weighted_choice(rng, ["LOW", "MEDIUM", "HIGH", "CRITICAL"], [0.28, 0.45, 0.22, 0.05]),
                        weighted_choice(rng, ["RESOLVED", "CLOSED", "ESCALATED"], [0.62, 0.28, 0.10]),
                        sla_breached,
                        weighted_choice(rng, ["ANSWERED", "COMPENSATED", "DOCUMENT_REQUESTED", "ESCALATED_BACKOFFICE"], [0.45, 0.16, 0.27, 0.12]),
                        round(sat, 2),
                    )
                )

        for campaign_year in range(2020, 2027):
            if random_date(rng, date(campaign_year, 1, 1), date(campaign_year, 12, 28)) < customer.acquisition_date:
                continue
            if rng.random() < (0.65 if customer.consent_email else 0.22):
                counters["campaign"] += 1
                campaign_type = weighted_choice(rng, ["CROSS_SELL", "UPSELL", "RENEWAL", "RETENTION"], [0.30, 0.18, 0.32, 0.20])
                opened = rng.random() < (0.48 + customer.digital_engagement * 0.25)
                clicked = opened and rng.random() < (0.18 + customer.digital_engagement * 0.18)
                responded = clicked and rng.random() < 0.34
                campaign_rows.append(
                    (
                        f"CMPCT_{counters['campaign']:011d}",
                        f"CMP_{campaign_year}_{campaign_type}",
                        customer.customer_id,
                        rng.choice(customer_policies).policy_id,
                        "CH_EMAIL",
                        campaign_type,
                        f"{campaign_type.title()} France {campaign_year}",
                        datetime(campaign_year, rng.randint(1, 12), rng.randint(1, 26), rng.randint(8, 19), tzinfo=UTC),
                        campaign_year,
                        opened,
                        clicked,
                        responded,
                        responded and rng.random() < 0.18,
                        f"OFF_{campaign_type}_{campaign_year}",
                    )
                )

        if rng.random() < 0.55:
            counters["quote"] += 1
            quote_product = rng.choice(products)
            quote_date = random_date(rng, customer.acquisition_date, HISTORY_END)
            competitor = clamp(rng.normalvariate(0.98, 0.12), 0.65, 1.35)
            status = weighted_choice(rng, ["SENT", "ACCEPTED", "DECLINED", "EXPIRED"], [0.32, 0.18, 0.31, 0.19])
            quote_rows.append(
                (
                    f"QUO_{counters['quote']:010d}",
                    customer.customer_id,
                    quote_product[0],
                    customer.preferred_channel_id,
                    rng.choice(sales_agents_by_agency[customer.agency_id]) if customer.preferred_channel_id in {"CH_BRANCH", "CH_CALL_CENTER"} else None,
                    quote_date,
                    round(float(quote_product[4]) * rng.uniform(0.86, 1.18), 2),
                    round(competitor, 4),
                    status,
                    None,
                )
            )

        risk_signal = customer.price_sensitivity + customer.service_sensitivity - customer.loyalty
        if risk_signal > 0.65 and rng.random() < 0.55:
            counters["retention"] += 1
            policy = rng.choice(customer_policies)
            action_date = random_date(rng, max(policy.start_date, date(2022, 1, 1)), min(HISTORY_END, policy.cancellation_date or HISTORY_END))
            action_type = weighted_choice(rng, ["DISCOUNT", "CALLBACK", "PAYMENT_PLAN", "LOYALTY_BONUS", "CLAIM_REVIEW"], [0.36, 0.25, 0.15, 0.14, 0.10])
            accepted = rng.random() < (0.36 + customer.loyalty * 0.28 - customer.price_sensitivity * 0.10)
            retention_rows.append(
                (
                    f"RET_{counters['retention']:010d}",
                    customer.customer_id,
                    policy.policy_id,
                    action_date,
                    datetime.combine(action_date, datetime.min.time(), UTC) + timedelta(hours=rng.randint(8, 19)),
                    action_type,
                    weighted_choice(rng, ["PREMIUM_INCREASE", "COMPLAINT", "PAYMENT_INCIDENT", "LOW_ENGAGEMENT", "RENEWAL_RISK", "HIGH_VALUE_SAVE"], [0.30, 0.17, 0.15, 0.12, 0.18, 0.08]),
                    round(policy.annual_premium * rng.uniform(0.03, 0.16), 2),
                    "CH_RETENTION_OUTBOUND",
                    rng.choice(retention_agents_by_agency[customer.agency_id]),
                    accepted,
                    accepted and rng.random() < 0.82,
                )
            )

    insert_specs = [
        ("fact_policy", "(policy_id,source_policy_id,customer_id,product_id,sales_channel_id,agent_id,agency_id,policy_start_date,policy_end_date,next_renewal_date,policy_status,payment_frequency,annual_premium,premium_discount_pct,premium_increase_pct_last_renewal,cancellation_date,cancellation_reason)", policy_rows),
        ("fact_policy_event", "(policy_event_id,policy_id,customer_id,product_id,event_date,event_timestamp,event_type,event_reason,previous_policy_status,new_policy_status,previous_annual_premium,new_annual_premium,premium_change_pct,source_system)", event_rows),
        ("fact_payment", "(payment_id,policy_id,customer_id,due_date,payment_date,payment_year,payment_amount,payment_status,payment_method,days_late,rejection_reason)", payment_rows),
        ("fact_claim", "(claim_id,source_claim_id,policy_id,customer_id,product_id,claim_date,reported_date,closed_date,claim_type,claim_status,claim_amount,paid_amount,deductible_amount,handling_days,fraud_suspicion_flag,claim_satisfaction_score)", claim_rows),
        ("fact_interaction", "(interaction_id,customer_id,policy_id,channel_id,agent_id,interaction_datetime,interaction_year,interaction_type,interaction_reason,direction,duration_seconds,sentiment_score,resolved_flag)", interaction_rows),
        ("fact_customer_service", "(case_id,customer_id,policy_id,interaction_id,opened_datetime,closed_datetime,case_type,priority,case_status,sla_breached_flag,resolution_code,satisfaction_score)", service_rows),
        ("fact_campaign_contact", "(campaign_contact_id,campaign_id,customer_id,policy_id,channel_id,campaign_type,campaign_name,contact_datetime,contact_year,opened_flag,clicked_flag,responded_flag,converted_flag,offer_id)", campaign_rows),
        ("fact_quote", "(quote_id,customer_id,product_id,channel_id,agent_id,quote_date,quoted_annual_premium,competitor_price_index,quote_status,converted_policy_id)", quote_rows),
        ("fact_retention_action", "(retention_action_id,customer_id,policy_id,action_date,action_timestamp,action_type,trigger_reason,offered_value,channel_id,agent_id,accepted_flag,retained_90d_flag)", retention_rows),
    ]
    for table, columns, rows in insert_specs:
        placeholders = ",".join(["%s"] * len(rows[0])) if rows else ""
        execute_many(conn, f"INSERT INTO retainflow.{table} {columns} VALUES ({placeholders})", rows)

    for policy in policies:
        stats[policy.customer_id]["policy_count"] += 1
        stats[policy.customer_id]["premium"] += policy.annual_premium if policy.status == "ACTIVE" else 0
    for row in payment_rows:
        if row[7] in {"LATE", "REJECTED", "WRITTEN_OFF"}:
            stats[row[2]]["payment_incidents"] += 1
        stats[row[2]].setdefault("payments", []).append({"due_date": row[3], "status": row[7]})
    for row in claim_rows:
        stats[row[3]]["claims"] += 1
        stats[row[3]]["claim_amount"] += float(row[10])
        stats[row[3]].setdefault("claims_history", []).append(
            {
                "claim_date": row[5],
                "status": row[9],
                "amount": float(row[10]),
            }
        )
    for row in service_rows:
        if row[6] == "COMPLAINT":
            stats[row[1]]["complaints"] += 1
        stats[row[1]]["service_satisfaction_sum"] += float(row[11] or 3)
        stats[row[1]]["service_satisfaction_count"] += 1
        stats[row[1]].setdefault("service_cases", []).append(
            {
                "opened_date": row[4].date(),
                "case_type": row[6],
                "status": row[8],
            }
        )
    for row in interaction_rows:
        stats[row[1]]["interactions"] += 1
        if row[3] in {"CH_MOBILE", "CH_WEB"}:
            stats[row[1]]["digital_interactions"] += 1
    for row in campaign_rows:
        stats[row[2]].setdefault("campaign_contacts", []).append(
            {
                "contact_date": row[7].date(),
                "responded": bool(row[11]),
            }
        )
    for row in quote_rows:
        stats[row[1]].setdefault("quotes", []).append(
            {
                "quote_date": row[5],
                "competitor_price_index": float(row[7]),
            }
        )
    for row in retention_rows:
        stats[row[1]].setdefault("retention_actions", []).append(
            {
                "action_date": row[3],
                "accepted": bool(row[10]),
            }
        )
    return policies, stats


def generate_snapshots_and_labels(
    conn: psycopg.Connection,
    customers: list[Customer],
    policies: list[Policy],
    stats: dict[str, dict[str, Any]],
    rng: random.Random,
) -> None:
    policies_by_customer: dict[str, list[Policy]] = defaultdict(list)
    for policy in policies:
        policies_by_customer[policy.customer_id].append(policy)
    product_lookup = {product[0]: product for product in PRODUCTS}
    snapshots = []
    labels = []
    for customer in customers:
        customer_policies = policies_by_customer[customer.customer_id]
        for observation_date, split_name in SNAPSHOT_DATES:
            observed = [p for p in customer_policies if p.start_date <= observation_date]
            active = [p for p in observed if p.status == "ACTIVE" and p.end_date >= observation_date]
            products = {p.product_family for p in active}
            family_counts = {
                "AUTO": sum(1 for p in active if p.product_family == "AUTO"),
                "HOME": sum(1 for p in active if p.product_family == "HOME"),
                "HEALTH": sum(1 for p in active if p.product_family == "HEALTH"),
                "LIFE": sum(1 for p in active if p.product_family == "LIFE"),
            }
            main_product_family = max(
                family_counts,
                key=lambda family: (family_counts[family], family),
            )
            if not active:
                main_product_family = "NONE"
            tier_rank = {"NONE": 0, "BASIC": 1, "STANDARD": 2, "PREMIUM": 3}
            active_tiers = [
                str(product_lookup[p.product_id][3])
                for p in active
                if p.product_id in product_lookup
            ]
            highest_coverage_tier = max(active_tiers or ["NONE"], key=lambda tier: tier_rank[tier])
            premium = sum(p.annual_premium for p in active)
            tenure_months = max(0, (observation_date.year - customer.acquisition_date.year) * 12 + observation_date.month - customer.acquisition_date.month)
            age_years = round((observation_date - customer.birth_date).days / 365.25, 2)
            policy_age_avg_months = (
                sum(
                    max(
                        0,
                        (observation_date.year - p.start_date.year) * 12
                        + observation_date.month
                        - p.start_date.month,
                    )
                    for p in active
                )
                / len(active)
                if active
                else 0.0
            )
            cancelled_to_date = sum(
                1
                for p in observed
                if p.cancellation_date is not None and p.cancellation_date <= observation_date
            )
            scale = max(0.15, tenure_months / 78)
            window_12m_start = observation_date - timedelta(days=365)
            window_6m_start = observation_date - timedelta(days=183)
            customer_stats = stats[customer.customer_id]
            payments_12m = [
                payment
                for payment in customer_stats.get("payments", [])
                if window_12m_start <= payment["due_date"] <= observation_date
            ]
            late_payment_count_12m = sum(
                1 for payment in payments_12m if payment["status"] in {"LATE", "REJECTED", "WRITTEN_OFF"}
            )
            rejected_payment_count_12m = sum(
                1 for payment in payments_12m if payment["status"] in {"REJECTED", "WRITTEN_OFF"}
            )
            service_cases_12m = [
                case
                for case in customer_stats.get("service_cases", [])
                if window_12m_start <= case["opened_date"] <= observation_date
            ]
            service_case_count_12m = len(service_cases_12m)
            unresolved_case_count_12m = sum(
                1 for case in service_cases_12m if case["status"] in {"OPEN", "IN_PROGRESS", "ESCALATED"}
            )
            retention_actions_12m = [
                action
                for action in customer_stats.get("retention_actions", [])
                if window_12m_start <= action["action_date"] <= observation_date
            ]
            retention_offer_count_12m = len(retention_actions_12m)
            retention_acceptance_rate_12m = (
                sum(1 for action in retention_actions_12m if action["accepted"])
                / retention_offer_count_12m
                if retention_offer_count_12m
                else 0.0
            )
            quotes_6m = [
                quote
                for quote in customer_stats.get("quotes", [])
                if window_6m_start <= quote["quote_date"] <= observation_date
            ]
            quote_count_6m = len(quotes_6m)
            competitor_price_index_avg_6m = (
                sum(quote["competitor_price_index"] for quote in quotes_6m) / quote_count_6m
                if quote_count_6m
                else 1.0
            )
            campaign_contacts_6m = [
                contact
                for contact in customer_stats.get("campaign_contacts", [])
                if window_6m_start <= contact["contact_date"] <= observation_date
            ]
            campaign_response_rate_6m = (
                sum(1 for contact in campaign_contacts_6m if contact["responded"])
                / len(campaign_contacts_6m)
                if campaign_contacts_6m
                else 0.0
            )
            total_claims_12m = int(np.random.default_rng(rng.randint(1, 10_000_000)).poisson((stats[customer.customer_id]["claims"] / max(1, len(observed))) * 0.35 * scale))
            payment_incidents_6m = int(np.random.default_rng(rng.randint(1, 10_000_000)).poisson(stats[customer.customer_id]["payment_incidents"] * 0.08 * scale))
            complaints_6m = int(np.random.default_rng(rng.randint(1, 10_000_000)).poisson(stats[customer.customer_id]["complaints"] * 0.12 * scale))
            interactions_3m = int(np.random.default_rng(rng.randint(1, 10_000_000)).poisson(max(1, stats[customer.customer_id]["interactions"]) * 0.08))
            premium_increase = max([p.premium_increase_pct for p in active], default=0)
            renewal_days = min([(p.end_date - observation_date).days for p in active if p.end_date >= observation_date], default=None)
            satisfaction_count = stats[customer.customer_id]["service_satisfaction_count"]
            avg_satisfaction = (
                round(stats[customer.customer_id]["service_satisfaction_sum"] / satisfaction_count, 2)
                if satisfaction_count
                else round(clamp(rng.normalvariate(3.7, 0.8), 1, 5), 2)
            )
            customer_value = clamp((premium / 2200) * 0.55 + len(products) * 0.12 + customer.loyalty * 0.35, 0, 1)
            churn_score = (
                LABEL_CHURN_INTERCEPT
                + customer.price_sensitivity * 1.35
                + customer.service_sensitivity * 0.55
                + payment_incidents_6m * 0.22
                + late_payment_count_12m * 0.08
                + rejected_payment_count_12m * 0.18
                + complaints_6m * 0.34
                + unresolved_case_count_12m * 0.14
                + premium_increase * 3.0
                + (0.28 if competitor_price_index_avg_6m < 0.92 and quote_count_6m > 0 else 0)
                - customer.loyalty * 1.25
                - len(products) * 0.16
                - customer_value * 0.28
                - retention_acceptance_rate_12m * 0.35
                - campaign_response_rate_6m * 0.16
                + (0.22 if customer.digital_profile == "LOW" else 0)
            )
            churn_probability = clamp(sigmoid(churn_score), 0.008, 0.62)
            risk_band = (
                "VERY_HIGH"
                if churn_probability >= 0.18
                else "HIGH"
                if churn_probability >= 0.12
                else "MEDIUM"
                if churn_probability >= 0.07
                else "LOW"
            )
            if payment_incidents_6m >= 2:
                reason = "PAYMENT_INCIDENT"
            elif complaints_6m >= 1 or avg_satisfaction < 2.8:
                reason = "SERVICE_DISSATISFACTION"
            elif premium_increase >= 0.08:
                reason = "PREMIUM_INCREASE"
            elif customer.price_sensitivity >= 0.72:
                reason = "PRICE_SENSITIVITY"
            else:
                reason = "LOW_ENGAGEMENT" if customer.digital_engagement < 0.35 else "BASELINE_RISK"
            future_churn_dates = [
                p.cancellation_date
                for p in observed
                if p.cancellation_date
                and observation_date
                < p.cancellation_date
                <= observation_date + timedelta(days=PREDICTION_HORIZON_DAYS)
            ]
            churn_date = min(future_churn_dates, default=None)
            synthetic_churn_event = (
                churn_date is None and rng.random() < churn_probability * LABEL_SYNTHETIC_CHURN_MULTIPLIER
            )
            if synthetic_churn_event:
                churn_date = observation_date + timedelta(days=rng.randint(7, PREDICTION_HORIZON_DAYS))
            churn_label = 1 if churn_date else 0
            lifecycle_status = "CHURNED_WITHIN_HORIZON" if churn_label else "ACTIVE_OBSERVED"
            snapshots.append(
                (
                    observation_date,
                    customer.customer_id,
                    split_name,
                    tenure_months,
                    len(active),
                    len(products),
                    round(premium, 2),
                    total_claims_12m,
                    round(total_claims_12m * rng.uniform(350, 1400), 2),
                    payment_incidents_6m,
                    complaints_6m,
                    interactions_3m,
                    rng.randint(0, 180),
                    int(max(0, rng.normalvariate(8 * customer.digital_engagement, 3))),
                    round(clamp(0.18 + customer.digital_engagement * 0.62 + rng.normalvariate(0, 0.08)), 4),
                    round(premium_increase, 4),
                    avg_satisfaction,
                    renewal_days,
                    round(customer_value, 4),
                    age_years,
                    family_counts["AUTO"],
                    family_counts["HOME"],
                    family_counts["HEALTH"],
                    family_counts["LIFE"],
                    cancelled_to_date,
                    round(policy_age_avg_months, 2),
                    late_payment_count_12m,
                    rejected_payment_count_12m,
                    service_case_count_12m,
                    unresolved_case_count_12m,
                    retention_offer_count_12m,
                    round(retention_acceptance_rate_12m, 4),
                    quote_count_6m,
                    round(competitor_price_index_avg_6m, 4),
                    round(campaign_response_rate_6m, 4),
                    main_product_family,
                    highest_coverage_tier,
                    risk_band,
                )
            )
            labels.append(
                (
                    observation_date,
                    customer.customer_id,
                    split_name,
                    PREDICTION_HORIZON_DAYS,
                    churn_label,
                    churn_date,
                    lifecycle_status,
                    round(churn_probability, 4),
                    risk_band,
                    reason,
                )
            )

    labels = enforce_minimum_churn_rate(labels, rng)

    execute_many(
        conn,
        """
        INSERT INTO retainflow.customer_360_snapshot
        (observation_date,customer_id,split_name,tenure_months,active_policy_count,number_of_products,total_annual_premium,
         total_claims_12m,total_claim_amount_12m,payment_incidents_6m,complaints_6m,interactions_3m,days_since_last_contact,
         digital_sessions_30d,email_open_rate_6m,premium_increase_pct_max_12m,avg_satisfaction_score_12m,renewal_days_min,
         customer_value_score,customer_age_years,active_auto_policy_count,active_home_policy_count,active_health_policy_count,
         active_life_policy_count,cancelled_policy_count_to_date,policy_age_avg_months,late_payment_count_12m,
         rejected_payment_count_12m,service_case_count_12m,unresolved_case_count_12m,retention_offer_count_12m,
         retention_acceptance_rate_12m,quote_count_6m,competitor_price_index_avg_6m,campaign_response_rate_6m,
         main_product_family,highest_coverage_tier,latent_churn_risk_band)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        snapshots,
    )
    execute_many(
        conn,
        """
        INSERT INTO retainflow.churn_label
        (observation_date,customer_id,split_name,prediction_horizon_days,churn_label,churn_date,customer_lifecycle_status,churn_probability,churn_risk_band,label_reason)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        labels,
    )


def enforce_minimum_churn_rate(labels: list[tuple[Any, ...]], rng: random.Random) -> list[tuple[Any, ...]]:
    """Guarantee enough positive labels per split while keeping weighted randomness."""
    labels_by_split: dict[str, list[int]] = defaultdict(list)
    for index, label in enumerate(labels):
        labels_by_split[str(label[2])].append(index)

    adjusted_labels = list(labels)
    for split_name, indexes in labels_by_split.items():
        positive_count = sum(int(adjusted_labels[index][4]) for index in indexes)
        minimum_positive_count = math.ceil(len(indexes) * LABEL_MIN_CHURN_RATE_BY_SPLIT)
        if positive_count >= minimum_positive_count:
            continue

        target_churn_rate = rng.uniform(*LABEL_TARGET_CHURN_RATE_RANGE_BY_SPLIT)
        target_positive_count = max(
            minimum_positive_count,
            math.ceil(len(indexes) * target_churn_rate),
        )
        candidate_indexes = [index for index in indexes if int(adjusted_labels[index][4]) == 0]
        needed = min(target_positive_count - positive_count, len(candidate_indexes))
        weighted_candidates = []
        for index in candidate_indexes:
            label = adjusted_labels[index]
            churn_probability = max(float(label[7]), 0.001)
            random_key = rng.random() ** (1 / churn_probability)
            weighted_candidates.append((random_key, index))

        selected_indexes = [
            index
            for _, index in sorted(weighted_candidates, reverse=True)[:needed]
        ]
        logger.info(
            "Raised churn labels for split=%s from %.2f%% to random target %.2f%%",
            split_name,
            positive_count / len(indexes) * 100,
            (positive_count + len(selected_indexes)) / len(indexes) * 100,
        )
        for index in selected_indexes:
            (
                observation_date,
                customer_id,
                label_split_name,
                prediction_horizon_days,
                _churn_label,
                _churn_date,
                _lifecycle_status,
                churn_probability,
                risk_band,
                reason,
            ) = adjusted_labels[index]
            churn_date = observation_date + timedelta(days=rng.randint(7, prediction_horizon_days))
            adjusted_labels[index] = (
                observation_date,
                customer_id,
                label_split_name,
                prediction_horizon_days,
                1,
                churn_date,
                "CHURNED_WITHIN_HORIZON",
                max(float(churn_probability), 0.10),
                risk_band if risk_band != "LOW" else "MEDIUM",
                reason,
            )

    return adjusted_labels


def run_generation(args: argparse.Namespace) -> None:
    from retainflow.data.csv_etl import run_csv_to_postgres

    logger.info(
        "Starting CSV -> PostgreSQL pipeline: n_customers=%s seed=%s reset=%s csv_dir=%s",
        args.n_customers,
        args.seed,
        args.reset,
        args.csv_dir,
    )
    output_path = run_csv_to_postgres(
        dsn=args.dsn,
        n_customers=args.n_customers,
        seed=args.seed,
        csv_dir=args.csv_dir,
        reset=args.reset,
    )
    print(f"Generation complete: CSV files in {output_path} loaded to PostgreSQL")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RetainFlow data into PostgreSQL.")
    parser.add_argument("--dsn", default=PG_DSN, help="PostgreSQL DSN.")
    parser.add_argument("--n-customers", type=int, default=int(os.getenv("RETAINFLOW_N_CUSTOMERS", "10000")))
    parser.add_argument("--seed", type=int, default=int(os.getenv("RETAINFLOW_SEED", "42")))
    parser.add_argument("--reset", action="store_true", help="Drop and recreate schema before generation.")
    parser.add_argument(
        "--csv-dir",
        default=os.getenv("RETAINFLOW_CSV_DIR", str(ROOT / "data" / "raw" / "retainflow_csv")),
        help="Directory where generated table CSV files are written before ETL loading.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_generation(parse_args())
