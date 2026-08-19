-- Optimisation (docs/00_project_charter.md, section 9 étape 8 : "EXPLAIN
-- ANALYZE, index ciblés, mesure avant/après"). Preuves chiffrées complètes
-- (EXPLAIN ANALYZE avant/après, méthodologie) : sql/optimization/README.md.
--
-- CONSTAT (mesuré, pas supposé) : `SELECT * FROM v_company_financial_profile
-- WHERE ticker = 'AAPL'` prenait 332,75 ms alors que la requête ne renvoie
-- que 19 lignes sur 714. Cause identifiée dans le plan EXPLAIN ANALYZE :
-- `v_company_financial_profile` empile 5 vues (v_growth, v_margins,
-- v_returns, v_leverage, v_cash_flow), chacune calculant des fonctions
-- fenêtrées (LAG) PARTITION BY company_id sur les 714 lignes complètes AVANT
-- que le filtre `ticker = 'AAPL'` (appliqué via une jointure à `companies`,
-- plusieurs niveaux plus loin) ne puisse s'appliquer. Le planificateur ne
-- peut pas pousser ce filtre à travers les frontières de partition d'une
-- fonction fenêtrée définie sur une autre colonne (company_id) — ce n'est
-- pas un index manquant, c'est un recalcul évitable de tout le dataset à
-- chaque requête.
--
-- SOLUTION : matérialiser le résultat de v_company_financial_profile (714
-- lignes, recalculées une seule fois au chargement, pas à chaque lecture).
-- Les vues qui en dépendent (v_sector_rankings, v_trailing_trends,
-- v_screening_base) sont redéfinies sur la version matérialisée : le gain se
-- propage à toute la chaîne, pas seulement à cette requête de démonstration.
--
-- Coût de la matérialisation : la vue doit être rafraîchie après chaque
-- chargement (financial_intelligence.data.load_to_postgres appelle
-- désormais REFRESH MATERIALIZED VIEW en fin de run) — compromis standard
-- lecture-rapide / écriture-à-rafraîchir, adapté ici car les lectures
-- (screening, rankings, consultation) sont bien plus fréquentes que les
-- chargements (une fois par run de fetch/normalize/load).

BEGIN;

CREATE MATERIALIZED VIEW mv_company_financial_profile AS
SELECT * FROM v_company_financial_profile;

-- Index unique requis pour permettre REFRESH MATERIALIZED VIEW CONCURRENTLY
-- (rafraîchissement sans verrou bloquant les lectures en cours).
CREATE UNIQUE INDEX idx_mv_cfp_fiscal_period ON mv_company_financial_profile (fiscal_period_id);

-- Index ciblés sur les deux patterns d'accès réels identifiés :
-- (1) historique d'une entreprise (Query A : "WHERE ticker = 'AAPL'")
CREATE INDEX idx_mv_cfp_ticker_year ON mv_company_financial_profile (ticker, fiscal_year);
-- (2) classement sectoriel par exercice (Query B, déjà rapide sans cet index
-- grâce au filtre fiscal_year poussé dans fiscal_periods, mais désormais
-- appliqué sur une table 44x plus petite que le recalcul complet des CTE)
CREATE INDEX idx_mv_cfp_sector_year ON mv_company_financial_profile (sector_id, fiscal_year);

COMMIT;
