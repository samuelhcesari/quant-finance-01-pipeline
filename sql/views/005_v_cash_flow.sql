-- v_cash_flow — génération de cash (docs/00_project_charter.md, section 5) :
-- FCF = CFO - CapEx, FCF margin = FCF / Revenue, FCF conversion = FCF / EBITDA.
--
-- capex est stocké tel que rapporté par SEC EDGAR sous le tag
-- PaymentsToAcquirePropertyPlantAndEquipment, qui est une sortie de cash
-- reportée en valeur POSITIVE dans XBRL (contrairement à certains tableaux de
-- flux de trésorerie qui l'affichent en négatif) -> FCF = CFO - CapEx est donc
-- correct tel quel, pas CFO + CapEx.

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
