import discord
from discord.ext import commands
import asyncio

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

        hex_keys = [
            ["0","1","2","3"],
            ["4","5","6","7"],
            ["8","9","A","B"],
            ["C","D","E","F"]
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

    def build_embed(self):
        embed = discord.Embed(title="🔷 Hex Glyph Keypad", color=0x00FFFF)
        embed.add_field(name="Input", value=f"`{self.input_string or ' '}`", inline=False)

        if self.emoji_sequence:
            embed.add_field(name="Preview", value=" ".join(self.emoji_sequence), inline=False)

        if self.class_type:
            embed.add_field(name="Class", value=self.class_type, inline=False)

        return embed

    async def temp_error(self, interaction, text):
        msg = await interaction.followup.send(text, ephemeral=True)
        await asyncio.sleep(10)
        try:
            await msg.delete()
        except:
            pass

    def make_callback(self, key):
        async def callback(interaction: discord.Interaction):

            if len(self.input_string) >= 12:
                return await interaction.response.defer()

            self.input_string += key
            self.emoji_sequence.append(
                f"<:{glyph_emojis[key].name}:{glyph_emojis[key].id}>"
            )

            # -------- GLYPH 1 --------
            if len(self.input_string) == 1:
                val = int(self.input_string, 16)

                if val == 0:
                    await self.temp_error(interaction, "⚠️ Address will take you to Glyph 1")

                elif val > 6:
                    self.input_string = ""
                    self.emoji_sequence = []
                    await self.temp_error(interaction, "❌ Invalid Glyph input: planet index")

            # -------- GLYPHS 2–4 --------
            if len(self.input_string) == 4:
                ssi_hex = self.input_string[1:4]
                ssi_val = int(ssi_hex, 16)

                if ssi_val == 0:
                    self.input_string = self.input_string[:1]
                    self.emoji_sequence = self.emoji_sequence[:1]
                    await self.temp_error(interaction, "❌ Error in SSI")

                elif 1 <= ssi_val <= 0x123:
                    self.class_type = "🟡 Yellow"

                elif 0x124 <= ssi_val < 0x3E8:
                    self.class_type = "RGB"

                elif 0x3E9 <= ssi_val <= 0x429:
                    self.class_type = "🟣 Purple"

                elif ssi_val > 0x429:
                    self.input_string = self.input_string[:1]
                    self.emoji_sequence = self.emoji_sequence[:1]
                    await self.temp_error(interaction, "❌ Invalid SSI: too high")

            # -------- GLYPHS 5–6 --------
            if len(self.input_string) == 6:
                yy_hex = self.input_string[4:6]

                if yy_hex.upper() == "81":
                    self.input_string = self.input_string[:4]
                    self.emoji_sequence = self.emoji_sequence[:4]
                    await self.temp_error(interaction, "❌ Invalid YY")

            # -------- GLYPHS 7–9 --------
            if len(self.input_string) == 9:
                zzz_hex = self.input_string[6:9]

                if zzz_hex.upper() == "801":
                    self.input_string = self.input_string[:6]
                    self.emoji_sequence = self.emoji_sequence[:6]
                    await self.temp_error(interaction, "❌ Invalid ZZZ")

            # -------- GLYPHS 10–12 --------
            if len(self.input_string) == 12:
                xxx_hex = self.input_string[9:12]

                if xxx_hex.upper() == "801":
                    self.input_string = self.input_string[:9]
                    self.emoji_sequence = self.emoji_sequence[:9]
                    await self.temp_error(interaction, "❌ Invalid XXX")

                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True

                await interaction.response.edit_message(
                    embed=self.build_embed(),
                    view=self
                )
                return 

            # -------- GALACTIC CORE --------
            if len(self.input_string) >= 12:
                core = self.input_string[4:12]

                if core == "00000000":
                    self.input_string = self.input_string[:4]
                    self.emoji_sequence = self.emoji_sequence[:4]
                    await self.temp_error(interaction, "🌌 Galactic Core Detected")

            await interaction.response.edit_message(
                embed=self.build_embed(),
                view=self
            )

        return callback

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

    @commands.command(name="hexkey",
    help="A glyph keyboard for stellar information")
    async def hexkey(self, ctx):
        view = SimpleHexKeypad(owner_id=ctx.author.id)
        await ctx.send(embed=view.build_embed(), view=view)


async def setup(bot):
    await bot.add_cog(HexKey(bot))