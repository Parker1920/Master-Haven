import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
import aiohttp

DB_PATH = os.path.join(os.path.dirname(__file__), "exchange.db")

from exchange.exchange import BASE_URL, API_KEY

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


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


def save_connection(discord_id: str, discord_name: str, exchange_username: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

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


def get_exchange_username(discord_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "SELECT exchange_username FROM user_links WHERE discord_id=?",
        (discord_id,)
    )

    row = cur.fetchone()
    conn.close()

    return row[0] if row else None


class PasswordModal(discord.ui.Modal, title="Connect Exchange Account"):
    password = discord.ui.TextInput(
        label="Enter password",
        placeholder="Your Travelers Exchange password",
        required=True,
        style=discord.TextStyle.short
    )

    def __init__(self, cog, exchange_username: str):
        super().__init__()
        self.cog = cog
        self.exchange_username = exchange_username

    async def on_submit(self, interaction: discord.Interaction):
        discord_id = str(interaction.user.id)
        discord_name = str(interaction.user.name)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{BASE_URL}/login",
                    json={
                        "username": self.exchange_username,
                        "password": self.password.value
                    },
                    headers={"Authorization": f"Bearer {API_KEY}"}
                ) as resp:

                    if resp.status != 200:
                        await interaction.response.send_message(
                            "❌ Invalid username or password.",
                            ephemeral=True
                        )
                        return

                    data = await resp.json()

        except aiohttp.ClientError:
            await interaction.response.send_message(
                "❌ Failed to connect to Exchange API.",
                ephemeral=True
            )
            return

        save_connection(
            discord_id,
            discord_name,
            self.exchange_username
        )

        embed = discord.Embed(
            title="✅ Exchange Connected",
            description=f"Discord account linked to **{self.exchange_username}**",
            color=discord.Color.green()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


class ConnectCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_db()

    @app_commands.command(
        name="connect",
        description="Link your Discord account to your Exchange account"
    )
    @app_commands.describe(
        exchange_username="Your Travelers Exchange username"
    )
    async def connect(
        self,
        interaction: discord.Interaction,
        exchange_username: str
    ):
        await interaction.response.send_modal(
            PasswordModal(self, exchange_username)
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ConnectCog(bot))