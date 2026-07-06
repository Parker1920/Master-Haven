-- 003_governance_documents.sql — register the LLC's standing governance
-- records in documents_generated (engagement_id NULL = company-level).
--
-- These files predate the app (sha256/filename NULL — the frontend shows no
-- download link for them); the rows give the Registry screen its document
-- index. A data migration, not seed, so the already-seeded dev DB gets them;
-- seed.py's documents_generated check is scoped to engagement docs so fresh
-- DBs seed those independently of these rows.
INSERT INTO documents_generated
    (engagement_id, doc_type, title, version, filename, sha256, generated_at, frozen, template_id)
VALUES
    (NULL, 'certificate_of_organization', 'Certificate of Organization', 1, NULL, NULL, '2026-06',    1, NULL),
    (NULL, 'operating_agreement',         'Operating Agreement',          1, NULL, NULL, '2026-06-26', 1, NULL),
    (NULL, 'schedule_a',                  'Schedule A — Capital Contribution', 1, NULL, NULL, '2026-06-26', 1, NULL),
    (NULL, 'cp575',                       'EIN Confirmation (CP 575)',    1, NULL, NULL, '2026',       1, NULL),
    (NULL, 'ops_reference',               'Ops & Compliance Reference',   1, NULL, NULL, '2026-06-28', 1, NULL);
