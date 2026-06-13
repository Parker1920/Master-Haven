import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import requests

BASE = "https://havenmap.online"

glyph_emojis = {
    "0": discord.PartialEmoji(name="0", id=1487546589269463211),
    "1": discord.PartialEmoji(name="1", id=1487546881692405843),
    "2": discord.PartialEmoji(name="2", id=1487546943319048222),
    "3": discord.PartialEmoji(name="3", id=1487546987858366615),
    "4": discord.PartialEmoji(name="4", id=1487547055651033129),
    "5": discord.PartialEmoji(name="5", id=1487547115688169754),
    "6": discord.PartialEmoji(name="6", id=1487547173934596226),
    "7": discord.PartialEmoji(name="7", id=1487547239361544403),
    "8": discord.PartialEmoji(name="8", id=1487547303932854353),
    "9": discord.PartialEmoji(name="9", id=1487547364553265152),
    "A": discord.PartialEmoji(name="A", id=1487547426406404126),
    "B": discord.PartialEmoji(name="B", id=1487547508065435728),
    "C": discord.PartialEmoji(name="C", id=1487547606140981379),
    "D": discord.PartialEmoji(name="D", id=1487547687229198369),
    "E": discord.PartialEmoji(name="E", id=1487547811003105300),
    "F": discord.PartialEmoji(name="F", id=1487547868922249479),
}


class SimpleHexKeypad(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id

        self.input_string = ""
        self.emoji_sequence = []
        self.class_type = None

        self.system_owner = None
        self.system_name = None

        hex_keys = [
            ["0", "1", "2", "3"],
            ["4", "5", "6", "7"],
            ["8", "9", "A", "B"],
            ["C", "D", "E", "F"]
        ]

        for r, row in enumerate(hex_keys):
            for key in row:
                btn = discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    emoji=glyph_emojis[key],
                    row=r
                )
                btn.callback = self.make_callback(key)
                self.add_item(btn)

        back = discord.ui.Button(label="←", style=discord.ButtonStyle.danger, row=4)
        back.callback = self.backspace
        self.add_item(back)

        reset = discord.ui.Button(label="Reset", style=discord.ButtonStyle.primary, row=4)
        reset.callback = self.reset
        self.add_item(reset)

    # ---------------- API ----------------
    def resolve_system(self, system_id: str, community_tag: str):
        try:
            r = requests.get(
                f"{BASE}/api/public/community-regions",
                params={"community": community_tag},
                timeout=10
            )
            data = r.json()

            for region in data.get("regions", []):
                for s in region.get("systems", []):
                    if s.get("id") == system_id:
                        return {
                            "owner": community_tag,
                            "system_name": s.get("name"),
                            "star_type": s.get("star_type"),
                            "grade": s.get("grade"),
                            "region": region.get("region_name"),
                            "coords": (
                                region.get("region_x"),
                                region.get("region_y"),
                                region.get("region_z")
                            )
                        }

            return None

        except Exception:
            return None

    # ---------------- UI ----------------
    def build_embed(self):
        embed = discord.Embed(
            title="🔷 Hex Glyph Keypad",
            color=0x00FFFF
        )

        embed.add_field(
            name="Input",
            value=f"`{self.input_string or ' '}`",
            inline=False
        )

        if self.emoji_sequence:
            embed.add_field(
                name="Preview",
                value=" ".join(self.emoji_sequence),
                inline=False
            )

        if self.class_type:
            embed.add_field(
                name="Class",
                value=self.class_type,
                inline=False
            )

        if self.system_owner:
            embed.add_field(
                name="System Owner",
                value=(
                    f"**Community:** {self.system_owner['owner']}\n"
                    f"**System:** {self.system_owner['system_name']}\n"
                    f"**Star Type:** {self.system_owner['star_type']}\n"
                    f"**Grade:** {self.system_owner['grade']}\n"
                    f"**Region:** {self.system_owner['region']}\n"
                    f"**Coords:** {self.system_owner['coords']}"
                ),
                inline=False
            )

        return embed

    async def temp_error(self, interaction, text):
        msg = await interaction.followup.send(text, ephemeral=True)
        await asyncio.sleep(8)
        try:
            await msg.delete()
        except:
            pass

    # ---------------- CALLBACK ----------------
    def make_callback(self, key):
        async def callback(interaction: discord.Interaction):

            if len(self.input_string) >= 12:
                return await interaction.response.defer()

            self.input_string += key
            self.emoji_sequence.append(
                f"<:{glyph_emojis[key].name}:{glyph_emojis[key].id}>"
            )

            # ---------------- FINAL SYSTEM PARSE ----------------
            if len(self.input_string) == 12:
                system_id = self.input_string[4:12]
                community_tag = "HAVEN"  # default or replace with dynamic mapping

                self.system_owner = self.resolve_system(system_id, community_tag)

                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True

                await interaction.response.edit_message(
                    embed=self.build_embed(),
                    view=self
                )
                return

            await interaction.response.edit_message(
                embed=self.build_embed(),
                view=self
            )

        return callback

    # ---------------- CONTROLS ----------------
    async def backspace(self, interaction: discord.Interaction):
        if self.input_string:
            self.input_string = self.input_string[:-1]
            if self.emoji_sequence:
                self.emoji_sequence.pop()

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

    async def reset(self, interaction: discord.Interaction):
        self.input_string = ""
        self.emoji_sequence = []
        self.class_type = None
        self.system_owner = None

        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = False

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )


class HexKey(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="hexkey",
        description="A glyph keyboard for stellar information"
    )
    async def hexkey(self, interaction: discord.Interaction):
        view = SimpleHexKeypad(owner_id=interaction.user.id)

        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view
        )


async def setup(bot):
    await bot.add_cog(HexKey(bot))