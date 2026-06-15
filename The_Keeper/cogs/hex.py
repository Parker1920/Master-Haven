import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import aiohttp

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

        self.system_owner_type = "uncharted"
        self.system_owner_tag = None

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

        back = discord.ui.Button(
            label="←",
            style=discord.ButtonStyle.danger,
            row=4
        )

        back.callback = self.backspace
        self.add_item(back)

        reset = discord.ui.Button(
            label="Reset",
            style=discord.ButtonStyle.primary,
            row=4
        )

        reset.callback = self.reset
        self.add_item(reset)

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

        if self.system_owner_tag:

            ownership_value = (
                f"{self.system_owner_type}:{self.system_owner_tag}"
            )

        else:
            ownership_value = self.system_owner_type

        embed.add_field(
            name="System Ownership",
            value=ownership_value,
            inline=False
        )

        if self.system_owner_tag:

            embed.add_field(
                name="Haven API",
                value=(
                    f"{BASE}/api/public/community-regions"
                    f"?community={self.system_owner_tag}"
                ),
                inline=False
            )

        return embed

    async def temp_error(self, interaction, text):

        msg = await interaction.followup.send(
            text,
            ephemeral=True
        )

        await asyncio.sleep(10)

        try:
            await msg.delete()
        except:
            pass

    async def safe_edit(self, interaction):

        try:

            await interaction.edit_original_response(
                embed=self.build_embed(),
                view=self
            )

        except discord.NotFound:
            pass

    async def fetch_system_owner(self, session, glyph):
        try:
            
            async with session.get(
                f"{BASE}/api/systems/search?q={glyph}&limit=1",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return None
                
                data = await resp.json()
                results = data.get("results", [])
                
                if results:
                    return results[0]  
                return None
    
        except asyncio.TimeoutError:
            print(f"TIMEOUT: glyph lookup for {glyph}")
            return None
    
        except Exception as e:
            print(f"ERROR: glyph lookup for {glyph} -> {e}")
            return None
            

    def make_callback(self, key):

        async def callback(interaction: discord.Interaction):

            if interaction.user.id != self.owner_id:

                return await interaction.response.send_message(
                    "Not your keypad.",
                    ephemeral=True
                )

            await interaction.response.defer()

            if len(self.input_string) >= 12:
                return

            self.input_string += key

            self.emoji_sequence.append(
                f"<:{glyph_emojis[key].name}:{glyph_emojis[key].id}>"
            )

            # GLYPH 1
            if len(self.input_string) == 1:

                val = int(self.input_string, 16)

                if val == 0:

                    await self.temp_error(
                        interaction,
                        "⚠️ Address will take you to Glyph 1"
                    )

                elif val > 6:

                    self.input_string = ""
                    self.emoji_sequence = []

                    await self.temp_error(
                        interaction,
                        "❌ Invalid Glyph input: planet index"
                    )

            # GLYPHS 2–4
            if len(self.input_string) == 4:

                ssi_val = int(self.input_string[1:4], 16)

                if ssi_val == 0:

                    self.input_string = self.input_string[:1]
                    self.emoji_sequence = self.emoji_sequence[:1]

                    await self.temp_error(
                        interaction,
                        "❌ Error in SSI"
                    )

                elif 1 <= ssi_val <= 0x123:
                    self.class_type = "🟡 Yellow"

                elif 0x124 <= ssi_val < 0x3E8:
                    self.class_type = "RGB"

                elif 0x3E9 <= ssi_val <= 0x429:
                    self.class_type = "🟣 Purple"

                elif 0x258 <= ssi_val <= 0x3E7:
                    self.class_type = "!phantom"

                elif ssi_val == 0x3E8:
                    self.class_type = "!Glass"

                elif ssi_val >= 0x430:
                    self.class_type = "!phantom"

            # GLYPHS 5–6
            if len(self.input_string) == 6:

                if self.input_string[4:6].upper() == "81":

                    self.input_string = self.input_string[:4]
                    self.emoji_sequence = self.emoji_sequence[:4]

                    await self.temp_error(
                        interaction,
                        "❌ Invalid YY"
                    )

            # GLYPHS 7–9
            if len(self.input_string) == 9:

                if self.input_string[6:9].upper() == "801":

                    self.input_string = self.input_string[:6]
                    self.emoji_sequence = self.emoji_sequence[:6]

                    await self.temp_error(
                        interaction,
                        "❌ Invalid ZZZ"
                    )

            # GLYPHS 10–12
            if len(self.input_string) == 12:

                if self.input_string[9:12].upper() == "801":

                    self.input_string = self.input_string[:9]
                    self.emoji_sequence = self.emoji_sequence[:9]

                    await self.temp_error(
                        interaction,
                        "❌ Invalid XXX"
                    )

                system_id = self.input_string.upper()

                print(f"INPUT SYSTEM ID: {system_id}")

                self.system_owner_type = "uncharted"
                self.system_owner_tag = None

                try:

                    timeout = aiohttp.ClientTimeout(total=120)

                    async with aiohttp.ClientSession(
                        timeout=timeout
                    ) as session:

                        data = await self.fetch_system_owner(
                            session,
                            system_id
                        )
                        
                        if data:
                        
                            self.system_owner_type = "community"
                            self.system_owner_tag = data.get(
                                "discord_tag"
                            )

                except Exception:

                    import traceback
                    traceback.print_exc()

                    self.system_owner_type = "uncharted"
                    self.system_owner_tag = None

                for item in self.children:

                    if isinstance(item, discord.ui.Button):
                        item.disabled = True

                await self.safe_edit(interaction)
                return

            await self.safe_edit(interaction)

        return callback

    async def backspace(self, interaction: discord.Interaction):

        await interaction.response.defer()

        if self.input_string:

            self.input_string = self.input_string[:-1]

            if self.emoji_sequence:
                self.emoji_sequence.pop()

        await self.safe_edit(interaction)

    async def reset(self, interaction: discord.Interaction):

        await interaction.response.defer()

        self.input_string = ""
        self.emoji_sequence = []

        self.class_type = None

        self.system_owner_type = "uncharted"
        self.system_owner_tag = None

        for item in self.children:

            if isinstance(item, discord.ui.Button):
                item.disabled = False

        await self.safe_edit(interaction)


class HexKey(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="hexkey",
        description="A glyph keyboard for stellar information"
    )
    async def hexkey(self, interaction: discord.Interaction):

        view = SimpleHexKeypad(
            owner_id=interaction.user.id
        )

        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view
        )


async def setup(bot):
    await bot.add_cog(HexKey(bot))