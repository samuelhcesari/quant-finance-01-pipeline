"""Tests SQL des vues de ratios contre une entreprise fictive dont les
résultats attendus sont calculés à la main (charte section 10 : "une
entreprise fictive avec Revenue, EBITDA, Debt connus -> vérifier que
v_leverage_ratios renvoie exactement la valeur attendue"). Base éphémère
(tests/conftest.py), transaction annulée après chaque test.

Données synthétiques (2 exercices consécutifs, "Fictive Corp") :

            FY2020   FY2021
revenue      1000     1200
cogs          600      700
gross_profit  400      500
ebitda        300      360
ebit          200      240
interest_exp   20       24
pretax_income 180      216
tax_expense    36     43.2
net_income    144    172.8
total_assets 1000     1100
total_equity  500      580
cash           50       80
st_debt        50       40
lt_debt       250      260
total_liab    500      520
cfo           250      300
capex          50       60
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tests.helpers import create_company, create_fiscal_year, create_sector


def _to_float(value):
    return float(value) if isinstance(value, Decimal) else value


@pytest.fixture()
def fictive_corp(db_conn):
    sector_id = create_sector(db_conn, "Test Sector")
    company_id = create_company(db_conn, "FICT", "Fictive Corp", sector_id)
    create_fiscal_year(
        db_conn, company_id, 2020,
        revenue=1000, cogs=600, gross_profit=400, ebitda=300, ebit=200,
        interest_expense=20, pretax_income=180, tax_expense=36, net_income=144,
        total_assets=1000, total_equity=500, cash_and_equivalents=50,
        short_term_debt=50, long_term_debt=250, total_liabilities=500,
        cfo=250, capex=50,
    )
    create_fiscal_year(
        db_conn, company_id, 2021,
        revenue=1200, cogs=700, gross_profit=500, ebitda=360, ebit=240,
        interest_expense=24, pretax_income=216, tax_expense=43.2, net_income=172.8,
        total_assets=1100, total_equity=580, cash_and_equivalents=80,
        short_term_debt=40, long_term_debt=260, total_liabilities=520,
        cfo=300, capex=60,
    )
    return company_id


def _fetch_one(db_conn, view: str, company_id: int, fiscal_year: int) -> dict:
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {view} WHERE company_id = %s AND fiscal_year = %s", (company_id, fiscal_year))
        columns = [c.name for c in cur.description]
        row = cur.fetchone()
        assert row is not None, f"aucune ligne dans {view} pour company_id={company_id} fiscal_year={fiscal_year}"
        return {col: _to_float(val) for col, val in zip(columns, row)}


def test_v_margins_fy2021(db_conn, fictive_corp):
    row = _fetch_one(db_conn, "v_margins", fictive_corp, 2021)
    assert row["gross_margin"] == pytest.approx(500 / 1200)
    assert row["ebitda_margin"] == pytest.approx(360 / 1200)
    assert row["ebit_margin"] == pytest.approx(240 / 1200)
    assert row["net_margin"] == pytest.approx(172.8 / 1200)


def test_v_growth_fy2021_vs_fy2020(db_conn, fictive_corp):
    row = _fetch_one(db_conn, "v_growth", fictive_corp, 2021)
    assert row["revenue_growth"] == pytest.approx(1200 / 1000 - 1)  # 0.20
    assert row["ebitda_growth"] == pytest.approx(360 / 300 - 1)  # 0.20
    fcf_2021 = 300 - 60
    fcf_2020 = 250 - 50
    assert row["fcf_growth"] == pytest.approx(fcf_2021 / fcf_2020 - 1)  # 0.20
    assert row["consecutive_year"] is True


def test_v_returns_fy2021(db_conn, fictive_corp):
    row = _fetch_one(db_conn, "v_returns", fictive_corp, 2021)
    avg_equity = (580 + 500) / 2
    avg_assets = (1100 + 1000) / 2
    assert row["roe"] == pytest.approx(172.8 / avg_equity)  # 0.32
    assert row["roa"] == pytest.approx(172.8 / avg_assets)
    assert row["effective_tax_rate"] == pytest.approx(43.2 / 216)  # 0.20
    nopat = 240 * (1 - 43.2 / 216)  # 192
    invested_capital = (40 + 260) + 580 - 80  # 800
    assert row["nopat"] == pytest.approx(nopat)
    assert row["invested_capital"] == pytest.approx(invested_capital)
    assert row["roic"] == pytest.approx(nopat / invested_capital)  # 0.24


def test_v_leverage_fy2021(db_conn, fictive_corp):
    row = _fetch_one(db_conn, "v_leverage", fictive_corp, 2021)
    total_debt = 40 + 260  # 300
    net_debt = total_debt - 80  # 220
    assert row["total_debt"] == pytest.approx(total_debt)
    assert row["net_debt"] == pytest.approx(net_debt)
    assert row["net_debt_to_ebitda"] == pytest.approx(net_debt / 360)
    assert row["debt_to_equity"] == pytest.approx(total_debt / 580)
    assert row["interest_coverage"] == pytest.approx(240 / 24)  # 10.0


def test_v_cash_flow_fy2021(db_conn, fictive_corp):
    row = _fetch_one(db_conn, "v_cash_flow", fictive_corp, 2021)
    fcf = 300 - 60  # 240
    assert row["fcf"] == pytest.approx(fcf)
    assert row["fcf_margin"] == pytest.approx(fcf / 1200)  # 0.20
    assert row["fcf_conversion"] == pytest.approx(fcf / 360)  # 0.6667


def test_v_growth_first_year_has_no_prior_period(db_conn, fictive_corp):
    """FY2020 est le premier exercice de l'entreprise fictive -> pas de LAG
    disponible, la croissance doit être NULL, pas 0 ni une erreur."""
    row = _fetch_one(db_conn, "v_growth", fictive_corp, 2020)
    assert row["revenue_growth"] is None
    assert row["consecutive_year"] is None  # pas d'exercice précédent du tout


def test_v_margins_handles_null_revenue_without_error(db_conn):
    """Dénominateur nul (charte section 5 : "cas à traiter explicitement, pas
    ignoré") -> NULLIF évite la division par zéro, la marge doit être NULL,
    pas une erreur SQL ni une valeur infinie."""
    sector_id = create_sector(db_conn, "Test Sector")
    company_id = create_company(db_conn, "ZERO", "Zero Revenue Corp", sector_id)
    create_fiscal_year(db_conn, company_id, 2021, revenue=0, gross_profit=0, ebitda=0)
    row = _fetch_one(db_conn, "v_margins", company_id, 2021)
    assert row["gross_margin"] is None
    assert row["ebitda_margin"] is None
