-- v_data_quality_flags — couche de qualité de données consolidée, réponse
-- directe à un retour de relecture externe pointant que coverage/missingness/
-- accounting identities/outliers étaient épars dans docs/data_sources.md
-- (texte libre) plutôt qu'interrogeables en SQL.
--
-- Détection d'outliers par z-score INTRA-SECTEUR (AVG/STDDEV en window
-- function, PARTITION BY sector_id) : comparer un ratio à la moyenne globale
-- toutes industries confondues pénaliserait injustement un secteur dont les
-- normes diffèrent structurellement (ex. marge EBITDA pharma vs construction,
-- déjà observé très différent dans sql/queries/001_...sql). Seuil |z| > 3,
-- convention statistique standard pour un outlier "extrême" (pas juste
-- "élevé") — pas un jugement de valeur sur l'entreprise, juste un signal
-- statistique à vérifier avant d'utiliser la ligne dans une analyse agrégée.

CREATE VIEW v_data_quality_flags AS
WITH stats AS (
    SELECT
        p.*,
        AVG(p.revenue_growth) OVER (PARTITION BY p.sector_id) AS sector_avg_growth,
        STDDEV(p.revenue_growth) OVER (PARTITION BY p.sector_id) AS sector_stddev_growth,
        AVG(p.ebitda_margin) OVER (PARTITION BY p.sector_id) AS sector_avg_margin,
        STDDEV(p.ebitda_margin) OVER (PARTITION BY p.sector_id) AS sector_stddev_margin,
        AVG(p.net_debt_to_ebitda) OVER (PARTITION BY p.sector_id) AS sector_avg_leverage,
        STDDEV(p.net_debt_to_ebitda) OVER (PARTITION BY p.sector_id) AS sector_stddev_leverage,
        b.total_assets,
        b.total_liabilities,
        b.total_equity
    FROM mv_company_financial_profile p
    JOIN balance_sheets b ON b.fiscal_period_id = p.fiscal_period_id
)
SELECT
    company_id,
    ticker,
    sector_name,
    fiscal_year,
    fiscal_period_id,

    -- Identité comptable : Actif = Passif + Capitaux propres, tolérance 1%.
    total_assets,
    total_liabilities,
    total_equity,
    CASE
        WHEN total_assets IS NULL OR total_liabilities IS NULL OR total_equity IS NULL THEN NULL
        WHEN total_assets = 0 THEN NULL
        ELSE ABS(total_assets - (total_liabilities + total_equity)) <= 0.01 * total_assets
    END AS accounting_identity_ok,

    -- Outliers intra-secteur (|z-score| > 3)
    revenue_growth,
    CASE WHEN sector_stddev_growth > 0
         THEN ABS(revenue_growth - sector_avg_growth) / sector_stddev_growth > 3
         ELSE FALSE
    END AS revenue_growth_outlier,

    ebitda_margin,
    CASE WHEN sector_stddev_margin > 0
         THEN ABS(ebitda_margin - sector_avg_margin) / sector_stddev_margin > 3
         ELSE FALSE
    END AS ebitda_margin_outlier,

    net_debt_to_ebitda,
    CASE WHEN sector_stddev_leverage > 0
         THEN ABS(net_debt_to_ebitda - sector_avg_leverage) / sector_stddev_leverage > 3
         ELSE FALSE
    END AS leverage_outlier
FROM stats;
