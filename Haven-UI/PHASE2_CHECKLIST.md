Phase 2 — UI parity & Discoveries viewer

Goal: Bring Haven-UI discoveries viewer and system entry to parity with desktop Control Room.

Priority items (initial sprint):
- Discovery Detail Page
  - Show discovery metadata: `discovery_name`, `discovery_type`, `description`, `discovered_by`, `tags`, `location_name`, `system`, `planet`, `moon`, timestamps.
  - Media gallery for photos (local `photos/`), with lightbox view and download option.
  - Action buttons: Edit (admin-only), Flag, Export JSON.
- Discoveries List Improvements
  - Advanced filters: type, system, planet, moon, discovered_by, date range.
  - Pagination and server-side limit/offset support.
  - Search suggestions (autocomplete from names/tags).
- Map Generation Status UI
  - Add job queue panel in UI (Queued / Running / Done / Failed).
  - Poll `/api/map_status` and show logs link when done.
- System Entry UI parity
  - Ensure Wizard pages match desktop fields and validation.
  - Add server-side admin-only save endpoint (already protected) and client feedback.
- Testing
  - Visual test: run the server and browse each page — Dashboard, Systems, Wizard, Discoveries, Settings.
  - Functional test: create/edit/delete a system (admin login required), create a discovery (bot or API key), generate a map.

Work plan:
1. Implement Discovery Detail Page (component + API support)
2. Add filters + pagination to `/api/discoveries` and UI
3. Add media gallery and serve `photos/` statically via backend
4. Implement map generation status endpoint and UI polling
5. Polish wizard UI & validations

Notes:
- Admin endpoints are cookie-based; the SPA sends cookies by default (`axios.withCredentials=true`).
- If you want, I can start implementing item #1 now (Discovery detail page). Otherwise, run the visual/functional tests described below and report gaps.
