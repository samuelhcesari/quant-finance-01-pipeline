# Portfolio Progress — Projet 1/3 : Financial Intelligence Pipeline (SQL)

Suivi d'avancement. Une case n'est cochée que quand le résultat a vraiment tourné, pas juste écrit dans le code. Roadmap reprise de [`docs/00_project_charter.md`](docs/00_project_charter.md) section 9.

## Cadrage

- [x] Charte (`docs/00_project_charter.md`)
- [x] Justification du schéma (`docs/01_data_model.md`)

## Roadmap

- [x] **1. Schéma & normalisation**
  - `sql/schema/001_init.sql` : 12 tables, contraintes, index — justifications dans `docs/01_data_model.md`.
  - `docker-compose.yml`/`Makefile` écrits mais jamais exécutés — Docker Desktop absent de la machine (voir "Blocages" plus bas).
  - Schéma appliqué et vérifié via PostgreSQL 16.15 portable (binaires EnterpriseDB, port 5433) : `initdb`, `pg_ctl start`, `createdb`, puis `psql -f sql/schema/001_init.sql` → 12 tables créées sans erreur, confirmées par `\dt`.
  - À refaire un jour via `make up && make schema` pour valider le chemin Docker officiel — la vérification actuelle porte sur le DDL, pas sur l'environnement Docker en lui-même.

- [x] **2. Fetchers de données**
  - Univers défini dans `configs/company_universe.yaml` : 43 entreprises, 3 secteurs (pharma, tech, construction).
  - `fetch_sec_edgar.py` : 43/43 OK, 182 Mo de JSON brut.
  - `fetch_fred.py` : 3/3 séries OK (DGS10 16 860 obs., BAMLH0A0HYM2 794, FEDFUNDS 865).
  - `fetch_yahoo.py` : 43/43 OK, 6,9 Mo de CSV, 5 ans d'historique.
  - Sources documentées dans [`docs/data_sources.md`](docs/data_sources.md).

