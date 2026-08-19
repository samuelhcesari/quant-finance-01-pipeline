-- v_transaction_multiples — EV/EBITDA, EV/Revenue depuis transaction_financials.
-- LEFT JOIN : Splunk et Lhoist North America n'ont pas de financials chargés.
-- ev_to_revenue calculé ici, pas stocké (dérivable de ev_at_offer/target_revenue_ttm).

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
