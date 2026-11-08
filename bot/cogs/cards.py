"""/card – caută o carte (Magic prin Scryfall, Pokemon prin pokemontcg.io)."""
from __future__ import annotations

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

HEADERS = {"User-Agent": "CMCDiscordBot/1.0", "Accept": "application/json"}


class Cards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession(headers=HEADERS, trust_env=True, timeout=aiohttp.ClientTimeout(total=15))

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    async def magic(self, name: str) -> discord.Embed | None:
        async with self.session.get("https://api.scryfall.com/cards/named", params={"fuzzy": name}) as r:
            if r.status != 200:
                return None
            c = await r.json()
        face = c["card_faces"][0] if "image_uris" not in c and c.get("card_faces") else c
        embed = discord.Embed(title=c["name"], url=c.get("scryfall_uri"), description=face.get("oracle_text", ""), colour=0x8338EC)
        embed.add_field(name="Tip", value=face.get("type_line", "-"))
        embed.add_field(name="Set", value=f"{c.get('set_name')} ({c.get('set', '').upper()})")
        prices = c.get("prices", {})
        price = " / ".join(p for p in [prices.get("eur") and f"€{prices['eur']}", prices.get("usd") and f"${prices['usd']}"] if p)
        if price:
            embed.add_field(name="Preț", value=price)
        img = (face.get("image_uris") or c.get("image_uris") or {}).get("normal")
        if img:
            embed.set_image(url=img)
        embed.set_footer(text="Scryfall")
        return embed

    async def pokemon(self, name: str) -> discord.Embed | None:
        q = f'name:"{name.replace(chr(34), "")}"'
        async with self.session.get("https://api.pokemontcg.io/v2/cards",
                                    params={"q": q, "pageSize": 1, "orderBy": "-set.releaseDate"}) as r:
            if r.status != 200:
                return None
            data = (await r.json()).get("data") or []
        if not data:
            return None
        c = data[0]
        embed = discord.Embed(title=c["name"], url=(c.get("cardmarket") or {}).get("url"), colour=0xFFCB05)
        embed.add_field(name="Set", value=f"{c['set']['name']} · {c.get('number')}/{c['set'].get('printedTotal')}")
        if c.get("rarity"):
            embed.add_field(name="Raritate", value=c["rarity"])
        cm = (c.get("cardmarket") or {}).get("prices") or {}
        if cm.get("averageSellPrice"):
            embed.add_field(name="Preț mediu Cardmarket", value=f"€{cm['averageSellPrice']}")
        if c.get("images", {}).get("large"):
            embed.set_image(url=c["images"]["large"])
        embed.set_footer(text="pokemontcg.io · ultima ediție cu acest nume")
        return embed

    @app_commands.command(name="card", description="Caută o carte și prețul ei.")
    @app_commands.choices(joc=[
        app_commands.Choice(name="Magic", value="magic"),
        app_commands.Choice(name="Pokemon", value="pokemon"),
    ])
    async def card(self, interaction: discord.Interaction, joc: str, nume: str):
        await interaction.response.defer()
        try:
            embed = await (self.magic(nume) if joc == "magic" else self.pokemon(nume))
        except (aiohttp.ClientError, TimeoutError):
            embed = None
            await interaction.followup.send("Serviciul de căutare nu răspunde acum. Încearcă mai târziu.")
            return
        if embed is None:
            await interaction.followup.send(f"Nu am găsit „{nume}”.")
        else:
            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Cards(bot))
