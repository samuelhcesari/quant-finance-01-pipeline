-- v_returns — rentabilité du capital (docs/00_project_charter.md, section 5) :
-- ROE = Net Income / Avg Shareholders Equity
-- ROA = Net Income / Avg Total Assets
-- ROIC = NOPAT / Invested Capital, avec NOPAT = EBIT x (1 - taux d'imposition
-- effectif) et Invested Capital = Total Debt + Equity - Cash.
--
-- "Avg" (moyenne début/fin d'exercice) nécessite le bilan de l'exercice
-- précédent -> LAG() sur total_equity/total_assets, exercice réellement
-- consécutif exigé (comme v_growth) sinon la moyenne serait calculée sur des
-- bilans non adjacents. Si l'exercice précédent n'existe pas ou n'est pas
-- consécutif, on utilise le solde de fin d'exercice seul (moyenne dégradée)
-- plutôt que de renvoyer NULL, ce qui priverait tout le premier exercice
-- disponible de toute mesure de rentabilité.
--
-- Total Debt = short_term_debt + long_term_debt : NULL si les DEUX composantes
-- sont NULL (dette réellement inconnue), sinon somme des composantes connues
-- (traite l'absence de l'une des deux comme 0, pas comme un blocage total).
--
-- Taux d'imposition effectif = tax_expense / pretax_income, NULL si
-- pretax_income <= 0 (un taux d'imposition sur une perte avant impôt n'a pas
-- de sens économique standard).

CREATE VIEW v_returns AS
WITH base AS (
    SELECT
        fp.company_id,
        fp.fiscal_period_id,
        fp.fiscal_year,
        i.net_income,
        i.ebit,
        i.tax_expense,
        i.pretax_income,
        b.total_equity,
        b.total_assets,
        b.cash_and_equivalents,
        CASE
            WHEN b.short_term_debt IS NULL AND b.long_term_debt IS NULL THEN NULL
            ELSE COALESCE(b.short_term_debt, 0) + COALESCE(b.long_term_debt, 0)
        END AS total_debt
    FROM fiscal_periods fp
    JOIN income_statements i ON i.fiscal_period_id = fp.fiscal_period_id
    JOIN balance_sheets b ON b.fiscal_period_id = fp.fiscal_period_id
    WHERE fp.period_type = 'FY'
),
with_lags AS (
    SELECT
        *,
        LAG(fiscal_year) OVER w AS fiscal_year_prior,
        LAG(total_equity) OVER w AS total_equity_prior,
        LAG(total_assets) OVER w AS total_assets_prior
    FROM base
    WINDOW w AS (PARTITION BY company_id ORDER BY fiscal_year)
)
SELECT
    company_id,
    fiscal_period_id,
    fiscal_year,

    CASE WHEN fiscal_year_prior = fiscal_year - 1 AND total_equity_prior IS NOT NULL
         THEN (total_equity + total_equity_prior) / 2.0
         ELSE total_equity
    END AS avg_equity_basis,
    net_income / NULLIF(
        CASE WHEN fiscal_year_prior = fiscal_year - 1 AND total_equity_prior IS NOT NULL
             THEN (total_equity + total_equity_prior) / 2.0
             ELSE total_equity
        END, 0
    ) AS roe,

    CASE WHEN fiscal_year_prior = fiscal_year - 1 AND total_assets_prior IS NOT NULL
         THEN (total_assets + total_assets_prior) / 2.0
         ELSE total_assets
    END AS avg_assets_basis,
    net_income / NULLIF(
        CASE WHEN fiscal_year_prior = fiscal_year - 1 AND total_assets_prior IS NOT NULL
             THEN (total_assets + total_assets_prior) / 2.0
             ELSE total_assets
        END, 0
    ) AS roa,

    CASE WHEN pretax_income > 0 THEN tax_expense / pretax_income END AS effective_tax_rate,
    CASE WHEN pretax_income > 0 THEN ebit * (1 - tax_expense / pretax_income) END AS nopat,
    (total_debt + total_equity - cash_and_equivalents) AS invested_capital,
    CASE
        WHEN pretax_income > 0 AND (total_debt + total_equity - cash_and_equivalents) <> 0
        THEN (ebit * (1 - tax_expense / pretax_income))
             / NULLIF(total_debt + total_equity - cash_and_equivalents, 0)
    END AS roic
FROM with_lags;
