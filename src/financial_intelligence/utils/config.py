"""Chemins et configuration partagés par les fetchers/loaders. Pas de logique métier ici."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CONFIGS_DIR = PROJECT_ROOT / "configs"

# SEC EDGAR exige un User-Agent identifiant un contact réel (politique d'accès
# équitable) -> définir SEC_USER_AGENT dans .env (jamais commité) avec ta
# propre adresse ; ce défaut générique ne doit servir qu'en dernier recours.
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "financial-intelligence-deal-analytics contact@example.com",
)
FRED_API_KEY = os.environ.get("FRED_API_KEY")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))  # 5432 = docker-compose.yml (chemin officiel)
DB_NAME = os.environ.get("DB_NAME", "financial_intelligence")
DB_USER = os.environ.get("DB_USER", "fida")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "fida_dev_password")
