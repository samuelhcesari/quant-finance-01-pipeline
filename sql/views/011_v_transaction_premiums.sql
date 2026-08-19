-- v_transaction_premiums — primes de transaction M&A (docs/00_project_
-- charter.md, section 5) : Premium = (Offer Price / Unaffected Price) - 1.
--
-- NULL quand unaffected_price n'est pas documenté pour la transaction (charte
-- section 6 : chaque transaction doit avoir une source vérifiable ; à défaut
-- de prix non-affecté explicitement cité dans le document source, la prime
-- n'est pas calculée plutôt qu'estimée à partir d'une fenêtre arbitraire).
-- Regroupement par secteur de la CIBLE (pas de l'acquéreur) et par année
-- d'annonce, pour permettre l'analyse "par secteur et par cycle" (charte
-- section 2, sous-question sur la dynamique des transactions M&A).

CREATE VIEW v_transaction_premiums AS
SELECT
    tx.transaction_id,
    a.ticker AS acquirer_ticker,
    a.name AS acquirer_name,
    t.name AS target_name,
    t.is_public AS target_is_public,
    ts.name AS target_sector,
    tx.announce_date,
    EXTRACT(YEAR FROM tx.announce_date)::INT AS announce_year,
    tx.payment_type,
    tx.offer_price_per_share,
    tx.unaffected_price,
    tx.unaffected_price_date,
    CASE
        WHEN tx.unaffected_price > 0
        THEN tx.offer_price_per_share / tx.unaffected_price - 1
    END AS premium,
    tx.deal_value,
    tx.source_url
FROM transactions tx
JOIN companies a ON a.company_id = tx.acquirer_company_id
JOIN companies t ON t.company_id = tx.target_company_id
LEFT JOIN sectors ts ON ts.sector_id = t.sector_id;
