# Project Charter — Financial Intelligence & Deal Analytics Platform

**Repository:** `financial-intelligence-deal-analytics`
**Phase:** 1 / 3 — SQL / PostgreSQL
**Status:** Planning complete — implementation not yet started

> Ce document constitue le cadrage obligatoire avant toute implémentation, conformément au cahier des charges. Aucun code métier n'est écrit tant que ce document n'est pas validé.

---

## 1. Executive Summary

Ce projet construit une plateforme de données financières sous PostgreSQL permettant d'analyser des entreprises cotées et privées à travers quatre lentilles professionnelles : **corporate finance**, **valorisation**, **fusions-acquisitions**, et **private equity screening**. L'objectif n'est pas de stocker des données, mais de démontrer une maîtrise du SQL analytique appliqué à des problématiques réelles de deal-sourcing et de recherche financière : croissance, rentabilité, effet de levier, génération de cash, multiples de valorisation, et dynamique des transactions M&A/LBO dans le temps.

Le produit final est une base de données normalisée, un ensemble de vues et requêtes analytiques avancées (window functions, CTE récursives, agrégation conditionnelle), un moteur de screening PE paramétrable, et une couche Python fine pour l'orchestration, le chargement des données et la restitution (rapports, graphiques).

## 2. Research / Business Question

Question centrale : *Peut-on construire, à partir de données financières publiques, un système d'aide à la décision capable d'identifier et de classer des entreprises selon des profils d'investissement standards (croissance, valeur, qualité, distressed), tout en rendant explicite la mécanique financière (croissance → marge → levier → multiple) qui sous-tend chaque classement ?*

Sous-questions opérationnelles :
- Quelles entreprises/secteurs présentent la meilleure combinaison croissance/marge/ROIC ?
- Comment les multiples de valorisation (EV/EBITDA, EV/Revenue) varient-ils par secteur et dans le temps, et existe-t-il une relation observable avec la croissance et la marge (proxy d'un "growth-adjusted multiple") ?
- Quelle est la dynamique des transactions M&A (volume, primes, multiples payés) par secteur et par cycle ?
- Quel profil d'entreprise (croissance, marge, levier) est statistiquement associé à un statut de cible M&A/LBO dans l'échantillon ?

## 3. Learning Objectives

- Concevoir un schéma relationnel normalisé (3NF raisonnable) représentant fidèlement la structure d'un état financier et d'une transaction M&A.
- Maîtriser le SQL analytique avancé : CTE imbriquées, window functions (LAG/LEAD/RANK/ROW_NUMBER), agrégation conditionnelle, vues matérialisées.
- Traduire des concepts de corporate finance (marges, ROIC, leverage, FCF, multiples) en requêtes SQL correctes et vérifiables.
- Construire un moteur de règles (screening) paramétrable directement en SQL.
- Comprendre et démontrer l'optimisation de requêtes (index, EXPLAIN ANALYZE, plans d'exécution).
- Documenter des choix de modélisation de données comme le ferait une équipe data/quant en environnement professionnel.

## 4. Technical Requirements

