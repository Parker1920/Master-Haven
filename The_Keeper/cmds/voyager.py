"""
Voyager poster slash commands.

/fingerprint [user] [username]   — drops a Voyager Card into chat
/atlas [galaxy]                  — drops a Galaxy Atlas into chat

Both commands embed PNGs served by the Haven backend at:
    {HAVEN_PUBLIC_URL}/api/posters/voyager_og/{username}.png
    {HAVEN_PUBLIC_URL}/api/posters/atlas/{galaxy}.png

The bot doesn't render anything itself — it's a thin client of the Haven
backend's poster service. Same source of truth as Discord/Twitter link
embeds, in-UI thumbnails, and direct shares.

Three URL env vars matter here, and they have different audiences:
  - HAVEN_API: the URL the bot uses to call the Haven backend itself.
    On the Pi this is the internal docker network address
    (http://haven:8005) because hairpin NAT means the public
    https://havenmap.online doesn't resolve back to itself from inside
    the Pi's LAN.
  - HAVEN_PUBLIC_URL: the URL embedded in messages that get sent OUT to
    Discord — image URLs, page links, anything Discord's CDN or the user's
    browser will fetch from the public internet. Must be the public site
    URL. Defaults to https://havenmap.online.
  - HAVEN_URL: legacy variable used by other cogs (the Haven_stats button).
    Kept as a fallback for HAVEN_PUBLIC_URL so single-host deploys can
    still set just one variable.
"""

import os
import re
import logging
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("commands.voyager")

# Public URL — anything that ends up in a Discord embed must use this.
# Falls back to HAVEN_URL (used elsewhere) and finally to the public domain.
HAVEN_PUBLIC_URL = (
    os.getenv("HAVEN_PUBLIC_URL")
    or os.getenv("HAVEN_URL")
    or "https://havenmap.online"
)

# Defensive: if HAVEN_PUBLIC_URL still looks like the internal docker address
# (someone copied HAVEN_API into HAVEN_PUBLIC_URL by mistake), fall back to
# the public default. Discord can't fetch from `haven:8005`, so an embed
# built from that URL gets rejected with a 400 "Not a well formed URL".
if HAVEN_PUBLIC_URL.startswith("http://haven:") or "://haven:" in HAVEN_PUBLIC_URL:
    log.warning(
        "HAVEN_PUBLIC_URL=%r looks like an internal docker URL; "
        "falling back to https://havenmap.online for Discord embeds.",
        HAVEN_PUBLIC_URL,
    )
    HAVEN_PUBLIC_URL = "https://havenmap.online"

# Strip any trailing path/slashes so f"{HAVEN_PUBLIC_URL}/voyager/x" doesn't
# end up with a doubled slash or a leftover suffix like "/map/latest".
HAVEN_PUBLIC_URL = HAVEN_PUBLIC_URL.rstrip("/")

# Galaxies that should appear in the /atlas autocomplete.
# (Top-explored galaxies in our DB, hardcoded for fast autocomplete.)
POPULAR_GALAXIES = [
    "Euclid",
    "Hilbert Dimension",
    "Calypso",
    "Hesperius Dimension",
    "Hyades",
    "Eissentam",
    "Aptarkaba",
    "Budullangr",
    "Ezdaranit",
    "Odyalutai",
    "Zavainlani",
]


def normalize_username_for_url(name: str) -> str:
    """Mirror of frontend posters/_shared/identity.js normalizeUsernameForUrl.

    Strips '#', strips trailing 4-digit Discord discriminator if present,
    lowercases. Must produce identical output to the backend's
    normalize_username_for_dedup used by the voyager-fingerprint endpoint.
    """
    if not name:
        return ""
    clean = str(name).replace("#", "").strip()
    # Strip trailing 4-digit discriminator if the char before isn't a digit
    if (
        len(clean) > 4
        and clean[-4:].isdigit()
        and not clean[-5].isdigit()
    ):
        clean = clean[:-4]
    return clean.lower().strip()


class VoyagerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ============================================================
    # /fingerprint
    # ============================================================
    @app_commands.command(
        name="fingerprint",
        description="Show a Voyager Card — anyone's galaxy fingerprint stats.",
    )
    @app_commands.describe(
        user="Discord member to look up (defaults to you)",
        username="Override username string if Discord name doesn't match Haven",
    )
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def fingerprint(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        username: Optional[str] = None,
    ):
        target_name = username or (user.name if user else interaction.user.name)
        slug = normalize_username_for_url(target_name)
        if not slug:
            await interaction.response.send_message(
                "Couldn't resolve a username to look up.",
                ephemeral=True,
            )
            return

        # Cache-bust by appending current minute so the bot doesn't keep
        # showing a stale image after invalidation. Discord caches embed
        # images for ~1 hour anyway; 1-min granularity is plenty.
        cache_buster = int(time.time() // 60)
        png_url = f"{HAVEN_PUBLIC_URL}/api/posters/voyager_og/{slug}.png?v={cache_buster}"
        page_url = f"{HAVEN_PUBLIC_URL}/voyager/{slug}"

        embed = discord.Embed(
            title=f"{target_name}'s Voyager Card",
            description=f"Galaxy fingerprint stats from havenmap.online",
            color=0x00C2B3,
            url=page_url,
        )
        embed.set_image(url=png_url)
        embed.set_footer(text="Voyager's Haven · live data")
        await interaction.response.send_message(embed=embed)

    @fingerprint.error
    async def fingerprint_error(self, interaction, error):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"Slow down, voyager. Try again in {error.retry_after:.0f}s.",
                ephemeral=True,
            )
        else:
            log.exception("fingerprint command failed", exc_info=error)
            try:
                await interaction.response.send_message(
                    "Something went wrong looking up that voyager.",
                    ephemeral=True,
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    "Something went wrong looking up that voyager.",
                    ephemeral=True,
                )

    # ============================================================
    # /atlas
    # ============================================================
    @app_commands.command(
        name="atlas",
        description="Show a Galaxy Atlas — political map of any galaxy.",
    )
    @app_commands.describe(galaxy="Galaxy name (defaults to Euclid)")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def atlas(
        self,
        interaction: discord.Interaction,
        galaxy: Optional[str] = "Euclid",
    ):
        galaxy = (galaxy or "Euclid").strip() or "Euclid"
        cache_buster = int(time.time() // 60)
        # Atlas URL needs the galaxy name URL-encoded (some have spaces)
        from urllib.parse import quote
        galaxy_path = quote(galaxy, safe="")
        png_url = f"{HAVEN_PUBLIC_URL}/api/posters/atlas/{galaxy_path}.png?v={cache_buster}"
        page_url = f"{HAVEN_PUBLIC_URL}/atlas/{galaxy_path}"

        embed = discord.Embed(
            title=f"{galaxy} — Galactic Atlas",
            description="Political map of named regions, drawn from live data.",
            color=0x00C2B3,
            url=page_url,
        )
        embed.set_image(url=png_url)
        embed.set_footer(text="Voyager's Haven · live data")
        await interaction.response.send_message(embed=embed)

    @atlas.autocomplete("galaxy")
    async def atlas_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ):
        # Filter the popular galaxy list by what the user has typed so far.
        cur = (current or "").lower()
        matches = [g for g in POPULAR_GALAXIES if cur in g.lower()]
        # Discord allows up to 25 autocomplete choices
        return [app_commands.Choice(name=g, value=g) for g in matches[:25]]

    @atlas.error
    async def atlas_error(self, interaction, error):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"Slow down, voyager. Try again in {error.retry_after:.0f}s.",
                ephemeral=True,
            )
        else:
            log.exception("atlas command failed", exc_info=error)
            try:
                await interaction.response.send_message(
                    "Something went wrong looking up that galaxy.",
                    ephemeral=True,
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    "Something went wrong looking up that galaxy.",
                    ephemeral=True,
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(VoyagerCog(bot))
