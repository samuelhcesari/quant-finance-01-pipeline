"""Normalise le JSON brut FRED (data/raw/fred/*.json) en un seul fichier
data/processed/macro_indicators.csv (series_code, obs_date, value).

FRED encode les observations manquantes avec la valeur littérale "." — ces
lignes sont ignorées plutôt qu'insérées comme 0.

Usage : python -m financial_intelligence.data.normalize_fred
"""

from __future__ import annotations

import csv
import json
import sys

from financial_intelligence.utils.config import DATA_PROCESSED_DIR, DATA_RAW_DIR

OUTPUT_COLUMNS = ["series_code", "obs_date", "value"]


def run() -> dict[str, int]:
    in_dir = DATA_RAW_DIR / "fred"
    out_dir = DATA_PROCESSED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "macro_indicators.csv"

    json_files = sorted(in_dir.glob("*.json"))
    if not json_files:
        print(f"Aucun fichier trouvé dans {in_dir}. Lancer fetch_fred d'abord.", file=sys.stderr)
        sys.exit(1)

    n_rows = 0
    n_missing = 0
    with open(out_path, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for path in json_files:
            series_code = path.stem
            data = json.loads(path.read_text(encoding="utf-8"))
            for obs in data.get("observations", []):
                if obs.get("value") == ".":
                    n_missing += 1
                    continue
                writer.writerow(
                    {"series_code": series_code, "obs_date": obs["date"], "value": obs["value"]}
                )
                n_rows += 1

    print(f"{len(json_files)} séries traitées -> {n_rows} observations dans {out_path} ({n_missing} valeurs manquantes ignorées)")
    return {"series": len(json_files), "rows": n_rows}


if __name__ == "__main__":
    run()
