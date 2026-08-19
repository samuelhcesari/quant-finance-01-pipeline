"""Charge un échantillon restreint et entièrement traçable de transactions M&A
réelles (docs/00_project_charter.md, section 6 : "Aucune base de deals M&A
propriétaire... À défaut, construction d'un jeu de transactions à partir
d'annonces publiques... échantillon volontairement restreint et entièrement
traçable"). Chaque transaction ci-dessous a été vérifiée directement sur la
source SEC primaire citée en `source_url` (récupérée via curl avec le
User-Agent SEC requis, pas via un résumé secondaire) avant d'être saisie ici.

Financials des cibles (transaction_financials) : réutilisent le même fetcher/
normalizer SEC EDGAR que les 43 entreprises de l'univers principal (mêmes
tags US-GAAP, même logique de sélection de période) — voir
data/raw/sec_edgar_ma_targets/*.json pour le JSON brut téléchargé pour ces
5 cibles. `target_revenue_ttm`/`target_ebitda_ttm` utilisent le dernier
exercice ANNUEL COMPLET clôturé avant l'annonce (pas un vrai TTM glissant,
qui exigerait des données trimestrielles non chargées à ce stade) —
approximation documentée, pas une donnée inventée.

Usage : python -m financial_intelligence.data.load_ma_transactions
"""

from __future__ import annotations

import psycopg

from financial_intelligence.utils.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

# Cibles publiques ou privées impliquées, avec leur secteur d'affectation
# (mêmes 3 secteurs que l'univers principal, cf. configs/company_universe.yaml).
TARGET_COMPANIES = [
    {"ticker": "SGEN", "cik": "1060736", "name": "Seagen Inc.", "sector": "pharma", "is_public": True},
    {"ticker": "HZNP", "cik": "1492426", "name": "Horizon Therapeutics Public Ltd Co", "sector": "pharma", "is_public": True},
    {"ticker": "SPLK", "cik": "1353283", "name": "Splunk Inc.", "sector": "tech", "is_public": True},
    {"ticker": "HCP", "cik": "1720671", "name": "HashiCorp, Inc.", "sector": "tech", "is_public": True},
    {"ticker": None, "cik": None, "name": "Lhoist North America, Inc.", "sector": "construction", "is_public": False},
]

