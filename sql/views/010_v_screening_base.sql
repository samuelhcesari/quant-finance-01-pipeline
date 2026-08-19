-- v_screening_base — regroupe toutes les métriques nécessaires au moteur de
-- screening (étape 6) en une seule vue : profil financier de base (étape 4/5),
-- tendances 3 ans (v_trailing_trends) et multiples de valorisation
-- (v_valuation, disponibles seulement sur les ~5 dernières années — cf.
-- limitation documentée dans docs/data_sources.md). LEFT JOIN volontaire :
-- l'absence de valorisation ne doit pas faire disparaître une ligne du
-- screening, seulement laisser ses colonnes de valorisation à NULL.
--
-- Les SEUILS de screening ne sont PAS dans cette vue (charte section 4 :
-- "seuils paramétrables via configuration externe (YAML), pas en dur dans le
-- SQL") — cette vue ne fait que mettre les métriques à disposition ; les
-- seuils vivent dans configs/screening/*.yaml et sont appliqués par
-- src/financial_intelligence/screening/engine.py.
--
-- Source de `p` : mv_company_financial_profile (vue matérialisée) depuis
-- l'étape d'optimisation (sql/optimization/001_...sql).

CREATE OR REPLACE VIEW v_screening_base AS
SELECT
    p.company_id,
    p.ticker,
    p.company_name,
    p.sector_id,
    p.sector_name,
    p.fiscal_year,
    p.fiscal_period_id,

    p.revenue_growth,
    p.ebitda_margin,
    p.net_margin,
    p.roic,
    p.roe,
    p.roa,
    p.net_debt_to_ebitda,
    p.debt_to_equity,
    p.interest_coverage,
    p.fcf,
    p.fcf_margin,
    p.fcf_conversion,

    t.revenue_growth_3y_avg,
    t.ebitda_margin_3y_avg,
    t.years_available_for_avg,

    v.ev_to_ebitda,
    v.price_to_earnings,
    v.fcf_yield
FROM mv_company_financial_profile p
LEFT JOIN v_trailing_trends t USING (company_id, fiscal_year)
LEFT JOIN v_valuation v USING (company_id, fiscal_period_id, fiscal_year);