| Composant | Choix | Justification |
|---|---|---|
| SGBD | PostgreSQL 16 | Support complet des window functions, CTE récursives, vues matérialisées, JSONB pour les métadonnées peu structurées |
| Langage d'orchestration | Python 3.11+ | Chargement des données, tests, génération de rapports — jamais de logique métier dupliquée hors SQL |
| Accès DB en Python | `psycopg` (v3) + `SQLAlchemy Core` (pas d'ORM lourd — le SQL doit rester lisible et auditable) | Garde le SQL explicite plutôt que masqué par un ORM |
| Migrations | `sqlite`→ non ; scripts SQL versionnés numérotés (`001_`, `002_`...) appliqués via un petit runner Python | Reproductibilité, pas de dépendance à un outil propriétaire |
| Tests | `pytest` + tests SQL exécutés contre une base PostgreSQL éphémère (Docker) | Garantit que les requêtes sont réellement validées, pas seulement lues |
| Environnement | Docker Compose (postgres + service Python) | `git clone && docker compose up` doit suffire pour reproduire l'environnement |
| Qualité de code | `ruff`, `black`, `mypy` (type hints stricts) | Standard professionnel |

## 5. Mathematical / Financial Requirements

Le projet ne nécessite pas de mathématiques avancées mais une **exactitude financière stricte**. Formules qui doivent être implémentées et vérifiées par des tests :

- **Croissance** : `growth_t = (X_t / X_{t-1}) - 1` pour Revenue, EBITDA, EPS, FCF (attention aux dénominateurs négatifs — cas à traiter explicitement, pas ignoré).
- **Marges** : `EBITDA margin = EBITDA / Revenue`, idem EBIT margin, Net margin, Gross margin.
- **Rentabilité du capital** : `ROE = Net Income / Avg Shareholders Equity`, `ROA = Net Income / Avg Total Assets`, `ROIC = NOPAT / Invested Capital` avec `NOPAT = EBIT × (1 - tax rate effectif)` et `Invested Capital = Total Debt + Equity - Cash`.
- **Levier** : `Net Debt/EBITDA`, `Debt/Equity`, `Interest Coverage = EBIT / Interest Expense`.
- **Cash flow** : `FCF = CFO - CapEx`, `FCF margin = FCF / Revenue`, `FCF conversion = FCF / EBITDA`.
- **Valorisation** : `EV = Market Cap + Total Debt - Cash & Equivalents`, puis `EV/EBITDA`, `EV/Revenue`, `EV/EBIT`, `P/E`, `P/B`, `FCF Yield = FCF / Market Cap`.
- **Primes de transaction M&A** : `Premium = (Offer Price / Unaffected Price) - 1`, avec `Unaffected Price` défini comme le cours N jours avant l'annonce (fenêtre à documenter, ex. -20 jours pour éviter les fuites d'information).

Chaque formule est isolée dans une vue SQL nommée explicitement (ex. `v_profitability_ratios`) et testée avec des valeurs de référence calculées à la main.

## 6. Data Requirements

Sources publiques retenues, sans clé API payante :

| Source | Contenu | Fréquence | Accès |
|---|---|---|---|
| **SEC EDGAR** (`data.sec.gov`, Company Facts API / XBRL frames) | États financiers US GAAP normalisés (10-K, 10-Q) pour sociétés cotées US | Trimestrielle/Annuelle | Gratuit, sans clé, rate-limited (déclarer un User-Agent) |
| **FRED** (Federal Reserve Economic Data) | Taux d'intérêt, spreads de crédit, indicateurs macro utilisés pour contextualiser les cycles de deals | Journalière/Mensuelle | Gratuit, clé API gratuite |
| **Yahoo Finance** (via `yfinance`) | Prix de marché, capitalisation, pour le calcul des multiples et de l'EV | Journalière | Gratuit, non officiel — limites documentées (fiabilité variable, à ne jamais présenter comme source de référence réglementaire) |
| **Kenneth French Data Library** | Données sectorielles/factorielles en support pour Projet 2, référencées ici pour cohérence de secteur | Mensuelle | Gratuit |
| Transactions M&A | **Aucune base de deals M&A propriétaire (Refinitiv, PitchBook) n'est accessible gratuitement.** À défaut, construction d'un jeu de transactions à partir d'annonces publiques (communiqués de presse, 8-K SEC pour les acquisitions matérielles) sur un échantillon volontairement restreint et entièrement traçable (source + URL par transaction). Ceci sera documenté explicitement comme une limitation du dataset dans le README. | — | Manuel, documenté ligne par ligne |

Pour chaque source, un fichier `docs/data_sources.md` documentera : URL exacte, date d'accès, période couverte, unités, transformations appliquées, biais connus (ex. survivorship bias sur les tickers actuellement listés).

