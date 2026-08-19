"""Normalise le JSON brut SEC EDGAR (data/raw/sec_edgar/*.json) en lignes
tabulaires annuelles (1 ligne = 1 entreprise x 1 exercice fiscal), écrites dans
data/processed/financials_annual.csv.

Uniquement les dépôts annuels (form=10-K, fp=FY) — pas de détail trimestriel
pour l'instant (docs/data_sources.md).

Deux champs sont recalculés depuis d'autres faits du même filing plutôt que
laissés vides : gross_profit = revenue - cogs si le tag GrossProfit est
absent, et ebitda = ebit + D&A (EBITDA n'a pas de tag XBRL direct).

Usage : python -m financial_intelligence.data.normalize_sec_edgar
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from financial_intelligence.data.xbrl_concepts import (
    ANCHOR_TAGS,
    ANNUAL_DURATION_MAX_DAYS,
    ANNUAL_DURATION_MIN_DAYS,
    BALANCE_SHEET_TAGS,
    CASH_FLOW_TAGS,
    DEPRECIATION_AMORTIZATION_TAGS,
    INCOME_STATEMENT_PER_SHARE_TAGS,
    INCOME_STATEMENT_SHARES_TAGS,
    INCOME_STATEMENT_TAGS,
)
from financial_intelligence.utils.config import DATA_PROCESSED_DIR, DATA_RAW_DIR

OUTPUT_COLUMNS = [
    "ticker",
    "cik",
    "entity_name",
    "fiscal_year",
    "period_end_date",
    "filed",
    "accn",
    "form",
    "revenue",
    "cogs",
    "gross_profit",
    "sga_expense",
    "ebit",
    "ebitda",
    "interest_expense",
    "pretax_income",
    "tax_expense",
    "net_income",
    "eps_basic",
    "eps_diluted",
    "shares_basic",
    "shares_diluted",
    "cash_and_equivalents",
    "total_current_assets",
    "total_assets",
    "short_term_debt",
    "long_term_debt",
    "total_current_liabilities",
    "total_liabilities",
    "total_equity",
    "cfo",
    "capex",
    "cfi",
    "cff",
    "dividends_paid",
]


def _is_annual_duration(entry: dict) -> bool:
    start = entry.get("start")
    end = entry.get("end")
    if not start or not end:
        return False
    delta = (date.fromisoformat(end) - date.fromisoformat(start)).days
    return ANNUAL_DURATION_MIN_DAYS <= delta <= ANNUAL_DURATION_MAX_DAYS


def _find_instant_value(us_gaap: dict, tags: list[str], accn: str, end: str, unit: str = "USD") -> float | None:
    """Concept "instant" (bilan) : identifié par (accn, end) uniquement — pas
    de start, une seule valeur possible par date de clôture."""
    for tag in tags:
        concept = us_gaap.get(tag)
        if not concept:
            continue
        for entry in concept.get("units", {}).get(unit, []):
            if entry.get("accn") == accn and entry.get("end") == end:
                return entry["val"]
    return None


def _find_duration_value(
    us_gaap: dict, tags: list[str], accn: str, start: str, end: str, unit: str = "USD"
) -> float | None:
    """Concept "duration" (résultat, flux) : DOIT matcher (accn, start, end)
    exactement. Un même filing/accn/end peut contenir plusieurs durées
    différentes pour le même concept (ex. le T4 seul ET l'exercice complet
    finissent tous deux le 31/12) — matcher sur `end` seul retournerait parfois
    la valeur trimestrielle au lieu de l'annuelle."""
    for tag in tags:
        concept = us_gaap.get(tag)
        if not concept:
            continue
        for entry in concept.get("units", {}).get(unit, []):
            if entry.get("accn") == accn and entry.get("start") == start and entry.get("end") == end:
                return entry["val"]
    return None


