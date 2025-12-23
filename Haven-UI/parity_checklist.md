# Control Room Web UI Parity Checklist

This file describes the features included in the current Haven-UI web conversion, and notes on parity vs. the desktop Control Room.

## Implemented Features (Paritally or Fully)
- [x] Dashboard: quick actions (generate map, open latest map), quick list of systems
- [x] Systems: list, edit, delete (multi-page view)
- [x] System Entry Wizard: multi-step form with nested planets and moons (create/edit)
- [x] Map Generation: invoke Beta_VH_Map to create `dist/VH-Map.html` and serve it
- [x] Test Manager: list test files and run individual tests
- [x] Logs: tail the latest control room logs
- [x] Settings: Theme & status (simple placeholder)
- [x] Round Table AI Chat Monitor: log viewer of `logs/ai_chat.log`
- [x] Photos upload endpoint (save to `photos/`)
- [x] Backup endpoint for database backups
- [x] Data sync check (JSON ↔ DB) via DataSynchronizer (DEPRECATED/ARCHIVED — use DB-only workflows)
- [x] Directory listing for `data/` and `logs/`

## TODO / Future Parity Tasks (Not Implemented Yet)
- Convert GUI-specific desktop widgets to a polished SPA (React/Vue) with identical UX
- Real-time WebSockets for AI Chat Monitor and logs (currently uses polling)
- Role-based auth and multi-user session management
- Full packaging & PWA export via web (we added placeholder endpoint)
- Export & packaging wizard (desktop only for now)

## Run Notes
- This server uses the repo's `src.control_room_api`—run from root or adjust PYTHONPATH.
- The design is modular: the web UI can be replaced with a SPA and hooked into the same API before final parity.

---

This checklist will be updated as new features are implemented.
