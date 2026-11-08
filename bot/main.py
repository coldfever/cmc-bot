"""Punctul de pornire al botului Critical Miss Club."""
from __future__ import annotations

import asyncio
import logging
import sys

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from . import db as database
from .config import Config, env

log = logging.getLogger("cmc")

COGS = [
    "bot.cogs.setup_server",
    "bot.cogs.roles",
    "bot.cogs.welcome",
    "bot.cogs.events",
    "bot.cogs.trade",
    "bot.cogs.cards",
    "bot.cogs.news",
    "bot.cogs.modlog",
    "bot.cogs.admin",
]


class CMCBot(commands.Bot):
    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        intents.members = True          # pentru mesajul de bun venit (activează în Developer Portal)
        intents.message_content = True  # pentru logul de mesaje șterse/editate (activează în Developer Portal)
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.guild_id = guild_id
        self.cfg = Config()
        self.db = None

    async def setup_hook(self) -> None:
        self.db = await database.connect()
        self.tree.on_error = self.on_app_command_error
        for ext in COGS:
            await self.load_extension(ext)
        guild = discord.Object(id=self.guild_id)
        # Comenzile se înregistrează doar pe serverul CMC: apar imediat, nu după o oră.
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        log.info("Sincronizat %d comenzi pe serverul %s", len(synced), self.guild_id)

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            text = "Nu ai permisiunea pentru comanda asta."
        elif isinstance(error, app_commands.CheckFailure):
            text = "Nu poți folosi comanda aici."
        else:
            log.exception("Eroare la comanda %s", interaction.command and interaction.command.name, exc_info=error)
            text = "A apărut o eroare. Staff-ul o poate vedea în logurile Railway."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=True)
            else:
                await interaction.response.send_message(text, ephemeral=True)
        except discord.HTTPException:
            pass

    async def on_ready(self) -> None:
        log.info("Conectat ca %s (id %s)", self.user, self.user.id if self.user else "?")
        if self.get_guild(self.guild_id) is None:
            log.error("Botul NU este pe serverul %s. Invită-l folosind linkul din ghid.", self.guild_id)

    def cmc_guild(self) -> discord.Guild | None:
        return self.get_guild(self.guild_id)

    def channel_by_name(self, guild: discord.Guild, name: str | None, category: str | None = None):
        if not name:
            return None
        for ch in guild.channels:
            if ch.name == name and (category is None or (ch.category and ch.category.name == category)):
                return ch
        return None

    @staticmethod
    def norm(name: str) -> str:
        """Nume comparabil: fără majuscule, spații, liniuțe, bare sau emoji."""
        return "".join(ch for ch in name.lower() if ch.isalnum())

    def find_role(self, guild: discord.Guild, name: str | None) -> discord.Role | None:
        if not name:
            return None
        exact = discord.utils.get(guild.roles, name=name)
        return exact or next((r for r in guild.roles if self.norm(r.name) == self.norm(name)), None)

    def bot_channel(self, guild: discord.Guild, purpose: str):
        return self.channel_by_name(guild, self.cfg.channel_name(purpose))

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
        await super().close()


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    token = env("DISCORD_TOKEN")
    guild_id = env("GUILD_ID", "1461340905385492545")
    if not token:
        print("Lipsește DISCORD_TOKEN. Pune-l în variabilele de mediu (Railway → Variables).", file=sys.stderr)
        sys.exit(1)
    bot = CMCBot(int(guild_id))
    asyncio.run(bot.start(token))


if __name__ == "__main__":
    main()
