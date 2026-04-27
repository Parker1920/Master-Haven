FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir \
        "discord.py>=2.3" \
        python-dotenv \
        aiohttp \
        gspread \
        google-auth

# bot.py hardcodes this path for the .env file; mount the real .env here at runtime.
RUN mkdir -p /storage/emulated/0/Voyage/The_Keeper

COPY . .

CMD ["python", "bot.py"]
