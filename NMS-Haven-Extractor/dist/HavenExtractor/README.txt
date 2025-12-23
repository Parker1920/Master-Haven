============================================================
  HAVEN EXTRACTOR v8.0.0 - Remote API Sync
  For No Man's Sky
============================================================

QUICK START:
1. Extract this entire folder to a location of your choice
2. Run "RUN_HAVEN_EXTRACTOR.bat"
3. The game will start with the extractor mod loaded
4. Warp to a solar system
5. Click "Extract Now" in the pyMHF GUI window
6. Data is automatically sent to Haven UI + saved locally!

API SYNC:
Remote sync is ENABLED BY DEFAULT!
The API URL (voyagers-haven-3dmap.ngrok.io) is hardcoded in the mod.
No configuration needed - just run and extract!

If you need to use a DIFFERENT ngrok URL:
1. Go to mod/ folder
2. Copy "haven_config.json.example" to "haven_config.json"
3. Edit haven_config.json and set your custom ngrok URL:
   {"api_url": "https://your-custom-url.ngrok-free.app"}

REQUIREMENTS:
- No Man's Sky (Steam version recommended)
- Windows 10/11
- No additional Python installation required!

FILES:
- RUN_HAVEN_EXTRACTOR.bat       - Main launcher (run this!)
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
  %USERPROFILE%\Documents\Haven-Extractor\extraction_YYYYMMDD_HHMMSS.json

For support, visit: https://github.com/voyagershaven
============================================================
