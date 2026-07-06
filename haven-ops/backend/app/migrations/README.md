# Migrations

Plain versioned SQL, no Alembic.

- Files are named `NNN_description.sql` (e.g. `001_init.sql`) and applied in
  filename order by `migrate.py` (lands in Stage 1).
- Applied migrations are recorded in the `schema_version` table; a file is
  never applied twice and never edited after it has shipped — fixes are new
  files.
