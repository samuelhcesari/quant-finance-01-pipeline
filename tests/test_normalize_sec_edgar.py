"""Tests unitaires du normalizer SEC EDGAR (charte section 10 : "parsing des
données brutes... cas limites"). Fixtures JSON synthétiques minimales,
reproduisant la forme réelle de l'API Company Facts — pas d'appel réseau.
Chaque cas reproduit un bug réel trouvé et corrigé pendant le chargement
(docs/data_sources.md section 6), pour empêcher une régression silencieuse.
"""

from __future__ import annotations

from financial_intelligence.data.normalize_sec_edgar import (
    _find_duration_value,
    _find_instant_value,
    _is_annual_duration,
    extract_annual_rows,
)


def _usd_concept(entries: list[dict]) -> dict:
    return {"units": {"USD": entries}}


def test_is_annual_duration_true_for_full_year():
    assert _is_annual_duration({"start": "2021-01-01", "end": "2021-12-31"}) is True


def test_is_annual_duration_false_for_quarter():
    assert _is_annual_duration({"start": "2021-10-01", "end": "2021-12-31"}) is False


def test_is_annual_duration_false_when_dates_missing():
    assert _is_annual_duration({"start": None, "end": "2021-12-31"}) is False
    assert _is_annual_duration({"start": "2021-01-01", "end": None}) is False


def test_find_instant_value_missing_tag_returns_none():
    us_gaap = {"Assets": _usd_concept([{"accn": "A1", "end": "2021-12-31", "val": 100}])}
    assert _find_instant_value(us_gaap, ["Liabilities"], "A1", "2021-12-31") is None


def test_find_instant_value_uses_first_matching_tag_in_priority_order():
    us_gaap = {
        "CashAndCashEquivalentsAtCarryingValue": _usd_concept(
            [{"accn": "A1", "end": "2021-12-31", "val": 42}]
        ),
    }
    tags = ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]
    assert _find_instant_value(us_gaap, tags, "A1", "2021-12-31") == 42


def test_find_duration_value_disambiguates_quarter_from_full_year():
    """Reproduit le bug BMY 2015 : un NetIncomeLoss trimestriel (T4 seul) et
    un NetIncomeLoss annuel partagent la même date de fin dans le même filing
    -> seule la correspondance (accn, start, end) exacte doit être retenue."""
    us_gaap = {
        "NetIncomeLoss": _usd_concept(
            [
                {"accn": "A1", "start": "2015-10-01", "end": "2015-12-31", "val": -197_000_000},  # T4 seul
                {"accn": "A1", "start": "2015-01-01", "end": "2015-12-31", "val": 1_565_000_000},  # exercice complet
            ]
        )
    }
    annual = _find_duration_value(us_gaap, ["NetIncomeLoss"], "A1", "2015-01-01", "2015-12-31")
    quarterly = _find_duration_value(us_gaap, ["NetIncomeLoss"], "A1", "2015-10-01", "2015-12-31")
    assert annual == 1_565_000_000
    assert quarterly == -197_000_000


def test_extract_annual_rows_skips_quarterly_supplementary_data():
    """Le concept ancre (NetIncomeLoss) filtré sur une durée ~365 jours ne
    doit retenir que l'exercice complet, pas les données trimestrielles
    supplémentaires taguées form=10-K/fp=FY dans le même filing."""
    facts = {
        "cik": 14272,
        "entityName": "Test Corp",
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": _usd_concept(
                    [
                        {"accn": "A1", "start": "2015-10-01", "end": "2015-12-31", "val": -197_000_000,
                         "fy": 2015, "fp": "FY", "form": "10-K", "filed": "2016-02-01"},
                        {"accn": "A1", "start": "2015-01-01", "end": "2015-12-31", "val": 1_565_000_000,
                         "fy": 2015, "fp": "FY", "form": "10-K", "filed": "2016-02-01"},
                    ]
                ),
                "Assets": _usd_concept([{"accn": "A1", "end": "2015-12-31", "val": 50_000_000_000}]),
            }
        },
    }
    rows = extract_annual_rows(facts, "TEST")
    assert len(rows) == 1
    assert rows[0]["net_income"] == 1_565_000_000
    assert rows[0]["total_assets"] == 50_000_000_000


