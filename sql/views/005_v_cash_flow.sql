-- v_cash_flow — FCF = CFO - CapEx, FCF margin, FCF conversion = FCF / EBITDA.
-- capex vient du tag XBRL PaymentsToAcquirePropertyPlantAndEquipment, reporté
-- en valeur positive -> CFO - CapEx, pas CFO + CapEx.

CREATE VIEW v_cash_flow AS
SELECT
    fp.company_id,
    fp.fiscal_period_id,
    fp.fiscal_year,
    cf.cfo,
    cf.capex,
    (cf.cfo - cf.capex) AS fcf,
    (cf.cfo - cf.capex) / NULLIF(i.revenue, 0) AS fcf_margin,
    (cf.cfo - cf.capex) / NULLIF(i.ebitda, 0) AS fcf_conversion
FROM fiscal_periods fp
JOIN cash_flow_statements cf ON cf.fiscal_period_id = fp.fiscal_period_id
JOIN income_statements i ON i.fiscal_period_id = fp.fiscal_period_id
WHERE fp.period_type = 'FY';
