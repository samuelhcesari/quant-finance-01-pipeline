"""Test bout-en-bout du moteur de screening. Deux entreprises fictives sur
3 exercices consécutifs (requis pour ebitda_margin_3y_avg/revenue_growth_3y_avg
du profil "quality") : GoodCo satisfait toutes les règles, BadCo aucune.
Passe par la vraie pile : insertion SQL -> v_screening_base ->
configs/screening/quality.yaml -> evaluate_profile.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from financial_intelligence.analytics.screening_engine import evaluate_profile, load_profiles
from tests.helpers import create_company, create_fiscal_year, create_sector


def _to_float(value):
    return float(value) if isinstance(value, Decimal) else value


def _fetch_screening_row(db_conn, company_id: int, fiscal_year: int) -> dict:
    with db_conn.cursor() as cur:
        # v_screening_base lit mv_company_financial_profile (vue matérialisée,
        # sql/optimization/001_...sql) : les lignes insérées par ce test dans
        # la même transaction n'y apparaissent qu'après un REFRESH explicite
        # (une vue matérialisée n'est pas recalculée automatiquement).
        cur.execute("REFRESH MATERIALIZED VIEW mv_company_financial_profile")
        cur.execute(
            "SELECT * FROM v_screening_base WHERE company_id = %s AND fiscal_year = %s",
            (company_id, fiscal_year),
        )
        columns = [c.name for c in cur.description]
        row = cur.fetchone()
        assert row is not None
        return {col: _to_float(val) for col, val in zip(columns, row)}


def _quality_profile() -> dict:
    profiles = load_profiles()
    (quality,) = [p for p in profiles if p["code"] == "quality"]
    return quality


def test_quality_profile_passes_for_synthetic_good_company(db_conn):
    sector_id = create_sector(db_conn, "Test Sector")
    company_id = create_company(db_conn, "GOOD", "GoodCo", sector_id)
    # 3 exercices consécutifs, marge ~25%, croissance positive, levier faible, ROIC élevé.
    create_fiscal_year(
        db_conn, company_id, 2019, revenue=1000, ebitda=250, ebit=220, pretax_income=100,
        tax_expense=20, net_income=80, total_equity=400, cash_and_equivalents=50,
        short_term_debt=0, long_term_debt=100,
    )
    create_fiscal_year(
        db_conn, company_id, 2020, revenue=1100, ebitda=275, ebit=240, pretax_income=110,
        tax_expense=22, net_income=88, total_equity=430, cash_and_equivalents=55,
        short_term_debt=0, long_term_debt=100,
    )
    create_fiscal_year(
        db_conn, company_id, 2021, revenue=1200, ebitda=300, ebit=260, pretax_income=120,
        tax_expense=24, net_income=96, total_equity=460, cash_and_equivalents=60,
        short_term_debt=0, long_term_debt=100,
    )

    row = _fetch_screening_row(db_conn, company_id, 2021)
    assert row["years_available_for_avg"] == 3
    assert row["ebitda_margin_3y_avg"] > 0.20
    assert row["roic"] > 0.15
    assert row["net_debt_to_ebitda"] < 2.0
    assert row["revenue_growth_3y_avg"] > 0

    passed, score = evaluate_profile(_quality_profile(), row)
    assert passed is True
    assert score == 1.0


def test_quality_profile_fails_for_synthetic_bad_company(db_conn):
    sector_id = create_sector(db_conn, "Test Sector")
    company_id = create_company(db_conn, "BAD", "BadCo", sector_id)
    # 3 exercices consécutifs, marge faible, revenu en déclin, levier très élevé, ROIC quasi nul.
    create_fiscal_year(
        db_conn, company_id, 2019, revenue=1000, ebitda=50, ebit=10, pretax_income=5,
        tax_expense=2, net_income=3, total_equity=100, cash_and_equivalents=10,
        short_term_debt=200, long_term_debt=300,
    )
    create_fiscal_year(
        db_conn, company_id, 2020, revenue=900, ebitda=40, ebit=8, pretax_income=4,
        tax_expense=1.6, net_income=2.4, total_equity=90, cash_and_equivalents=8,
        short_term_debt=200, long_term_debt=305,
    )
    create_fiscal_year(
        db_conn, company_id, 2021, revenue=800, ebitda=30, ebit=5, pretax_income=2,
        tax_expense=1, net_income=1, total_equity=80, cash_and_equivalents=5,
        short_term_debt=200, long_term_debt=310,
    )

    row = _fetch_screening_row(db_conn, company_id, 2021)
    assert row["years_available_for_avg"] == 3
    assert row["ebitda_margin_3y_avg"] < 0.20
    assert row["roic"] < 0.15
    assert row["net_debt_to_ebitda"] > 2.0
    assert row["revenue_growth_3y_avg"] < 0

    passed, score = evaluate_profile(_quality_profile(), row)
    assert passed is False
    # 1 règle sur 5 est quand même satisfaite : years_available_for_avg == 3
    # (BadCo a 3 exercices de données, comme GoodCo — la disponibilité de la
    # donnée n'est pas en soi un signal de qualité financière).
    assert score == pytest.approx(0.2)
