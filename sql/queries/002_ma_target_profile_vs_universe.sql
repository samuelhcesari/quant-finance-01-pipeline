-- Profil financier des cibles M&A vs le reste de l'univers, par percentile
-- sectoriel. N=4 cibles avec financials disponibles (Splunk et Lhoist North
-- America exclues) — échantillon illustratif, pas un test statistique.

WITH target_ratios AS (
    SELECT
        tx.transaction_id,
        t.name AS target_name,
        ts.name AS target_sector,
        tx.announce_date,
        tf.target_ebitda_ttm / NULLIF(tf.target_revenue_ttm, 0) AS target_ebitda_margin,
        tf.target_net_debt / NULLIF(tf.target_ebitda_ttm, 0) AS target_net_debt_to_ebitda
    FROM transactions tx
    JOIN companies t ON t.company_id = tx.target_company_id
    LEFT JOIN sectors ts ON ts.sector_id = t.sector_id
    JOIN transaction_financials tf ON tf.transaction_id = tx.transaction_id
    WHERE tf.target_revenue_ttm IS NOT NULL
),
universe_by_sector AS (
    SELECT sector_name, ebitda_margin, net_debt_to_ebitda
    FROM v_screening_base
    WHERE ebitda_margin IS NOT NULL
)
SELECT
    tr.target_name,
    tr.target_sector,
    ROUND(tr.target_ebitda_margin::numeric, 3) AS target_ebitda_margin,
    ROUND((
        SELECT PERCENT_RANK() OVER (ORDER BY val)
        FROM (
            SELECT ebitda_margin AS val FROM universe_by_sector u WHERE u.sector_name = tr.target_sector
            UNION ALL SELECT tr.target_ebitda_margin
        ) x
        ORDER BY val = tr.target_ebitda_margin DESC, val
        LIMIT 1
    )::numeric, 2) AS ebitda_margin_percentile_in_sector,
    ROUND(tr.target_net_debt_to_ebitda::numeric, 2) AS target_net_debt_to_ebitda,
    (SELECT COUNT(*) FROM universe_by_sector u WHERE u.sector_name = tr.target_sector) AS sector_peer_count
FROM target_ratios tr
ORDER BY tr.announce_date;
