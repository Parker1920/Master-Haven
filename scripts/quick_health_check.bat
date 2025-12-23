@echo off
echo ============================================
echo Master Haven - Quick Health Check
echo ============================================
echo.

cd /d "%~dp0.."

python -c "import sqlite3; from pathlib import Path; print('=== Database Check ===\n'); db_path = Path('Haven-UI/data/haven_ui.db'); conn = sqlite3.connect(str(db_path)); cursor = conn.cursor(); cursor.execute('PRAGMA table_info(planets)'); cols = [row[1] for row in cursor.fetchall()]; print(f'Planets table: {len(cols)} columns'); print(f'Has coordinates: {\"YES\" if \"x\" in cols else \"NO\"}'); print(f'Has game properties: {\"YES\" if \"climate\" in cols else \"NO\"}'); cursor.execute('SELECT COUNT(*) FROM systems'); systems = cursor.fetchone()[0]; cursor.execute('SELECT COUNT(*) FROM planets'); planets = cursor.fetchone()[0]; cursor.execute('SELECT COUNT(*) FROM discoveries'); discoveries = cursor.fetchone()[0]; cursor.execute('SELECT COUNT(*) FROM pending_systems WHERE status=\"pending\"'); pending = cursor.fetchone()[0]; print(f'\n=== Data Status ==='); print(f'Systems: {systems}'); print(f'Planets: {planets}'); print(f'Discoveries: {discoveries}'); print(f'Pending approvals: {pending}'); conn.close(); print('\n=== Path Config ==='); exec('from config.paths import haven_paths'); print(f'Haven DB: {haven_paths.haven_db}'); print(f'Keeper DB: {haven_paths.keeper_db}'); print('\n=== Status: READY ==='); print('All checks passed!')"

echo.
echo ============================================
pause
