"""Helpers d'insertion de données synthétiques, réutilisés entre fichiers de test."""

from __future__ import annotations

import psycopg


def create_sector(conn: psycopg.Connection, name: str) -> int:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO sectors (name) VALUES (%s) RETURNING sector_id", (name,))
        return cur.fetchone()[0]


def create_company(conn: psycopg.Connection, ticker: str, name: str, sector_id: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO companies (ticker, name, sector_id, country, is_public) "
            "VALUES (%s, %s, %s, 'US', TRUE) RETURNING company_id",
            (ticker, name, sector_id),
        )
        return cur.fetchone()[0]


def create_fiscal_year(
    conn: psycopg.Connection,
    company_id: int,
    fiscal_year: int,
    *,
    revenue: float | None = None,
    cogs: float | None = None,
    gross_profit: float | None = None,
    sga_expense: float | None = None,
    ebitda: float | None = None,
    ebit: float | None = None,
    interest_expense: float | None = None,
    pretax_income: float | None = None,
    tax_expense: float | None = None,
    net_income: float | None = None,
    total_assets: float | None = None,
    total_equity: float | None = None,
    cash_and_equivalents: float | None = None,
    short_term_debt: float | None = None,
    long_term_debt: float | None = None,
    total_liabilities: float | None = None,
    total_current_assets: float | None = None,
    total_current_liabilities: float | None = None,
    cfo: float | None = None,
    capex: float | None = None,
) -> int:
    """Insère une période annuelle complète (fiscal_periods + les 3 états
    financiers) pour une entreprise synthétique. Tous les champs financiers
    sont optionnels (NULL par défaut) — chaque test ne renseigne que ce dont
    il a besoin."""
    period_end = f"{fiscal_year}-12-31"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fiscal_periods (company_id, period_end_date, fiscal_year, period_type, form_type)
            VALUES (%s, %s, %s, 'FY', '10-K')
            RETURNING fiscal_period_id
            """,
            (company_id, period_end, fiscal_year),
        )
        fiscal_period_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO income_statements
                (fiscal_period_id, revenue, cogs, gross_profit, sga_expense, ebitda, ebit,
                 interest_expense, pretax_income, tax_expense, net_income)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                fiscal_period_id, revenue, cogs, gross_profit, sga_expense, ebitda, ebit,
                interest_expense, pretax_income, tax_expense, net_income,
            ),
        )
        cur.execute(
            """
            INSERT INTO balance_sheets
                (fiscal_period_id, cash_and_equivalents, total_current_assets, total_assets,
                 short_term_debt, long_term_debt, total_current_liabilities, total_liabilities, total_equity)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                fiscal_period_id, cash_and_equivalents, total_current_assets, total_assets,
                short_term_debt, long_term_debt, total_current_liabilities, total_liabilities, total_equity,
            ),
        )
        cur.execute(
            """
            INSERT INTO cash_flow_statements (fiscal_period_id, cfo, capex)
            VALUES (%s, %s, %s)
            """,
            (fiscal_period_id, cfo, capex),
        )
    return fiscal_period_id
