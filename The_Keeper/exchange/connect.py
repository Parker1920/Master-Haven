import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os


DB_PATH = os.path.join(os.path.dirname(__file__), "cogs","Data","xp.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_links (
        discord_id TEXT PRIMARY KEY,
        discord_name TEXT,
        exchange_username TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


class ConnectCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_db()

    @app_commands.command(name="connect", description="Link your Discord account to your Exchange account")
    @app_commands.describe(exchange_username="Your Travelers Exchange username")
    async def connect(self, interaction: discord.Interaction, exchange_username: str):
        discord_id = str(interaction.user.id)
        discord_name = str(interaction.user.name)

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # Insert or update existing link
        cur.execute("""
        INSERT INTO user_links (discord_id, discord_name, exchange_username)
        VALUES (?, ?, ?)
        ON CONFLICT(discord_id)
        DO UPDATE SET
            discord_name=excluded.discord_name,
            exchange_username=excluded.exchange_username
        """, (discord_id, discord_name, exchange_username))

        conn.commit()
        conn.close()

        await interaction.response.send_message(
            f"✅ Connected **{discord_name}** → Exchange account **{exchange_username}**",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ConnectCog(bot))