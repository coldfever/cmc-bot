"""Știri: urmărește fluxuri RSS (site-uri de știri TCG, YouTube etc.) și le postează în canale."""
from __future__ import annotations

import asyncio
import logging

import aiohttp
import discord
import feedparser
from discord import app_commands
from discord.ext import commands, tasks

log = logging.getLogger("cmc.news")


class News(commands.Cog):
    stiri = app_commands.Group(name="stiri", description="Fluxuri de știri automate", guild_only=True,
                               default_permissions=discord.Permissions(manage_guild=True))

    def __init__(self, bot):
        self.bot = bot
        self.poll.start()

    def cog_unload(self):
        self.poll.cancel()

    async def _fetch(self, url: str):
        async with aiohttp.ClientSession(headers={"User-Agent": "CMCDiscordBot/1.0"}, trust_env=True, timeout=aiohttp.ClientTimeout(total=20)) as s:
            async with s.get(url) as r:
                body = await r.read()
        return await asyncio.to_thread(feedparser.parse, body)

    @staticmethod
    def _entry_id(e) -> str:
        return e.get("id") or e.get("link") or e.get("title", "")

    @stiri.command(name="adauga", description="Adaugă un flux RSS care se postează automat într-un canal.")
    @app_commands.describe(url="Linkul RSS (ex: https://www.youtube.com/feeds/videos.xml?channel_id=...)", canal="Unde se postează", nume="Nume scurt")
    async def add(self, interaction: discord.Interaction, url: str, canal: discord.TextChannel, nume: str | None = None):
        await interaction.response.defer(ephemeral=True)
        try:
            feed = await self._fetch(url)
        except Exception:
            feed = None
        if not feed or not feed.entries:
            await interaction.followup.send("Nu am putut citi fluxul (sau e gol). Verifică linkul.", ephemeral=True)
            return
        name = nume or feed.feed.get("title", url)[:80]
        try:
            cur = await self.bot.db.execute(
                "INSERT INTO feeds(guild_id, url, channel_id, name, initialized) VALUES (?,?,?,?,1)",
                (interaction.guild.id, url, canal.id, name),
            )
        except Exception:
            await interaction.followup.send("Fluxul există deja pentru canalul ăsta.", ephemeral=True)
            return
        # marchează articolele existente ca văzute, ca să nu inundăm canalul
        await self.bot.db.executemany(
            "INSERT OR IGNORE INTO feed_seen(feed_id, entry_id) VALUES (?,?)",
            [(cur.lastrowid, self._entry_id(e)) for e in feed.entries],
        )
        await self.bot.db.commit()
        await interaction.followup.send(f"Gata: **{name}** → {canal.mention}. Se postează doar articolele noi.", ephemeral=True)

    @stiri.command(name="lista", description="Fluxurile urmărite.")
    async def list_(self, interaction: discord.Interaction):
        async with self.bot.db.execute("SELECT * FROM feeds WHERE guild_id = ?", (interaction.guild.id,)) as cur:
            rows = await cur.fetchall()
        text = "\n".join(f"#{r['id']} **{r['name']}** → <#{r['channel_id']}>\n{r['url']}" for r in rows) or "Niciun flux."
        await interaction.response.send_message(text[:1990], ephemeral=True)

    @stiri.command(name="sterge", description="Oprește un flux (id din /stiri lista).")
    async def remove(self, interaction: discord.Interaction, id: int):
        await self.bot.db.execute("DELETE FROM feeds WHERE id = ? AND guild_id = ?", (id, interaction.guild.id))
        await self.bot.db.execute("DELETE FROM feed_seen WHERE feed_id = ?", (id,))
        await self.bot.db.commit()
        await interaction.response.send_message("Șters.", ephemeral=True)

    @tasks.loop(minutes=15)
    async def poll(self):
        async with self.bot.db.execute("SELECT * FROM feeds") as cur:
            feeds = await cur.fetchall()
        for f in feeds:
            try:
                parsed = await self._fetch(f["url"])
            except Exception as e:  # rețea, timeout
                log.warning("Flux %s: %s", f["url"], e)
                continue
            guild = self.bot.get_guild(f["guild_id"])
            channel = guild and guild.get_channel(f["channel_id"])
            if channel is None:
                continue
            for e in reversed(parsed.entries[:10]):
                eid = self._entry_id(e)
                cur = await self.bot.db.execute("INSERT OR IGNORE INTO feed_seen(feed_id, entry_id) VALUES (?,?)", (f["id"], eid))
                if cur.rowcount == 0:
                    continue
                await self.bot.db.commit()
                title = e.get("title", "Articol nou")
                link = e.get("link", "")
                try:
                    await channel.send(f"📰 **{f['name']}** · {title}\n{link}")
                except discord.HTTPException:
                    pass
            await self.bot.db.commit()

    @poll.before_loop
    async def _wait(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(News(bot))
