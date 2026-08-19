-- v_leverage — effet de levier (docs/00_project_charter.md, section 5) :
-- Net Debt/EBITDA, Debt/Equity, Interest Coverage = EBIT / Interest Expense.
--
-- Total Debt = short_term_debt + long_term_debt, NULL si les deux composantes
-- sont NULL (même traitement qu'en v_returns, répété ici volontairement pour
-- que cette vue reste testable isolément sans dépendre d'une autre vue).
-- Interest Coverage non calculé (NULL) quand interest_expense = 0 (pas de
-- dette portant intérêt identifiée -> ratio non défini, pas "infini" affiché
-- comme s'il s'agissait d'une vraie mesure).

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
