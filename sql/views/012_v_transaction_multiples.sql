-- v_transaction_multiples — multiples payés lors des transactions M&A (docs/
-- 00_project_charter.md, section 5 : EV/EBITDA, EV/Revenue) — calculés à
-- partir de transaction_financials, alimenté quand les états financiers de la
-- cible ont pu être extraits (cf. docs/data_sources.md : Splunk et Lhoist
-- North America n'ont pas de transaction_financials chargé — LEFT JOIN
-- volontaire pour que la transaction reste visible même sans multiple calculable).
--
-- ev_to_revenue calculé ici (pas stocké dans transaction_financials) car
-- dérivable directement de deux faits bruts déjà présents (ev_at_offer,
-- target_revenue_ttm) — même principe que les vues de ratios de l'étape 4 :
-- pas de colonne stockée pour une valeur recalculable.

CREATE VIEW v_transaction_multiples AS
SELECT
    tx.transaction_id,
    a.ticker AS acquirer_ticker,
    t.name AS target_name,
    ts.name AS target_sector,
    tx.announce_date,
    EXTRACT(YEAR FROM tx.announce_date)::INT AS announce_year,
    tf.target_revenue_ttm,
    tf.target_ebitda_ttm,
    tf.target_net_debt,
    tf.ev_at_offer,
    tf.ev_ebitda_multiple,
    CASE
        WHEN tf.target_revenue_ttm > 0
        THEN tf.ev_at_offer / tf.target_revenue_ttm
    END AS ev_to_revenue,
    tf.notes
FROM transactions tx
JOIN companies a ON a.company_id = tx.acquirer_company_id
JOIN companies t ON t.company_id = tx.target_company_id
LEFT JOIN sectors ts ON ts.sector_id = t.sector_id
LEFT JOIN transaction_financials tf ON tf.transaction_id = tx.transaction_id;
