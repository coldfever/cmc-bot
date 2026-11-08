"""Log de moderare în #mod-log: mesaje șterse/editate, intrări și ieșiri."""
from __future__ import annotations

import discord
from discord.ext import commands


class ModLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _log_channel(self, guild: discord.Guild | None):
        if guild is None or guild.id != self.bot.guild_id:
            return None
        return self.bot.bot_channel(guild, "mod_log")

    async def _send(self, guild, embed):
        ch = self._log_channel(guild)
        if ch:
            try:
                await ch.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if message.channel == self._log_channel(message.guild):
            return
        e = discord.Embed(title="🗑️ Mesaj șters", description=(message.content or "*(fără text)*")[:3500], colour=discord.Colour.red())
        e.add_field(name="Autor", value=message.author.mention)
        e.add_field(name="Canal", value=message.channel.mention)
        if message.attachments:
            e.add_field(name="Atașamente", value="\n".join(a.filename for a in message.attachments)[:1000], inline=False)
        await self._send(message.guild, e)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.guild is None or before.content == after.content:
            return
        e = discord.Embed(title="✏️ Mesaj editat", colour=discord.Colour.orange(), url=after.jump_url)
        e.add_field(name="Înainte", value=(before.content or "-")[:1000], inline=False)
        e.add_field(name="După", value=(after.content or "-")[:1000], inline=False)
        e.add_field(name="Autor", value=before.author.mention)
        e.add_field(name="Canal", value=before.channel.mention)
        await self._send(before.guild, e)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        e = discord.Embed(description=f"📥 {member.mention} a intrat (cont creat <t:{int(member.created_at.timestamp())}:R>)", colour=discord.Colour.green())
        await self._send(member.guild, e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        e = discord.Embed(description=f"📤 {member} a ieșit", colour=discord.Colour.dark_grey())
        await self._send(member.guild, e)


async def setup(bot):
    await bot.add_cog(ModLog(bot))
