# Data Sources

Documentation des sources de données utilisées, conformément à `docs/00_project_charter.md` section 6. Chaque exécution réelle des fetchers est journalisée ci-dessous avec sa date, son résultat exact, et les biais connus. Aucune donnée de ce projet n'est inventée.

## 1. SEC EDGAR — Company Facts API (XBRL)

- **URL** : `https://data.sec.gov/api/xbrl/companyfacts/CIK{10 chiffres}.json`
- **Mapping ticker → CIK** : `https://www.sec.gov/files/company_tickers.json`
- **Fetcher** : [`src/financial_intelligence/data/fetch_sec_edgar.py`](../src/financial_intelligence/data/fetch_sec_edgar.py)
- **Authentification** : aucune clé requise. Header `User-Agent` obligatoire déclarant un contact réel (format `nom-du-projet contact@example.com`, défini via `SEC_USER_AGENT` dans `.env`, jamais commité), conformément à la politique d'accès équitable de la SEC.
- **Contenu** : états financiers US GAAP normalisés issus des 10-K/10-Q, tous les concepts `us-gaap` disponibles par entreprise (pas de filtrage à la source — le filtrage vers les champs utiles se fera à l'étape de normalisation/chargement, étape 3 du roadmap).
- **Unités** : telles que rapportées par l'entreprise (généralement USD, non ajustées à une échelle commune).
- **Transformations appliquées à la collecte** : aucune. JSON brut sauvegardé tel quel dans `data/raw/sec_edgar/{ticker}.json`.
- **Exécution réelle** : 2026-08-19, 43/43 tickers récupérés avec succès (0 échec). Volume total : 182 Mo. Exemples vérifiés manuellement : AAPL (CIK 320193, 1509 points us-gaap), PFE (CIK 78003, 2001 points us-gaap).
- **Biais connus** : couverture limitée aux entreprises qui filent auprès de la SEC (US listées) — pas de comparaison possible avec des entreprises privées ou étrangères non filantes sans complément manuel (cf. `transaction_financials` pour les cibles M&A privées).

## 2. FRED (Federal Reserve Economic Data)

- **URL** : `https://api.stlouisfed.org/fred/series/observations`
- **Fetcher** : [`src/financial_intelligence/data/fetch_fred.py`](../src/financial_intelligence/data/fetch_fred.py)
- **Authentification** : clé API gratuite (`FRED_API_KEY` dans `.env`, jamais commitée — voir `.gitignore` et `.env.example`).
- **Séries retenues** (choisies pour contextualiser les cycles M&A/LBO, cf. charte section 6) :
  | Série | Description | Usage |
  |---|---|---|
  | `DGS10` | 10-Year Treasury Constant Maturity Rate | taux sans risque |
  | `BAMLH0A0HYM2` | ICE BofA US High Yield Index Option-Adjusted Spread | coût de la dette LBO |
  | `FEDFUNDS` | Federal Funds Effective Rate | cycle monétaire |
- **Transformations appliquées à la collecte** : aucune. JSON brut sauvegardé dans `data/raw/fred/{series_id}.json`.
- **Exécution réelle** : 2026-08-19, 3/3 séries récupérées (0 échec). `DGS10` : 16 860 observations. `BAMLH0A0HYM2` : 794 observations. `FEDFUNDS` : 865 observations.
- **Biais connus** : séries macro US uniquement — cohérent avec l'échantillon d'entreprises 100% US, mais ne permettrait pas de contextualiser des deals internationaux sans source additionnelle.
- **Limitation découverte en exploitant les données (sql/queries/003_macro_context.sql)** : contrairement à `DGS10` (16 860 observations, plusieurs décennies) et `FEDFUNDS` (865 observations, depuis les années 1950), la série `BAMLH0A0HYM2` ne couvre que 2023-08-21 → aujourd'hui (786 observations en base). L'API FRED n'a pas été interrogée avec une fenêtre de date restreinte (aucun `observation_start` dans `fetch_fred.py`) — la série renvoyée par FRED sous cet identifiant précis est simplement plus récente que prévu. Conséquence concrète : toute analyse croisant `BAMLH0A0HYM2` avec des événements antérieurs à août 2023 (ex. transactions M&A Horizon Therapeutics et Seagen) ne peut pas inclure le spread de crédit pour ces cas.

## 3. Yahoo Finance (via `yfinance`)

- **Fetcher** : [`src/financial_intelligence/data/fetch_yahoo.py`](../src/financial_intelligence/data/fetch_yahoo.py)
- **Authentification** : aucune (accès non officiel via la librairie `yfinance`).
- **Contenu** : historique OHLCV + Adj Close, période `5y` (2021-08-19 → 2026-08-19 au moment de l'exécution), fréquence journalière.
- **Transformations appliquées à la collecte** : aucune. CSV brut sauvegardé dans `data/raw/yahoo/{ticker}.csv`.
- **Exécution réelle** : 2026-08-19, 43/43 tickers récupérés (0 échec). ~1252–1255 lignes par ticker selon les jours de cotation effectifs sur la période. Volume total : 6,9 Mo.
- **Biais connus** (explicitement rappelés par la charte, section 6) : source non officielle, fiabilité variable, ne doit jamais être présentée comme référence réglementaire — utilisée uniquement pour les prix de marché et le calcul de capitalisation/EV, jamais pour les états financiers (ceux-ci viennent exclusivement de SEC EDGAR).

## 4. Univers d'entreprises

- **Définition** : [`configs/company_universe.yaml`](../configs/company_universe.yaml) — 43 entreprises, 3 secteurs contrastés choisis par l'utilisateur (pharmaceutique, technologie, construction).
- **Origine du choix** : sélection manuelle de grandes capitalisations et mid-caps US cotées, publiquement connues comme appartenant à ces secteurs. Ce n'est pas une donnée extraite d'une source externe — c'est une décision de scope du projet, documentée ici pour traçabilité.
- **Biais connu** : biais de survivance — toutes les entreprises de l'échantillon sont cotées et actives à la date de collecte (2026-08-19). Aucune entreprise délistée, faillie ou retirée de la cote sur la période 2021–2026 n'est incluse, ce qui peut surestimer la performance moyenne observée dans les analyses ultérieures.

## 5. Transactions M&A (étape 7 du roadmap)

Conformément à la charte (section 6), aucune base de deals M&A propriétaire n'étant accessible gratuitement, 5 transactions réelles ont été construites manuellement à partir d'annonces publiques SEC, chacune vérifiée directement sur la source primaire (récupérée via `curl` avec le `User-Agent` SEC requis — jamais un résumé secondaire pris pour argent comptant) avant saisie dans [`load_ma_transactions.py`](../src/financial_intelligence/data/load_ma_transactions.py). Chargé le 2026-08-19, idempotence vérifiée par double exécution (5 transactions, 4 `transaction_financials`, décomptes stables).

| Acquéreur | Cible | Annonce | Prix/action | Valeur | Source |
|---|---|---|---|---|---|
| Pfizer (PFE) | Seagen Inc. (SGEN, publique) | 2023-03-13 | 229,00 $ cash | 43 Md$ EV | [Exhibit 99.1, 8-K](https://www.sec.gov/Archives/edgar/data/1060736/000119312523068474/d467472dex991.htm) |
| Amgen (AMGN) | Horizon Therapeutics (HZNP, publique) | 2022-12-12 | 116,50 $ cash | 27,8 Md$ equity / 28,3 Md$ EV | [Exhibit 99.1, 8-K](https://www.sec.gov/Archives/edgar/data/318154/000119312522302256/d346985dex991.htm) |
| Cisco (CSCO) | Splunk Inc. (SPLK, publique) | 2023-09-20 | 157,00 $ cash | ~28 Md$ equity | [8-K, Item 1.01](https://www.sec.gov/Archives/edgar/data/858877/000119312523239165/d464532d8k.htm) |
| IBM (IBM) | HashiCorp, Inc. (HCP, publique) | 2024-04-24 | 35,00 $ cash | 6,4 Md$ EV | [Exhibit 99.1, 8-K](https://www.sec.gov/Archives/edgar/data/51143/000005114324000018/ibm-20240424xex991.htm) |
| Martin Marietta (MLM) | Lhoist North America, Inc. (**privée**) | 2026-06-27 | n/a (cible privée) | 13,5 Md$ (7,0 Md$ cash + 6,5 Md$ actions) | [8-K, Item 1.01](https://www.sec.gov/Archives/edgar/data/916076/000095015726000770/form8-k.htm) |

**Cible privée** : Lhoist North America (filiale du groupe belge Lhoist) n'a ni CIK ni ticker — ajoutée à `companies` avec `is_public = FALSE`, cas explicitement anticipé dans `docs/01_data_model.md` section 3.5.

**Financials des cibles** (`transaction_financials`) : réutilisent le même fetcher/normalizer SEC EDGAR que les 43 entreprises de l'univers principal (`data/raw/sec_edgar_ma_targets/*.json`). `target_revenue_ttm`/`target_ebitda_ttm` = dernier exercice ANNUEL COMPLET clôturé avant l'annonce (approximation documentée, pas un vrai TTM glissant qui exigerait des données trimestrielles non chargées à ce stade). Non chargé pour Splunk (aucune période annuelle extraite par le normalizer standard — tags XBRL non couverts) ni pour Lhoist North America (cible privée, états financiers non extraits séparément, hors périmètre de ce chargement) — `LEFT JOIN` volontaire dans les vues pour que la transaction reste visible même sans multiple calculable.

**Validation croisée réelle** : la prime recalculée par `v_transaction_premiums` pour Amgen/Horizon (`116,50 / 78,76 - 1 = 47,92%`) correspond exactement à la prime annoncée par Amgen dans son communiqué officiel ("a premium of approximately 47.9%"). Multiples EV/Revenue obtenus économiquement plausibles : Seagen 21,9x (biotech ADC pré-rentable très demandée), Horizon 8,8x (pharma spécialisée rentable), HashiCorp 11,0x (SaaS infrastructure en forte croissance).

**Vues** : [`011_v_transaction_premiums.sql`](../sql/views/011_v_transaction_premiums.sql) (Premium = Offer/Unaffected - 1, charte section 5), [`012_v_transaction_multiples.sql`](../sql/views/012_v_transaction_multiples.sql) (EV/EBITDA, EV/Revenue). Appliquées sans erreur le 2026-08-19.

## 6. Normalisation et chargement (étape 3 du roadmap)

- **Normalizers** : [`normalize_sec_edgar.py`](../src/financial_intelligence/data/normalize_sec_edgar.py), [`normalize_yahoo.py`](../src/financial_intelligence/data/normalize_yahoo.py), [`normalize_fred.py`](../src/financial_intelligence/data/normalize_fred.py) — produisent `data/processed/*.csv` à partir du brut.
- **Loader** : [`load_to_postgres.py`](../src/financial_intelligence/data/load_to_postgres.py) — idempotent (`INSERT ... ON CONFLICT DO UPDATE`), vérifié par double exécution consécutive (714/714/714 lignes stables sur `fiscal_periods`/`income_statements`/`balance_sheets` entre les deux runs, aucune ligne dupliquée).
- **Portée assumée** : uniquement les dépôts annuels (10-K, `fp=FY`) — le détail trimestriel n'est pas chargé à ce stade.
- **Correspondance des tags US-GAAP** : [`xbrl_concepts.py`](../src/financial_intelligence/data/xbrl_concepts.py). Les filers SEC ne taguent pas tous la même ligne comptable avec le même concept XBRL ; chaque champ a une liste de tags candidats par ordre de préférence. Aucune valeur non trouvée n'est inventée (reste `NULL`).
- **Ce qui a foiré et comment je l'ai trouvé (2026-08-19)**, chacun vérifié par requête SQL directe après correction, pas juste "corrigé et on passe à autre chose" :
  1. Mon premier chargement donnait 1560 lignes pour 43 entreprises — beaucoup trop pour ~15 ans d'historique par entreprise. En creusant, j'ai vu qu'un même exercice apparaît dans plusieurs 10-K différents (l'année où c'est l'exercice courant, puis en comparatif dans les 10-K suivants). J'ai dédoublonné par date de clôture en gardant le filing le plus ancien — celui où la période était vraiment l'exercice courant.
  2. Après ce premier fix, je suis retombé à 764 lignes, mais un test de cohérence m'a montré des chiffres bizarres pour BMY. En regardant le JSON brut, j'ai trouvé que certains 10-K contiennent des données trimestrielles supplémentaires (une note "quarterly financial data"), taguées exactement comme l'exercice annuel (`form=10-K/fp=FY`), parfois avec la même date de fin (BMY 2015 : un `NetIncomeLoss` "T4 seul" et un "exercice complet" avec la même date de fin dans le même filing). Mon ancre de détection utilisait `Assets` (un concept "instant", une seule valeur par date) — incapable de distinguer les deux. Je suis passé à `NetIncomeLoss` (un concept "duration") filtré sur 350-380 jours, et j'ai resserré la correspondance à `(accn, start, end)` exact plutôt que juste `(accn, end)`.
  3. Troisième problème, plus sournois : le tag `fy` que renvoie SEC EDGAR n'est pas fiable pour les tableaux "Selected Financial Data" (5 ans d'historique) des 10-K anciens (~2009-2011) — plusieurs exercices distincts s'y retrouvaient tagués avec le même `fy`. J'ai arrêté de faire confiance à ce tag et je dérive `fiscal_year` directement de `period_end_date`, avec un cas particulier pour les calendriers 52/53 semaines (clôture le 1er-3 janvier, ex. JNJ).
  4. Résultat après ces trois corrections : **0 doublon** `(company_id, fiscal_year)` sur les 714 lignes chargées, vérifié par requête `GROUP BY ... HAVING COUNT(*) > 1`.
- **Validation de cohérence inter-tables (charte section 11)** : test réel `Total Assets ≈ Total Liabilities + Total Equity` (tolérance 1%), formalisé dans `sql/views/013_v_data_quality_flags.sql`. Sur les 714 lignes, seules 461 ont les trois champs renseignés (`total_liabilities` n'est rempli qu'à 64,6%, cf. ci-dessous) — parmi ces 461 lignes réellement testables, **56 (12,1%) sont hors tolérance**. Cas le plus important investigué en détail : MRNA exercice 2017 (écart de 108%) — remonte au JSON XBRL brut lui-même (`Assets`=1 084 489 000, `Liabilities`=459 193 000, `StockholdersEquity`=-551 365 000, filing `0001682852-19-000009`), pas à une erreur d'extraction. Explication la plus probable : Moderna, non cotée avant fin 2018, portait probablement des actions préférentielles rachetables classées en "capitaux propres temporaires" (mezzanine equity, hors `Liabilities` et hors `StockholdersEquity` en XBRL) — catégorie non capturée par le schéma actuel. **Limitation documentée, non corrigée à ce stade** : les champs `total_liabilities`/`total_equity` peuvent sous-estimer le passif réel pour les entreprises ayant des instruments de capitaux propres temporaires (typiquement des sociétés récemment introduites en bourse). À garder en tête pour l'étape 4 (vues analytiques) : les ratios de levier calculés sur ces lignes spécifiques seront biaisés.
- **Taux de remplissage par champ (43 entreprises, 714 exercices-année, mesuré le 2026-08-19 sur le dataset final)** : `net_income` 100,0%, `cfo`/`cfi`/`cff` 100,0%, `cash_and_equivalents` 99,9%, `total_equity` 99,4%, `revenue` 97,8%, `total_assets` 94,1% (pas 100% — l'ancre de détection des périodes annuelles est un concept de flux (`NetIncomeLoss`), pas `Assets`, depuis la correction du bug quart/année : cf. ci-dessus — une période peut donc avoir un résultat net sans bilan complet dans le même filing) ; plus bas : `total_liabilities` 64,6%, `short_term_debt` 58,7%, `dividends_paid` 57,0%, `ebit` 75,6%, `ebitda` 72,5% (EBITDA n'est pas un concept US-GAAP standard, reconstruit uniquement quand `OperatingIncomeLoss` ET un tag de D&A sont tous deux présents dans le même filing). Détail exact reproductible via `python -m financial_intelligence.data.normalize_sec_edgar`.
- **`market_prices.shares_outstanding` et `.market_cap`** : volontairement laissés `NULL`. `yfinance` ne fournit qu'un nombre d'actions en circulation actuel (snapshot), pas un historique quotidien fiable — le multiplier par le prix historique produirait une capitalisation approximative non documentable précisément par date. Limitation explicite, à lever plus tard si besoin (ex. via `dei:EntityCommonStockSharesOutstanding` de SEC EDGAR, disponible par date de dépôt).

## 7. Vues analytiques (étape 4 du roadmap) — validation par calcul manuel

6 vues créées dans `sql/views/` (`001_v_growth.sql` → `006_v_valuation.sql`), une par famille de formule de la charte section 5. Appliquées le 2026-08-19 sur l'instance réelle (port 5433), aucune erreur SQL, chaque vue testée sur les 714 lignes de l'échantillon complet.

**Validation manuelle sur AAPL, exercice fiscal 2024** (chiffres bruts tirés de la base, calcul indépendant en dehors de SQL puis comparaison à la sortie des vues — charte section 10/11) :

| Métrique | Calcul manuel | Sortie de la vue | Écart |
|---|---|---|---|
| Gross margin | 180 683 / 391 035 = 0,46213 | 0,46206 | arrondi |
| EBITDA margin | 134 661 / 391 035 = 0,34434 | 0,34437 | arrondi |
| Net margin | 93 736 / 391 035 = 0,23971 | 0,23971 | exact |
| Revenue growth (FY24 vs FY23) | 391 035 / 383 285 − 1 = 0,02022 | 0,02022 | exact |
| FCF growth | 108 807 / 99 584 − 1 = 0,09262 | 0,09262 | exact |
| ROE (Avg equity) | 93 736 / ((56 950+62 146)/2) = 1,57415 | 1,57413 | arrondi |
| ROIC | NOPAT 93 529,5 / IC 123 669 = 0,75627 | 0,75631 | arrondi |
| Net Debt/EBITDA | (96 662−29 943) / 134 661 = 0,4956 | 0,4955 | arrondi |
| Interest coverage | `interest_expense` NULL pour FY2024 → non calculable | NULL | conforme |
| FCF | 118 254 − 9 447 = 108 807 | 108 807 | exact |
| EV/EBITDA (approx.) | prix 227,79 $ (27/09/2024, dernier cours ≤ clôture) × 15 408 095 000 actions ≈ 3 509,8 Md$ + dette nette → EV ≈ 3 576,5 Md$ / EBITDA 134 661 M$ | 26,560x | plausible pour AAPL à cette date |

Les 6 vues concordent avec le calcul indépendant à l'arrondi près sur tous les points testés. Aucune divergence non expliquée.

## 8. Couche de qualité de données

Avant cette section, coverage/identités comptables/outliers étaient documentés dispersés en texte libre dans ce fichier — pas interrogeables directement. Consolidé dans `sql/views/013_v_data_quality_flags.sql` et `sql/queries/004_data_quality_report.sql`, exécuté le 2026-08-19 :

**Taux de remplissage** (10 champs clés, sur 714 lignes) : `net_income`/`cfo` 100%, `revenue` 97,8%, `total_equity` 99,4%, `total_assets` 94,1%, `ebit` 75,6%, `ebitda` 72,5%, `total_liabilities` 64,6%, `short_term_debt` 58,7%, `dividends_paid` 57,0%.

**Identité comptable** : 461/714 lignes réellement testables (les trois champs du bilan renseignés), dont 56 (12,1%) hors tolérance de 1%. Voir section 6/7 pour le cas MRNA 2017 investigué en détail.

**Outliers statistiques** (z-score intra-secteur, |z| > 3 — comparé aux pairs du même secteur, pas à l'ensemble de l'échantillon) : 25/714 lignes flaguées sur au moins une métrique (11 croissance, 6 marge, 8 levier). Exemples vérifiés économiquement explicables, pas des erreurs de données : MRNA 2020-2021 (croissance +1234% puis +2199%, lancement du vaccin COVID), VRTX 2009-2011 (marges très négatives avant l'approbation de son premier médicament, Incivek en 2011), BLDR 2012 (levier 114,9x, séquelle de la crise des subprimes sur la construction).

**Doublons** : 0 ligne `(company_id, fiscal_year)` en double, confirmé par requête indépendante de la contrainte UNIQUE qui les empêche déjà en base.

**Restatements/révisions de filings** : hors périmètre, décision prise dès la conception du schéma (`01_data_model.md` section 5) — le loader retient systématiquement le filing le plus ancien par exercice (section 6 ci-dessus), donc les chiffres "as originally reported" sont préférés à une éventuelle correction ultérieure.
