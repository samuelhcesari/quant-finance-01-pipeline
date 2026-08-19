"""Normalise les CSV bruts Yahoo Finance (data/raw/yahoo/*.csv) en un seul
fichier data/processed/market_prices.csv (ticker, price_date, close_price,
volume).

shares_outstanding et market_cap restent NULL : yfinance ne fournit qu'un
nombre d'actions actuel (snapshot), pas un historique quotidien fiable.

Usage : python -m financial_intelligence.data.normalize_yahoo
"""

from __future__ import annotations

import csv
import sys

import pandas as pd

from financial_intelligence.utils.config import DATA_PROCESSED_DIR, DATA_RAW_DIR

OUTPUT_COLUMNS = ["ticker", "price_date", "close_price", "volume"]


def run() -> dict[str, int]:
    in_dir = DATA_RAW_DIR / "yahoo"
    out_dir = DATA_PROCESSED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "market_prices.csv"

    csv_files = sorted(in_dir.glob("*.csv"))
    if not csv_files:
        print(f"Aucun fichier trouvé dans {in_dir}. Lancer fetch_yahoo d'abord.", file=sys.stderr)
        sys.exit(1)

    n_rows = 0
    with open(out_path, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for path in csv_files:
            ticker = path.stem
            df = pd.read_csv(path)
            for _, r in df.iterrows():
                writer.writerow(
                    {
                        "ticker": ticker,
                        "price_date": str(r["Date"])[:10],
                        "close_price": r["Close"],
                        "volume": int(r["Volume"]) if pd.notna(r["Volume"]) else "",
                    }
                )
                n_rows += 1

    print(f"{len(csv_files)} tickers traités -> {n_rows} lignes de prix dans {out_path}")
    return {"tickers": len(csv_files), "rows": n_rows}


if __name__ == "__main__":
    run()
