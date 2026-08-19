-- v_screening_base — regroupe profil financier, tendances 3 ans et
-- valorisation (v_valuation, ~5 dernières années). LEFT JOIN sur la
-- valorisation pour ne pas perdre la ligne quand elle est absente.
-- Aucun seuil ici : configs/screening/*.yaml + screening_engine.py.
-- Source de `p` : mv_company_financial_profile.

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
