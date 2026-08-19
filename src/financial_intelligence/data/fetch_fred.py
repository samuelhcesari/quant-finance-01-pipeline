"""Fetcher FRED — télécharge les séries macro brutes utilisées pour contextualiser
les cycles de deals.

Sauvegarde le JSON brut de l'API FRED tel quel, sans transformation.

Usage : python -m financial_intelligence.data.fetch_fred
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

from financial_intelligence.utils.config import DATA_RAW_DIR, FRED_API_KEY

FRED_SERIES_URL = "https://api.stlouisfed.org/fred/series/observations"
REQUEST_DELAY_SECONDS = 0.2

# Séries choisies pour contextualiser les cycles M&A/LBO : taux sans risque,
# spread de crédit high-yield (coût de la dette des deals à effet de levier),
# taux Fed Funds (cycle monétaire).
SERIES = {
    "DGS10": "10-Year Treasury Constant Maturity Rate",
    "BAMLH0A0HYM2": "ICE BofA US High Yield Index Option-Adjusted Spread",
    "FEDFUNDS": "Federal Funds Effective Rate",
}


def fetch_series(series_id: str) -> dict:
    if not FRED_API_KEY:
        print(
            "FRED_API_KEY manquante. Renseigner .env (voir .env.example).",
            file=sys.stderr,
        )
        sys.exit(1)
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
    }
    resp = requests.get(FRED_SERIES_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def run() -> dict[str, list[str]]:
    out_dir = DATA_RAW_DIR / "fred"
    out_dir.mkdir(parents=True, exist_ok=True)

    ok: list[str] = []
    failed: list[str] = []

    for series_id, label in SERIES.items():
        try:
            data = fetch_series(series_id)
        except requests.HTTPError as exc:
            print(f"  [FAIL] {series_id} ({label}) : {exc}")
            failed.append(series_id)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        out_path = out_dir / f"{series_id}.json"
        out_path.write_text(json.dumps(data), encoding="utf-8")
        n_obs = len(data.get("observations", []))
        print(f"  [OK]   {series_id} ({label}) -> {out_path.name} ({n_obs} observations)")
        ok.append(series_id)
        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\nTerminé : {len(ok)} OK, {len(failed)} échec(s) sur {len(SERIES)}.")
    return {"ok": ok, "failed": failed}


if __name__ == "__main__":
    run()
