"""Normalise le JSON brut SEC EDGAR (data/raw/sec_edgar/*.json) en lignes
tabulaires annuelles (1 ligne = 1 entreprise x 1 exercice fiscal), écrites dans
data/processed/financials_annual.csv.

Portée assumée pour ce premier chargement : uniquement les dépôts annuels
(form=10-K, fp=FY) — le détail trimestriel n'est pas chargé à ce stade
(limitation documentée dans docs/data_sources.md).

Toute valeur non trouvée dans le filing reste vide (aucune donnée inventée).
Seules deux valeurs sont recalculées arithmétiquement à partir de faits bruts
du même filing, jamais estimées : gross_profit = revenue - cogs (si le tag
GrossProfit est absent) et ebitda = ebit + D&A (EBITDA n'est pas un concept
US-GAAP standard, il n'existe donc aucun tag XBRL direct à préférer).

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

    # Une période annuelle = une entrée d'un concept ancre "duration"
    # (NetIncomeLoss, avec repli ProfitLoss) taguée form=10-K/fp=FY ET dont la
    # durée (end - start) correspond à un exercice complet (~365 jours). Ce
    # filtre sur la durée est indispensable : certains 10-K contiennent des
    # données trimestrielles supplémentaires (note "quarterly financial data")
    # elles aussi taguées form=10-K/fp=FY, avec parfois la même date de fin que
    # le T4 annuel (ex. BMY 2015 : un NetIncomeLoss "2015-10-01 -> 2015-12-31"
    # (T4 seul) coexiste avec "2015-01-01 -> 2015-12-31" (exercice complet)
    # dans le même filing) — sans ce filtre de durée, les deux se confondent.
    #
    # Un même exercice apparaît aussi dans plusieurs 10-K différents (année
    # courante lors de son propre 10-K, puis comparatif dans les 10-K
    # suivants). On garde le filing le PLUS ANCIEN par date de fin : c'est le
    # 10-K où cette période était l'exercice courant, donc le seul où le tag
    # `fy` de SEC EDGAR est fiable (dans un 10-K ultérieur, la période
    # comparative hérite du `fy` du filing, pas de sa propre année — constaté
    # sur AAPL : le 10-K FY2025 retague le bilan 2024-09-28 avec fy=2025 alors
    # que le 10-K FY2024 d'origine le tague correctement fy=2024, avec la même
    # valeur dans les deux cas). Choix qui a aussi l'avantage d'éviter tout
    # biais de "look-ahead" via un restatement ultérieur : les chiffres
    # retenus sont ceux "as originally reported".
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

        # fiscal_year dérivé de period_end_date, pas du tag `fy` de SEC EDGAR :
        # celui-ci s'est révélé peu fiable pour les tableaux "Selected
        # Financial Data" (5 ans d'historique) des 10-K anciens (~2009-2011),
        # où plusieurs exercices distincts sont parfois tagués avec le même
        # `fy` (celui du dépôt). L'année de la date de clôture est déterministe
        # et vérifiable pour l'ensemble de l'échantillon. Cas particulier des
        # calendriers fiscaux 52/53 semaines (ex. JNJ) : la clôture tombe
        # parfois le 1er/2/3 janvier de l'année suivante — dans ce cas
        # l'exercice appartient à l'année précédente (ex. clôture 2012-01-01 =
        # exercice 2011), sans quoi elle entrerait en collision avec
        # l'exercice qui se termine réellement en décembre de cette même année.
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

    # Taux de remplissage par champ, pour documentation honnête des trous XBRL.
    fill_fields = [c for c in OUTPUT_COLUMNS if c not in ("ticker", "cik", "entity_name", "fiscal_year", "period_end_date", "filed", "accn", "form")]
    print("\nTaux de remplissage par champ :")
    for field in fill_fields:
        n_filled = sum(1 for r in all_rows if r.get(field) is not None)
        pct = (n_filled / len(all_rows) * 100) if all_rows else 0
        print(f"  {field:28s} {n_filled:4d}/{len(all_rows)} ({pct:5.1f}%)")

    return {"companies": len(json_files), "rows": len(all_rows)}


if __name__ == "__main__":
    run()
