"""Comenzi utile pentru staff: regulament, mesaje oficiale, verificare bot."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

REGULAMENT = """**Regulament Critical Miss Club**

**1. Respect.** Fără insulte, hărțuire, discriminare sau spam. Suntem aici să ne distrăm.
**2. Canalul potrivit.** Discuțiile despre un joc merg în categoria jocului; off-topic în #off-topic.
**3. Fără conținut NSFW, politică sau reclame** la alte magazine/servere fără acordul staff-ului.
**4. Turnee.** Înscrierea se face cu butoanele din anunț. Dacă nu mai poți veni, apasă „Nu vin” ca să eliberezi locul.
**5. Decizia staff-ului și a judge-ului** la turnee este finală.

**Schimburi și vânzări**
• Folosiți `/anunt-schimb` în canalul jocului, cu poză și stare reală a cărților.
• Fără proxy-uri sau contrafaceri vândute ca originale.
• Clubul nu garantează tranzacțiile private. Recomandăm schimbul în persoană, la club.
• După o tranzacție reușită dați `/rep` celuilalt. Țepele se raportează staff-ului.
• Anunțurile expiră automat; închideți-le cu `/finalizat` când ați vândut.

Problemă? Scrieți unui membru **Staff**."""


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="posteaza-regulament", description="Postează regulamentul standard în #regulament.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def rules(self, interaction: discord.Interaction):
        channel = self.bot.bot_channel(interaction.guild, "regulament") or interaction.channel
        await channel.send(embed=discord.Embed(description=REGULAMENT, colour=discord.Colour.red()))
        await interaction.response.send_message(f"Postat în {channel.mention}. Îl poți edita din `bot/cogs/admin.py`.", ephemeral=True)

    @app_commands.command(name="anunta", description="Trimite un anunț oficial (embed) ca bot.")
    @app_commands.describe(canal="Unde", titlu="Titlul", text="Textul (\\n pentru rând nou)", ping_everyone="Ping @everyone")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def announce(self, interaction: discord.Interaction, canal: discord.TextChannel, titlu: str, text: str,
                       ping_everyone: bool = False, poza: discord.Attachment | None = None):
        embed = discord.Embed(title=titlu, description=text.replace("\\n", "\n"), colour=discord.Colour.blurple())
        if poza:
            embed.set_image(url=poza.url)
        await canal.send(content="@everyone" if ping_everyone else None, embed=embed,
                         allowed_mentions=discord.AllowedMentions(everyone=ping_everyone))
        await interaction.response.send_message("Trimis.", ephemeral=True)

    @app_commands.command(name="verifica-bot", description="Verifică dacă botul are tot ce îi trebuie pe server.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def check(self, interaction: discord.Interaction):
        guild = interaction.guild
        me = guild.me
        lines = []
        perms = me.guild_permissions
        for p, label in [("administrator", "Administrator"), ("manage_roles", "Manage Roles"), ("manage_channels", "Manage Channels"),
                         ("manage_events", "Manage Events"), ("manage_threads", "Manage Threads")]:
            lines.append(f"{'✅' if getattr(perms, p) else '❌'} {label}")
        lines.append(f"{'✅' if 'COMMUNITY' in guild.features else '⚠️'} Server Community (necesar pentru forumuri)")
        game_roles = [discord.utils.get(guild.roles, name=g.role) for g in self.bot.cfg.games]
        too_high = [r.name for r in game_roles if r and r >= me.top_role]
        lines.append("✅ Rolul botului e deasupra rolurilor de joc" if not too_high else f"❌ Mută rolul botului deasupra: {', '.join(too_high)}")
        for purpose, name in self.bot.cfg.bot_channels.items():
            ok = self.bot.bot_channel(guild, purpose) is not None
            lines.append(f"{'✅' if ok else '❌'} canal #{name}")
        lines.append(f"{'✅' if self.bot.intents.members else '❌'} Server Members Intent")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
