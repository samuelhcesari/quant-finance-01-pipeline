"""Applique les scripts SQL versionnés numérotés (sql/schema/, sql/views/,
sql/optimization/) dans un ordre explicite, pas un glob par dossier : les vues
008-010 dépendent de mv_company_financial_profile (sql/optimization/001), donc
l'optimisation doit s'appliquer entre la vue 007 et la vue 008.

Liste dupliquée dans le Makefile pour le chemin Docker (`make schema`).

Usage : python -m financial_intelligence.utils.schema_runner [--db-name NAME]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

from financial_intelligence.utils.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER, PROJECT_ROOT

SQL_ROOT = PROJECT_ROOT / "sql"

ORDERED_SQL_FILES = [
    "schema/001_init.sql",
    "schema/002_transactions_unique.sql",
    "views/001_v_growth.sql",
    "views/002_v_margins.sql",
    "views/003_v_returns.sql",
    "views/004_v_leverage.sql",
    "views/005_v_cash_flow.sql",
    "views/006_v_valuation.sql",
    "views/007_v_company_financial_profile.sql",
    "optimization/001_mv_company_financial_profile.sql",
    "views/008_v_sector_rankings.sql",
    "views/009_v_trailing_trends.sql",
    "views/010_v_screening_base.sql",
    "views/011_v_transaction_premiums.sql",
    "views/012_v_transaction_multiples.sql",
    "views/013_v_data_quality_flags.sql",
]


def apply_schema(conn: psycopg.Connection, sql_root: Path = SQL_ROOT, quiet: bool = False) -> None:
    with conn.cursor() as cur:
        for rel_path in ORDERED_SQL_FILES:
            path = sql_root / rel_path
            sql = path.read_text(encoding="utf-8")
            if not quiet:
                print(f"Applying {rel_path}")
            cur.execute(sql)
    conn.commit()


def run(db_name: str | None = None) -> None:
    conn = psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=db_name or DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    try:
        apply_schema(conn)
        print("\nSchéma appliqué sans erreur.")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-name", default=None, help=f"Base cible (défaut : {DB_NAME})")
    args = parser.parse_args()
    try:
        run(args.db_name)
    except psycopg.Error as exc:
        print(f"Échec de l'application du schéma : {exc}", file=sys.stderr)
        sys.exit(1)
