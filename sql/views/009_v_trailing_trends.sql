-- v_trailing_trends — moyenne mobile 3 ans (ROWS BETWEEN 2 PRECEDING AND
-- CURRENT ROW), calculée sur autant d'exercices disponibles (1 à 3) ;
-- years_available_for_avg expose la taille réelle de la fenêtre.
-- roic_3y_ago = LAG(roic, 3). Source : mv_company_financial_profile.

CREATE OR REPLACE VIEW v_trailing_trends AS
SELECT
    company_id,
    ticker,
    fiscal_year,

    revenue_growth,
    AVG(revenue_growth) OVER w AS revenue_growth_3y_avg,

    ebitda_margin,
    AVG(ebitda_margin) OVER w AS ebitda_margin_3y_avg,

    roic,
    LAG(roic, 3) OVER (PARTITION BY company_id ORDER BY fiscal_year) AS roic_3y_ago,

    COUNT(*) OVER w AS years_available_for_avg
FROM mv_company_financial_profile
WINDOW w AS (PARTITION BY company_id ORDER BY fiscal_year ROWS BETWEEN 2 PRECEDING AND CURRENT ROW);
