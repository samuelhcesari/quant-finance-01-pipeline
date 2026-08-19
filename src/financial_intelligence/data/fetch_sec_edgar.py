"""Fetcher SEC EDGAR — télécharge les Company Facts (XBRL) brutes pour l'univers
d'entreprises défini dans configs/company_universe.yaml.

Ne fait aucun parsing/normalisation : sauvegarde le JSON brut tel que renvoyé par
l'API, sans transformation (docs/00_project_charter.md, section 7 — "data/raw/
(JSON/CSV bruts, jamais modifiés)"). La normalisation vers des lignes tabulaires
est une étape séparée (étape 3 du roadmap, sql/schema alimenté par des loaders).

Usage : python -m financial_intelligence.data.fetch_sec_edgar
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

from financial_intelligence.utils.config import CONFIGS_DIR, DATA_RAW_DIR, SEC_USER_AGENT

try:
    import yaml
except ImportError:  # pragma: no cover
    print("PyYAML manquant. `pip install -r requirements.txt`.", file=sys.stderr)
    raise

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
REQUEST_DELAY_SECONDS = 0.15  # SEC fair use policy : max 10 req/s, on reste large en dessous


def load_universe(path: Path = CONFIGS_DIR / "company_universe.yaml") -> dict[str, list[str]]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return {sector: data["tickers"] for sector, data in raw["sectors"].items()}


def fetch_ticker_to_cik_map() -> dict[str, int]:
    """Résout ticker -> CIK via le fichier officiel publié par la SEC."""
    resp = requests.get(TICKERS_URL, headers={"User-Agent": SEC_USER_AGENT}, timeout=30)
    resp.raise_for_status()
    raw = resp.json()
    return {entry["ticker"].upper(): entry["cik_str"] for entry in raw.values()}


def fetch_company_facts(cik: int) -> dict:
    url = COMPANY_FACTS_URL.format(cik=cik)
    resp = requests.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def run(universe_path: Path = CONFIGS_DIR / "company_universe.yaml") -> dict[str, list[str]]:
    """Télécharge les Company Facts pour chaque ticker de l'univers. Retourne un
    résumé {ok: [...], failed: [...]} basé sur des appels réseau réels."""
    sectors = load_universe(universe_path)
    all_tickers = sorted({t for tickers in sectors.values() for t in tickers})

    out_dir = DATA_RAW_DIR / "sec_edgar"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Résolution CIK pour {len(all_tickers)} tickers via {TICKERS_URL} ...")
    ticker_to_cik = fetch_ticker_to_cik_map()

    ok: list[str] = []
    failed: list[str] = []

    for ticker in all_tickers:
        cik = ticker_to_cik.get(ticker)
        if cik is None:
            print(f"  [SKIP] {ticker} : CIK introuvable dans {TICKERS_URL}")
            failed.append(ticker)
            continue
        try:
            facts = fetch_company_facts(cik)
        except requests.HTTPError as exc:
            print(f"  [FAIL] {ticker} (CIK {cik}) : {exc}")
            failed.append(ticker)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        out_path = out_dir / f"{ticker}.json"
        out_path.write_text(json.dumps(facts), encoding="utf-8")
        n_facts = sum(len(v) for v in facts.get("facts", {}).get("us-gaap", {}).values())
        print(f"  [OK]   {ticker} (CIK {cik}) -> {out_path.name} ({n_facts} points us-gaap)")
        ok.append(ticker)
        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\nTerminé : {len(ok)} OK, {len(failed)} échec(s) sur {len(all_tickers)}.")
    if failed:
        print(f"Échecs : {failed}")
    return {"ok": ok, "failed": failed}


if __name__ == "__main__":
    run()
