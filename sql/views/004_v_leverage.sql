-- v_leverage — Net Debt/EBITDA, Debt/Equity, Interest Coverage = EBIT /
-- Interest Expense. Total Debt NULL seulement si st_debt et lt_debt sont NULL
-- tous deux. Interest Coverage NULL si interest_expense = 0.

CREATE VIEW v_leverage AS
SELECT
    fp.company_id,
    fp.fiscal_period_id,
    fp.fiscal_year,
    CASE
        WHEN b.short_term_debt IS NULL AND b.long_term_debt IS NULL THEN NULL
        ELSE COALESCE(b.short_term_debt, 0) + COALESCE(b.long_term_debt, 0)
    END AS total_debt,
    (
        CASE
            WHEN b.short_term_debt IS NULL AND b.long_term_debt IS NULL THEN NULL
            ELSE COALESCE(b.short_term_debt, 0) + COALESCE(b.long_term_debt, 0)
        END - b.cash_and_equivalents
    ) AS net_debt,
    (
        CASE
            WHEN b.short_term_debt IS NULL AND b.long_term_debt IS NULL THEN NULL
            ELSE COALESCE(b.short_term_debt, 0) + COALESCE(b.long_term_debt, 0)
        END - b.cash_and_equivalents
    ) / NULLIF(i.ebitda, 0) AS net_debt_to_ebitda,
    CASE
        WHEN b.short_term_debt IS NULL AND b.long_term_debt IS NULL THEN NULL
        ELSE COALESCE(b.short_term_debt, 0) + COALESCE(b.long_term_debt, 0)
    END / NULLIF(b.total_equity, 0) AS debt_to_equity,
    CASE WHEN i.interest_expense > 0 THEN i.ebit / i.interest_expense END AS interest_coverage
FROM fiscal_periods fp
JOIN income_statements i ON i.fiscal_period_id = fp.fiscal_period_id
JOIN balance_sheets b ON b.fiscal_period_id = fp.fiscal_period_id
WHERE fp.period_type = 'FY';
