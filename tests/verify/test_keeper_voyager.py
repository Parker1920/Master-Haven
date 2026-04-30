"""
Verification tests for The_Keeper's `/fingerprint` and `/atlas` slash commands.

These commands were just fixed in The_Keeper/cmds/voyager.py and were the
top priority per the Phase 1 dispatch. We test:

  - URL format of the embed image (cache-buster, slug normalization)
  - URL-encoding of galaxies with spaces (Hilbert Dimension)
  - Autocomplete substring filtering and 25-choice cap

Tests do NOT touch real Discord. The interaction is a Mock; send_message is
an AsyncMock. Per directive, if any test inadvertently constructs an
aiohttp.ClientSession we STOP.

Test list (PROPOSAL §3):
  12. test_keeper_fingerprint_url_format
  13. test_keeper_atlas_url_format
  14. test_keeper_atlas_autocomplete_filters  (P1)
"""

from __future__ import annotations

import os
import sys
import re
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

pytestmark = [pytest.mark.verify, pytest.mark.keeper]

# ---------------------------------------------------------------------------
# Make The_Keeper importable.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
KEEPER_DIR = REPO_ROOT / "The_Keeper"
if str(KEEPER_DIR) not in sys.path:
    sys.path.insert(0, str(KEEPER_DIR))


# ---------------------------------------------------------------------------
# aiohttp ClientSession sentinel — fail the test if any real one is created
# during command execution. (Per directive: "If discord.py mock isn't tight
# enough and any test creates a real aiohttp.ClientSession, STOP.")
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _no_aiohttp_session(monkeypatch):
    """Patch aiohttp.ClientSession with a sentinel that raises if used."""
    try:
        import aiohttp
    except ImportError:
        # aiohttp isn't installed — no need to patch
        yield
        return

    real_init = aiohttp.ClientSession.__init__

    def boom(self, *args, **kwargs):
        raise AssertionError(
            "Test created a real aiohttp.ClientSession — Discord network "
            "leakage. Tighten the discord.Interaction mock."
        )

    monkeypatch.setattr(aiohttp.ClientSession, "__init__", boom)
    yield
    # restore happens automatically via monkeypatch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_fake_interaction(name: str = "TestVoyager", user_id: int = 12345):
    """Build a Mock(spec=discord.Interaction)-equivalent."""
    interaction = MagicMock()
    interaction.user.name = name
    interaction.user.id = user_id
    # All I/O paths must be AsyncMocks so awaits resolve cleanly.
    interaction.response.send_message = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup.send = AsyncMock()
    return interaction


def _get_callback(cog, attr_name: str):
    """Return the underlying async callback for a cog's app_commands.

    discord.py 2.x exposes the inner function as `.callback` on the Command
    object that the decorator returns. Calling .callback directly bypasses
    the cooldown / check decorators."""
    cmd = getattr(cog, attr_name)
    callback = getattr(cmd, "callback", None)
    assert callback is not None, (
        f"{attr_name} has no .callback attribute — did discord.py change?"
    )
    return callback


def _extract_embed(interaction) -> "discord.Embed":
    """Pull the embed out of the send_message call."""
    interaction.response.send_message.assert_awaited_once()
    call = interaction.response.send_message.await_args
    embed = call.kwargs.get("embed")
    if embed is None and call.args:
        # positional — first arg might be content, embed could still be in kwargs
        embed = next((a for a in call.args if hasattr(a, "image")), None)
    assert embed is not None, (
        f"send_message called without embed: args={call.args}, kwargs={call.kwargs}"
    )
    return embed


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_keeper_fingerprint_url_format():
    """`/fingerprint` builds the right voyager_og PNG URL with cache-buster."""
    from cmds.voyager import VoyagerCog, normalize_username_for_url

    bot = MagicMock()
    cog = VoyagerCog(bot=bot)

    interaction = _make_fake_interaction(name="TestVoyager")
    callback = _get_callback(cog, "fingerprint")
    await callback(cog, interaction, user=None, username=None)

    embed = _extract_embed(interaction)

    # The poster URL must be normalized via the bot's own normalizer.
    expected_slug = normalize_username_for_url("TestVoyager")
    assert expected_slug == "testvoyager"

    image_url = embed.image.url
    assert image_url, f"embed.image.url is empty: {embed.to_dict()!r}"
    # Must contain the canonical poster path with the normalized slug
    # and a cache-buster query param.
    assert "/api/posters/voyager_og/testvoyager.png" in image_url, (
        f"unexpected image URL: {image_url}"
    )
    assert re.search(r"[?&]v=\d+", image_url), (
        f"missing or malformed cache-buster in {image_url}"
    )

    # The page link in `embed.url` should point at /voyager/<slug>.
    page_url = embed.url
    assert page_url and page_url.endswith("/voyager/testvoyager"), (
        f"unexpected page URL: {page_url}"
    )


