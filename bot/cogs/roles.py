"""Panou de alegere a jocurilor (roluri) în #alege-jocurile, cu meniuri care rămân active după restart."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class GameSelect(discord.ui.Select):
    def __init__(self, bot, competitive: bool):
        self.bot = bot
        self.competitive = competitive
        games = [g for g in bot.cfg.games if (g.competitive_role if competitive else True)]
        options = [
            discord.SelectOption(label=(g.competitive_role if competitive else g.name), value=g.key, emoji=g.emoji or None)
            for g in games
        ][:25]
        super().__init__(
            custom_id="cmc:roles:competitive" if competitive else "cmc:roles:games",
            placeholder=("Notificări de turnee (competitiv)…" if competitive else "Ce jocuri joci?"),
            min_values=0,
            max_values=len(options),
            options=options,
        )

    def _role_name(self, g) -> str | None:
        return g.competitive_role if self.competitive else g.role

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        guild = interaction.guild
        assert isinstance(member, discord.Member) and guild is not None
        chosen = set(self.values)
        add, remove, missing = [], [], []
        for g in self.bot.cfg.games:
            name = self._role_name(g)
            if not name:
                continue
            role = discord.utils.get(guild.roles, name=name)
            if role is None:
                if g.key in chosen:
                    missing.append(name)
                continue
            if g.key in chosen and role not in member.roles:
                add.append(role)
            elif g.key not in chosen and role in member.roles:
                remove.append(role)
        try:
            if add:
                await member.add_roles(*add, reason="Alegere jocuri")
            if remove:
                await member.remove_roles(*remove, reason="Alegere jocuri")
        except discord.Forbidden:
            await interaction.response.send_message(
                "Nu pot modifica rolurile. Rolul botului trebuie să fie deasupra rolurilor de joc (Setări server → Roluri).",
                ephemeral=True,
            )
            return
        parts = []
        if add:
            parts.append("Adăugat: " + ", ".join(r.name for r in add))
        if remove:
            parts.append("Scos: " + ", ".join(r.name for r in remove))
        if missing:
            parts.append("Roluri inexistente (anunță staff-ul): " + ", ".join(missing))
        await interaction.response.send_message("\n".join(parts) or "Nicio schimbare.", ephemeral=True)


class RolesView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.add_item(GameSelect(bot, competitive=False))
        if any(g.competitive_role for g in bot.cfg.games):
            self.add_item(GameSelect(bot, competitive=True))


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(RolesView(bot))

    @app_commands.command(name="panou-roluri", description="Postează panoul de alegere a jocurilor în #alege-jocurile.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def post_panel(self, interaction: discord.Interaction):
        guild = interaction.guild
        channel = self.bot.bot_channel(guild, "alege_jocuri") or interaction.channel
        lines = "\n".join(f"{g.emoji} **{g.name}**" for g in self.bot.cfg.games)
        embed = discord.Embed(
            title="Alege jocurile pe care le joci",
            description=(
                "Selectează din primul meniu jocurile tale ca să primești acces la canalele lor.\n"
                "Din al doilea meniu alegi dacă vrei ping la turneele competitive.\n"
                "Poți schimba oricând: debifezi și rolul se scoate.\n\n" + lines
            ),
            colour=discord.Colour.blurple(),
        )
        await channel.send(embed=embed, view=RolesView(self.bot))
        await interaction.response.send_message(f"Panou postat în {channel.mention}.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Roles(bot))
