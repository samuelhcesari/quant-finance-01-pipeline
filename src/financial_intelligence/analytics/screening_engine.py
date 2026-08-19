"""Moteur de screening PE générique : lit les règles de chaque profil dans
configs/screening/*.yaml, les évalue contre v_screening_base, journalise dans
screening_results (config_hash + run_date).

Règle = {metric, operator, threshold, allow_null}. Si metric est NULL :
allow_null=true -> règle satisfaite ; allow_null=false -> règle non satisfaite.
Sinon : comparaison metric OPERATOR threshold.

passed = (fraction de règles satisfaites) >= min_score du profil.

Usage : python -m financial_intelligence.analytics.screening_engine
"""

from __future__ import annotations

import hashlib
import operator as op
import sys
from pathlib import Path

import psycopg
import yaml

from financial_intelligence.utils.config import (
    CONFIGS_DIR,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
)

OPERATORS = {
    ">=": op.ge,
    "<=": op.le,
    ">": op.gt,
    "<": op.lt,
    "==": op.eq,
    "!=": op.ne,
}


def _connect() -> psycopg.Connection:
    return psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )


def load_profiles(screening_dir: Path = CONFIGS_DIR / "screening") -> list[dict]:
    profiles = []
    for path in sorted(screening_dir.glob("*.yaml")):
        raw_text = path.read_text(encoding="utf-8")
        config = yaml.safe_load(raw_text)
        config["config_path"] = path.relative_to(CONFIGS_DIR.parent).as_posix()
        config["config_hash"] = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:16]
        profiles.append(config)
    return profiles


def evaluate_rule(rule: dict, row: dict) -> bool:
    value = row.get(rule["metric"])
    if value is None:
        return bool(rule.get("allow_null", False))
    return OPERATORS[rule["operator"]](float(value), float(rule["threshold"]))


def evaluate_profile(profile: dict, row: dict) -> tuple[bool, float]:
    rules = profile["rules"]
    satisfied = [evaluate_rule(r, row) for r in rules]
    score = sum(satisfied) / len(satisfied) if satisfied else 0.0
    passed = score >= profile.get("min_score", 1.0)
    return passed, score


def upsert_profile(conn: psycopg.Connection, profile: dict) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO screening_profiles (code, name, description, config_path, config_version)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name, description = EXCLUDED.description,
                config_path = EXCLUDED.config_path, config_version = EXCLUDED.config_version
            RETURNING screening_profile_id
            """,
            (
                profile["code"],
                profile["name"],
                profile.get("description", ""),
                profile["config_path"],
                profile["version"],
            ),
        )
        return cur.fetchone()[0]


def fetch_screening_base(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM v_screening_base")
        columns = [c.name for c in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def run() -> dict[str, int]:
    profiles = load_profiles()
    if not profiles:
        print("Aucun profil trouvé dans configs/screening/.", file=sys.stderr)
        sys.exit(1)

    print(f"Connexion à {DB_HOST}:{DB_PORT}/{DB_NAME} ...")
    conn = _connect()
    try:
        rows = fetch_screening_base(conn)
        print(f"{len(rows)} lignes (entreprise x exercice) à évaluer depuis v_screening_base.")

        totals: dict[str, int] = {}
        with conn.cursor() as cur:
            for profile in profiles:
                profile_id = upsert_profile(conn, profile)
                n_passed = 0
                for row in rows:
                    passed, score = evaluate_profile(profile, row)
                    if passed:
                        n_passed += 1
                    cur.execute(
                        """
                        INSERT INTO screening_results
                            (screening_profile_id, company_id, fiscal_period_id, passed, score, config_hash)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            profile_id,
                            row["company_id"],
                            row["fiscal_period_id"],
                            passed,
                            score,
                            profile["config_hash"],
                        ),
                    )
                conn.commit()
                totals[profile["code"]] = n_passed
                print(f"  {profile['code']:12s} ({profile['name']}) : {n_passed}/{len(rows)} lignes passent")

        print("\nScreening terminé sans erreur.")
        return totals
    finally:
        conn.close()


if __name__ == "__main__":
    run()