**Environnement de développement** : les scripts de collecte (`src/financial_intelligence/data/fetch_*.py`) nécessitent un accès réseau sortant vers `data.sec.gov`, `api.stlouisfed.org` et Yahoo Finance. Exécutés avec succès en conditions réelles (cf. `PORTFOLIO_PROGRESS.md` et `docs/data_sources.md` pour les résultats datés). Cohérent avec l'exigence de reproductibilité : `git clone → install deps → download data → run pipeline`.

## 7. Database / Software Architecture

```
Raw sources (SEC EDGAR, FRED, Yahoo Finance)
        │
        ▼
  Python fetchers (src/financial_intelligence/data/)
        │  → data/raw/ (JSON/CSV bruts, jamais modifiés)
        ▼
  Python normalizers (parsing XBRL → lignes tabulaires)
        │  → data/processed/ (CSV prêts à charger)
        ▼
  COPY / loaders → PostgreSQL (sql/schema/, tables normalisées)
        │
        ▼
  Vues analytiques SQL (sql/views/) : ratios, rankings, screening
        │
        ▼
  Requêtes de restitution (sql/queries/) + notebooks Python (lecture seule, jamais d'écriture de logique métier)
```

Principe directeur : **toute la logique financière vit en SQL** (vues), Python ne fait que l'ingestion, l'orchestration et la restitution graphique.

## 8. Folder Structure

```
financial-intelligence-deal-analytics/
├── README.md
├── LICENSE
├── .gitignore
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── src/financial_intelligence/
│   ├── data/          # fetchers + normalizers
│   ├── models/        # dataclasses représentant les entités (Company, Transaction...)
│   ├── analytics/      # orchestration des requêtes analytiques depuis Python
│   ├── portfolio/       # (stub — non prioritaire pour ce projet)
│   ├── risk/            # (stub — non prioritaire pour ce projet)
│   └── utils/           # connexion DB, logging, config
├── sql/
│   ├── schema/           # 001_..., 002_... DDL versionné
│   ├── views/            # ratios, rankings, screening profiles
│   ├── queries/          # requêtes de restitution documentées
│   └── optimization/     # EXPLAIN ANALYZE avant/après, index
├── tests/                 # pytest, y compris tests SQL contre DB éphémère
├── notebooks/             # exploration, jamais de logique définitive
├── configs/               # profils de screening (YAML), connexion DB
├── data/{raw,processed}/  # gitignored sauf échantillons de démo
├── results/                # exports de screening, rankings
├── reports/                 # rapport de recherche (Markdown/PDF)
└── docs/                    # ce document + data_sources.md + design decisions
```

## 9. Development Roadmap

1. **Schéma & normalisation** — DDL complet, contraintes, index de base.
2. **Fetchers de données** — SEC EDGAR (états financiers), FRED (contexte macro), Yahoo Finance (marché). Échantillon initial : 30–50 entreprises US, 2–3 secteurs contrastés.
3. **Chargement** — scripts idempotents (`INSERT ... ON CONFLICT DO UPDATE`), logs de chargement.
4. **Vues analytiques** — croissance, marges, leverage, cash flow, valorisation (section 5).
5. **SQL avancé** — window functions pour rankings et évolutions temporelles, CTE pour le moteur de screening.
6. **Moteur de screening** — 4 profils paramétrables (PE Growth, PE Value, Quality, Distressed).
7. **Transactions M&A** — table + vues de primes et multiples payés.
8. **Optimisation** — EXPLAIN ANALYZE, index ciblés, mesure avant/après.
9. **Tests** — unitaires (Python) + SQL (valeurs de référence).
10. **Documentation** — README, rapport de recherche, `data_sources.md`.

## 10. Testing Strategy

