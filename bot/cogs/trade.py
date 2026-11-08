"""Schimburi și vânzări: anunțuri cu format standard, expirare automată, reputație."""
from __future__ import annotations

import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .events import game_autocomplete

KINDS = {"vand": ("Vând", discord.Colour.green()), "cumpar": ("Cumpăr", discord.Colour.blue()),
         "schimb": ("Schimb", discord.Colour.purple()), "licitatie": ("Licitație", discord.Colour.gold())}
STARI = ["Mint", "Near Mint", "Excellent", "Good", "Played", "Poor", "Sigilat", "-"]


class Trade(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.expire.start()

    def cog_unload(self):
        self.expire.cancel()

    @app_commands.command(name="anunt-schimb", description="Postează un anunț de vânzare / cumpărare / schimb.")
    @app_commands.describe(
        tip="Ce vrei să faci", joc="Jocul", titlu="Ex: Charizard ex 199/165",
        detalii="Ce oferi / ce cauți, ediție, limbă etc.", stare="Starea cărților",
        pret="Preț sau buget (ex: 150 lei, negociabil)", poza="Poză (recomandat)",
    )
    @app_commands.choices(
        tip=[app_commands.Choice(name=v[0], value=k) for k, v in KINDS.items()],
        stare=[app_commands.Choice(name=s, value=s) for s in STARI],
    )
    @app_commands.autocomplete(joc=game_autocomplete)
    @app_commands.guild_only()
    async def post(self, interaction: discord.Interaction, tip: str, joc: str, titlu: app_commands.Range[str, 3, 90],
                   detalii: app_commands.Range[str, 3, 1500], stare: str = "-", pret: str | None = None,
                   poza: discord.Attachment | None = None):
        game = self.bot.cfg.game(joc)
        if game is None or not game.trade_channel:
            await interaction.response.send_message("Jocul nu are canal de schimburi.", ephemeral=True)
            return
        channel = self.bot.channel_by_name(interaction.guild, game.trade_channel, game.category)
        if channel is None:
            await interaction.response.send_message("Nu găsesc canalul de schimburi al jocului. Anunță staff-ul.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        label, colour = KINDS[tip]
        days = self.bot.cfg.trade_expiry_days
        embed = discord.Embed(title=f"[{label}] {titlu}", description=detalii, colour=colour)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        if stare != "-":
            embed.add_field(name="Stare", value=stare)
        if pret:
            embed.add_field(name="Preț", value=pret)
        rep = await self._rep_count(interaction.guild.id, interaction.user.id)
        embed.add_field(name="Reputație", value=f"⭐ {rep}")
        if poza:
            embed.set_image(url=poza.url)
        embed.set_footer(text=f"Expiră automat în {days} zile · autorul închide cu /finalizat · contact: răspunde aici sau DM")

        name = f"[{label}] {titlu}"[:100]
        if isinstance(channel, discord.ForumChannel):
            tag = discord.utils.get(channel.available_tags, name=label)
            tw = await channel.create_thread(
                name=name, embed=embed, applied_tags=[tag] if tag else [],
                content=interaction.user.mention, allowed_mentions=discord.AllowedMentions.none(),
            )
            thread, message = tw.thread, tw.message
        else:
            message = await channel.send(embed=embed)
            thread = await message.create_thread(name=name, auto_archive_duration=10080)
            await thread.add_user(interaction.user)
        await self.bot.db.execute(
            "INSERT INTO trades(guild_id, channel_id, thread_id, message_id, user_id, kind, title, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (interaction.guild.id, channel.id, thread.id, message.id, interaction.user.id, tip, titlu, int(time.time())),
        )
        await self.bot.db.commit()
        await interaction.followup.send(f"Anunț postat: {thread.mention}", ephemeral=True)

    @app_commands.command(name="finalizat", description="Închide anunțul tău de schimb (folosește comanda în firul anunțului).")
    @app_commands.guild_only()
    async def close(self, interaction: discord.Interaction):
        async with self.bot.db.execute("SELECT * FROM trades WHERE thread_id = ? AND closed = 0", (interaction.channel_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            await interaction.response.send_message("Comanda merge doar în firul unui anunț deschis.", ephemeral=True)
            return
        is_staff = interaction.user.guild_permissions.manage_messages
        if row["user_id"] != interaction.user.id and not is_staff:
            await interaction.response.send_message("Doar autorul anunțului (sau staff-ul) îl poate închide.", ephemeral=True)
            return
        await interaction.response.send_message("✅ Anunț finalizat. Nu uitați de `/rep` dacă tranzacția a mers bine!")
        await self._close_thread(row, "Finalizat")

    async def _close_thread(self, row, tag_name: str):
        await self.bot.db.execute("UPDATE trades SET closed = 1 WHERE id = ?", (row["id"],))
        await self.bot.db.commit()
        guild = self.bot.get_guild(row["guild_id"])
        if guild is None:
            return
        thread = guild.get_thread(row["thread_id"])
        if thread is None:
            try:
                thread = await guild.fetch_channel(row["thread_id"])
            except discord.HTTPException:
                return
        kwargs = {"archived": True, "locked": True}
        if isinstance(thread.parent, discord.ForumChannel):
            tag = discord.utils.get(thread.parent.available_tags, name=tag_name)
            if tag:
                kwargs["applied_tags"] = (list(thread.applied_tags) + [tag])[:5]
        try:
            await thread.edit(**kwargs)
        except discord.HTTPException:
            pass

    @tasks.loop(hours=6)
    async def expire(self):
        limit = int(time.time()) - self.bot.cfg.trade_expiry_days * 86400
        async with self.bot.db.execute("SELECT * FROM trades WHERE closed = 0 AND created_at < ?", (limit,)) as cur:
            rows = await cur.fetchall()
        for row in rows:
            guild = self.bot.get_guild(row["guild_id"])
            thread = guild and guild.get_thread(row["thread_id"])
            if thread:
                try:
                    await thread.send(f"⌛ Anunțul a expirat după {self.bot.cfg.trade_expiry_days} zile. <@{row['user_id']}>, poți posta din nou cu `/anunt-schimb`.")
                except discord.HTTPException:
                    pass
            await self._close_thread(row, "Finalizat")

    @expire.before_loop
    async def _wait(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------ reputație
    async def _rep_count(self, guild_id: int, user_id: int) -> int:
        async with self.bot.db.execute("SELECT COUNT(*) AS n FROM reputation WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)) as cur:
            return (await cur.fetchone())["n"]

    @app_commands.command(name="rep", description="Dă +1 reputație cuiva după o tranzacție reușită.")
    @app_commands.describe(membru="Cu cine ai făcut schimbul", nota="Ex: schimb rapid, cărți exact ca în poză")
    @app_commands.guild_only()
    async def rep(self, interaction: discord.Interaction, membru: discord.Member, nota: str | None = None):
        if membru.id == interaction.user.id or membru.bot:
            await interaction.response.send_message("Nu poți da reputație ție sau unui bot.", ephemeral=True)
            return
        week = int(time.time()) - 7 * 86400
        async with self.bot.db.execute(
            "SELECT 1 FROM reputation WHERE guild_id = ? AND user_id = ? AND giver_id = ? AND created_at > ?",
            (interaction.guild.id, membru.id, interaction.user.id, week),
        ) as cur:
            if await cur.fetchone():
                await interaction.response.send_message("I-ai dat deja reputație săptămâna asta.", ephemeral=True)
                return
        await self.bot.db.execute(
            "INSERT INTO reputation(guild_id, user_id, giver_id, note, created_at) VALUES (?,?,?,?,?)",
            (interaction.guild.id, membru.id, interaction.user.id, nota, int(time.time())),
        )
        await self.bot.db.commit()
        total = await self._rep_count(interaction.guild.id, membru.id)
        await interaction.response.send_message(f"⭐ {interaction.user.mention} → {membru.mention} (+1, total {total}) {('· ' + nota) if nota else ''}")

    @app_commands.command(name="reputatie", description="Vezi reputația unui membru.")
    @app_commands.guild_only()
    async def reputation(self, interaction: discord.Interaction, membru: discord.Member):
        total = await self._rep_count(interaction.guild.id, membru.id)
        async with self.bot.db.execute(
            "SELECT giver_id, note, created_at FROM reputation WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 5",
            (interaction.guild.id, membru.id),
        ) as cur:
            rows = await cur.fetchall()
        lines = [f"<t:{r['created_at']}:d> de la <@{r['giver_id']}> {('· ' + r['note']) if r['note'] else ''}" for r in rows]
        embed = discord.Embed(title=f"⭐ {membru.display_name}: {total}", description="\n".join(lines) or "Nicio recenzie încă.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Trade(bot))