- [x] **3. Chargement**
  - Normalizers écrits et exécutés : SEC EDGAR (43 entreprises → 714 lignes annuelles), Yahoo (53 940 lignes de prix), FRED (17 792 observations, 727 valeurs manquantes ignorées).
  - 3 bugs de normalisation trouvés en cours de route (doublons d'exercice inter-filings, confusion trimestre/exercice complet dans certains 10-K, tag `fy` peu fiable) — détail dans `docs/data_sources.md` section 6. Après correction : 0 doublon vérifié par requête.
  - `load_to_postgres.py` chargé sans erreur : sectors 3, companies 43, les 4 tables d'états financiers à 714 chacune, market_prices 53 940, macro_indicators 17 792.
  - Idempotence vérifiée (relancer le loader sans truncate donne les mêmes décomptes).
  - Test de cohérence comptable (Actif ≈ Passif + Capitaux propres, tolérance 1%) : 56 lignes en dehors sur les 461 réellement testables (12,1% — pas 714, `total_liabilities` manque sur le reste). Cas MRNA 2017 creusé et expliqué (probables capitaux propres temporaires pré-IPO), pas corrigé.

- [x] **4. Vues analytiques**
  - 6 vues (`v_growth`, `v_margins`, `v_returns`, `v_leverage`, `v_cash_flow`, `v_valuation`) appliquées sans erreur, testées sur les 714 lignes.
  - Validées à la main sur AAPL FY2024 : marges, croissance, ROE 157,4%, ROIC 75,6%, EV/EBITDA 26,6x, P/E 37,5x — tout concorde. Détail dans `docs/data_sources.md` section 7.
  - Dénominateurs négatifs/nuls gérés explicitement partout (`NULLIF`, flags `*_prior_negative`), jamais masqués.
  - `v_valuation` approxime la capitalisation par `close_price × shares_diluted` faute de mieux (limitation documentée).

- [x] **5. SQL avancé**
  - `v_company_financial_profile` : CTE consolidant les 5 vues de ratios en une ligne par entreprise/exercice.
  - `v_sector_rankings` : `RANK()`/`PERCENT_RANK()` intra-secteur, `NULLS LAST`, `sector_peer_count` exposé.
  - `v_trailing_trends` : moyenne mobile 3 ans, `LAG(roic, 3)`.
  - Vérifié sur données réelles : NVDA #1 en croissance et marge dans le secteur Tech FY2024 (boom IA), TXN dernier (creux semi-conducteurs) ; ROIC AAPL en hausse continue 2020→2025 ; `roic_3y_ago` de 2024 recoupe exactement le ROIC réel de 2021.

- [x] **6. Moteur de screening**
  - `v_screening_base` regroupe profil financier, tendances 3 ans et valorisation — aucun seuil dedans.
  - 4 profils en YAML (`configs/screening/`), moteur générique en Python, aucun chiffre en dur.
  - Exécuté sur les 714 lignes : distressed 3, pe_growth 54, pe_value 63, quality 107. Reproductible (double run, mêmes décomptes).
  - Résultats plausibles : quality retient AAPL/MSFT/NVDA/GOOGL/META/ADBE ; distressed identifie VTRS (dette post scission Pfizer/Mylan), INTC 2023, VMC 2010 (récession construction).

- [x] **7. Transactions M&A**
  - Migration `002_transactions_unique.sql` (contrainte manquante pour un chargement idempotent).
  - 5 transactions réelles chargées, chacune vérifiée sur sa source SEC primaire : PFE/Seagen, AMGN/Horizon Therapeutics, CSCO/Splunk, IBM/HashiCorp, MLM/Lhoist North America (cible privée, cas testé exprès).
  - Financials des 4 cibles publiques réutilisent le fetcher SEC EDGAR existant, chargés dans `transaction_financials` (Splunk et la cible privée non couverts, documenté).
  - `v_transaction_premiums`/`v_transaction_multiples` OK. Prime Amgen/Horizon recalculée (47,92%) colle avec celle annoncée officiellement (47,9%). Multiples EV/Revenue plausibles (Seagen 21,9x, Horizon 8,8x, HashiCorp 11,0x).

- [x] **8. Optimisation**
  - 2 requêtes benchmarkées (historique entreprise, classement sectoriel). Cause identifiée dans le plan : les fonctions fenêtrées se recalculaient sur les 714 lignes avant que le filtre s'applique — pas un problème d'index.
  - Solution : `mv_company_financial_profile` (vue matérialisée + 3 index), rafraîchie automatiquement après chargement. Les vues en aval en dépendent désormais.
  - Résultat : 332,75 ms → 0,171 ms (~1950x), et 12,25 ms → 0,854 ms (~14x) en bonus.
  - Non-régression vérifiée : screening ré-exécuté après le refactor, résultats identiques.

- [x] **9. Tests**
  - Gap comblé au passage : le runner Python pour appliquer les migrations SQL (demandé dans la charte) n'existait pas encore — créé et testé sur une base vide, 12 tables + 12 vues + 1 vue matérialisée sans erreur. `Makefile` corrigé au passage (n'appliquait que le DDL brut).
  - Base de test éphémère reconstruite à chaque session pytest, isolation par transaction.
  - Tests unitaires (parsing XBRL, chaque bug réel reproduit ; règles de screening).
  - Tests SQL avec valeurs calculées à la main sur une entreprise fictive.
  - Tests d'intégrité référentielle (chaque FK/CHECK/UNIQUE testée pour rejet effectif d'un orphelin).
  - Test bout-en-bout screening : deux cas synthétiques conçus pour passer/échouer.
  - 51/51 tests passent (~2,1s).

- [x] **10. Documentation**
  - README réécrit selon la structure de la charte.
  - `reports/research_report.md`, avec une vraie analyse de sensibilité (259/191/144 exercices qualifiants au seuil ROIC 10%/15%/20%).
  - `docs/design_decisions.md` : 7 arbitrages transverses documentés.
  - 2 erreurs trouvées en se relisant avant publication : un tableau ROIC approximé au lieu des vraies valeurs mesurées plus tôt, et un taux de remplissage `total_assets` cité comme 100% qui était devenu obsolète (94,1% réel) après un changement d'ancre du normalizer. Corrigées après revérification en base.
  - `Makefile` complété (`fetch-data`/`normalize`/`load`/`screen`/`test`).

## Au-delà du roadmap : profondeur quantitative

Le roadmap de la charte couvre schéma/rankings/screening, mais reste essentiellement descriptif (classements, seuils pass/fail) — trois questions posées dès la charte (section 2) n'avaient jamais reçu de réponse chiffrée. Ajouté dans `sql/queries/` :

- **Corrélation croissance/marge/ROIC vs multiples de valorisation** (`001_...sql`, `CORR()` natif Postgres, N=118) : quasi nulle globalement, mais en pharma/biotech marge et ROIC sont corrélés négativement au multiple (-0,70 / -0,40).
- **Profil des cibles M&A vs l'univers** (`002_...sql`, N=4, illustratif — pas un test statistique vu la taille) : HashiCorp et Seagen avaient la marge EBITDA la plus basse de leur secteur au moment de l'annonce.
- **Contexte macro FRED exploité pour la première fois** (`003_...sql`) : les 17 792 observations chargées à l'étape 2 ne servaient nulle part jusqu'ici. En les utilisant, découverte d'une vraie limite de couverture (le spread crédit high-yield ne remonte qu'à août 2023 dans les données récupérées, pas toute la profondeur disponible sur FRED) — documentée dans `docs/data_sources.md`.

