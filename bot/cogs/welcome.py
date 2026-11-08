"""Mesaj de bun venit pentru membrii noi."""
from __future__ import annotations

import discord
from discord.ext import commands


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def build_embed(self, member: discord.Member) -> discord.Embed:
        guild = member.guild
        rules = self.bot.bot_channel(guild, "regulament")
        pick = self.bot.bot_channel(guild, "alege_jocuri")
        events = self.bot.bot_channel(guild, "evenimente")
        desc = [f"Salut {member.mention}, bine ai venit în **Critical Miss Club**! 🎲"]
        if rules:
            desc.append(f"📜 Citește {rules.mention}")
        if pick:
            desc.append(f"🃏 Alege-ți jocurile în {pick.mention}")
        if events:
            desc.append(f"📅 Vezi turneele și serile de joc în {events.mention}")
        embed = discord.Embed(description="\n".join(desc), colour=discord.Colour.green())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Membrul #{guild.member_count}")
        return embed

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != self.bot.guild_id or member.bot:
            return
        channel = self.bot.bot_channel(member.guild, "bun_venit")
        if channel:
            await channel.send(embed=self.build_embed(member))


async def setup(bot):
    await bot.add_cog(Welcome(bot))
