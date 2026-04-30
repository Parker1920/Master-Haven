# Archived test files

These files were authorized for deletion in Phase 3 but moved here instead
of deleted, per [PROPOSAL.md §9](../PROPOSAL.md). Final deletion is
scheduled for ~30 days after v1 lands stable (see `FOLLOWUP.md`).

| Original path | Archive name | Why retired |
|---|---|---|
| `Haven-UI/tests/api/test_endpoints.py` | `legacy_api_test_endpoints.py` | Wrong port (8000 → 8005), bare `print()` not pytest |
| `Haven-UI/tests/api/test_api_calls.py` | `legacy_api_test_api_calls.py` | References `/api/rtai/*` (removed) and `:8080/health` (Keeper Sync, defunct) |
| `Haven-UI/tests/api/test_post_discovery.py` | `legacy_api_test_post_discovery.py` | Wrong port; predates v1.33.0 discovery approval workflow |
| `Haven-UI/tests/integration/test_integration.py` | `legacy_integration_test.py` | Reads `data.json` (project switched to SQLite long ago) |
| `Haven-UI/scripts/smoke_test.py` | `legacy_scripts_smoke_test.py` | Default `http://127.0.0.1:8000`; superseded by `tests/smoke/` |

These remain available for reference (payload patterns, DB inspection
helpers) but are NOT collected by pytest — `tests/pytest.ini` only walks
`smoke/` and `verify/`.

Do not run them. They will fail.
