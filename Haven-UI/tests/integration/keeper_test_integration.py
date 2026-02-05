import os
import asyncio
import sys
from pathlib import Path

# Ensure keeper module path
sys.path.insert(0, str(Path('keeper-discord-bot-main') / 'src'))

# Set environment variables to point to Haven-UI local data
os.environ['HAVEN_DATA_PATH'] = str(Path('Haven-UI') / 'data' / 'data.json')
os.environ['HAVEN_DB_PATH'] = str(Path('Haven-UI') / 'data' / 'haven_ui.db')

from core.haven_integration_http import HavenIntegrationHTTP

async def test():
    hi = HavenIntegrationHTTP()
    print('Mode:', hi.mode)
    print('db_path:', hi.db_path)
    print('haven_data_path:', hi.haven_data_path)
    ok = await hi.load_haven_data()
    print('Loaded', ok, 'systems count:', len(hi.haven_data) if hi.haven_data else 0)

if __name__ == '__main__':
    asyncio.run(test())