Détail complet dans `reports/research_report.md` section 6.5.

## Suite au retour de relecture externe : couche data-quality + repositionnement

Un retour extérieur pointait à raison deux choses : le nom "Platform" survendait le périmètre réel (43 entreprises, 5 deals), et coverage/identités comptables/outliers étaient documentés en texte libre plutôt qu'interrogeables.

- **Repositionnement** : titre README changé en "Financial Intelligence Pipeline", avec une phrase explicite sur le périmètre volontairement restreint dès l'intro.
- **`v_data_quality_flags`** (`sql/views/013_...sql`) : identité comptable + détection d'outliers par z-score intra-secteur (|z| > 3), consolidés en une vue interrogeable.
- **`004_data_quality_report.sql`** : rapport complet (fill rate par champ, identité comptable, outliers, doublons).
- **Correction de précision trouvée en construisant cette vue** : le chiffre "56/714 (7,8%)" cité partout pour l'identité comptable était imprécis — seules 461 lignes ont assez de données pour être testées (`total_liabilities` à 64,6% de couverture), donc c'est en fait **56/461 (12,1%)**. Corrigé dans README, rapport et cette page.
- **25 outliers réels trouvés et vérifiés explicables** : MRNA (lancement vaccin COVID), VRTX (avant son premier médicament approuvé), BLDR (séquelle subprimes) — pas des erreurs de données.
- 5 tests ajoutés pour la nouvelle vue (identité comptable OK/KO/NULL, détection d'outlier avec échantillon assez large pour éviter l'effet de masquage statistique). **51/51 tests passent.**

## Blocages actifs

- **Docker Desktop absent.** Installation bloquée par une élévation admin que je ne peux pas gérer à distance. Contournement : PostgreSQL 16.15 portable (binaires EnterpriseDB, sans installeur, sans admin). Le chemin Docker reste la cible officielle de reproductibilité, à vérifier séparément quand Docker sera installé.

## Environnement PostgreSQL portable (contournement local, non versionné)

- Emplacement : `C:\Users\<user>\pgsql-portable\` (hors dépôt git).
- Port **5433** (pas 5432, pour ne pas entrer en conflit avec un futur Postgres Docker/natif).
- Démarrer : `pgsql\bin\pg_ctl.exe -D ...\data -l ...\server.log -o "-p 5433" start`
- Arrêter : `pgsql\bin\pg_ctl.exe -D ...\data stop`
- Connexion : `psql -h localhost -p 5433 -U fida -d financial_intelligence` (mot de passe dev : `fida_dev_password`).

## Visualisations (2026-08-20)

Audit préalable : zéro visualisation n'existait nulle part dans le repo (que des tableaux markdown), `results/` était vide (juste `.gitkeep`), aucune lib de plotting dans les dépendances. `v_screening_base` avait déjà toutes les colonnes nécessaires (P/E, EV/EBITDA, FCF Yield, Revenue Growth, EBITDA Margin, ROIC, Debt/Equity) — aucune modification SQL nécessaire.

- Ajout de `matplotlib>=3.8` (seule nouvelle dépendance) dans `requirements.txt`/`pyproject.toml`.
- `src/financial_intelligence/analytics/visualize.py` : 4 figures générées depuis les vues/tables existantes, sauvegardées dans `results/figures/*.png` (exception ajoutée au `.gitignore` pour que ces PNG soient visibles directement sur GitHub).
- **Bug trouvé en générant le graphique de comparaison sectorielle** : la moyenne du ROIC pharma tombait à -103%, écrasée par un seul point (ABBV 2016, ROIC réel de -8144%, capital investi proche de zéro cette année-là). Passé de moyenne à médiane pour ce graphique — corrigé avant publication, pas après.
- Gestion explicite des NULL/NaN/inf (`_clean_numeric`), testée (3 nouveaux tests).
- `make visualize` ajouté au Makefile. README mis à jour avec une section Visualizations (4 lignes, une image + une explication courte chacune).
- **54/54 tests passent** après ajout.

## 10/10 étapes terminées

Ce qui reste ouvert n'est pas une étape du roadmap, juste le blocage Docker documenté depuis l'étape 1 : une fois Docker Desktop installé, lancer `make up && make schema` puis vérifier les 12 tables via `docker compose exec postgres psql -U fida -d financial_intelligence -c '\dt'`, pour confirmer que le chemin Docker donne le même résultat que celui utilisé tout au long de ce projet.
