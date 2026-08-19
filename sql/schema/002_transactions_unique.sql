-- 002_transactions_unique.sql — ajoute la contrainte d'unicité manquante sur
-- `transactions` pour permettre un chargement idempotent.

BEGIN;

ALTER TABLE transactions
    ADD CONSTRAINT uq_transactions_deal UNIQUE (acquirer_company_id, target_company_id, announce_date);

COMMIT;