# Chaque transaction cite sa source SEC primaire vérifiée (curl + User-Agent
# SEC, pas une recherche web secondaire). Voir commentaire par transaction.
TRANSACTIONS = [
    {
        # Pfizer Inc. (NYSE: PFE) acquiert Seagen Inc. (Nasdaq: SGEN).
        # Source : communiqué conjoint, Exhibit 99.1 du 8-K, 13 mars 2023.
        "acquirer_ticker": "PFE",
        "target_ticker": "SGEN",
        "announce_date": "2023-03-13",
        "status": "announced",
        "payment_type": "cash",
        "offer_price_per_share": 229.00,
        "deal_value": 43_000_000_000,  # "total enterprise value of approximately $43 billion" (source)
        "unaffected_price": None,
        "unaffected_price_date": None,
        "source_type": "8-K",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1060736/000119312523068474/d467472dex991.htm",
        "financials": {
            # Dernier exercice annuel complet avant l'annonce : FY2022 (clôture 2022-12-31).
            "target_revenue_ttm": 1_962_412_000,
            "target_ebitda_ttm": -566_270_000,  # Seagen non rentable en FY2022 (réel, pas une erreur)
            "target_net_debt": None,  # tags de dette US-GAAP standard absents du filing (convertible notes taguées différemment)
            "ev_at_offer": 43_000_000_000,
            "ev_ebitda_multiple": None,  # non calculable : EBITDA cible négatif
            "notes": "EBITDA FY2022 négatif -> multiple EV/EBITDA non défini économiquement, volontairement NULL.",
        },
    },
    {
        # Amgen Inc. (Nasdaq: AMGN) acquiert Horizon Therapeutics plc (Nasdaq: HZNP).
        # Source : Rule 2.7 Announcement (Irish Takeover Rules), Exhibit 99.1 du 8-K, 12 décembre 2022.
        "acquirer_ticker": "AMGN",
        "target_ticker": "HZNP",
        "announce_date": "2022-12-12",
        "status": "announced",
        "payment_type": "cash",
        "offer_price_per_share": 116.50,
        "deal_value": 27_800_000_000,  # valeur des capitaux propres ("fully diluted basis", source)
        # "last closing price... prior to the Company's issuance of an announcement of a possible
        # offer" (source) -> fenêtre anti-fuite la plus propre disponible dans le document.
        "unaffected_price": 78.76,
        "unaffected_price_date": "2022-11-29",
        "source_type": "8-K",
        "source_url": "https://www.sec.gov/Archives/edgar/data/318154/000119312522302256/d346985dex991.htm",
        "financials": {
            # Dernier exercice annuel complet avant l'annonce : FY2021 (clôture 2021-12-31),
            # FY2022 exclu car sa clôture (2021-12-31... 2022-12-31) tombe après l'annonce.
            "target_revenue_ttm": 3_226_410_000,
            "target_ebitda_ttm": 896_878_000,
            "target_net_debt": 16_000_000 + 2_555_233_000 - 1_580_317_000,  # st_debt + lt_debt - cash, FY2021
            "ev_at_offer": 28_300_000_000,  # "implies an enterprise value of approximately $28.3 billion" (source)
            "ev_ebitda_multiple": 28_300_000_000 / 896_878_000,
            "notes": "target_revenue_ttm/target_ebitda_ttm = FY2021 (dernier exercice complet avant l'annonce), pas un TTM glissant exact.",
        },
    },
    {
        # Cisco Systems, Inc. (Nasdaq: CSCO) acquiert Splunk Inc. (Nasdaq: SPLK).
        # Source : Form 8-K, Item 1.01, accord daté du 20 septembre 2023, filed 21 septembre 2023.
        "acquirer_ticker": "CSCO",
        "target_ticker": "SPLK",
        "announce_date": "2023-09-20",
        "status": "announced",
        "payment_type": "cash",
        "offer_price_per_share": 157.00,
        "deal_value": 28_000_000_000,  # "aggregate equity value... approximately $28 billion" (source)
        "unaffected_price": None,
        "unaffected_price_date": None,
        "source_type": "8-K",
        "source_url": "https://www.sec.gov/Archives/edgar/data/858877/000119312523239165/d464532d8k.htm",
        "financials": None,  # Splunk : aucune période annuelle extraite par le normalizer standard (0 lignes) -> non chargé, pas inventé.
    },
    {
        # IBM (NYSE: IBM) acquiert HashiCorp, Inc. (Nasdaq: HCP).
        # Source : Exhibit 99.1 (communiqué de résultats Q1 2024 mentionnant l'acquisition), 8-K, 24 avril 2024.
        "acquirer_ticker": "IBM",
        "target_ticker": "HCP",
        "announce_date": "2024-04-24",
        "status": "announced",
        "payment_type": "cash",
        "offer_price_per_share": 35.00,
        "deal_value": 6_400_000_000,  # "representing an enterprise value of $6.4 billion" (source)
        "unaffected_price": None,
        "unaffected_price_date": None,
        "source_type": "8-K",
        "source_url": "https://www.sec.gov/Archives/edgar/data/51143/000005114324000018/ibm-20240424xex991.htm",
        "financials": {
            # Dernier exercice annuel complet avant l'annonce : FY clôturé 2024-01-31 (calendrier fiscal HashiCorp).
            "target_revenue_ttm": 583_137_000,
            "target_ebitda_ttm": -244_772_000,  # HashiCorp non rentable (réel, SaaS en forte croissance)
            "target_net_debt": None,  # tags de dette US-GAAP standard absents du filing
            "ev_at_offer": 6_400_000_000,
            "ev_ebitda_multiple": None,  # non calculable : EBITDA cible négatif
            "notes": "EBITDA négatif -> multiple EV/EBITDA volontairement NULL.",
        },
    },
    {
        # Martin Marietta Materials, Inc. (NYSE: MLM) acquiert Lhoist North America, Inc.
        # (filiale du groupe belge Lhoist, cible PRIVÉE — is_public=FALSE).
        # Source : Form 8-K, Item 1.01, Securities Sale Agreement datée du 27 juin 2026.
        "acquirer_ticker": "MLM",
        "target_ticker": None,  # cible privée, identifiée par nom dans TARGET_COMPANIES
        "target_name": "Lhoist North America, Inc.",
        "announce_date": "2026-06-27",
        "status": "announced",
        "payment_type": "mixed",  # $7.0bn cash + $6.5bn actions Martin Marietta (source)
        "offer_price_per_share": None,  # cible privée : pas de prix par action
        "deal_value": 13_500_000_000,
        "unaffected_price": None,
        "unaffected_price_date": None,
        "source_type": "8-K",
        "source_url": "https://www.sec.gov/Archives/edgar/data/916076/000095015726000770/form8-k.htm",
        "financials": {
            "target_revenue_ttm": None,  # cible privée, états financiers de LNA non extraits (hors périmètre de ce chargement)
            "target_ebitda_ttm": None,
            "target_net_debt": None,
            "ev_at_offer": 13_500_000_000,  # valeur totale de la transaction annoncée, cible privée
            "ev_ebitda_multiple": None,
            "notes": "Cible privée (LNA, filiale de Lhoist Group) — pas d'états financiers extraits séparément dans ce chargement.",
        },
    },
]


