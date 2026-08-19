"""Charge les CSV normalisés (data/processed/) dans les 12 tables PostgreSQL.

Idempotent : chaque table est chargée via INSERT ... ON CONFLICT DO UPDATE, sur
les contraintes UNIQUE définies dans sql/schema/001_init.sql. Un re-run produit
le même état final (mêmes lignes mises à jour, pas de doublons).

Ordre de chargement dicté par les FK : sectors -> companies -> fiscal_periods ->
{income_statements, balance_sheets, cash_flow_statements} -> market_prices,
macro_indicators.

Usage : python -m financial_intelligence.data.load_to_postgres
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

import psycopg
import yaml

from financial_intelligence.utils.config import (
    CONFIGS_DIR,
    DATA_PROCESSED_DIR,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
)


def _connect() -> psycopg.Connection:
    return psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num_or_none(v: Any) -> float | None:
    if v is None or v == "":
        return None
    return float(v)


def load_sectors(conn: psycopg.Connection, universe: dict) -> dict[str, int]:
    sector_ids: dict[str, int] = {}
    with conn.cursor() as cur:
        for code, data in universe["sectors"].items():
            cur.execute(
                """
                INSERT INTO sectors (name) VALUES (%s)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING sector_id
                """,
                (data["label"],),
            )
            sector_ids[code] = cur.fetchone()[0]
    conn.commit()
    print(f"  sectors: {len(sector_ids)} lignes")
    return sector_ids


def load_companies(
    conn: psycopg.Connection, financials_rows: list[dict], universe: dict, sector_ids: dict[str, int]
) -> dict[str, int]:
    ticker_to_sector_code = {
        t: code for code, data in universe["sectors"].items() for t in data["tickers"]
    }
    companies: dict[str, dict] = {}
    for row in financials_rows:
        ticker = row["ticker"]
        if ticker not in companies:
            companies[ticker] = {"cik": row["cik"], "name": row["entity_name"]}

    company_ids: dict[str, int] = {}
    with conn.cursor() as cur:
        for ticker, info in sorted(companies.items()):
            sector_code = ticker_to_sector_code.get(ticker)
            sector_id = sector_ids.get(sector_code) if sector_code else None
            cur.execute(
                """
                INSERT INTO companies (cik, ticker, name, sector_id, country, is_public)
                VALUES (%s, %s, %s, %s, 'US', TRUE)
                ON CONFLICT (ticker) DO UPDATE SET
                    cik = EXCLUDED.cik, name = EXCLUDED.name, sector_id = EXCLUDED.sector_id,
                    updated_at = now()
                RETURNING company_id
                """,
                (info["cik"], ticker, info["name"], sector_id),
            )
            company_ids[ticker] = cur.fetchone()[0]
    conn.commit()
    print(f"  companies: {len(company_ids)} lignes")
    return company_ids


def load_financials(
    conn: psycopg.Connection, financials_rows: list[dict], company_ids: dict[str, int]
) -> dict[str, int]:
    n_periods = n_income = n_balance = n_cf = 0
    with conn.cursor() as cur:
        for row in financials_rows:
            company_id = company_ids[row["ticker"]]

            cur.execute(
                """
                INSERT INTO fiscal_periods
                    (company_id, period_end_date, fiscal_year, period_type, form_type,
                     filing_date, source_accession_number)
                VALUES (%s, %s, %s, 'FY', %s, %s, %s)
                ON CONFLICT (company_id, period_end_date, period_type) DO UPDATE SET
                    fiscal_year = EXCLUDED.fiscal_year,
                    form_type = EXCLUDED.form_type,
                    filing_date = EXCLUDED.filing_date,
                    source_accession_number = EXCLUDED.source_accession_number
                RETURNING fiscal_period_id
                """,
                (
                    company_id,
                    row["period_end_date"],
                    int(row["fiscal_year"]),
                    row["form"],
                    row["filed"] or None,
                    row["accn"],
                ),
            )
            fiscal_period_id = cur.fetchone()[0]
            n_periods += 1

            cur.execute(
                """
                INSERT INTO income_statements
                    (fiscal_period_id, revenue, cogs, gross_profit, sga_expense, ebitda, ebit,
                     interest_expense, pretax_income, tax_expense, net_income, eps_basic,
                     eps_diluted, shares_basic, shares_diluted)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fiscal_period_id) DO UPDATE SET
                    revenue = EXCLUDED.revenue, cogs = EXCLUDED.cogs,
                    gross_profit = EXCLUDED.gross_profit, sga_expense = EXCLUDED.sga_expense,
                    ebitda = EXCLUDED.ebitda, ebit = EXCLUDED.ebit,
                    interest_expense = EXCLUDED.interest_expense,
                    pretax_income = EXCLUDED.pretax_income, tax_expense = EXCLUDED.tax_expense,
                    net_income = EXCLUDED.net_income, eps_basic = EXCLUDED.eps_basic,
                    eps_diluted = EXCLUDED.eps_diluted, shares_basic = EXCLUDED.shares_basic,
                    shares_diluted = EXCLUDED.shares_diluted
                """,
                (
                    fiscal_period_id,
                    _num_or_none(row["revenue"]), _num_or_none(row["cogs"]),
                    _num_or_none(row["gross_profit"]), _num_or_none(row["sga_expense"]),
                    _num_or_none(row["ebitda"]), _num_or_none(row["ebit"]),
                    _num_or_none(row["interest_expense"]), _num_or_none(row["pretax_income"]),
                    _num_or_none(row["tax_expense"]), _num_or_none(row["net_income"]),
                    _num_or_none(row["eps_basic"]), _num_or_none(row["eps_diluted"]),
                    _num_or_none(row["shares_basic"]), _num_or_none(row["shares_diluted"]),
                ),
            )
            n_income += 1

            cur.execute(
                """
                INSERT INTO balance_sheets
                    (fiscal_period_id, cash_and_equivalents, total_current_assets, total_assets,
                     short_term_debt, long_term_debt, total_current_liabilities, total_liabilities,
                     total_equity)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fiscal_period_id) DO UPDATE SET
                    cash_and_equivalents = EXCLUDED.cash_and_equivalents,
                    total_current_assets = EXCLUDED.total_current_assets,
                    total_assets = EXCLUDED.total_assets, short_term_debt = EXCLUDED.short_term_debt,
                    long_term_debt = EXCLUDED.long_term_debt,
                    total_current_liabilities = EXCLUDED.total_current_liabilities,
                    total_liabilities = EXCLUDED.total_liabilities, total_equity = EXCLUDED.total_equity
                """,
                (
                    fiscal_period_id,
                    _num_or_none(row["cash_and_equivalents"]), _num_or_none(row["total_current_assets"]),
                    _num_or_none(row["total_assets"]), _num_or_none(row["short_term_debt"]),
                    _num_or_none(row["long_term_debt"]), _num_or_none(row["total_current_liabilities"]),
                    _num_or_none(row["total_liabilities"]), _num_or_none(row["total_equity"]),
                ),
            )
            n_balance += 1

            cur.execute(
                """
                INSERT INTO cash_flow_statements (fiscal_period_id, cfo, capex, cfi, cff, dividends_paid)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (fiscal_period_id) DO UPDATE SET
                    cfo = EXCLUDED.cfo, capex = EXCLUDED.capex, cfi = EXCLUDED.cfi,
                    cff = EXCLUDED.cff, dividends_paid = EXCLUDED.dividends_paid
                """,
                (
                    fiscal_period_id,
                    _num_or_none(row["cfo"]), _num_or_none(row["capex"]), _num_or_none(row["cfi"]),
                    _num_or_none(row["cff"]), _num_or_none(row["dividends_paid"]),
                ),
            )
            n_cf += 1
    conn.commit()
    print(f"  fiscal_periods: {n_periods} lignes")
    print(f"  income_statements: {n_income} lignes")
    print(f"  balance_sheets: {n_balance} lignes")
    print(f"  cash_flow_statements: {n_cf} lignes")
    return {"fiscal_periods": n_periods, "income_statements": n_income, "balance_sheets": n_balance, "cash_flow_statements": n_cf}


def load_market_prices(conn: psycopg.Connection, rows: list[dict], company_ids: dict[str, int]) -> int:
    n = 0
    with conn.cursor() as cur:
        for row in rows:
            company_id = company_ids.get(row["ticker"])
            if company_id is None:
                continue
            cur.execute(
                """
                INSERT INTO market_prices (company_id, price_date, close_price, volume)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (company_id, price_date) DO UPDATE SET
                    close_price = EXCLUDED.close_price, volume = EXCLUDED.volume
                """,
                (company_id, row["price_date"], _num_or_none(row["close_price"]), row["volume"] or None),
            )
            n += 1
    conn.commit()
    print(f"  market_prices: {n} lignes")
    return n


def load_macro_indicators(conn: psycopg.Connection, rows: list[dict]) -> int:
    n = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                """
                INSERT INTO macro_indicators (series_code, obs_date, value)
                VALUES (%s, %s, %s)
                ON CONFLICT (series_code, obs_date) DO UPDATE SET value = EXCLUDED.value
                """,
                (row["series_code"], row["obs_date"], _num_or_none(row["value"])),
            )
            n += 1
    conn.commit()
    print(f"  macro_indicators: {n} lignes")
    return n


def refresh_materialized_views(conn: psycopg.Connection) -> None:
    """mv_company_financial_profile (sql/optimization/001_...sql) ne se
    rafraîchit pas toute seule après un chargement -> sans cet appel, les
    vues qui en dépendent (v_sector_rankings, v_trailing_trends,
    v_screening_base) resteraient sur des données périmées."""
    with conn.cursor() as cur:
        try:
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_company_financial_profile")
        except psycopg.errors.UndefinedTable:
            conn.rollback()
            print(
                "  [ATTENTION] mv_company_financial_profile n'existe pas encore "
                "(sql/optimization/001_...sql non appliqué) — vues dépendantes non rafraîchies.",
                file=sys.stderr,
            )
            return
    conn.commit()
    print("  mv_company_financial_profile rafraîchie.")


def run() -> None:
    universe_path = CONFIGS_DIR / "company_universe.yaml"
    financials_path = DATA_PROCESSED_DIR / "financials_annual.csv"
    market_prices_path = DATA_PROCESSED_DIR / "market_prices.csv"
    macro_path = DATA_PROCESSED_DIR / "macro_indicators.csv"

    for p in (universe_path, financials_path, market_prices_path, macro_path):
        if not p.exists():
            print(f"Fichier manquant : {p}. Lancer les normalizers d'abord.", file=sys.stderr)
            sys.exit(1)

    with open(universe_path, encoding="utf-8") as f:
        universe = yaml.safe_load(f)
    financials_rows = _read_csv(financials_path)
    market_rows = _read_csv(market_prices_path)
    macro_rows = _read_csv(macro_path)

    print(f"Connexion à {DB_HOST}:{DB_PORT}/{DB_NAME} ...")
    conn = _connect()
    try:
        print("Chargement...")
        sector_ids = load_sectors(conn, universe)
        company_ids = load_companies(conn, financials_rows, universe, sector_ids)
        load_financials(conn, financials_rows, company_ids)
        load_market_prices(conn, market_rows, company_ids)
        load_macro_indicators(conn, macro_rows)
        refresh_materialized_views(conn)
        print("\nChargement terminé sans erreur.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
