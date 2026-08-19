"""Tests d'intégrité référentielle (charte section 10 : "toute foreign key
testée pour orphelins"). Le schéma applique les FK en base (pas seulement en
Python) -> chaque test vérifie qu'une tentative d'insertion orpheline est
effectivement rejetée par PostgreSQL, pas seulement supposée l'être.
"""

from __future__ import annotations

import psycopg
import pytest

from tests.helpers import create_company, create_fiscal_year, create_sector


def test_fiscal_periods_rejects_unknown_company(db_conn):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO fiscal_periods (company_id, period_end_date, fiscal_year, period_type) "
                "VALUES (999999, '2021-12-31', 2021, 'FY')"
            )
    db_conn.rollback()


def test_income_statements_rejects_unknown_fiscal_period(db_conn):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with db_conn.cursor() as cur:
            cur.execute("INSERT INTO income_statements (fiscal_period_id, revenue) VALUES (999999, 100)")
    db_conn.rollback()


def test_market_prices_rejects_unknown_company(db_conn):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO market_prices (company_id, price_date, close_price) "
                "VALUES (999999, '2021-01-01', 100)"
            )
    db_conn.rollback()


def test_transactions_rejects_same_company_as_acquirer_and_target(db_conn):
    """CHECK chk_transactions_parties : une entreprise ne peut pas s'acquérir
    elle-même."""
    sector_id = create_sector(db_conn, "Test Sector")
    company_id = create_company(db_conn, "SELF", "Self Corp", sector_id)
    with pytest.raises(psycopg.errors.CheckViolation):
        with db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO transactions
                    (acquirer_company_id, target_company_id, announce_date, status, source_type, source_url)
                VALUES (%s, %s, '2021-01-01', 'announced', '8-K', 'https://example.test')
                """,
                (company_id, company_id),
            )
    db_conn.rollback()


def test_fiscal_periods_rejects_duplicate_period_for_same_company(db_conn):
    """UNIQUE (company_id, period_end_date, period_type) — idempotence des
    loaders (docs/00_project_charter.md, section 9 étape 3)."""
    sector_id = create_sector(db_conn, "Test Sector")
    company_id = create_company(db_conn, "DUP", "Dup Corp", sector_id)
    create_fiscal_year(db_conn, company_id, 2021, revenue=100)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO fiscal_periods (company_id, period_end_date, fiscal_year, period_type) "
                "VALUES (%s, '2021-12-31', 2021, 'FY')",
                (company_id,),
            )
    db_conn.rollback()


def test_companies_rejects_public_company_without_ticker(db_conn):
    """CHECK chk_companies_public_ticker : une entreprise publique doit avoir
    un ticker (docs/01_data_model.md, section 3.5)."""
    sector_id = create_sector(db_conn, "Test Sector")
    with pytest.raises(psycopg.errors.CheckViolation):
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO companies (ticker, name, sector_id, country, is_public) "
                "VALUES (NULL, 'Should Fail Corp', %s, 'US', TRUE)",
                (sector_id,),
            )
    db_conn.rollback()


def test_companies_allows_private_company_without_ticker(db_conn):
    """Cas explicitement anticipé : cible M&A privée (docs/01_data_model.md,
    section 3.5 ; réellement utilisé pour Lhoist North America, étape 7)."""
    sector_id = create_sector(db_conn, "Test Sector")
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO companies (ticker, name, sector_id, country, is_public) "
            "VALUES (NULL, 'Private Target Corp', %s, 'US', FALSE) RETURNING company_id",
            (sector_id,),
        )
        assert cur.fetchone() is not None