def extract_annual_rows(facts_json: dict, ticker: str) -> list[dict[str, Any]]:
    us_gaap = facts_json.get("facts", {}).get("us-gaap", {})
    cik = facts_json.get("cik")
    entity_name = facts_json.get("entityName")

    # Ancre = NetIncomeLoss (repli ProfitLoss), form=10-K/fp=FY, durée ~365j.
    # Le filtre de durée exclut les données trimestrielles parfois présentes
    # dans le même filing avec la même date de fin que le T4 (ex. BMY 2015).
    # Un exercice apparaît dans plusieurs 10-K (courant, puis comparatif dans
    # les suivants) ; on garde le filing le plus ancien — le tag `fy` d'un
    # 10-K ultérieur hérite parfois de l'année du filing plutôt que de sa
    # propre année (ex. AAPL, bilan 2024-09-28 retagué fy=2025).
    by_end: dict[str, dict[str, Any]] = {}
    for anchor_tag in ANCHOR_TAGS:
        anchor = us_gaap.get(anchor_tag)
        if not anchor:
            continue
        for entry in anchor.get("units", {}).get("USD", []):
            if entry.get("form") != "10-K" or entry.get("fp") != "FY":
                continue
            if not _is_annual_duration(entry):
                continue
            end = entry["end"]
            current_best = by_end.get(end)
            if current_best is None or entry.get("filed", "") < current_best.get("filed", ""):
                by_end[end] = entry
        if by_end:
            break  # premier concept ancre trouvé avec des données -> pas de repli

    periods = list(by_end.values())

    rows: list[dict[str, Any]] = []
    for p in periods:
        accn, start, end = p["accn"], p["start"], p["end"]
        filed, form = p.get("filed"), p.get("form")

        # fiscal_year = année de period_end_date, pas le tag `fy` (peu fiable
        # sur les 10-K ~2009-2011). Calendriers 52/53 semaines (ex. JNJ) :
        # clôture le 1er-3 janvier -> exercice précédent.
        end_month, end_day = int(end[5:7]), int(end[8:10])
        fiscal_year = int(end[:4])
        if end_month == 1 and end_day <= 3:
            fiscal_year -= 1

        row: dict[str, Any] = {
            "ticker": ticker,
            "cik": cik,
            "entity_name": entity_name,
            "fiscal_year": fiscal_year,
            "period_end_date": end,
            "filed": filed,
            "accn": accn,
            "form": form,
        }

        for field, tags in INCOME_STATEMENT_TAGS.items():
            row[field] = _find_duration_value(us_gaap, tags, accn, start, end)
        for field, tags in BALANCE_SHEET_TAGS.items():
            row[field] = _find_instant_value(us_gaap, tags, accn, end)
        for field, tags in CASH_FLOW_TAGS.items():
            row[field] = _find_duration_value(us_gaap, tags, accn, start, end)
        for field, tags in INCOME_STATEMENT_PER_SHARE_TAGS.items():
            row[field] = _find_duration_value(us_gaap, tags, accn, start, end, unit="USD/shares")
        for field, tags in INCOME_STATEMENT_SHARES_TAGS.items():
            row[field] = _find_duration_value(us_gaap, tags, accn, start, end, unit="shares")

        if row.get("gross_profit") is None and row.get("revenue") is not None and row.get("cogs") is not None:
            row["gross_profit"] = row["revenue"] - row["cogs"]

        d_and_a = _find_duration_value(us_gaap, DEPRECIATION_AMORTIZATION_TAGS, accn, start, end)
        if row.get("ebit") is not None and d_and_a is not None:
            row["ebitda"] = row["ebit"] + d_and_a
        else:
            row["ebitda"] = None

        rows.append(row)

    return rows


def run() -> dict[str, int]:
    in_dir = DATA_RAW_DIR / "sec_edgar"
    out_dir = DATA_PROCESSED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "financials_annual.csv"

    json_files = sorted(in_dir.glob("*.json"))
    if not json_files:
        print(f"Aucun fichier trouvé dans {in_dir}. Lancer fetch_sec_edgar d'abord.", file=sys.stderr)
        sys.exit(1)

    all_rows: list[dict[str, Any]] = []
    per_company_counts: dict[str, int] = {}

    for path in json_files:
        ticker = path.stem
        facts_json = json.loads(path.read_text(encoding="utf-8"))
        rows = extract_annual_rows(facts_json, ticker)
        per_company_counts[ticker] = len(rows)
        all_rows.extend(rows)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print(f"{len(json_files)} entreprises traitées -> {len(all_rows)} lignes annuelles dans {out_path}")
    zero = [t for t, c in per_company_counts.items() if c == 0]
    if zero:
        print(f"  [ATTENTION] 0 période annuelle extraite pour : {zero}")

    # Taux de remplissage par champ (couverture XBRL variable selon le tag).
    fill_fields = [c for c in OUTPUT_COLUMNS if c not in ("ticker", "cik", "entity_name", "fiscal_year", "period_end_date", "filed", "accn", "form")]
    print("\nTaux de remplissage par champ :")
    for field in fill_fields:
        n_filled = sum(1 for r in all_rows if r.get(field) is not None)
        pct = (n_filled / len(all_rows) * 100) if all_rows else 0
        print(f"  {field:28s} {n_filled:4d}/{len(all_rows)} ({pct:5.1f}%)")

    return {"companies": len(json_files), "rows": len(all_rows)}


if __name__ == "__main__":
    run()
