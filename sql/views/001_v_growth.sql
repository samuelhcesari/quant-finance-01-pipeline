-- v_growth — growth_t = (X_t / X_{t-1}) - 1 pour Revenue, EBITDA, EPS, FCF.
-- NULL si la valeur précédente est <= 0 (base négative -> % trompeur) ; flag
-- *_prior_negative pour ces cas. LAG() retenu seulement entre exercices
-- vraiment consécutifs (fiscal_year_prior = fiscal_year - 1).

CREATE VIEW v_growth AS
WITH base AS (
    SELECT
        fp.company_id,
        fp.fiscal_period_id,
        fp.fiscal_year,
        i.revenue,
        i.ebitda,
        i.eps_diluted,
        (cf.cfo - cf.capex) AS fcf
    FROM fiscal_periods fp
    JOIN income_statements i ON i.fiscal_period_id = fp.fiscal_period_id
    JOIN cash_flow_statements cf ON cf.fiscal_period_id = fp.fiscal_period_id
    WHERE fp.period_type = 'FY'
),
with_lags AS (
    SELECT
        company_id,
        fiscal_period_id,
        fiscal_year,
        revenue,
        LAG(revenue) OVER w AS revenue_prior,
        LAG(fiscal_year) OVER w AS fiscal_year_prior,
        ebitda,
        LAG(ebitda) OVER w AS ebitda_prior,
        eps_diluted,
        LAG(eps_diluted) OVER w AS eps_diluted_prior,
        fcf,
        LAG(fcf) OVER w AS fcf_prior
    FROM base
    WINDOW w AS (PARTITION BY company_id ORDER BY fiscal_year)
)
SELECT
    company_id,
    fiscal_period_id,
    fiscal_year,
    (fiscal_year_prior = fiscal_year - 1) AS consecutive_year,

    revenue, revenue_prior,
    (revenue_prior < 0) AS revenue_prior_negative,
    CASE WHEN fiscal_year_prior = fiscal_year - 1 AND revenue_prior > 0
         THEN revenue / revenue_prior - 1 END AS revenue_growth,

    ebitda, ebitda_prior,
    (ebitda_prior < 0) AS ebitda_prior_negative,
    CASE WHEN fiscal_year_prior = fiscal_year - 1 AND ebitda_prior > 0
         THEN ebitda / ebitda_prior - 1 END AS ebitda_growth,

    eps_diluted, eps_diluted_prior,
    (eps_diluted_prior < 0) AS eps_diluted_prior_negative,
    CASE WHEN fiscal_year_prior = fiscal_year - 1 AND eps_diluted_prior > 0
         THEN eps_diluted / eps_diluted_prior - 1 END AS eps_diluted_growth,

    fcf, fcf_prior,
    (fcf_prior < 0) AS fcf_prior_negative,
    CASE WHEN fiscal_year_prior = fiscal_year - 1 AND fcf_prior > 0
         THEN fcf / fcf_prior - 1 END AS fcf_growth
FROM with_lags;
