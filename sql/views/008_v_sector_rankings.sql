-- v_sector_rankings — classement intra-secteur par exercice (docs/00_project_
-- charter.md, section 3 : "window functions (LAG/LEAD/RANK/ROW_NUMBER)").
--
-- RANK() (pas ROW_NUMBER()) : les ex-aequo doivent recevoir le même rang,
-- avec un saut dans la numérotation qui suit (comportement RANK standard),
-- plutôt qu'un ordre arbitraire entre valeurs strictement égales.
-- NULLS LAST partout : une métrique manquante ne doit ni gagner ni fausser le
-- classement en se retrouvant arbitrairement en tête.
-- net_debt_to_ebitda classé ASC (un levier plus faible est "meilleur"),
-- toutes les autres métriques DESC.
-- sector_peer_count expose la taille réelle du groupe de comparaison : un
-- rang 2 sur 3 pairs n'a pas la même signification qu'un rang 2 sur 14.
--
-- Source : mv_company_financial_profile (vue matérialisée, pas la vue
-- v_company_financial_profile) depuis l'étape d'optimisation (sql/
-- optimization/001_...sql) — évite de recalculer LAG/marges/ROIC sur les 714
-- lignes à chaque lecture de ce classement.

CREATE OR REPLACE VIEW v_sector_rankings AS
SELECT
    company_id,
    ticker,
    company_name,
    sector_id,
    sector_name,
    fiscal_year,

    revenue_growth,
    RANK() OVER (PARTITION BY sector_id, fiscal_year ORDER BY revenue_growth DESC NULLS LAST) AS growth_rank_in_sector,

    ebitda_margin,
    RANK() OVER (PARTITION BY sector_id, fiscal_year ORDER BY ebitda_margin DESC NULLS LAST) AS margin_rank_in_sector,

    roic,
    RANK() OVER (PARTITION BY sector_id, fiscal_year ORDER BY roic DESC NULLS LAST) AS roic_rank_in_sector,
    PERCENT_RANK() OVER (PARTITION BY sector_id, fiscal_year ORDER BY roic) AS roic_percentile_in_sector,

    net_debt_to_ebitda,
    RANK() OVER (PARTITION BY sector_id, fiscal_year ORDER BY net_debt_to_ebitda ASC NULLS LAST) AS leverage_rank_in_sector,

    COUNT(*) OVER (PARTITION BY sector_id, fiscal_year) AS sector_peer_count
FROM mv_company_financial_profile;
