import os
import json
import asyncio
from pathlib import Path

# Ensure the Keeper integration code is importable
import sys
sys.path.insert(0, str(Path('keeper-discord-bot-main') / 'src'))

# Set environment to HTTP API mode, pointing at the local Haven-UI server
os.environ['HAVEN_SYNC_API_URL'] = 'http://127.0.0.1:8000'
os.environ['HAVEN_API_KEY'] = 'TESTKEY-LOCAL'
# Ensure we prefer local DB/JSON path if needed
os.environ['USE_HAVEN_DATABASE'] = 'false'

from core.haven_integration_http import HavenIntegrationHTTP

async def run_test():
    hi = HavenIntegrationHTTP()
    print('Mode:', hi.mode)
    print('api_url:', hi.api_url)
    print('api_key:', hi.api_key)
    ok = await hi.load_haven_data()
    print('Loaded Haven data via HTTP:', ok)

    # Now try a dummy discovery write to the server
    discovery = {
        'system_name': 'HttpTestSystem',
        'planet': 'HttpTestPlanet',
        'description': 'Integration test posted by Keeper bot',
    }
    try:
        discovery_id = await hi.write_discovery_to_database(discovery)
        print('Discovery write result:', discovery_id)
    except Exception as e:
        print('Write discovery failed:', e)
    finally:
        await hi.close()

if __name__ == '__main__':
    asyncio.run(run_test())
