"""Tests de v_data_quality_flags (sql/views/013_...sql) — identité comptable
et détection d'outliers, sur des entreprises fictives dont le résultat
attendu est connu à l'avance."""

from __future__ import annotations

import pytest

from tests.helpers import create_company, create_fiscal_year, create_sector


def _refresh_and_fetch(db_conn, company_id: int, fiscal_year: int) -> dict:
    with db_conn.cursor() as cur:
        cur.execute("REFRESH MATERIALIZED VIEW mv_company_financial_profile")
        cur.execute(
            "SELECT * FROM v_data_quality_flags WHERE company_id = %s AND fiscal_year = %s",
            (company_id, fiscal_year),
        )
        columns = [c.name for c in cur.description]
        row = cur.fetchone()
        assert row is not None
        return dict(zip(columns, row))


def test_accounting_identity_ok_when_balanced(db_conn):
    sector_id = create_sector(db_conn, "Test Sector")
    company_id = create_company(db_conn, "BAL", "Balanced Corp", sector_id)
    create_fiscal_year(
        db_conn, company_id, 2021,
        revenue=1000, ebitda=200, ebit=150,
        total_assets=1000, total_liabilities=600, total_equity=400,
    )
    row = _refresh_and_fetch(db_conn, company_id, 2021)
    assert row["accounting_identity_ok"] is True


def test_accounting_identity_fails_when_unbalanced(db_conn):
    sector_id = create_sector(db_conn, "Test Sector")
    company_id = create_company(db_conn, "UNBAL", "Unbalanced Corp", sector_id)
    create_fiscal_year(
        db_conn, company_id, 2021,
        revenue=1000, ebitda=200, ebit=150,
        total_assets=1000, total_liabilities=600, total_equity=100,  # 600+100 != 1000
    )
    row = _refresh_and_fetch(db_conn, company_id, 2021)
    assert row["accounting_identity_ok"] is False


def test_accounting_identity_null_when_data_missing(db_conn):
    sector_id = create_sector(db_conn, "Test Sector")
    company_id = create_company(db_conn, "MISS", "Missing Data Corp", sector_id)
    create_fiscal_year(
        db_conn, company_id, 2021,
        revenue=1000, ebitda=200, ebit=150,
        total_assets=1000, total_equity=400,  # total_liabilities absent
    )
    row = _refresh_and_fetch(db_conn, company_id, 2021)
    assert row["accounting_identity_ok"] is None


def test_extreme_growth_flagged_as_outlier_vs_sector_peers(db_conn):
    """20 pairs à +5% de croissance, une 21e à +5000% -> doit être flaguée
    outlier. N=20 plutôt que N=5 : avec trop peu de pairs, l'outlier gonfle
    lui-même la moyenne/écart-type du secteur et peut repasser sous |z|>3."""
    sector_id = create_sector(db_conn, "Test Sector")
    for i in range(20):
        cid = create_company(db_conn, f"PEER{i}", f"Peer {i}", sector_id)
        create_fiscal_year(db_conn, cid, 2020, revenue=1000, ebitda=200, ebit=150,
                            total_assets=1000, total_liabilities=500, total_equity=500)
        create_fiscal_year(db_conn, cid, 2021, revenue=1050, ebitda=200, ebit=150,
                            total_assets=1000, total_liabilities=500, total_equity=500)

    outlier_id = create_company(db_conn, "OUTLIER", "Outlier Corp", sector_id)
    create_fiscal_year(db_conn, outlier_id, 2020, revenue=1000, ebitda=200, ebit=150,
                        total_assets=1000, total_liabilities=500, total_equity=500)
    create_fiscal_year(db_conn, outlier_id, 2021, revenue=51000, ebitda=200, ebit=150,
                        total_assets=1000, total_liabilities=500, total_equity=500)

    row = _refresh_and_fetch(db_conn, outlier_id, 2021)
    assert row["revenue_growth_outlier"] is True


def test_no_outlier_flagged_when_peers_are_similar(db_conn):
    sector_id = create_sector(db_conn, "Test Sector")
    for i in range(5):
        cid = create_company(db_conn, f"SIM{i}", f"Similar {i}", sector_id)
        create_fiscal_year(db_conn, cid, 2020, revenue=1000, ebitda=200, ebit=150,
                            total_assets=1000, total_liabilities=500, total_equity=500)
        create_fiscal_year(db_conn, cid, 2021, revenue=1050 + i, ebitda=200, ebit=150,
                            total_assets=1000, total_liabilities=500, total_equity=500)

    row = _refresh_and_fetch(db_conn, cid, 2021)
    assert row["revenue_growth_outlier"] is False
