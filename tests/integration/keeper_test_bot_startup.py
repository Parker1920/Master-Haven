import asyncio
import os
import sys
from pathlib import Path

# Ensure keeper module path
sys.path.insert(0, str(Path('keeper-discord-bot-main') / 'src'))

# Load env
from dotenv import load_dotenv
load_dotenv('keeper-discord-bot-main/.env')

from main import TheKeeper

async def test():
    bot = TheKeeper()
    print('Created bot')
    await bot.setup_hook()
    print('Setup hook completed')
    print('Sync worker running?', bot.sync_worker.is_running if bot.sync_worker else 'no')
    print('Sync API port:', bot.sync_api.port if bot.sync_api else 'no')
    # Clean up: stop sync worker and api
    await bot.close()

if __name__ == '__main__':
    asyncio.run(test())