def _connect() -> psycopg.Connection:
    return psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )


def _get_sector_id(cur, sector_code: str) -> int:
    sector_labels = {
        "pharma": "Pharmaceutique / Biotech",
        "tech": "Technologie",
        "construction": "Construction / Matériaux / E&C",
    }
    cur.execute("SELECT sector_id FROM sectors WHERE name = %s", (sector_labels[sector_code],))
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"Secteur introuvable : {sector_code}")
    return row[0]


def upsert_target_companies(conn: psycopg.Connection) -> dict[str, int]:
    ids: dict[str, int] = {}
    with conn.cursor() as cur:
        for tc in TARGET_COMPANIES:
            sector_id = _get_sector_id(cur, tc["sector"])
            key = tc["ticker"] or tc["name"]
            if tc["ticker"]:
                cur.execute(
                    """
                    INSERT INTO companies (cik, ticker, name, sector_id, country, is_public)
                    VALUES (%s, %s, %s, %s, 'US', %s)
                    ON CONFLICT (ticker) DO UPDATE SET
                        cik = EXCLUDED.cik, name = EXCLUDED.name, sector_id = EXCLUDED.sector_id,
                        updated_at = now()
                    RETURNING company_id
                    """,
                    (tc["cik"], tc["ticker"], tc["name"], sector_id, tc["is_public"]),
                )
            else:
                # Cible privée sans ticker/CIK : pas de contrainte UNIQUE naturelle
                # (cf. docs/01_data_model.md 3.5) -> check-then-insert manuel.
                cur.execute(
                    "SELECT company_id FROM companies WHERE name = %s AND ticker IS NULL", (tc["name"],)
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        "UPDATE companies SET sector_id = %s, updated_at = now() WHERE company_id = %s",
                        (sector_id, existing[0]),
                    )
                    ids[key] = existing[0]
                    continue
                cur.execute(
                    """
                    INSERT INTO companies (cik, ticker, name, sector_id, country, is_public)
                    VALUES (NULL, NULL, %s, %s, 'US', FALSE)
                    RETURNING company_id
                    """,
                    (tc["name"], sector_id),
                )
            ids[key] = cur.fetchone()[0]
    conn.commit()
    return ids


