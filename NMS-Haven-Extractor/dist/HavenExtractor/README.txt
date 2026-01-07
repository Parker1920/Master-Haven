============================================================
  HAVEN EXTRACTOR v9.0.0 - Batch Mode
  For No Man's Sky
============================================================

QUICK START:
1. Extract this entire folder to a location of your choice
2. Run "RUN_HAVEN_EXTRACTOR.bat"
3. The game will start with the extractor mod loaded
4. Warp to a solar system - data is captured automatically!
5. Continue warping to collect multiple systems
6. Click "Export Batch" to save all systems to JSON

BATCH MODE WORKFLOW:
1. Warp to a new system - planet data captured via hook
2. Continue warping - all systems saved to batch automatically
3. Click "Batch Status" to see how many systems collected
4. Click "Export Batch" when ready to save all data

Data extracted per system:
- star_type, economy_type, economy_strength, conflict_level
- dominant_lifeform, planet count

Data extracted per planet:
- biome, biome_subtype, weather
- flora_level, fauna_level, sentinel_level
- common_resource, uncommon_resource, rare_resource
- is_moon, planet_size, planet_name

API SYNC:
Remote sync is ENABLED BY DEFAULT!
The API URL (voyagers-haven-3dmap.ngrok.io) is hardcoded in the mod.
No configuration needed - just run and extract!

If you need to use a DIFFERENT ngrok URL:
1. Go to mod/ folder
2. Copy "haven_config.json.example" to "haven_config.json"
3. Edit haven_config.json and set your custom ngrok URL:
   {"api_url": "https://your-custom-url.ngrok-free.app"}

GUI BUTTONS:
- "Check Planet Data" - See captured planet info
- "Extract Now"       - Manual extraction of current system
- "Export Batch"      - Save ALL collected systems to JSON
- "Clear Batch"       - Clear batch for fresh collection
- "Batch Status"      - Show batch collection progress

REQUIREMENTS:
- No Man's Sky (Steam version recommended)
- Windows 10/11
- No additional Python installation required!

FILES:
- RUN_HAVEN_EXTRACTOR.bat       - Main launcher (run this!)
- RUN_DEBUG.bat                 - Debug launcher with extra info
- FIRST_TIME_SETUP.bat          - Verify installation
- python/                       - Embedded Python (don't modify)
- mod/                          - Extractor mod files

TROUBLESHOOTING:
- If the game doesn't start, try running as Administrator
- Make sure No Man's Sky is installed via Steam
- Check that antivirus isn't blocking the launcher
- If API sync fails, make sure Haven UI host has ngrok running

LOCAL OUTPUT (always saved as backup):
  %USERPROFILE%\Documents\Haven-Extractor\latest.json
  %USERPROFILE%\Documents\Haven-Extractor\batch_*.json

For support, visit: https://github.com/voyagershaven
============================================================
