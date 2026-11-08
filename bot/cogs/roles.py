"""Acces pe server:
1. #regulament – butonul „Accept regulamentul” dă rolul Membru (deblochează serverul).
2. #alege-jocurile – câte o iconiță (buton) pentru fiecare joc; apăsarea pune/scoate rolul.
Butoanele rămân funcționale și după repornirea botului.
"""
from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands


# ---------------------------------------------------------------- regulament
class AcceptRulesButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cmc:rules:accept"):
    def __init__(self):
        super().__init__(discord.ui.Button(label="Am citit și accept regulamentul", emoji="✅",
                                           style=discord.ButtonStyle.success, custom_id="cmc:rules:accept"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls()

    async def callback(self, interaction: discord.Interaction):
        bot = interaction.client
        guild, member = interaction.guild, interaction.user
        role = bot.find_role(guild, bot.cfg.member_role)
        if role is None:
            await interaction.response.send_message("Rolul de membru nu există încă. Anunță staff-ul.", ephemeral=True)
            return
        pick = bot.bot_channel(guild, "alege_jocuri")
        where = f" Acum alege-ți jocurile în {pick.mention}." if pick else ""
        if role in member.roles:
            await interaction.response.send_message(f"Ai acceptat deja regulamentul.{where}", ephemeral=True)
            return
        try:
            await member.add_roles(role, reason="A acceptat regulamentul")
        except discord.Forbidden:
            await interaction.response.send_message("Nu pot da rolul. Anunță staff-ul (rolul botului trebuie să fie mai sus).", ephemeral=True)
            return
        await interaction.response.send_message(f"Bine ai venit în Critical Miss Club! 🎲{where}", ephemeral=True)


def rules_view() -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(AcceptRulesButton())
    return view


# ---------------------------------------------------------------- jocuri
class GameRoleButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cmc:role:(?P<key>[a-z0-9_]+):(?P<kind>g|c)"):
    def __init__(self, key: str, kind: str, label: str = "", emoji: str | None = None):
        style = discord.ButtonStyle.secondary if kind == "g" else discord.ButtonStyle.primary
        super().__init__(discord.ui.Button(label=label or key, emoji=emoji, style=style, custom_id=f"cmc:role:{key}:{kind}"))
        self.key, self.kind = key, kind

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["key"], match["kind"])

    async def callback(self, interaction: discord.Interaction):
        bot = interaction.client
        game = bot.cfg.game(self.key)
        if game is None:
            await interaction.response.send_message("Jocul nu mai există în configurare.", ephemeral=True)
            return
        name = game.role if self.kind == "g" else game.competitive_role
        role = bot.find_role(interaction.guild, name)
        member = interaction.user
        if role is None:
            await interaction.response.send_message(f"Rolul `{name}` nu există. Anunță staff-ul.", ephemeral=True)
            return
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Panou jocuri")
                msg = f"❎ Am scos **{role.name}**."
            else:
                await member.add_roles(role, reason="Panou jocuri")
                msg = f"✅ Ai primit **{role.name}**."
                if self.kind == "g":
                    msg += " Canalele jocului au apărut în listă."
                else:
                    msg += " Vei primi ping la turneele competitive."
        except discord.Forbidden:
            await interaction.response.send_message("Nu pot modifica rolul. Anunță staff-ul.", ephemeral=True)
            return
        await interaction.response.send_message(msg + " (apasă din nou ca să anulezi)", ephemeral=True)


def games_view(cfg, kind: str) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for g in cfg.games[:25]:
        if kind == "g":
            view.add_item(GameRoleButton(g.key, "g", g.name, g.emoji or None))
        elif g.competitive_role:
            view.add_item(GameRoleButton(g.key, "c", g.name, "🏆"))
    return view


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_dynamic_items(AcceptRulesButton, GameRoleButton)

    @app_commands.command(name="panou-roluri", description="Postează iconițele de alegere a jocurilor în #alege-jocurile.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def post_panel(self, interaction: discord.Interaction):
        cfg = self.bot.cfg
        channel = self.bot.bot_channel(interaction.guild, "alege_jocuri") or interaction.channel
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title="🃏 Ce jocuri joci?",
            description=(
                "Ca să nu fie serverul aglomerat, canalele fiecărui joc se văd doar de cine le alege.\n"
                "**Apasă pe iconița jocului** ca să-i vezi canalele. Apasă din nou ca să le ascunzi.\n"
                "Poți alege oricâte jocuri."
            ),
            colour=discord.Colour.blurple(),
        )
        await channel.send(embed=embed, view=games_view(cfg, "g"))
        if any(g.competitive_role for g in cfg.games):
            comp = discord.Embed(
                title="🏆 Notificări turnee",
                description="Vrei ping când se anunță un turneu competitiv? Apasă pe jocurile pentru care vrei notificări.",
                colour=discord.Colour.gold(),
            )
            await channel.send(embed=comp, view=games_view(cfg, "c"))
        await interaction.followup.send(f"Panou postat în {channel.mention}.", ephemeral=True)

    @app_commands.command(name="membri-existenti", description="Dă rolul Membru tuturor celor care sunt deja pe server.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def grant_existing(self, interaction: discord.Interaction):
        guild = interaction.guild
        role = self.bot.find_role(guild, self.bot.cfg.member_role)
        if role is None:
            await interaction.response.send_message("Rolul Membru nu există. Rulează întâi /configureaza-server.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        todo = [m for m in guild.members if not m.bot and role not in m.roles]
        done = 0
        for m in todo:
            try:
                await m.add_roles(role, reason="Membru existent înainte de verificare")
                done += 1
            except discord.HTTPException:
                pass
            await asyncio.sleep(0.3)
        await interaction.followup.send(f"Am dat rolul **{role.name}** la {done} membri.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Roles(bot))
