-- 002_transactions_unique.sql
-- Le schéma initial (001_init.sql) ne posait aucune contrainte d'unicité sur
-- `transactions`, ce qui empêchait un chargement idempotent (INSERT ...
-- ON CONFLICT DO UPDATE) comme pratiqué partout ailleurs dans le projet.
-- Clé naturelle retenue : un couple (acquéreur, cible) ne peut annoncer
-- qu'une seule transaction à une date d'annonce donnée.

BEGIN;

ALTER TABLE transactions
    ADD CONSTRAINT uq_transactions_deal UNIQUE (acquirer_company_id, target_company_id, announce_date);

COMMIT;
