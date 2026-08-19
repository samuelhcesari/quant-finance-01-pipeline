# Optimisation SQL — étape 8 du roadmap

Preuves chiffrées avant/après (`EXPLAIN ANALYZE`), exécutées le 2026-08-19 sur l'instance PostgreSQL 16.15 réelle (port 5433, 714 lignes `fiscal_periods`, 43 entreprises). Aucun chiffre ci-dessous n'est estimé — tous proviennent d'une exécution réelle de `EXPLAIN ANALYZE`.

## Méthodologie

Plutôt que d'optimiser abstraitement, deux requêtes représentatives d'un usage réel de la plateforme ont été choisies :

- **Query A** — historique complet d'une entreprise (ex. consultation d'une fiche AAPL) : `SELECT * FROM v_company_financial_profile WHERE ticker = 'AAPL' ORDER BY fiscal_year`.
- **Query B** — classement sectoriel pour un exercice donné (ex. dashboard de screening) : `SELECT * FROM v_sector_rankings WHERE sector_name = 'Technologie' AND fiscal_year = 2024`.

## Constat initial (avant optimisation)

**Query A : 332,75 ms d'exécution pour 19 lignes retournées sur 714.**

Plan `EXPLAIN ANALYZE` (extrait) :
```
Sort (actual time=330.828..330.843 rows=19 loops=1)
  ->  Nested Loop (actual time=8.733..330.800 rows=19 loops=1)
        Join Filter: (...)
        Rows Removed by Join Filter: 13547
        ->  ... (empile v_growth, v_margins, v_returns, v_leverage, v_cash_flow)
              ->  WindowAgg (LAG sur revenue_growth, PARTITION BY company_id)
                    ->  Sort (Sort Key: company_id, fiscal_year) sur 714 lignes
              ... (5 niveaux de jointures similaires, un par vue de ratio)
        ->  Seq Scan on companies c
              Filter: (ticker = 'AAPL'::text)
Planning Time: 43.178 ms
Execution Time: 332.750 ms
```

**Cause identifiée** (pas supposée — lue directement dans le plan) : `v_company_financial_profile` empile 5 vues, chacune calculant des fonctions fenêtrées (`LAG`) `PARTITION BY company_id` sur l'intégralité des 714 lignes. Le filtre `ticker = 'AAPL'` ne s'applique qu'à la toute fin, via une jointure vers `companies`, plusieurs niveaux plus loin. Le planificateur PostgreSQL ne peut pas pousser ce filtre à travers la frontière de partition d'une fonction fenêtrée définie sur une autre colonne (`company_id`) — **ce n'est pas un index manquant**, c'est un recalcul complet du dataset à chaque lecture, même pour une seule entreprise.

**Query B : 12,25 ms** — déjà rapide, car le filtre `fiscal_year = 2024` est poussé efficacement dans `fiscal_periods` via l'index `idx_fiscal_periods_year` existant (`Bitmap Index Scan`, 42 lignes seulement remontées avant jointure). Aucune action nécessaire pour cette requête — mentionné ici pour ne pas laisser croire que "optimiser" signifie systématiquement "tout doit être lent au départ".

## Solution appliquée

`sql/optimization/001_mv_company_financial_profile.sql` : matérialisation de `v_company_financial_profile` (714 lignes, calculées une fois au chargement plutôt qu'à chaque lecture), avec :
- un index UNIQUE sur `fiscal_period_id` (requis pour `REFRESH MATERIALIZED VIEW CONCURRENTLY`, i.e. rafraîchissement sans verrou bloquant les lectures) ;
- un index sur `(ticker, fiscal_year)` — pattern d'accès de Query A ;
- un index sur `(sector_id, fiscal_year)` — pattern d'accès de Query B.

`v_sector_rankings`, `v_trailing_trends` et `v_screening_base` ont été redéfinies (`CREATE OR REPLACE VIEW`) pour lire `mv_company_financial_profile` au lieu de `v_company_financial_profile` : le gain se propage à toute la chaîne de vues, pas seulement à la requête de démonstration. `load_to_postgres.py` appelle désormais `REFRESH MATERIALIZED VIEW CONCURRENTLY` en fin de chargement (`refresh_materialized_views()`).

**Compromis assumé** : la vue matérialisée peut être périmée entre deux chargements. Acceptable ici car les lectures (screening, rankings, consultation) sont bien plus fréquentes que les chargements (une fois par run de fetch/normalize/load), et le rafraîchissement est automatisé, pas manuel.

## Résultat mesuré (après optimisation)

**Query A : 0,171 ms** (contre 332,75 ms) — **facteur ~1950x**.
```
Sort (actual time=0.100..0.101 rows=19 loops=1)
  ->  Bitmap Heap Scan on mv_company_financial_profile (actual time=0.063..0.065 rows=19 loops=1)
        Recheck Cond: (ticker = 'AAPL'::text)
        ->  Bitmap Index Scan on idx_mv_cfp_ticker_year (actual time=0.052..0.052 rows=19 loops=1)
Planning Time: 5.307 ms
Execution Time: 0.171 ms
```
Plan simplifié à l'extrême : un `Bitmap Index Scan` direct sur `(ticker, fiscal_year)` remonte exactement les 19 lignes nécessaires, plus de recalcul des fonctions fenêtrées sur les 714 lignes à chaque lecture.

**Query B : 0,854 ms** (contre 12,25 ms) — **facteur ~14x**, alors que cette requête n'était pas identifiée comme un problème au départ : bénéfice indirect du passage à `mv_company_financial_profile` pour toute la chaîne `v_sector_rankings`.

## Validation de non-régression

Après le refactor, le moteur de screening (étape 6) a été ré-exécuté en entier : **résultats strictement identiques** à l'exécution pré-optimisation (`distressed` 3/714, `pe_growth` 54/714, `pe_value` 63/714, `quality` 107/714). L'optimisation change la vitesse, pas les données.
