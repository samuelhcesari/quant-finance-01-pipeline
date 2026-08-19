"""Fixtures pytest pour une base PostgreSQL éphémère `financial_intelligence_test`
(jamais la base de développement). Schéma reconstruit une fois par session via
schema_runner. Chaque test tourne dans sa propre transaction, annulée
(ROLLBACK) à la fin.
"""

from __future__ import annotations

import psycopg
import pytest

from financial_intelligence.utils.config import DB_HOST, DB_PASSWORD, DB_PORT, DB_USER
from financial_intelligence.utils.schema_runner import apply_schema

TEST_DB_NAME = "financial_intelligence_test"


def _admin_connect() -> psycopg.Connection:
    conn = psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname="postgres", user=DB_USER, password=DB_PASSWORD,
        autocommit=True,
    )
    return conn


@pytest.fixture(scope="session")
def test_database() -> str:
    admin = _admin_connect()
    try:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {TEST_DB_NAME}")
    finally:
        admin.close()

    conn = psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=TEST_DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    try:
        apply_schema(conn, quiet=True)
    finally:
        conn.close()

    yield TEST_DB_NAME

    admin = _admin_connect()
    try:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")
    finally:
        admin.close()


@pytest.fixture()
def db_conn(test_database: str):
    conn = psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=test_database, user=DB_USER, password=DB_PASSWORD
    )
    try:
        yield conn
    finally:
        conn.rollback()  # annule tout ce que le test a inséré, isolation garantie
        conn.close()
