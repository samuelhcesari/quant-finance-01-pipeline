# Data Model — Justification du schéma relationnel

**Statut :** Schéma conçu, DDL écrit (`sql/schema/001_init.sql`), **non encore appliqué ni vérifié** (bloqué par l'absence de Docker sur la machine de développement au moment de la rédaction — voir `PORTFOLIO_PROGRESS.md`).

Ce document justifie les choix de modélisation avant toute implémentation, conformément à la règle du cahier des charges : aucune ligne de DDL n'est écrite sans que sa raison d'être soit documentée ici.

---

## 1. Principes directeurs

- **3NF raisonnable** : pas de colonne dérivable stockée si elle peut être recalculée de façon fiable en SQL (les ratios — marges, ROIC, leverage, multiples — vivent dans des *vues*, jamais dans des colonnes de table, cf. charte section 7 et section 5).
- **Une table = une source de vérité** : les données brutes normalisées (états financiers, prix de marché, macro, transactions) sont stockées telles que produites par les fetchers ; aucune transformation métier n'est appliquée au chargement.
- **Traçabilité** : toute donnée sensible à la source (notamment M&A) porte une référence explicite à son origine (`source_url`, `source_type`), car le jeu de données de transactions est construit manuellement à partir d'annonces publiques (charte section 6).
- **Séparation période / contenu** : les trois états financiers (résultat, bilan, flux de trésorerie) partagent la même notion de période comptable. Plutôt que de dupliquer `company_id`, `period_end_date`, `fiscal_year`, `form_type` dans chacune des trois tables, ces métadonnées sont isolées dans `fiscal_periods`, référencée par les trois tables d'états financiers. Cela évite les incohérences (ex. une même période avec deux dates de clôture différentes selon la table) et centralise la contrainte d'unicité `(company_id, period_end_date, period_type)`.

## 2. Les 12 tables

| # | Table | Rôle | Alimentée par |
|---|---|---|---|
| 1 | `sectors` | Taxonomie sectorielle (comparaison intra-secteur des multiples et rankings) | Statique / SEC SIC codes |
| 2 | `companies` | Référentiel entreprises (CIK, ticker, secteur, statut public/privé) | SEC EDGAR (CIK), Yahoo Finance (ticker) |
| 3 | `fiscal_periods` | Référentiel des périodes comptables (1 ligne = 1 période = 1 filing) | SEC EDGAR (accession number, form type) |
| 4 | `income_statements` | Compte de résultat par période | SEC EDGAR Company Facts (XBRL) |
| 5 | `balance_sheets` | Bilan par période | SEC EDGAR Company Facts (XBRL) |
| 6 | `cash_flow_statements` | Tableau de flux de trésorerie par période | SEC EDGAR Company Facts (XBRL) |
| 7 | `market_prices` | Cours, volume, capitalisation par jour | Yahoo Finance (`yfinance`) |
| 8 | `macro_indicators` | Séries macro (taux, spreads) pour contextualiser les cycles de deals | FRED |
| 9 | `transactions` | Transactions M&A (annonce, prix offert, statut) | 8-K SEC / communiqués de presse, saisie manuelle documentée |
| 10 | `transaction_financials` | Financials de la cible au moment de l'annonce (pour calcul de prime et multiple payé) | Dérivé de `transactions` + documents sources |
| 11 | `screening_profiles` | Métadonnées des 4 profils de screening (nom, description, config YAML référencée) | `configs/*.yaml` |
| 12 | `screening_results` | Résultats d'exécution du moteur de screening (audit trail, testable) | Généré par le moteur SQL |

## 3. Justification des choix non triviaux

### 3.1 `fiscal_periods` séparé des trois états financiers
Alternative rejetée : dupliquer `company_id` / `period_end_date` / `form_type` dans `income_statements`, `balance_sheets`, `cash_flow_statements`. Rejetée car (a) risque d'incohérence entre les trois tables pour une même période, (b) une contrainte d'unicité et des index sur la notion de période n'ont besoin d'exister qu'une fois. `fiscal_periods` est la clé de jointure unique vers les trois tables (relation 1:1 via `fiscal_period_id` en clé primaire ET étrangère).

### 3.2 Pas de table `valuations`
Alternative envisagée dans la charte (section 15, `docs/design_decisions.md` à venir) : une table `valuations` séparée. Décision : **rejetée pour cette version**. `EV`, `EV/EBITDA`, `P/E`, `FCF Yield`, etc. sont entièrement dérivables de `balance_sheets` (dette, cash) + `market_prices` (market cap) + `income_statements`/`cash_flow_statements` (EBITDA, FCF) à une date donnée. Les stocker créerait une redondance et un risque de désynchronisation si une donnée source est corrigée après coup. Ces métriques vivront dans des vues SQL (`v_valuation_multiples`, etc.), conformément au principe directeur de la charte : *"toute la logique financière vit en SQL (vues)"*. Ce choix sera reconsidéré si le besoin de figer un instantané de valorisation (ex. valorisation au moment d'une transaction) apparaît — c'est déjà couvert pour le cas M&A par `transaction_financials`.

### 3.3 `transaction_financials` séparé de `transactions`
Une transaction M&A peut concerner une cible privée non couverte par `income_statements`/`balance_sheets` (pas de filing SEC). `transaction_financials` capture donc un instantané autonome (revenue TTM, EBITDA TTM, dette nette, EV à l'offre, multiple payé) directement depuis le document source de l'annonce, sans dépendre de l'existence de filings réguliers pour la cible. Table séparée plutôt que colonnes dans `transactions` : ces champs sont optionnels et spécifiques à l'analyse de multiples, ils ne définissent pas l'entité "transaction" elle-même.

### 3.4 `screening_results` comme table (pas seulement une vue)
Le moteur de screening est paramétrable via YAML (`configs/`), donc son résultat dépend d'une configuration versionnée à un instant donné — ce n'est pas une fonction pure des données financières seules. Stocker les résultats d'exécution (avec `run_date`, `config_hash`) permet : (a) l'audit trail exigé par la charte (*"aucune donnée fictive... tout chiffre affiché doit provenir d'une exécution réelle et documentée"*), (b) les tests du moteur de screening (section 10 : *"vérifier qu'un enregistrement synthétique... produit bien le résultat attendu"*) sans recalcul implicite, (c) la comparaison de rankings entre deux versions de configuration.

### 3.5 `companies.cik` et `companies.ticker` nullable
Une entreprise cible de M&A privée (jamais cotée, jamais filante SEC) doit pouvoir exister dans `companies` pour permettre la jointure depuis `transactions.target_company_id`, sans posséder ni CIK ni ticker. D'où `is_public BOOLEAN` pour distinguer explicitement ce cas plutôt que de déduire le statut de la nullité des colonnes.

## 4. Contraintes d'intégrité clés

- Toutes les FK sont `NOT NULL` sauf lorsque justifié explicitement ci-dessus (cibles/acquéreurs privés dans `transactions`).
- `UNIQUE(company_id, period_end_date, period_type)` sur `fiscal_periods` — empêche le double chargement d'une même période (idempotence des loaders, cf. charte section 9 étape 3).
- `UNIQUE(company_id, price_date)` sur `market_prices`, `UNIQUE(series_code, obs_date)` sur `macro_indicators` — même logique d'idempotence pour les chargements `ON CONFLICT DO UPDATE`.
- `CHECK` sur les colonnes énumérées (`period_type`, `form_type`, `status`, `payment_type`, `source_type`) plutôt que des tables de référence séparées : ce sont des ensembles de valeurs fermés, stables, et sans attribut propre — une table de lookup ajouterait une jointure sans bénéfice.

## 5. Ce que ce schéma ne couvre pas encore

- Pas de gestion de versionnement/restatement des filings (un 10-K/A qui corrige un 10-K précédent) — hors scope de la V1, à documenter comme limitation si rencontré dans les données réelles.
- Pas de devise multi-monnaie — toutes les données sont supposées en USD (cohérent avec l'échantillon SEC EDGAR US annoncé en charte section 9 étape 2).
- `screening_profiles.config_path`/`config_version` référencent des fichiers YAML externes qui n'existent pas encore (créés à l'étape 6 du roadmap) — la table est prête à les recevoir dès leur création.
