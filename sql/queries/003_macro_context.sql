-- Contexte de crédit au moment des transactions M&A, et corrélation entre
-- multiples et spread high-yield.
--
-- BAMLH0A0HYM2 (spread crédit high-yield) ne couvre que 2023-08-21 ->
-- aujourd'hui dans les données récupérées (786 observations), pas tout
-- l'historique FRED. Le spread HY est donc NULL pour Horizon Therapeutics
-- (2022-12-12) et Seagen (2023-03-13), antérieures à cette fenêtre.

-- 1. Contexte macro à la date d'annonce (dernière observation <= announce_date).
WITH macro_at_announce AS (
    SELECT DISTINCT ON (tx.transaction_id, mi.series_code)
        tx.transaction_id, mi.series_code, mi.value, mi.obs_date
    FROM transactions tx
    JOIN macro_indicators mi ON mi.obs_date <= tx.announce_date
    ORDER BY tx.transaction_id, mi.series_code, mi.obs_date DESC
)
SELECT
    t.name AS target_name,
    tx.announce_date,
    MAX(CASE WHEN m.series_code = 'DGS10' THEN m.value END) AS treasury_10y_pct,
    MAX(CASE WHEN m.series_code = 'BAMLH0A0HYM2' THEN m.value END) AS hy_credit_spread_pct,
    MAX(CASE WHEN m.series_code = 'FEDFUNDS' THEN m.value END) AS fed_funds_pct
FROM transactions tx
JOIN companies t ON t.company_id = tx.target_company_id
LEFT JOIN macro_at_announce m ON m.transaction_id = tx.transaction_id
GROUP BY t.name, tx.announce_date, tx.transaction_id
ORDER BY tx.announce_date;

-- 2. Les multiples de valorisation de l'univers réagissent-ils au spread de
-- crédit high-yield ? Moyenne d'EV/EBITDA par exercice fiscal (toutes
-- entreprises, tous secteurs) vs spread HY à la date de clôture la plus
-- proche de chaque exercice.
WITH avg_multiple_by_year AS (
    SELECT fiscal_year, AVG(ev_to_ebitda) AS avg_ev_ebitda, COUNT(*) AS n
    FROM v_screening_base
    WHERE ev_to_ebitda IS NOT NULL AND ev_to_ebitda BETWEEN 0 AND 100
    GROUP BY fiscal_year
),
spread_by_year AS (
    SELECT DISTINCT ON (fy.fiscal_year)
        fy.fiscal_year, mi.value AS hy_spread_pct, mi.obs_date
    FROM avg_multiple_by_year fy
    JOIN macro_indicators mi
        ON mi.series_code = 'BAMLH0A0HYM2'
        AND mi.obs_date <= make_date(fy.fiscal_year, 12, 31)
    ORDER BY fy.fiscal_year, mi.obs_date DESC
)
SELECT
    m.fiscal_year, m.n AS companies, ROUND(m.avg_ev_ebitda::numeric, 1) AS avg_ev_ebitda, s.hy_spread_pct
FROM avg_multiple_by_year m
JOIN spread_by_year s USING (fiscal_year)
ORDER BY m.fiscal_year;

-- Corrélation entre les deux séries ci-dessus
WITH avg_multiple_by_year AS (
    SELECT fiscal_year, AVG(ev_to_ebitda) AS avg_ev_ebitda
    FROM v_screening_base
    WHERE ev_to_ebitda IS NOT NULL AND ev_to_ebitda BETWEEN 0 AND 100
    GROUP BY fiscal_year
),
spread_by_year AS (
    SELECT DISTINCT ON (fy.fiscal_year)
        fy.fiscal_year, mi.value AS hy_spread_pct
    FROM avg_multiple_by_year fy
    JOIN macro_indicators mi
        ON mi.series_code = 'BAMLH0A0HYM2'
        AND mi.obs_date <= make_date(fy.fiscal_year, 12, 31)
    ORDER BY fy.fiscal_year, mi.obs_date DESC
)
SELECT
    COUNT(*) AS n_years,
    ROUND(CORR(m.avg_ev_ebitda, s.hy_spread_pct)::numeric, 3) AS corr_avg_multiple_vs_hy_spread
FROM avg_multiple_by_year m
JOIN spread_by_year s USING (fiscal_year);
