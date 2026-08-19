# Design Decisions

Les arbitrages qui m'ont vraiment demandé de trancher entre deux options, avec pourquoi j'ai tranché comme ça. Les décisions de modélisation du schéma lui-même (pourquoi 12 tables précises, pourquoi pas de table `valuations`) sont dans [`01_data_model.md`](01_data_model.md) — ici, ce sont les arbitrages transverses au reste du pipeline.

## 1. J'ai vérifié tout le pipeline sur PostgreSQL portable plutôt que d'attendre Docker

Docker Desktop demande une élévation admin (UAC) et l'activation de WSL2, que je ne pouvais pas faire depuis mon environnement de développement. Plutôt que de bloquer tout le projet en attendant, j'ai téléchargé les binaires PostgreSQL 16.15 officiels (EnterpriseDB, sans installeur) et vérifié tout le pipeline dessus — schéma, chargement, vues, screening, tests, tout tourne réellement.

`docker-compose.yml` et le `Makefile` restent le chemin de reproductibilité que je documente comme cible officielle, mais je ne l'ai jamais testé sur cette machine. Je le note explicitement à chaque étape concernée dans `PORTFOLIO_PROGRESS.md` plutôt que de laisser croire que c'est vérifié.

## 2. `fiscal_year` est calculé depuis la date de clôture, pas depuis le tag `fy` de SEC EDGAR

Au départ, j'utilisais directement le champ `fy` renvoyé par l'API SEC EDGAR — ça avait l'air fiable. Le problème : quand une période comparative est reprise dans un 10-K ultérieur, son `fy` hérite parfois de l'année du filing plutôt que de sa propre année. J'ai vu ça concrètement sur AAPL : le 10-K FY2025 retague le bilan de 2024-09-28 avec `fy=2025`, alors que la même donnée dans le 10-K FY2024 d'origine porte correctement `fy=2024`. Et les tableaux "Selected Financial Data" des vieux 10-K (~2009-2011) taguent parfois plusieurs exercices différents avec le même `fy`.

J'ai changé pour dériver `fiscal_year` directement de `period_end_date` (avec un cas particulier pour les calendriers 52/53 semaines, genre JNJ, où la clôture tombe parfois le 1er janvier). C'est déterministe et ça ne dépend d'aucune convention de tagging propre à chaque entreprise. Détail des cas trouvés : `data_sources.md` section 6.

## 3. J'ancre les périodes annuelles sur un concept de flux, pas sur le bilan

Ma première version détectait les exercices annuels via `Assets` (un concept "instant", une seule valeur par date). Ça semblait suffisant. Le bug est apparu sur Bristol-Myers Squibb 2015 : certains 10-K contiennent des données trimestrielles supplémentaires (une note "quarterly financial data") qui partagent parfois exactement la même date de fin que l'exercice annuel — impossible à distinguer avec un concept "instant" seul.

J'ai basculé sur `NetIncomeLoss` (un concept "duration", avec un début et une fin) filtré sur une durée de 350 à 380 jours, ce qui exclut mécaniquement les trimestres. Conséquence que j'assume : `total_assets` n'est rempli qu'à 94,1% des lignes, pas 100%, parce qu'une période peut avoir un résultat net sans bilan complet dans le même filing. Je préfère documenter cette limite plutôt que la cacher derrière un taux de remplissage artificiellement gonflé.

## 4. J'ai matérialisé `v_company_financial_profile` après avoir vu le vrai coût en EXPLAIN ANALYZE

Je ne me suis pas dit "il faut une vue matérialisée" a priori. J'ai mesuré une requête de consultation d'historique d'entreprise à 332,75 ms, ce qui m'a paru élevé pour 714 lignes. Le plan EXPLAIN ANALYZE montrait que PostgreSQL recalculait les fonctions fenêtrées (`LAG`) sur les 714 lignes complètes avant même d'appliquer le filtre `ticker` — le planificateur ne peut pas pousser ce filtre à travers la frontière de partition d'une fonction fenêtrée sur une autre colonne.

La matérialisation (`mv_company_financial_profile`, rafraîchie après chaque chargement) ramène ça à 0,171 ms. Le compromis : la vue peut être périmée entre deux chargements, ce que j'accepte parce qu'on lit (screening, consultation) beaucoup plus souvent qu'on ne charge. Détail complet avec les deux plans avant/après : `sql/optimization/README.md`.

## 5. Le moteur de screening est générique, les seuils vivent en YAML

J'aurais pu écrire directement `WHERE revenue_growth >= 0.15 AND ...` dans une vue SQL par profil, ou coder les 4 profils comme 4 fonctions Python avec des constantes. J'ai préféré un seul moteur générique (`evaluate_rule`/`evaluate_profile`) qui interprète des règles `{metric, operator, threshold, allow_null}` définies en YAML — pour pouvoir changer un seuil (`roic >= 0.15` → `0.12`) sans toucher au SQL ni au Python.

Ça m'a forcé à trancher un cas que j'aurais pu laisser implicite : que fait-on quand une métrique est `NULL` ? Par défaut en SQL, `NULL >= 0.15` n'est ni vrai ni faux, ça disparaît silencieusement. J'ai rendu ce choix explicite par règle (`allow_null: true/false`) plutôt que de laisser le comportement SQL par défaut décider à ma place — testé dans `tests/test_screening_engine.py`.

## 6. J'approxime la capitalisation boursière avec `close_price × shares_diluted`

Pour calculer l'EV, le P/B ou le FCF Yield, il me fallait une capitalisation boursière. Le problème : `yfinance` ne donne qu'un nombre d'actions en circulation actuel (un instantané), pas un historique. J'ai deux options : laisser ces métriques vides, ou approximer avec le nombre moyen pondéré d'actions diluées de l'exercice (`shares_diluted`, une vraie donnée SEC EDGAR, disponible pour 90,9% des exercices).

J'ai choisi d'approximer plutôt que de laisser vide, parce que ça reste une vraie donnée multipliée par un vrai cours — mais je le dis clairement dans le code et dans la doc : ce n'est pas un nombre d'actions exact à la date de clôture, notamment pour les entreprises qui rachètent massivement leurs actions en cours d'année (Apple, typiquement).

## 7. Une cible M&A privée est une ligne `companies` comme les autres

Quand j'ai chargé la transaction Martin Marietta / Lhoist North America, Lhoist n'a ni CIK ni ticker (filiale privée d'un groupe belge). J'avais anticipé ce cas dès la conception du schéma (`01_data_model.md` section 3.5) plutôt que de le découvrir en cours de route : `companies.is_public = FALSE`, `cik`/`ticker` `NULL`. Une table séparée pour les entités privées aurait dupliqué la logique de jointure dans `transactions` (`acquirer_company_id`/`target_company_id` pointent toujours vers `companies`, publique ou privée) sans bénéfice réel.
