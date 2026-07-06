-- 004_document_origin_and_asset_receipts.sql
--
-- (1) documents_generated.origin — where the record's file came from:
--       'generated' = rendered + frozen by docgen
--       'uploaded'  = a real file uploaded through the UI (governance PDFs,
--                     receipt scans, signed copies, …)
--       'seed'      = seeded metadata record with no file yet
--     Only 'uploaded' rows may ever be deleted; generated/seed records are
--     permanent. Backfill: anything already carrying a sha256 was generated.
--
-- (2) assets.document_id — link an asset to its receipt scan (an uploaded
--     document row), so "Itemize" flags can carry actual evidence.
ALTER TABLE documents_generated ADD COLUMN origin TEXT NOT NULL DEFAULT 'seed';
UPDATE documents_generated SET origin = 'generated' WHERE sha256 IS NOT NULL;

ALTER TABLE assets ADD COLUMN document_id INTEGER REFERENCES documents_generated(id);
