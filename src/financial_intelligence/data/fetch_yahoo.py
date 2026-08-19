"""Fetcher Yahoo Finance — télécharge l'historique de prix/volume brut pour
l'univers d'entreprises via `yfinance` (docs/00_project_charter.md, section 6 :
source non officielle, fiabilité variable, jamais présentée comme référence
réglementaire).

Sauvegarde un CSV brut par ticker (OHLCV + Adj Close), sans transformation.

Usage : python -m financial_intelligence.data.fetch_yahoo
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import yfinance as yf

from financial_intelligence.utils.config import CONFIGS_DIR, DATA_RAW_DIR
from financial_intelligence.data.fetch_sec_edgar import load_universe

REQUEST_DELAY_SECONDS = 0.5
PERIOD = "5y"


def run(universe_path: Path = CONFIGS_DIR / "company_universe.yaml") -> dict[str, list[str]]:
    sectors = load_universe(universe_path)
    all_tickers = sorted({t for tickers in sectors.values() for t in tickers})

    out_dir = DATA_RAW_DIR / "yahoo"
    out_dir.mkdir(parents=True, exist_ok=True)

    ok: list[str] = []
    failed: list[str] = []

    for ticker in all_tickers:
        try:
            hist = yf.Ticker(ticker).history(period=PERIOD, auto_adjust=False)
        except Exception as exc:  # yfinance lève des exceptions variées selon la panne réseau
            print(f"  [FAIL] {ticker} : {exc}")
            failed.append(ticker)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        if hist.empty:
            print(f"  [FAIL] {ticker} : réponse vide")
            failed.append(ticker)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        out_path = out_dir / f"{ticker}.csv"
        hist.to_csv(out_path)
        print(f"  [OK]   {ticker} -> {out_path.name} ({len(hist)} lignes, {hist.index.min().date()} -> {hist.index.max().date()})")
        ok.append(ticker)
        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\nTerminé : {len(ok)} OK, {len(failed)} échec(s) sur {len(all_tickers)}.")
    if failed:
        print(f"Échecs : {failed}")
    return {"ok": ok, "failed": failed}


if __name__ == "__main__":
    run()
