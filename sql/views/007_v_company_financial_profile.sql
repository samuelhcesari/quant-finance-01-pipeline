-- v_company_financial_profile — consolide en une seule ligne (entreprise x
-- exercice) les métriques des 5 vues de ratios (étape 4), via des CTE
-- imbriquées (docs/00_project_charter.md, section 3 : "CTE imbriquées, window
-- functions"). Sert de base commune aux rankings sectoriels (étape 5) et au
-- moteur de screening (étape 6) — évite que chaque vue en aval réécrive ses
-- propres jointures vers les 6 vues de ratios.

CREATE VIEW v_company_financial_profile AS
WITH g AS (
    SELECT * FROM v_growth
),
m AS (
    SELECT * FROM v_margins
),
r AS (
    SELECT * FROM v_returns
),
l AS (
    SELECT * FROM v_leverage
),
cf AS (
    SELECT * FROM v_cash_flow
)
SELECT
    c.company_id,
    c.ticker,
    c.name AS company_name,
    c.sector_id,
    s.name AS sector_name,
    g.fiscal_year,
    g.fiscal_period_id,

    g.revenue,
    g.revenue_growth,
    g.ebitda_growth,
    g.eps_diluted_growth,
    g.fcf_growth,

    m.gross_margin,
    m.ebitda_margin,
    m.ebit_margin,
    m.net_margin,

    r.roe,
    r.roa,
    r.roic,
    r.effective_tax_rate,

    l.total_debt,
    l.net_debt,
    l.net_debt_to_ebitda,
    l.debt_to_equity,
    l.interest_coverage,

    cf.fcf,
    cf.fcf_margin,
    cf.fcf_conversion
FROM g
JOIN m USING (company_id, fiscal_period_id, fiscal_year)
JOIN r USING (company_id, fiscal_period_id, fiscal_year)
JOIN l USING (company_id, fiscal_period_id, fiscal_year)
JOIN cf USING (company_id, fiscal_period_id, fiscal_year)
JOIN companies c ON c.company_id = g.company_id
JOIN sectors s ON s.sector_id = c.sector_id;
