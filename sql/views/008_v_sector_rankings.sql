-- v_sector_rankings — RANK()/PERCENT_RANK() intra-secteur par exercice.
-- NULLS LAST partout. net_debt_to_ebitda classé ASC, le reste DESC.
-- sector_peer_count expose la taille du groupe de comparaison.
-- Source : mv_company_financial_profile (vue matérialisée, sql/optimization/001_...sql).

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
