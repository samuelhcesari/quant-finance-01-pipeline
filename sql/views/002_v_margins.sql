-- v_margins — Gross/EBITDA/EBIT/Net margin = X / Revenue. NULLIF(revenue, 0)
-- évite la division par zéro ; un revenue négatif n'est pas filtré.

CREATE VIEW v_margins AS
SELECT
    fp.company_id,
    fp.fiscal_period_id,
    fp.fiscal_year,
    i.revenue,
    i.gross_profit / NULLIF(i.revenue, 0) AS gross_margin,
    i.ebitda / NULLIF(i.revenue, 0) AS ebitda_margin,
    i.ebit / NULLIF(i.revenue, 0) AS ebit_margin,
    i.net_income / NULLIF(i.revenue, 0) AS net_margin
FROM fiscal_periods fp
JOIN income_statements i ON i.fiscal_period_id = fp.fiscal_period_id
WHERE fp.period_type = 'FY';