- **Tests unitaires Python** : parsing des données brutes (cas limites — valeurs manquantes, dénominateurs nuls/négatifs).
- **Tests SQL** : chaque vue de ratio testée contre un mini jeu de données synthétique où le résultat attendu est calculé à la main (ex. une entreprise fictive avec Revenue, EBITDA, Debt connus → vérifier que `v_leverage_ratios` renvoie exactement la valeur attendue).
- **Tests d'intégrité référentielle** : toute foreign key testée pour orphelins après chargement.
- **Tests du moteur de screening** : vérifier qu'un enregistrement synthétique conçu pour passer/échouer un profil donné produit bien le résultat attendu.
- Base de test : PostgreSQL éphémère via Docker, recréée à chaque run (`pytest` fixture avec rollback ou schema temporaire).

## 11. Validation Strategy

- Comparaison manuelle d'un échantillon de ratios calculés en SQL avec un calcul indépendant en Python/pandas sur les mêmes données brutes (double calcul, pas de confiance aveugle en une seule implémentation).
- Vérification de cohérence inter-tables (ex. somme des composantes du bilan, Total Assets = Total Liabilities + Equity, avec tolérance d'arrondi documentée).
- Revue qualitative : les entreprises classées en tête du screening "Quality" doivent être économiquement plausibles (pas de résultat absurde dû à une donnée aberrante non filtrée).

## 12. Expected Deliverables

- Base PostgreSQL fonctionnelle avec schéma documenté et diagramme entité-relation.
- 15+ requêtes SQL avancées documentées et commentées.
- Moteur de screening avec 4 profils, seuils paramétrables via configuration externe (YAML), pas en dur dans le SQL.
- Suite de tests passant (`pytest`).
- README professionnel (section 13).
- Rapport de recherche (section 14).
- `data_sources.md` complet.
- Section optimisation SQL avec preuves avant/après (temps d'exécution, plans EXPLAIN).

## 13. README Structure

```
# Financial Intelligence & Deal Analytics Platform
## Abstract
## Motivation
## Research Question
## Key Contributions
## Data (+ limitations, notamment sur les données M&A)
## Methodology
## Database Architecture (ERD)
## SQL Highlights (2-3 requêtes commentées, les plus démonstratives)
## Screening Engine
## Results
## Query Optimization
## Limitations
## Reproducibility (docker compose up, make fetch-data, make load, make test)
## Installation
## Usage
## Tests
## References
```

## 14. Research Paper Structure (`reports/research_report.md`)

```
Abstract
1. Introduction
2. Research Question
3. Background (concepts de corporate finance et de valorisation mobilisés)
4. Data (sources, période, échantillon, limitations)
5. Methodology (modèle de données, définitions des ratios, logique de screening)
6. Results (rankings, profils de screening, dynamique des multiples/transactions)
7. Robustness (sensibilité des rankings au choix de fenêtre temporelle et de secteur de comparaison)
8. Economic Interpretation (pourquoi ces résultats sont-ils plausibles économiquement ?)
9. Limitations (échantillon M&A restreint, biais de survivance, qualité Yahoo Finance)
10. Conclusion
11. References (uniquement sources vérifiables : documentation SEC, FRED, littérature standard sur les ratios financiers — pas de référence inventée)
```

## 15. GitHub Presentation Strategy

- README avec badge de build/tests, diagramme ERD en image (généré depuis le schéma, pas dessiné à la main).
- Un exemple concret de sortie du moteur de screening (table Markdown) visible directement dans le README, avec mention explicite que les valeurs proviennent d'un run réel documenté et daté.
- Commits atomiques et sémantiques (`feat:`, `test:`, `docs:`, `perf:`), pas de commit "final".
- Un fichier `docs/design_decisions.md` séparé expliquant les arbitrages de modélisation (ex. pourquoi une table `valuations` séparée plutôt que des colonnes dans `companies`).
- Aucune donnée fictive présentée comme réelle ; tout chiffre affiché dans le README doit provenir d'une exécution réelle et documentée du pipeline, ou être explicitement marqué comme exemple illustratif.

---

*Prochaine étape après validation de ce cadrage : Section suivante du roadmap — conception du schéma relationnel (`sql/schema/001_init.sql`) et du diagramme entité-relation.*