@pytest.mark.asyncio
async def test_keeper_atlas_url_format():
    """`/atlas` URL-encodes galaxy names that contain spaces."""
    from cmds.voyager import VoyagerCog

    bot = MagicMock()
    cog = VoyagerCog(bot=bot)

    interaction = _make_fake_interaction()
    callback = _get_callback(cog, "atlas")
    await callback(cog, interaction, galaxy="Hilbert Dimension")

    embed = _extract_embed(interaction)

    image_url = embed.image.url
    assert image_url, f"embed.image.url is empty: {embed.to_dict()!r}"
    # Galaxy with space must be URL-encoded.
    assert "/api/posters/atlas/Hilbert%20Dimension.png" in image_url, (
        f"galaxy not URL-encoded in {image_url}"
    )
    assert re.search(r"[?&]v=\d+", image_url), (
        f"missing cache-buster in {image_url}"
    )

    page_url = embed.url
    assert page_url and page_url.endswith("/atlas/Hilbert%20Dimension"), (
        f"unexpected page URL: {page_url}"
    )


@pytest.mark.asyncio
@pytest.mark.p1
async def test_keeper_atlas_autocomplete_filters():
    """Atlas autocomplete returns substring matches, capped at 25."""
    from cmds.voyager import VoyagerCog, POPULAR_GALAXIES
    from discord import app_commands

    bot = MagicMock()
    cog = VoyagerCog(bot=bot)

    interaction = _make_fake_interaction()
    autocomplete = getattr(cog.atlas, "autocomplete", None)
    # discord.py exposes the registered autocomplete via the command's
    # internal map; try a couple of well-known accessors.
    callback = None
    for attr in ("_param_autocomplete", "autocomplete_handlers"):
        candidate = getattr(cog.atlas, attr, None)
        if isinstance(candidate, dict) and "galaxy" in candidate:
            callback = candidate["galaxy"]
            break
    if callback is None:
        # Fallback: cog.atlas_autocomplete is the bound method we wrote.
        callback = cog.atlas_autocomplete

    # Substring match — "hil" should hit "Hilbert Dimension".
    choices = await callback(interaction, "hil") if callable(callback) else []
    # Some discord.py versions wrap it; unwrap if needed.
    if callable(getattr(choices, "__await__", None)):
        choices = await choices

    assert isinstance(choices, list), f"expected list, got {type(choices)}"
    assert len(choices) <= 25, f"discord allows max 25 choices, got {len(choices)}"
    assert len(choices) >= 1, "expected at least one match for 'hil'"
    for c in choices:
        assert isinstance(c, app_commands.Choice)
        assert "hil" in c.name.lower(), f"non-matching choice: {c.name!r}"

    # Sanity: every choice's name+value comes from POPULAR_GALAXIES.
    pop_set = set(POPULAR_GALAXIES)
    for c in choices:
        assert c.name in pop_set, f"choice {c.name!r} not in POPULAR_GALAXIES"
        assert c.value in pop_set, f"value {c.value!r} not in POPULAR_GALAXIES"