def test_extract_annual_rows_keeps_earliest_filing_per_period():
    """Un même exercice apparaît dans son propre 10-K (fy correct) puis en
    comparatif dans le 10-K suivant (fy parfois retagué à tort, cf. AAPL
    2024-09-28 retagué fy=2025 dans le 10-K FY2025) -> le filing le plus
    ancien doit être retenu."""
    facts = {
        "cik": 1,
        "entityName": "Test Corp",
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": _usd_concept(
                    [
                        {"accn": "ORIGINAL", "start": "2023-01-01", "end": "2023-12-31", "val": 100,
                         "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-02-01"},
                        {"accn": "COMPARATIVE", "start": "2023-01-01", "end": "2023-12-31", "val": 100,
                         "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01"},  # fy retagué, filing ultérieur
                    ]
                ),
                "Assets": _usd_concept(
                    [
                        {"accn": "ORIGINAL", "end": "2023-12-31", "val": 900},
                        {"accn": "COMPARATIVE", "end": "2023-12-31", "val": 900},
                    ]
                ),
            }
        },
    }
    rows = extract_annual_rows(facts, "TEST")
    assert len(rows) == 1
    assert rows[0]["accn"] == "ORIGINAL"
    assert rows[0]["fiscal_year"] == 2023  # dérivé de period_end_date, pas du tag `fy` du filing ultérieur


def test_extract_annual_rows_fiscal_year_52_53_week_calendar_edge_case():
    """Calendrier fiscal 52/53 semaines (ex. JNJ) : une clôture le 1er-3
    janvier appartient à l'exercice précédent, sinon elle entrerait en
    collision avec l'exercice qui se termine réellement en décembre de cette
    même année civile."""
    facts = {
        "cik": 1, "entityName": "Test Corp",
        "facts": {"us-gaap": {
            "NetIncomeLoss": _usd_concept(
                [{"accn": "A1", "start": "2011-01-03", "end": "2012-01-01", "val": 100,
                  "fy": 2012, "fp": "FY", "form": "10-K", "filed": "2012-02-01"}]
            ),
            "Assets": _usd_concept([{"accn": "A1", "end": "2012-01-01", "val": 900}]),
        }},
    }
    rows = extract_annual_rows(facts, "TEST")
    assert rows[0]["fiscal_year"] == 2011


def test_extract_annual_rows_missing_tag_stays_none_not_invented():
    facts = {
        "cik": 1, "entityName": "Test Corp",
        "facts": {"us-gaap": {
            "NetIncomeLoss": _usd_concept(
                [{"accn": "A1", "start": "2021-01-01", "end": "2021-12-31", "val": 100,
                  "fy": 2021, "fp": "FY", "form": "10-K", "filed": "2022-02-01"}]
            ),
            "Assets": _usd_concept([{"accn": "A1", "end": "2021-12-31", "val": 900}]),
            # Aucun tag de revenu présent dans ce filing synthétique.
        }},
    }
    rows = extract_annual_rows(facts, "TEST")
    assert rows[0]["revenue"] is None


def test_extract_annual_rows_gross_profit_fallback_from_revenue_minus_cogs():
    facts = {
        "cik": 1, "entityName": "Test Corp",
        "facts": {"us-gaap": {
            "NetIncomeLoss": _usd_concept(
                [{"accn": "A1", "start": "2021-01-01", "end": "2021-12-31", "val": 100,
                  "fy": 2021, "fp": "FY", "form": "10-K", "filed": "2022-02-01"}]
            ),
            "Assets": _usd_concept([{"accn": "A1", "end": "2021-12-31", "val": 900}]),
            "Revenues": _usd_concept(
                [{"accn": "A1", "start": "2021-01-01", "end": "2021-12-31", "val": 1000}]
            ),
            "CostOfGoodsAndServicesSold": _usd_concept(
                [{"accn": "A1", "start": "2021-01-01", "end": "2021-12-31", "val": 600}]
            ),
            # Pas de tag GrossProfit direct -> doit être recalculé 1000 - 600.
        }},
    }
    rows = extract_annual_rows(facts, "TEST")
    assert rows[0]["gross_profit"] == 400


def test_extract_annual_rows_ebitda_requires_both_ebit_and_depreciation():
    facts_missing_da = {
        "cik": 1, "entityName": "Test Corp",
        "facts": {"us-gaap": {
            "NetIncomeLoss": _usd_concept(
                [{"accn": "A1", "start": "2021-01-01", "end": "2021-12-31", "val": 100,
                  "fy": 2021, "fp": "FY", "form": "10-K", "filed": "2022-02-01"}]
            ),
            "Assets": _usd_concept([{"accn": "A1", "end": "2021-12-31", "val": 900}]),
            "OperatingIncomeLoss": _usd_concept(
                [{"accn": "A1", "start": "2021-01-01", "end": "2021-12-31", "val": 200}]
            ),
            # Pas de tag de dépréciation/amortissement -> ebitda doit rester NULL, pas ebit seul.
        }},
    }
    rows = extract_annual_rows(facts_missing_da, "TEST")
    assert rows[0]["ebit"] == 200
    assert rows[0]["ebitda"] is None
