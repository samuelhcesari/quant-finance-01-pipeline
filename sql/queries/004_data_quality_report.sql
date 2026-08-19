-- Rapport de qualité de données : fill rate, identités comptables, outliers,
-- doublons. S'appuie sur v_data_quality_flags (sql/views/013_...sql).

-- 1. Taux de remplissage par champ, par table (pas de PIVOT dynamique en SQL
-- standard -> UNION ALL explicite).
SELECT 'income_statements' AS table_name, 'revenue' AS field, COUNT(revenue) AS filled, COUNT(*) AS total, ROUND(100.0*COUNT(revenue)/COUNT(*),1) AS pct FROM income_statements
UNION ALL SELECT 'income_statements', 'ebit', COUNT(ebit), COUNT(*), ROUND(100.0*COUNT(ebit)/COUNT(*),1) FROM income_statements
UNION ALL SELECT 'income_statements', 'ebitda', COUNT(ebitda), COUNT(*), ROUND(100.0*COUNT(ebitda)/COUNT(*),1) FROM income_statements
UNION ALL SELECT 'income_statements', 'net_income', COUNT(net_income), COUNT(*), ROUND(100.0*COUNT(net_income)/COUNT(*),1) FROM income_statements
UNION ALL SELECT 'balance_sheets', 'total_assets', COUNT(total_assets), COUNT(*), ROUND(100.0*COUNT(total_assets)/COUNT(*),1) FROM balance_sheets
UNION ALL SELECT 'balance_sheets', 'total_equity', COUNT(total_equity), COUNT(*), ROUND(100.0*COUNT(total_equity)/COUNT(*),1) FROM balance_sheets
UNION ALL SELECT 'balance_sheets', 'total_liabilities', COUNT(total_liabilities), COUNT(*), ROUND(100.0*COUNT(total_liabilities)/COUNT(*),1) FROM balance_sheets
UNION ALL SELECT 'balance_sheets', 'short_term_debt', COUNT(short_term_debt), COUNT(*), ROUND(100.0*COUNT(short_term_debt)/COUNT(*),1) FROM balance_sheets
UNION ALL SELECT 'cash_flow_statements', 'cfo', COUNT(cfo), COUNT(*), ROUND(100.0*COUNT(cfo)/COUNT(*),1) FROM cash_flow_statements
UNION ALL SELECT 'cash_flow_statements', 'dividends_paid', COUNT(dividends_paid), COUNT(*), ROUND(100.0*COUNT(dividends_paid)/COUNT(*),1) FROM cash_flow_statements
ORDER BY table_name, field;

-- 2. Identité comptable : combien de lignes sont réellement testables (les
-- trois champs renseignés), et combien de celles-là échouent la tolérance 1%.
SELECT
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE accounting_identity_ok IS NOT NULL) AS testable_rows,
    COUNT(*) FILTER (WHERE accounting_identity_ok = FALSE) AS violations,
    ROUND(100.0 * COUNT(*) FILTER (WHERE accounting_identity_ok = FALSE)
        / NULLIF(COUNT(*) FILTER (WHERE accounting_identity_ok IS NOT NULL), 0), 1) AS violation_pct_of_testable
FROM v_data_quality_flags;

-- 3. Outliers statistiques (|z-score| > 3, intra-secteur) par métrique.
SELECT
    COUNT(*) FILTER (WHERE revenue_growth_outlier) AS revenue_growth_outliers,
    COUNT(*) FILTER (WHERE ebitda_margin_outlier) AS ebitda_margin_outliers,
    COUNT(*) FILTER (WHERE leverage_outlier) AS leverage_outliers,
    COUNT(*) FILTER (WHERE revenue_growth_outlier OR ebitda_margin_outlier OR leverage_outlier) AS rows_with_any_outlier,
    COUNT(*) AS total_rows
FROM v_data_quality_flags;

-- 4. Doublons (company_id, fiscal_year) — doit renvoyer 0 lignes (déjà
-- empêché par la contrainte UNIQUE de fiscal_periods).
SELECT company_id, fiscal_year, COUNT(*)
FROM fiscal_periods
GROUP BY company_id, fiscal_year
HAVING COUNT(*) > 1;

-- 5. Restatements/révisions de filings : hors périmètre. Le loader retient
-- le filing le plus ancien par exercice ("as originally reported").