def fetch_company_ids_by_ticker(conn: psycopg.Connection, tickers: list[str]) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT ticker, company_id FROM companies WHERE ticker = ANY(%s)", (tickers,))
        return dict(cur.fetchall())


def run() -> dict[str, int]:
    print(f"Connexion à {DB_HOST}:{DB_PORT}/{DB_NAME} ...")
    conn = _connect()
    try:
        target_ids = upsert_target_companies(conn)
        print(f"  cibles M&A upsertées : {len(target_ids)}")

        acquirer_tickers = sorted({t["acquirer_ticker"] for t in TRANSACTIONS})
        acquirer_ids = fetch_company_ids_by_ticker(conn, acquirer_tickers)
        missing = [t for t in acquirer_tickers if t not in acquirer_ids]
        if missing:
            raise RuntimeError(f"Acquéreurs absents de `companies` (univers principal) : {missing}")

        n_tx = n_fin = 0
        with conn.cursor() as cur:
            for tx in TRANSACTIONS:
                acquirer_id = acquirer_ids[tx["acquirer_ticker"]]
                target_key = tx["target_ticker"] or tx["target_name"]
                target_id = target_ids[target_key]

                cur.execute(
                    """
                    INSERT INTO transactions
                        (acquirer_company_id, target_company_id, announce_date, status, payment_type,
                         offer_price_per_share, deal_value, unaffected_price, unaffected_price_date,
                         source_type, source_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (acquirer_company_id, target_company_id, announce_date) DO UPDATE SET
                        status = EXCLUDED.status, payment_type = EXCLUDED.payment_type,
                        offer_price_per_share = EXCLUDED.offer_price_per_share,
                        deal_value = EXCLUDED.deal_value, unaffected_price = EXCLUDED.unaffected_price,
                        unaffected_price_date = EXCLUDED.unaffected_price_date,
                        source_type = EXCLUDED.source_type, source_url = EXCLUDED.source_url
                    RETURNING transaction_id
                    """,
                    (
                        acquirer_id, target_id, tx["announce_date"], tx["status"], tx["payment_type"],
                        tx["offer_price_per_share"], tx["deal_value"], tx["unaffected_price"],
                        tx["unaffected_price_date"], tx["source_type"], tx["source_url"],
                    ),
                )
                transaction_id = cur.fetchone()[0]
                n_tx += 1

                fin = tx["financials"]
                if fin is not None:
                    cur.execute(
                        """
                        INSERT INTO transaction_financials
                            (transaction_id, target_revenue_ttm, target_ebitda_ttm, target_net_debt,
                             ev_at_offer, ev_ebitda_multiple, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (transaction_id) DO UPDATE SET
                            target_revenue_ttm = EXCLUDED.target_revenue_ttm,
                            target_ebitda_ttm = EXCLUDED.target_ebitda_ttm,
                            target_net_debt = EXCLUDED.target_net_debt,
                            ev_at_offer = EXCLUDED.ev_at_offer,
                            ev_ebitda_multiple = EXCLUDED.ev_ebitda_multiple,
                            notes = EXCLUDED.notes
                        """,
                        (
                            transaction_id, fin["target_revenue_ttm"], fin["target_ebitda_ttm"],
                            fin["target_net_debt"], fin["ev_at_offer"], fin["ev_ebitda_multiple"],
                            fin["notes"],
                        ),
                    )
                    n_fin += 1
        conn.commit()
        print(f"  transactions : {n_tx} lignes")
        print(f"  transaction_financials : {n_fin} lignes")
        print("\nChargement M&A terminé sans erreur.")
        return {"transactions": n_tx, "transaction_financials": n_fin}
    finally:
        conn.close()


if __name__ == "__main__":
    run()
