-- 002_company_entity_type.sql — add company.entity_type.
--
-- The Company quick-reference ("Type: PA single-member LLC") and the emitted
-- doc's Legal-name row need the entity type, and it has to come from data —
-- 001 shipped without a column for it. Backfills the existing singleton;
-- fresh DBs get it from the seed.
ALTER TABLE company ADD COLUMN entity_type TEXT;
UPDATE company SET entity_type = 'PA single-member LLC' WHERE id = 1;
